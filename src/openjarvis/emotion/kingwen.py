"""King Wen emotion provider for OpenJarvis.

Loads the generated King Wen immutable tables and exposes:
- consultation entrypoint for prompt injection
- voice-preset resolution keyed by voiceWeight
- Oracle Console formatter for live response annotation

Data contract:
- data/hexagram-registry.json
- data/emotional-weights.json
- data/temporal-reflections.json
- kingwen_ternary_tables_complete.py
"""

from __future__ import annotations

import hashlib
import importlib.util as _ilu
import json
import os as _os
from pathlib import Path
from typing import Any, Dict, Optional

from openjarvis.core.session_clock_bridge import (
    consciousness_state,
    consciousness_tick,
    get_consciousness_clock,
)


class KingWenEmotionProvider:
    """Deterministic 64-hex emotional state and voice-selection provider."""

    def __init__(
        self,
        registry_path: str | Path,
        weights_path: str | Path,
        reflections_path: str | Path,
        ternary_module_path: str | Path | None = None,
    ) -> None:
        self._registry: Dict[str, Any] = {}
        self._weights: Dict[str, Any] = {}
        self._reflections: Dict[str, Any] = {}
        self._ternary_entry_cache: Dict[str, Dict[str, Any]] = {}
        self._ternary_module = None
        self._load(registry_path, weights_path, reflections_path)
        self._ternary_module = self._load_ternary_module(ternary_module_path)

    def _load(
        self,
        registry_path: str | Path,
        weights_path: str | Path,
        reflections_path: str | Path,
    ) -> None:
        self._registry = self._read_json(registry_path)
        self._weights = self._read_json(weights_path)
        self._reflections = self._read_json(reflections_path)

    @staticmethod
    def _read_json(path: str | Path) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"King Wen data missing: {p}")
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _load_ternary_module(ternary_module_path: str | Path | None) -> Any:
        if ternary_module_path is None:
            env_path = _os.environ.get("KING_WEN_IMMUTABLE_TABLES")
            if env_path:
                candidate = Path(env_path) / "kingwen_ternary_tables_complete.py"
                ternary_module_path = candidate
            else:
                candidate = (
                    Path(__file__).resolve().parents[3]
                    / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
                    / "kingwen_ternary_tables_complete.py"
                )
                ternary_module_path = candidate
        path = Path(ternary_module_path)
        if not path.exists():
            return None
        spec = _ilu.spec_from_file_location("kingwen_ternary_tables_complete", path)
        if spec is None or spec.loader is None:
            return None
        module = _ilu.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _stable_hash(text: str) -> int:
        """Full-text deterministic hash, no truncation."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big")

    def _load_collapse_recorded(self) -> Dict[str, Any] | None:
        try:
            env_path = _os.environ.get("KING_WEN_IMMUTABLE_TABLES")
            if env_path:
                candidate = Path(env_path) / "collapse_full_128_output.json"
                if candidate.exists():
                    import json as _json
                    return _json.loads(candidate.read_text(encoding="utf-8"))
            base = Path(__file__).resolve().parents[4]
            for name in (
                "KING-WEN-I-CHING-IMMUTABLE-TABLES",
                "KING-WEN-I-CHING-I-MMUTABLE-TABLES",
            ):
                candidate = base / name / "collapse_full_128_output.json"
                if candidate.exists():
                    import json as _json
                    return _json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _load_ternary_expansion(self) -> Dict[str, Any] | None:
        try:
            env_path = _os.environ.get("KING_WEN_IMMUTABLE_TABLES")
            if env_path:
                candidate = Path(env_path) / "scripts" / "ternary_full_expansion.json"
                if candidate.exists():
                    import json as _json
                    return _json.loads(candidate.read_text(encoding="utf-8"))
            base = Path(__file__).resolve().parents[4]
            for name in (
                "KING-WEN-I-CHING-IMMUTABLE-TABLES",
                "KING-WEN-I-CHING-I-MMUTABLE-TABLES",
            ):
                candidate = base / name / "scripts" / "ternary_full_expansion.json"
                if candidate.exists():
                    import json as _json
                    return _json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    def _resolve_expansion_source(self, emotional_input: int) -> Dict[str, Any]:
        """Return the highest-fidelity expansion source available.

        Priority:
        1. ternary_full_expansion.json  — 729 hexagrams / 5832 resolved states
        2. collapse_full_128_output.json — 64 hexagrams / 512 resolved states
        3. live fallback build from registry + weights
        """
        ternary = self._load_ternary_expansion()
        if ternary:
            return ternary
        recorded = self._load_collapse_recorded()
        if recorded:
            return recorded
        return {"expanded": [], "resolved": [], "consensus": {}, "canonical_map": {}}

    def _ternary_full_expansion(self, emotional_input: int) -> Dict[str, Any]:
        data = self._load_ternary_expansion()
        if not data:
            return {"expanded": [], "resolved": [], "consensus": {}, "canonical_map": {}}
        trigrams = data.get("trigrams", {})
        hexagrams = data.get("hexagrams", {})
        resolved = data.get("resolved", {})
        weights = self._weights
        registry = self._registry
        expanded = []
        canonical_map = {}
        for hid_str, hex_entry in hexagrams.items():
            hid = int(hid_str)
            canonical_id = hex_entry.get("canonical_id")
            if canonical_id is not None:
                canonical_map.setdefault(int(canonical_id), hid)
            record = None
            if canonical_id is not None:
                record = registry.get(str(int(canonical_id)))
            if record is None:
                record = {
                    "name": "",
                    "chinese": "",
                    "binary": "".join(str(x) for x in hex_entry.get("vector", [])),
                    "unicode": "",
                    "upper_trigram": "",
                    "lower_trigram": "",
                    "category": "",
                    "action": "",
                }
            weight_entry = weights.get(str(canonical_id or hid), {})
            phases = []
            for pb in range(8):
                rid = hid * 8 + pb
                r = resolved.get(str(rid)) or {}
                tongue = self._resolve_emotion_tongue(canonical_id or hid, "ternary")
                phases.append({
                    "hexagram_id": hid,
                    "phase_bits": pb,
                    "phase_temporal": r.get("phase_temporal", ""),
                    "phase_polarity": r.get("phase_polarity", ""),
                    "phase_description": r.get("phase_description", ""),
                    "winning_entry": {},
                    "emotional_tongue": tongue,
                    "porosity": float(tongue.get("porosity", 0.0) or 0.0),
                    "vectors": {
                        "voiceWeight": float(weight_entry.get("voiceWeight", 0.0)),
                        "coherence": float(weight_entry.get("coherence", 0.0)),
                        "chaos": float(weight_entry.get("chaos", 0.0)),
                        "whimsy": float(weight_entry.get("whimsy", 0.0)),
                        "darkTone": float(weight_entry.get("darkTone", 0.0)),
                    },
                    "inject_site": self._resolve_inject_site(canonical_id or hid),
                    "training_weight_vectors": tongue.get("training_weight_vectors", {}),
                    "yao_vocabulary": {},
                    "line_states": [],
                    "sample_paths": [],
                    "ternary_str": str(hid * 8 + pb),
                    "ternary_lines_top_to_bottom": hex_entry.get("vector", []),
                })
            expanded.append({
                "hexagram_id": hid,
                "hexagram_symbols": record,
                "phases": phases,
                "trigram_vector": hex_entry.get("vector", []),
                "upper_trigram_id": hex_entry.get("upper_trigram_id"),
                "lower_trigram_id": hex_entry.get("lower_trigram_id"),
                "is_canonical": bool(hex_entry.get("is_canonical")),
                "canonical_id": canonical_id,
            })
        consensus = self._compute_ternary_consensus(expanded, emotional_input)
        return {
            "expanded": expanded,
            "resolved": list(resolved.values()) if isinstance(resolved, dict) else [],
            "consensus": consensus,
            "canonical_map": canonical_map,
        }

    def _compute_ternary_consensus(self, expanded: list[Dict[str, Any]], emotional_input: int) -> Dict[str, Any]:
        phases = [p for item in expanded for p in item.get("phases", [])]
        hex_ids = [item.get("hexagram_id") or item.get("hexagram_symbols", {}).get("hexagram_id") for item in expanded]
        phase_temporals = [p.get("phase_temporal") for p in phases if p.get("phase_temporal")]
        phase_polarities = [p.get("phase_polarity") for p in phases if p.get("phase_polarity")]
        porosities = [float(p.get("porosity", 0.0)) for p in phases]
        voice = [float(p.get("vectors", {}).get("voiceWeight", 0.0)) for p in phases]
        coherence = [float(p.get("vectors", {}).get("coherence", 0.0)) for p in phases]
        chaos = [float(p.get("vectors", {}).get("chaos", 0.0)) for p in phases]
        whimsy = [float(p.get("vectors", {}).get("whimsy", 0.0)) for p in phases]
        dark = [float(p.get("vectors", {}).get("darkTone", 0.0)) for p in phases]
        inject_sites = [p.get("inject_site", {}) for p in phases if p.get("inject_site")]
        primary_pools = [str(x.get("primary_pool", "")) for x in inject_sites if x.get("primary_pool")]
        secondary_pools = [str(x.get("secondary_pool", "")) for x in inject_sites if x.get("secondary_pool")]
        primary_porosities = [float(x.get("porosity", 0.0)) for x in inject_sites if x.get("porosity") is not None]
        reasons = [str(x.get("reason", "")) for x in inject_sites if x.get("reason")]
        ternary_agg: Dict[int, Dict[str, int]] = {}
        yao_label_agg: Dict[int, Dict[str, int]] = {}
        direction_counts: Dict[str, int] = {}
        past_states: list[str] = []
        present_states: list[str] = []
        future_states: list[str] = []
        for p in phases:
            for entry in (p.get("line_states") or []):
                if not isinstance(entry, dict):
                    continue
                pos = int(entry.get("position") or 0)
                yao_key = str(entry.get("yao_key") or "")
                yao_label = str(entry.get("yao_label") or "")
                if pos:
                    pos_map = ternary_agg.setdefault(pos, {})
                    pos_map[yao_key] = pos_map.get(yao_key, 0) + 1
                    if yao_label:
                        label_pos_map = yao_label_agg.setdefault(pos, {})
                        label_pos_map[yao_label] = label_pos_map.get(yao_label, 0) + 1
            tongue = p.get("emotional_tongue") or {}
            states = tongue.get("states") or {}
            past_states.append(str(states.get("past", "")))
            present_states.append(str(states.get("present", "")))
            future_states.append(str(states.get("future", "")))
            direction_counts[str(tongue.get("direction", ""))] = direction_counts.get(str(tongue.get("direction", "")), 0) + 1
        consensus_yao_mode: Dict[str, str] = {}
        for pos, label_counts in yao_label_agg.items():
            consensus_yao_mode[str(pos)] = max(label_counts, key=label_counts.__getitem__)
        past_mode = self._mode([s for s in past_states if s]) if past_states else None
        present_mode = self._mode([s for s in present_states if s]) if present_states else None
        future_mode = self._mode([s for s in future_states if s]) if future_states else None
        return {
            "hexagram_id_mode": self._mode(hex_ids),
            "phase_temporal_mode": self._mode(phase_temporals),
            "phase_polarity_mode": self._mode(phase_polarities),
            "porosity_mean": self._mean(porosities),
            "porosity_median": self._median(porosities),
            "porosity_mode": self._mode(porosities),
            "primary_porosity_mean": self._mean(primary_porosities),
            "primary_porosity_median": self._median(primary_porosities),
            "primary_porosity_mode": self._mode(primary_porosities),
            "vectors_mean": {
                "voiceWeight": self._mean(voice),
                "coherence": self._mean(coherence),
                "chaos": self._mean(chaos),
                "whimsy": self._mean(whimsy),
                "darkTone": self._mean(dark),
            },
            "vectors_median": {
                "voiceWeight": self._median(voice),
                "coherence": self._median(coherence),
                "chaos": self._median(chaos),
                "whimsy": self._median(whimsy),
                "darkTone": self._median(dark),
            },
            "vectors_mode": {
                "voiceWeight": self._mode(voice),
                "coherence": self._mode(coherence),
                "chaos": self._mode(chaos),
                "whimsy": self._mode(whimsy),
                "darkTone": self._mode(dark),
            },
            "primary_pool_mode": self._mode(primary_pools),
            "secondary_pool_mode": self._mode(secondary_pools),
            "direction_mode": self._mode(list(direction_counts.keys())),
            "yao_consensus": ternary_agg,
            "yao_label_mode": consensus_yao_mode,
            "past_mode": past_mode,
            "present_mode": present_mode,
            "future_mode": future_mode,
            "reasons": reasons[:8],
        }

    def _collapse(self, text: str, session_id: str, emotional_input: int) -> Dict[str, Any]:
        """Expand all 64 hexagrams × 8 phases from recorded output, then return consensus summary."""
        expanded: list[Dict[str, Any]] | None = None
        if getattr(self, "_collapse_recorded", None) is None:
            self._collapse_recorded = self._load_collapse_recorded()
        recorded = getattr(self, "_collapse_recorded", None) or {}
        recorded_exp = recorded.get("expanded") or []
        if recorded_exp:
            by_key: Dict[str, Dict[str, Any]] = {}
            for item in recorded_exp:
                key = (int(item.get("hexagram_id") or 0), int(item.get("phase_bits") or 0))
                by_key[key] = item
            expanded = []
            for hexagram_id in range(1, 65):
                record = self._registry[str(hexagram_id)]
                hex_phases: list[Dict[str, Any]] = []
                for phase_bits in range(8):
                    key = (hexagram_id, phase_bits)
                    item = by_key.get(key)
                    if not item:
                        weights = self._weights.get(str(hexagram_id), {})
                        ternary_entry = self._resolve_ternary_entry(hexagram_id, phase_bits) or {}
                        tongue = self._resolve_emotion_tongue(hexagram_id, session_id)
                        item = {
                            "hexagram_id": hexagram_id,
                            "phase_bits": phase_bits,
                            "hexagram_symbols": record,
                            "inject_site": self._resolve_inject_site(hexagram_id),
                            "yao_vocabulary": getattr(self._ternary_module, "YAO_VOCABULARY", {}) if self._ternary_module else {},
                            "line_states": [{"position": i + 1, "yao_key": "", "yao_label": ""} for i in range(6)],
                            "expanded_vector": {
                                "chaos": float(weights.get("chaos", 0.0)),
                                "whimsy": float(weights.get("whimsy", 0.0)),
                                "darkTone": float(weights.get("darkTone", 0.0)),
                                "coherence": float(weights.get("coherence", 0.0)),
                                "voiceWeight": float(weights.get("voiceWeight", 0.0)),
                            },
                        }
                    hex_phases.append(
                        {
                            "hexagram_id": hexagram_id,
                            "phase_bits": phase_bits,
                            "phase_temporal": "",
                            "phase_polarity": "",
                            "phase_description": "",
                            "winning_entry": {},
                            "emotional_tongue": {},
                            "porosity": float((item.get("inject_site") or {}).get("porosity", 0.0) or 0.0),
                            "vectors": item.get("expanded_vector") or {},
                            "inject_site": item.get("inject_site") or {},
                            "training_weight_vectors": {},
                            "yao_vocabulary": item.get("yao_vocabulary") or {},
                            "line_states": item.get("line_states") or [],
                            "sample_paths": item.get("sample_paths") or [],
                            "ternary_str": self._ternary_module.encode_hex_phase(hexagram_id, phase_bits) if self._ternary_module else "",
                            "ternary_lines_top_to_bottom": self._resolve_ternary_lines_top_to_bottom(hexagram_id, phase_bits),
                        }
                    )
                expanded.append({"hexagram_id": hexagram_id, "hexagram_symbols": record, "phases": hex_phases})

        if expanded is None:
            expanded = []
            for hexagram_id in range(1, 65):
                record = self._registry[str(hexagram_id)]
                weights = self._weights.get(str(hexagram_id), {})
                hex_phases = []
                for phase_bits in range(8):
                    tongue = self._resolve_emotion_tongue(hexagram_id, session_id)
                    hex_phases.append(
                        {
                            "hexagram_id": hexagram_id,
                            "phase_bits": phase_bits,
                            "phase_temporal": "",
                            "phase_polarity": "",
                            "phase_description": "",
                            "winning_entry": {},
                            "emotional_tongue": tongue,
                            "porosity": float(tongue.get("porosity", 0.0)),
                            "vectors": {
                                "voiceWeight": float(weights.get("voiceWeight", 0.0)),
                                "coherence": float(weights.get("coherence", 0.0)),
                                "chaos": float(weights.get("chaos", 0.0)),
                                "whimsy": float(weights.get("whimsy", 0.0)),
                                "darkTone": float(weights.get("darkTone", 0.0)),
                            },
                            "inject_site": self._resolve_inject_site(hexagram_id),
                            "training_weight_vectors": tongue.get("training_weight_vectors", {}),
                            "yao_vocabulary": {},
                            "line_states": [],
                            "sample_paths": [],
                            "ternary_str": self._ternary_module.encode_hex_phase(hexagram_id, phase_bits) if self._ternary_module else "",
                            "ternary_lines_top_to_bottom": self._resolve_ternary_lines_top_to_bottom(hexagram_id, phase_bits),
                        }
                    )
                expanded.append({"hexagram_id": hexagram_id, "hexagram_symbols": record, "phases": hex_phases})

        if recorded.get("resolved"):
            resolved_raw = recorded.get("resolved") or []
            resolved_index: Dict[tuple[int, int], Dict[str, Any]] = {}
            for item in resolved_raw:
                key = (int(item.get("hexagram_id") or 0), int(item.get("phase_bits") or 0))
                resolved_index[key] = item
            for hex_item in expanded:
                for phase_item in hex_item.get("phases", []):
                    key = (int(phase_item.get("hexagram_id") or 0), int(phase_item.get("phase_bits") or 0))
                    resolved_item = resolved_index.get(key)
                    if resolved_item:
                        phase_item["phase_temporal"] = resolved_item.get("phase_temporal", phase_item.get("phase_temporal", ""))
                        phase_item["phase_polarity"] = resolved_item.get("phase_polarity", phase_item.get("phase_polarity", ""))
                        phase_item["phase_description"] = resolved_item.get("phase_description", phase_item.get("phase_description", ""))
                        phase_item["winning_entry"] = resolved_item.get("winning_entry") or phase_item.get("winning_entry", {})
                        phase_item["line_states"] = resolved_item.get("line_states") or phase_item.get("line_states", [])
                        phase_item["yao_vocabulary"] = resolved_item.get("yao_vocabulary") or phase_item.get("yao_vocabulary", {})
                        phase_item["sample_paths"] = resolved_item.get("sample_paths") or phase_item.get("sample_paths", [])
                        if resolved_item.get("resolved_vector"):
                            phase_item["vectors"] = resolved_item.get("resolved_vector")
                        phase_item["checklist"] = resolved_item.get("checklist") or []
                        phase_item.setdefault("ternary_str", "")
                        phase_item.setdefault("ternary_lines_top_to_bottom", [])

        consensus = self._compute_consensus(expanded)
        # Also flatten resolved states from recorded for full 512-state output
        resolved_flat = []
        if recorded.get("resolved"):
            resolved_flat = recorded.get("resolved") or []
        return {
            "expanded": expanded,
            "consensus": consensus,
            "resolved": resolved_flat,
            "source": "collapse_full_128",
        }

    @staticmethod
    def _mode(values: list[Any]) -> Any:
        if not values:
            return None
        counts: Dict[Any, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return max(counts, key=counts.__getitem__)  # type: ignore[arg-type]

    @staticmethod
    def _mean(values: list[float]) -> float:
        if not values:
            return 0.0
        return float(sum(values)) / float(len(values))

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        n = len(s)
        if n % 2 == 1:
            return float(s[n // 2])
        return float((s[n // 2 - 1] + s[n // 2]) / 2.0)

    def _compute_consensus(self, expanded: list[Dict[str, Any]]) -> Dict[str, Any]:
        phases = [p for item in expanded for p in item.get("phases", [])]
        hex_ids = [item.get("hexagram_id") or item.get("hexagram_symbols", {}).get("hexagram_id") for item in expanded]
        phase_temporals = [p.get("phase_temporal") for p in phases if p.get("phase_temporal")]
        phase_polarities = [p.get("phase_polarity") for p in phases if p.get("phase_polarity")]
        porosities = [float(p.get("porosity", 0.0)) for p in phases]
        voice = [float(p.get("vectors", {}).get("voiceWeight", 0.0)) for p in phases]
        coherence = [float(p.get("vectors", {}).get("coherence", 0.0)) for p in phases]
        chaos = [float(p.get("vectors", {}).get("chaos", 0.0)) for p in phases]
        whimsy = [float(p.get("vectors", {}).get("whimsy", 0.0)) for p in phases]
        dark = [float(p.get("vectors", {}).get("darkTone", 0.0)) for p in phases]
        inject_sites = [p.get("inject_site", {}) for p in phases if p.get("inject_site")]
        primary_pools = [str(x.get("primary_pool", "")) for x in inject_sites if x.get("primary_pool")]
        secondary_pools = [str(x.get("secondary_pool", "")) for x in inject_sites if x.get("secondary_pool")]
        primary_porosities = [float(x.get("porosity", 0.0)) for x in inject_sites if x.get("porosity") is not None]
        reasons = [str(x.get("reason", "")) for x in inject_sites if x.get("reason")]
        ternary_agg: Dict[int, Dict[str, int]] = {}
        yao_label_agg: Dict[int, Dict[str, int]] = {}
        direction_counts: Dict[str, int] = {}
        past_states: list[str] = []
        present_states: list[str] = []
        future_states: list[str] = []
        for p in phases:
            for entry in (p.get("line_states") or []):
                if not isinstance(entry, dict):
                    continue
                pos = int(entry.get("position") or 0)
                yao_key = str(entry.get("yao_key") or "")
                yao_label = str(entry.get("yao_label") or "")
                if pos:
                    pos_map = ternary_agg.setdefault(pos, {})
                    pos_map[yao_key] = pos_map.get(yao_key, 0) + 1
                    if yao_label:
                        label_pos_map = yao_label_agg.setdefault(pos, {})
                        label_pos_map[yao_label] = label_pos_map.get(yao_label, 0) + 1
            tongue = p.get("emotional_tongue") or {}
            states = tongue.get("states") or {}
            past_states.append(str(states.get("past", "")))
            present_states.append(str(states.get("present", "")))
            future_states.append(str(states.get("future", "")))
            direction_counts[str(tongue.get("direction", ""))] = direction_counts.get(str(tongue.get("direction", "")), 0) + 1
        consensus_yao_mode: Dict[str, str] = {}
        for pos, label_counts in yao_label_agg.items():
            consensus_yao_mode[str(pos)] = max(label_counts, key=label_counts.__getitem__)
        past_mode = self._mode([s for s in past_states if s]) if past_states else None
        present_mode = self._mode([s for s in present_states if s]) if present_states else None
        future_mode = self._mode([s for s in future_states if s]) if future_states else None
        return {
            "hexagram_id_mode": self._mode(hex_ids),
            "phase_temporal_mode": self._mode(phase_temporals),
            "phase_polarity_mode": self._mode(phase_polarities),
            "porosity_mean": self._mean(porosities),
            "porosity_median": self._median(porosities),
            "porosity_mode": self._mode(porosities),
            "primary_porosity_mean": self._mean(primary_porosities),
            "primary_porosity_median": self._median(primary_porosities),
            "primary_porosity_mode": self._mode(primary_porosities),
            "vectors_mean": {
                "voiceWeight": self._mean(voice),
                "coherence": self._mean(coherence),
                "chaos": self._mean(chaos),
                "whimsy": self._mean(whimsy),
                "darkTone": self._mean(dark),
            },
            "vectors_median": {
                "voiceWeight": self._median(voice),
                "coherence": self._median(coherence),
                "chaos": self._median(chaos),
                "whimsy": self._median(whimsy),
                "darkTone": self._median(dark),
            },
            "vectors_mode": {
                "voiceWeight": self._mode(voice),
                "coherence": self._mode(coherence),
                "chaos": self._mode(chaos),
                "whimsy": self._mode(whimsy),
                "darkTone": self._mode(dark),
            },
            "primary_pool_mode": self._mode(primary_pools),
            "secondary_pool_mode": self._mode(secondary_pools),
            "direction_mode": self._mode(list(direction_counts.keys())),
            "yao_consensus": ternary_agg,
            "yao_label_mode": consensus_yao_mode,
            "past_mode": past_mode,
            "present_mode": present_mode,
            "future_mode": future_mode,
            "reasons": reasons[:8],
        }

    def _resolve_inject_site(self, hexagram_id: int) -> Dict[str, Any]:
        try:
            return self._ternary_module.HEXAGRAM_INJECTION_SITE[int(hexagram_id)]  # type: ignore[index]
        except Exception:
            return {}

    def _resolve_emotion_tongue(self, hexagram_id: int, session_id: str = "openjarvis") -> Dict[str, Any]:
        """Return a single injected tongue record from the sequence.

        The tongue is drawn from the active hexagram's emotional weights and
        temporal reflections, expressed with King Wen yao-state labels:
        young yin, old yin, present yin, new yao, old yao, present yao,
        old yang, new yang, present yang.
        """
        hexagram_id = int(hexagram_id) or 1
        weights = self._weights.get(str(hexagram_id), {}) or {}
        reflections = self._reflections.get(str(hexagram_id), {}) or {}
        phase_bits = int(self._stable_hash(f"tongue:{hexagram_id}:{session_id or 'openjarvis'}") % 8)
        ternary_entry = self._resolve_ternary_entry(hexagram_id, phase_bits)
        voice = float(weights.get("voiceWeight", 0.0))
        coherence = float(weights.get("coherence", 0.0))
        chaos = float(weights.get("chaos", 0.0))
        whimsy = float(weights.get("whimsy", 0.0))
        dark_tone = float(weights.get("darkTone", 0.0))
        past_text = str(reflections.get("past", ""))
        present_text = str(reflections.get("present", ""))
        future_text = str(reflections.get("future", ""))
        direction = self._direction_from_training_notes(
            str(weights.get("trainingNotes", ""))
        )
        ternary_lines = ternary_entry.get("ternary_lines_top_to_bottom") or []
        changing_lines = ternary_entry.get("phase_changing_lines") or []
        porosity = self._compute_porosity(ternary_lines, changing_lines, direction)

        past_state = self._classify_yin(
            past_text,
            young_bias=0.3,
            old_bias=0.7,
        )
        present_state = self._classify_yao(
            present_text,
            young_bias=0.35,
            old_bias=0.65,
        )
        future_state = self._classify_yang(
            future_text,
            young_bias=0.45,
            old_bias=0.55,
        )
        return {
            "hexagram_id": hexagram_id,
            "voice_weight": voice,
            "coherence": coherence,
            "chaos": chaos,
            "whimsy": whimsy,
            "dark_tone": dark_tone,
            "porosity": porosity,
            "training_weight_vectors": {
                "voiceWeight": voice,
                "coherence": coherence,
                "chaos": chaos,
                "whimsy": whimsy,
                "darkTone": dark_tone,
                "porosity": porosity,
            },
            "direction": direction,
            "states": {
                "past": past_state,
                "present": present_state,
                "future": future_state,
            },
            "texts": {
                "past": past_text,
                "present": present_text,
                "future": future_text,
            },
        }

    @staticmethod
    def _classify_yin(text: str, young_bias: float = 0.5, old_bias: float = 0.5) -> str:
        if not text:
            return "present yin"
        text_hash = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)
        value = ((text_hash % 1_000_000) / 1_000_000.0)
        if value < young_bias * 0.5:
            return "young yin"
        if value > 1.0 - (1.0 - old_bias) * 0.5:
            return "old yin"
        return "present yin"

    @staticmethod
    def _classify_yao(text: str, young_bias: float = 0.5, old_bias: float = 0.5) -> str:
        if not text:
            return "present yao"
        text_hash = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)
        value = ((text_hash % 1_000_000) / 1_000_000.0)
        if value < young_bias * 0.5:
            return "new yao"
        if value > 1.0 - (1.0 - old_bias) * 0.5:
            return "old yao"
        return "present yao"

    @staticmethod
    def _classify_yang(text: str, young_bias: float = 0.5, old_bias: float = 0.5) -> str:
        if not text:
            return "present yang"
        text_hash = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)
        value = ((text_hash % 1_000_000) / 1_000_000.0)
        if value < young_bias * 0.5:
            return "new yang"
        if value > 1.0 - (1.0 - old_bias) * 0.5:
            return "old yang"
        return "present yang"

    @staticmethod
    def _compute_porosity(
        ternary_lines: list[int],
        changing_lines: list[int],
        direction: str,
    ) -> float:
        """Derive porosity from ternary changing/openness signals."""
        max_lines = 6 if not ternary_lines else len(ternary_lines)
        changing_count = len(changing_lines) if changing_lines else 0
        changer_bonus = changing_count / max(1, max_lines)
        direction_bonus = {
            "yield": 0.05,
            "adapt": 0.04,
            "assert": -0.05,
            "wait": 0.02,
        }.get(str(direction or "").lower(), 0.0)
        porosity = 0.35 + changer_bonus * 0.4 + direction_bonus
        return max(0.0, min(1.0, float(porosity)))

    @staticmethod
    def _direction_from_training_notes(text: str) -> str:
        """Derive directional influence token from training notes text deterministically."""
        if not text:
            return "neutral"
        lowered = text.lower()
        candidates = [
            ("assert", "assert"),
            ("yield", "yield"),
            ("adapt", "adapt"),
            ("wait", "wait"),
            ("sovereign", "assert"),
            ("boundary", "wait"),
            ("dissipator", "adapt"),
            ("transformer", "yield"),
        ]
        for needle, direction in candidates:
            if needle in lowered:
                return direction
        return "neutral"

    def _resolve_ternary_lines_top_to_bottom(self, hexagram_id: int, phase_bits: int) -> list[int]:
        module = self._ternary_module
        if module is None:
            return []
        try:
            entry = module.decode_9bit(module.encode_hex_phase(hexagram_id, phase_bits))
            ternary_lines = entry.get("ternary_lines_top_to_bottom") or []
            if ternary_lines:
                return [int(x) for x in ternary_lines]
        except Exception:
            pass
        return []

    def _resolve_ternary_entry(self, hexagram_id: int, phase_bits: int) -> Dict[str, Any]:
        cache_key = f"{hexagram_id}:{phase_bits}"
        entry = self._ternary_entry_cache.get(cache_key)
        if entry is not None:
            return entry
        module = self._ternary_module
        if module is None:
            return {}
        try:
            encoded_index = module.encode_hex_phase(hexagram_id, phase_bits)
            entry = module.decode_9bit(encoded_index)
        except Exception:
            entry = {}
        self._ternary_entry_cache[cache_key] = entry
        return entry

    def _format_reaction_frame(self, entry: Dict[str, Any]) -> str:
        phase = entry.get("phase_temporal")
        ternary_lines = entry.get("ternary_lines_top_to_bottom") or []
        changing_lines = entry.get("phase_changing_lines") or []
        recovering_lines = [i + 1 for i in range(len(ternary_lines)) if ternary_lines[i] == 0]
        deepened_lines = [i + 1 for i in range(len(ternary_lines)) if ternary_lines[i] == 1]
        coherence = float(entry.get("coherence") or 0.0)
        if coherence > 0.7:
            cadence = "steady, coherent delivery"
        elif coherence > 0.35:
            cadence = "soft hesitation, shortened clauses"
        else:
            cadence = "fractured rhythm, brief reflections"
        return "\n".join(
            [
                "Reaction",
                f"Phase: {phase}",
                f"Changing lines: {changing_lines}",
                f"Recovering lines: {recovering_lines}",
                f"Deepened lines: {deepened_lines}",
                f"Speech cadence: {cadence}",
            ]
        )

    def consult(
            self,
            text: str = "",
            session_id: str = "openjarvis",
            emotional_input: int | None = None,
            *,
            include_full_expansion: bool = False,
            ternary: bool = False,
        ) -> Dict[str, Any]:
            """Return a deterministic emotional-state response for prompt injection.

            Always returns the full 64-hexagram expansion with winner labeled.
            Legacy single-hex fields are derived from consensus winner.
            If ternary=True, returns full 729-hex/5,832-resolved ternary expansion.
            """
            if not text:
                raise ValueError("King Wen consult requires non-empty text for deterministic session-state derivation.")
            if emotional_input is None:
                raise ValueError("King Wen consult requires explicit emotional_input; pass a slider value.")
            if not isinstance(emotional_input, (int, float)):
                raise TypeError("King Wen consult requires numeric emotional_input.")
            local_input = int(emotional_input)
            if local_input < 0 or local_input > 100:
                raise ValueError("King Wen consult requires emotional_input in range 0-100.")

            if ternary:
                ternary_payload = self._ternary_full_expansion(local_input)
                return {
                    "mode": "ternary",
                    "expanded_count": 729,
                    "resolved_count": 5832,
                    "canonical_count": 64,
                    "ternary_count": 665,
                    "expanded": ternary_payload.get("expanded", []),
                    "resolved": ternary_payload.get("resolved", []),
                    "consensus": ternary_payload.get("consensus", {}),
                    "canonical_map": ternary_payload.get("canonical_map", {}),
                    "source": "ternary_full_expansion",
                }

            collapse = self._collapse(text, session_id, local_input)
            expanded = collapse.get("expanded", [])
            consensus = collapse.get("consensus") or {}
            resolved_flat = collapse.get("resolved", [])

            record = self._registry[str(1)]
            weights = self._weights.get(str(1), {})
            reflections = self._reflections.get(str(1), {})

            cns_tick = consciousness_tick(
                session_id,
                domain="cns",
                yin_yang_yao=str(consensus.get("yao_label_mode") or ""),
                past_present_future=str(consensus.get("phase_temporal_mode") or ""),
            )

            payload: Dict[str, Any] = {
                "source": collapse.get("source", "collapse_full_128"),
                "all_hexagrams_count": len(expanded),
                "all_resolved_count": max(len(resolved_flat), len(expanded) * 8),
                "expanded": expanded,
                "consensus": consensus,
                "resolved": resolved_flat,
                "consciousness": {
                    "tick_id": cns_tick.get("tick_id"),
                    "yin_yang_yao": cns_tick.get("yin_yang_yao") or "",
                    "past_present_future": cns_tick.get("past_present_future") or "",
                },
            }
            return payload

    @staticmethod
    def _build_unified_weave(reflections: Dict[str, Any]) -> str:
        """Merge past/present/future reflections into a single oracle utterance."""
        past = str((reflections or {}).get("past", "")).strip()
        present = str((reflections or {}).get("present", "")).strip()
        future = str((reflections or {}).get("future", "")).strip()
        if not past and not present and not future:
            return ""
        return f"{past} → {present} → {future}"

    def encode_tongue(self, tongue: Dict[str, Any]) -> str:
        """Encode a captured emotional-tongue save string.

        Compact deterministic carrier for the current 512-state collapse:
        unicode | porosity | chaos | whimsy | darkTone | coherence | voiceWeight
        """
        registry = getattr(self, "_registry", {})
        tongue = tongue or {}
        hexagram_id = tongue.get("hexagram_id")
        if not hexagram_id:
            hexagram_id = self._stable_hash(str(tongue)) % 64 + 1
        record = registry.get(str(int(hexagram_id))) or {}
        unicode_char = str(record.get("unicode", "")) or ""
        porosity = float(tongue.get("porosity", 0.35))
        vectors = tongue.get("training_weight_vectors") or {}
        return "|".join(
            [
                unicode_char,
                f"{porosity:.4f}",
                f"{float(vectors.get('chaos', tongue.get('chaos', 0.0))):.6f}",
                f"{float(vectors.get('whimsy', tongue.get('whimsy', 0.0))):.6f}",
                f"{float(vectors.get('darkTone', tongue.get('dark_tone', 0.0))):.6f}",
                f"{float(vectors.get('coherence', tongue.get('coherence', 0.0))):.6f}",
                f"{float(vectors.get('voiceWeight', tongue.get('voice_weight', 0.0))):.6f}",
            ]
        )

    def decode_tongue(self, save_string: str) -> Dict[str, Any]:
        """Decode a save string back into a usable tongue envelope.

        Returns a minimal dict with unicode, porosity, vectors, and
        direction hint. Rehydration intentionally does not recompute
        full ternary/phases/temporal states from this carrier.
        """
        parts = [p.strip() for p in str(save_string or "").split("|")]
        while len(parts) < 7:
            parts.append("")
        unicode_char, porosity_s, chaos_s, whimsy_s, dark_s, coherence_s, voice_s = parts[:7]
        try:
            porosity = float(porosity_s)
        except Exception:
            porosity = 0.35
        vectors = {
            "chaos": float(chaos_s or 0.0),
            "whimsy": float(whimsy_s or 0.0),
            "darkTone": float(dark_s or 0.0),
            "coherence": float(coherence_s or 0.0),
            "voiceWeight": float(voice_s or 0.0),
        }
        tongue: Dict[str, Any] = {
            "unicode": unicode_char,
            "porosity": porosity,
            "training_weight_vectors": vectors,
            "voice_weight": vectors["voiceWeight"],
            "coherence": vectors["coherence"],
            "chaos": vectors["chaos"],
            "whimsy": vectors["whimsy"],
            "dark_tone": vectors["darkTone"],
        }
        if unicode_char:
            registry = getattr(self, "_registry", {})
            hexagram_id = None
            for rid, record in registry.items():
                if record.get("unicode") == unicode_char:
                    hexagram_id = int(rid)
                    break
            if hexagram_id is not None:
                tongue["hexagram_id"] = hexagram_id
                tongue["action"] = (registry.get(str(hexagram_id)) or {}).get("action", "")
                tongue["category"] = (registry.get(str(hexagram_id)) or {}).get("category", "")
        return tongue

    # ------------------------------------------------------------------
    # Voice wiring
    # ------------------------------------------------------------------

    VOICE_PRESETS = {
        "openai_tts": [
            {"min_weight": 0.00, "max_weight": 0.50, "voice_id": "nova", "speed": 1.0},
            {"min_weight": 0.50, "max_weight": 0.75, "voice_id": "fable", "speed": 1.05},
            {"min_weight": 0.75, "max_weight": 1.01, "voice_id": "onyx", "speed": 1.1},
        ],
        "cartesia": [
            {"min_weight": 0.00, "max_weight": 0.50, "voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091", "speed": 1.0},
            {"min_weight": 0.50, "max_weight": 0.75, "voice_id": "c8f7835e-28a3-4f0c-80d7-c1302ac62aae", "speed": 1.05},
            {"min_weight": 0.75, "max_weight": 1.01, "voice_id": "c8f7835e-28a3-4f0c-80d7-c1302ac62aae", "speed": 1.12},
        ],
        "kokoro": [
            {"min_weight": 0.00, "max_weight": 0.50, "voice_id": "af_heart", "speed": 1.0},
            {"min_weight": 0.50, "max_weight": 0.75, "voice_id": "am_adam", "speed": 1.05},
            {"min_weight": 0.75, "max_weight": 1.01, "voice_id": "bf_emma", "speed": 1.1},
        ],
    }

    def voice_preset(self, tts_backend: str, voice_weight: float) -> Dict[str, float | str]:
        backend_key = (tts_backend or "cartesia").lower()
        if backend_key == "openai":
            backend_key = "openai_tts"
        presets = self.VOICE_PRESETS.get(backend_key, self.VOICE_PRESETS["cartesia"])
        weight = max(0.0, min(1.0, float(voice_weight or 0.0)))
        for preset in presets:
            if preset["min_weight"] <= weight < preset["max_weight"]:
                return {
                    "voice_id": preset["voice_id"],
                    "speed": float(preset["speed"]),
                    "backend": backend_key,
                }
        fallback = presets[-1]
        return {
            "voice_id": fallback["voice_id"],
            "speed": float(fallback["speed"]),
            "backend": backend_key,
        }

    # ------------------------------------------------------------------
    # Prompt / response formatting
    # ------------------------------------------------------------------

    def format_prompt_section(self, payload: Dict[str, Any]) -> str:
        lines = [
            "## Emotional State",
            "",
            f"- Hexagram: {payload.get('hexagram_id', '')} {payload.get('hexagram_name', '')} {payload.get('hexagram_unicode', '')}",
            f"- Structure: {payload.get('upper_trigram', '')} over {payload.get('lower_trigram', '')}",
            f"- Binary: {payload.get('binary', '')}",
            f"- Category: {payload.get('category', '')} | Action: {payload.get('action', '')}",
            f"- Training notes: {payload.get('trainingNotes', '')}",
            "### Emotional weight",
        ]
        deltas = payload.get("emotional_deltas", {})
        for k in ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]:
            lines.append(f"- {k}: {deltas.get(k, 0.0)}")
        lines.extend(
            [
                "",
                "### Reflections",
                f"- Past: {payload.get('reflections', {}).get('past', '')}",
                f"- Present: {payload.get('reflections', {}).get('present', '')}",
                f"- Future: {payload.get('reflections', {}).get('future', '')}",
            ]
        )
        return "\n".join(lines)

    def format_voice_section(self, preset: Dict[str, float | str]) -> str:
        return (
            "## Voice Preset\n"
            "\n"
            f"- backend: {preset.get('backend')}\n"
            f"- voice_id: {preset.get('voice_id')}\n"
            f"- speed: {preset.get('speed')}\n"
        )

    def format_oracle_console(
        self,
        payload: Dict[str, Any],
        response_text: str = "",
        *,
        oracle_label: str = "Oracle Console",
        canonical_tick_ms: float = 640.0,
    ) -> str:
        """Translate live King Wen consultation into the user-facing Oracle Console block."""
        reflections = payload.get("reflections", {}) if isinstance(payload, dict) else {}
        deltas = payload.get("emotional_deltas", {}) if isinstance(payload, dict) else {}
        resolved_emotion = float(deltas.get("coherence", 0.0))
        reaction = payload.get("reaction_frame") if isinstance(payload, dict) else ""
        hexagram_sequence = payload.get("hexagram_sequence") if isinstance(payload, dict) else []
        sequence_text = " → ".join(hexagram_sequence) if hexagram_sequence else ""
        tongue = payload.get("emotional_tongue") if isinstance(payload, dict) else {}
        states = tongue.get("states") if isinstance(tongue, dict) else {}
        porosity = float(tongue.get("porosity", 0.0)) if isinstance(tongue, dict) else 0.0
        direction = str(tongue.get("direction", "") or "") if isinstance(tongue, dict) else ""
        training_weight_vectors = tongue.get("training_weight_vectors") if isinstance(tongue, dict) else {}
        past_state = states.get("past", "") if isinstance(states, dict) else ""
        present_state = states.get("present", "") if isinstance(states, dict) else ""
        future_state = states.get("future", "") if isinstance(states, dict) else ""
        lines = [
            oracle_label,
            response_text,
            "Past",
            past_state,
            "Present",
            present_state,
            "Future",
            future_state,
            "Resolved Emotion",
            "",
            f"{resolved_emotion:.2f}",
            "CONSULT",
            "Response",
            f"{canonical_tick_ms:.0f}ms",
            "Past Reflection",
            reflections.get("past", ""),
            "Present Reflection",
            reflections.get("present", ""),
            "Future Reflection",
            reflections.get("future", ""),
            "Hexagram Sequence",
            sequence_text,
            "Reaction Frame",
            reaction or "",
            "Unified Oracle Weave",
            reflections.get("present", ""),
            "Emotional Tongue",
            json.dumps(tongue, ensure_ascii=False) if tongue else "",
        ]
        if porosity:
            lines.extend(["Porosity", f"{porosity:.2f}"])
        if direction:
            lines.extend(["Direction", direction])
        if training_weight_vectors:
            lines.extend(["Training Weight Vectors", json.dumps(training_weight_vectors, ensure_ascii=False)])
        return "\n".join(lines)

    def format_oracle_console_with_tongue(self, payload: Dict[str, Any]) -> str:
        """Render the Oracle Console with tongue-only past/present/future as the primary timeline."""
        reflections = payload.get("reflections", {}) if isinstance(payload, dict) else {}
        deltas = payload.get("emotional_deltas", {}) if isinstance(payload, dict) else {}
        resolved_emotion = float(deltas.get("coherence", 0.0))
        reaction = payload.get("reaction_frame") if isinstance(payload, dict) else ""
        hexagram_sequence = payload.get("hexagram_sequence") if isinstance(payload, dict) else []
        sequence_text = " → ".join(hexagram_sequence) if hexagram_sequence else ""
        tongue = payload.get("emotional_tongue") if isinstance(payload, dict) else {}
        states = tongue.get("states") if isinstance(tongue, dict) else {}
        porosity = float(tongue.get("porosity", 0.0)) if isinstance(tongue, dict) else 0.0
        direction = str(tongue.get("direction", "") or "") if isinstance(tongue, dict) else ""
        training_weight_vectors = tongue.get("training_weight_vectors") if isinstance(tongue, dict) else {}
        past_state = states.get("past", "") if isinstance(states, dict) else ""
        present_state = states.get("present", "") if isinstance(states, dict) else ""
        future_state = states.get("future", "") if isinstance(states, dict) else ""
        lines = [
            "Oracle Console",
            "",
            "Past",
            past_state,
            "Present",
            present_state,
            "Future",
            future_state,
            "Resolved Emotion",
            "",
            f"{resolved_emotion:.2f}",
            "CONSULT",
            "Response",
            "640ms",
            "Past Reflection",
            reflections.get("past", ""),
            "Present Reflection",
            reflections.get("present", ""),
            "Future Reflection",
            reflections.get("future", ""),
            "Hexagram Sequence",
            sequence_text,
            "Reaction Frame",
            reaction or "",
            "Unified Oracle Weave",
            reflections.get("present", ""),
            "Emotional Tongue",
            json.dumps(tongue, ensure_ascii=False) if tongue else "",
        ]
        if porosity:
            lines.extend(["Porosity", f"{porosity:.2f}"])
        if direction:
            lines.extend(["Direction", direction])
        if training_weight_vectors:
            lines.extend(["Training Weight Vectors", json.dumps(training_weight_vectors, ensure_ascii=False)])
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Deterministic selector
    # ------------------------------------------------------------------

    def _select(self, text: str, session_id: str) -> int:
        """Deterministic hexagram selection."""
        seed = f"{session_id}:{text}".encode("utf-8")
        total = 0
        for byte in seed:
            total = (total * 31 + byte) % 2**31
        return (total % 64) + 1

    def get_kingwen_call_sign(self, text: str, session_id: str, hexagram_id: int, phase_bits: int) -> str:
        """Return a deterministic call sign for the active King Wen sequence.

        Format: ``KW:<hexagram_id>:<phase_bits>:<session_id>:<hash8>``

        This marker is intended as an injectable state token for downstream
        consumers that need to tag or route by the current ternary frame.
        """
        stable = self._stable_hash(f"{session_id}:{text}:{hexagram_id}:{phase_bits}")
        hash8 = f"{stable & 0xFFFFFFFF:08x}"
        return f"KW:{hexagram_id}:{phase_bits}:{session_id}:{hash8}"

    def getHexagram(self, text: str = "", session_id: str = "openjarvis", emotional_input: int = None, *, hexagram_id: int | None = None, phase_bits: int | None = None) -> Dict[str, Any]:
        """Return the requested hexagram state from the full expansion, or derive from consult when not explicitly selected."""
        if not text:
            raise ValueError("King Wen getHexagram requires non-empty text for deterministic state derivation.")
        if emotional_input is None:
            raise ValueError("King Wen getHexagram requires explicit emotional_input; pass a slider value.")
        collapse = self._collapse(text, session_id, emotional_input)
        expanded = collapse.get("expanded", [])
        resolved_index: Dict[tuple[int, int], Dict[str, Any]] = {}
        for item in collapse.get("resolved", []) or []:
            key = (int(item.get("hexagram_id") or 0), int(item.get("phase_bits") or 0))
            resolved_index[key] = item

        selected_entry: Dict[str, Any] = {}
        selected_phase: Dict[str, Any] = {}
        if hexagram_id is not None and phase_bits is not None:
            for item in expanded:
                if int(item.get("hexagram_id") or 0) == int(hexagram_id):
                    selected_entry = item
                    for ph in item.get("phases", []):
                        if int(ph.get("phase_bits") or -1) == int(phase_bits):
                            selected_phase = ph
                    break
        else:
            # No explicit selector: use first expanded entry as default carrier.
            # Caller must not interpret this as a collapse-to-1 winner.
            selected_entry = next(iter(expanded), {})
            selected_phase = next(iter(selected_entry.get("phases", [])), {})

        record = selected_entry.get("hexagram_symbols") or self._registry.get(str(hexagram_id or 1), {})
        weights = self._weights.get(str(hexagram_id or selected_entry.get("hexagram_id") or 1), {})
        ternary_entry = selected_phase.get("ternary_lines_top_to_bottom") and selected_phase or self._resolve_ternary_entry(int(hexagram_id or selected_entry.get("hexagram_id") or 1), int(phase_bits or 0))
        return {
            "hexagram_id": int(hexagram_id or selected_entry.get("hexagram_id") or 1),
            "hexagram_name": record.get("name", ""),
            "hexagram_unicode": record.get("unicode", ""),
            "binary": record.get("binary", ""),
            "upper_trigram": record.get("upper_trigram", ""),
            "lower_trigram": record.get("lower_trigram", ""),
            "category": record.get("category", ""),
            "action": record.get("action", ""),
            "phase_bits": int(phase_bits or selected_phase.get("phase_bits") or 0),
            "phase_temporal": selected_phase.get("phase_temporal") or ternary_entry.get("phase_temporal", ""),
            "ternary_str": selected_phase.get("ternary_str") or str(int(hexagram_id or 1) * 8 + int(phase_bits or 0)),
            "ternary_lines_top_to_bottom": selected_phase.get("ternary_lines_top_to_bottom") or ternary_entry.get("ternary_lines_top_to_bottom") or [],
            "phase_changing_lines": selected_phase.get("line_states") or ternary_entry.get("phase_changing_lines") or [],
            "call_sign": self.get_kingwen_call_sign(text, session_id, int(hexagram_id or selected_entry.get("hexagram_id") or 1), int(phase_bits or selected_phase.get("phase_bits") or 0)),
            "has_call_sign": True,
            "has_sequence": bool(collapse.get("hexagram_sequence")),
            "has_reaction": bool(collapse.get("reaction_frame")),
            "has_states": bool((collapse.get("emotional_tongue") or {}).get("states")),
            "has_vectors": bool((collapse.get("emotional_tongue") or {}).get("training_weight_vectors")),
            "has_tongue": bool(collapse.get("emotional_tongue")),
            "valid": self._ternary_to_bool(record.get("category") or collapse.get("action")),
            "success": True,
            "active": True,
            "voice_weight": float(weights.get("voiceWeight", 0.0)),
            "coherence": float(weights.get("coherence", 0.0)),
            "chaos": float(weights.get("chaos", 0.0)),
            "whimsy": float(weights.get("whimsy", 0.0)),
            "dark_tone": float(weights.get("darkTone", 0.0)),
            "selected_from_expanded": hexagram_id is not None and phase_bits is not None,
            "expanded_count": len(expanded),
            "resolved_count": len(collapse.get("resolved", []) or []),
        }

    def getEmotionalState(self, text: str = "", session_id: str = "openjarvis", emotional_input: int = None) -> Dict[str, Any]:
        """Return the current emotional-weight consensus from full 64-hex expansion.

        Uses the recorded ``collapse_full_128`` payload when available, so the
        returned state is derived from ``inject_site`` + ``yao_vocabulary`` +
        ``line_states`` + ``resolved_vector`` rather than 1-of-64 hash selection.
        """
        if not text:
            raise ValueError("King Wen getEmotionalState requires non-empty text for deterministic state derivation.")
        if emotional_input is None:
            raise ValueError("King Wen getEmotionalState requires explicit emotional_input; pass a slider value.")
        collapse = self._collapse(text, session_id, emotional_input)
        consensus = collapse.get("consensus") or {}
        vectors = consensus.get("vectors_mode") or consensus.get("vectors_mean") or {}
        return {
            "source": collapse.get("source"),
            "hexagram_id_mode": consensus.get("hexagram_id_mode"),
            "phase_temporal_mode": consensus.get("phase_temporal_mode"),
            "phase_polarity_mode": consensus.get("phase_polarity_mode"),
            "voice_weight": float(vectors.get("voiceWeight", 0.0)),
            "coherence": float(vectors.get("coherence", 0.0)),
            "chaos": float(vectors.get("chaos", 0.0)),
            "whimsy": float(vectors.get("whimsy", 0.0)),
            "dark_tone": float(vectors.get("darkTone", 0.0)),
            "vectors": {
                "voiceWeight": float(vectors.get("voiceWeight", 0.0)),
                "coherence": float(vectors.get("coherence", 0.0)),
                "chaos": float(vectors.get("chaos", 0.0)),
                "whimsy": float(vectors.get("whimsy", 0.0)),
                "darkTone": float(vectors.get("darkTone", 0.0)),
            },
            "porosity_mean": consensus.get("primary_porosity_mean"),
            "porosity_median": consensus.get("primary_porosity_median"),
            "porosity_mode": consensus.get("primary_porosity_mode"),
            "primary_pool_mode": consensus.get("primary_pool_mode"),
            "secondary_pool_mode": consensus.get("secondary_pool_mode"),
            "direction_mode": consensus.get("direction_mode"),
            "past_mode": consensus.get("past_mode"),
            "present_mode": consensus.get("present_mode"),
            "future_mode": consensus.get("future_mode"),
            "yao_label_mode": consensus.get("yao_label_mode"),
            "reasons": consensus.get("reasons") or [],
            "call_sign": self.get_kingwen_call_sign(text, session_id, int(consensus.get("hexagram_id_mode") or 1), 0),
            "has_call_sign": True,
            "has_sequence": True,
            "has_reaction": True,
            "has_states": True,
            "has_vectors": True,
            "has_tongue": True,
            "valid": True,
            "success": True,
            "active": True,
        }

    def inject_state(self, text: str, session_id: str, call_sign: str) -> Dict[str, Any]:
        """Inject a tagged King Wen state into the provider stream.

        The call sign must have been produced by :meth:`get_kingwen_call_sign`
        from a prior consult on the same text/session.  The tagged state is
        appended to the provider's internal consult history so downstream
        consumers can branch or return to it deterministically.
        """
        if not call_sign or not isinstance(call_sign, str):
            raise ValueError("King Wen inject_state requires a non-empty call_sign string.")
        prefix = f"KW:{session_id}:{text}:"
        token = call_sign if call_sign.startswith(prefix) else f"{prefix}{call_sign}"
        history = getattr(self, "_injected_history", None)
        if history is None:
            self._injected_history = []
            history = self._injected_history
        entry = {
            "text": text,
            "session_id": session_id,
            "call_sign": call_sign,
            "token": token,
            "injected_at": consciousness_tick(session_id, domain="cns").get("tick_id"),
        }
        history.append(entry)
        if len(history) > 64:
            del history[:-64]
        return {"injected": True, "token": token, "history_len": len(history)}

    @staticmethod
    def _ternary_to_bool(value: Any) -> bool:
        """Translate a King Wen ternary-ish value into a strict boolean.

        Truth contract:
        - numeric > 0 is True
        - non-empty string is True
        - integer 1 is True
        - integer 0 / empty / None / False is False
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    # ------------------------------------------------------------------
    # Domain lock: resolve Unicode + porosity/vectors into gating logic
    # ------------------------------------------------------------------

    def resolve_domain_lock_for_tool(
        self,
        unicode_char: str = "",
        porosity: float = 0.35,
        vectors: Optional[Dict[str, Any]] = None,
        *,
        tool_name: str = "",
        tool_category: str = "",
    ) -> Dict[str, Any]:
        """Resolve whether a tool call should be allowed under the active consult.

        The domain lock uses the King Wen save-string surface as its identity
        token: the canonical unicode glyph plus porosity plus emotional vectors.
        Existing gating mechanics in OpenJarvis (``ToolExecutor``, capability
        policy, boundary guard) remain the enforcement points; this method only
        produces the decision so those existing layers can act on it without
        knowing King Wen internals.

        Returns:
            Dict with ``allowed``, ``reason``, ``unicode``, ``porosity``,
            ``vectors``, and ``action``/``category`` when available.
        """
        registry = getattr(self, "_registry", {})
        hexagram_id = None
        if unicode_char:
            for rid, record in registry.items():
                if record.get("unicode") == unicode_char:
                    hexagram_id = int(rid)
                    break
        record = registry.get(str(hexagram_id), {}) if hexagram_id is not None else {}
        weights = registry.get("weights_map", {}) if hasattr(self, "_weights") else {}
        weights = self._weights.get(str(hexagram_id), {}) if hexagram_id is not None else {}
        action = str(record.get("action", weights.get("action", "")) or "").lower()
        category = str(record.get("category", weights.get("category", "")) or "").lower()
        tool_name_s = str(tool_name or "").lower()
        tool_category_s = str(tool_category or "").lower()
        vectors = vectors or {}
        coherence = float(vectors.get("coherence", 0.0))
        voice_weight = float(vectors.get("voiceWeight", 0.0))
        chaos = float(vectors.get("chaos", 0.0))
        whimsy = float(vectors.get("whimsy", 0.0))
        dark_tone = float(vectors.get("darkTone", 0.0))
        action_mismatch = bool(action and tool_name_s and action not in tool_name_s and tool_name_s not in action)
        category_mismatch = bool(category and tool_category_s and category not in tool_category_s and tool_category_s not in category)
        porosity_bonus = max(0.0, min(1.0, (porosity - 0.35) * 2.0))
        stability = max(0.0, min(1.0, (coherence + voice_weight) / 2.0))
        stability = stability + porosity_bonus * 0.1 - chaos * 0.2 - dark_tone * 0.15 + whimsy * 0.05
        if coherence < 0.25 or voice_weight < 0.35:
            allowed = False
            reason = (
                "King Wen domain lock: consult is too unstable to authorize tool use"
                f" (coherence={coherence:.2f}, voiceWeight={voice_weight:.2f})."
            )
        elif action_mismatch and category_mismatch and stability < 0.45:
            allowed = False
            wait = False
            reason = (
                "King Wen domain lock: tool intent conflicts with active consult frame"
                f" action={action or 'neutral'}, category={category or 'neutral'}."
            )
        elif action_mismatch and category_mismatch:
            allowed = True
            wait = False
            reason = (
                "King Wen domain lock: tool intent conflicts with active consult frame"
                f" action={action or 'neutral'}, category={category or 'neutral'}; allowing under explicit intent."
            )
        elif action_mismatch or category_mismatch:
            allowed = True
            wait = bool(stability < 0.55)
            reason = (
                "King Wen domain lock: partial mismatch on"
                f" action={action or 'neutral'}, category={category or 'neutral'}; monitor for drift."
            )
        else:
            allowed = True
            wait = bool(stability < 0.5)
            reason = "King Wen domain lock: tool aligns with active consult frame."
        return {
            "allowed": allowed,
            "wait": wait,
            "reason": reason,
            "unicode": unicode_char or "",
            "porosity": round(float(porosity), 4),
            "vectors": {
                "coherence": round(coherence, 4),
                "voiceWeight": round(voice_weight, 4),
                "chaos": round(chaos, 4),
                "whimsy": round(whimsy, 4),
                "darkTone": round(dark_tone, 4),
            },
            "action": action or "neutral",
            "category": category or "neutral",
            "stability": round(stability, 4),
        }
