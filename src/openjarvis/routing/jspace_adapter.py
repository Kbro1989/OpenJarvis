"""J-Space readout adapter for Hermes.

Implements WS-01: J-lens-inspired vector readout over captured JSONL datasets
**without model surgery**.  The module prefers the primary ledger and falls
back to cosine similarity over ``curated-session-extracts.jsonl`` when that
source is missing or empty.

Public API
----------
* :class:`JSpaceReadoutAdapter`
* :func:`read_jspace`
* :func:`jacobian_lens_readout`

Fallback behavior
-----------------
1. ``session-artifact-ledger.jsonl`` present?
   -> Yes: rank by cosine to ``query_vector``.
   -> No: fall back to curated extracts.
2. ``curated-session-extracts.jsonl`` present?
   -> Yes: cosine similarity ranking.
   -> No: return ``[]`` without raising.
3. If neither exposes usable vectors, preserve flow and callers may use an
   externally supplied query vector.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openjarvis.core.paths import get_cache_dir, get_data_dir

logger = logging.getLogger("openjarvis.routing.jspace_adapter")


@dataclass(slots=True)
class JSpaceRecord:
    """Single vector readout record with stable identity and provenance."""

    session_id: str = ""
    artifact_type: str = ""
    artifact_id: str = ""
    rank: int = 0
    score: float = 0.0
    primary_vector: Tuple[float, ...] = ()
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "rank": self.rank,
            "score": self.score,
            "primary_vector_length": len(self.primary_vector),
            "source": self.source,
            "metadata": self.metadata,
        }


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _safe_normalize(vector: Sequence[float]) -> Tuple[float, ...]:
    if not vector:
        return ()
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return ()
    return tuple(x / norm for x in vector)


def _text_to_embedding(text: str, *, dim: int = 768) -> Tuple[float, ...]:
    if dim <= 0:
        return ()
    src = (text or "").encode("utf-8", errors="ignore")
    out = [0.0] * dim
    h = 0x6C3BF9C8 if not src else 0x6C3BF9C8
    for byte in src:
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    for idx in range(dim):
        h = (h * 0x100000001B3 + idx) & 0xFFFFFFFFFFFFFFFF
        bucket = int(h % 701) - 350
        if bucket == 0:
            bucket = idx + 1
        out[idx % dim] += (
            float(h % 2953) / float(abs(bucket) + 1) if bucket else 0.0
        )
    folded = _safe_normalize(out)
    return folded if folded else (0.0,) * dim


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _best_vector(record: Dict[str, Any]) -> Tuple[Tuple[float, ...], str]:
    for key in ("primary_vector", "vector", "embedding", "fallback_vector"):
        value = record.get(key)
        if value:
            return tuple(float(x) for x in value), key
    return (), "missing"


def _session_id(record: Dict[str, Any]) -> str:
    return str(
        record.get("session_id")
        or record.get("sessionId")
        or record.get("session")
        or ""
    )


def _artifact_id(record: Dict[str, Any]) -> str:
    return str(
        record.get("artifact_id")
        or record.get("artifactId")
        or record.get("id")
        or ""
    )


def _artifact_type(record: Dict[str, Any]) -> str:
    return str(record.get("artifact_type") or record.get("type") or "")


def _iter_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            out.append(json.loads(raw_line))
        except json.JSONDecodeError:
            continue
    return out


def _load_core_ledger_records(data_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = data_dir or get_data_dir()
    candidates = [
        root / "cache" / "session-artifact-ledger.jsonl",
        root / "session-artifact-ledger.jsonl",
        Path.cwd() / "cache" / "session-artifact-ledger.jsonl",
        Path.cwd() / "session-artifact-ledger.jsonl",
    ]
    out: List[Dict[str, Any]] = []
    for path in candidates:
        out.extend(_iter_jsonl(path))
    return out


def _load_curated_extracts(
    data_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    root = data_dir or get_cache_dir()
    data_root = get_data_dir() if data_dir is None else data_dir
    candidates = [
        root / "curated-session-extracts.jsonl",
        data_root / "cache" / "curated-session-extracts.jsonl",
        root / "curated_extracts.jsonl",
        data_root / "curated-session-extracts.jsonl",
    ]
    out: List[Dict[str, Any]] = []
    for path in candidates:
        out.extend(_iter_jsonl(path))
    return out


# ---------------------------------------------------------------------------
# Internal readouts
# ---------------------------------------------------------------------------


def _readout_from_ledger(
    session_id: Optional[str],
    query_vector: Sequence[float],
    *,
    search_in_progress: bool = False,
    ledger: Optional[List[Dict[str, Any]]] = None,
) -> List[JSpaceRecord]:
    if query_vector is None or not query_vector:
        return []
    ledger = ledger if ledger is not None else _load_core_ledger_records()
    if not ledger:
        return []
    norm_q = _safe_normalize(list(query_vector))
    out: List[JSpaceRecord] = []
    seen: set = set()
    rank = 0
    for record in ledger:
        session_text = _session_id(record)
        if session_id and session_text and not search_in_progress:
            if session_text != session_id:
                continue
        artifact_id = _artifact_id(record)
        if artifact_id and artifact_id in seen:
            continue
        vector_value, vec_key = _best_vector(record)
        if not vector_value:
            continue
        score = _cosine(norm_q, _safe_normalize(vector_value))
        out.append(
            JSpaceRecord(
                session_id=session_text or session_id or "",
                artifact_type=_artifact_type(record),
                artifact_id=artifact_id,
                rank=rank,
                score=round(score, 8),
                primary_vector=vector_value,
                source=vec_key,
                metadata={
                    "readout_timestamp": _now_iso(),
                    "surface": str(
                        record.get("surface") or record.get("consumer") or ""
                    ),
                    "synaptic_weight": record.get("synaptic_weight"),
                },
            )
        )
        rank += 1
        if artifact_id:
            seen.add(artifact_id)
    out.sort(key=lambda rec: (-rec.score, rec.rank))
    for idx, rec in enumerate(out):
        rec.rank = idx
    return out


def _fallback_cosine_over_extracts(
    session_id: Optional[str],
    query_vector: Sequence[float],
    *,
    limit: int = 32,
    extracts: Optional[List[Dict[str, Any]]] = None,
) -> List[JSpaceRecord]:
    if query_vector is None or not query_vector:
        return []
    norm_q = _safe_normalize(list(query_vector))
    if not norm_q:
        return []
    extracts = extracts if extracts is not None else _load_curated_extracts()
    scored: List[Tuple[float, int, Dict[str, Any]]] = []
    for idx, record in enumerate(extracts):
        vector_value, _ = _best_vector(record)
        if not vector_value:
            continue
        if session_id:
            session_text = _session_id(record)
            if session_text and session_text != session_id:
                continue
        scored.append(
            (_cosine(norm_q, _safe_normalize(vector_value)), idx, record)
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    result: List[JSpaceRecord] = []
    seen: set = set()
    for rank, (score, _, record) in enumerate(scored[:limit]):
        vector_value, vec_key = _best_vector(record)
        artifact_id = _artifact_id(record)
        if artifact_id and artifact_id in seen:
            continue
        if artifact_id:
            seen.add(artifact_id)
        result.append(
            JSpaceRecord(
                session_id=_session_id(record) or session_id or "",
                artifact_type=_artifact_type(record),
                artifact_id=artifact_id,
                rank=rank,
                score=round(score, 8),
                primary_vector=vector_value,
                source=f"fallback:{vec_key}",
                metadata={
                    "readout_timestamp": _now_iso(),
                    "fallback_reason": "primary_unavailable_or_empty",
                    "record_keys": sorted((record or {}).keys()),
                },
            )
        )
    return result


# ---------------------------------------------------------------------------
# Public adapter API
# ---------------------------------------------------------------------------


class JSpaceReadoutAdapter:
    """J-lens-inspired readout adapter over session/ledger data.

    Parameters
    ----------
    data_dir:
        Optional override for the OpenJarvis data directory.
        Defaults to :func:`openjarvis.core.paths.get_data_dir`.
    cache_dir:
        Optional override for the cache directory used for curated extracts.
        Defaults to :func:`openjarvis.core.paths.get_cache_dir`.
    limit:
        Default top-K bound applied to ``read``.
    warm:
        If ``True``, perform one placeholder warming step on init.
    """

    def __init__(
        self,
        *,
        data_dir: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        limit: int = 32,
        warm: bool = False,
    ) -> None:
        self._data_dir = data_dir or get_data_dir()
        self._cache_dir = cache_dir or get_cache_dir()
        self._limit = max(1, int(limit))
        self._primary_unavailable_reason: Optional[str] = None
        self._primary_unavailable_at_ts: Optional[str] = None
        self._last_records: List[JSpaceRecord] = []
        self._last_fallback_records: List[JSpaceRecord] = []
        if warm:
            self._mark_primary_unavailable("warm_unavailable")

    def _mark_primary_unavailable(self, reason: str) -> None:
        self._primary_unavailable_reason = str(reason)
        self._primary_unavailable_at_ts = _now_iso()

    def primary_is_available(self) -> bool:
        """Return True iff the primary ledger exists and is non-empty."""
        candidates = [
            self._data_dir / "cache" / "session-artifact-ledger.jsonl",
            self._data_dir / "session-artifact-ledger.jsonl",
            Path.cwd() / "cache" / "session-artifact-ledger.jsonl",
            Path.cwd() / "session-artifact-ledger.jsonl",
        ]
        return any(path.exists() and path.stat().st_size > 0 for path in candidates)

    def mark_primary_unavailable(self, reason: str) -> None:
        """Force the adapter to use the documented cosine fallback."""
        self._mark_primary_unavailable(str(reason))

    def restore_primary(self) -> None:
        """Restore normal primary path behavior."""
        self._primary_unavailable_reason = None
        self._primary_unavailable_at_ts = None

    def read(
        self,
        session_id: Optional[str],
        query_vector: Sequence[float],
        *,
        limit: Optional[int] = None,
        search_in_progress: bool = False,
        embeddings_only: bool = False,
    ) -> List[JSpaceRecord]:
        """Return highest-scoring J-space records for ``session_id``.

        Falls back from ledger JSONL to curated extracts JSONL, preserving
        caller flow by returning ``[]`` when no usable vectors exist.
        """
        limit_value = self._limit if limit is None else max(1, int(limit))
        if query_vector is None or not query_vector:
            return []
        records: List[JSpaceRecord] = []
        if self._primary_unavailable_reason or not self.primary_is_available():
            records = _fallback_cosine_over_extracts(
                session_id=session_id,
                query_vector=query_vector,
                limit=limit_value,
            )
            self._last_records = records
            self._last_fallback_records = records
            return records
        records = _readout_from_ledger(
            session_id=session_id,
            query_vector=query_vector,
            search_in_progress=search_in_progress,
        )
        if records:
            if embeddings_only:
                records = [rec for rec in records if rec.primary_vector]
            self._last_records = records
            self._last_fallback_records = []
            return records[:limit_value]
        if embeddings_only:
            self._last_records = records
            return records
        self._mark_primary_unavailable("empty_primary;fallback")
        records = _fallback_cosine_over_extracts(
            session_id=session_id,
            query_vector=query_vector,
            limit=limit_value,
        )
        self._last_records = records
        self._last_fallback_records = records
        return records

    def read_top(
        self,
        session_id: Optional[str],
        query_vector: Sequence[float],
        top_k: int = 5,
        *,
        search_in_progress: bool = False,
    ) -> List[Dict[str, Any]]:
        """Read and return lightweight dicts for downstream consumers."""
        return [
            rec.to_public_dict()
            for rec in self.read(
                session_id,
                query_vector,
                limit=top_k,
                search_in_progress=search_in_progress,
            )
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize adapter state for persistence."""
        return {
            "module": "openjarvis.routing.jspace_adapter",
            "primary_is_available": self.primary_is_available(),
            "primary_unavailable_reason": self._primary_unavailable_reason,
            "primary_unavailable_at_ts": self._primary_unavailable_at_ts,
            "last_record_count": len(self._last_records),
            "last_fallback_record_count": len(self._last_fallback_records),
            "data_dir": str(self._data_dir),
            "cache_dir": str(self._cache_dir),
            "limit": self._limit,
        }

    def _is_usable_vector(self, vector: Sequence[float]) -> bool:
        norm = math.sqrt(sum(x * x for x in vector)) if vector else 0.0
        return norm > 1e-9


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


