"""Portable offset-tailing/kanban ingest tool ported from antigravity.

Original sources:
- C:\\Users\\krist\\.gemini\\antigravity\\kanban-staging-queue\\watcher.py
- C:\\Users\\krist\\.gemini\\antigravity\\kanban-staging-queue\\ticker.py
- C:\\Users\\krist\\.gemini\\antigravity\\kanban-staging-queue\\skill_sync.py

Ported pattern:
- Tail-read a markdown task file or JSONL queue by byte offset
- Hash task text for idempotency
- Skip malformed lines without crashing
- Persist offset/synced state locally

Constraints:
- No hard dependency on antigravity runtime paths
- No external cloud-specific calls
- No mock/stub/placeholder
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterable, Tuple


DEFAULT_STAGING_JSONL = os.environ.get(
    "OPENJARVIS_KANBAN_STAGING_JSONL",
    str(Path.home() / ".openjarvis" / "kanban-staging.jsonl"),
)
DEFAULT_OFFSET_PATH = os.environ.get(
    "OPENJARVIS_KANBAN_OFFSET",
    str(Path.home() / ".openjarvis" / "kanban-staging.offset"),
)
DEFAULT_TASK_MD = os.environ.get(
    "OPENJARVIS_KANBAN_TASK_MD",
    str(Path.home() / ".openjarvis" / "kanban-task.md"),
)
DEFAULT_SYNCED_PATH = os.environ.get(
    "OPENJARVIS_KANBAN_SYNCED",
    str(Path.home() / ".openjarvis" / "kanban-synced.json"),
)


def slugify_idempotency(value: str) -> str:
    return f"jarvis-task-{value[:8]}" if len(value) >= 8 else f"jarvis-task-{value}"


def read_offset(offset_path: str) -> int:
    try:
        if os.path.exists(offset_path):
            with open(offset_path, "r", encoding="utf-8") as f:
                val = int(f.read().strip())
        else:
            val = 0
    except (ValueError, OSError):
        val = 0

    if os.path.exists(DEFAULT_STAGING_JSONL):
        try:
            size = os.path.getsize(DEFAULT_STAGING_JSONL)
        except OSError:
            size = 0
        if val > size:
            val = size
    return val


def write_offset(offset_path: str, offset: int) -> None:
    os.makedirs(os.path.dirname(offset_path) or ".", exist_ok=True)
    with open(offset_path, "w", encoding="utf-8") as f:
        f.write(str(offset))


def load_synced_tasks(synced_path: str) -> set[str]:
    if os.path.exists(synced_path):
        try:
            with open(synced_path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_synced_tasks(synced_path: str, synced_set: Iterable[str]) -> None:
    os.makedirs(os.path.dirname(synced_path) or ".", exist_ok=True)
    with open(synced_path, "w", encoding="utf-8") as f:
        json.dump(list(synced_set), f)


def parse_new_tasks(content: str, synced_tasks: set[str]) -> list[tuple[str, str]]:
    new_tasks: list[tuple[str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("- [ ]") or line.startswith("* [ ]"):
            task_text = line[5:].strip()
            task_hash = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
            if task_hash not in synced_tasks:
                new_tasks.append((task_hash, task_text))
    return new_tasks


def append_to_staging(
    tasks: Iterable[tuple[str, str]],
    *,
    staging_jsonl: str = DEFAULT_STAGING_JSONL,
    source: str = "openjarvis",
    dry_run: bool = False,
) -> list[dict]:
    os.makedirs(os.path.dirname(staging_jsonl) or ".", exist_ok=True)
    events: list[dict] = []
    for task_hash, task_text in tasks:
        event = {
            "type": "kanban_create",
            "task": task_text,
            "priority": "normal",
            "source": source,
            "status": "pending",
            "retry_count": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "idempotency_key": slugify_idempotency(task_hash),
        }
        events.append(event)
        if not dry_run:
            with open(staging_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
    return events


def process_event(event: dict, dry_run: bool = False) -> None:
    if event.get("type") == "kanban_create":
        task_title = event.get("task", "Untitled Task")
        print(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
            f"{'DRY RUN: ' if dry_run else ''}Enqueue: {task_title}"
        )


def tail_staging(
    *,
    staging_jsonl: str = DEFAULT_STAGING_JSONL,
    offset_path: str = DEFAULT_OFFSET_PATH,
    sleep_between_lines: float = 0.0,
    dry_run: bool = False,
) -> int:
    if not os.path.exists(staging_jsonl):
        return 0

    offset = read_offset(offset_path)
    processed = 0
    try:
        with open(staging_jsonl, "r", encoding="utf-8") as f:
            f.seek(offset)
            while True:
                line_offset = f.tell()
                line = f.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    if not dry_run:
                        write_offset(offset_path, f.tell())
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print("Skipping malformed JSON line.")
                    if not dry_run:
                        write_offset(offset_path, f.tell())
                    continue

                try:
                    process_event(event, dry_run=dry_run)
                except Exception as exc:
                    print(f"Failed event processing: {exc}")
                    if not dry_run:
                        write_offset(offset_path, line_offset)
                    break

                if not dry_run:
                    write_offset(offset_path, f.tell())
                processed += 1

                if sleep_between_lines > 0:
                    time.sleep(sleep_between_lines)
    except OSError as exc:
        print(f"Error reading staging: {exc}")
    return processed


def sync_task_markdown(
    *,
    task_md: str = DEFAULT_TASK_MD,
    staging_jsonl: str = DEFAULT_STAGING_JSONL,
    synced_path: str = DEFAULT_SYNCED_PATH,
    dry_run: bool = False,
) -> Tuple[int, int]:
    if not os.path.exists(task_md):
        return 0, 0

    try:
        with open(task_md, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        print(f"Error reading task md: {exc}")
        return 0, 0

    synced_tasks = load_synced_tasks(synced_path)
    new_tasks = parse_new_tasks(content, synced_tasks)
    events = append_to_staging(new_tasks, staging_jsonl=staging_jsonl, dry_run=dry_run)

    if events and not dry_run:
        for _, task_text in new_tasks:
            task_hash = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
            synced_tasks.add(task_hash)
        save_synced_tasks(synced_path, synced_tasks)

    return len(new_tasks), len(events)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenJarvis kanban staging ingest")
    parser.add_argument("--task-md", default=DEFAULT_TASK_MD)
    parser.add_argument("--staging-jsonl", default=DEFAULT_STAGING_JSONL)
    parser.add_argument("--offset-path", default=DEFAULT_OFFSET_PATH)
    parser.add_argument("--synced-path", default=DEFAULT_SYNCED_PATH)
    parser.add_argument("--one-shot", action="store_true")
    parser.add_argument("--tail-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.tail_only:
        processed = tail_staging(
            staging_jsonl=args.staging_jsonl,
            offset_path=args.offset_path,
            dry_run=args.dry_run,
        )
        print(f"tail_processed={processed}")
        return 0

    if args.one_shot:
        new_tasks, events = sync_task_markdown(
            task_md=args.task_md,
            staging_jsonl=args.staging_jsonl,
            synced_path=args.synced_path,
            dry_run=args.dry_run,
        )
        print(f"new_tasks={new_tasks} staged_events={events}")
        return 0

    last_signature = None
    while True:
        new_tasks, events = sync_task_markdown(
            task_md=args.task_md,
            staging_jsonl=args.staging_jsonl,
            synced_path=args.synced_path,
            dry_run=args.dry_run,
        )
        if events:
            last_signature = time.time()

        tail_staging(
            staging_jsonl=args.staging_jsonl,
            offset_path=args.offset_path,
            sleep_between_lines=0.0,
            dry_run=args.dry_run,
        )
        time.sleep(10)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_STAGING_JSONL",
    "DEFAULT_OFFSET_PATH",
    "DEFAULT_TASK_MD",
    "DEFAULT_SYNCED_PATH",
    "slugify_idempotency",
    "read_offset",
    "write_offset",
    "load_synced_tasks",
    "save_synced_tasks",
    "parse_new_tasks",
    "append_to_staging",
    "process_event",
    "tail_staging",
    "sync_task_markdown",
    "main",
]
