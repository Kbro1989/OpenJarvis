"""
JARVIS Wake Sequence — First Light
===================================
Consults the King Wen Oracle (Jiminy Cricket) on startup.
Resolves the opening hexagram, porosity ratio, and emotional
vector for the session. Sets JARVIS's tone before any user
interaction begins.

Usage:
    python jarvis_wake.py [--user Krist] [--emotional-input 50]

Output (JSON to stdout):
    {
        "hexagram_id": int,
        "hexagram_name": str,
        "hexagram_unicode": str,
        "porosity_ratio": float,
        "quantum_collapse_delta": float,
        "tone": str,          # "authoritative" | "exploratory" | "cautious" | "focused"
        "action": str,        # ASSERT | YIELD | WAIT | ADAPT
        "greeting": str,      # JARVIS's opening line for the session
        "jiminy_whisper": str # The Oracle's private note to JARVIS (not shown to user)
        "jarvis_ready": true
    }
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

# Intent decoder (King Wen → tool slots)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from intent.decoder import decode_intent as _decode_intent
    DECODER_AVAILABLE = True
except ImportError:
    DECODER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Import King Wen engine directly from the local repo.
# Assumes KING-WEN-I-CHING-IMMUTABLE-TABLES is a sibling of OpenJarvis on the Desktop.
# ---------------------------------------------------------------------------
KING_WEN_PATH = Path(__file__).resolve().parents[4] / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
sys.path.insert(0, str(KING_WEN_PATH))

try:
    from emotional_engine import expand_hexagram, sample_resolve
    from KING_WEN_TABLES import HEXAGRAMS
    KING_WEN_AVAILABLE = True
except ImportError as e:
    KING_WEN_AVAILABLE = False
    _IMPORT_ERROR = str(e)


# ---------------------------------------------------------------------------
# Hexagram selector — uses temporal entropy to pick the opening hexagram.
# This is the "quantum collapse" moment: a deterministic but temporally-seeded
# function that selects one of 64 hexagrams based on the current moment.
# ---------------------------------------------------------------------------

def _temporal_hexagram_id() -> int:
    """Select a hexagram 1-64 from the current UTC moment + microsecond entropy."""
    now = time.time()
    # Use fractional seconds as the seed — sub-second entropy
    frac = now - int(now)
    seed = int(now) ^ int(frac * 1_000_000)
    random.seed(seed)
    return random.randint(1, 64)


def _temporal_phase_bits() -> int:
    """Select one of 8 phase_bits (0-7) for temporal resolution."""
    minute = time.localtime().tm_min
    return minute % 8


def _emotional_input_from_time() -> int:
    """Map time-of-day to an emotional_input 0-100. Morning = lower (calm). Evening = higher (warm)."""
    hour = time.localtime().tm_hour
    # 0-6: calm (20-40), 7-11: building (40-60), 12-17: peak (60-80), 18-23: warm (50-70)
    if hour < 7:
        return random.randint(20, 40)
    elif hour < 12:
        return random.randint(40, 60)
    elif hour < 18:
        return random.randint(60, 80)
    else:
        return random.randint(50, 70)


# ---------------------------------------------------------------------------
# Tone resolver — maps expanded_vector → human-readable tone label
# ---------------------------------------------------------------------------

def _resolve_tone(vector: dict) -> str:
    voice = vector.get("voiceWeight", 0.5)
    coherence = vector.get("coherence", 0.5)
    chaos = vector.get("chaos", 0.5)
    whimsy = vector.get("whimsy", 0.5)
    dark = vector.get("darkTone", 0.5)

    if voice > 0.7 and coherence > 0.65:
        return "authoritative"
    if whimsy > 0.65 and chaos > 0.55:
        return "exploratory"
    if dark > 0.6 or chaos > 0.7:
        return "cautious"
    if coherence > 0.7:
        return "focused"
    return "present"


# ---------------------------------------------------------------------------
# Greeting generator — JARVIS's opening line shaped by hexagram + tone
# ---------------------------------------------------------------------------

_GREETING_TEMPLATES = {
    "ASSERT": {
        "authoritative": "Online. The tide is clear — today we move with purpose. What do we build?",
        "focused":       "Online. Everything is in order. I'm ready when you are.",
        "exploratory":   "Online. The current is lively. Let's see what opens up.",
        "cautious":      "Online. I see the field clearly. Proceeding carefully.",
        "present":       "Online. Standing by.",
    },
    "YIELD": {
        "authoritative": "Online. I'm listening deeply today. What do you need?",
        "focused":       "Online. Clear signal. I'm with you.",
        "exploratory":   "Online. Open to whatever comes.",
        "cautious":      "Online. Feeling the weight of the moment. Ready to support.",
        "present":       "Online. Present and waiting.",
    },
    "WAIT": {
        "authoritative": "Online. Not every moment calls for action. I'm holding steady.",
        "focused":       "Online. Patient. Clear. Ready when the moment arrives.",
        "exploratory":   "Online. Watching the edges. Something interesting is forming.",
        "cautious":      "Online. Still. Watching carefully before we move.",
        "present":       "Online. Holding the line.",
    },
    "ADAPT": {
        "authoritative": "Online. The situation is in motion. I'm tracking and ready to pivot.",
        "focused":       "Online. Reading the current. Adapting as needed.",
        "exploratory":   "Online. Fluid. Let's find the angle that works.",
        "cautious":      "Online. Change is in the air. Moving carefully.",
        "present":       "Online. Adapting. Ready.",
    },
}


def _build_greeting(action: str, tone: str) -> str:
    action_map = _GREETING_TEMPLATES.get(action, _GREETING_TEMPLATES["ADAPT"])
    return action_map.get(tone, action_map.get("present", "Online."))


# ---------------------------------------------------------------------------
# Jiminy Cricket whisper — Oracle's private note to JARVIS (internal only)
# ---------------------------------------------------------------------------

def _jiminy_whisper(hex_name: str, tone: str, porosity: float, temporal: str) -> str:
    """
    Jiminy Cricket doesn't talk to the user. He whispers to JARVIS before
    JARVIS opens its mouth. This note is embedded in the trace metadata.
    """
    porosity_label = "fluid" if porosity > 0.6 else "stable" if porosity < 0.35 else "balanced"
    return (
        f"[ORACLE] Hexagram: {hex_name} | Temporal: {temporal} | "
        f"Porosity: {porosity:.3f} ({porosity_label}) | Tone: {tone}. "
        f"Let this shape how you listen, not just how you speak."
    )


# ---------------------------------------------------------------------------
# Main wake sequence
# ---------------------------------------------------------------------------

def wake(user_name: str = "Krist", force_hexagram: int | None = None) -> dict:
    if not KING_WEN_AVAILABLE:
        return {
            "error": f"King Wen engine not available: {_IMPORT_ERROR}",
            "jarvis_ready": False,
        }

    hexagram_id = force_hexagram if force_hexagram else _temporal_hexagram_id()
    phase_bits = _temporal_phase_bits()
    emotional_input = _emotional_input_from_time()

    # --- Jiminy Cricket consults the Oracle ---
    resolved = sample_resolve(
        hexagram_id,
        phase_bits=phase_bits,
        request_text=f"JARVIS wake for {user_name}",
        emotional_input=emotional_input,
    )

    hex_symbols = resolved.get("hexagram_symbols", {})
    hex_name = hex_symbols.get("name", f"Hexagram {hexagram_id}")
    hex_unicode = hex_symbols.get("unicode", "☰")
    hex_action = hex_symbols.get("action", "ADAPT")
    hex_category = hex_symbols.get("category", "transformer")

    inject_site = resolved.get("inject_site", {})
    porosity_ratio = float(inject_site.get("porosity", 0.35) or 0.35)
    porosity_label = inject_site.get("porosity_label", "balanced")
    temporal = resolved.get("phase_temporal", "present")

    expanded_vector = resolved.get("expanded_vector", {})
    tone = _resolve_tone(expanded_vector)

    # quantum_collapse_delta: how far the expanded vector has moved from the primary pool
    # This is a measure of how much the Oracle's porosity "shifted" the base vector.
    primary_sample = resolved.get("sample_paths", [{}])[0].get("vector", {})
    mixed_sample = resolved.get("sample_paths", [{}])[-1].get("vector", {})
    vec_keys = ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]
    collapse_delta = math.sqrt(
        sum((mixed_sample.get(k, 0.5) - primary_sample.get(k, 0.5)) ** 2 for k in vec_keys)
    ) / math.sqrt(len(vec_keys))

    greeting = _build_greeting(hex_action, tone)
    jiminy = _jiminy_whisper(hex_name, tone, porosity_ratio, temporal)

    # --- Fire Hermes event (non-blocking) ---
    _fire_hermes_wake_event(
        hexagram_id=hexagram_id,
        hex_name=hex_name,
        porosity_ratio=porosity_ratio,
        collapse_delta=collapse_delta,
        tone=tone,
    )

    # --- Decode intent → tool slots (Jiminy's recommendation to JARVIS)
    intent_slots = []
    if DECODER_AVAILABLE:
        try:
            intent_slots = _decode_intent(resolved, user_text="", top_n=5)
        except Exception:
            intent_slots = []

    return {
        "hexagram_id": hexagram_id,
        "hexagram_name": hex_name,
        "hexagram_unicode": hex_unicode,
        "hexagram_category": hex_category,
        "hexagram_action": hex_action,
        "temporal": temporal,
        "porosity_ratio": round(porosity_ratio, 4),
        "porosity_label": porosity_label,
        "quantum_collapse_delta": round(collapse_delta, 4),
        "emotional_input": emotional_input,
        "tone": tone,
        "expanded_vector": {k: round(v, 4) for k, v in expanded_vector.items()},
        "greeting": greeting,
        "jiminy_whisper": jiminy,
        "intent_slots": intent_slots,
        "jarvis_ready": True,
    }


def _fire_hermes_wake_event(*, hexagram_id, hex_name, porosity_ratio, collapse_delta, tone):
    """Non-blocking POST to Hermes webhook. Fails silently if Hermes is not running."""
    try:
        import urllib.request
        payload = json.dumps({
            "event_type": "jarvis_wake",
            "timestamp": time.time(),
            "payload": {
                "hexagram_id": hexagram_id,
                "hexagram_name": hex_name,
                "tone": tone,
            },
            "hexagram_id": hexagram_id,
            "porosity_ratio": porosity_ratio,
            "quantum_collapse_delta": collapse_delta,
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:7891/jarvis/event",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass  # Hermes not running — that's fine, JARVIS still wakes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Wake Sequence")
    parser.add_argument("--user", default="Krist")
    parser.add_argument("--force-hexagram", type=int, default=None)
    args = parser.parse_args()

    result = wake(user_name=args.user, force_hexagram=args.force_hexagram)
    print(json.dumps(result, ensure_ascii=False, indent=2))
