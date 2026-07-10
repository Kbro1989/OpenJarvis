"""Nous/StepFun inference engine.

Reuses the same Hermes auth-discovery path as ``hermes_runtime.py`` so
OpenJarvis can call the Nous portal directly without importing Hermes.
This keeps Hermes untouched while exposing ``stepfun/...`` models inside
OpenJarvis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message
from openjarvis.engine._base import EngineConnectionError, InferenceEngine

try:
    import requests as _requests
except Exception:  # pragma: no cover - optional dependency
    _requests = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)

_NOW_PLAYING_MODEL = "stepfun/step-3.7-flash:free"


def _load_json(path) -> Any | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _resolve_nous_portal() -> Dict[str, str]:
    candidates = [
        __import__("pathlib").Path(__import__("os").environ.get("HERMES_AGENT_PATH", "")) / "auth.json",
        __import__("pathlib").Path(__import__("os").environ.get("HERMES_HOME", "")) / "auth.json",
        __import__("pathlib").Path(__import__("os").environ.get("APPDATA", "")) / "hermes" / "auth.json",
        __import__("pathlib").Path.home() / "AppData" / "Local" / "hermes" / "auth.json",
        __import__("pathlib").Path.home() / ".hermes" / "auth.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            data = __import__("json").loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        nous = data.get("providers", {}).get("nous")
        if isinstance(nous, dict):
            inference_base_url = str(nous.get("inference_base_url") or "").strip()
            access_token = str(nous.get("access_token") or "").strip()
            agent_key = str(nous.get("agent_key") or "").strip()
            if inference_base_url and (access_token or agent_key):
                return {
                    "auth_json": str(candidate),
                    "base_url": inference_base_url,
                    "portal_base_url": str(nous.get("portal_base_url") or inference_base_url).strip(),
                    "client_id": str(nous.get("client_id") or "").strip(),
                    "access_token": access_token,
                    "refresh_token": str(nous.get("refresh_token") or "").strip(),
                    "agent_key": agent_key,
                    "auth_type": "oauth",
                }
        pool = data.get("credential_pool", {}).get("nous")
        if isinstance(pool, list):
            for entry in pool:
                if not isinstance(entry, dict):
                    continue
                inference_base_url = str(entry.get("inference_base_url") or "").strip()
                access_token = str(entry.get("access_token") or "").strip()
                agent_key = str(entry.get("agent_key") or "").strip()
                if inference_base_url and (access_token or agent_key):
                    return {
                        "auth_json": str(candidate),
                        "base_url": inference_base_url,
                        "portal_base_url": inference_base_url,
                        "client_id": str(entry.get("client_id") or "").strip(),
                        "access_token": access_token,
                        "refresh_token": str(entry.get("refresh_token") or "").strip(),
                        "agent_key": agent_key,
                        "auth_type": str(entry.get("auth_type") or "oauth").strip(),
                    }
    return {}


@EngineRegistry.register("nous")
class NousEngine(InferenceEngine):
    """Call the Nous portal directly using Hermes-owned credential discovery."""

    engine_id = "nous"
    is_cloud = True
    _default_host = ""

    def __init__(self) -> None:
        self._portal = _resolve_nous_portal()
        self._base_url = (self._portal.get("base_url") or "").rstrip("/")
        if self._base_url.endswith("/v1"):
            self._base_url = self._base_url[:-3]
        self._token = (
            self._portal.get("access_token") or self._portal.get("agent_key") or ""
        )

    def _payload(self, messages: Sequence[Message]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for m in messages:
            role = getattr(m, "role", None)
            if role is None and isinstance(m, dict):
                role = m.get("role", "user")
            value = getattr(role, "value", role)
            role_str = str(value or "user").lower()
            content = m.content if hasattr(m, "content") else str(m.get("content", "") or "")
            out.append({"role": role_str, "content": content or ""})
        return out

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self._base_url or not self._token:
            raise EngineConnectionError(
                "Nous portal not available from Hermes credentials"
            )
        payload = {
            "model": model or _NOW_PLAYING_MODEL,
            "messages": self._payload(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        try:
            response = _requests.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=600.0,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise EngineConnectionError(f"Nous portal request failed: {exc}") from exc

        choice = (((data.get("choices") or [{}])[0]).get("message") or {})
        usage = data.get("usage") or {}
        content = (
            choice.get("content") or choice.get("reasoning") or ""
        )
        return {
            "content": content,
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            "model": data.get("model") or model or _NOW_PLAYING_MODEL,
            "finish_reason": (((data.get("choices") or [{}])[0]).get("finish_reason") or "stop"),
            "framework": "nous-portal",
        }

    def list_models(self) -> List[str]:
        if not self._base_url or not self._token or _requests is None:
            return [_NOW_PLAYING_MODEL]
        try:
            response = _requests.get(
                f"{self._base_url}/v1/models",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            models = [
                str(item.get("id", ""))
                for item in data.get("data", [])
                if isinstance(item, dict) and item.get("id")
            ]
            return models or [_NOW_PLAYING_MODEL]
        except Exception:
            return [_NOW_PLAYING_MODEL]

    def health(self) -> bool:
        try:
            return bool(self._base_url) and bool(self._token) and (
                _requests.get(
                    f"{self._base_url}/v1/models",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=30.0,
                ).ok
                if _requests is not None
                else True
            )
        except Exception:
            return False

    def close(self) -> None:
        return None

    def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ):
        """Nous runtime does not support native streaming yet."""
        result = self.generate(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        content = result.get("content") or ""
        if content:
            yield content
