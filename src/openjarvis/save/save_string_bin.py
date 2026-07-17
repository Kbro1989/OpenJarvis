"""save_string_bin.py — Local save-string bin with tick-based Cloudflare push.

Pattern from openrsc-vinilla:
  rsc-server-do-worker.js  → 640ms tick + save-string I/O
  worker.js                → R2->KV->D1 persistence
  wrangler.toml            → KV + Queue bindings

Jarvis adaptation:
  Local bin: ~/.openjarvis/save_string_bin.jsonl (append-only, no CF dependency)
  Tick scheduler: configurable interval, usage-aware throttling
  CF push: POG2_SOVEREIGN KV + POG2_COLLAPSE_QUEUE Queue
  Quantum-safe: King Wen collapse states are high-frequency; bin absorbs bursts,
                tick pushes only confirmed/stabilized states to avoid burning CF usage.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools._stubs import BaseTool, ToolSpec
from openjarvis.core.types import ToolResult

LOGGER = logging.getLogger(__name__)

_BIN_PATH = Path.home() / ".openjarvis" / "save_string_bin.jsonl"
_PUSH_STATE_PATH = Path.home() / ".openjarvis" / "save_string_push_state.json"
_DEFAULT_TICK_INTERVAL = 640  # ms, matches RSC DO tick
_DEFAULT_MAX_PUSH_PER_TICK = 5
_DEFAULT_DAILY_BUDGET = 500  # max CF writes per day


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class SaveStringRecord:
    session_id: str
    timestamp: int  # ms epoch
    domain: str  # session | kingwen | agent | trace
    state: Dict[str, Any]
    pushed: bool = False
    push_attempts: int = 0
    last_push_ts: Optional[int] = None


@dataclass(slots=True)
class PushState:
    daily_count: int = 0
    daily_reset_ts: int = field(default_factory=lambda: int(time.time() * 1000))
    last_push_ts: Optional[int] = None
    consecutive_failures: int = 0


# ── Local bin ─────────────────────────────────────────────────────────────────

def _load_push_state() -> PushState:
    if not _PUSH_STATE_PATH.exists():
        return PushState()
    try:
        data = json.loads(_PUSH_STATE_PATH.read_text(encoding="utf-8"))
        return PushState(**data)
    except (json.JSONDecodeError, OSError, TypeError):
        return PushState()


def _save_push_state(state: PushState) -> None:
    try:
        _PUSH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PUSH_STATE_PATH.write_text(
            json.dumps({
                "daily_count": state.daily_count,
                "daily_reset_ts": state.daily_reset_ts,
                "last_push_ts": state.last_push_ts,
                "consecutive_failures": state.consecutive_failures,
            }),
            encoding="utf-8",
        )
    except OSError as exc:
        LOGGER.warning("push state write failed: %s", exc)


def _maybe_reset_daily(state: PushState) -> PushState:
    now = int(time.time() * 1000)
    if now - state.daily_reset_ts > 86400_000:  # 24h
        return PushState(daily_reset_ts=now)
    return state


def append_record(record: SaveStringRecord) -> Path:
    """Append a save-string record to local bin. No CF dependency."""
    _BIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "session_id": record.session_id,
        "timestamp": record.timestamp,
        "domain": record.domain,
        "state": record.state,
        "pushed": record.pushed,
        "push_attempts": record.push_attempts,
        "last_push_ts": record.last_push_ts,
    }, separators=(",", ":"))
    with _BIN_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    LOGGER.debug("Appended save-string record: %s", record.session_id)
    return _BIN_PATH


def read_unpaged_records(limit: Optional[int] = None) -> List[SaveStringRecord]:
    """Read unpushed records from local bin."""
    if not _BIN_PATH.exists():
        return []
    records = []
    with _BIN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if not data.get("pushed"):
                    records.append(SaveStringRecord(**data))
            except (json.JSONDecodeError, TypeError):
                continue
            if limit and len(records) >= limit:
                break
    return records


def mark_records_pushed(session_ids: List[str], push_ts: int) -> None:
    """Mark records as pushed by rewriting bin with updated flags."""
    if not _BIN_PATH.exists():
        return
    lines = _BIN_PATH.read_text(encoding="utf-8").splitlines()
    updated = []
    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if data.get("session_id") in session_ids:
                data["pushed"] = True
                data["push_attempts"] = data.get("push_attempts", 0) + 1
                data["last_push_ts"] = push_ts
            updated.append(json.dumps(data, separators=(",", ":")))
        except (json.JSONDecodeError, TypeError):
            updated.append(line)
    tmp = _BIN_PATH.with_suffix(".tmp")
    tmp.write_text("\n".join(updated) + "\n", encoding="utf-8")
    tmp.replace(_BIN_PATH)


# ── Usage-aware tick push ─────────────────────────────────────────────────────

def should_push(
    state: PushState,
    max_per_tick: int = _DEFAULT_MAX_PUSH_PER_TICK,
    daily_budget: int = _DEFAULT_DAILY_BUDGET,
) -> bool:
    """Check if we should push to CF based on usage budget."""
    state = _maybe_reset_daily(state)
    if state.daily_count >= daily_budget:
        LOGGER.debug("Daily CF write budget exhausted: %d/%d", state.daily_count, daily_budget)
        return False
    return state.daily_count < max_per_tick


def tick_push(
    max_per_tick: int = _DEFAULT_MAX_PUSH_PER_TICK,
    daily_budget: int = _DEFAULT_DAILY_BUDGET,
    push_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run one tick: push unpushed records to CF if budget allows.

    Args:
        max_per_tick: max records to push this tick
        daily_budget: max CF writes per 24h
        push_fn: callable(record) -> bool. If None, simulates push.
    """
    state = _maybe_reset_daily(_load_push_state())
    result = {"pushed": 0, "failed": 0, "skipped_budget": 0, "errors": []}

    if not should_push(state, max_per_tick, daily_budget):
        result["skipped_budget"] = len(read_unpaged_records())
        _save_push_state(state)
        return result

    records = read_unpaged_records(limit=max_per_tick)
    if not records:
        _save_push_state(state)
        return result

    pushed_ids = []
    for rec in records:
        try:
            if push_fn is None:
                # Default: simulate push without CF dependency
                success = True
            else:
                success = push_fn(rec)
            if success:
                pushed_ids.append(rec.session_id)
                state.daily_count += 1
                result["pushed"] += 1
                state.last_push_ts = rec.timestamp
                state.consecutive_failures = 0
            else:
                result["failed"] += 1
                state.consecutive_failures += 1
        except Exception as exc:
            result["failed"] += 1
            result["errors"].append(str(exc))
            state.consecutive_failures += 1

    if pushed_ids:
        mark_records_pushed(pushed_ids, int(time.time() * 1000))

    _save_push_state(state)
    return result


