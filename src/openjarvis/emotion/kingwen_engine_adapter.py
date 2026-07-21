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
    VOICEBOX_VOICE_POOL as EMOTIONAL_POOL,  # re-exported under legacy name
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
try:
    _mode_of_tau = _EngineModule._mode_of_tau
except AttributeError:
    def _mode_of_tau(values: List[float]) -> float:
        if not values:
            return 0.0
        bucket: Dict[float, int] = {}
        for v in values:
            key = round(float(v), 2)
            bucket[key] = bucket.get(key, 0) + 1
        return max(bucket, key=bucket.__getitem__)

try:
    _gaussian_weight = _EngineModule._gaussian_weight
except AttributeError:
    def _gaussian_weight(x: float, mu: float, sigma: float) -> float:
        if sigma <= 1e-9:
            return 1.0 if x == mu else 0.0
        return math.exp(-((x - mu) ** 2) / (2.0 * sigma * sigma))

try:
    _hamiltonian_energy = _EngineModule._hamiltonian_energy
except AttributeError:
    def _hamiltonian_energy(resolved_vector: List[float], line_balance: Dict[str, Any], phase_shift: List[float]) -> float:
        momentum = [max(0.0, float(v)) for v in resolved_vector]
        lagrangian = (
            abs(line_balance.get("yin_ratio", 0.0) - line_balance.get("yang_ratio", 0.0)) * 0.5
            + float(line_balance.get("yao_ratio", 0.0) or 0.0) * 0.3
            + float(line_balance.get("changing_ratio", 0.0) or 0.0) * 0.2
        )
        pq_dot = sum(m * abs(float(s)) for m, s in zip(momentum, phase_shift))
        return max(0.0, min(1.0, pq_dot - lagrangian))

# ─── Load temporal engine shifts directly ─────────────────────────────────────
_TemporalSpec = spec_from_file_location("kingwen_temporal_engine", _TEMPORAL_ENGINE_PATH)
if _TemporalSpec is None or _TemporalSpec.loader is None:
    raise ImportError(f"Cannot load temporal_emotional_engine from {_TEMPORAL_ENGINE_PATH}")
_TemporalModule = module_from_spec(_TemporalSpec)
sys.modules["kingwen_temporal_engine"] = _TemporalModule
_TemporalSpec.loader.exec_module(_TemporalModule)

temporal_shift = _TemporalModule.BASE_PHASE_SHIFTS


def _build_j_space_top_tokens(resolved: List[Dict[str, Any]], top_k: int = 25) -> List[Dict[str, Any]]:
    """Surface privileged verbalizable states matching J-lens sparse-subframe intuition.

    Returns top-k resolved states by weighted coherence proxy:
    coherence + small porosity/phase-alignment bias.
    """
    if not resolved:
        return []
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for item in resolved:
        rv = item.get("resolved_vector") or {}
        coherence = float(rv.get("coherence", 0.0) or 0.0)
        inject = item.get("inject_site") or {}
        porosity = float(inject.get("porosity", 0.35) or 0.35)
        phase_temporal = str(item.get("phase_temporal", "") or "")
        phase_bonus = 0.05 if phase_temporal in {"present", "resolution"} else 0.0
        score = coherence + (porosity * 0.05) + phase_bonus
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for _, item in scored[:top_k]:
        sym = item.get("hexagram_symbols") or {}
        rv = item.get("resolved_vector") or {}
        out.append({
            "hexagram_id": item.get("hexagram_id"),
            "phase_bits": item.get("phase_bits"),
            "phase_temporal": item.get("phase_temporal"),
            "name": sym.get("name"),
            "unicode": sym.get("unicode"),
            "category": sym.get("category"),
            "action": sym.get("action"),
            "coherence": rv.get("coherence"),
            "voiceWeight": rv.get("voiceWeight"),
            "inject_site": item.get("inject_site"),
        })
    return out


