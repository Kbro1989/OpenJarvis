"""Hermes runtime engine — shells out to a local Hermes Agent checkout,
or calls the Nous portal directly if portal auth is available in auth.json.

This bridges OpenJarvis queries into Hermes Agent without importing Hermes
into this process. It exposes the standard ``InferenceEngine`` interface
so ``SystemBuilder`` can use it as a first-class runtime target.

Implicit contract assumed by this implementation:
- The active Hermes checkout is ``C:\\\\Users\\\\krist\\\\AppData\\\\Local\\\\hermes\\\\hermes-agent``.
- That repo exposes the runner at ``src/openjarvas/evals/backends/external/_runners/hermes_runner.py``.
- The runner accepts ``--task``,``--model``,``--output-json`` and writes a JSON result file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message
from openjarvis.engine._base import EngineConnectionError
from openjarvis.engine._stubs import InferenceEngine

try:
    import requests as _requests
except Exception:  # pragma: no cover - network helper optional
    _requests = None  # type: ignore[assignment]

LOGGER = __import__("logging").getLogger(__name__)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_nous_portal(hermes_path: Path) -> Dict[str, str]:
    candidates = [
        hermes_path / "auth.json",
        Path(os.environ.get("HERMES_HOME", "")) / "auth.json",
        Path(os.environ.get("APPDATA", "")) / "hermes" / "auth.json",
        Path.home() / "AppData" / "Local" / "hermes" / "auth.json",
        Path.home() / ".hermes" / "auth.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        data = _load_json(candidate)
        if not isinstance(data, dict):
            continue
        nous = data.get("providers", {}).get("nous")
        if isinstance(nous, dict):
            inference_base_url = str(nous.get("inference_base_url") or "").strip()
            portal_base_url = str(nous.get("portal_base_url") or "").strip()
            client_id = str(nous.get("client_id") or "").strip()
            access_token = str(nous.get("access_token") or "").strip()
            refresh_token = str(nous.get("refresh_token") or "").strip()
            agent_key = str(nous.get("agent_key") or "").strip()
            if inference_base_url and (access_token or agent_key):
                return {
                    "auth_json": str(candidate),
                    "base_url": inference_base_url,
                    "portal_base_url": portal_base_url or inference_base_url,
                    "client_id": client_id,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
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


def _load_nous_credentials(portal: Dict[str, str]) -> Dict[str, str]:
    if not portal:
        return {}
    return {
        "base_url": portal.get("base_url", ""),
        "portal_base_url": portal.get("portal_base_url", ""),
        "access_token": portal.get("access_token", ""),
        "refresh_token": portal.get("refresh_token", ""),
        "agent_key": portal.get("agent_key", ""),
        "client_id": portal.get("client_id", ""),
        "auth_json": portal.get("auth_json", ""),
    }


def _discover_nous_models(credentials: Dict[str, str], timeout: float) -> List[str]:
    if _requests is None:
        return []
    base_url = (credentials.get("base_url") or "").rstrip("/")
    if not base_url:
        return []
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    token = credentials.get("access_token") or credentials.get("agent_key") or ""
    if not token:
        return []
    try:
        response = _requests.get(
            f"{base_url}/v1/models",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return [
            str(item.get("id", ""))
            for item in data.get("data", [])
            if isinstance(item, dict) and item.get("id")
        ]
    except Exception:
        return []


def _first_reasoning_text(message: Dict[str, Any]) -> str:
    details = message.get("reasoning_details")
    if not isinstance(details, list):
        return ""
    parts = [
        str(detail.get("text") or "")
        for detail in details
        if isinstance(detail, dict) and isinstance(detail.get("text"), str)
    ]
    if not parts:
        return ""
    return "".join(parts).strip()


@EngineRegistry.register("hermes")
class HermesRuntimeEngine(InferenceEngine):
    """Run inference through a local Hermes Agent checkout."""

    engine_id = "hermes"
    is_cloud = False
    _default_host = ""

    def __init__(
        self,
        path: Optional[Path] = None,
        python_executable: Optional[str] = None,
        api_mode: str = "chat_completions",
        max_iterations: int = 90,
        timeout_seconds: float = 600.0,
    ) -> None:
        self._path = (
            Path(path).expanduser().resolve()
            if path
            else Path(
                os.environ.get("HERMES_AGENT_PATH", "")
                or r"C:\Users\krist\AppData\Local\hermes\hermes-agent"
            )
        )
        self._python_executable = python_executable or os.environ.get(
            "HERMES_AGENT_PYTHON"
        ) or sys.executable
        self._api_mode = api_mode
        self._max_iterations = max_iterations
        self._timeout = float(timeout_seconds)

        if not self._path.exists() or not self._path.is_dir():
            raise EngineConnectionError(f"Hermes path does not exist: {self._path}")

        self._portal = _resolve_nous_portal(self._path)
        self._credentials = _load_nous_credentials(self._portal)
        self._discovered_models: List[str] = _discover_nous_models(
            self._credentials, self._timeout
        )

    def _runner_script(self) -> Path:
        root = self._path
        candidates = [
            root / "src" / "openjarvas" / "evals" / "backends" / "external" / "_runners" / "hermes_runner.py",
            root / "src" / "openjarvis" / "evals" / "backends" / "external" / "_runners" / "hermes_runner.py",
            root / "hermes_runner.py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(
            f"Hermes runner script not found under {self._path}. "
            "Expected hermes_runner.py."
        )

    def _extract_content_from_messages(self, messages: Sequence[Message]) -> tuple[str, str]:
        system_parts: List[str] = []
        user_parts: List[str] = []

        def role_of(m: Message) -> str:
            raw = getattr(m, "role", None)
            if raw is None and isinstance(m, dict):
                raw = m.get("role", "user")
            value = getattr(raw, "value", raw)
            return str(value or "user").lower()

        def content_of(m: Message) -> str:
            if isinstance(m, dict):
                return str(m.get("content") or "")
            return str(getattr(m, "content", "") or "")

        for msg in messages:
            text = content_of(msg)
            if not text:
                continue
            role = role_of(msg)
            if role == "system":
                system_parts.append(text)
            elif role == "user":
                user_parts.append(text)
            elif role == "assistant":
                user_parts.append(f"assistant: {text}")
            elif role == "tool":
                user_parts.append(f"tool: {text}")
            else:
                user_parts.append(text)

        return "\n\n".join(system_parts), "\n\n".join(user_parts)

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        full = self.generate_full(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return {
            "content": full.get("content", ""),
            "usage": full.get("usage", {}),
            "model": full.get("model", model),
            "finish_reason": full.get("finish_reason", "stop"),
            "tool_calls": full.get("tool_calls"),
        }

    def generate_full(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = self._extract_content_from_messages(messages)
        if not user_prompt:
            user_prompt = "continue"
        if self._portal.get("base_url") and _requests is not None:
            return self._run_remote_portal(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return self._run_runner(
            system_prompt, user_prompt, model, temperature, max_tokens, kwargs
        )

    async def stream(  # type: ignore[override]
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ):
        """Hermes runtime does not support native streaming yet."""
        result = self.generate_full(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        content = result.get("content", "")
        if content:
            yield content

    def _run_runner(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        runner = self._runner_script()
        output_json = Path(tempfile.gettempdir()) / f"openjarvis-hermes-{id(self)}-{os.getpid()}.json"
        cmd = [
            self._python_executable,
            str(runner),
            "--task",
            user_prompt,
            "--model",
            model,
            "--base-url",
            kwargs.get("base_url", ""),
            "--api-key",
            kwargs.get("api_key", ""),
            "--api-mode",
            self._api_mode,
            "--max-iterations",
            str(self._max_iterations),
            "--output-json",
            str(output_json),
        ]
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        env = dict(os.environ)
        env["HERMES_AGENT_PATH"] = str(self._path)
        if "HERMES_AGENT_PYTHON" not in env and self._python_executable:
            env["HERMES_AGENT_PYTHON"] = self._python_executable
        try:
            proc = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        finally:
            pass

        stderr_tail = (proc.stderr or "").strip().splitlines()[-10:]
        stderr_summary = "\n".join(stderr_tail)

        if not output_json.exists():
            return {
                "content": "",
                "usage": {},
                "model": model,
                "finish_reason": "error",
                "error": (
                    "Hermes runner produced no output JSON.\n"
                    f"stderr:\n{stderr_summary}"
                ),
            }

        try:
            data = json.loads(output_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {
                "content": "",
                "usage": {},
                "model": model,
                "finish_reason": "error",
                "error": f"Hermes runner emitted invalid JSON: {exc}",
            }

        if data.get("error"):
            return {
                "content": data.get("content", ""),
                "usage": data.get("usage", {}),
                "model": model,
                "finish_reason": "error",
                "error": data.get("error"),
            }

        usage = data.get("usage", {})
        return {
            "content": data.get("content", ""),
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            "model": model,
            "finish_reason": "stop",
            "tool_calls": data.get("tool_calls"),
            "turn_count": data.get("turn_count"),
            "framework": "hermes",
            "framework_commit": data.get("framework_commit"),
            "latency_seconds": data.get("latency_seconds"),
        }

    def _run_remote_portal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        if _requests is None:
            return {
                "content": "",
                "usage": {},
                "model": model,
                "finish_reason": "error",
                "error": "requests is not installed; cannot call Nous portal",
            }

        base_url = (self._credentials.get("base_url") or "").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        if not base_url:
            return {
                "content": "",
                "usage": {},
                "model": model,
                "finish_reason": "error",
                "error": "Nous portal base_url is empty",
            }

        auth_token = self._credentials.get("access_token") or self._credentials.get("agent_key") or ""
        if not auth_token:
            return {
                "content": "",
                "usage": {},
                "model": model,
                "finish_reason": "error",
                "error": "Nous portal auth token is empty",
            }

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        target_model = model or ""
        if not target_model:
            target_model = "nousresearch/nous-hermes-2"
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        chat_url = f"{base_url}/v1/chat/completions"
        try:
            response = _requests.post(
                chat_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "content": "",
                "usage": {},
                "model": model,
                "finish_reason": "error",
                "error": f"Nous portal request failed: {exc}",
            }

        choice = (((data.get("choices") or [{}])[0]).get("message") or {})
        usage = data.get("usage") or {}
        content = (
            choice.get("content")
            or choice.get("reasoning")
            or _first_reasoning_text(choice)
            or ""
        )
        return {
            "content": content,
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            "model": data.get("model") or model,
            "finish_reason": ((data.get("choices") or [{}])[0]).get("finish_reason") or "stop",
            "framework": "nous-portal",
        }

    def list_models(self) -> List[str]:
        if self._discovered_models:
            return list(dict.fromkeys(self._discovered_models))
        fallback = self._detect_model_name()
        return [fallback] if fallback else []

    def _detect_model_name(self) -> str:
        try:
            return Path(self._python_executable).stem or "hermes"
        except Exception:
            return "hermes"

    def health(self) -> bool:
        try:
            if not self._path.exists() or not self._path.is_dir():
                return False
            if self._portal.get("base_url"):
                return bool(self._credentials.get("access_token") or self._credentials.get("agent_key"))
            runner = self._runner_script()
            return runner.exists()
        except Exception:
            return False


__all__ = ["HermesRuntimeEngine", "EngineConnectionError"]
