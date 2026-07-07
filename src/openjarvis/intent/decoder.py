"""
JARVIS Intent Decoder — King Wen → Tool Selection
===================================================
Translates the full 4-space King Wen oracle output into ranked
JARVIS tool usages. This is the "quantum collapse" from ambiguous
user intent into concrete actionable choices.

The 4 spaces:
  1. YIN / YANG / YAO space  — what TYPE of action is called for
  2. TEMPORAL space           — WHEN to act (past=recall, present=execute, future=plan)
  3. VECTOR space             — HOW to weight tool parameters (chaos, coherence, voiceWeight, etc)
  4. HEXAGRAM space           — WHAT domain/archetype the action belongs to

Each resolved oracle state produces a ranked list of tool slots:
  [
    {
      "tool": "web_search",
      "confidence": 0.87,
      "params": {"mode": "exploratory", "depth": "deep"},
      "rationale": "high whimsy + future temporal → research before acting",
      "yao_driver": "new_yang"
    },
    ...
  ]

Usage:
    from openjarvis.intent.decoder import decode_intent
    slots = decode_intent(oracle_result, user_text)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# King Wen path
# ---------------------------------------------------------------------------
KING_WEN_PATH = Path(__file__).resolve().parents[4] / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
sys.path.insert(0, str(KING_WEN_PATH))

try:
    from emotional_engine import expand_hexagram, sample_resolve
    KING_WEN_AVAILABLE = True
except ImportError:
    KING_WEN_AVAILABLE = False

# ---------------------------------------------------------------------------
# Tool registry — maps JARVIS tool filenames to semantic tags
# ---------------------------------------------------------------------------
# Tags: search | memory | execute | write | read | speak | think |
#       browse | transform | schedule | delegate | sense

TOOL_REGISTRY: List[Dict[str, Any]] = [
    # --- Active / execution tools ---
    {"tool": "shell_exec",          "tags": {"execute", "transform"},     "yin_yang": "yang",  "weight": 1.0},
    {"tool": "repl",                "tags": {"execute", "transform"},     "yin_yang": "yang",  "weight": 0.9},
    {"tool": "code_interpreter",    "tags": {"execute", "transform"},     "yin_yang": "yang",  "weight": 0.9},
    {"tool": "apply_patch",         "tags": {"write", "transform"},       "yin_yang": "yang",  "weight": 0.85},
    {"tool": "git_tool",            "tags": {"write", "execute"},         "yin_yang": "yang",  "weight": 0.8},
    {"tool": "docker_shell_exec",   "tags": {"execute"},                  "yin_yang": "yang",  "weight": 0.75},

    # --- Search / retrieval tools ---
    {"tool": "web_search",          "tags": {"search", "read"},           "yin_yang": "yin",   "weight": 1.0},
    {"tool": "knowledge_search",    "tags": {"search", "memory", "read"}, "yin_yang": "yin",   "weight": 0.95},
    {"tool": "retrieval",           "tags": {"memory", "read"},           "yin_yang": "yin",   "weight": 0.9},
    {"tool": "knowledge_sql",       "tags": {"search", "read"},           "yin_yang": "yin",   "weight": 0.85},
    {"tool": "db_query",            "tags": {"search", "read"},           "yin_yang": "yin",   "weight": 0.8},
    {"tool": "digest_collect",      "tags": {"search", "sense"},          "yin_yang": "yin",   "weight": 0.8},

    # --- File I/O tools ---
    {"tool": "file_read",           "tags": {"read", "memory"},           "yin_yang": "yin",   "weight": 0.85},
    {"tool": "file_write",          "tags": {"write"},                    "yin_yang": "yang",  "weight": 0.85},
    {"tool": "pdf_tool",            "tags": {"read"},                     "yin_yang": "yin",   "weight": 0.75},
    {"tool": "scan_chunks",         "tags": {"read", "sense"},            "yin_yang": "yin",   "weight": 0.7},
    {"tool": "storage_tools",       "tags": {"read", "write", "memory"},  "yin_yang": "yao",   "weight": 0.75},

    # --- Communication / output tools ---
    {"tool": "text_to_speech",      "tags": {"speak"},                    "yin_yang": "yang",  "weight": 0.9},
    {"tool": "audio_tool",          "tags": {"speak", "sense"},           "yin_yang": "yao",   "weight": 0.8},
    {"tool": "image_tool",          "tags": {"sense", "transform"},       "yin_yang": "yao",   "weight": 0.75},
    {"tool": "http_request",        "tags": {"execute", "search"},        "yin_yang": "yang",  "weight": 0.85},
    {"tool": "channel_tools",       "tags": {"delegate", "speak"},        "yin_yang": "yang",  "weight": 0.8},

    # --- Cognitive / meta tools ---
    {"tool": "think",               "tags": {"think"},                    "yin_yang": "yin",   "weight": 1.0},
    {"tool": "llm_tool",            "tags": {"think", "transform"},       "yin_yang": "yao",   "weight": 0.9},
    {"tool": "calculator",          "tags": {"think", "execute"},         "yin_yang": "yang",  "weight": 0.7},
    {"tool": "browser",             "tags": {"browse", "search"},         "yin_yang": "yin",   "weight": 0.85},
    {"tool": "browser_axtree",      "tags": {"browse", "sense"},          "yin_yang": "yin",   "weight": 0.7},

    # --- Memory / profile tools ---
    {"tool": "memory_manage",       "tags": {"memory", "write", "read"},  "yin_yang": "yao",   "weight": 0.9},
    {"tool": "user_profile_manage", "tags": {"memory", "read"},           "yin_yang": "yin",   "weight": 0.8},
    {"tool": "knowledge_tools",     "tags": {"memory", "search"},         "yin_yang": "yin",   "weight": 0.85},
    {"tool": "approval_store",      "tags": {"memory", "think"},          "yin_yang": "yin",   "weight": 0.7},

    # --- Scheduling / delegation tools ---
    {"tool": "proactive_tools",     "tags": {"schedule", "sense"},        "yin_yang": "yao",   "weight": 0.85},
    {"tool": "skill_manage",        "tags": {"delegate", "transform"},    "yin_yang": "yao",   "weight": 0.8},
    {"tool": "mcp_adapter",         "tags": {"delegate", "execute"},      "yin_yang": "yao",   "weight": 0.75},
]


# ---------------------------------------------------------------------------
# Yao → tool bias map
# "changing lines" tell us which dimension of a tool to emphasize
# ---------------------------------------------------------------------------
YAO_TOOL_BIAS: Dict[str, Dict[str, float]] = {
    # Past-facing yao states → memory and recall emphasis
    "old_yin":     {"memory": 1.4, "read": 1.2, "think": 1.1},
    "old_yang":    {"execute": 1.3, "write": 1.2, "search": 1.1},
    "old_yao":     {"transform": 1.4, "memory": 1.2, "delegate": 1.1},

    # Present-stable states → balanced
    "stable_yin":  {"read": 1.2, "think": 1.2, "memory": 1.1},
    "stable_yang": {"execute": 1.2, "search": 1.1, "browse": 1.1},
    "stable_yao":  {"transform": 1.2, "delegate": 1.1, "speak": 1.1},

    # Future / new states → proactive, scheduled, exploratory
    "young_yin":   {"search": 1.3, "browse": 1.2, "sense": 1.2},
    "new_yang":    {"execute": 1.4, "schedule": 1.3, "delegate": 1.2},
    "new_yao":     {"delegate": 1.4, "schedule": 1.3, "transform": 1.2},
}

# ---------------------------------------------------------------------------
# Temporal phase → urgency + tool class bias
# ---------------------------------------------------------------------------
TEMPORAL_BIAS: Dict[str, Dict[str, Any]] = {
    "past":           {"urgency": 0.3, "bias_tags": {"memory", "read"},          "avoid_tags": {"schedule", "delegate"}},
    "present":        {"urgency": 0.8, "bias_tags": {"execute", "speak"},        "avoid_tags": set()},
    "future":         {"urgency": 0.4, "bias_tags": {"schedule", "search"},      "avoid_tags": {"execute"}},
    "transition":     {"urgency": 0.6, "bias_tags": {"transform", "think"},      "avoid_tags": set()},
    "resolution":     {"urgency": 0.7, "bias_tags": {"write", "speak"},          "avoid_tags": {"browse"}},
    "dissolution":    {"urgency": 0.5, "bias_tags": {"think", "memory"},         "avoid_tags": {"execute"}},
    "crystallization":{"urgency": 0.9, "bias_tags": {"write", "execute"},        "avoid_tags": {"browse", "search"}},
    "void":           {"urgency": 0.1, "bias_tags": {"think"},                   "avoid_tags": {"execute", "speak"}},
}

# ---------------------------------------------------------------------------
# Hexagram action → tool verb class
# ASSERT  = high-confidence execution
# YIELD   = receptive / retrieval
# WAIT    = cognitive hold — think/sense before acting
# ADAPT   = transform + delegate
# ---------------------------------------------------------------------------
ACTION_BIAS: Dict[str, Dict[str, float]] = {
    "ASSERT": {"execute": 1.5, "write": 1.3, "speak": 1.2, "search": 0.8, "think": 0.7},
    "YIELD":  {"read": 1.5, "memory": 1.4, "search": 1.3, "think": 1.2, "execute": 0.6},
    "WAIT":   {"think": 1.5, "sense": 1.4, "memory": 1.2, "read": 1.1, "execute": 0.4},
    "ADAPT":  {"transform": 1.5, "delegate": 1.4, "search": 1.2, "execute": 1.0, "think": 1.1},
}

# ---------------------------------------------------------------------------
# Vector → tool parameter shaping
# Maps the 5 emotional dimensions to tool call parameters
# ---------------------------------------------------------------------------

def _vector_to_params(vector: Dict[str, float], tool: str) -> Dict[str, Any]:
    """Translate the resolved emotional vector into tool-call parameters."""
    chaos     = vector.get("chaos", 0.5)
    whimsy    = vector.get("whimsy", 0.5)
    dark_tone = vector.get("darkTone", 0.5)
    coherence = vector.get("coherence", 0.5)
    voice     = vector.get("voiceWeight", 0.5)

    params: Dict[str, Any] = {}

    if tool in ("web_search", "knowledge_search", "browser"):
        params["mode"] = "exploratory" if whimsy > 0.6 else "focused"
        params["depth"] = "deep" if coherence > 0.7 else "quick"
        params["safe"] = dark_tone < 0.4

    elif tool in ("shell_exec", "repl", "code_interpreter"):
        params["timeout"] = 30 if chaos < 0.4 else 10  # lower chaos = more patience
        params["safe_mode"] = dark_tone > 0.5
        params["verbose"] = voice > 0.7

    elif tool in ("text_to_speech", "audio_tool"):
        params["speed"] = 1.0 + (voice - 0.5) * 0.4   # voiceWeight scales speed
        params["tone"] = "warm" if whimsy > 0.5 else ("stern" if dark_tone > 0.5 else "neutral")
        params["volume"] = min(1.0, 0.6 + voice * 0.4)

    elif tool in ("llm_tool", "think"):
        params["temperature"] = round(0.3 + chaos * 0.7, 2)  # chaos → temperature
        params["max_tokens"] = 512 if coherence > 0.7 else 1024
        params["system_prompt_weight"] = round(coherence, 2)

    elif tool in ("memory_manage", "knowledge_tools", "retrieval"):
        params["recency_bias"] = 1.0 - dark_tone  # dark = focus on old memories
        params["confidence_threshold"] = round(coherence * 0.8, 2)

    elif tool in ("proactive_tools", "skill_manage"):
        params["priority"] = "high" if voice > 0.75 else "normal"
        params["schedule_window"] = "immediate" if chaos > 0.6 else "deferred"

    elif tool in ("file_read", "file_write", "apply_patch"):
        params["overwrite_guard"] = dark_tone > 0.4
        params["validate"] = coherence > 0.6

    return params


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------

def _score_tool(
    tool_entry: Dict[str, Any],
    action: str,
    temporal: str,
    vector: Dict[str, float],
    dominant_yao: Optional[str],
    porosity: float,
) -> float:
    """Score a single tool entry against the oracle state. Returns 0.0–1.0."""

    tags = tool_entry["tags"]
    yin_yang = tool_entry["yin_yang"]
    base_weight = tool_entry["weight"]

    score = base_weight

    # 1. Action bias
    action_biases = ACTION_BIAS.get(action, {})
    for tag in tags:
        score *= action_biases.get(tag, 1.0)

    # 2. Temporal bias
    temporal_meta = TEMPORAL_BIAS.get(temporal, {"urgency": 0.5, "bias_tags": set(), "avoid_tags": set()})
    bias_tags = temporal_meta["bias_tags"]
    avoid_tags = temporal_meta["avoid_tags"]

    if tags & bias_tags:
        score *= 1.3
    if tags & avoid_tags:
        score *= 0.4

    # 3. Yao changing-line bias
    if dominant_yao:
        yao_biases = YAO_TOOL_BIAS.get(dominant_yao, {})
        for tag in tags:
            score *= yao_biases.get(tag, 1.0)

    # 4. Yin/Yang alignment
    # yang action + yang tool = amplified; mismatch = damped
    action_polarity = "yang" if action in ("ASSERT",) else ("yin" if action in ("YIELD", "WAIT") else "yao")
    if yin_yang == action_polarity:
        score *= 1.2
    elif yin_yang == "yao":
        score *= 1.05  # yao tools are always somewhat useful (transformative)
    else:
        score *= 0.85

    # 5. Vector modulation
    chaos     = vector.get("chaos", 0.5)
    coherence = vector.get("coherence", 0.5)
    voice     = vector.get("voiceWeight", 0.5)
    whimsy    = vector.get("whimsy", 0.5)
    dark      = vector.get("darkTone", 0.5)

    # High coherence boosts execute/write; high chaos boosts search/browse
    if "execute" in tags or "write" in tags:
        score *= (0.6 + coherence * 0.8)
    if "search" in tags or "browse" in tags:
        score *= (0.5 + whimsy * 0.8 + chaos * 0.4)
    if "speak" in tags:
        score *= (0.4 + voice * 1.2)
    if "think" in tags:
        score *= (0.5 + (1.0 - chaos) * 0.8)
    if "schedule" in tags:
        score *= (0.4 + (1.0 - chaos) * 0.6)

    # High porosity = the Oracle is uncertain = prefer thinking tools over executing
    if porosity > 0.7:
        if "think" in tags or "search" in tags:
            score *= (1.0 + (porosity - 0.7) * 1.5)
        if "execute" in tags:
            score *= (1.0 - (porosity - 0.7) * 0.8)

    # 6. Urgency modulation from temporal
    urgency = temporal_meta["urgency"]
    # Low urgency = prefer slow/careful tools; high urgency = prefer fast tools
    if urgency > 0.7 and {"schedule", "delegate"} & tags:
        score *= 1.2
    if urgency < 0.3 and "execute" in tags:
        score *= 0.7

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Dominant yao extractor — finds the most significant changing line
# ---------------------------------------------------------------------------

def _dominant_yao(line_states: List[Dict[str, Any]]) -> Optional[str]:
    """Pick the dominant yao key from the resolved line states (highest position old_ line)."""
    changing = [ls for ls in line_states if str(ls.get("yao_key", "")).startswith("old_")]
    if not changing:
        # Fall back to any non-stable line
        non_stable = [ls for ls in line_states if "stable" not in str(ls.get("yao_key", ""))]
        if non_stable:
            return str(non_stable[-1].get("yao_key", "stable_yang"))
        return None
    # Highest position = most present/future-facing
    best = max(changing, key=lambda ls: int(ls.get("position", 0)))
    return str(best.get("yao_key", "old_yao"))


# ---------------------------------------------------------------------------
# Intent rationale builder
# ---------------------------------------------------------------------------

def _rationale(tool: str, tags: set, action: str, temporal: str, dominant_yao: Optional[str], porosity: float) -> str:
    parts = []
    if "execute" in tags and action == "ASSERT":
        parts.append("ASSERT action → direct execution")
    if "search" in tags or "browse" in tags:
        parts.append(f"{temporal} temporal → gather before acting")
    if "think" in tags and porosity > 0.6:
        parts.append(f"porosity={porosity:.2f} → Oracle uncertain, think first")
    if "speak" in tags:
        parts.append("voice channel required")
    if "memory" in tags and temporal == "past":
        parts.append("past temporal → retrieve from memory")
    if "schedule" in tags and temporal == "future":
        parts.append("future temporal → schedule for later")
    if dominant_yao:
        parts.append(f"yao driver: {dominant_yao}")
    return "; ".join(parts) if parts else f"oracle-weighted ({action}/{temporal})"


# ---------------------------------------------------------------------------
# Main decode function
# ---------------------------------------------------------------------------

def decode_intent(
    oracle_result: Dict[str, Any],
    user_text: str = "",
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Translate a full oracle result (from sample_resolve or oracle_bridge)
    into a ranked list of JARVIS tool slots.

    Args:
        oracle_result: the dict returned by sample_resolve() or oracle_bridge.consult()
        user_text:     the raw user utterance (used for keyword boosts)
        top_n:         how many tools to return

    Returns:
        List of dicts, each with keys:
          tool, confidence, params, rationale, yao_driver, tags, yin_yang
    """
    # Extract oracle state
    hexagram_id  = oracle_result.get("hexagram_id", 1)
    action       = oracle_result.get("hexagram_action") or oracle_result.get("hexagram_symbols", {}).get("action", "ADAPT")
    temporal     = oracle_result.get("temporal") or oracle_result.get("phase_temporal", "present")
    porosity     = float(oracle_result.get("porosity_ratio") or oracle_result.get("inject_site", {}).get("porosity", 0.35) or 0.35)
    vector       = oracle_result.get("resolved_vector") or oracle_result.get("expanded_vector") or {}
    line_states  = oracle_result.get("line_states", [])

    dominant_yao = _dominant_yao(line_states)

    # Keyword boost: scan user_text for direct tool hints
    keyword_boosts: Dict[str, float] = {}
    text_lower = user_text.lower()
    if any(k in text_lower for k in ("search", "find", "look", "google", "browse")):
        keyword_boosts["web_search"] = 1.4
        keyword_boosts["browser"] = 1.3
        keyword_boosts["knowledge_search"] = 1.3
    if any(k in text_lower for k in ("run", "execute", "shell", "command", "script")):
        keyword_boosts["shell_exec"] = 1.5
        keyword_boosts["repl"] = 1.4
    if any(k in text_lower for k in ("write", "create", "save", "file")):
        keyword_boosts["file_write"] = 1.4
        keyword_boosts["apply_patch"] = 1.3
    if any(k in text_lower for k in ("remember", "recall", "memory", "history")):
        keyword_boosts["memory_manage"] = 1.5
        keyword_boosts["knowledge_search"] = 1.4
        keyword_boosts["retrieval"] = 1.4
    if any(k in text_lower for k in ("say", "speak", "voice", "tts", "aloud")):
        keyword_boosts["text_to_speech"] = 1.6
    if any(k in text_lower for k in ("think", "reason", "plan", "consider")):
        keyword_boosts["think"] = 1.5
        keyword_boosts["llm_tool"] = 1.3
    if any(k in text_lower for k in ("schedule", "remind", "later", "cron")):
        keyword_boosts["proactive_tools"] = 1.5

    # Score all tools
    scored: List[Dict[str, Any]] = []
    for entry in TOOL_REGISTRY:
        tool_name = entry["tool"]
        raw_score = _score_tool(entry, action, temporal, vector, dominant_yao, porosity)
        # Apply keyword boost
        raw_score *= keyword_boosts.get(tool_name, 1.0)
        confidence = round(min(1.0, raw_score), 4)

        scored.append({
            "tool":        tool_name,
            "confidence":  confidence,
            "params":      _vector_to_params(vector, tool_name),
            "rationale":   _rationale(tool_name, entry["tags"], action, temporal, dominant_yao, porosity),
            "yao_driver":  dominant_yao,
            "tags":        sorted(entry["tags"]),
            "yin_yang":    entry["yin_yang"],
        })

    # Sort by confidence descending
    scored.sort(key=lambda x: x["confidence"], reverse=True)

    return scored[:top_n]


