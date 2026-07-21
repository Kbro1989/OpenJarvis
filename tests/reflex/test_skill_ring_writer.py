"""Tests for ReflexiveSkillRingWriter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from openjarvis.core.events import EventBus, EventType
from openjarvis.reflex.skill_ring_writer import (
    ReflexiveSkillRingWriter,
    SkillRingRecord,
    _SkillHitsAccumulator,
    _outcome_vector,
    _success_rate,
    flush_session_session_id,
)


class FakeEvent:
    def __init__(self, data):
        self.data = data or {}


def test_success_rate_empty():
    assert _success_rate([]) == 0.0


def test_outcome_vector_empty():
    events = []
    hits = {}
    assert _outcome_vector(events, hits) == ()


def test_skill_hits_accumulator_merge():
    acc = _SkillHitsAccumulator()
    acc.add_tool("web_search")
    acc.add_tool("web_search")
    acc.add_skill("wiki-math-parser")
    merged = acc.merged
    assert merged["web_search"] == 2
    assert merged["wiki-math-parser"] == 1


def test_write_session_end_no_learn_events():
    with tempfile.TemporaryDirectory() as td:
        ring = Path(td) / "reflexive-skills.jsonl"
        writer = ReflexiveSkillRingWriter(cache_dir=Path(td))
        bus = EventBus()
        writer.attach(bus)
        bus.publish(EventType.SESSION_END, {"session_id": "nostore"})
        lines = ring.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["session_id"] == "nostore"
        assert payload["fallback"] is False
        assert payload["schema"] == "reflexive-skills/v1"


def test_fallback_on_flush_exception(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        ring = Path(td) / "reflexive-skills.jsonl"
        writer = ReflexiveSkillRingWriter(cache_dir=Path(td))
        writer._flush_session = lambda session_id: (_ for _ in ()).throw(RuntimeError("boom"))
        bus = EventBus()
        writer.attach(bus)
        bus.publish(EventType.SESSION_END, {"session_id": "bad"})
        lines = ring.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["session_id"] == "bad"
        assert payload["fallback"] is True
        assert payload["schema"] == "session-artifact-ledger/v1"


def test_record_shape_from_build_record(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        writer = ReflexiveSkillRingWriter(cache_dir=Path(td))
        # Stub learn events
        class Evt:
            handler = "/oracle"
            status = "success"
            hexagram_id = 1
        record = writer._build_record("x1", [Evt()], _SkillHitsAccumulator())
        assert record.session_id == "x1"
        assert record.success_rate == 1.0
        assert record.dominant_handler == "/oracle"
        assert record.dominant_hexagram_id == 1