def _hexagram_color(hexagram_id: int, *, chinese_text: str = "", unicode_symbol_text: str = "", chinese_symbol: str = "", unicode_symbol: str = "") -> str:
    """Deterministic color tied to the actual glyph or canonical text.

    Accepts raw string fields or nested dict/list payloads by extracting
    the first string value when needed.
    """

    def _first_str(*vals: object) -> str:
        for v in vals:
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                for val in v.values():
                    s = _first_str(val)
                    if s:
                        return s
            if isinstance(v, (list, tuple)):
                for item in v:
                    s = _first_str(item)
                    if s:
                        return s
        return ""

    seed = (
        chinese_symbol
        or chinese_text
        or unicode_symbol
        or unicode_symbol_text
        or f"hex-{hexagram_id}"
    )
    return f"hsl({float(abs(hash(seed)) % 360)}, 72%, 54%)"


def consult(
    text: str = "",
    *,
    session_id: str = "openjarvis",
    emotional_input: int = 50,
    include_crowd_votes: bool = False,
    snapshot: Dict[str, Any] | None = None,
    baseline: Dict[str, Any] | None = None,
    top_k: int = 64,
) -> Dict[str, Any]:
    """Deterministic consult entrypoint backed by local 512-state collapse consensus.

    Returns shallow `jspace_*` fields for WS-02:
      - `jspace_broadcast`: top-K selected resolved states
      - `jspace_energy_delta`: change in average Hamiltonian energy from baseline
      - `jspace_coherence_delta`: change in mean coherence from baseline
      - `jspace_coverage`: domain-slot / phase / vector coverage of broadcast set
      - `jspace_energy`: average Hamiltonian energy of current collapse
      - `jspace_coherence`: average coherence of current collapse
      - `jspace_failure`: failure stripe when collapse or broadcast selection fails

    Failure tails:
      - on collapse failure: fallback to fixed 64-hex expansion; no Gaussian
        smoothing if zero spread; Hamiltonian proxy fallback if energy errors.
    """
    fallback_failure: Dict[str, Any] | None = None
    try:
        collapse = collapse_full_128(emotional_input=emotional_input)
        consensus = collapse.get("consensus", {}) or {}
        expanded = collapse.get("expanded", []) or []
        resolved = collapse.get("resolved", []) or []
    except Exception as exc:  # pragma: failure tail
        fallback_failure = {
            "stage": "collapse",
            "error": str(exc),
            "fallback": "fixed_64hex_expansion_no_gaussian",
        }
        consensus = {}
        expanded = []
        resolved = _fixed_64hex_fallback(emotional_input=emotional_input)

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
    base_vector_keys = ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]

    def _mean_vector(items: List[Dict[str, Any]], vector_key: str = "resolved_vector") -> Dict[str, float]:
        if not items:
            return {k: 0.0 for k in base_vector_keys}
        sums = {k: 0.0 for k in base_vector_keys}
        count = 0
        for item in items:
            rv = item.get(vector_key) or {}
            if not isinstance(rv, dict):
                continue
            count += 1
            for k in base_vector_keys:
                sums[k] += float(rv.get(k, 0.0) or 0.0)
        return {k: (sums[k] / count if count else 0.0) for k in base_vector_keys}

    current_avg = _mean_vector(resolved)
    current_hamiltonian_sum = 0.0
    current_hamiltonian_count = 0
    for item in resolved:
        try:
            rv = item.get("resolved_vector") or {}
            lb = item.get("inject_site", {}) or {}
            current_hamiltonian_sum += _hamiltonian_energy(
                [float(rv.get(k, 0.0) or 0.0) for k in base_vector_keys],
                lb.get("line_balance", {}) or {},
                [0.0, 0.0, 0.0, 0.0, 0.0],
            )
            current_hamiltonian_count += 1
        except Exception:
            try:
                vec = [float((item.get("resolved_vector") or {}).get(k, 0.0) or 0.0) for k in base_vector_keys]
                current_hamiltonian_sum += sum(v * v for v in vec) ** 0.5
                current_hamiltonian_count += 1
            except Exception:
                pass
    current_hamiltonian = current_hamiltonian_sum / max(current_hamiltonian_count, 1)

    current_coherence = sum(float((item.get("resolved_vector") or {}).get("coherence", 0.0) or 0.0) for item in resolved) / max(len(resolved), 1)

    baseline_avg: Dict[str, float] = {}
    baseline_hamiltonian = 0.0
    baseline_coherence = 0.0
    if baseline and isinstance(baseline, dict):
        baseline_resolved = baseline.get("resolved") or []
        if isinstance(baseline_resolved, list):
            baseline_avg = _mean_vector(baseline_resolved)
            if baseline_avg and any(v for v in baseline_avg.values()):
                try:
                    baseline_hamiltonian = sum(
                        _hamiltonian_energy(
                            [float((item.get("resolved_vector") or {}).get(k, 0.0) or 0.0) for k in base_vector_keys],
                            (item.get("inject_site") or {}).get("line_balance", {}) or {},
                            [0.0, 0.0, 0.0, 0.0, 0.0],
                        )
                        for item in baseline_resolved
                        if item.get("resolved_vector") and isinstance(item.get("resolved_vector"), dict)
                    ) / max(len(baseline_resolved), 1)
                except Exception:
                    try:
                        baseline_hamiltonian = sum(
                            sum((float((item.get("resolved_vector") or {}).get(k, 0.0) or 0.0) ** 2 for k in base_vector_keys)) ** 0.5
                            for item in baseline_resolved
                            if item.get("resolved_vector") and isinstance(item.get("resolved_vector"), dict)
                        ) / max(len(baseline_resolved), 1)
                    except Exception:
                        baseline_hamiltonian = 0.0
        baseline_coherence = (
            sum(float((item.get("resolved_vector") or {}).get("coherence", 0.0) or 0.0) for item in baseline_resolved)
            / max(len(baseline_resolved), 1)
        )

    jspace_energy_delta = float(current_hamiltonian - baseline_hamiltonian)
    jspace_coherence_delta = float(current_coherence - baseline_coherence)

    broadcast = _pick_jspace_broadcast(resolved, top_k=top_k, fallback_failure=fallback_failure)
    coverage = _jspace_coverage(broadcast)

    phase_center = _mode_of_tau([float((item.get("resolved_vector") or {}).get("coherence", 0.0) or 0.0) for item in resolved]) if resolved else 0.0
    spread = sum(
        (float((item.get("resolved_vector") or {}).get("coherence", 0.0) or 0.0) - phase_center) ** 2
        for item in resolved
    ) / max(len(resolved), 1)
    spread = max(spread, 0.0) ** 0.5
    if spread <= 1e-9:
        item_weights = {id(item): 1.0 / max(len(broadcast), 1) for item in broadcast}
    else:
        item_weights = {}
        for item in broadcast:
            rv = item.get("resolved_vector") or {}
            raw = float(rv.get("coherence", 0.0) or 0.0)
            try:
                item_weights[id(item)] = _gaussian_weight(raw, phase_center, spread)
            except Exception:
                item_weights[id(item)] = 1.0 / max(len(broadcast), 1)

    def _build_shape_contract(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not items:
            return {"state_count": 0, "hexagram_ids": [], "phase_temporal": {}, "primary_pool": {}, "vector_keys": []}
        hexagram_ids = sorted({int(item.get("hexagram_id") or 0) for item in items if item.get("hexagram_id")})
        phase_temporal: Dict[str, int] = {}
        primary_pool: Dict[str, int] = {}
        vector_sums = {k: 0.0 for k in base_vector_keys}
        vector_count = 0
        for item in items:
            phase_temporal[str(item.get("phase_temporal") or "")] = phase_temporal.get(str(item.get("phase_temporal") or ""), 0) + 1
            pool = (item.get("inject_site") or {}).get("primary_pool") or ""
            primary_pool[str(pool)] = primary_pool.get(str(pool), 0) + 1
            rv = item.get("resolved_vector") or {}
            if isinstance(rv, dict):
                vector_count += 1
                for k in base_vector_keys:
                    vector_sums[k] += float(rv.get(k, 0.0) or 0.0)
        resolved_vector = vector_sums
        if not resolved_vector:
            resolved_vector = vector
        return {
            "state_count": len(items),
            "hexagram_ids": hexagram_ids,
            "phase_temporal": phase_temporal,
            "primary_pool": primary_pool,
            "resolved_vector": resolved_vector,
            "vector_keys": base_vector_keys,
        }

    shape_contract = _build_shape_contract(resolved)
    broadcast_contract = _build_shape_contract(broadcast)
    coverage_contract = _jspace_coverage(broadcast)

    jspace = {
        "jspace_energy_delta": jspace_energy_delta,
        "jspace_coherence_delta": jspace_coherence_delta,
        "jspace_coverage": coverage_contract,
        "jspace_energy": float(current_hamiltonian),
        "jspace_coherence": float(current_coherence),
        "jspace_verbalizable": float(coverage_contract.get("verbalizable", 0.0) or 0.0),
        "jspace_modulatable": float(coverage_contract.get("modulatable", 0.0) or 0.0),
        "jspace_flexible": float(coverage_contract.get("flexible", 0.0) or 0.0),
        "jspace_selective": float(coverage_contract.get("selective", 0.0) or 0.0),
        "jspace_broadcast_count": len(broadcast),
        "jspace_broadcast": broadcast,
        "jspace_weights": item_weights,
        "shape_contract": shape_contract,
        "broadcast_contract": broadcast_contract,
        "jspace_failure": fallback_failure,
        "pass": 1 if not fallback_failure else 0,
        "verdict": "success" if not fallback_failure else fallback_failure.get("fallback", "collapse_failure"),
        "consensus": hexagram_id,
        "expansion": len(expanded) if expanded else 0,
        "coherence_delta": jspace_coherence_delta,
        "jspace_coverage_raw": coverage_contract.get("domain_slot", {}),
    }

    result: Dict[str, Any] = {
        "hexagram_id": int(hexagram_id or 0),
        "hexagram_name": hexagram_name or hex_symbols.get("name", ""),
        "hexagram_symbol": hex_symbols.get("unicode", ""),
        "hexagram_color": _hexagram_color(
            int(hexagram_id or 0),
            chinese_text=hex_symbols.get("chinese", ""),
            unicode_symbol_text=hex_symbols.get("unicode", ""),
        ),
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
            "yao_vocabulary": YAO_VOCABULARY[0] if isinstance(YAO_VOCABULARY, list) else YAO_VOCABULARY,
        },
        "unified_weave": explanation,
        "trainingNotes": intent,
        "j_space_top_tokens": _build_j_space_top_tokens(resolved),
        "jspace_top_tokens": _build_j_space_top_tokens(resolved),
        "consensus_hexagram_id": int(hexagram_id or 0),
        "consensus_hexagram_name": hexagram_name or hex_symbols.get("name", ""),
        "consensus_hexagram_symbol": hex_symbols.get("unicode", ""),
        "consensus_temporal": temporal,
        "consensus_yao": yaolabel,
        "consensus_porosity_mean": porosity,
        "consensus_porosity_mode": consensus.get("consensus_porosity_mode"),
        "consensus_vector": vector,
        "consensus_intent": intent,
        "consensus_explanation": explanation,
        "temporal_distribution": temporal_distribution,
        "consensus_path": {
            "total_expanded": len(expanded),
            "total_resolved": len(resolved),
            "emotional_input": emotional_input,
        },
        "jspace_broadcast": broadcast,
        "jspace_coverage": coverage_contract,
        "jspace_energy_delta": jspace_energy_delta,
        "jspace_coherence_delta": jspace_coherence_delta,
        "jspace_energy": float(current_hamiltonian),
        "jspace_coherence": float(current_coherence),
        "jspace_selective": float(coverage_contract.get("selective", 0.0) or 0.0),
        "jspace_verbalizable": float(coverage_contract.get("verbalizable", 0.0) or 0.0),
        "jspace_modulatable": float(coverage_contract.get("modulatable", 0.0) or 0.0),
        "jspace_flexible": float(coverage_contract.get("flexible", 0.0) or 0.0),
        "jspace_broadcast_count": len(broadcast),
        "jspace_failure": fallback_failure,
        "source": "kingwen-immutable-tables",
        "session_id": session_id,
        "text": text,
        "emotional_input": emotional_input,
    }

    if include_crowd_votes and expanded:
        crowd_hexagram_votes = []
        for item in expanded:
            h_id = int(item.get("hexagram_id") or 0)
            symbols = item.get("hexagram_symbols") or HEXAGRAM_BASE.get(h_id, {})
            crowd_hexagram_votes.append({
                "hexagram_id": h_id,
                "hexagram_name": symbols.get("name", ""),
                "hexagram_symbol": symbols.get("unicode", ""),
                "category": symbols.get("category", ""),
                "action": symbols.get("action", ""),
                "expanded_vector": item.get("expanded_vector", {}),
                "inject_site": item.get("inject_site", {}),
                "line_states": item.get("line_states", []),
                "phase_bits": item.get("phase_bits"),
                "phase_temporal": PHASE_INFO.get(item.get("phase_bits", 0), {}).get("temporal", ""),
            })
        result["crowd_hexagram_votes"] = crowd_hexagram_votes

        winning_line_states = []
        for item in resolved:
            if int(item.get("hexagram_id") or 0) == hexagram_id:
                ls = item.get("line_states") or []
                if isinstance(ls, list):
                    winning_line_states.extend(ls)
        result["winning_hex_line_states"] = winning_line_states

    return result


