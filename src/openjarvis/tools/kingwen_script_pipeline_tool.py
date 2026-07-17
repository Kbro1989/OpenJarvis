"""kingwen_script_pipeline_tool.py — Universal cognitive script pipeline.

Expands POG2's Gutenberg→movie pipeline into a universal agentic cognitive
state machine that drives emotional/intent influence over ANY script type:
  prose | screenplay | dialogue | lyrics | image_prompt | code | essay |
  training_record | gutenberg

Architecture:
  1. Mini quantum intent expansion  → collapse intent to hexagram state
  2. Voice weight modulation        → decision-matrix multi-axis scoring
  3. Script-type dispatcher         → 9 generators, each hexagram-led
  4. Append-only ledger             → ~/.openjarvis/script_pipeline_ledger.jsonl

No cross-calling Hermes or POG2 runtime.  Quantum expansion is implemented
inline using `consult()` from the existing OpenJarvis engine adapter.
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

LOGGER = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_TOOL_ID = "kingwen_script_pipeline"
_LEDGER_PATH = Path.home() / ".openjarvis" / "script_pipeline_ledger.jsonl"

SCRIPT_TYPES = frozenset({
    "prose",
    "screenplay",
    "dialogue",
    "lyrics",
    "image_prompt",
    "code",
    "essay",
    "training_record",
    "gutenberg",
})

# Hexagram category → aesthetic signature for modulation
_CATEGORY_AESTHETICS: Dict[str, Dict[str, str]] = {
    "sovereign": {
        "register": "authoritative",
        "arc":      "assertion → dominion → integration",
        "sd_tag":   "majestic, golden hour, commanding composition",
    },
    "boundary": {
        "register": "observant",
        "arc":      "perception → limit → wisdom",
        "sd_tag":   "liminal, dusk light, threshold geometry",
    },
    "transformer": {
        "register": "dynamic",
        "arc":      "catalyst → dissolution → rebirth",
        "sd_tag":   "kinetic blur, deep contrast, emergent form",
    },
}

# Action → narrative role mapping
_ACTION_ROLES = {
    "ASSERT":  {"protagonist": True,  "tension_bias": 0.2},
    "YIELD":   {"protagonist": False, "tension_bias": -0.2},
    "ADAPT":   {"protagonist": None,  "tension_bias": 0.0},
    "OBSERVE": {"protagonist": False, "tension_bias": -0.1},
    "PERSIST": {"protagonist": True,  "tension_bias": 0.1},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(output: str, metadata: Dict[str, Any] | None = None) -> ToolResult:
    return ToolResult(tool_name=_TOOL_ID, content=output, success=True,
                      metadata=metadata or {})


def _err(msg: str) -> ToolResult:
    return ToolResult(tool_name=_TOOL_ID, content=f"ERROR: {msg}",
                      success=False)


def _append_ledger(record: Dict[str, Any]) -> None:
    """Append one record to the ledger.  Silently no-ops on any IO error."""
    try:
        _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("ledger write failed: %s", exc)


def _vec(oracle: Dict[str, Any]) -> Dict[str, float]:
    """Extract float voice-weight vector from oracle result dict."""
    raw = oracle.get("emotional_deltas") or oracle.get("consensus_vector") or {}
    axes = ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]
    return {k: float(raw.get(k, 0.0) or 0.0) for k in axes}


# ── Mini quantum intent expansion ─────────────────────────────────────────────

def _quantum_expand(
    intent: str,
    emotional_input: int,
    max_passes: int,
) -> Dict[str, Any]:
    """Run multi-pass superposition collapse over the intent string.

    Each pass shifts the emotional_input by a coherence-biased delta derived
    from the previous pass result.  The pass with the highest coherence score
    is selected as the collapsed state.

    Returns the winning oracle result dict.
    """
    from openjarvis.emotion.kingwen_engine_adapter import consult  # lazy import

    best: Dict[str, Any] = {}
    best_coherence = -1.0

    ei = max(0, min(100, emotional_input))

    for pass_num in range(max(1, max_passes)):
        try:
            result = consult(text=intent, session_id="script_pipeline",
                             emotional_input=ei)
        except Exception as exc:
            LOGGER.warning("quantum pass %d failed: %s", pass_num, exc)
            break

        v = _vec(result)
        coherence = v.get("coherence", 0.0)

        if coherence > best_coherence:
            best_coherence = coherence
            best = result

        # Coherence-biased gap fill for next pass
        gap = 0.5 - coherence           # positive when below midpoint
        shift = int(round(gap * 20))    # −10..+10
        ei = max(0, min(100, ei + shift))

    return best


def _force_hex_state(hex_id: int, emotional_input: int) -> Dict[str, Any]:
    """Skip expansion; directly force a specific hexagram identity.

    Runs a full consult for the voice weight vector, then overlays the
    requested hexagram's metadata from HEXAGRAM_BASE so that the returned
    state has hexagram_id == hex_id regardless of what the consensus picked.
    """
    from openjarvis.emotion.kingwen_engine_adapter import (
        consult, HEXAGRAM_BASE, HEXAGRAM_INJECTION_SITE,
    )

    result = consult(text=f"force_hex:{hex_id}", session_id="script_pipeline",
                     emotional_input=emotional_input)

    # Force hex identity fields
    hdata = HEXAGRAM_BASE.get(int(hex_id), {})
    result["hexagram_id"]              = int(hex_id)
    result["hexagram_name"]            = hdata.get("name", result.get("hexagram_name", ""))
    result["hexagram_symbol"]          = hdata.get("unicode", result.get("hexagram_symbol", ""))
    result["action"]                   = hdata.get("action", result.get("action", ""))
    result["category"]                 = hdata.get("category", result.get("category", ""))
    result["consensus_hexagram_id"]    = int(hex_id)
    result["consensus_hexagram_name"]  = hdata.get("name", "")
    result["consensus_hexagram_symbol"]= hdata.get("unicode", "")
    result["_forced_hex"]              = int(hex_id)
    return result


# ── Trigram force vectors (8 elemental trigrams, upper_idx/lower_idx 0-7) ──────
#
# Each trigram carries an elemental bias that shifts the base vector axes.
# Indices follow the immutable table encoding:
#   0=Kun(earth) 1=Zhen(thunder) 2=Kan(water) 3=Xun(wind)
#   4=Li(fire)   5=Gen(mountain) 6=Dui(lake)  7=Qian(heaven)
#
# Values are normalised per-axis influence weights (not absolute axis values).
# These are blended with the canonical weight via the trigram mix ratio.

_TRIGRAM_FORCE: Dict[int, Dict[str, float]] = {
    0: {"chaos": 0.05, "whimsy": 0.10, "darkTone": 0.10, "coherence": 0.90, "voiceWeight": 0.55},  # Kun  ☷ earth
    1: {"chaos": 0.70, "whimsy": 0.30, "darkTone": 0.35, "coherence": 0.40, "voiceWeight": 0.65},  # Zhen ☳ thunder
    2: {"chaos": 0.55, "whimsy": 0.10, "darkTone": 0.75, "coherence": 0.30, "voiceWeight": 0.45},  # Kan  ☵ water
    3: {"chaos": 0.40, "whimsy": 0.65, "darkTone": 0.15, "coherence": 0.60, "voiceWeight": 0.70},  # Xun  ☴ wind
    4: {"chaos": 0.30, "whimsy": 0.45, "darkTone": 0.20, "coherence": 0.75, "voiceWeight": 0.80},  # Li   ☲ fire
    5: {"chaos": 0.10, "whimsy": 0.15, "darkTone": 0.40, "coherence": 0.80, "voiceWeight": 0.60},  # Gen  ☶ mountain
    6: {"chaos": 0.20, "whimsy": 0.80, "darkTone": 0.10, "coherence": 0.65, "voiceWeight": 0.75},  # Dui  ☱ lake
    7: {"chaos": 0.05, "whimsy": 0.15, "darkTone": 0.00, "coherence": 0.98, "voiceWeight": 0.95},  # Qian ☰ heaven
}

# King Wen sequence pair map (hex_id → pair index 0-31)
# Hexagrams are ordered in 32 complementary pairs.
# Pair 0 = (1,2), pair 1 = (3,4), ..., pair 31 = (63,64).
_KW_PAIR = {hid: (hid - 1) // 2 for hid in range(1, 65)}


# ── Advanced mathematical enrichment ─────────────────────────────────────────

def _enrich_with_advanced_math(
    modulated: Dict[str, float],
    oracle: Dict[str, Any],
    emotional_input: int,
) -> Dict[str, float]:
    """Layer five mathematical expressions onto the porosity-modulated vector.

    Applied in order (each layer reads the output of the previous):

    1. **Canonical anchor** — blend with the immutable EMOTIONAL_WEIGHTS
       ground-truth for this hexagram (weight = 1 - porosity_max).
    2. **Inject site porosity window** — clamp each axis into [low, high]
       derived from POROSITY_LEVELS[inject.porosity].
    3. **Trigram force vectors** — upper and lower trigram elemental biases
       are mixed in at a fixed blend ratio (0.18 upper + 0.12 lower).
    4. **Ternary yao line-state tension** — count moving lines from
       binary_bottom_to_top; each moving line adds tension_per_line
       to chaos and darkTone, subtracts from coherence.
    5. **Gaussian emotional pull** — G = exp(-(ei-50)^2/1250) pulls the
       axis means toward the canonical vector proportionally to G.
    6. **Hamiltonian sequence modifier** — King Wen pair position (0-31)
       maps to a phase angle; cos(phase*π) modifies coherence, sin modifies
       whimsy, giving a smooth sinusoidal drift through the sequence space.
    """
    import math
    try:
        from openjarvis.emotion.kingwen_engine_adapter import (
            EMOTIONAL_WEIGHTS, HEXAGRAM_BASE,
            HEXAGRAM_INJECTION_SITE, POROSITY_LEVELS,
        )
    except Exception:
        return modulated  # graceful no-op if tables unavailable

    axes = ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]
    result = {k: float(modulated.get(k, 0.0)) for k in axes}

    hex_id = int(oracle.get("hexagram_id") or 1)
    hdata  = HEXAGRAM_BASE.get(hex_id, {})

    # ── 1. Canonical anchor ──────────────────────────────────────────────────
    cw_raw = EMOTIONAL_WEIGHTS.get(str(hex_id), {})
    canonical: Dict[str, float] = {
        k: float(cw_raw.get(k, result[k])) for k in axes
    }
    # Injection site porosity drives anchor strength:
    # sealed (0) → strong anchor (0.85), porous_max (4) → weak anchor (0.15)
    inj     = HEXAGRAM_INJECTION_SITE.get(hex_id, {})
    por_int = int(inj.get("porosity", 2))
    anchor_w = max(0.15, 0.85 - por_int * 0.175)  # 0.85, 0.675, 0.5, 0.325, 0.15
    for k in axes:
        result[k] = round(result[k] * (1.0 - anchor_w) + canonical[k] * anchor_w, 6)

    # ── 2. Inject site porosity window clamping ──────────────────────────────
    pl = POROSITY_LEVELS.get(str(por_int), POROSITY_LEVELS.get(por_int, {}))
    win = pl.get("window", [0.0, 1.0]) if isinstance(pl, dict) else [0.0, 1.0]
    low, high = float(win[0]), float(win[1])
    # The window defines how far each axis may deviate from its canonical value.
    for k in axes:
        delta = result[k] - canonical[k]
        # Clamp delta to [-high, +high]; window low is minimum exchange magnitude
        clamped_delta = max(-high, min(high, delta))
        if abs(clamped_delta) < low and abs(delta) > 0:
            clamped_delta = math.copysign(low, delta)
        result[k] = round(max(0.0, min(1.0, canonical[k] + clamped_delta)), 6)

    # ── 3. Trigram force vectors ─────────────────────────────────────────────
    upper_idx = int(hdata.get("upper_idx", 7))
    lower_idx = int(hdata.get("lower_idx", 7))
    upper_force = _TRIGRAM_FORCE.get(upper_idx, _TRIGRAM_FORCE[7])
    lower_force = _TRIGRAM_FORCE.get(lower_idx, _TRIGRAM_FORCE[7])
    for k in axes:
        blend = result[k] * 0.70 + upper_force[k] * 0.18 + lower_force[k] * 0.12
        result[k] = round(max(0.0, min(1.0, blend)), 6)

    # ── 4. Ternary yao line-state tension ────────────────────────────────────
    # Parse binary_bottom_to_top: '1'=yang, '0'=yin, each is a stable line.
    # Moving lines come from the yao label (consensus_yao from oracle).
    # A moving line is identified by '9' (old yang) or '6' (old yin) in the
    # yarrow count — we approximate from consensus_yao string suffix.
    yao_label   = str(oracle.get("consensus_yao", "") or "")
    # e.g. "moving_yao_3" → 3 moving lines; "stable_yao" → 0
    moving_count = 0
    for part in yao_label.replace("-", "_").split("_"):
        try:
            moving_count = int(part)
            break
        except ValueError:
            pass
    moving_count = min(6, max(0, moving_count))

    # Additional ternary tension from the 6-line binary string
    binary_str = str(hdata.get("binary_bottom_to_top", "111111"))
    yin_count  = binary_str.count("0")         # yin lines
    yang_count = binary_str.count("1")         # yang lines
    yin_ratio  = yin_count / max(1, len(binary_str))
    yang_ratio = yang_count / max(1, len(binary_str))

    tension_factor = moving_count / 6.0        # 0.0 (stable) → 1.0 (all moving)
    line_chaos     = tension_factor * 0.15     # moving lines add chaos
    line_dark      = tension_factor * 0.10 * yin_ratio    # yin-heavy + moving → dark
    line_coh_delta = -tension_factor * 0.12 + (yang_ratio - yin_ratio) * 0.05

    result["chaos"]     = round(max(0.0, min(1.0, result["chaos"]     + line_chaos)), 6)
    result["darkTone"]  = round(max(0.0, min(1.0, result["darkTone"]  + line_dark)), 6)
    result["coherence"] = round(max(0.0, min(1.0, result["coherence"] + line_coh_delta)), 6)
    # Yin-dominant lines soften the voice weight slightly
    result["voiceWeight"] = round(max(0.0, min(1.0,
        result["voiceWeight"] - yin_ratio * 0.05 + yang_ratio * 0.03
    )), 6)

    # ── 5. Gaussian emotional pull ────────────────────────────────────────────
    # G is 1.0 when ei=50 (neutral), approaching 0 at extremes.
    # It pulls the result axes toward canonical at strength G*0.25.
    ei = float(max(0, min(100, emotional_input)))
    G  = math.exp(-((ei - 50.0) ** 2) / 1250.0)   # σ=25, peak at ei=50
    for k in axes:
        result[k] = round(
            max(0.0, min(1.0, result[k] * (1.0 - G * 0.25) + canonical[k] * G * 0.25)),
            6,
        )

    # ── 6. Hamiltonian King Wen sequence modifier ────────────────────────────
    # Each hexagram has a position in one of 32 complementary pairs.
    # Pair index 0-31 maps to a phase angle θ ∈ [0, π].
    # cos(θ) modifies coherence (maximum at pair 0, minimum at pair 16).
    # sin(θ) modifies whimsy (maximum at pair 8, zero at pairs 0 and 16).
    pair_idx   = _KW_PAIR.get(hex_id, 0)          # 0..31
    theta      = math.pi * pair_idx / 31.0        # 0..π
    coh_shift  = math.cos(theta) * 0.04           # ±0.04 over the sequence
    whim_shift = math.sin(theta) * 0.03           # 0..+0.03 peak at pair 8
    result["coherence"] = round(max(0.0, min(1.0, result["coherence"] + coh_shift)), 6)
    result["whimsy"]    = round(max(0.0, min(1.0, result["whimsy"]    + whim_shift)), 6)

    return result


# ── Voice weight modulation (decision-matrix multi-axis) ──────────────────────

def _modulate(
    v: Dict[str, float],
    script_type: str,
    voice_override: Dict[str, float] | None,
) -> Dict[str, float]:
    """Apply decision-matrix multi-axis scoring.

    Each axis is multiplied by a type-specific porosity weight, then any
    override values replace the result.  Produces the final modulated vector.
    """
    # Porosity windows per script type (how much the type amplifies each axis)
    _POROSITY: Dict[str, Dict[str, float]] = {
        "prose":           {"chaos": 0.6, "whimsy": 0.7, "darkTone": 0.8, "coherence": 1.0, "voiceWeight": 0.9},
        "screenplay":      {"chaos": 0.9, "whimsy": 0.5, "darkTone": 0.9, "coherence": 0.8, "voiceWeight": 1.0},
        "dialogue":        {"chaos": 0.7, "whimsy": 1.0, "darkTone": 0.6, "coherence": 0.7, "voiceWeight": 1.0},
        "lyrics":          {"chaos": 0.5, "whimsy": 1.0, "darkTone": 0.9, "coherence": 0.6, "voiceWeight": 0.8},
        "image_prompt":    {"chaos": 0.8, "whimsy": 0.9, "darkTone": 1.0, "coherence": 0.5, "voiceWeight": 0.7},
        "code":            {"chaos": 0.2, "whimsy": 0.1, "darkTone": 0.1, "coherence": 1.0, "voiceWeight": 0.8},
        "essay":           {"chaos": 0.4, "whimsy": 0.5, "darkTone": 0.5, "coherence": 1.0, "voiceWeight": 0.9},
        "training_record": {"chaos": 0.3, "whimsy": 0.3, "darkTone": 0.3, "coherence": 1.0, "voiceWeight": 1.0},
        "gutenberg":       {"chaos": 0.5, "whimsy": 0.6, "darkTone": 0.7, "coherence": 0.8, "voiceWeight": 0.9},
    }
    pw = _POROSITY.get(script_type, {k: 1.0 for k in v})
    modulated = {k: round(v.get(k, 0.0) * pw.get(k, 1.0), 6) for k in v}

    # Hamiltonian alignment (base pass): dampen chaos when coherence dominates
    if modulated.get("coherence", 0.0) > 0.7:
        modulated["chaos"] = round(modulated.get("chaos", 0.0) * 0.7, 6)

    # Apply explicit overrides last
    if voice_override:
        for k, val in voice_override.items():
            if k in modulated:
                modulated[k] = float(val)

    return modulated


def _modulate_full(
    v: Dict[str, float],
    script_type: str,
    voice_override: Optional[Dict[str, float]],
    oracle: Dict[str, Any],
    emotional_input: int,
) -> Dict[str, float]:
    """Full modulation pipeline: porosity → advanced math layers.

    1. Porosity-window base modulation (_modulate)
    2. Advanced math enrichment (_enrich_with_advanced_math):
       canonical anchor · inject site · trigram force · yao tension ·
       Gaussian pull · Hamiltonian sequence position
    3. Final voice_override
    """
    modulated = _modulate(v, script_type, None)          # base pass, no override yet
    enriched  = _enrich_with_advanced_math(modulated, oracle, emotional_input)
    if voice_override:
        for k, val in voice_override.items():
            if k in enriched:
                enriched[k] = float(val)
    return enriched


# ── Script type generators ─────────────────────────────────────────────────────

def _gen_prose(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Literary narrative — past/present/future arc from temporal reflections."""
    name    = oracle.get("hexagram_name", "The Unnamed")
    symbol  = oracle.get("hexagram_symbol", "")
    action  = oracle.get("action", "ASSERT")
    cat     = oracle.get("category", "transformer")
    phase   = oracle.get("phase_temporal", "present")
    aesth   = _CATEGORY_AESTHETICS.get(cat, _CATEGORY_AESTHETICS["transformer"])
    arc     = aesth["arc"]
    reg     = aesth["register"]

    chaos_pct   = int(mv.get("chaos",      0.0) * 100)
    dark_pct    = int(mv.get("darkTone",   0.0) * 100)
    whimsy_pct  = int(mv.get("whimsy",     0.0) * 100)

    past_tone    = "fractured" if dark_pct > 50 else "formative"
    present_tone = "turbulent" if chaos_pct > 50 else "measured"
    future_tone  = "surreal"   if whimsy_pct > 60 else "purposeful"

    return (
        f"# {symbol} {name}  [{action}]\n"
        f"*Register: {reg}  ·  Arc: {arc}  ·  Phase: {phase}*\n\n"
        f"**Past ({past_tone}):**  {intent.capitalize()} did not begin here. "
        f"The origins were {past_tone} — a time when forces gathered without name, "
        f"when the first motion was made not from choice but from necessity.\n\n"
        f"**Present ({present_tone}):**  Now the {present_tone} current runs "
        f"through what was once still.  {action.capitalize()} is not a posture — "
        f"it is the shape of this moment pressed into form.  The {name} hexagram "
        f"does not advise.  It describes.\n\n"
        f"**Future ({future_tone}):**  What comes forward will be {future_tone}.  "
        f"Not predicted — *shaped*.  The arc bends: {arc}.  "
        f"What you carry into that arc is the only variable that belongs to you.\n\n"
        f"*Emotional vector — chaos: {chaos_pct}%  dark: {dark_pct}%  "
        f"whimsy: {whimsy_pct}%*"
    )


