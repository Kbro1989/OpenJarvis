"""Append-only persistence for King Wen swarm consensus telemetry.

Schema is intentionally minimal and append-only. No oracle-generated state;
everything is lifted from ``Event.data`` when present. This store is not a
lookup table, not a semantic map, and not a synthetic oracle.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


DEFAULT_DB_NAME = "kingwen_swarm.db"
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS kingwen_consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    agent TEXT,
    hexagram_id TEXT,
    hexagram_name TEXT,
    phase_temporal TEXT,
    porosity REAL,
    voice_weight REAL,
    coherence REAL,
    chaos REAL,
    whimsy REAL,
    dark_tone REAL,
    trajectory TEXT,
    broadcast_mode TEXT,
    autonomy REAL,
    memory_sync_interval REAL,
    swarm_enabled INTEGER,
    payload JSON
);
"""
_INSERT_ROW = """
INSERT INTO kingwen_consensus (
    ts, agent, hexagram_id, hexagram_name, phase_temporal,
    porosity, voice_weight, coherence, chaos, whimsy, dark_tone,
    trajectory, broadcast_mode, autonomy, memory_sync_interval, swarm_enabled,
    payload
) VALUES (
    :ts, :agent, :hexagram_id, :hexagram_name, :phase_temporal,
    :porosity, :voice_weight, :coherence, :chaos, :whimsy, :dark_tone,
    :trajectory, :broadcast_mode, :autonomy, :memory_sync_interval, :swarm_enabled,
    :payload
)
"""


@dataclass(slots=True)
class SwarmRecord:
    ts: float
    agent: Optional[str] = None
    hexagram_id: Optional[str] = None
    hexagram_name: Optional[str] = None
    phase_temporal: Optional[str] = None
    porosity: Optional[float] = None
    voice_weight: Optional[float] = None
    coherence: Optional[float] = None
    chaos: Optional[float] = None
    whimsy: Optional[float] = None
    dark_tone: Optional[float] = None
    trajectory: Optional[str] = None
    broadcast_mode: Optional[str] = None
    autonomy: Optional[float] = None
    memory_sync_interval: Optional[float] = None
    swarm_enabled: Optional[bool] = None
    payload: dict[str, Any] = field(default_factory=dict)


class KingwenSwarmStore:
    """Lightweight append-only swarm telemetry store backed by SQLite."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        base_dir = Path(
            os.environ.get("OPENJARVIS_STATE_DIR", "~/.openjarvis")
        ).expanduser()
        base_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(db_path) if db_path else base_dir / DEFAULT_DB_NAME
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def append_event(self, event) -> int:
        """Persist one kingwen consensus event and return the inserted row id."""
        data = getattr(event, "data", {}) or {}
        row = SwarmRecord(
            ts=float(getattr(event, "timestamp", time.time()) or time.time()),
            agent=self._first(data, "agent"),
            hexagram_id=self._first(
                data,
                "hexagram_id",
                "hexagram",
            ),
            hexagram_name=self._first(
                data,
                "hexagram_name",
            ),
            phase_temporal=self._first(
                data,
                "phase_temporal",
                "phase",
                "temporal",
            ),
            porosity=self._scalar(data, "porosity"),
            voice_weight=self._scalar(data, "voiceWeight", "voice_weight"),
            coherence=self._scalar(data, "coherence"),
            chaos=self._scalar(data, "chaos"),
            whimsy=self._scalar(data, "whimsy"),
            dark_tone=self._scalar(data, "darkTone", "dark_tone"),
            trajectory=self._first(data, "trajectory"),
            broadcast_mode=self._first(
                data,
                "kingwen_broadcast_mode",
                "broadcast_mode",
            ),
            autonomy=self._scalar(data, "agent_autonomy"),
            memory_sync_interval=self._scalar(data, "memory_sync_interval"),
            swarm_enabled=self._flag(data, "swarm_broadcast_enabled"),
            payload=dict(data),
        )
        cursor = self._conn.execute(_INSERT_ROW, self._to_row(row))
        self._conn.commit()
        return cursor.lastrowid

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _to_row(self, row: SwarmRecord) -> dict[str, Any]:
        return {
            "ts": row.ts,
            "agent": row.agent,
            "hexagram_id": row.hexagram_id,
            "hexagram_name": row.hexagram_name,
            "phase_temporal": row.phase_temporal,
            "porosity": row.porosity,
            "voice_weight": row.voice_weight,
            "coherence": row.coherence,
            "chaos": row.chaos,
            "whimsy": row.whimsy,
            "dark_tone": row.dark_tone,
            "trajectory": row.trajectory,
            "broadcast_mode": row.broadcast_mode,
            "autonomy": row.autonomy,
            "memory_sync_interval": row.memory_sync_interval,
            "swarm_enabled": 1 if row.swarm_enabled else 0,
            "payload": json.dumps(row.payload, ensure_ascii=False),
        }

    @staticmethod
    def _first(data: dict[str, Any], *keys: str) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            text = str(value)
            if not text:
                continue
            return text
        return None

    @staticmethod
    def _scalar(data: dict[str, Any], *keys: str) -> Optional[float]:
        value = KingwenSwarmStore._first(data, *keys)
        if value is None:
            return None
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _flag(data: dict[str, Any], key: str) -> Optional[bool]:
        value = data.get(key)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if not text:
            return None
        return text not in {"0", "false", "no", "off"}
