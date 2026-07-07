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
    from emotional_engine import expand_hexagram, sample_resolve, collapse_full_128
    from KING_WEN_TABLES import HEXAGRAMS
    KING_WEN_AVAILABLE = True
except ImportError as e:
    KING_WEN_AVAILABLE = False
    _IMPORT_ERROR = str(e)


def consult(query: str, context: str = "", emotional_input: int = 50) -> dict:
    if not KING_WEN_AVAILABLE:
        return {"error": f"King Wen unavailable: {_IMPORT_ERROR}"}

    # Derive hexagram from query hash — same query always resolves to same hexagram
    # (deterministic), but different emotional_inputs shift the porosity output.
    query_hash = hash(query.lower().strip()) % 64
    hexagram_id = (query_hash % 64) + 1
    phase_bits = int(time.time()) % 8  # temporal phase — changes every ~7.5 minutes

    resolved = sample_resolve(
        hexagram_id,
        phase_bits=phase_bits,
        request_text=query,
        emotional_input=emotional_input,
    )

    hex_sym = resolved.get("hexagram_symbols", {})
    inject = resolved.get("inject_site", {})
    vec = resolved.get("resolved_vector", {})

    # Derive tone_mode from the resolved vector
    voice = vec.get("voiceWeight", 0.5)
    coherence = vec.get("coherence", 0.5)
    chaos = vec.get("chaos", 0.5)
    whimsy = vec.get("whimsy", 0.5)

    if voice > 0.7 and coherence > 0.65:
        tone_mode = "authoritative"
    elif whimsy > 0.65 and chaos > 0.55:
        tone_mode = "exploratory"
    elif coherence > 0.7:
        tone_mode = "focused"
    else:
        tone_mode = "present"

    action = hex_sym.get("action", "ADAPT")
    category = hex_sym.get("category", "transformer")

    # recommended_action: combines hexagram action with Oracle judgment
    action_map = {
        "ASSERT": "Proceed with confidence. The path is clear.",
        "YIELD":  "Listen before acting. Let the situation speak first.",
        "WAIT":   "Hold position. The timing is not yet right.",
        "ADAPT":  "Stay flexible. The situation is in motion.",
    }
    recommended_action = action_map.get(action, "Proceed with awareness.")

    return {
        "hexagram_id": hexagram_id,
        "hexagram_name": hex_sym.get("name", f"Hexagram {hexagram_id}"),
        "hexagram_unicode": hex_sym.get("unicode", ""),
        "hexagram_chinese": hex_sym.get("chinese", ""),
        "hexagram_category": category,
        "judgment": inject.get("reason", ""),
        "porosity_ratio": round(float(inject.get("porosity", 0.35) or 0.35), 4),
        "porosity_label": inject.get("porosity_label", "balanced"),
        "void_dropper_pos": phase_bits,
        "quantum_collapse_delta": round(abs(vec.get("voiceWeight", 0.5) - vec.get("chaos", 0.5)), 4),
        "tone_mode": tone_mode,
        "resolved_vector": {k: round(v, 4) for k, v in vec.items()},
        "temporal": resolved.get("phase_temporal", "present"),
        "recommended_action": recommended_action,
        "query": query,
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
