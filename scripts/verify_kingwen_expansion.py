"""verify_kingwen_expansion.py

Verify OpenJarvis completion injection uses the real immutable-tables
expansion frontier, not hardcoded counts, and that it builds/reports
the actual 64-slot batch payload.
"""
from __future__ import annotations

import logging
import os
import sys

ROOT = os.environ.get(
    "KING_WEN_IMMUTABLE_TABLES",
    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES",
)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openjarvis.emotion.kingwen_engine_adapter import collapse_full_128
from openjarvis.emotion.kingwen_completion_injection import KingWenCompletionInjectionEngine


def main() -> int:
    engine = KingWenCompletionInjectionEngine(session_id="verify-repl")
    payload = engine.inject("progress openjarvis completion engine", emotional_input=50)

    consensus = payload.get("consensus") or {}
    expansion = payload.get("expansion") or {}
    total_expanded = int(expansion.get("total_expanded") or 0)
    total_resolved = int(expansion.get("total_resolved") or 0)
    expansion_source = str(expansion.get("source") or payload.get("expansion_source") or "none")

    raw_collapse = collapse_full_128(emotional_input=50) or {}
    raw_total_expanded = len(raw_collapse.get("expanded") or [])
    raw_total_resolved = len(raw_collapse.get("resolved") or [])

    print(f"expansion_source={expansion_source}")
    print(f"engine_expanded={total_expanded}")
    print(f"engine_resolved={total_resolved}")
    print(f"raw_collapse_total={raw_total_expanded}")
    print(f"raw_resolved_len={raw_total_resolved}")
    print(f"consensus_hexagram_id={consensus.get('consensus_hexagram_id')}")
    print(f"injection={payload.get('injection')}")

    if total_expanded <= 0 or total_resolved <= 0:
        print("FAIL: expansion counts are zero")
        return 1
    if expansion_source == "none":
        print("FAIL: no expansion source used")
        return 1
    if total_expanded != raw_total_expanded or total_resolved != raw_total_resolved:
        print("FAIL: engine counts do not match adapter raw counts")
        return 1
    print("PASS: real expansion frontier used, counts match adapter payload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