def get_bin_stats() -> Dict[str, Any]:
    """Get local bin statistics."""
    if not _BIN_PATH.exists():
        return {"total": 0, "unpushed": 0, "pushed": 0, "bin_path": str(_BIN_PATH)}
    total = 0
    unpushed = 0
    with _BIN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            try:
                data = json.loads(line)
                if not data.get("pushed"):
                    unpushed += 1
            except (json.JSONDecodeError, TypeError):
                pass
    state = _load_push_state()
    return {
        "total": total,
        "unpushed": unpushed,
        "pushed": total - unpushed,
        "bin_path": str(_BIN_PATH),
        "daily_cf_writes": state.daily_count,
        "last_push_ts": state.last_push_ts,
    }


# ── Cloudflare push bridge ────────────────────────────────────────────────────

def push_record_to_cf(
    record: SaveStringRecord,
    router_url: str = "http://localhost:8790",
    token: Optional[str] = None,
) -> bool:
    """Push a single save-string record to jarvis-router.

    Calls:
      POST /training/export  → POG2_COLLAPSE_QUEUE + KV
      POST /jarvis/wake      → KV + GLOBE broadcast

    Mirrors the contract in cloudflare/jarvis-router/src/index.ts.
    """
    try:
        import urllib.request
        import urllib.error

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Primary path: training export → Queue + KV
        export_payload = {
            "trace_id": f"tr_{record.session_id}",
            "hexagram_id": record.state.get("kingwen", {}).get("current_hexagram", 0),
            "porosity_ratio": record.state.get("kingwen", {}).get("porosity", 0.0),
            "quantum_collapse_delta": 1.0,
            "text": record.state.get("user", {}).get("username", ""),
            "weight": 1.0,
        }
        req = urllib.request.Request(
            f"{router_url}/training/export",
            data=json.dumps(export_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status not in (200, 202):
                LOGGER.warning("CF /training/export returned %s", resp.status)
                return False

        # Secondary path: jarvis wake → KV last_wake + globe
        wake_payload = {
            "hexagram_id": record.state.get("kingwen", {}).get("current_hexagram"),
            "hexagram_name": "",
            "porosity_ratio": record.state.get("kingwen", {}).get("porosity", 0.0),
            "temporal": record.state.get("kingwen", {}).get("phase_temporal", ""),
            "tone": "",
            "expanded_vector": record.state.get("kingwen", {}).get("emotional_vector", {}),
        }
        req2 = urllib.request.Request(
            f"{router_url}/jarvis/wake",
            data=json.dumps(wake_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as resp:
            if resp.status not in (200, 202):
                LOGGER.warning("CF /jarvis/wake returned %s", resp.status)
                return False

        return True
    except Exception as exc:
        LOGGER.warning("CF push failed: %s", exc)
        return False


def tick_push_cf(
    max_per_tick: int = _DEFAULT_MAX_PUSH_PER_TICK,
    daily_budget: int = _DEFAULT_DAILY_BUDGET,
    router_url: str = "http://localhost:8790",
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Tick push with real CF backend."""
    def _push(rec: SaveStringRecord) -> bool:
        return push_record_to_cf(rec, router_url=router_url, token=token)

    return tick_push(max_per_tick=max_per_tick, daily_budget=daily_budget, push_fn=_push)


# ── Tool implementation ────────────────────────────────────────────────────────

class SaveStringBinTool(BaseTool):
    """Local save-string bin with tick-based Cloudflare push.

    Zero CF runtime dependency for local operations.
    Push to CF only happens when explicitly called or ticked.
    """

    tool_id = "save_string_bin"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="save_string_bin",
            description=(
                "Local save-string bin: append, read, stats, tick-push to Cloudflare. "
                "Absorbs King Wen quantum state bursts locally; pushes confirmed states "
                "on tick schedule to avoid burning CF usage. "
                "Parameters: action (append|read|stats|tick_push|reset), "
                "session_id, domain, state (dict), max_per_tick, daily_budget."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action: append|read|stats|tick_push|reset",
                        "enum": ["append", "read", "stats", "tick_push", "reset"],
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID for append action",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain: session|kingwen|agent|trace",
                        "enum": ["session", "kingwen", "agent", "trace"],
                    },
                    "state": {
                        "type": "object",
                        "description": "State dict for append action",
                    },
                    "max_per_tick": {
                        "type": "integer",
                        "description": "Max pushes per tick (default 5)",
                        "default": _DEFAULT_MAX_PUSH_PER_TICK,
                    },
                    "daily_budget": {
                        "type": "integer",
                        "description": "Max CF writes per 24h (default 500)",
                        "default": _DEFAULT_DAILY_BUDGET,
                    },
                },
                "required": ["action"],
            },
        )

    def execute(
        self,
        action: str,
        session_id: str = "",
        domain: str = "session",
        state: Optional[Dict[str, Any]] = None,
        max_per_tick: int = _DEFAULT_MAX_PUSH_PER_TICK,
        daily_budget: int = _DEFAULT_DAILY_BUDGET,
        **_: Any,
    ) -> ToolResult:
        if action == "append":
            if not session_id or not state:
                return ToolResult(
                    tool_name="save_string_bin",
                    content="ERROR: session_id and state required for append",
                    success=False,
                )
            rec = SaveStringRecord(
                session_id=session_id,
                timestamp=int(time.time() * 1000),
                domain=domain,
                state=state,
            )
            append_record(rec)
            return ToolResult(
                tool_name="save_string_bin",
                content=f"Appended save-string record: {session_id} [{domain}]",
                success=True,
                metadata={"session_id": session_id, "domain": domain},
            )

        elif action == "read":
            records = read_unpaged_records()
            return ToolResult(
                tool_name="save_string_bin",
                content=json.dumps(
                    [r.__dict__ for r in records[:20]], indent=2, default=str
                ),
                success=True,
                metadata={"count": len(records)},
            )

        elif action == "stats":
            stats = get_bin_stats()
            return ToolResult(
                tool_name="save_string_bin",
                content=json.dumps(stats, indent=2),
                success=True,
                metadata=stats,
            )

        elif action == "tick_push":
            result = tick_push(
                max_per_tick=max_per_tick,
                daily_budget=daily_budget,
            )
            return ToolResult(
                tool_name="save_string_bin",
                content=json.dumps(result, indent=2),
                success=True,
                metadata=result,
            )

        elif action == "reset":
            if _BIN_PATH.exists():
                _BIN_PATH.unlink()
            if _PUSH_STATE_PATH.exists():
                _PUSH_STATE_PATH.unlink()
            return ToolResult(
                tool_name="save_string_bin",
                content="Reset save-string bin and push state",
                success=True,
            )

        else:
            return ToolResult(
                tool_name="save_string_bin",
                content=f"ERROR: unknown action '{action}'",
                success=False,
            )


# ── Registration ───────────────────────────────────────────────────────────────

ToolRegistry.register("save_string_bin")(SaveStringBinTool)
