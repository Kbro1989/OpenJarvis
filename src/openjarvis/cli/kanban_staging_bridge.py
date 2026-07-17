"""Bridge from antigravity kanban-staging-queue into OpenJarvis/Hermes."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import List

HERMES_KANBAN_STAGING_JSONL = os.environ.get(
    "OPENJARVIS_KANBAN_STAGING_JSONL",
    str(Path.home() / ".hermes" / "kanban-staging.jsonl"),
)
HERMES_KANBAN_OFFSET = os.environ.get(
    "OPENJARVIS_KANBAN_OFFSET",
    str(Path.home() / ".hermes" / "kanban-staging.offset"),
)
HERMES_KANBAN_INSERTED_JSONL = os.environ.get(
    "OPENJARVIS_KANBAN_INSERTED_JSONL",
    str(Path.home() / ".hermes" / "kanban-inserted.jsonl"),
)
HERMES_KANBAN_SYNCED_JSON = os.environ.get(
    "OPENJARVIS_KANBAN_SYNCED_JSON",
    str(Path.home() / ".hermes" / "kanban-synced.json"),
)


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _append_jsonl(path: str, record: dict) -> None:
    _ensure_parent(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl(path: str) -> List[dict]:
    records: List[dict] = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


class HermesKanbanStagingBridge:
    """Port of the antigravity kanban-staging-queue bridge for Hermes native queues."""

    def __init__(
        self,
        staging_jsonl: str = HERMES_KANBAN_STAGING_JSONL,
        offset_path: str = HERMES_KANBAN_OFFSET,
        inserted_jsonl: str = HERMES_KANBAN_INSERTED_JSONL,
        synced_json: str = HERMES_KANBAN_SYNCED_JSON,
    ) -> None:
        self.staging_jsonl = staging_jsonl
        self.offset_path = offset_path
        self.inserted_jsonl = inserted_jsonl
        self.synced_json = synced_json

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_synced(self) -> set[str]:
        if os.path.exists(self.synced_json):
            try:
                with open(self.synced_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data) if isinstance(data, list) else set()
            except (json.JSONDecodeError, OSError):
                return set()
        return set()

    def _save_synced(self, synced: set[str]) -> None:
        _ensure_parent(self.synced_json)
        with open(self.synced_json, "w", encoding="utf-8") as f:
            json.dump(sorted(synced), f)

    @staticmethod
    def _slugify_idempotency(value: str) -> str:
        return f"ag-task-{value[:8]}" if len(value) >= 8 else f"ag-task-{value}"

    def _read_offset(self) -> int:
        try:
            if os.path.exists(self.offset_path):
                with open(self.offset_path, "r", encoding="utf-8") as f:
                    offset = int(f.read().strip() or "0")
            else:
                offset = 0
        except (ValueError, OSError):
            offset = 0
        try:
            size = os.path.getsize(self.staging_jsonl)
        except OSError:
            size = 0
        if offset > size:
            offset = size
        return offset

    def _write_offset(self, offset: int) -> None:
        _ensure_parent(self.offset_path)
        with open(self.offset_path, "w", encoding="utf-8") as f:
            f.write(str(offset))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def stage_from_ag_task_md(
        self,
        task_md_path: str,
        dry_run: bool = False,
    ) -> List[dict]:
        """Parse unchecked tasks from a markdown file and stage them into Hermes.

        Returns the staged event dicts.
        """
        if not os.path.exists(task_md_path):
            return []

        try:
            with open(task_md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            return []

        synced = self._load_synced()
        new_tasks: list[tuple[str, str]] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("* [ ]"):
                task_text = stripped[5:].strip()
                task_hash = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
                if task_hash not in synced:
                    new_tasks.append((task_hash, task_text))

        staged: List[dict] = []
        for task_hash, task_text in new_tasks:
            event = {
                "type": "kanban_create",
                "task": task_text,
                "priority": "normal",
                "source": "openjarvis",
                "status": "pending",
                "retry_count": 0,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "idempotency_key": self._slugify_idempotency(task_hash),
            }
            staged.append(event)
            print(
                f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
                f"{'DRY RUN: ' if dry_run else ''}"
                f"Staged task: {task_text}"
            )
            if not dry_run:
                _append_jsonl(self.staging_jsonl, event)

        if staged and not dry_run:
            for task_hash, _ in new_tasks[: len(staged)]:
                synced.add(task_hash)
            self._save_synced(synced)

        return staged

    def drain_to_kanban(
        self,
        limit: int = 50,
        dry_run: bool = False,
    ) -> List[str]:
        """Consume staged events from the Hermes staging queue and "insert" them.

        Returns the list of inserted task identifiers.
        """
        if not os.path.exists(self.staging_jsonl):
            return []

        offset = self._read_offset()
        inserted_ids: List[str] = []
        seen_events = _read_jsonl(self.inserted_jsonl)
        seen_keys = {event.get("idempotency_key") for event in seen_events}

        try:
            with open(self.staging_jsonl, "r", encoding="utf-8") as f:
                f.seek(offset)
                processed = 0
                while processed < limit:
                    line_offset = f.tell()
                    line = f.readline()
                    if not line:
                        break

                    line = line.strip()
                    if not line:
                        if not dry_run:
                            self._write_offset(f.tell())
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        print("Skipping malformed JSON line.")
                        if not dry_run:
                            self._write_offset(f.tell())
                        continue

                    if event.get("type") == "kanban_create":
                        task_title = event.get("task", "Untitled Task")
                        idempotency = event.get("idempotency_key", "")
                        if idempotency in seen_keys:
                            print(
                                f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
                                f"Idempotent skip: {task_title}"
                            )
                        else:
                            task_id = f"ag-task-{hashlib.sha256((idempotency + task_title).encode('utf-8')).hexdigest()[:12]}"
                            print(
                                f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
                                f"{'DRY RUN: ' if dry_run else ''}"
                                f"Enqueue: {task_title}"
                            )
                            if not dry_run:
                                insert_record = {
                                    "task_id": task_id,
                                    "task": task_title,
                                    "idempotency_key": idempotency,
                                    "timestamp": time.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                                    ),
                                }
                                _append_jsonl(self.inserted_jsonl, insert_record)
                                seen_keys.add(idempotency)
                                inserted_ids.append(task_id)
                            else:
                                inserted_ids.append(task_id)

                    if not dry_run:
                        self._write_offset(f.tell())
                    processed += 1
        except OSError as exc:
            print(f"Error reading staging: {exc}")

        return inserted_ids

    def sync_status(self) -> dict:
        """Return a dict with counts of staged/synced/inserted items."""
        staged_count = 0
        if os.path.exists(self.staging_jsonl):
            try:
                with open(self.staging_jsonl, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            staged_count += 1
            except OSError:
                pass

        inserted_count = 0
        if os.path.exists(self.inserted_jsonl):
            try:
                with open(self.inserted_jsonl, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            inserted_count += 1
            except OSError:
                pass

        synced_count = len(self._load_synced())
        return {
            "staged": staged_count,
            "inserted": inserted_count,
            "synced_task_hashes": synced_count,
        }


__all__ = [
    "HERMES_KANBAN_STAGING_JSONL",
    "HERMES_KANBAN_OFFSET",
    "HERMES_KANBAN_INSERTED_JSONL",
    "HERMES_KANBAN_SYNCED_JSON",
    "HermesKanbanStagingBridge",
]
