#!/usr/bin/env python3
"""Persistent blueprint/job store for Jarvis automation blueprints."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS blueprints (
    key TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    schedule TEXT,
    tools TEXT,
    agent TEXT,
    output_artifact TEXT,
    status TEXT DEFAULT 'active',
    last_run TEXT,
    next_run TEXT,
    metadata TEXT
);
CREATE TABLE IF NOT EXISTS artifact_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blueprint_key TEXT,
    created_at TEXT,
    status TEXT,
    path TEXT,
    size INTEGER,
    summary TEXT
);
"""


@dataclass(slots=True)
class BlueprintRecord:
    key: str
    title: str = ""
    description: str = ""
    schedule: str = ""
    tools: str = ""
    agent: str = "simple"
    output_artifact: str = "brief"
    status: str = "active"
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BlueprintStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with sqlite3.connect(self.db_path) as con:
            con.executescript(SCHEMA)
            con.commit()

    def close(self) -> None:
        return None

    def save_blueprint(self, record: BlueprintRecord) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute(
                "INSERT OR REPLACE INTO blueprints(key,title,description,schedule,tools,agent,output_artifact,status,last_run,next_run,metadata) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.key,
                    record.title,
                    record.description,
                    record.schedule,
                    record.tools,
                    record.agent,
                    record.output_artifact,
                    record.status,
                    record.last_run,
                    record.next_run,
                    json.dumps(record.metadata, ensure_ascii=False),
                ),
            )
            con.commit()

    def get_blueprint(self, key: str) -> Optional[BlueprintRecord]:
        with self._lock, sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT * FROM blueprints WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_blueprints(self, status: Optional[str] = None) -> List[BlueprintRecord]:
        with self._lock, sqlite3.connect(self.db_path) as con:
            if status:
                rows = con.execute("SELECT * FROM blueprints WHERE status=?", (status,)).fetchall()
            else:
                rows = con.execute("SELECT * FROM blueprints").fetchall()
        return [self._row_to_record(r) for r in rows]

    def remove_blueprint(self, key: str) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute("DELETE FROM blueprints WHERE key=?", (key,))
            con.commit()

    def update_last_run(self, key: str, timestamp: str) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE blueprints SET last_run=? WHERE key=?", (timestamp, key))
            con.commit()

    def update_status(self, key: str, status: str) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE blueprints SET status=? WHERE key=?", (status, key))
            con.commit()

    def delete_blueprint(self, key: str) -> None:
        self.remove_blueprint(key)

    def log_artifact(self, blueprint_key: str, status: str, path: str, summary: str) -> None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute(
                "INSERT INTO artifact_logs(blueprint_key,created_at,status,path,summary) VALUES(?,?,?,?,?)",
                (blueprint_key, __import__("datetime").datetime.now(timezone.utc).isoformat(), status, path, summary),
            )
            con.commit()

    def _row_to_record(self, row: Any) -> BlueprintRecord:
        return BlueprintRecord(
            key=row[0],
            title=row[1],
            description=row[2],
            schedule=row[3],
            tools=row[4],
            agent=row[5],
            output_artifact=row[6],
            status=row[7],
            last_run=row[8],
            next_run=row[9],
            metadata=json.loads(row[10] or "{}"),
        )


__all__ = ["BlueprintRecord", "BlueprintStore"]