def read_jspace(
    session_id: Optional[str],
    query_vector: Sequence[float],
    *,
    top_k: int = 8,
    search_in_progress: bool = False,
) -> List[Dict[str, Any]]:
    """Convenience wrapper around :class:`JSpaceReadoutAdapter`."""
    adapter = JSpaceReadoutAdapter(limit=top_k)
    return adapter.read_top(
        session_id=session_id,
        query_vector=query_vector,
        top_k=top_k,
        search_in_progress=search_in_progress,
    )


def jacobian_lens_readout(
    session_id: Optional[str],
    query_vector: Sequence[float],
    *,
    mark_unavailable: bool = True,
    unavail_reason: str = "jacobian_lens_not_deployed",
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """Jacobian-lens-flavored readout adapter.

    Prefers ledger records, then curated-extracts cosine fallback, then the
    query vector itself as the final record if no usable result exists.
    """
    adapter = JSpaceReadoutAdapter(limit=max(1, top_k))
    if mark_unavailable:
        adapter.mark_primary_unavailable(unavail_reason)
    records = adapter.read(
        session_id=session_id,
        query_vector=query_vector,
        limit=max(1, top_k),
    )
    public = [rec.to_public_dict() for rec in records]
    if not public and adapter._is_usable_vector(query_vector):
        public.append(
            JSpaceRecord(
                session_id=session_id or "",
                score=1.0,
                primary_vector=tuple(float(x) for x in query_vector),
                source="query_vector_fallback",
            ).to_public_dict()
        )
    return public
