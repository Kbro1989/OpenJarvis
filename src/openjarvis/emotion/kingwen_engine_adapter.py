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
    """Deterministic consult entrypoint matching Desktop workflow + worker contract."""
    payload = expand_hexagram(
        hexagram_id=1,
        request_text=text,
        phase_bits=0,
        emotional_input=emotional_input,
    )
    return {
        "hexagram_id": payload["hexagram_id"],
        "hexagram_name": payload["hexagram_symbols"]["name"],
        "phase_temporal": PHASE_INFO[0]["temporal"],
        "action": payload["hexagram_symbols"]["action"],
        "category": payload["hexagram_symbols"]["category"],
        "reaction_frame": payload["inject_site"].get("reason", ""),
        "emotional_deltas": payload["expanded_vector"],
        "emotional_tongue": {
            "porosity": payload["inject_site"].get("porosity"),
            "training_weight_vectors": payload["expanded_vector"],
        },
        "unified_weave": payload["inject_site"].get("reason", ""),
        "source": "kingwen-immutable-tables",
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
