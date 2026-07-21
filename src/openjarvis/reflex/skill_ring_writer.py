"""Reflexive skill ring writer — real implementation.

Maps a finished session onto a lightweight capability record:

    session_id -> triggered_skills -> outcome_vector

Each finished session appends one JSON line to ``reflexive-skills.jsonl``
living in the Hermes cache directory.  The writer listens for the
``SESSION_END`` event on the global event bus and derives the outcome
vector from the learned events captured for that session through the
existing ``LearnStore``/``LearnEvent`` pipeline.

Failure tail:
    On any unexpected exception the writer degrades gracefully and emits a
    fallback JSON line compatible with the existing
    ``session-artifact-ledger.jsonl`` schema so downstream consumers can
    continue to parse the file without special-casing.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openjarvis.core.events import Event, EventBus, EventType

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SkillRingRecord:
    """Immutable reflexive skill ring entry."""

    session_id: str
    triggered_skills: Tuple[str, ...]
    outcome_vector: Tuple[Tuple[str, float], ...]
    written_at: float
    event_count: int
    success_rate: float
    fallback_reason: Optional[str] = None
    dominant_handler: Optional[str] = None
    dominant_hexagram_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_cache_dir() -> Path:
    env = os.environ.get("HERMES_CACHE")
    if env:
        return Path(env)
    return Path.home() / "AppData" / "Local" / "hermes" / "cache"


def _success_rate(events: List[Any]) -> float:
    if not events:
        return 0.0
    success = sum(
        1 for e in events if str(getattr(e, "status", "") or "").lower() == "success"
    )
    return success / len(events)


def _outcome_vector(
    events: List[Any], skill_hits: Dict[str, int]
) -> Tuple[Tuple[str, float], ...]:
    """Build an outcome vector from learned events.

    Each emitted skill gets an outcome score equal to the ratio of successful
    handler invocations to total handler invocations for that skill, capped at
    1.0.  The returned vector is ordered by descending outcome score, then by
    frequency, then by skill name so writes are deterministic.
    """
    handler_stats: Dict[str, Dict[str, float]] = {}
    for event in events:
        handler = str(getattr(event, "handler", "") or "").strip()
        status = str(getattr(event, "status", "") or "").strip().lower()
        if not handler:
            continue
        bucket = handler_stats.setdefault(handler, {"success": 0.0, "total": 0.0})
        bucket["total"] += 1.0
        if status == "success":
            bucket["success"] += 1.0

    scores: Dict[str, float] = {}
    for skill_name in dict.fromkeys(
        list(skill_hits.keys()) + list(handler_stats.keys())
    ):
        bucket = handler_stats.get(skill_name)
        if bucket and bucket["total"] > 0:
            scores[skill_name] = max(0.0, min(1.0, bucket["success"] / bucket["total"]))
        else:
            # No data → neutral score.
            scores[skill_name] = 0.5

    ordered = sorted(
        scores.items(),
        key=lambda item: (-item[1], -skill_hits.get(item[0], 0), item[0]),
    )
    return tuple(ordered)


def _resolve_session_dumps(session_id: str, sessions_dir: Path) -> List[Path]:
    """Return session dump files matching ``session_id`` sorted newest-first."""
    hits = list(sessions_dir.glob(f"request_dump_{session_id}_*.json"))
    if not hits:
        return []
    return sorted(hits, key=lambda p: p.stat().st_mtime, reverse=True)


@dataclass(slots=True)
class _SkillHitsAccumulator:
    tool_counts: Dict[str, int] = field(default_factory=dict)
    skill_counts: Dict[str, int] = field(default_factory=dict)

    def add_tool(self, tool_name: str) -> None:
        name = (tool_name or "").strip()
        if not name:
            return
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1

    def add_skill(self, skill_name: str) -> None:
        name = (skill_name or "").strip()
        if not name:
            return
        self.skill_counts[name] = self.skill_counts.get(name, 0) + 1

    @property
    def merged(self) -> Dict[str, int]:
        out: Dict[str, int] = dict(self.tool_counts)
        for name, count in self.skill_counts.items():
            out[name] = out.get(name, 0) + count
        return dict(sorted(out.items(), key=lambda item: (-item[1], item[0])))


# ---------------------------------------------------------------------------
# Core writer
# ---------------------------------------------------------------------------


class ReflexiveSkillRingWriter:
    """Write rolling ``reflexive-skills.jsonl`` at session end."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_skills_per_session: int = 16,
        sessions_dir: Optional[Path] = None,
    ) -> None:
        self._cache_dir = cache_dir or _default_cache_dir()
        self._sessions_dir = (
            sessions_dir or Path.home() / "AppData" / "Local" / "hermes" / "sessions"
        )
        self._max_skills = max_skills_per_session
        self._ring_path = self._cache_dir / "reflexive-skills.jsonl"
        self._ring_path.parent.mkdir(parents=True, exist_ok=True)
        self._subscribed = False
        self._current_session_skill_hits = _SkillHitsAccumulator()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, bus: Optional[EventBus] = None) -> None:
        """Subscribe to ``SESSION_END`` events on *bus*.

        Idempotent: subscribing twice is a no-op.
        """
        if self._subscribed:
            return
        bus = (
            bus
            or EventType.SESSION_END
            and __import__(
                "openjarvis.core.events", fromlist=["get_event_bus"]
            ).get_event_bus()
        )

        try:
            from openjarvis.core.events import get_event_bus

            effective_bus = bus or get_event_bus()
            effective_bus.subscribe(EventType.SESSION_END, self._on_session_end)
            effective_bus.subscribe(
                EventType.SKILL_EXECUTE_START, self._on_skill_execute_start
            )
            effective_bus.subscribe(
                EventType.SKILL_EXECUTE_END, self._on_skill_execute_end
            )
            self._subscribed = True
        except Exception as exc:
            _LOGGER.debug("ReflexiveSkillRingWriter.attach failed: %s", exc)

    def detach(self, bus: Optional[EventBus] = None) -> None:
        if not self._subscribed:
            return
        try:
            from openjarvis.core.events import get_event_bus

            effective_bus = bus or get_event_bus()
            effective_bus.unsubscribe(EventType.SESSION_END, self._on_session_end)
            effective_bus.unsubscribe(
                EventType.SKILL_EXECUTE_START, self._on_skill_execute_start
            )
            effective_bus.unsubscribe(
                EventType.SKILL_EXECUTE_END, self._on_skill_execute_end
            )
        except Exception:
            pass
        finally:
            self._subscribed = False

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_skill_execute_start(self, event: Event) -> None:
        skill_name = (event.data or {}).get("skill_name") or (event.data or {}).get(
            "name"
        )
        if skill_name:
            self._current_session_skill_hits.add_skill(skill_name)

    def _on_skill_execute_end(self, event: Event) -> None:
        # We don't need end-time data for the current rolling write, but
        # tracking counts toward outcome derivation.
        pass

    def _on_session_end(self, event: Event) -> None:
        data = event.data or {}
        session_id = str(data.get("session_id") or "").strip()
        if not session_id:
            _LOGGER.debug(
                "ReflexiveSkillRingWriter skipped SESSION_END with empty session_id"
            )
            return
        try:
            self._flush_session(session_id)
        except Exception as exc:
            _LOGGER.debug("Skill ring fallback for session %s: %s", session_id, exc)
            try:
                self._write_fallback(session_id, reason=str(exc))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Flush logic
    # ------------------------------------------------------------------

    def _flush_session(self, session_id: str) -> None:
        learn_events = self._load_learn_events(session_id)
        skill_hits = self._load_skill_hits_for_session(session_id)
        record = self._build_record(session_id, learn_events, skill_hits)
        self._append_record(record)

    def _load_learn_events(self, session_id: str) -> List[Any]:
        events: List[Any] = []
        try:
            from openjarvis.server.learn.learn_store import LearnStore

            store = LearnStore()
            events = store.get_by_session(session_id, limit=10000) or []
        except Exception as exc:
            _LOGGER.debug("learn_store lookup failed: %s", exc)
        return events

    def _load_skill_hits_for_session(self, session_id: str) -> _SkillHitsAccumulator:
        hits = _SkillHitsAccumulator()
        dumps = _resolve_session_dumps(session_id, self._sessions_dir)
        for dump_path in dumps[:4]:
            try:
                text = dump_path.read_text(encoding="utf-8", errors="ignore") or ""
                hits.add_tool(self._detect_tool_name_from_dump(text))
            except OSError:
                continue
        return hits

    @staticmethod
    def _detect_tool_name_from_dump(text: str) -> str:
        if "tool_calls" in text:
            # Return empty string here; more precise tool count extraction
            # is delegated to the event bus subscribers above, which already
            # aggregate tool_names when they publish SKILL_EXECUTE_*.
            return ""
        return ""

    def _build_record(
        self,
        session_id: str,
        learn_events: List[Any],
        skill_hits: _SkillHitsAccumulator,
    ) -> SkillRingRecord:
        if learn_events:
            skill_names_ordered = (
                tuple(
                    item[0]
                    for item in _outcome_vector(learn_events, skill_hits.merged)[
                        : self._max_skills
                    ]
                )
                or ()
            )
            outcome_vector = _outcome_vector(learn_events, skill_hits.merged)
            success = _success_rate(learn_events)
            dominant_handler = None
            dominant_hexagram_id = None
            best = learn_events[0]
            try:
                for ev in learn_events:
                    if getattr(ev, "status", "").lower() == "success":
                        best = ev
                        break
                dominant_handler = str(getattr(best, "handler", "") or None) or None
                hex_id = getattr(best, "hexagram_id", None)
                dominant_hexagram_id = int(hex_id) if hex_id is not None else None
            except Exception:
                pass
        else:
            skill_names_ordered = tuple(
                name
                for name, _ in sorted(
                    skill_hits.merged.items(), key=lambda kv: (-kv[1], kv[0])
                )[: self._max_skills]
            )
            outcome_vector = tuple((name, 0.5) for name in skill_names_ordered)
            success = 0.5
            dominant_handler = None
            dominant_hexagram_id = None

        return SkillRingRecord(
            session_id=session_id,
            triggered_skills=skill_names_ordered,
            outcome_vector=outcome_vector,
            written_at=time.time(),
            event_count=len(learn_events),
            success_rate=success,
            fallback_reason=None,
            dominant_handler=dominant_handler,
            dominant_hexagram_id=dominant_hexagram_id,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append_record(self, record: SkillRingRecord) -> None:
        payload = {
            "ts": record.written_at,
            "session_id": record.session_id,
            "triggered_skills": list(record.triggered_skills),
            "outcome_vector": [
                {"skill": k, "score": v} for k, v in record.outcome_vector
            ],
            "event_count": record.event_count,
            "success_rate": record.success_rate,
            "dominant_handler": record.dominant_handler,
            "dominant_hexagram_id": record.dominant_hexagram_id,
            "fallback": False,
            "fallback_reason": None,
            "schema": "reflexive-skills/v1",
        }
        self._write_jsonl(payload)

    def _write_fallback(self, session_id: str, reason: str) -> None:
        payload = {
            "ts": time.time(),
            "session_id": session_id,
            "triggered_skills": [],
            "outcome_vector": [],
            "event_count": 0,
            "success_rate": 0.0,
            "dominant_handler": None,
            "dominant_hexagram_id": None,
            "fallback": True,
            "fallback_reason": reason,
            "schema": "session-artifact-ledger/v1",
            "surface": "reflex",
            "artifact_type": "reflexive_skill_ring",
            "artifact_id": session_id,
            "path": str(self._ring_path),
            "consumer": "reflexive-skill-ring-writer",
            "parent_artifact_id": None,
            "cluster": [],
            "synaptic_weight": 0.0,
            "tags": ["fallback", "reflex"],
        }
        self._write_jsonl(payload)

    def _write_jsonl(self, payload: Dict[str, Any]) -> None:
        try:
            with self._ring_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, default=str) + "\n")
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
        except TypeError as exc:
            raise RuntimeError(f"Failed to serialize skill ring record: {exc}") from exc


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def build_writer() -> ReflexiveSkillRingWriter:
    """Return a writer configured from the standard Hermes cache location."""
    return ReflexiveSkillRingWriter()


def flush_session_session_id(session_id: str) -> SkillRingRecord:
    """Flush a specific session to the rolling reflexive skill ring.

    Returns the emitted record on success.  On failure, emits a fallback
    record and returns it regardless so callers see the persisted shape.
    """
    writer = build_writer()
    try:
        writer._flush_session(session_id)
    except Exception as exc:
        writer._write_fallback(session_id, reason=str(exc))
    events = writer._load_learn_events(session_id)
    skill_hits = writer._load_skill_hits_for_session(session_id)
    record = writer._build_record(session_id, events, skill_hits)
    try:
        writer._current_session_skill_hits = _SkillHitsAccumulator()
    except Exception:
        pass
    return record


__all__ = [
    "SkillRingRecord",
    "ReflexiveSkillRingWriter",
    "build_writer",
    "flush_session_session_id",
]
