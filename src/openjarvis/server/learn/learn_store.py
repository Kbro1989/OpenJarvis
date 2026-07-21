"""Learn Store — SQLite persistence for LearnEvent capture stream.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .learn_event import LearnEvent, derive_tags

logger = logging.getLogger(__name__)
DEFAULT_DB = Path.home() / ".openjarvis" / "learn.db"


class LearnStore:
    """SQLite-backed store for learning events."""

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS learn_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    handler TEXT NOT NULL,
                    user_input TEXT,
                    query TEXT,
                    response_summary TEXT,
                    response_full TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    save_string_before TEXT,
                    save_string_after TEXT,
                    hexagram_id INTEGER,
                    domain TEXT,
                    valence REAL,
                    arousal REAL,
                    coherence REAL,
                    tool_used TEXT,
                    agent_used TEXT,
                    artifact_path TEXT,
                    duration_ms INTEGER,
                    token_count INTEGER,
                    tags TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_handler ON learn_events(handler)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_session ON learn_events(session_id)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON learn_events(timestamp)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_hexagram ON learn_events(hexagram_id)")
            con.commit()

    def save(self, event: LearnEvent) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute("""
                INSERT INTO learn_events (
                    event_id, timestamp, session_id, handler, user_input, query,
                    response_summary, response_full, status, error_message,
                    save_string_before, save_string_after, hexagram_id, domain,
                    valence, arousal, coherence, tool_used, agent_used,
                    artifact_path, duration_ms, token_count, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.timestamp, event.session_id,
                event.handler, event.user_input, event.query,
                event.response_summary, event.response_full, event.status,
                event.error_message, event.save_string_before,
                event.save_string_after, event.hexagram_id, event.domain,
                event.valence, event.arousal, event.coherence,
                event.tool_used, event.agent_used, event.artifact_path,
                event.duration_ms, event.token_count,
                json.dumps(event.tags),
            ))
            con.commit()
        logger.debug("LearnEvent saved: %s (%s)", event.event_id, event.handler)

    def get_by_handler(self, handler: str, limit: int = 100) -> List[LearnEvent]:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM learn_events WHERE handler = ? ORDER BY timestamp DESC LIMIT ?",
                (handler, limit),
            ).fetchall()
        return [self._row_to_event(dict(r)) for r in rows]

    def get_by_session(self, session_id: str, limit: int = 1000) -> List[LearnEvent]:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM learn_events WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [self._row_to_event(dict(r)) for r in rows]

    def get_by_hexagram(self, hexagram_id: int, limit: int = 100) -> List[LearnEvent]:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM learn_events WHERE hexagram_id = ? ORDER BY timestamp DESC LIMIT ?",
                (hexagram_id, limit),
            ).fetchall()
        return [self._row_to_event(dict(r)) for r in rows]

    def search(self, query: str, limit: int = 50) -> List[LearnEvent]:
        pattern = f"%{query}%"
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("""
                SELECT * FROM learn_events
                WHERE user_input LIKE ? OR query LIKE ? OR response_summary LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (pattern, pattern, pattern, limit)).fetchall()
        return [self._row_to_event(dict(r)) for r in rows]

    def get_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock, sqlite3.connect(self.db_path) as con:
            where = "WHERE session_id = ?" if session_id else ""
            params = (session_id,) if session_id else ()
            total = con.execute(f"SELECT COUNT(*) FROM learn_events {where}", params).fetchone()[0]
            by_handler = con.execute(f"SELECT handler, COUNT(*) FROM learn_events {where} GROUP BY handler", params).fetchall()
            by_status = con.execute(f"SELECT status, COUNT(*) FROM learn_events {where} GROUP BY status", params).fetchall()
        return {
            "total_events": total,
            "by_handler": {h: c for h, c in by_handler},
            "by_status": {s: c for s, c in by_status},
        }

    def _row_to_event(self, row: Dict[str, Any]) -> LearnEvent:
        tags = json.loads(row.get("tags", "[]"))
        return LearnEvent(
            event_id=row["event_id"], timestamp=row["timestamp"],
            session_id=row["session_id"], handler=row["handler"],
            user_input=row.get("user_input", ""), query=row.get("query", ""),
            response_summary=row.get("response_summary", ""),
            response_full=row.get("response_full"),
            status=row["status"], error_message=row.get("error_message"),
            save_string_before=row.get("save_string_before"),
            save_string_after=row.get("save_string_after"),
            hexagram_id=row.get("hexagram_id"), domain=row.get("domain"),
            valence=row.get("valence"), arousal=row.get("arousal"),
            coherence=row.get("coherence"),
            tool_used=row.get("tool_used"), agent_used=row.get("agent_used"),
            artifact_path=row.get("artifact_path"),
            duration_ms=row.get("duration_ms"), token_count=row.get("token_count"),
            tags=tags,
        )