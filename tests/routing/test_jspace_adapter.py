"""Tests for `openjarvis.routing.jspace_adapter`."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from openjarvis.routing.jspace_adapter import (
    JSpaceReadoutAdapter,
    _cosine,
    _safe_normalize,
    _text_to_embedding,
    jacobian_lens_readout,
    read_jspace,
)


def _write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )


def test_empty_query_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    adapter = JSpaceReadoutAdapter(
        data_dir=tmp_path, cache_dir=tmp_path / "cache"
    )
    assert adapter.read_top("s", []) == []
    assert adapter.read("s", []) == []


def test_no_data_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    adapter = JSpaceReadoutAdapter(
        data_dir=tmp_path, cache_dir=tmp_path / "cache", warm=True
    )
    assert adapter.read_top("s", [0.1, 0.2]) == []
    assert not adapter.primary_is_available()


def test_primary_path_ranks_by_cosine(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    cache = tmp_path / "cache"
    _write_jsonl(
        cache / "session-artifact-ledger.jsonl",
        [
            {
                "session_id": "S1",
                "artifact_id": "a1",
                "artifact_type": "t",
                "surface": "x",
                "primary_vector": [1.0, 0.0],
            },
            {
                "session_id": "S1",
                "artifact_id": "a2",
                "artifact_type": "t",
                "surface": "x",
                "primary_vector": [0.0, 1.0],
            },
            {
                "session_id": "S2",
                "artifact_id": "b1",
                "artifact_type": "t",
                "surface": "x",
                "primary_vector": [1.0, 0.0],
            },
        ],
    )
    adapter = JSpaceReadoutAdapter(data_dir=tmp_path, cache_dir=cache)
    assert adapter.primary_is_available() is True
    out = adapter.read("S1", [1.0, 0.0], limit=10)
    assert [r.artifact_id for r in out] == ["a1", "a2"]


def test_fallback_path_when_primary_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    cache = tmp_path / "cache"
    _write_jsonl(
        cache / "curated-session-extracts.jsonl",
        [
            {
                "session_id": "S3",
                "artifact_id": "c1",
                "artifact_type": "t",
                "embedding": [1.0, 0.0],
            },
            {
                "session_id": "S3",
                "artifact_id": "c2",
                "artifact_type": "t",
                "embedding": [0.0, 1.0],
            },
        ],
    )
    adapter = JSpaceReadoutAdapter(data_dir=tmp_path, cache_dir=cache)
    assert adapter.primary_is_available() is False
    out = adapter.read("S3", [1.0, 0.0], limit=10)
    assert [r.artifact_id for r in out] == ["c1", "c2"]
    assert out[0].score == pytest.approx(1.0, abs=1e-6)
    assert out[0].source.startswith("fallback:")


def test_fallback_session_filtering(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    cache = tmp_path / "cache"
    _write_jsonl(
        cache / "curated-session-extracts.jsonl",
        [
            {
                "session_id": "S4",
                "artifact_id": "d1",
                "embedding": [1.0, 0.0],
            },
            {
                "session_id": "S5",
                "artifact_id": "d2",
                "embedding": [1.0, 0.0],
            },
        ],
    )
    adapter = JSpaceReadoutAdapter(data_dir=tmp_path, cache_dir=cache)
    out = adapter.read("S4", [1.0, 0.0], limit=10)
    assert [r.artifact_id for r in out] == ["d1"]


def test_deduplication_in_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    cache = tmp_path / "cache"
    _write_jsonl(
        cache / "curated-session-extracts.jsonl",
        [
            {
                "session_id": "S6",
                "artifact_id": "e1",
                "embedding": [1.0, 0.0],
            },
            {
                "session_id": "S6",
                "artifact_id": "e1",
                "embedding": [1.0, 0.0],
            },
        ],
    )
    adapter = JSpaceReadoutAdapter(data_dir=tmp_path, cache_dir=cache)
    out = adapter.read("S6", [1.0, 0.0], limit=10)
    assert len(out) == 1


def test_search_in_progress_relaxes_session_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    cache = tmp_path / "cache"
    ledgers = [
        {
            "session_id": "S7a",
            "artifact_id": "f1",
            "artifact_type": "t",
            "primary_vector": [1.0, 0.0],
        },
        {
            "session_id": "S7b",
            "artifact_id": "f2",
            "artifact_type": "t",
            "primary_vector": [0.0, 1.0],
        },
    ]
    _write_jsonl(cache / "session-artifact-ledger.jsonl", ledgers)
    adapter = JSpaceReadoutAdapter(data_dir=tmp_path, cache_dir=cache)
    out = adapter.read(None, [1.0, 0.0], search_in_progress=True, limit=10)
    assert [r.session_id for r in out] == ["S7a", "S7b"]


def test_read_jspace_convenience_wrapper(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    cache = tmp_path / "cache"
    _write_jsonl(
        cache / "curated-session-extracts.jsonl",
        [
            {
                "session_id": "S8",
                "artifact_id": "g1",
                "embedding": [1.0, 0.0],
            },
        ],
    )
    out = read_jspace("S8", [1.0, 0.0], top_k=5)
    assert len(out) == 1
    assert out[0]["source"].startswith("fallback:")


def test_jacobian_lens_readout_query_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    JSpaceReadoutAdapter(
        data_dir=tmp_path, cache_dir=tmp_path / "cache"
    )
    out = jacobian_lens_readout("S9", [0.7, 0.0], top_k=3, mark_unavailable=True)
    assert len(out) == 1
    assert out[0]["source"] == "query_vector_fallback"


def test_deterministic_text_embedding():
    v1 = _text_to_embedding("hello")
    v2 = _text_to_embedding("hello")
    assert v1 == v2
    assert all(isinstance(x, float) for x in v1)
    assert len(v1) == 768


def test_normalize_and_cosine_helpers():
    assert _safe_normalize([]) == ()
    one = [3.0, 4.0]
    norm = _safe_normalize(one)
    assert pytest.approx(math.sqrt(sum(x * x for x in norm)), abs=1e-9) == 1.0
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0, abs=1e-9)
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0, abs=1e-9)
