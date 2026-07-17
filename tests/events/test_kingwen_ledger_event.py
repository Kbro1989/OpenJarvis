"""Minimal verification for King Wen ledger event channel."""
from __future__ import annotations

from openjarvis.core.events import EventBus, EventType


def test_kingwen_ledger_write_event_registered() -> None:
    assert EventType.KINGWEN_LEDGER_WRITE == "kingwen_ledger_write"


def test_kingwen_ledger_write_event_bus_publish() -> None:
    bus = EventBus(record_history=True)
    received = []
    bus.subscribe(EventType.KINGWEN_LEDGER_WRITE, lambda e: received.append(e))
    event = bus.publish(
        EventType.KINGWEN_LEDGER_WRITE,
        {"ledger_record": {"session_id": "s1", "artifact_type": "kingwen_turn_start"}},
    )
    assert event.event_type == EventType.KINGWEN_LEDGER_WRITE
    assert event.data["ledger_record"]["session_id"] == "s1"
    assert len(bus.history) == 1
    assert len(received) == 1