def _gen_screenplay(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Screenplay — slug + action block + dialogue, tension from chaos/coherence ratio."""
    name    = oracle.get("hexagram_name", "The Unknown")
    symbol  = oracle.get("hexagram_symbol", "")
    action  = oracle.get("action", "ASSERT")
    phase   = oracle.get("phase_temporal", "present")
    cat     = oracle.get("category", "transformer")

    chaos     = mv.get("chaos",      0.0)
    coherence = mv.get("coherence",  0.0)
    dark      = mv.get("darkTone",   0.0)
    vw        = mv.get("voiceWeight",0.0)

    # Location tone driven by category
    loc_map = {"sovereign": "EXTERIOR", "boundary": "INTERIOR", "transformer": "EXTERIOR"}
    ext_int = loc_map.get(cat, "EXTERIOR")
    env     = "STORM — DUSK" if dark > 0.6 else "DAY — GOLDEN HOUR"
    if chaos > 0.7:
        env = "NIGHT — ELECTRICAL STORM"

    # Speaker A: protagonist when ASSERT, antagonist/other when YIELD
    role_a = _ACTION_ROLES.get(action, _ACTION_ROLES["ADAPT"])
    spk_a  = "PROTAGONIST" if role_a["protagonist"] else "ORACLE"
    spk_b  = "ORACLE"      if role_a["protagonist"] else "PROTAGONIST"

    # Dialogue tone
    if coherence > 0.7:
        line_a = f"This is not what I intended. {intent.rstrip('.').capitalize()}."
        line_b = "Intent is not outcome. The hexagram names the gap between them."
    elif chaos > 0.6:
        line_a = f"Everything is moving. {intent.rstrip('.').capitalize()} — even that."
        line_b = "Then stop naming it and let it move."
    else:
        line_a = f"{intent.rstrip('.').capitalize()} — that's all I know to say."
        line_b = f"That's enough.  {name} does not require more."

    return (
        f"{ext_int}. {name.upper()} — {env}\n\n"
        f"[{symbol}  HEXAGRAM {oracle.get('hexagram_id', '?')}  ·  {action}  ·  {phase.upper()}]\n\n"
        f"The scene is established.  Voice weight: {int(vw * 100)}%.  "
        f"Tension index: {int(chaos * 100)} / {int(coherence * 100)}.\n\n"
        f"{spk_a}\n  {line_a}\n\n"
        f"{spk_b}\n  {line_b}\n\n"
        f"[beat]\n\n"
        f"The {phase} holds.  The arc of {name} does not resolve here — it turns.\n\n"
        f"CUT TO BLACK."
    )


def _gen_dialogue(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Two-character exchange driven by voiceWeight and whimsy axes."""
    name   = oracle.get("hexagram_name", "The Unknown")
    symbol = oracle.get("hexagram_symbol", "")
    action = oracle.get("action", "ASSERT")

    vw     = mv.get("voiceWeight", 0.5)
    whimsy = mv.get("whimsy",      0.5)
    dark   = mv.get("darkTone",    0.0)

    # Voice weight maps to speaker confidence / dominance
    dom_speaker  = "A" if vw >= 0.5 else "B"
    sub_speaker  = "B" if dom_speaker == "A" else "A"

    # Whimsy controls lateral/unexpected responses
    lateral_response = whimsy > 0.6

    if action == "ASSERT":
        dom_line  = f"I'm saying {intent.rstrip('.')} is not a question."
        sub_line  = "Then why does it feel like one?" if lateral_response else "Understood."
    elif action == "YIELD":
        dom_line  = f"Maybe {intent.rstrip('.')} is what we don't control."
        sub_line  = "Or what we choose not to." if lateral_response else "That's one way to see it."
    else:
        dom_line  = f"{intent.rstrip('.').capitalize()}. Where does that leave us?"
        sub_line  = "Exactly where we needed to be." if not lateral_response else "Somewhere new, which was always the point."

    dark_note = f"\n\n[{sub_speaker} pauses — the silence has weight]" if dark > 0.5 else ""

    return (
        f"# Dialogue  {symbol} {name}  [{action}]\n\n"
        f"{dom_speaker}: {dom_line}\n\n"
        f"{sub_speaker}: {sub_line}{dark_note}\n\n"
        f"{dom_speaker}: {name}. That's the name of this moment, you know.\n\n"
        f"{sub_speaker}: {'I do.' if not lateral_response else 'Then let it be named.'}\n\n"
        f"*[Voice weight: {int(vw*100)}%  Whimsy: {int(whimsy*100)}%  "
        f"Dark: {int(dark*100)}%]*"
    )


def _gen_lyrics(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Song lyrics — verse/chorus/bridge, axes drive rhyme density, darkness, meter."""
    name   = oracle.get("hexagram_name", "The Unknown")
    symbol = oracle.get("hexagram_symbol", "")
    action = oracle.get("action", "ASSERT")
    cat    = oracle.get("category", "transformer")

    chaos   = mv.get("chaos",      0.5)
    whimsy  = mv.get("whimsy",     0.5)
    dark    = mv.get("darkTone",   0.0)
    coh     = mv.get("coherence",  0.5)

    # Rhyme density: whimsy drives it (high whimsy = dense rhyme)
    rhyme_label = "AABB" if whimsy > 0.7 else ("ABAB" if whimsy > 0.4 else "free verse")
    # Meter length: coherence drives line length (high coherence = longer lines)
    meter = "long-form" if coh > 0.7 else ("mid-form" if coh > 0.4 else "short-form")
    # Darkness affects subject matter
    dark_theme = "loss and shadow" if dark > 0.6 else ("tension and turning" if dark > 0.3 else "motion and becoming")

    core = intent.rstrip(".").strip()

    verse = (
        f"In the field of {core.lower()}\n"
        f"Where {name.lower()} holds the line\n"
        f"{'Every edge cuts both ways' if dark > 0.5 else 'Something waits to shine'}\n"
        f"{'Into the breaking dark' if dark > 0.5 else 'Into the unformed light'}"
    )
    chorus = (
        f"{symbol} {name.upper()}\n"
        f"The {action.lower()} in the bone\n"
        f"{'Carry the weight alone' if dark > 0.6 else 'No one walks this alone'}\n"
        f"{'Until the moment breaks' if chaos > 0.5 else 'Until the pattern shows'}"
    )
    bridge = (
        f"[{'BRIDGE — ' + cat.upper()}]\n"
        f"{'What we feared to name' if dark > 0.5 else 'What we barely named'}\n"
        f"Becomes the {'wound' if dark > 0.6 else 'word'} — becomes the frame"
    )

    return (
        f"# {symbol} {name}  [{action}]\n"
        f"*Rhyme: {rhyme_label}  ·  Meter: {meter}  ·  Theme: {dark_theme}*\n\n"
        f"[VERSE]\n{verse}\n\n"
        f"[CHORUS]\n{chorus}\n\n"
        f"[VERSE 2]\n"
        f"The {cat} does not wait\n"
        f"{'For permission to arrive' if coh > 0.5 else 'For grief to subside'}\n"
        f"{'It simply is the state' if coh > 0.5 else 'It comes in like a tide'}\n"
        f"{'That makes the pattern live' if coh > 0.5 else 'And does not choose a side'}\n\n"
        f"[CHORUS]\n{chorus}\n\n"
        f"{bridge}\n\n"
        f"[CHORUS — OUT]\n{chorus}"
    )


def _gen_image_prompt(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Stable Diffusion-style weighted prompt from hexagram + voice weight axes."""
    name   = oracle.get("hexagram_name", "The Unknown")
    symbol = oracle.get("hexagram_symbol", "")
    cat    = oracle.get("category", "transformer")
    action = oracle.get("action", "ASSERT")

    chaos   = mv.get("chaos",      0.0)
    whimsy  = mv.get("whimsy",     0.0)
    dark    = mv.get("darkTone",   0.0)
    coh     = mv.get("coherence",  0.5)
    vw      = mv.get("voiceWeight",0.5)

    aesth   = _CATEGORY_AESTHETICS.get(cat, _CATEGORY_AESTHETICS["transformer"])
    base_tags = aesth["sd_tag"]

    # Axis-driven modifiers
    style_tags: List[str] = [base_tags]
    if dark > 0.6:
        style_tags.append("chiaroscuro lighting, deep shadows, cinematic noir")
    elif dark > 0.3:
        style_tags.append("dramatic lighting, contrast-rich")

    if chaos > 0.6:
        style_tags.append("dynamic motion blur, fragmented composition, kinetic energy")
    elif chaos < 0.2:
        style_tags.append("perfectly still, serene atmosphere, crystalline clarity")

    if whimsy > 0.7:
        style_tags.append("surrealist elements, unexpected scale, dreamlike transitions")
    elif whimsy > 0.4:
        style_tags.append("subtle unexpected details, soft fantastical accents")

    if coh > 0.8:
        style_tags.append("hyper-detailed, 8K resolution, razor-sharp focus")

    action_tags = {
        "ASSERT":  "strong perspective, dominant foreground subject",
        "YIELD":   "wide open space, subject receding, environmental scale",
        "ADAPT":   "balanced composition, dual focal points",
        "OBSERVE": "observer POV, environmental immersion",
        "PERSIST": "enduring structures, geological scale, time-worn surfaces",
    }
    if action in action_tags:
        style_tags.append(action_tags[action])

    quality_tags = (
        f"masterpiece, best quality, intricate detail, "
        f"concept art, artstation trending, ({symbol} hexagram symbol:1.2)"
    )

    prompt = (
        f"{intent}, {', '.join(style_tags)}, {quality_tags}\n\n"
        f"**Negative prompt:** text, watermark, blurry, low quality, artifacts, "
        f"oversaturated, flat lighting, cartoon\n\n"
        f"*Hex: {symbol} {name}  ·  Action: {action}  ·  "
        f"CFG guidance hint: {round(7.0 + (coh - 0.5) * 4.0, 1)}  ·  "
        f"Voice weight: {int(vw*100)}%*"
    )
    return f"# Image Prompt  {symbol} {name}\n\n{prompt}"


def _gen_code(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Route to kingwen_narrative_generate in code_completion mode."""
    try:
        from openjarvis.tools.kingwen_narrative_dispatch_tool import _generate_narrative

        hex_id  = oracle.get("hexagram_id", 1)
        name    = oracle.get("hexagram_name", "")
        action  = oracle.get("action", "ASSERT")
        cat     = oracle.get("category", "transformer")
        phase   = oracle.get("phase_temporal", "present")

        output = _generate_narrative(
            oracle_state={
                "hexagram_id": hex_id,
                "hexagram_name": name,
                "action": action,
                "category": cat,
                "phase_temporal": phase,
                "emotional_deltas": mv,
            },
            intent_text=intent,
            mode="code_completion",
        )
        return output
    except Exception as exc:
        # Graceful fallback if _generate_narrative is not importable
        return (
            f"# Code Intent: {oracle.get('hexagram_name','Unknown')} [{oracle.get('action','')}]\n\n"
            f"```python\n"
            f"# Intent: {intent}\n"
            f"# Hexagram: {oracle.get('hexagram_id', '?')} — {oracle.get('hexagram_name','')}\n"
            f"# Coherence: {mv.get('coherence', 0.0):.3f}  Chaos: {mv.get('chaos', 0.0):.3f}\n"
            f"# Voice weight: {mv.get('voiceWeight', 0.0):.3f}\n"
            f"# TODO: implement '{intent}'\n"
            f"```\n\n"
            f"*(kingwen_narrative_generate unavailable: {exc})*"
        )


def _gen_essay(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Structured essay — thesis from ASSERT hex, counter from chaos anchors, synthesis from ADAPT."""
    name   = oracle.get("hexagram_name", "The Unknown")
    symbol = oracle.get("hexagram_symbol", "")
    action = oracle.get("action", "ASSERT")
    cat    = oracle.get("category", "transformer")
    phase  = oracle.get("phase_temporal", "present")

    coh   = mv.get("coherence",  0.5)
    chaos = mv.get("chaos",      0.5)
    dark  = mv.get("darkTone",   0.0)
    vw    = mv.get("voiceWeight",0.5)

    # Thesis strength from coherence
    thesis_strength = "conclusively" if coh > 0.7 else ("tentatively" if coh < 0.4 else "carefully")

    # Counter strength from chaos
    counter_weight = "deeply undermines" if chaos > 0.7 else ("partially challenges" if chaos > 0.4 else "gently questions")

    return (
        f"# Essay: {intent.capitalize()}\n"
        f"*{symbol} {name}  [{action}]  ·  Phase: {phase}  ·  Register: {cat}*\n\n"
        f"---\n\n"
        f"## Thesis\n\n"
        f"The claim can be stated {thesis_strength}: {intent.rstrip('.')}. "
        f"The {name} hexagram ({action}) positions this not as opinion but as the shape "
        f"of the current moment — a structural truth pressed into language by the "
        f"{'dominant coherence' if coh > 0.6 else 'distributed tension'} "
        f"of the present phase.\n\n"
        f"## Development\n\n"
        f"To hold this position requires understanding what it rests on. "
        f"The {cat} category imposes its own logic: {_CATEGORY_AESTHETICS.get(cat, {}).get('arc', 'unnamed arc')}. "
        f"Within this arc, every act of {action.lower()} carries the risk of "
        f"{'premature closure' if coh > 0.7 else 'unresolved dispersal'}.  "
        f"The essay's task is to move through that risk with awareness.\n\n"
        f"## Counter\n\n"
        f"One objection {counter_weight} the thesis: the degree to which "
        f"{'external disruption' if chaos > 0.5 else 'internal resistance'} "
        f"reframes what {intent.rstrip('.')} actually means in practice.  "
        f"{'If the field is dark enough' if dark > 0.5 else 'If the system is stable enough'}, "
        f"the thesis may be accurate as description while failing as prescription.\n\n"
        f"## Synthesis\n\n"
        f"The synthesis is not a compromise — it is the ADAPT function of the hexagram system.  "
        f"It accepts both positions as locally true and asks what the transition between them "
        f"reveals.  Voice weight at {int(vw*100)}% suggests the synthesis leans "
        f"{'toward assertion' if vw > 0.6 else 'toward inquiry'}.\n\n"
        f"---\n"
        f"*Coherence: {coh:.3f}  Chaos: {chaos:.3f}  Dark: {dark:.3f}*"
    )


def _gen_training_record(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """Produce a Megatron multi-domain JSONL record for downstream ingestion."""
    hex_id   = oracle.get("hexagram_id", 0)
    name     = oracle.get("hexagram_name", "")
    action   = oracle.get("action", "")
    cat      = oracle.get("category", "")
    phase    = oracle.get("phase_temporal", "")

    record = {
        "domain":           "kingwen_script_pipeline",
        "source":           "kingwen_script_pipeline_tool",
        "hexagram_id":      hex_id,
        "name":             name,
        "category":         cat,
        "action":           action,
        "construct":        f"hexagram::{hex_id}::{action}",
        "math":             (
            f"{name}: {cat} dominant={action}={phase} "
            f"porosity={oracle.get('consensus_porosity_mean', 'null')}"
        ),
        "emotional_weights": mv,
        "pattern_shape":    oracle.get("emotional_tongue", {}),
        "allowed_bridges":  ["kingwen_script_pipeline_to_megatron"],
        "source_domain":    "kingwen_script_pipeline",
        "intent_text":      intent,
        "phase_temporal":   phase,
    }
    json_str = json.dumps(record, ensure_ascii=False)
    return (
        f"# Training Record  [Hexagram {hex_id} — {name}]\n\n"
        f"*Format: Megatron multi-domain JSONL  ·  Bridge: kingwen_script_pipeline_to_megatron*\n\n"
        f"```json\n{json_str}\n```\n\n"
        f"*Record appended to ledger.*"
    )


def _gen_gutenberg(oracle: Dict[str, Any], mv: Dict[str, float], intent: str) -> str:
    """POG2-compatible Gutenberg mode.

    Scans the local rsmv corpus cache tables for an entry whose hex_id or
    emotional vector best matches the current oracle state, then returns the
    passage text decorated with hex metadata.

    Falls back gracefully if no cache is found.
    """
    from openjarvis.core.paths import get_kingwen_workspace_dir  # type: ignore[import]

    hex_id    = oracle.get("hexagram_id", 1)
    name      = oracle.get("hexagram_name", "")
    symbol    = oracle.get("hexagram_symbol", "")
    action    = oracle.get("action", "")
    coh       = mv.get("coherence", 0.5)

    workspace = get_kingwen_workspace_dir()
    cache_path = Path(workspace) / "kingwen_train_data" / "rsmv_live_cache_tables.json"

    if not cache_path.exists():
        return (
            f"# Gutenberg  {symbol} {name}  [{action}]\n\n"
            f"*(rsmv corpus cache not found at {cache_path})*\n\n"
            f"No passage located.  Intent: {intent}\n"
            f"Hexagram: {hex_id} — {name}  ·  Coherence: {coh:.3f}"
        )

    # The cache can be very large — stream it line by line if JSONL,
    # or parse top-level entries if JSON.
    best_passage: str = ""
    best_score:   float = -1.0

    try:
        raw = cache_path.read_bytes()
        # Try JSON object first (may be dict of lists)
        try:
            data = json.loads(raw)
            entries: List[Any] = []
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        entries.extend(v)
        except json.JSONDecodeError:
            # Try JSONL
            entries = []
            for line in raw.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            # Score by hex_id match + coherence proximity
            eid  = entry.get("hexagram_id") or entry.get("hex_id") or 0
            ecoh = float((entry.get("emotional_weights") or {}).get("coherence", 0.0) or 0.0)

            score = 0.0
            if int(eid) == int(hex_id):
                score += 1.0
            score += 1.0 - abs(ecoh - coh)

            if score > best_score:
                best_score = score
                text = entry.get("text") or entry.get("passage") or entry.get("content") or ""
                if text:
                    best_passage = str(text)[:800]

    except Exception as exc:
        LOGGER.warning("gutenberg cache read failed: %s", exc)

    if not best_passage:
        best_passage = (
            f"[No matching passage found in corpus cache for hex {hex_id}]"
        )

    return (
        f"# Gutenberg  {symbol} {name}  [{action}]\n\n"
        f"*POG2-compatible passage match  ·  Intent: {intent}*\n\n"
        f"---\n\n"
        f"{best_passage}\n\n"
        f"---\n\n"
        f"*Hexagram: {hex_id} — {name}  ·  Coherence match: {best_score:.3f}  "
        f"·  Action: {action}*"
    )


# ── Script dispatcher ─────────────────────────────────────────────────────────

_GENERATORS = {
    "prose":           _gen_prose,
    "screenplay":      _gen_screenplay,
    "dialogue":        _gen_dialogue,
    "lyrics":          _gen_lyrics,
    "image_prompt":    _gen_image_prompt,
    "code":            _gen_code,
    "essay":           _gen_essay,
    "training_record": _gen_training_record,
    "gutenberg":       _gen_gutenberg,
}


def _dispatch(oracle: Dict[str, Any], mv: Dict[str, float],
              script_type: str, intent: str) -> str:
    gen = _GENERATORS.get(script_type)
    if gen is None:
        return f"ERROR: unknown script_type '{script_type}'"
    return gen(oracle, mv, intent)


# ── Tool implementation ────────────────────────────────────────────────────────

class KingWenScriptPipelineTool(BaseTool):
    """Universal cognitive script pipeline — hexagram-led emotional state machine."""

    tool_id: str = _TOOL_ID

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=_TOOL_ID,
            description=(
                "Hexagram-led emotional state machine that generates any script type "
                "(prose, screenplay, dialogue, lyrics, image_prompt, code, essay, "
                "training_record, gutenberg) using mini quantum expansion on intent "
                "and voice weight modulation.  "
                "Parameters: intent (str), script_type (str), "
                "emotional_input (int 0-100, default 50), force_hex (int 1-64, optional), "
                "max_passes (int, default 3), voice_override (dict, optional)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "The raw creative intent or topic to generate from.",
                    },
                    "script_type": {
                        "type": "string",
                        "enum": sorted(SCRIPT_TYPES),
                        "description": "Target script type.",
                    },
                    "emotional_input": {
                        "type": "integer",
                        "description": "Emotional seed for quantum expansion (0-100, default 50).",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "force_hex": {
                        "type": "integer",
                        "description": "Skip quantum expansion and use a specific hexagram (1-64).",
                        "minimum": 1,
                        "maximum": 64,
                    },
                    "max_passes": {
                        "type": "integer",
                        "description": "Quantum expansion pass count (default 3).",
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "voice_override": {
                        "type": "object",
                        "description": (
                            "Override specific voice weight axes after modulation.  "
                            "Keys: chaos, whimsy, darkTone, coherence, voiceWeight (floats 0.0-1.0)."
                        ),
                    },
                },
                "required": ["intent", "script_type"],
            },
        )

    def execute(self, **params: Any) -> ToolResult:
        """BaseTool abstract method — delegates to run()."""
        return self.run(**params)

    def run(self, intent: str, script_type: str,
            emotional_input: int = 50,
            force_hex: Optional[int] = None,
            max_passes: int = 3,
            voice_override: Optional[Dict[str, float]] = None,
            **_: Any) -> ToolResult:

        if not intent:
            return _err("'intent' is required and cannot be empty")
        if script_type not in SCRIPT_TYPES:
            return _err(
                f"unknown script_type '{script_type}'.  "
                f"Valid: {', '.join(sorted(SCRIPT_TYPES))}"
            )

        t_start = time.monotonic()

        # ── 1. Quantum expansion or forced hex ────────────────────────────────
        try:
            if force_hex is not None:
                oracle = _force_hex_state(int(force_hex), int(emotional_input))
                expansion_mode = f"forced_hex={force_hex}"
            else:
                oracle = _quantum_expand(intent, int(emotional_input), int(max_passes))
                expansion_mode = f"quantum_passes={max_passes}"
        except Exception as exc:
            return _err(f"quantum expansion failed: {exc}")

        if not oracle:
            return _err("oracle returned empty state — check King Wen workspace")

        # ── 2. Voice weight modulation ─────────────────────────────────────────
        raw_vector   = _vec(oracle)
        modulated_v  = _modulate_full(raw_vector, script_type, voice_override, oracle, int(emotional_input))

        # ── 3. Generate output ─────────────────────────────────────────────────
        try:
            output = _dispatch(oracle, modulated_v, script_type, intent)
        except Exception as exc:
            LOGGER.exception("script generation failed for type=%s", script_type)
            return _err(f"generation failed: {exc}")

        elapsed = round(time.monotonic() - t_start, 3)

        # ── 4. Ledger append ───────────────────────────────────────────────────
        ledger_record: Dict[str, Any] = {
            "ts":             time.time(),
            "intent":         intent,
            "script_type":    script_type,
            "expansion_mode": expansion_mode,
            "hexagram_id":    oracle.get("hexagram_id"),
            "hexagram_name":  oracle.get("hexagram_name"),
            "hexagram_symbol":oracle.get("hexagram_symbol"),
            "action":         oracle.get("action"),
            "category":       oracle.get("category"),
            "phase_temporal": oracle.get("phase_temporal"),
            "raw_vector":      raw_vector,
            "modulated_vector": modulated_v,
            "emotional_input": emotional_input,
            "elapsed_s":       elapsed,
            "output_preview":  output[:200],
            "enrichment": {
                "inject_site": oracle.get("emotional_tongue", {}).get("porosity"),
                "yao_label":   oracle.get("consensus_yao", ""),
                "hex_binary":  None,  # filled below if HEXAGRAM_BASE available
            },
        }
        _append_ledger(ledger_record)

        metadata: Dict[str, Any] = {
            "hexagram_id":     oracle.get("hexagram_id"),
            "hexagram_name":   oracle.get("hexagram_name"),
            "hexagram_symbol": oracle.get("hexagram_symbol"),
            "action":          oracle.get("action"),
            "category":        oracle.get("category"),
            "phase_temporal":  oracle.get("phase_temporal"),
            "script_type":     script_type,
            "expansion_mode":  expansion_mode,
            "modulated_vector":modulated_v,
            "elapsed_s":       elapsed,
            "ledger":          str(_LEDGER_PATH),
        }
        return _ok(output, metadata)


# ── Registration ──────────────────────────────────────────────────────────────

def register(registry: ToolRegistry) -> None:
    """Register KingWenScriptPipelineTool with the tool registry."""
    registry.register(KingWenScriptPipelineTool())
