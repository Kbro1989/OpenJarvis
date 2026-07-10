"""Direct cloud API router — bypasses the engine system entirely.

Reads API keys from the process environment, with a legacy
~/.openjarvis/cloud-keys.env fallback for non-desktop/manual setups. Uses
httpx directly so no cloud SDK packages are required.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from openjarvis.core.paths import get_config_dir
from openjarvis.core.types import Message

# ---------------------------------------------------------------------------
# Key / provider detection
# ---------------------------------------------------------------------------

_CLOUD_ENV_FILE = get_config_dir() / "cloud-keys.env"

_OPENAI_PREFIXES = ("gpt-", "o1-", "o3-", "o4-", "chatgpt-")
_ANTHROPIC_PREFIXES = ("claude-",)
_GOOGLE_PREFIXES = ("gemini-",)
_MINIMAX_PREFIXES = ("MiniMax-",)
_STEPFUN_PREFIXES = ("stepfun/",)

# HuggingFace orgs that host local-only quantised models — never route to cloud.
_LOCAL_HF_ORGS = (
    "mlx-community/",
    "bartowski/",
    "unsloth/",
    "lmstudio-community/",
)


def _load_keys() -> dict[str, str]:
    """Read available cloud keys every call so live updates are picked up."""
    keys: dict[str, str] = {}
    if _CLOUD_ENV_FILE.exists():
        for raw in _CLOUD_ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "MINIMAX_API_KEY",
        "STEPFUN_API_KEY",
    ):
        val = os.environ.get(name)
        if val:
            keys[name] = val
    return keys


def get_provider(model: str) -> str | None:
    """Return the provider for a model name, or None if it's a local model."""
    if any(model.startswith(p) for p in _OPENAI_PREFIXES):
        return "openai"
    if any(model.startswith(p) for p in _ANTHROPIC_PREFIXES):
        return "anthropic"
    if any(model.startswith(p) for p in _GOOGLE_PREFIXES):
        return "google"
    if any(model.startswith(p) for p in _MINIMAX_PREFIXES):
        return "minimax"
    if any(model.startswith(p) for p in _STEPFUN_PREFIXES):
        return "stepfun"
    if any(model.startswith(org) for org in _LOCAL_HF_ORGS):
        return None
    if "/" in model:
        return "openrouter"
    return None


def is_cloud_model(model: str) -> bool:
    """Return True if the model is served by a cloud provider."""
    return get_provider(model) is not None


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------


def _to_openai_msgs(messages: Sequence[Message]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        role = m.role.value if hasattr(m.role, "value") else str(m.role)
        out.append({"role": role, "content": m.content or ""})
    return out


def _to_anthropic_msgs(
    messages: Sequence[Message],
) -> tuple[str, list[dict[str, Any]]]:
    system_text = ""
    chat: list[dict[str, Any]] = []
    for m in messages:
        role = m.role.value if hasattr(m.role, "value") else str(m.role)
        if role == "system":
            system_text = m.content or ""
        else:
            ar = "user" if role != "assistant" else "assistant"
            chat.append({"role": ar, "content": m.content or ""})
    return system_text, chat


def _to_google_contents(messages: Sequence[Message]) -> list[dict[str, Any]]:
    contents = []
    for m in messages:
        role = m.role.value if hasattr(m.role, "value") else str(m.role)
        if role == "system":
            contents.append({"role": "user", "parts": [{"text": m.content or ""}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": m.content or ""}]})
        else:
            contents.append({"role": "user", "parts": [{"text": m.content or ""}]})
    return contents


# ---------------------------------------------------------------------------
# Streaming generators
# ---------------------------------------------------------------------------


async def _stream_openai(
    model: str,
    messages: Sequence[Message],
    temperature: float,
    max_tokens: int,
    base_url: str = "https://api.openai.com/v1",
    api_key_name: str = "OPENAI_API_KEY",
) -> AsyncIterator[str]:
    keys = _load_keys()
    api_key = keys.get(api_key_name, "")
    if not api_key:
        raise ValueError(f"{api_key_name} not set — add it in the Cloud Models tab")

    payload = {
        "model": model,
        "messages": _to_openai_msgs(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content") or ""
                except Exception:
                    delta = ""
                if delta:
                    yield delta


async def _stream_anthropic(
    model: str,
    messages: Sequence[Message],
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    keys = _load_keys()
    api_key = keys.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set — add it in the Cloud Models tab")

    system_text, chat_msgs = _to_anthropic_msgs(messages)
    payload: dict[str, Any] = {
        "model": model,
        "messages": chat_msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if system_text:
        payload["system"] = system_text

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                try:
                    event = json.loads(data)
                    if event.get("type") == "content_block_delta":
                        text = event.get("delta", {}).get("text") or ""
                        if text:
                            yield text
                except Exception:
                    pass


async def _stream_google(
    model: str,
    messages: Sequence[Message],
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    keys = _load_keys()
    api_key = keys.get("GEMINI_API_KEY") or keys.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set — add it in the Cloud Models tab")

    contents = _to_google_contents(messages)
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:streamGenerateContent?alt=sse&key={api_key}"
    )

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                try:
                    chunk = json.loads(data)
                    candidates = chunk.get("candidates", [{}])
                    content_parts = (
                        candidates[0].get("content", {}).get("parts", []) if candidates else []
                    )
                    for part in content_parts:
                        text = part.get("text") or ""
                        if text:
                            yield text
                except Exception:
                    pass


async def _stream_openrouter(
    model: str,
    messages: Sequence[Message],
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    keys = _load_keys()
    api_key = keys.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set — add it in the Cloud Models tab")

    payload = {
        "model": model,
        "messages": _to_openai_msgs(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                    if delta:
                        yield delta
                except Exception:
                    pass
