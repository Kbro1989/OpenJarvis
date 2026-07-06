"""Voice reward sidecar — sensor path for King Wen voice outcomes.

Subscribes to KINGWEN_VOICE_COMPLETE events, normalizes voice quality
into a scalar score, persists to kingwen_voice_rewards table in TraceStore.
Does NOT touch Episode, MultiObjectiveReward, or model routing.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

KINGWEN_VOICE_REWARDS_TABLE = "kingwen_voice_rewards"

# Normalization weights (must sum to 1.0 for scalar score)
DEFAULT_WEIGHTS: dict[str, float] = {
    "compliance": 0.40,
    "porosity": 0.15,
    "vector_truth": 0.25,
    "dsp_fidelity": 0.20,
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


# ─── Persistence ───────────────────────────────────────────────────────────────


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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    trace_store.execute(sql)


def persist_voice_reward(event_data: dict[str, Any], score: float) -> None:
    """Write voice reward to TraceStore."""
    trace_store = _get_trace_store()
    _ensure_table(trace_store)

    sql = f"""
    INSERT INTO {KINGWEN_VOICE_REWARDS_TABLE}
    (session_id, hexagram_id, phase_temporal, voice_vector, porosity,
     backend, compliance, violations, dsp_meta, score, weights, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
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
            json.dumps(DEFAULT_WEIGHTS),
            event_data.get("timestamp", time.time()),
        ),
    )


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
    score = compute_voice_score(
        compliance=data.get("compliance", "compliant"),
        porosity=data.get("porosity"),
        vector=data.get("voice_vector", {}),
        dsp_meta=data.get("dsp_meta", {}),
    )
    persist_voice_reward(data, score)
    LOGGER.debug("Voice reward persisted: score=%s session=%s", score, data.get("session_id"))


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
