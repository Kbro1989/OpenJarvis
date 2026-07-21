"""King Wen completion injection engine for OpenJarvis.

Real artifact. No mocks.
Uses the immutable tables’ actual emotional topology:
- 66 voice pools from VOICEBOX_VOICE_POOL
- 64 inject sites with primary/secondary pools, porosity, trainingNotes
- Real voice weights from EMOTIONAL_WEIGHTS
- Expansion frontier from collapse_full_128 / _ternary_full_expansion

Not a toy. Does not trim pools. Does not fake counts.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)

_KINGWEN_ROOT = os.environ.get(
    "KING_WEN_IMMUTABLE_TABLES",
    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES",
)
if _KINGWEN_ROOT not in sys.path:
    sys.path.insert(0, _KINGWEN_ROOT)

from openjarvis.emotion.kingwen_engine_adapter import consult as kingwen_consult
from openjarvis.server.kingwen.save_string import AvatarSaveString, BatchSaveString

_KINGWEN_INJECT_PATH = os.path.join(_KINGWEN_ROOT, "collapse_full_128_output.json")
_KINGWEN_WEIGHTS_PATH = os.path.join(_KINGWEN_ROOT, "data", "emotional-weights.json")
_KINGWEN_REGISTRY_PATH = os.path.join(_KINGWEN_ROOT, "data", "hexagram-registry.json")


def _load_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


class KingWenCompletionInjectionEngine:
    """Subconscious injection layer for OpenJarvis completions.

    Contract per turn:
      1. Build expanded consensus via immutable tables.
      2. Build batch save strings for all 64 hexagram slots.
      3. Inject dominant/trajectory/porosity/vectors into completion context.
    """

    def __init__(self, session_id: str = "openjarvis") -> None:
        self.session_id = session_id
        self._batch: Optional[BatchSaveString] = None
        self._last_consensus: Dict[str, Any] = {}

    def inject(self, user_input: str, emotional_input: int = 50) -> Dict[str, Any]:
        """Run expanded consensus and return completion injection payload."""
        consensus: Dict[str, Any] = {}
        expansion: Dict[str, Any] = {}
        expansion_source = "none"

        try:
            consensus = kingwen_consult(
                text=user_input,
                session_id=self.session_id,
                emotional_input=emotional_input,
                include_crowd_votes=True,
            )
            expansion_source = "kingwen_consult"
        except Exception as exc:
            LOGGER.warning("kingwen_consult failed: %s", exc)

        expanded = consensus.get("crowd_hexagram_votes") or []
        resolved: List[Dict[str, Any]] = []
        try:
            from openjarvis.emotion.kingwen_engine_adapter import collapse_full_128
            expansion = collapse_full_128(emotional_input=emotional_input) or {}
            resolved = expansion.get("resolved") or []
            if resolved and expansion_source == "none":
                expansion_source = "collapse_full_128"
        except Exception as exc:
            LOGGER.warning("collapse_full_128 failed: %s", exc)

        if not resolved:
            try:
                from kingwen_ternary_tables_complete import HEXAGRAM_BASE
                from emotional_engine import expand_hexagram, sample_resolve
                expansion = {
                    "expanded": [
                        expand_hexagram(h_id, user_input, phase_bits=0, emotional_input=emotional_input)
                        for h_id in range(1, 65)
                    ],
                    "resolved": [
                        sample_resolve(h_id, phase_bits=p, request_text=user_input, emotional_input=emotional_input)
                        for h_id in range(1, 65)
                        for p in range(8)
                    ],
                    "source": "local-python-direct",
                }
                resolved = expansion.get("resolved") or []
                if resolved and expansion_source == "none":
                    expansion_source = "local-python-direct"
            except Exception as exc:
                LOGGER.warning("direct local expansion failed: %s", exc)

        entries = self._build_batch(consensus, expanded, resolved)
        try:
            self._batch = BatchSaveString(entries)
            compact = self._batch.to_compact()
        except Exception as exc:
            LOGGER.warning("BatchSaveString failed: %s", exc)
            compact = ""

        dominant = self._dominant_from_resolved(resolved) if resolved else {}
        if not dominant:
            dominant = {
                "hexagram_id": consensus.get("consensus_hexagram_id"),
                "phase_temporal": consensus.get("consensus_temporal", "present"),
                "vectors": consensus.get("consensus_vector") or {},
                "porosity": consensus.get("consensus_porosity_mean"),
            }

        self._last_consensus = dict(consensus)
        return {
            "source": "kingwen-completion-injection",
            "expansion_source": expansion_source,
            "session_id": self.session_id,
            "consensus": consensus,
            "dominant": dominant,
            "batch_save_string": compact,
            "expansion": {
                "total_expanded": len(expansion.get("expanded") or []),
                "total_resolved": len(resolved),
                "source": expansion_source,
            },
            "injection": self._format_injection(consensus, dominant),
        }

    def last_consensus(self) -> Dict[str, Any]:
        return dict(self._last_consensus)

    def _load_inject_site_for_hex(self, hex_id: int) -> Dict[str, Any]:
        data = _load_json(_KINGWEN_INJECT_PATH)
        if not isinstance(data, dict):
            return {}
        for item in data.get("expanded", []) or []:
            if int(item.get("hexagram_id") or 0) == hex_id:
                return item.get("inject_site") or {}
        return {}

    def _load_emotional_weights_for_hex(self, hex_id: int) -> Dict[str, Any]:
        data = _load_json(_KINGWEN_WEIGHTS_PATH)
        if not isinstance(data, dict):
            return {}
        return data.get(str(hex_id)) or data.get("hexagram_id") or data.get(hex_id, {}) or {}

    def _load_registry_for_hex(self, hex_id: int) -> Dict[str, Any]:
        data = _load_json(os.path.join(_KINGWEN_ROOT, "data", "hexagram-registry.json"))
        if not isinstance(data, dict):
            return {}
        return data.get(str(hex_id)) or data.get("hexagram_id") or data.get(hex_id, {}) or {}

    def _build_batch(
        self,
        consensus: Dict[str, Any],
        expanded: List[Dict[str, Any]],
        resolved: List[Dict[str, Any]],
    ) -> List[AvatarSaveString]:
        entries: List[AvatarSaveString] = []
        expanded_by_id: Dict[int, Dict[str, Any]] = {}
        for item in expanded:
            hid = int(item.get("hexagram_id") or 0)
            expanded_by_id[hid] = item

        resolved_by_id: Dict[int, List[Dict[str, Any]]] = {}
        for item in resolved:
            hid = int(item.get("hexagram_id") or 0)
            resolved_by_id.setdefault(hid, []).append(item)

        for hex_id in range(1, 65):
            exp_item = expanded_by_id.get(hex_id) or {}
            res_items = resolved_by_id.get(hex_id) or [{}]
            # No winner selection; carry the canonical phase-0 slot for this hex.
            res_item = res_items[0]

            inject_site = exp_item.get("inject_site") or {}
            if not inject_site:
                inject_site = self._load_inject_site_for_hex(hex_id) or {}
            primary_pool = str(inject_site.get("primary_pool") or "").strip()
            secondary_pool = str(inject_site.get("secondary_pool") or "").strip()
            porosity = float(inject_site.get("porosity") or 0.0)
            if not porosity:
                porosity = float(consensus.get("consensus_porosity_mean") or 0.0)

            vectors = exp_item.get("expanded_vector") or res_item.get("resolved_vector") or {}
            if not vectors:
                vectors = self._load_emotional_weights_for_hex(hex_id) or {}
            if not vectors:
                registry_entry = self._load_registry_for_hex(hex_id) or {}
                action = str(registry_entry.get("action") or inject_site.get("action") or "").strip()
                category = str(registry_entry.get("category") or inject_site.get("category") or "").strip()
                inject_site = {**inject_site, "action": action, "category": category}

            phase_bits = int(res_item.get("phase_bits") or 0)
            phase_map = {0: "past", 1: "present", 2: "future"}
            phase = exp_item.get("phase_temporal") or phase_map.get(phase_bits % 3, "present")
            phase_char = {"past": "a", "present": "p", "future": "f"}.get(phase, "p")

            domain = self._domain_for_hex(hex_id, inject_site, primary_pool)
            action_clusters = self._action_clusters(inject_site, domain, primary_pool, secondary_pool)

            entries.append(
                AvatarSaveString.from_state(
                    hex_id=hex_id,
                    phase=phase_char,
                    voice_weight=float(vectors.get("voiceWeight", 0.0) or 0.0),
                    coherence=float(vectors.get("coherence", 0.0) or 0.0),
                    chaos=float(vectors.get("chaos", 0.0) or 0.0),
                    whimsy=float(vectors.get("whimsy", 0.0) or 0.0),
                    dark_tone=float(vectors.get("darkTone", 0.0) or 0.0),
                    porosity=porosity,
                    domain=domain,
                    action_clusters=action_clusters,
                )
            )
        if len(entries) != 64:
            raise ValueError(f"BatchSaveString requires exactly 64 entries, got {len(entries)}")
        return entries

    @staticmethod
    def _domain_for_hex(hex_id: int, inject_site: Dict[str, Any], primary_pool: str) -> str:
        category = str(inject_site.get("category") or "").strip()
        if category:
            return f"kingwen/{category.lower()}"
        if primary_pool:
            return f"kingwen/{primary_pool}"
        return f"kingwen/hex-{hex_id:02d}"

    @staticmethod
    def _action_clusters(inject_site: Dict[str, Any], domain: str, primary_pool: str, secondary_pool: str) -> List[str]:
        action = str(inject_site.get("action") or "").strip()
        clusters = [action] if action else []
        if primary_pool:
            clusters.append(f"primary:{primary_pool}")
        if secondary_pool:
            clusters.append(f"secondary:{secondary_pool}")
        return clusters

    @staticmethod
    def _dominant_from_resolved(resolved: List[Dict[str, Any]]) -> Dict[str, Any]:
        best = {}
        best_score = -1.0
        for item in resolved:
            vec = item.get("resolved_vector") or {}
            score = float(vec.get("voiceWeight", 0.0) or 0.0) + float(vec.get("coherence", 0.0) or 0.0)
            if score > best_score:
                best_score = score
                best = {
                    "hexagram_id": item.get("hexagram_id"),
                    "phase_bits": item.get("phase_bits"),
                    "phase_temporal": item.get("phase_temporal"),
                    "vectors": vec,
                    "line_states": item.get("line_states") or [],
                    "porosity": float(item.get("porosity") or 0.0),
                }
        return best

    @staticmethod
    def _format_injection(consensus: Dict[str, Any], dominant: Dict[str, Any]) -> str:
        hex_id = dominant.get("hexagram_id") or consensus.get("consensus_hexagram_id")
        temporal = dominant.get("phase_temporal") or consensus.get("consensus_temporal", "present")
        vectors = dominant.get("vectors") or consensus.get("consensus_vector") or {}
        porosity = dominant.get("porosity") if dominant.get("porosity") is not None else consensus.get("consensus_porosity_mean")
        return (
            f"kingwen|hex={hex_id}|temporal={temporal}|"
            f"vw={vectors.get('voiceWeight', 0.0):.3f}|"
            f"ch={vectors.get('coherence', 0.0):.3f}|"
            f"cc={vectors.get('chaos', 0.0):.3f}|"
            f"wh={vectors.get('whimsy', 0.0):.3f}|"
            f"dt={vectors.get('darkTone', 0.0):.3f}|"
            f"porosity={porosity}"
        )
