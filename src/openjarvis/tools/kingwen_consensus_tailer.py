"""King Wen consensus tailer — offset-tailing delta reader for 512-state collapse events.

Builds on the verified antigravity kanban offset-tailing pattern from
``openjarvis.tools.kanban_ingest``. Reads new JSONL lines by byte offset,
filters for ``KINGWEN_CONSENSUS_UPDATE`` events, and surfaces them to the
workflow engine without full-file rewrites.

Constraints:
- No hard dependency on antigravity runtime paths
- No external cloud-specific calls
- No mock/stub/placeholder
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from openjarvis.tools.kanban_ingest import read_offset, write_offset, tail_staging  # noqa: E402
except ImportError:  # pragma: no cover
    def read_offset(offset_path: str) -> int:  # type: ignore[misc]
        try:
            if os.path.exists(offset_path):
                with open(offset_path, "r", encoding="utf-8") as f:
                    return int(f.read().strip())
        except (ValueError, OSError):
            pass
        return 0

    def write_offset(offset_path: str, offset: int) -> None:  # type: ignore[misc]
        os.makedirs(os.path.dirname(offset_path) or ".", exist_ok=True)
        with open(offset_path, "w", encoding="utf-8") as f:
            f.write(str(offset))


DEFAULT_CONSENSUS_LOG = os.environ.get(
    "OPENJARVIS_KINGWEN_CONSENSUS_LOG",
    str(os.path.expanduser("~/.openjarvis/kingwen-consensus.jsonl")),
)


class KingWenConsensusTailer:
    def __init__(self, log_path: str, offset_path: str) -> None:
        self.log_path = log_path
        self.offset_path = offset_path
        self.consensus_buffer: list[dict[str, Any]] = []

    def ingest_new_consensus(self) -> list[dict[str, Any]]:
        new_events: list[dict[str, Any]] = []
        if not os.path.exists(self.log_path):
            return new_events

        offset = read_offset(self.offset_path)
        with open(self.log_path, "r", encoding="utf-8") as f:
            f.seek(offset)
            while True:
                line_offset = f.tell()
                line = f.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    write_offset(self.offset_path, f.tell())
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    write_offset(self.offset_path, f.tell())
                    continue

                if event.get("type") == "KINGWEN_CONSENSUS_UPDATE":
                    new_events.append(event)
                    self.consensus_buffer.append(event)

                write_offset(self.offset_path, f.tell())

        return new_events

    def clear(self) -> None:
        self.consensus_buffer.clear()


__all__ = [
    "DEFAULT_CONSENSUS_LOG",
    "KingWenConsensusTailer",
]
