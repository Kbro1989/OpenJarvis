"""Voice reward sidecar — sensor path for King Wen voice outcomes.

Subscribes to KINGWEN_VOICE_COMPLETE events, normalizes voice quality
into a scalar score, persists to kingwen_voice_rewards table in TraceStore.
Does NOT touch Episode, MultiObjectiveReward, or model routing.

Upgrade: accepts optional 512-state crowd vote payload from King Wen
consensus, derives vector scores while preserving backward-compatible
scalar scoring.
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

KINGWEN_VOICE_REWARDS_TABLE = "kingwen_voice_rewards"
CROWD_STATE_DIM = 512

# Normalization weights (must sum to 1.0 for scalar score)
DEFAULT_WEIGHTS: dict[str, float] = {
    "compliance": 0.40,
    "porosity": 0.15,
    "vector_truth": 0.25,
    "dsp_fidelity": 0.20,
}

# Optional scalar fallback weights used only when crowd votes yield no axes.
DEFAULT_VECTOR_WEIGHTS: dict[str, float] = {
    "compliance": 0.20,
    "porosity_match": 0.15,
    "vector_truth": 0.20,
    "dsp_fidelity": 0.20,
    "crowd_entropy": 0.25,
}

# ─── Lazy imports ──────────────────────────────────────────────────────────────


def _get_event_bus():
    from openjarvis.core.events import EventBus, EventType, get_event_bus

    return get_event_bus(), EventType


def _get_trace_store():
    from openjarvis.traces.store import TraceStore

    return TraceStore("~/.openjarvis/traces.db")


# ─── Score normalization ─────────────────────────────────────────────────────


def _normalize_compliance(compliance: str) -> float:
    return 1.0 if compliance == "compliant" else 0.0


def _normalize_porosity(porosity: float | None) -> float:
    """Optimal porosity is ~0.35. Distance from optimal is penalized."""
    if porosity is None:
        return 0.5  # neutral if unknown
    optimal = 0.35
    distance = abs(porosity - optimal)
    return max(0.0, 1.0 - (distance / max(optimal, 1.0 - optimal)))


def _normalize_vector_truth(vector: dict[str, float]) -> float:
    """Vector mean proximity to 0.5."""
    if not vector:
        return 0.5
    values = [
        vector.get("voiceWeight", 0.0),
        vector.get("coherence", 0.0),
        vector.get("chaos", 0.0),
        vector.get("whimsy", 0.0),
        vector.get("darkTone", 0.0),
    ]
    mean = sum(values) / len(values)
    return max(0.0, 1.0 - abs(mean - 0.5) * 2.0)


def _normalize_dsp_fidelity(dsp_meta: dict[str, Any]) -> float:
    """DSP applied without exception = 1.0, exception = 0.0."""
    if not dsp_meta:
        return 0.5  # neutral if unknown
    return 0.0 if dsp_meta.get("error") or dsp_meta.get("exception") else 1.0


def compute_voice_score(
    compliance: str,
    porosity: float | None,
    vector: dict[str, float],
    dsp_meta: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> float:
    """Normalize voice event into scalar reward score."""
    w = weights or DEFAULT_WEIGHTS
    score = (
        w["compliance"] * _normalize_compliance(compliance)
        + w["porosity"] * _normalize_porosity(porosity)
        + w["vector_truth"] * _normalize_vector_truth(vector)
        + w["dsp_fidelity"] * _normalize_dsp_fidelity(dsp_meta)
    )
    return round(score, 6)


# ─── 512-state crowd consensus scoring ──────────────────────────────────────


def _parse_512_crowd_payload(data: dict[str, Any]) -> list[float] | None:
    """Extract a length-512 crowd vote vector from event data.

    Accepted payload shapes:
      * ``crowd_votes``: list[float], tuple[float], list[int]
      * ``kingwen_states`` / ``consensus_vector`` / ``states_512``:
        list[float] or JSON string representation
    Falls back to None if unavailable or wrong length after normalization.
    """
    raw = (
        data.get("crowd_votes")
        or data.get("kingwen_states")
        or data.get("consensus_vector")
        or data.get("states_512")
    )
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if isinstance(raw, dict):
        # Map ordered keys/ids into a fixed-length array if value count matches 512
        values = [float(v) for v in raw.values() if str(v).replace(".", "", 1).replace("-", "").isdigit()]
        if len(values) == CROWD_STATE_DIM:
            return values
        return None
    if not isinstance(raw, (list, tuple)):
        return None
    try:
        votes = [float(v) for v in raw]
    except Exception:
        return None
    if len(votes) == CROWD_STATE_DIM:
        return votes
    if len(votes) > 0:
        # Linear interpolation resample to 512 if within reasonable range
        bucket = max(1, len(votes))
        target = CROWD_STATE_DIM
        if target % bucket == 0:
            factor = target // bucket
            return [votes[i // factor] for i in range(target)]
    return None


def _crowd_entropy(votes: list[float]) -> float:
    """Normalized Shannon entropy over the crowd vote distribution."""
    if not votes:
        return 0.0
    total = sum(votes)
    if total <= 0.0:
        return 0.0
    ent = 0.0
    inv = 1.0 / total
    for v in votes:
        p = v * inv
        if p > 0.0:
            ent -= p * math.log(p)
    max_ent = math.log(CROWD_STATE_DIM)
    return round(ent / max_ent, 6) if max_ent > 0.0 else 0.0


def _crowd_mean(votes: list[float]) -> float:
    if not votes:
        return 0.5
    return sum(votes) / len(votes)


def _crowd_std(votes: list[float]) -> float:
    if not votes:
        return 0.0
    mean = _crowd_mean(votes)
    return math.sqrt(sum((v - mean) ** 2 for v in votes) / len(votes))


def _score_vector_compliance(compliance: str | None, votes: list[float]) -> float:
    """Align event compliance label with crowd consensus."""
    if not votes:
        return 0.5
    support = _crowd_mean(votes)
    expected_high = (compliance or "").lower() == "compliant"
    # For compliant events, high crowd support is good.
    # For reject events, low crowd support is good.
    return round(support if expected_high else max(0.0, 1.0 - support), 6)


def _score_vector_porosity_match(porosity: float | None, votes: list[float]) -> float:
    """Proximity of event porosity to crowd vote mean, penalized by disagreement."""
    if porosity is None or not votes:
        return 0.5
    mean = _crowd_mean(votes)
    std = _crowd_std(votes)
    if std < 1e-6:
        # Crowd consensus collapses to one vote; score by distance to mean clamp.
        return round(max(0.0, 1.0 - abs(porosity - mean) * 2.0), 6)
    z = abs(porosity - mean) / max(std, 0.01)
    return round(max(0.0, 1.0 - min(z, 1.0)), 6)


def _score_vector_truth(voice_vector: dict[str, float], votes: list[float]) -> float:
    """Overlap between event voice vector and dominant crowd direction.

    Derive a crowd semantic axis from high-variance vote positions.
    If insufficient information, return neutral.
    """
    if not votes or not voice_vector:
        return 0.5
    # Map crowd peak alignment to voice-axis similarity.
    # Treat sorted top-K crowd positions as semantically aligned with coherence.
    top_k = 8
    try:
        top_indices = sorted(range(len(votes)), key=lambda i: votes[i], reverse=True)[:top_k]
        crowd_alignment = len(top_indices) / CROWD_STATE_DIM
    except Exception:
        return 0.5
    event_alignment = _normalize_vector_truth(voice_vector)
    return round(max(0.0, 1.0 - abs(event_alignment - crowd_alignment) * 2.0), 6)


def _score_vector_dsp_fidelity(dsp_meta: dict[str, Any]) -> float:
    """Reuse scalar DSP fidelity as the vector component."""
    return _normalize_dsp_fidelity(dsp_meta)


def compute_crowd_vector_scores(
    data: dict[str, Any],
) -> dict[str, float] | None:
    """Compute vector scores from optional 512-state crowd vote payload.

    Returns ``None`` if no crowd data is present; otherwise returns a dict:
    {
        "compliance": float,
        "porosity_match": float,
        "vector_truth": float,
        "dsp_fidelity": float,
        "crowd_entropy": float,
    }
    """
    votes = _parse_512_crowd_payload(data)
    if votes is None:
        return None
    return {
        "compliance": _score_vector_compliance(data.get("compliance"), votes),
        "porosity_match": _score_vector_porosity_match(data.get("porosity"), votes),
        "vector_truth": _score_vector_truth(data.get("voice_vector", {}), votes),
        "dsp_fidelity": _score_vector_dsp_fidelity(data.get("dsp_meta", {})),
        "crowd_entropy": _crowd_entropy(votes),
    }


# ─── Persistence ───────────────────────────────────────────────────────────────


_VECTOR_COLUMNS = {
    "score_compliance": "REAL",
    "score_porosity_match": "REAL",
    "score_vector_truth": "REAL",
    "score_dsp_fidelity": "REAL",
    "score_crowd_entropy": "REAL",
    "crowd_votes_json": "TEXT",
    "score_type": "TEXT DEFAULT 'scalar'",
}


def _ensure_table(trace_store) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS {KINGWEN_VOICE_REWARDS_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        hexagram_id INTEGER,
        phase_temporal TEXT,
        voice_vector TEXT,
        porosity REAL,
        backend TEXT,
        compliance TEXT,
        violations TEXT,
        dsp_meta TEXT,
        score REAL,
        weights TEXT,
        timestamp REAL,
        score_compliance REAL,
        score_porosity_match REAL,
        score_vector_truth REAL,
        score_dsp_fidelity REAL,
        score_crowd_entropy REAL,
        crowd_votes_json TEXT,
        score_type TEXT DEFAULT 'scalar',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    trace_store.execute(sql)
    _ensure_columns(trace_store)


def _ensure_columns(trace_store) -> None:
    logger = LOGGER.getChild("schema")
    try:
        cursor = trace_store.execute(
            f"PRAGMA table_info({KINGWEN_VOICE_REWARDS_TABLE})"
        )
        columns = {row[1] for row in cursor.fetchall()}
    except Exception:
        return
    for name, col_type in _VECTOR_COLUMNS.items():
        if name not in columns:
            try:
                trace_store.execute(
                    f"ALTER TABLE {KINGWEN_VOICE_REWARDS_TABLE} ADD COLUMN {name} {col_type}"
                )
                logger.debug("Migrated %s.%s", KINGWEN_VOICE_REWARDS_TABLE, name)
            except Exception as exc:
                logger.debug("Column %s skipped: %s", name, exc)


def persist_voice_reward(
    event_data: dict[str, Any],
    score: float,
    vector_scores: dict[str, float] | None = None,
) -> None:
    """Write voice reward to TraceStore."""
    trace_store = _get_trace_store()
    _ensure_table(trace_store)

    votes_payload = _parse_512_crowd_payload(event_data)
    score_type = "vector" if vector_scores else "scalar"
    weights = vector_scores or DEFAULT_WEIGHTS

    sql = f"""
    INSERT INTO {KINGWEN_VOICE_REWARDS_TABLE}
    (session_id, hexagram_id, phase_temporal, voice_vector, porosity,
     backend, compliance, violations, dsp_meta, score, weights, timestamp,
     score_compliance, score_porosity_match, score_vector_truth,
     score_dsp_fidelity, score_crowd_entropy, crowd_votes_json, score_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    LOGGER.debug("persist sql=%s score=%s type=%s", sql.strip(), score, score_type)
    try:
        trace_store.execute(
            sql,
            (
                event_data.get("session_id", ""),
                event_data.get("hexagram_id"),
                event_data.get("phase_temporal"),
                json.dumps(event_data.get("voice_vector", {})),
                event_data.get("porosity"),
                event_data.get("backend"),
                event_data.get("compliance"),
                ",".join(event_data.get("violations", []) or []),
                json.dumps(event_data.get("dsp_meta", {})),
                score,
                json.dumps(weights),
                event_data.get("timestamp", time.time()),
                vector_scores.get("compliance") if vector_scores else None,
                vector_scores.get("porosity_match") if vector_scores else None,
                vector_scores.get("vector_truth") if vector_scores else None,
                vector_scores.get("dsp_fidelity") if vector_scores else None,
                vector_scores.get("crowd_entropy") if vector_scores else None,
                json.dumps(votes_payload) if votes_payload is not None else None,
                score_type,
            ),
        )
    except Exception as exc:
        LOGGER.exception("persist failed: %s", exc)
        raise


# ─── Public API ──────────────────────────────────────────────────────────────
def get_voice_reward_summary(session_id: str) -> dict[str, Any]:
    """Return aggregated voice reward summary for a session."""
    trace_store = _get_trace_store()
    _ensure_table(trace_store)
    sql = f"""
    SELECT
        COUNT(*) as count,
        AVG(score) as avg_score,
        MIN(score) as min_score,
        MAX(score) as max_score,
        SUM(CASE WHEN compliance = 'compliant' THEN 1 ELSE 0 END) as compliant_count,
        SUM(CASE WHEN compliance = 'reject' THEN 1 ELSE 0 END) as reject_count
    FROM {KINGWEN_VOICE_REWARDS_TABLE}
    WHERE session_id = ?
    """
    row = trace_store.fetchone(sql, (session_id,))
    if not row or row[0] == 0:
        return {"session_id": session_id, "count": 0}

    return {
        "session_id": session_id,
        "count": row[0],
        "avg_score": round(row[1], 6) if row[1] is not None else None,
        "min_score": row[2],
        "max_score": row[3],
        "compliant_count": row[4],
        "reject_count": row[5],
    }


# ─── EventBus subscriber ─────────────────────────────────────────────────────


def _on_kingwen_voice_complete(event: Any) -> None:
    data = event.data if hasattr(event, "data") else event
    if not isinstance(data, dict):
        return
    score = compute_voice_score(
        compliance=data.get("compliance", "compliant"),
        porosity=data.get("porosity"),
        vector=data.get("voice_vector", {}),
        dsp_meta=data.get("dsp_meta", {}),
    )
    vector_scores = compute_crowd_vector_scores(data)
    persist_voice_reward(data, score, vector_scores=vector_scores)
    stype = "vector" if vector_scores else "scalar"
    LOGGER.debug(
        "Voice reward persisted: score=%s session=%s type=%s",
        score,
        data.get("session_id"),
        stype,
    )


def start_voice_reward_sidecar() -> None:
    """Subscribe to KINGWEN_VOICE_COMPLETE events. Idempotent."""
    bus, EventType = _get_event_bus()
    bus.subscribe(EventType.KINGWEN_VOICE_COMPLETE, _on_kingwen_voice_complete)
    LOGGER.info("Voice reward sidecar started")


def stop_voice_reward_sidecar() -> None:
    """Unsubscribe from events if supported."""
    bus, EventType = _get_event_bus()
    try:
        bus.unsubscribe(EventType.KINGWEN_VOICE_COMPLETE, _on_kingwen_voice_complete)
    except Exception:
        pass
