"""kingwen_model_select_tool.py — King Wen oracle-driven model selection for Jarvis.

Tools registered here:
  - kingwen_model_select : Select the optimal model from the Jarvis model catalog
                           based on King Wen hexagram state, temporal phase, and
                           emotional vector requirements.
  - kingwen_model_list   : List all models that match a hexagram category/action
                           constraint (e.g., "transit" → reasoning/MoE models).

Hexagram → Model Affinity Map:
  - Hex 1  (IDLE/Creative)          → high-creativity cloud models (Gemini Pro, Claude Opus)
  - Hex 2  (STEALTH/Receptive)      → small/fast local models (Qwen3 0.6B, Qwen3 1.7B)
  - Hex 8  (TRANSIT/Consensus)      → MoE models (Qwen3.5, DeepSeek MoE)
  - Hex 11 (TR_SALT/Peace)          → balanced midsize (Qwen3 8B, Gemma3 12B)
  - Hex 12 (TR_CRIT/Standstill)     → max-context reasoning (Gemini 2.5 Pro, Kimi K2)
  - Hex 29 (LIMP/Degraded)          → lowest-cost fast fallback (Gemini Flash, Qwen3 0.6B)
  - Hex 58 (PURGE/Reset)            → reset to default (user preference / env default)
  - Hex 52 (ST_CRIT/Hold)           → large local (Qwen3 32B, DeepSeek R2)
  - Other                           → balanced default (Qwen3 14B, Gemma3 27B)

No mock. Uses real ModelRegistry.list() to discover registered models.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from openjarvis.core.registry import ToolRegistry, ModelRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

def _ok(tool_id: str, output: str, metadata: dict = None) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=output, success=True, metadata=metadata or {})


def _err(tool_id: str, msg: str) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=f"ERROR: {msg}", success=False)


LOGGER = logging.getLogger(__name__)

# ── Hexagram model affinity profiles ─────────────────────────────────────────

# Each entry: (min_params_b, max_params_b, preferred_engines, preferred_providers, allow_cloud)
HEX_AFFINITY: Dict[int, Dict[str, Any]] = {
    1:  {"min_params": 20.0, "engines": ("cloud", "vllm"), "providers": ("google", "anthropic", "openai"), "cloud": True,  "arch": "proprietary",       "label": "creative"},
    2:  {"min_params": 0.0,  "max_params": 4.0,  "engines": ("ollama", "mlx", "lemonade"), "providers": ("alibaba", "google"), "cloud": False, "label": "stealth"},
    8:  {"min_params": 4.0,  "engines": ("ollama", "vllm", "sglang"), "providers": ("alibaba", "deepseek"), "cloud": False, "arch": "moe",              "label": "consensus"},
    11: {"min_params": 7.0,  "max_params": 15.0, "engines": ("ollama", "vllm"), "providers": ("alibaba", "google"), "cloud": False,                    "label": "balanced"},
    12: {"min_params": 0.0,  "engines": ("cloud",), "providers": ("google", "anthropic", "kimi"), "cloud": True,  "min_context": 500000,                "label": "deep_reasoning"},
    29: {"min_params": 0.0,  "max_params": 4.0,  "engines": ("cloud", "ollama", "mlx"), "providers": ("google",), "cloud": True,                       "label": "minimal"},
    58: {"min_params": 0.0,  "engines": (),       "providers": (),                     "cloud": None,                                                   "label": "reset"},
    52: {"min_params": 28.0, "engines": ("ollama", "vllm"), "providers": ("alibaba", "deepseek", "qwen"), "cloud": False,                              "label": "deep_local"},
}

DEFAULT_AFFINITY: Dict[str, Any] = {
    "min_params": 12.0, "max_params": 35.0, "engines": ("ollama", "vllm", "cloud"),
    "providers": ("alibaba", "google", "meta"), "cloud": True, "label": "default",
}


def _score_model(spec: Any, affinity: Dict[str, Any], chaos: float, coherence: float) -> float:
    """Score a ModelSpec against a hexagram affinity profile. Higher = better."""
    score = 0.0

    params = float(getattr(spec, "parameter_count_b", 0.0) or 0.0)
    engines = tuple(getattr(spec, "supported_engines", ()) or ())
    provider = str(getattr(spec, "provider", "") or "")
    ctx = int(getattr(spec, "context_length", 0) or 0)
    requires_key = bool(getattr(spec, "requires_api_key", False))
    arch = str((getattr(spec, "metadata", None) or {}).get("architecture", "") or "")

    min_p = affinity.get("min_params", 0.0)
    max_p = affinity.get("max_params", 999.0)
    pref_engines = affinity.get("engines", ())
    pref_providers = affinity.get("providers", ())
    cloud_ok = affinity.get("cloud", True)
    min_ctx = affinity.get("min_context", 0)
    pref_arch = affinity.get("arch", "")

    # Param range bonus
    if min_p <= params <= max_p:
        score += 3.0
    elif params >= min_p:
        score += 1.0

    # Engine match
    if any(e in engines for e in pref_engines):
        score += 2.0

    # Provider match
    if provider in pref_providers:
        score += 2.0

    # Cloud suitability
    if cloud_ok is True and requires_key:
        score += 1.0
    elif cloud_ok is False and not requires_key:
        score += 1.5

    # Context requirement
    if ctx >= min_ctx:
        score += 1.0

    # Architecture bonus
    if pref_arch and arch == pref_arch:
        score += 1.5

    # Chaos factor: high chaos boosts larger models (more capable deliberation)
    score += chaos * (params / max(params, 70.0))

    # Coherence factor: high coherence boosts smaller/faster models
    if params > 0 and coherence > 0.6:
        score -= (params - min_p) / max(max_p - min_p, 1.0) * coherence * 0.5

    return round(score, 4)


def select_model_for_hex(
    hexagram_id: int,
    chaos: float = 0.5,
    coherence: float = 0.5,
    preferred_engine: Optional[str] = None,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """Return top_n scored model candidates for the given hexagram state."""
    affinity = HEX_AFFINITY.get(hexagram_id, DEFAULT_AFFINITY)

    # Hex 58 = purge/reset: return env default signal
    if hexagram_id == 58:
        return [{"model_id": "__env_default__", "label": "reset", "score": 0.0, "reason": "Hex 58 purge — reset to default model"}]

    try:
        from openjarvis.intelligence.model_catalog import BUILTIN_MODELS
        candidates = BUILTIN_MODELS
    except Exception:
        return [{"model_id": "__fallback__", "label": "fallback", "score": 0.0, "reason": "ModelRegistry unavailable"}]

    scored: List[Tuple[float, Any]] = []
    for spec in candidates:
        if preferred_engine:
            engines = tuple(getattr(spec, "supported_engines", ()) or ())
            if preferred_engine not in engines:
                continue
        s = _score_model(spec, affinity, chaos, coherence)
        scored.append((s, spec))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "model_id": getattr(s, "model_id", ""),
            "name": getattr(s, "name", ""),
            "provider": getattr(s, "provider", ""),
            "parameter_count_b": getattr(s, "parameter_count_b", 0.0),
            "context_length": getattr(s, "context_length", 0),
            "supported_engines": list(getattr(s, "supported_engines", ())),
            "requires_api_key": getattr(s, "requires_api_key", False),
            "architecture": (getattr(s, "metadata", None) or {}).get("architecture", ""),
            "score": score,
            "affinity_label": affinity.get("label", "default"),
        }
        for score, s in scored[:top_n]
    ]


# ── Tool: Oracle Model Select ─────────────────────────────────────────────────

@ToolRegistry.register("kingwen_model_select")
class KingWenModelSelectTool(BaseTool):
    """Select the optimal LLM from the Jarvis model catalog driven by King Wen hexagram state."""

    tool_id = "kingwen_model_select"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_model_select",
            description=(
                "Selects the best matching LLM from the Jarvis model catalog based on the "
                "current King Wen hexagram state, temporal phase, and emotional vector weights. "
                "Returns a ranked list of candidates with scores, engine support, and reasoning. "
                "Hex 1 = creative cloud, Hex 2 = fast local, Hex 8 = MoE consensus, "
                "Hex 11 = balanced, Hex 12 = deep reasoning, Hex 29 = minimal fallback, "
                "Hex 52 = deep local, Hex 58 = purge/reset to default."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "hexagram_id": {
                        "type": "integer",
                        "description": "King Wen Hexagram ID (1–64) from oracle consult.",
                    },
                    "chaos": {
                        "type": "number",
                        "description": "Chaos emotional vector weight [0–1]. High = prefer more capable models.",
                        "default": 0.5,
                    },
                    "coherence": {
                        "type": "number",
                        "description": "Coherence emotional vector weight [0–1]. High = prefer faster smaller models.",
                        "default": 0.5,
                    },
                    "preferred_engine": {
                        "type": "string",
                        "description": "Filter by engine: 'ollama', 'vllm', 'cloud', 'mlx', 'llamacpp', etc. Empty = all.",
                        "default": "",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top candidates to return.",
                        "default": 3,
                    },
                },
                "required": ["hexagram_id"],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        hex_id = int(params.get("hexagram_id", 1))
        chaos = float(params.get("chaos", 0.5))
        coherence = float(params.get("coherence", 0.5))
        engine = str(params.get("preferred_engine", "")).strip() or None
        top_n = int(params.get("top_n", 3))

        try:
            candidates = select_model_for_hex(hex_id, chaos, coherence, engine, top_n)
            top = candidates[0] if candidates else {}
            return _ok(self.tool_id, f"Hex #{hex_id} → best model: {top.get('name', top.get('model_id', 'none'))} (score {top.get('score', 0):.2f})", {'hexagram_id': hex_id, 'candidates': candidates, 'affinity_label': HEX_AFFINITY.get(hex_id, DEFAULT_AFFINITY).get('label', 'default'), 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_model_select failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Model List by Category ─────────────────────────────────────────────

@ToolRegistry.register("kingwen_model_list")
class KingWenModelListTool(BaseTool):
    """List Jarvis model catalog entries matching a hexagram category label or engine filter."""

    tool_id = "kingwen_model_list"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_model_list",
            description=(
                "Lists all models from the Jarvis model catalog that match a given King Wen "
                "affinity label (creative/stealth/consensus/balanced/deep_reasoning/minimal/deep_local/default) "
                "or engine filter. Returns model IDs, sizes, providers, and context lengths."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "affinity_label": {
                        "type": "string",
                        "description": "Hexagram affinity label: creative, stealth, consensus, balanced, deep_reasoning, minimal, deep_local, default.",
                        "default": "default",
                    },
                    "engine": {
                        "type": "string",
                        "description": "Filter by engine: 'ollama', 'vllm', 'cloud', 'mlx', 'llamacpp'. Empty = all.",
                        "default": "",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return.",
                        "default": 20,
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        label = str(params.get("affinity_label", "default")).lower().strip()
        engine = str(params.get("engine", "")).strip()
        max_results = int(params.get("max_results", 20))

        try:
            from openjarvis.intelligence.model_catalog import BUILTIN_MODELS

            # Reverse-map label to hexagram
            hex_for_label = {v.get("label"): k for k, v in HEX_AFFINITY.items()}
            hex_id = hex_for_label.get(label, 0)
            affinity = HEX_AFFINITY.get(hex_id, DEFAULT_AFFINITY) if hex_id else DEFAULT_AFFINITY

            results = []
            for spec in BUILTIN_MODELS:
                engines = tuple(getattr(spec, "supported_engines", ()) or ())
                if engine and engine not in engines:
                    continue
                if affinity.get("engines") and not any(e in engines for e in affinity["engines"]):
                    if label not in ("default", ""):
                        continue
                results.append({
                    "model_id": getattr(spec, "model_id", ""),
                    "name": getattr(spec, "name", ""),
                    "provider": getattr(spec, "provider", ""),
                    "parameter_count_b": getattr(spec, "parameter_count_b", 0.0),
                    "context_length": getattr(spec, "context_length", 0),
                    "engines": list(engines),
                    "requires_api_key": getattr(spec, "requires_api_key", False),
                    "architecture": (getattr(spec, "metadata", None) or {}).get("architecture", ""),
                })
                if len(results) >= max_results:
                    break

            return _ok(self.tool_id, f"Found {len(results)} models for affinity '{label}'", {'models': results, 'affinity_label': label, 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_model_list failed")
            return _err(self.tool_id, str(exc))
