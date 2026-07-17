"""Minimal verification for causality ledger module."""
from __future__ import annotations

import json
from pathlib import Path

from openjarvis.core.causality_ledger import (
    CausalityLedgerRecord,
    record_from_session_artifact,
    append,
    LEDGER_PATH,
)


def test_record_from_session_artifact_roundtrip(tmp_path: Path) -> None:
    LEDGER_PATH = str(tmp_path / "ledger.jsonl")
    record = record_from_session_artifact(
        session_id="s1",
        surface="cli",
        artifact_type="session_dump",
        artifact_id="id",
        path="path",
        intent="intent",
        intent_source="user_first",
        cluster=["a", "b"],
        synaptic_weight=0.9,
        tags=["a"],
        reason="agent_turn_start",
        model="m",
        parent_artifact_id=None,
        consumer="all",
        kingwen={"hexagram_id": 1},
        provenance={"source": "agent_turn_start"},
    )
    assert record.session_id == "s1"
    assert record.synaptic_weight == 0.9
    assert record.kingwen == {"hexagram_id": 1}
    data = record.to_dict()
    assert data["session_id"] == "s1"
    assert data["artifact_type"] == "session_dump"


def test_append_writes_jsonl(tmp_path: Path) -> None:
    import openjarvis.core.causality_ledger as ledger_mod
    ledger_mod.LEDGER_PATH = str(tmp_path / "ledger.jsonl")
    record = record_from_session_artifact(
        session_id="s2",
        surface="cli",
        artifact_type="session_dump",
        artifact_id="id2",
        path="path2",
        intent="intent2",
        intent_source="user_first",
        cluster=["x"],
        synaptic_weight=1.0,
        tags=["x"],
    )
    append(record)
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["session_id"] == "s2"
    assert parsed["kingwen"] == {}
