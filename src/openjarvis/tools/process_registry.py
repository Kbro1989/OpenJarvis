"""Process Registry -- Lightweight client for checking background processes.

Reads from the Hermes checkpoint file to display active background tasks
without requiring direct Hermes imports.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def format_uptime_short(seconds: int) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    mins, secs = divmod(s, 60)
    if mins < 60:
        return f"{mins}m {secs}s"
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins}m"

class ProcessRegistry:
    """Read-only process registry client that reads Hermes processes.json checkpoint."""

    def __init__(self) -> None:
        self.checkpoint_path = Path.home() / "AppData" / "Local" / "hermes" / "processes.json"

    def list_sessions(self, task_id: str | None = None, session_key: str | None = None) -> List[Dict[str, Any]]:
        """List running background processes from the checkpoint file."""
        if not self.checkpoint_path.exists():
            return []
        try:
            content = self.checkpoint_path.read_text(encoding="utf-8")
            entries = json.loads(content)
        except Exception as exc:
            logger.debug("Failed to read processes.json checkpoint: %s", exc)
            return []

        result = []
        for entry in entries:
            session_id = entry.get("session_id", "")
            command = entry.get("command", "")
            pid = entry.get("pid")
            started_at = entry.get("started_at", time.time())
            cwd = entry.get("cwd")
            
            # Filter if task_id/session_key specifies a match
            if task_id and entry.get("task_id") != task_id:
                continue
            if session_key and entry.get("session_key") != session_key:
                continue

            uptime = int(time.time() - started_at)
            started_formatted = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started_at))

            result.append({
                "session_id": session_id,
                "command": command[:200],
                "cwd": cwd,
                "pid": pid,
                "started_at": started_formatted,
                "uptime_seconds": uptime,
                "status": "running",
                "output_preview": "",
            })
        return result

    def register_process(self, session_id: str, command: str, pid: int, cwd: str) -> None:
        """Register a background process in the checkpoint file."""
        entries = []
        if self.checkpoint_path.exists():
            try:
                content = self.checkpoint_path.read_text(encoding="utf-8")
                entries = json.loads(content)
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                pass
        
        # Remove any existing entry with the same session_id
        entries = [e for e in entries if isinstance(e, dict) and e.get("session_id") != session_id]
        
        entries.append({
            "session_id": session_id,
            "command": command,
            "pid": pid,
            "started_at": time.time(),
            "cwd": cwd,
        })
        
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to write to processes.json: %s", exc)

    def deregister_process(self, session_id: str) -> None:
        """Deregister a background process from the checkpoint file."""
        if not self.checkpoint_path.exists():
            return
        try:
            content = self.checkpoint_path.read_text(encoding="utf-8")
            entries = json.loads(content)
        except Exception:
            return
        
        if not isinstance(entries, list):
            return
            
        new_entries = [e for e in entries if isinstance(e, dict) and e.get("session_id") != session_id]
        if len(new_entries) == len(entries):
            return
            
        try:
            self.checkpoint_path.write_text(json.dumps(new_entries, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to update processes.json: %s", exc)

process_registry = ProcessRegistry()
