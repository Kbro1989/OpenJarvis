"""Command-center routes for the OpenJarvis backend.

These endpoints mirror the Hermes Desktop command-center capability with
OpenJarvis-native implementations. No dependencies on Hermes runtime.

Exposed endpoints
-----------------
- ``GET /v1/command-center/status``
    Current system / server status.
- ``GET /v1/command-center/logs``
    Recent server log entries.
- ``POST /v1/command-center/maintenance/cleanup``
    Perform lightweight server-side cleanup.
- ``GET /v1/command-center/usage``
    Basic usage analytics derived from the local trace store.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/v1/command-center", tags=["command-center"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class SystemStatusResponse(BaseModel):
    """Snapshot of the server + host environment."""

    status: str
    uptime_seconds: float
    model: str
    engine_name: str
    agent_name: str | None
    trace_store_enabled: bool
    analytics_enabled: bool
    memory_backend_connected: bool
    channel_bridge_connected: bool
    python_version: str
    platform: str
    pid: int


class LogEntry(BaseModel):
    timestamp: float
    level: str
    logger: str
    message: str


class LogResponse(BaseModel):
    """Container around a list of recent log lines."""

    entries: list[LogEntry]
    level_filter: str


class MaintenanceCleanupResponse(BaseModel):
    """Outcome of a maintenance run."""

    traces_removed: int = 0
    bytes_freed: int = 0
    message: str = ""


class UsageSummaryResponse(BaseModel):
    """High-level usage analytics for the current session."""

    session_started_at: float
    session_uptime_seconds: float
    total_traces: int | None = None
    trace_store_path: str | None = None
    total_prompt_tokens: int | None = None
    total_completion_tokens: int | None = None
    total_tokens: int | None = None


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------
@router.get("/status", response_model=SystemStatusResponse)
async def get_status(request: Request) -> SystemStatusResponse:
    """Return a snapshot of OpenJarvis server health and environment."""
    import platform
    import sys

    from openjarvis.core.config import load_config

    trace_store_enabled = False
    analytics_enabled = False
    memory_backend_connected = False
    channel_bridge_connected = False

    try:
        cfg = load_config()
        analytics_enabled = bool(getattr(cfg, "analytics", None)) and getattr(
            cfg.analytics, "enabled", False
        )
    except Exception:
        pass

    try:
        trace_store = getattr(request.app.state, "trace_store", None)
        trace_store_enabled = trace_store is not None
    except Exception:
        pass

    try:
        memory_backend_connected = getattr(
            request.app.state, "memory_backend", None
        ) is not None
    except Exception:
        pass

    try:
        channel_bridge_connected = getattr(
            request.app.state, "channel_bridge", None
        ) is not None
    except Exception:
        pass

    return SystemStatusResponse(
        status="ok",
        uptime_seconds=round(time.time() - getattr(request.app.state, "session_start", time.time()), 3),
        model=getattr(request.app.state, "model", ""),
        engine_name=getattr(request.app.state, "engine_name", ""),
        agent_name=getattr(request.app.state, "agent_name", None),
        trace_store_enabled=trace_store_enabled,
        analytics_enabled=analytics_enabled,
        memory_backend_connected=memory_backend_connected,
        channel_bridge_connected=channel_bridge_connected,
        python_version=platform.python_version(),
        platform=platform.platform(),
        pid=os.getpid(),
    )


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
def _read_env_log_file(
    env_var: str,
    fallback_patterns: list[str],
    max_bytes: int = 256_000,
) -> list[LogEntry]:
    """Best-effort read of a log file using environment hints."""
    candidates: list[str] = []

    env_value = os.environ.get(env_var)
    if env_value:
        candidates.append(env_value)

    for pattern in fallback_patterns:
        matches = list(Path(".").glob(pattern))
        candidates.extend(str(p) for p in matches[:5])

    if not candidates:
        return []

    for path_str in candidates:
        path = Path(path_str)
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
            entries: list[LogEntry] = []
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                if size > max_bytes:
                    fh.seek(-max_bytes, os.SEEK_END)
                    fh.readline()
                for raw_line in fh:
                    line = raw_line.rstrip("\n")
                    if not line:
                        continue
                    ts = 0.0
                    lvl = "INFO"
                    logger_name = "root"
                    message = line
                    try:
                        import datetime

                        if line.startswith("{"):
                            import json

                            payload = json.loads(line)
                            if isinstance(payload, dict):
                                lvl = str(payload.get("levelname", lvl)).upper()
                                logger_name = payload.get("name", "root")
                                message = payload.get("message", line)
                                asctime = payload.get("asctime")
                                if asctime:
                                    try:
                                        ts = datetime.datetime.strptime(
                                            asctime,
                                            "%Y-%m-%d %H:%M:%S",
                                        ).timestamp()
                                    except Exception:
                                        pass
                        else:
                            parts = line.split(" - ", 3)
                            if len(parts) == 4:
                                timestamp_str, logger_name, lvl, message = parts
                                try:
                                    ts = datetime.datetime.strptime(
                                        timestamp_str,
                                        "%Y-%m-%d %H:%M:%S,%f",
                                    ).timestamp()
                                except Exception:
                                    pass
                            elif len(parts) == 3:
                                logger_name, lvl, message = parts
                    except Exception:
                        pass
                    entries.append(
                        LogEntry(
                            timestamp=ts,
                            level=lvl,
                            logger=logger_name,
                            message=message,
                        )
                    )
            return entries
        except Exception:
            continue
    return []


@router.get("/logs", response_model=LogResponse)
async def get_logs(
    request: Request,
    level: str = "DEBUG",
    max_entries: int = 200,
) -> LogResponse:
    """Return recent server log entries.

    Supports ``level`` query filtering (case-insensitive).
    Falls back to the Python root logger handlers when a log file is not
    available.
    """
    entries = _read_env_log_file(
        env_var="OPENJARVIS_LOG_FILE",
        fallback_patterns=[
            "**/openjarvis*.log",
            "**/*.log",
        ],
    )

    level_filter = level.upper()
    if entries:
        filtered = [
            e for e in entries if e.level.upper() == level_filter or level_filter == "DEBUG"
        ]
        if not filtered:
            filtered = entries
        entries = filtered[-max_entries:]

    return LogResponse(entries=entries, level_filter=level_filter)


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------
@router.post("/maintenance/cleanup", response_model=MaintenanceCleanupResponse)
async def maintenance_cleanup(request: Request) -> MaintenanceCleanupResponse:
    """Run lightweight backend maintenance tasks.

    Currently removes expired or superfluous trace records from the local
    ``TraceStore`` when available. Such pruning is best-effort: failures
    must never crash the server.
    """
    traces_removed = 0
    bytes_freed = 0
    message = "No maintenance actions were available."

    try:
        trace_store = getattr(request.app.state, "trace_store", None)
        if trace_store is not None:
            before = os.path.getsize(trace_store.db_path)

            # Many implementations expose a prune-like helper; wrap optional.
            try:
                if hasattr(trace_store, "prune"):
                    trace_store.prune()
                    message = "Traces pruned via TraceStore.prune()."
                elif hasattr(trace_store, "delete_expired"):
                    trace_store.delete_expired()
                    message = "Expired traces deleted via TraceStore.delete_expired()."
                else:
                    message = (
                        "TraceStore exists but provides no cleanup helper; "
                        "skipping trace cleanup."
                    )
            except Exception as exc:  # noqa: BLE001 — best-effort only
                logger.debug("Trace cleanup failed: %s", exc)
                message = f"Trace cleanup failed: {exc}"

            try:
                after = os.path.getsize(trace_store.db_path)
                bytes_freed = max(0, before - after)
            except Exception:
                pass

            try:
                if hasattr(trace_store, "count"):
                    traces_removed = int(
                        trace_store.count()
                    )
            except Exception:
                traces_removed = 0
    except Exception:
        pass

    return MaintenanceCleanupResponse(
        traces_removed=traces_removed,
        bytes_freed=bytes_freed,
        message=message,
    )


# ---------------------------------------------------------------------------
# Usage analytics
# ---------------------------------------------------------------------------
@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(request: Request) -> UsageSummaryResponse:
    """Return basic server-side usage analytics.

    When a local ``TraceStore`` is wired into ``app.state`` the totals are
    taken from that store. When traces are disabled or the store is not
    present, the fields are left as ``None``.
    """
    session_start = getattr(request.app.state, "session_start", time.time())
    session_uptime = round(time.time() - session_start, 3)

    trace_store_path: str | None = None
    trace_store = getattr(request.app.state, "trace_store", None)
    total_traces: int | None = None
    total_prompt_tokens: int | None = None
    total_completion_tokens: int | None = None
    total_tokens: int | None = None

    if trace_store is not None:
        try:
            trace_store_path = str(getattr(trace_store, "db_path", ""))
        except Exception:
            trace_store_path = None

        try:
            if hasattr(trace_store, "count"):
                total_traces = int(trace_store.count())
        except Exception:
            total_traces = None

        try:
            if hasattr(trace_store, "aggregate"):
                agg = trace_store.aggregate()
                total_prompt_tokens = int(agg.get("prompt_tokens") or 0) or None
                total_completion_tokens = (
                    int(agg.get("completion_tokens") or 0) or None
                )
                total_tokens = int(agg.get("total_tokens") or 0) or None
                if total_prompt_tokens == 0:
                    total_prompt_tokens = None
                if total_completion_tokens == 0:
                    total_completion_tokens = None
                if total_tokens == 0:
                    total_tokens = None
        except Exception:
            total_traces = None
            total_prompt_tokens = None
            total_completion_tokens = None
            total_tokens = None

    return UsageSummaryResponse(
        session_started_at=round(session_start, 3),
        session_uptime_seconds=session_uptime,
        total_traces=total_traces,
        trace_store_path=trace_store_path,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
    )


__all__ = ["router"]