# ---------------------------------------------------------------------------
# Convenience: decode directly from hexagram_id + emotional_input
# ---------------------------------------------------------------------------

def decode_from_hexagram(
    hexagram_id: int,
    emotional_input: int = 50,
    phase_bits: int = 0,
    user_text: str = "",
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Shortcut: resolve hexagram via King Wen engine then decode intent."""
    if not KING_WEN_AVAILABLE:
        return [{"error": "King Wen engine not available"}]
    result = sample_resolve(hexagram_id, phase_bits=phase_bits, emotional_input=emotional_input)
    return decode_intent(result, user_text=user_text, top_n=top_n)


if __name__ == "__main__":
    import json, argparse, time

    # Quick self-test using today's temporal hexagram
    sys.path.insert(0, str(KING_WEN_PATH))
    from emotional_engine import sample_resolve as _sr

    import random
    random.seed(int(time.time()))
    hex_id = random.randint(1, 64)
    phase  = int(time.time()) % 8

    print(f"\n=== JARVIS Intent Decoder — Hexagram {hex_id}, Phase {phase} ===\n")
    oracle = _sr(hex_id, phase_bits=phase, emotional_input=65)
    slots  = decode_intent(oracle, user_text="", top_n=7)

    for i, slot in enumerate(slots, 1):
        print(f"  #{i}  [{slot['confidence']:.3f}]  {slot['tool']:<26}  "
              f"{slot['yin_yang']:<5}  {slot['rationale']}")

    print(f"\n  Oracle: {oracle.get('hexagram_symbols',{}).get('name')} | "
          f"Action: {oracle.get('hexagram_symbols',{}).get('action')} | "
          f"Temporal: {oracle.get('phase_temporal')} | "
          f"Yao: {slots[0].get('yao_driver')}")
