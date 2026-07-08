"""King Wen engine adapter — direct import path from the immutable tables repo.

Upgrade path:
  C:\\Users\\krist\\Desktop\\KING-WEN-I-CHING-IMMUTABLE-TABLES
      → src/openjarvis/emotion/kingwen_engine_adapter.py
      → kingwen_dashboard.py / _cmd_models / _oracle_speak / jarvis-router

Exposes:
  - expand_hexagram(...)
  - sample_resolve(...)
  - collapse_full_128(emotional_input)
  - consensus_from_resolved(...)
  - temporal_shift(temporal, vector)

No POG2/rsmv dependency.
No mock/stub/placeholder. Real imports from the source-of-truth repo.
"""

from __future__ import annotations

from importlib.util import spec_from_file_location, module_from_spec
import os
import sys
from typing import Any, Dict, List, Tuple

# ─── Source-of-truth path ─────────────────────────────────────────────────────
_KINGWEN_TABLES_DIR = os.environ.get(
    "KING_WEN_IMMUTABLE_TABLES",
    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES",
)
_KINGWEN_TERNARY_PATH = os.path.join(_KINGWEN_TABLES_DIR, "kingwen_ternary_tables_complete.py")
_EMOTIONAL_ENGINE_PATH = os.path.join(_KINGWEN_TABLES_DIR, "emotional_engine.py")
_TEMPORAL_ENGINE_PATH = os.path.join(_KINGWEN_TABLES_DIR, "temporal_emotional_engine.py")

# ─── Load immutable ternary module directly ───────────────────────────────────
_TernarySpec = spec_from_file_location("kingwen_ternary_tables_complete", _KINGWEN_TERNARY_PATH)
if _TernarySpec is None or _TernarySpec.loader is None:
    raise ImportError(f"Cannot load King Wen immutable tables from {_KINGWEN_TERNARY_PATH}")
_TernaryModule = module_from_spec(_TernarySpec)
sys.modules["kingwen_ternary_tables_complete"] = _TernaryModule
_TernarySpec.loader.exec_module(_TernaryModule)

# Re-export immutable names so callers don't need to touch the raw module.
from kingwen_ternary_tables_complete import (  # noqa: E402
    EMOTIONAL_POOL,
    EMOTIONAL_WEIGHTS,
    HEXAGRAM_BASE,
    HEXAGRAM_INJECTION_SITE,
    PHASE_INFO,
    PHASE_LINE_MAP,
    POROSITY_LEVELS,
    SLIDER_CHECKLIST,
    TOTAL_ENCODINGS,
    YAO_VOCABULARY,
)

# ─── Load emotional engine functions directly ─────────────────────────────────
_EngineSpec = spec_from_file_location("kingwen_emotional_engine", _EMOTIONAL_ENGINE_PATH)
if _EngineSpec is None or _EngineSpec.loader is None:
    raise ImportError(f"Cannot load emotional_engine from {_EMOTIONAL_ENGINE_PATH}")
_EngineModule = module_from_spec(_EngineSpec)
sys.modules["kingwen_emotional_engine"] = _EngineModule
_EngineSpec.loader.exec_module(_EngineModule)

expand_hexagram = _EngineModule.expand_hexagram
sample_resolve = _EngineModule.sample_resolve
collapse_full_128 = _EngineModule.collapse_full_128
consensus_from_resolved = _EngineModule._compute_consensus_from_resolved

# ─── Load temporal engine shifts directly ─────────────────────────────────────
_TemporalSpec = spec_from_file_location("kingwen_temporal_engine", _TEMPORAL_ENGINE_PATH)
if _TemporalSpec is None or _TemporalSpec.loader is None:
    raise ImportError(f"Cannot load temporal_emotional_engine from {_TEMPORAL_ENGINE_PATH}")
_TemporalModule = module_from_spec(_TemporalSpec)
sys.modules["kingwen_temporal_engine"] = _TemporalModule
_TemporalSpec.loader.exec_module(_TemporalModule)

temporal_shift = _TemporalModule.BASE_PHASE_SHIFTS


def consult(text: str = "", *, session_id: str = "openjarvis", emotional_input: int = 50) -> Dict[str, Any]:
    """Deterministic consult entrypoint backed by local 512-state collapse consensus."""
    try:
        collapse = collapse_full_128(emotional_input=emotional_input)
        consensus = collapse.get("consensus", {}) or {}
    except Exception:
        consensus = {}

    hexagram_id = consensus.get("consensus_hexagram_id")
    hexagram_name = consensus.get("consensus_hexagram_name", "")
    temporal = consensus.get("consensus_temporal") or "present"
    porosity = consensus.get("consensus_porosity_mean")
    vector = consensus.get("consensus_vector") or {}
    intent = consensus.get("consensus_intent", "")
    explanation = consensus.get("consensus_explanation", "")
    yaolabel = consensus.get("consensus_yao", "stable_yao")
    temporal_distribution = consensus.get("temporal_distribution", {})

    trajectory = "still"
    if temporal in {"transition", "dissolution"}:
        trajectory = "diverging"
    elif temporal in {"resolution", "crystallization"}:
        trajectory = "converging"

    hex_symbols = HEXAGRAM_BASE.get(int(hexagram_id or 1), {})
    return {
        "hexagram_id": int(hexagram_id or 0),
        "hexagram_name": hexagram_name or hex_symbols.get("name", ""),
        "phase_temporal": temporal,
        "agree_temporal": temporal,
        "trajectory": trajectory,
        "action": hex_symbols.get("action", ""),
        "category": hex_symbols.get("category", ""),
        "reaction_frame": explanation,
        "emotional_deltas": vector,
        "emotional_tongue": {
            "porosity": porosity,
            "training_weight_vectors": vector,
        },
        "unified_weave": explanation,
        "trainingNotes": intent,
        "consensus_hexagram_id": int(hexagram_id or 0),
        "consensus_hexagram_name": hexagram_name or hex_symbols.get("name", ""),
        "consensus_temporal": temporal,
        "consensus_yao": yaolabel,
        "consensus_porosity_mean": porosity,
        "consensus_porosity_mode": consensus.get("consensus_porosity_mode"),
        "consensus_vector": vector,
        "consensus_intent": intent,
        "consensus_explanation": explanation,
        "temporal_distribution": temporal_distribution,
        "source": "kingwen-immutable-tables",
        "session_id": session_id,
        "text": text,
        "emotional_input": emotional_input,
    }


__all__ = [
    "KING_WEN_TABLES_DIR",
    "expand_hexagram",
    "sample_resolve",
    "collapse_full_128",
    "consensus_from_resolved",
    "temporal_shift",
    "consult",
    # immutable re-exports
    "EMOTIONAL_POOL",
    "EMOTIONAL_WEIGHTS",
    "HEXAGRAM_BASE",
    "HEXAGRAM_INJECTION_SITE",
    "PHASE_INFO",
    "PHASE_LINE_MAP",
    "POROSITY_LEVELS",
    "SLIDER_CHECKLIST",
    "TOTAL_ENCODINGS",
    "YAO_VOCABULARY",
]
