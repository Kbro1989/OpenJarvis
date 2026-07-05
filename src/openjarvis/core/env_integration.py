"""Integrate Hermes-sourced credentials into OpenJarvis runtime env.

This module only loads Hermes-owned dotenv/auth material and re-exposes the
relevant provider keys as ``os.environ`` entries. It does not read or trust
OpenJarvis secrets from ``.openjarvis/credentials.toml`` here; that stays in
``core/credentials.py``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_hermes_home() -> Path:
    """Resolve the active Hermes config root on Windows/WSL."""
    candidates = [
        Path(os.environ.get("HERMES_HOME", "")),
        Path(os.environ.get("APPDATA", "")) / "hermes",
        Path.home() / "AppData" / "Local" / "hermes",
        Path.home() / ".hermes",
    ]
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_dir():
                return candidate
        except OSError:
            continue
    return Path.home() / ".hermes"


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE dotenv file without secrets logging."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Hermes dotenv not readable: %s", exc)
        return values
    for raw in text.splitlines():
        expanded = os.path.expandvars(os.path.expanduser(raw))
        line = expanded.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            values[key] = value
    return values


def _canonical_provider_name(provider: str) -> str:
    return provider.strip().lower().replace("-", "").replace("_", "")


def _provider_access_token_key(provider: str) -> str:
    canon = _canonical_provider_name(provider)
    return {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "huggingface": "HUGGINGFACE_TOKEN",
        "fireworks": "FIREWORKS_API_KEY",
        "groq": "GROQ_API_KEY",
        "gateway": "GATEWAY_API_KEY",
    }.get(canon, f"{canon.upper()}_API_KEY")


def _provider_base_url_env(provider: str) -> str:
    canon = _canonical_provider_name(provider)
    return {
        "deepseek": "DEEPSEEK_BASE_URL",
        "openrouter": "OPENROUTER_BASE_URL",
        "openai": "OPENAI_BASE_URL",
        "gemini": "GEMINI_BASE_URL",
        "google": "GOOGLE_API_BASE_URL",
        "anthropic": "ANTHROPIC_BASE_URL",
        "fireworks": "FIREWORKS_BASE_URL",
        "groq": "GROQ_BASE_URL",
        "gateway": "GATEWAY_BASE_URL",
    }.get(canon, f"{canon.upper()}_BASE_URL")


def _normalize_provider_payload(provider_name: str, payload: dict) -> dict[str, str]:
    """Map provider-specific schema into canonical env-style keys."""
    if not isinstance(payload, dict):
        return {}

    flattened: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(value, str):
            continue
        if key == "access_token":
            flattened[_provider_access_token_key(provider_name)] = value
        elif key == "base_url":
            flattened[_provider_base_url_env(provider_name)] = value
        elif key == "inference_base_url":
            flattened[_provider_base_url_env(provider_name)] = value
        else:
            flattened[key] = value
    return flattened


def _load_auth_json(path: Path) -> dict[str, str]:
    """Parse Hermes ``auth.json`` and return provider→env mappings."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.debug("Hermes auth.json not readable: %s", exc)
        return {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    flat: dict[str, str] = {}
    providers = data.get("providers")
    if isinstance(providers, dict):
        for provider_name, payload in providers.items():
            if isinstance(payload, dict):
                flat.update(_normalize_provider_payload(provider_name, payload))

    pool = data.get("credential_pool")
    if isinstance(pool, dict):
        for provider_name, entries in pool.items():
            if isinstance(entries, list):
                valid = [
                    entry
                    for entry in entries
                    if isinstance(entry, dict)
                    and str(entry.get("last_status", "")) in {"ok", "active", ""}
                ]
                if valid:
                    flat.update(_normalize_provider_payload(provider_name, valid[0]))

    return flat


def _provider_env_map() -> dict[str, str]:
    """Return Hermes-style session keys projected into OpenJarvis/LLM env keys."""
    return {
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY",
        "OPENAI_API_KEY": "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY": "GEMINI_API_KEY",
        "GOOGLE_API_KEY": "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY": "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL": "DEEPSEEK_BASE_URL",
        "OPENAI_BASE_URL": "OPENAI_BASE_URL",
        "OPENROUTER_BASE_URL": "OPENROUTER_BASE_URL",
        "GEMINI_BASE_URL": "GEMINI_BASE_URL",
        "GOOGLE_API_BASE_URL": "GOOGLE_API_BASE_URL",
        "ANTHROPIC_BASE_URL": "ANTHROPIC_BASE_URL",
        "FIREWORKS_BASE_URL": "FIREWORKS_BASE_URL",
        "GROQ_BASE_URL": "GROQ_BASE_URL",
        "GATEWAY_API_KEY": "GATEWAY_API_KEY",
        "HUGGINGFACE_TOKEN": "HUGGINGFACE_TOKEN",
        "FIREWORKS_API_KEY": "FIREWORKS_API_KEY",
        "GROQ_API_KEY": "GROQ_API_KEY",
    }


def inject_hermes_env(hermes_home: str | Path | None = None) -> None:
    """Inject Hermes host credentials into os.environ without overwriting.

    Reads the Hermes dotenv/auth files from the active Hermes home and injects
    entries only when they are not already present in ``os.environ``. Secrets
    are never logged; only key names and counts are reported at debug level.
    """
    home = Path(hermes_home) if hermes_home else _default_hermes_home()
    dotenv = home / ".env"
    auth_json = home / "auth.json"

    merged: dict[str, str] = {}
    merged.update(_load_dotenv(dotenv))
    if auth_json.exists():
        merged.update(_load_auth_json(auth_json))

    env_map = _provider_env_map()
    injected: list[str] = []
    for source_key, env_key in env_map.items():
        if env_key not in os.environ and source_key in merged and merged[source_key]:
            os.environ[env_key] = merged[source_key]
            injected.append(env_key)
    if injected:
        logger.debug("Hermes credential injection: %s", ", ".join(injected))
