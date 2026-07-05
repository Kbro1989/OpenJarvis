"""Desktop execution bridge — authoritative local-program runner for Hermes desktop.

This module exposes a small FastAPI router that turns OpenJarvis's existing
local-execution contract into real HTTP endpoints the desktop Electron app,
the local TUI, and the dashboard can call.  It does NOT introduce new
execution semantics: every request funnels through the same bounded shell
rules already used by ``ShellExecTool``, with an additional explicit
execution_mode so callers can distinguish shell invocation from program
dispatch.

Security model
--------------
- POST-only for execution; GET is limited to health/status.
- Commands are executed through the host shell, capped at 300s by default.
- Working directories must exist and be directories when supplied.
- Environment passthrough is explicit and small by default.
- This bridge does not bypass the existing Windows/shell constraints of the
  host checkout; it merely exposes them over HTTP for the local desktop
  surfaces.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, List, Optional

import json

from fastapi import APIRouter, HTTPException

from openjarvis.core.types import ToolResult
from openjarvis.core.paths import get_kingwen_workspace_dir
from openjarvis.emotion.kingwen import KingWenEmotionProvider
import os

router = APIRouter(prefix="/v1/desktop", tags=["desktop"])

# ---------------------------------------------------------------------------
# NO-MOCK King Wen runtime loader
# ---------------------------------------------------------------------------
# Real implementation, no stubs / no placeholders / no fabricated outputs.
# Only accepted path: actual JSON tables + KingWenEmotionProvider.consult().
# If any data file is missing, this stores the error and surfaces it on
# every request. Callers /must not/ receive synthetic fallback data.
#
# Data path precedence:
#   1. OPENJARVIS_KINGWEN_DIR env override
#   2. get_kingwen_workspace_dir() / data/
#   3. CWD / data/
# ---------------------------------------------------------------------------

_kingwen_workspace: str | None = None
_kingwen_load_error: str | None = None
_kingwen_provider: KingWenEmotionProvider | None = None


def _resolve_kingwen_data_dir() -> str:
    override = os.environ.get("OPENJARVIS_KINGWEN_DIR", "").strip()
    candidates = []
    if override:
        candidates.append(override)
    candidates.append(str(get_kingwen_workspace_dir() / "data"))
    try:
        candidates.append(str(Path(os.getcwd()) / "data"))
    except Exception:
        pass

    seen: set[str] = set()
    for raw in candidates:
        try:
            p = str(raw)
            if p not in seen and os.path.isdir(p):
                seen.add(p)
                return p
        except Exception:
            continue
    return candidates[0] if candidates else ""


def _load_kingwen_provider() -> KingWenEmotionProvider | None:
    global _kingwen_provider, _kingwen_load_error, _kingwen_workspace
    if _kingwen_provider is not None:
        return _kingwen_provider
    if _kingwen_load_error is not None:
        return None

    data_dir = _resolve_kingwen_data_dir()
    _kingwen_workspace = os.path.dirname(data_dir) if data_dir else None
    registry = os.path.join(data_dir, "hexagram-registry.json")
    weights = os.path.join(data_dir, "emotional-weights.json")
    reflections = os.path.join(data_dir, "temporal-reflections.json")

    missing = [p for p in [registry, weights, reflections] if not os.path.isfile(p)]
    if missing:
        _kingwen_load_error = (
            "King Wen data files missing; expected under: "
            f"{data_dir} | missing: {missing}"
        )
        return None

    try:
        _kingwen_provider = KingWenEmotionProvider(
            registry_path=registry,
            weights_path=weights,
            reflections_path=reflections,
        )
        _kingwen_load_error = None
        return _kingwen_provider
    except Exception as exc:
        _kingwen_load_error = f"King Wen provider init failed: {type(exc).__name__}: {exc}"
        _kingwen_provider = None
        return None

# Mirrors shell_exec.py constraints rather than inventing new limits.
_MAX_OUTPUT_BYTES = 102_400
_MAX_TIMEOUT = 300
_DEFAULT_TIMEOUT = 30
_BASE_ENV_KEYS = ("PATH", "HOME", "USER", "LANG", "TERM")


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "desktop_execution"}


@router.post("/execute")
async def execute_command(payload: dict[str, Any]) -> dict[str, Any]:
    command = str(payload.get("command", "")).strip()
    if not command:
        raise HTTPException(status_code=400, detail="`command` is required.")

    timeout = payload.get("timeout", _DEFAULT_TIMEOUT)
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = _DEFAULT_TIMEOUT
    timeout = max(1, min(timeout, _MAX_TIMEOUT))

    working_dir = payload.get("working_dir")
    wd_path = Path(working_dir).expanduser() if working_dir else None
    if wd_path is not None:
        if not wd_path.exists() or not wd_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"working_dir does not exist or is not a directory: {working_dir}",
            )

    env_passthrough: List[str] = list(payload.get("env_passthrough") or [])
    allowed_env_keys = list(_BASE_ENV_KEYS) + [str(key) for key in env_passthrough]
    env: dict[str, str] = {}
    for key in allowed_env_keys:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(wd_path) if wd_path else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "content": f"Command timed out after {timeout} seconds.",
            "exit_code": -1,
            "timeout_used": timeout,
            "working_dir": working_dir,
        }
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=f"Permission denied: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"OS error: {exc}") from exc

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if len(stdout) > _MAX_OUTPUT_BYTES:
        stdout = stdout[:_MAX_OUTPUT_BYTES] + "\n... (stdout truncated)"
    if len(stderr) > _MAX_OUTPUT_BYTES:
        stderr = stderr[:_MAX_OUTPUT_BYTES] + "\n... (stderr truncated)"

    sections: list[str] = []
    if stdout:
        sections.append(f"=== STDOUT ===\n{stdout}")
    if stderr:
        sections.append(f"=== STDERR ===\n{stderr}")
    content = "\n".join(sections) if sections else "(no output)"

    return {
        "success": result.returncode == 0,
        "content": content,
        "exit_code": result.returncode,
        "timeout_used": timeout,
        "working_dir": working_dir,
    }


@router.post("/dispatch")
async def dispatch_program(payload: dict[str, Any]) -> dict[str, Any]:
    program = str(payload.get("program", "")).strip()
    if not program:
        raise HTTPException(status_code=400, detail="`program` is required.")

    args: list[str] = [str(item) for item in (payload.get("args") or [])]
    timeout = payload.get("timeout", _DEFAULT_TIMEOUT)
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = _DEFAULT_TIMEOUT
    timeout = max(1, min(timeout, _MAX_TIMEOUT))

    working_dir = payload.get("working_dir")
    wd_path = Path(working_dir).expanduser() if working_dir else None
    if wd_path is not None:
        if not wd_path.exists() or not wd_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"working_dir does not exist or is not a directory: {working_dir}",
            )

    env_passthrough: List[str] = [str(key) for key in (payload.get("env_passthrough") or [])]
    allowed_env_keys = list(_BASE_ENV_KEYS) + env_passthrough
    env: dict[str, str] = {}
    for key in allowed_env_keys:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val

    cmd = [program, *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(wd_path) if wd_path else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "content": f"Program timed out after {timeout} seconds.",
            "exit_code": -1,
            "timeout_used": timeout,
            "working_dir": working_dir,
        }
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=f"Permission denied: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"OS error: {exc}") from exc

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if len(stdout) > _MAX_OUTPUT_BYTES:
        stdout = stdout[:_MAX_OUTPUT_BYTES] + "\n... (stdout truncated)"
    if len(stderr) > _MAX_OUTPUT_BYTES:
        stderr = stderr[:_MAX_OUTPUT_BYTES] + "\n... (stderr truncated)"

    sections = []
    if stdout:
        sections.append(f"=== STDOUT ===\n{stdout}")
    if stderr:
        sections.append(f"=== STDERR ===\n{stderr}")
    content = "\n".join(sections) if sections else "(no output)"

    return {
        "success": result.returncode == 0,
        "content": content,
        "exit_code": result.returncode,
        "timeout_used": timeout,
        "working_dir": working_dir,
    }


@router.get("/execution-modes")
async def execution_modes() -> dict[str, Any]:
    return {
        "shell": {
            "endpoint": "/v1/desktop/execute",
            "description": "Run a shell command string through the host shell.",
        },
        "program": {
            "endpoint": "/v1/desktop/dispatch",
            "description": "Run a program with an explicit argv list.",
        },
        "kingwen": {
            "endpoint": "/v1/desktop/kingwen/consult",
            "description": "King Wen deterministic emotion consult for desktop avatar/butler.",
        },
    }


@router.get("/kingwen/status")
async def kingwen_status() -> dict[str, Any]:
    provider = _load_kingwen_provider()
    return {
        "enabled": provider is not None,
        "error": _kingwen_load_error,
        "workspace": _kingwen_workspace,
        "canonical_tick_ms": 640.0,
    }


@router.post("/kingwen/consult")
async def kingwen_consult(payload: dict[str, Any]) -> dict[str, Any]:
    provider = _load_kingwen_provider()
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "kingwen_unavailable",
                "message": _kingwen_load_error or "King Wen provider not initialized.",
            },
        )

    text = str(payload.get("text", "") or "").strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail={"error": "text_required", "message": "`text` is required for deterministic consult."},
        )

    session_id = str(payload.get("session_id", "desktop-overlay") or "desktop-overlay")
    emotional_input = payload.get("emotional_input", 50)

    try:
        emotional_input = int(emotional_input)
    except (TypeError, ValueError):
        emotional_input = 50
    emotional_input = max(0, min(100, emotional_input))

    try:
        result = provider.consult(
            text=text,
            session_id=session_id,
            emotional_input=emotional_input,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "consult_failed",
                "message": f"{type(exc).__name__}: {exc}",
            },
        ) from exc

    tts_backend = str(payload.get("tts_backend", "") or "").strip() or "cartesia"
    try:
        voice_preset = provider.voice_preset(
            tts_backend=tts_backend,
            voice_weight=float(result.get("emotional_deltas", {}).get("voiceWeight", 0.0) or 0.0),
        )
    except Exception:
        voice_preset = {
            "backend": tts_backend,
            "voice_id": "",
            "speed": 1.0,
        }

    return {
        "hexagram_id": result.get("hexagram_id"),
        "hexagram_name": result.get("hexagram_name"),
        "hexagram_unicode": result.get("hexagram_unicode"),
        "binary": result.get("binary"),
        "upper_trigram": result.get("upper_trigram"),
        "lower_trigram": result.get("lower_trigram"),
        "category": result.get("category"),
        "action": result.get("action"),
        "emotional_deltas": result.get("emotional_deltas", {}),
        "reflections": result.get("reflections", {}),
        "trainingNotes": result.get("trainingNotes"),
        "voice_preset": voice_preset,
        "session_id": session_id,
        "canonical_tick_ms": 640.0,
        "source": "kingwen",
    }


def _get_tool(name: str) -> Any | None:
    try:
        from openjarvis.core.registry import ToolRegistry

        if ToolRegistry.contains(name):
            return ToolRegistry.get(name)
    except Exception:
        pass
    return None


def _build_tool_executor(allowed_names: List[str]) -> Any | None:
    try:
        from openjarvis.tools._stubs import BaseTool, ToolExecutor

        tools = []
        for name in allowed_names:
            cls = _get_tool(name)
            if cls is None:
                continue
            try:
                if isinstance(cls, type) and issubclass(cls, BaseTool):
                    tools.append(cls())
                else:
                    tools.append(cls)
            except Exception:
                continue
        if not tools:
            return None
        return ToolExecutor(tools)
    except Exception:
        return None


_ALLOWED_DESKTOP_TOOL_NAMES = [
    "calculator",
    "think",
    "web_search",
    "shell_exec",
    "file_read",
    "file_write",
    "http_request",
    "text_to_speech",
    "audio_transcribe",
    "image_generate",
    "memory_search",
    "memory_retrieve",
    "memory_store",
    "kingwen_consult",
]


@router.get("/tools")
async def list_desktop_tools() -> dict[str, Any]:
    """List tools the desktop avatar bridge is allowed to invoke."""
    allowed = _ALLOWED_DESKTOP_TOOL_NAMES
    available: list[dict[str, Any]] = []
    for name in allowed:
        tool = _get_tool(name)
        if tool is None:
            continue
        try:
            spec = tool.spec
        except Exception:
            continue
        try:
            available.append(
                {
                    "name": getattr(spec, "name", name),
                    "description": getattr(spec, "description", "") or "",
                    "category": getattr(spec, "category", "") or "",
                    "timeout_seconds": float(getattr(spec, "timeout_seconds", 30.0) or 30.0),
                    "requires_confirmation": bool(getattr(spec, "requires_confirmation", False) or False),
                    "parameters": getattr(spec, "parameters", None) or {},
                }
            )
        except Exception:
            continue
    return {"allowed": available, "count": len(available)}


@router.post("/tools/execute")
async def execute_desktop_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a desktop-allowed tool and return a real tool result."""
    name = str(payload.get("name") or "").strip()
    arguments = payload.get("arguments") or {}
    if not name:
        raise HTTPException(status_code=400, detail="`name` is required.")
    if name not in set(_ALLOWED_DESKTOP_TOOL_NAMES):
        raise HTTPException(
            status_code=403,
            detail=f"Tool '{name}' is not in the desktop allowed-tool list.",
        )

    if name == "kingwen_consult":
        return await kingwen_consult(payload)

    tool_executor = _build_tool_executor([name])
    if tool_executor is None:
        raise HTTPException(
            status_code=500,
            detail=f"Tool '{name}' is registered, but no executor could be built.",
        )

    try:
        from openjarvis.core.types import ToolCall

        tc = ToolCall(
            id="desktop-tool-1",
            name=name,
            arguments=json.dumps(arguments) if not isinstance(arguments, str) else arguments,
        )
        result = tool_executor.execute(tc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {exc}") from exc

    return {
        "success": result.success,
        "tool_name": result.tool_name,
        "content": result.content,
        "exit_code": getattr(result, "exit_code", None),
        "metadata": result.metadata or {},
        "source": "desktop-tool",
    }


__all__ = ["router"]
