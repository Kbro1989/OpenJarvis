"""
Oracle Bridge — Hermes ↔ King Wen Consult
==========================================
Called by the Hermes `oracle_consult` skill entrypoint.
Accepts a query + context via stdin JSON or CLI args.
Returns a full Oracle consultation result as JSON stdout.

Dual-direction:
  Hermes → oracle_bridge.py → King Wen engine → JSON → Hermes agent
  JARVIS  → oracle_bridge.py → King Wen engine → JSON → JARVIS tone
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

KING_WEN_PATH = Path(__file__).resolve().parents[4] / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
sys.path.insert(0, str(KING_WEN_PATH))

try:
    from openjarvis.emotion.kingwen_engine_adapter import collapse_full_128, consult as kingwen_consult  # noqa: E402
    KING_WEN_AVAILABLE = True
except ImportError as e:
    KING_WEN_AVAILABLE = False
    _IMPORT_ERROR = str(e)


def consult(query: str, context: str = "", emotional_input: int = 50) -> dict:
    if not KING_WEN_AVAILABLE:
        return {"error": f"King Wen unavailable: {_IMPORT_ERROR}"}

    collapse = collapse_full_128(emotional_input=emotional_input)
    consensus = collapse.get("consensus", {}) or {}
    expanded = collapse.get("expanded", []) or []
    resolved = collapse.get("resolved", []) or []

    hexagram_id = consensus.get("consensus_hexagram_id")
    hexagram_name = consensus.get("consensus_hexagram_name", "")
    temporal = consensus.get("consensus_temporal") or "present"
    porosity = consensus.get("consensus_porosity_mean")
    vector = consensus.get("consensus_vector") or {}
    intent = consensus.get("consensus_intent", "")
    explanation = consensus.get("consensus_explanation", "")
    yaolabel = consensus.get("consensus_yao", "stable_yao")
    temporal_distribution = consensus.get("temporal_distribution", {})

    hex_symbols = {}
    if hexagram_id:
        try:
            hex_symbols = kingwen_consult(query, emotional_input=emotional_input)
            hex_symbols = {
                "unicode": hex_symbols.get("hexagram_symbol", ""),
                "chinese": hex_symbols.get("hexagram_chinese", ""),
                "pinyin": hex_symbols.get("hexagram_pinyin", ""),
            }
        except Exception:
            pass

    return {
        "hexagram_id": int(hexagram_id or 0),
        "hexagram_name": hexagram_name or "",
        "hexagram_symbol": hex_symbols.get("unicode", ""),
        "hexagram_chinese": hex_symbols.get("chinese", ""),
        "hexagram_pinyin": hex_symbols.get("pinyin", ""),
        "consensus_hexagram_id": int(hexagram_id or 0),
        "consensus_hexagram_name": hexagram_name or "",
        "consensus_temporal": temporal,
        "consensus_yao": yaolabel,
        "consensus_porosity_mean": porosity,
        "consensus_porosity_mode": consensus.get("consensus_porosity_mode"),
        "consensus_vector": vector,
        "consensus_intent": intent,
        "consensus_explanation": explanation,
        "temporal_distribution": temporal_distribution,
        "porosity_ratio": round(float(porosity or 0.35), 4),
        "resolved_vector": {k: round(v, 4) for k, v in vector.items()},
        "temporal": temporal,
        "query": query,
        "context": context,
        "consensus_path": {
            "total_expanded": len(collapse.get("expanded", []) or []),
            "total_resolved": len(collapse.get("resolved", []) or []),
            "emotional_input": emotional_input,
        },
        "crowd_hexagram_votes": [
            {
                "hexagram_id": item.get("hexagram_id"),
                "hexagram_name": (item.get("hexagram_symbols") or {}).get("name", ""),
                "hexagram_symbol": (item.get("hexagram_symbols") or {}).get("unicode", ""),
                "category": (item.get("hexagram_symbols") or {}).get("category", ""),
                "action": (item.get("hexagram_symbols") or {}).get("action", ""),
                "expanded_vector": item.get("expanded_vector", {}),
                "inject_site": item.get("inject_site", {}),
                "line_states": item.get("line_states", []),
                "phase_bits": item.get("phase_bits"),
                "phase_temporal": (item.get("hexagram_symbols") or {}).get("name", ""),
            }
            for item in expanded[:64]
        ],
        "winning_hex_line_states": [
            ls
            for item in resolved
            if int(item.get("hexagram_id") or 0) == int(hexagram_id or 0)
            for ls in (item.get("line_states") or [])
        ],
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Oracle Bridge — King Wen consult")
    parser.add_argument("--query", default="")
    parser.add_argument("--context", default="")
    parser.add_argument("--emotional-input", type=int, default=50)

    # Also accept JSON piped via stdin (for Hermes skill entrypoint)
    if not sys.stdin.isatty():
        try:
            stdin_data = json.load(sys.stdin)
            args_query = stdin_data.get("query", "")
            args_context = stdin_data.get("context", "")
            args_ei = int(stdin_data.get("emotional_input", 50))
            result = consult(args_query, args_context, args_ei)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)
        except Exception:
            pass

    args = parser.parse_args()
    result = consult(args.query, args.context, args.emotional_input)
    print(json.dumps(result, ensure_ascii=False, indent=2))