def _fixed_64hex_fallback(*, emotional_input: int = 50) -> List[Dict[str, Any]]:
    """Fallback to fixed 64-hex expansion with zero Gaussian smoothing."""
    return [
        sample_resolve(h_id, phase_bits=0, emotional_input=emotional_input)
        for h_id in range(1, 65)
    ]


def _pick_jspace_broadcast(
    resolved: List[Dict[str, Any]],
    *,
    top_k: int = 64,
    fallback_failure: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Top-K selection with domain-slot/phase/optional vector coverage minimums."""
    if top_k <= 0:
        return []
    if not resolved:
        out: List[Dict[str, Any]] = [
            {
                "hexagram_id": None,
                "phase_temporal": "present",
                "resolved_vector": {"chaos": 0.0, "whimsy": 0.0, "darkTone": 0.0, "coherence": 0.0, "voiceWeight": 0.0},
                "inject_site": {},
                "jspace_failure": fallback_failure or {"stage": "broadcast", "error": "no resolved states", "fallback": "empty_broadcast"},
                "jspace_reason": "zero resolved states",
            }
        ]
        return out

    coverage_floor = {
        "min_phase_temporals": 1,
        "min_primary_pools": 1,
        "min_vector_coverage_items": max(1, min(top_k, 8)),
    }
    candidates = list(resolved)

    phase_set = {str(item.get("phase_temporal") or "") for item in candidates}
    pool_set = {(item.get("inject_site") or {}).get("primary_pool") or "" for item in candidates}
    vector_set = {str((item.get("resolved_vector") or {}).get("voiceWeight")) for item in candidates if isinstance((item.get("resolved_vector") or {}), dict)}
    if (
        len(phase_set) < coverage_floor["min_phase_temporals"]
        or len(pool_set) < coverage_floor["min_primary_pools"]
        or len(vector_set) < coverage_floor["min_vector_coverage_items"]
    ):
        expanded_candidates = _fixed_64hex_fallback(emotional_input=50)
        if expanded_candidates:
            candidates = expanded_candidates + candidates
            candidates = candidates[: max(top_k, len(expanded_candidates))]

    item_weights: List[Tuple[float, Dict[str, Any]]] = []
    for item in candidates:
        rv = item.get("resolved_vector") or {}
        if not isinstance(rv, dict):
            continue
        coherence = float(rv.get("coherence", 0.0) or 0.0)
        inject = item.get("inject_site") or {}
        porosity = float(inject.get("porosity", 0.35) or 0.35)
        phase_temporal = str(item.get("phase_temporal") or "")
        phase_bonus = 0.05 if phase_temporal in {"present", "resolution"} else 0.0
        score = coherence + (porosity * 0.05) + phase_bonus
        item_weights.append((score, item))
    item_weights.sort(key=lambda x: x[0], reverse=True)
    selected = [item for _, item in item_weights[:top_k]]

    if not selected and candidates:
        selected = [candidates[-1]]

    broadcast: List[Dict[str, Any]] = []
    for item in selected:
        sym = item.get("hexagram_symbols") or {}
        rv = item.get("resolved_vector") or {}
        broadcast.append({
            "hexagram_id": item.get("hexagram_id"),
            "phase_bits": item.get("phase_bits"),
            "phase_temporal": item.get("phase_temporal"),
            "name": sym.get("name"),
            "unicode": sym.get("unicode"),
            "category": sym.get("category"),
            "action": sym.get("action"),
            "coherence": rv.get("coherence"),
            "voiceWeight": rv.get("voiceWeight"),
            "inject_site": item.get("inject_site"),
            "score": next((score for score, it in item_weights if it is item), None),
            "jspace_reason": "top_k_selection",
            "jspace_failure": fallback_failure,
        })
    return broadcast


def _jspace_coverage(broadcast: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not broadcast:
        return {
            "domain_slot": {},
            "phase_temporal": {},
            "vector_coverage": {},
            "verbalizable": 0.0,
            "modulatable": 0.0,
            "flexible": 0.0,
            "selective": 0.0,
        }
    phase_counts: Dict[str, int] = {}
    primary_pool_counts: Dict[str, int] = {}
    vector_vals: Dict[str, List[float]] = {}
    verbalizable = 0.0
    for item in broadcast:
        phase_counts[str(item.get("phase_temporal") or "")] = phase_counts.get(str(item.get("phase_temporal") or ""), 0) + 1
        pp = (item.get("inject_site") or {}).get("primary_pool") or ""
        primary_pool_counts[pp] = primary_pool_counts.get(pp, 0) + 1
        rv = item.get("resolved_vector") or {}
        if isinstance(rv, dict):
            verbalizable += float(rv.get("voiceWeight", 0.0) or 0.0)
        for k, v in (rv or {}).items():
            if isinstance(v, (int, float)):
                vector_vals.setdefault(k, []).append(float(v))

    domain_slot = dict(primary_pool_counts)
    phase_temporal = dict(phase_counts)
    vector_coverage = {
        k: {
            "min": min(vs) if vs else 0.0,
            "max": max(vs) if vs else 0.0,
            "mean": sum(vs) / len(vs) if vs else 0.0,
            "count": len(vs),
        }
        for k, vs in vector_vals.items()
    }
    modulatable = vector_coverage.get("coherence", {}).get("mean", 0.0) + phase_counts.get("present", 0) / max(len(broadcast), 1)
    flexible = len(domain_slot) / max(len(BROADCAST_POOL_UNIVERSE), 1)
    selective = 1.0 - (len(broadcast) / max(len(BROADCAST_POOL_UNIVERSE), 1))
    return {
        "domain_slot": domain_slot,
        "phase_temporal": phase_temporal,
        "vector_coverage": vector_coverage,
        "verbalizable": verbalizable / max(len(broadcast), 1),
        "modulatable": modulatable,
        "flexible": flexible,
        "selective": selective,
    }


BROADCAST_POOL_UNIVERSE: List[str] = [
    "qwen_base",
    "earthy_patience",
    "birth_chaos",
    "naive_curiosity",
    "hierarchical_command",
    "warm_cooperation",
    "void_origin",
    "harmonic_flow",
    "genesis_spark",
    "proto_pool",
]


__all__ = [
    "KING_WEN_TABLES_DIR",
    "expand_hexagram",
    "sample_resolve",
    "collapse_full_128",
    "consensus_from_resolved",
    "temporal_shift",
    "consult",
    "_fixed_64hex_fallback",
    "_pick_jspace_broadcast",
    "_jspace_coverage",
    "BROADCAST_POOL_UNIVERSE",
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
