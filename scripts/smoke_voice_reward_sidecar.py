"""Live smoke test for voice_reward_sidecar upgrade."""

from __future__ import annotations

import tempfile
from pathlib import Path

import openjarvis.speech.voice_reward_sidecar as sidecar

v = sidecar


def _new_store(db_path: Path):
    TraceStore = __import__(
        "openjarvis.traces.store", fromlist=["TraceStore"]
    ).TraceStore
    return TraceStore(db_path)


def test_backward_compatible_scalar() -> None:
    score = v.compute_voice_score(
        compliance="compliant",
        porosity=0.35,
        vector={"coherence": 0.6},
        dsp_meta={},
    )
    assert 0.0 <= score <= 1.0, score
    print(f"scalar_score={score}")


def test_missing_crowd_payload_returns_none() -> None:
    assert v.compute_crowd_vector_scores({}) is None
    assert v.compute_crowd_vector_scores({"nope": 1}) is None


def test_vector_crowd_scoring() -> None:
    votes = [0.0] * 512
    votes[42] = 1.0
    votes[300] = 1.0
    data = {
        "compliance": "compliant",
        "porosity": 0.5,
        "voice_vector": {"coherence": 0.9},
        "dsp_meta": {"error": "dsp:x"},
        "crowd_votes": votes,
    }
    scores = v.compute_crowd_vector_scores(data)
    assert scores is not None, scores
    assert scores["crowd_entropy"] > 0.0
    assert scores["dsp_fidelity"] == 0.0
    print(f"vector_scores={scores}")


def test_scalar_persist_and_table_migration() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "traces.db"
        store = _new_store(db_path)
        original_getter = v._get_trace_store
        try:
            v._get_trace_store = lambda: store
            v._ensure_table(store)
            row = store.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (v.KINGWEN_VOICE_REWARDS_TABLE,),
            )
            assert row and row[0] == v.KINGWEN_VOICE_REWARDS_TABLE
            cols = {r[1] for r in store._conn.execute(
                f"PRAGMA table_info({v.KINGWEN_VOICE_REWARDS_TABLE})"
            ).fetchall()}
            missing = set(v._VECTOR_COLUMNS.keys()) - cols
            assert not missing, missing
            v.persist_voice_reward(
                {
                    "session_id": "s-1",
                    "hexagram_id": 1,
                    "compliance": "compliant",
                    "violations": [],
                    "timestamp": 1.0,
                },
                score=0.9,
            )
            rows = store._conn.execute(
                "SELECT score, score_type, score_crowd_entropy"
                f" FROM {v.KINGWEN_VOICE_REWARDS_TABLE}"
            ).fetchall()
            row = next((r for r in rows if r[0] == 0.9), None)
            if row is None:
                raise AssertionError(f"inserted row not found; raw rows={rows}")
            assert row == (0.9, "scalar", None), row
        finally:
            v._get_trace_store = original_getter
            store.close()


def test_unique_reward_per_event_invariants() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "traces.db"
        store = _new_store(db_path)
        original_getter = v._get_trace_store
        try:
            v._get_trace_store = lambda: store
            v._ensure_table(store)
            event = {
                "session_id": "s-u1",
                "hexagram_id": 3,
                "compliance": "compliant",
                "violations": [],
                "timestamp": 3.0,
            }
            v.persist_voice_reward(event, score=0.5)
            v.persist_voice_reward(event, score=0.6)
            row = store.fetchone(
                f"SELECT COUNT(*) FROM {v.KINGWEN_VOICE_REWARDS_TABLE} WHERE session_id='s-u1'"
            )
            assert row and row[0] == 2, row
        finally:
            v._get_trace_store = original_getter
            store.close()


def test_vector_persist() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "traces.db"
        store = _new_store(db_path)
        original_getter = v._get_trace_store
        try:
            v._get_trace_store = lambda: store
            v._ensure_table(store)
            data = {
                "session_id": "s-v",
                "hexagram_id": 2,
                "compliance": "compliant",
                "violations": [],
                "timestamp": 2.0,
                "crowd_votes": [0.0] * 512,
            }
            scores = {
                "compliance": 0.8,
                "porosity_match": 0.7,
                "vector_truth": 0.9,
                "dsp_fidelity": 1.0,
                "crowd_entropy": 0.3,
            }
            v.persist_voice_reward(data, score=0.9, vector_scores=scores)
            sql = (
                "SELECT score, score_type, score_crowd_entropy, "
                f"crowd_votes_json FROM {v.KINGWEN_VOICE_REWARDS_TABLE} WHERE session_id=?"
            )
            print("SQL", sql)
            row = store.fetchone(sql, ("s-v",))
            assert row, row
            assert row[0] == 0.9, row
            assert row[1] == "vector", row
            assert row[2] == 0.3, row
            assert row[3] is not None, row
        finally:
            v._get_trace_store = original_getter
            store.close()


def main() -> int:
    test_backward_compatible_scalar()
    test_missing_crowd_payload_returns_none()
    test_vector_crowd_scoring()
    test_scalar_persist_and_table_migration()
    test_unique_reward_per_event_invariants()
    test_vector_persist()
    print("smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
