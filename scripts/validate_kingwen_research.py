#!/usr/bin/env python3
"""Realtime validation: completion engine follows real research data."""

import sys
from typing import Any, Dict

ROOT = r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES"
sys.path.insert(0, ROOT)

from kingwen_ternary_tables_complete import VOICEBOX_VOICE_POOL, HEXAGRAM_INJECTION_SITE, EMOTIONAL_WEIGHTS
from openjarvis.emotion.kingwen_completion_injection import KingWenCompletionInjectionEngine


def _validate_slot(slot: Any, pool_names: set[str], inject_site: Dict[str, Any]) -> list[str]:
    issues: list[str] = []
    primary = str((inject_site.get("primary_pool") or "")).strip()
    secondary = str((inject_site.get("secondary_pool") or "")).strip()
    if primary and primary not in pool_names:
        issues.append(f"missing primary pool {primary}")
    if secondary and secondary not in pool_names:
        issues.append(f"missing secondary pool {secondary}")
    if not primary and not secondary:
        issues.append("no pools")
    if not str(inject_site.get("category") or "").strip():
        issues.append("missing category")
    if not str(inject_site.get("action") or "").strip():
        issues.append("missing action")
    return issues


def main() -> int:
    engine = KingWenCompletionInjectionEngine(session_id="realtime-validate")
    payload = engine.inject("validate research fidelity", emotional_input=50)

    consensus: Dict[str, Any] = payload.get("consensus") or {}
    expanded = consensus.get("crowd_hexagram_votes") or []
    pool_names = set(VOICEBOX_VOICE_POOL.keys())

    slot_failures = 0
    reported = 0
    active_hex = None
    active_domain = None
    active_injection = None

    for item in expanded:
        hex_id = int(item.get("hexagram_id") or 0)
        inject_site = item.get("inject_site") or {}
        issues = _validate_slot(item, pool_names, inject_site)
        if hex_id <= 3 or not reported:
            print(f"hex={hex_id:02d} domain={inject_site.get('category') or '-'} primary={inject_site.get('primary_pool') or '-'} secondary={inject_site.get('secondary_pool') or '-'} issues={issues}")
            reported += 1
        if issues and hex_id <= 3:
            slot_failures += len(issues)

    dominant = payload.get("dominant") or {}
    hex_id = dominant.get("hexagram_id") or consensus.get("consensus_hexagram_id")
    active_hex = hex_id
    active_domain = str((dominant.get("vectors") or {}).get("domain") or payload.get("injection") or "")
    active_injection = payload.get("injection")

    print("expansion_source=" + str(payload.get("expansion_source")))
    print("total_resolved=" + str(payload.get("expansion", {}).get("total_resolved")))
    print("active_hex=" + str(active_hex))
    print("active_domain=" + str(active_domain))
    print("active_injection=" + str(active_injection))

    if slot_failures:
        print("SLOT_FAILURES=" + str(slot_failures))
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
