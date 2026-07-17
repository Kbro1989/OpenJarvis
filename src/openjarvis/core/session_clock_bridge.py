"""session_clock_bridge.py

Bridge from OpenJarvis into Hermes' native session_clock provenance
system. Completely decoupled from Hermes' runtime imports using a
local contract-only implementation.

Attaches to:
- agent.session_clock.provenance(...) contract
- agent._session_clock / agent._session_tick contract
- moa_loop filter_live_slots / mark_slot_result contract
"""
from __future__ import annotations

import datetime
import threading
from typing import Any, Dict, Optional


class SessionClock:
    """Temporal authority for one session (contract-only)."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.tick_counter = 0
        self._lock = threading.Lock()

    def next_tick(self, phase: str = "agent") -> Dict[str, Any]:
        """Advance and return a fresh tick coordinate."""
        with self._lock:
            self.tick_counter += 1
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return {
                "session_id": self.session_id,
                "tick_id": self.tick_counter,
                "phase": phase,
                "wall_now": now,
            }

    def coordinate(self) -> Dict[str, Any]:
        """Current coordinate without advancing."""
        return {
            "session_id": self.session_id,
            "tick_id": self.tick_counter,
            "wall_now": self.created_at.isoformat(),
        }


_clocks: Dict[str, SessionClock] = {}
_registry_lock = threading.Lock()


def get_session_clock(session_id: str) -> SessionClock:
    """Return the SessionClock for session_id, creating it if absent."""
    with _registry_lock:
        if session_id not in _clocks:
            _clocks[session_id] = SessionClock(session_id)
        return _clocks[session_id]


def get_session_tick(session_id: str) -> Optional[str]:
    """Get the next tick identifier as a stringified dict."""
    clock = get_session_clock(session_id)
    if clock is None:
        return None
    try:
        tick = clock.next_tick(phase="session:start")
        return str(tick)
    except Exception:
        return None


def provenance(
    session_id: str,
    phase: str = "agent",
    event: str = "tick",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a provenance dict mirroring the Hermes schema contract."""
    clock = get_session_clock(session_id)
    if clock is None:
        return {}
    try:
        tick = clock.next_tick(phase=phase)
        return {
            "event": event,
            "provenance": {
                "session_id": tick["session_id"],
                "tick_id": tick["tick_id"],
                "phase": tick["phase"],
                "wall_now": tick["wall_now"],
            },
            "payload": payload or {},
        }
    except Exception:
        return {}


def tag_payload(payload: Dict[str, Any], session_id: str, phase: str, event: str) -> Dict[str, Any]:
    """Enrich a payload dictionary with temporal coordinates."""
    payload["temporal"] = {
        "session_id": session_id,
        "phase": phase,
        "event": event,
        "provenance": provenance(session_id, phase, event),
        "tick": get_session_tick(session_id),
    }
    return payload

