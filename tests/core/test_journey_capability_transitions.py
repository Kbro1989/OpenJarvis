from __future__ import annotations

from typing import Any, Dict, List

import pytest

from openjarvis.core.events import Event, EventType, reset_event_bus
from openjarvis.core.journey_executor import JourneyExecutor


class FakeBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event_type: EventType, data: Dict[str, Any] | None = None) -> Event:
        event = Event(event_type=event_type, timestamp=0.0, data=data or {})
        self.events.append(event)
        return event


class _FakeLookupExecutor(JourneyExecutor):
    def __init__(self, *, fake_return, bus, **kwargs):
        super().__init__(event_bus=bus, **kwargs)
        self._fake_return = fake_return
        self._novel_edges: list[dict[str, Any]] = []

    def _run_lookup_script(self, query: str, autotags: List[str] | None) -> Dict[str, Any]:
        return self._fake_return

    def _detect_novel_edges(self, matches):
        return self._novel_edges


class _RaisingExecutor(JourneyExecutor):
    def _compute_capability_transitions(self, matches):  # type: ignore[override]
        raise RuntimeError("kaput")


def test_lookup_appends_capability_transitions_and_preserves_match_output():
    reset_event_bus()
    bus = FakeBus()
    fake_return = {
        "matches": [
            {
                "session_id": "s1",
                "score": 0.9,
                "synaptic_weight": 1.0,
                "intent": "alpha",
                "cluster": ["alpha", "beta"],
                "related_sessions": ["s2"],
                "path": "/tmp/s1",
                "artifact_type": "session_dump",
                "surface": "shared",
            },
            {
                "session_id": "s2",
                "score": 0.7,
                "synaptic_weight": 0.9,
                "intent": "beta",
                "cluster": ["beta", "gamma"],
                "related_sessions": ["s1"],
                "path": "/tmp/s2",
                "artifact_type": "session_dump",
                "surface": "shared",
            },
        ]
    }
    exe = _FakeLookupExecutor(fake_return=fake_return, bus=bus)

    matches = exe.lookup("test")

    assert len(matches) == 2
    assert matches[0].session_id == "s1"
    assert matches[1].session_id == "s2"

    journey_events = [e for e in bus.events if e.event_type == EventType.JOURNEY_ARRIVAL]
    assert len(journey_events) == 1
    payload = journey_events[0].data

    assert payload["query"] == "test"
    assert payload["match_count"] == 2
    assert payload["top_session"] == "s1"
    assert pytest.approx(payload["top_score"]) == 0.9
    assert len(payload["matches"]) == 2
    assert payload["matches"][0]["session_id"] == "s1"
    assert payload["matches"][1]["session_id"] == "s2"
    assert "capability_transitions" in payload
    assert isinstance(payload["capability_transitions"], list)
    assert len(payload["capability_transitions"]) == 1
    assert payload["capability_transitions"][0]["from"] == "s1"
    assert payload["capability_transitions"][0]["to"] == "s2"


def test_lookup_capability_transitions_empty_on_single_match():
    reset_event_bus()
    bus = FakeBus()
    fake_return = {
        "matches": [
            {
                "session_id": "s1",
                "score": 0.9,
                "synaptic_weight": 1.0,
                "intent": "alpha",
                "cluster": ["alpha"],
                "related_sessions": [],
                "path": "/tmp/s1",
                "artifact_type": "session_dump",
                "surface": "shared",
            }
        ]
    }
    exe = _FakeLookupExecutor(fake_return=fake_return, bus=bus)

    matches = exe.lookup("test")

    assert len(matches) == 1
    payload = bus.events[0].data
    assert payload["capability_transitions"] == []


def test_lookup_safe_when_capability_computation_raises():
    reset_event_bus()
    bus = FakeBus()
    fake_return = {
        "matches": [
            {
                "session_id": "s1",
                "score": 0.9,
                "synaptic_weight": 1.0,
                "intent": "alpha",
                "cluster": ["alpha", "beta"],
                "related_sessions": ["s2"],
                "path": "/tmp/s1",
                "artifact_type": "session_dump",
                "surface": "shared",
            },
            {
                "session_id": "s2",
                "score": 0.7,
                "synaptic_weight": 0.9,
                "intent": "beta",
                "cluster": ["beta", "gamma"],
                "related_sessions": ["s1"],
                "path": "/tmp/s2",
                "artifact_type": "session_dump",
                "surface": "shared",
            },
        ]
    }
    exe = _RaisingExecutor(event_bus=bus)
    exe._run_lookup_script = lambda query, autotags: fake_return  # type: ignore[method-assign]
    exe._detect_novel_edges = lambda matches: []  # type: ignore[method-assign]

    matches = exe.lookup("test")

    assert len(matches) == 2
    payload = bus.events[0].data
    assert payload["capability_transitions"] == []
    assert payload["top_session"] == "s1"
