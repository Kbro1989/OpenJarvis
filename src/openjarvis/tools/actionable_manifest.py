"""Normalize Jarvis tools and user-facing action words into one actionable manifest.

This module scans registered ``BaseTool`` implementations and emits a
deterministic, serializable list of actionable usages. The manifest is meant
to be consumed by the Ollama serve path so local CLI requests can resolve
text-to-action without ad-hoc prompt injection strings.

Output shape per entry:
    {
        "tool": str,
        "aliases": list[str],
        "category": str,
        "description": str,
        "action_words": list[str],
        "pass_type": str,
        "usage_examples": list[str],
    }

Pass types are normalized from internal docstrings/spec metadata to one of:
    shell, browser, filesystem, retrieval, structured_output,
    audio, messaging, knowledge, inter_agent, system
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools._stubs import BaseTool

# Aliases/normalizations for tool names and common typed commands.
_TOOL_ALIASES: dict[str, list[str]] = {
    "shell_exec": ["run", "execute", "cmd", "command", "shell", "bash", "powershell"],
    "docker_shell_exec": ["docker", "container", "sandbox"],
    "file_read": ["read", "open", "cat", "view", "inspect"],
    "file_write": ["write", "save", "create", "edit text"],
    "apply_patch": ["patch", "diff", "unified", "modify"],
    "git_commit": ["commit", "checkin"],
    "git_status": ["status", "branch", "repo state"],
    "git_diff": ["diff", "changes"],
    "git_log": ["log", "history", "commits"],
    "code_interpreter": ["python", "run code", "interpret", "exec"],
    "code_interpreter_docker": ["sandbox python", "container code"],
    "repl": ["repl", "interactive", "python shell"],
    "web_search": ["search", "look up", "search web", "find"],
    "browser_navigate": ["open url", "browse", "navigate"],
    "browser_click": ["click"],
    "browser_type": ["type"],
    "browser_screenshot": ["screenshot", "capture"],
    "browser_extract": ["extract", "scrape"],
    "http_request": ["request", "http", "api call", "fetch url"],
    "pdf_extract": ["pdf", "extract pdf"],
    "image_generate": ["image", "draw", "generate image"],
    "audio_transcribe": ["transcribe", "audio", "speech to text"],
    "calculator": ["calculate", "math", "compute"],
    "retrieval": ["memory", "recall", "context", "retrieve"],
    "memory_search": ["search memory", "memory search"],
    "memory_store": ["store memory", "remember"],
    "memory_index": ["index memory", "ingest"],
    "knowledge_search": ["knowledge search", "kg search"],
    "knowledge_sql": ["sql", "knowledge sql"],
    "db_query": ["query db", "database"],
    "think": ["think", "reason"],
    "text_to_speech": ["tts", "speak", "voice"],
    "digest_collect": ["digest", "daily digest", "morning digest"],
    "channel_send": ["send message", "send channel"],
    "channel_list": ["list channels"],
    "channel_status": ["channel status"],
    "agent_spawn": ["spawn agent", "new agent"],
    "agent_send": ["send agent", "message agent"],
    "agent_list": ["list agents"],
    "agent_kill": ["kill agent", "stop agent"],
    "llm": ["llm", "ask model", "call model"],
}

# Pass type inference from tool name/category keywords.
_PASS_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("shell_exec", "docker_shell_exec", "repl", "code_interpreter"), "shell"),
    (("browser_", "http_request"), "browser"),
    (("file_read", "file_write", "apply_patch", "pdf_extract"), "filesystem"),
    (("retrieval", "memory_search", "memory_store", "memory_index"), "retrieval"),
    (("knowledge_search", "knowledge_sql", "db_query"), "knowledge"),
    (("text_to_speech", "audio_transcribe"), "audio"),
    (("channel_send", "channel_list", "channel_status"), "messaging"),
    (("agent_spawn", "agent_send", "agent_list", "agent_kill"), "inter_agent"),
    (("digest_collect",), "structured_output"),
    (("think",), "structured_output"),
    (("calculator", "llm"), "structured_output"),
]


def _infer_pass_type(name: str, category: str) -> str:
    lowered = name.lower()
    for hints, pass_type in _PASS_HINTS:
        if any(lowered.startswith(h) or lowered == h for h in hints):
            return pass_type
    if category:
        cat_lowered = category.lower()
        mapping = {
            "browser": "browser",
            "files": "filesystem",
            "memory": "retrieval",
            "knowledge": "knowledge",
            "voice": "audio",
            "messaging": "messaging",
            "agents": "inter_agent",
        }
        for key, value in mapping.items():
            if key in cat_lowered:
                return value
    return "system"


def _extract_action_words(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9_+/()-]{2,}", lowered)
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "have", "into",
        "your", "request", "content", "optional", "default", "example", "using",
    }
    dedup = []
    seen = set()
    for word in words:
        if word not in stop and word not in seen:
            seen.add(word)
            dedup.append(word)
    return dedup[:24]


def _examples_from_spec(spec: Any) -> list[str]:
    examples: list[str] = []
    params = getattr(spec, "parameters", None) or {}
    properties = params.get("properties", {}) if isinstance(params, dict) else {}
    for key, value in properties.items():
        if isinstance(value, dict):
            desc = value.get("description") or value.get("title") or ""
            if desc:
                examples.append(f"{key}: {desc}")
        if len(examples) >= 5:
            break
    return examples


def build_actionable_manifest() -> dict[str, Any]:
    """Return the normalized actionable manifest as a serializable dict."""
    entries: list[dict[str, Any]] = []
    aliases = {k.lower(): v for k, v in _TOOL_ALIASES.items()}
    seen_tools: set[str] = set()
    for key, entry in ToolRegistry.items():
        try:
            tool = entry() if callable(entry) else entry
        except Exception:
            continue
        if not isinstance(tool, BaseTool):
            continue
        spec = tool.spec
        name = spec.name
        if not name or name in seen_tools:
            continue
        seen_tools.add(name)
        description = spec.description or name
        action_words = _extract_action_words(description)
        extra_aliases = aliases.get(name.lower(), [])
        lookup_key = name.lower().split("_")[0]
        for alias_key, alias_values in aliases.items():
            if alias_key.startswith(lookup_key):
                extra_aliases.extend(alias_values)
        extra_aliases = list(dict.fromkeys(extra_aliases))
        entries.append(
            {
                "tool": name,
                "aliases": extra_aliases[:32],
                "category": spec.category or "",
                "description": description.strip(),
                "action_words": action_words,
                "pass_type": _infer_pass_type(name, spec.category or ""),
                "usage_examples": _examples_from_spec(spec),
            }
        )
    manifest = {
        "hash": hashlib.sha256(
            json.dumps(entries, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
        "count": len(entries),
        "entries": entries,
    }
    return manifest


def write_actionable_manifest(path: str | Path) -> Path:
    """Write the manifest to disk and return the written path."""
    manifest = build_actionable_manifest()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def load_actionable_manifest(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return build_actionable_manifest()
    return json.loads(target.read_text(encoding="utf-8"))


def resolve_action(text: str, manifest: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Pick the best actionable entry for a text snippet from the manifest."""
    if manifest is None:
        manifest = build_actionable_manifest()
    lowered = text.lower()
    best: tuple[int, dict[str, Any]] | None = None
    for entry in manifest.get("entries", []):
        score = 0
        for alias in entry.get("aliases", []):
            if alias in lowered:
                score += 3
        for word in entry.get("action_words", []):
            if word in lowered:
                score += 2
        name = entry.get("tool", "")
        if name and name.lower() in lowered:
            score += 5
        if not score:
            continue
        if best is None or score > best[0]:
            best = (score, entry)
    return best[1] if best else None
