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

    def _collapse(self, text: str, session_id: str, emotional_input: int = 50) -> Dict[str, Any]:
        """Score all 64 hexagrams × 8 phases and return the best collapsed path plus its full winning state fragment.

        Uses per-candidate deterministic hashing so short strings do not all land on the same hexagram,
        while preserving emotional-weight influence and slider-based phase bias.
        """
        slider = emotional_input / 100.0
        best_score = -1.0
        best_hex = 1
        best_phase = 0
        for hexagram_id in range(1, 65):
            record = self._registry[str(hexagram_id)]
            weights = self._weights.get(str(hexagram_id), {})
            name = record.get("name", "")
            voice = float(weights.get("voiceWeight", 0.0))
            coherence = float(weights.get("coherence", 0.0))
            emotional_alignment = voice * 0.6 + coherence * 0.4
            for phase_bits in range(8):
                # Per-candidate full hash so identical short strings still spread across the 512-state space.
                seed = self._stable_hash(f"{hexagram_id}:{phase_bits}:{session_id}:{text}")
                hash_term = (seed % 1_000_000) / 1_000_000.0
                # Name proximity only as a minor curiosity bonus, not a dominant selector.
                name_hash = self._stable_hash(name)
                name_proximity = 1.0 - abs(
                    ((self._stable_hash(f"{session_id}:{text}") % 1_000_000) / 1_000_000.0)
                    - ((name_hash % 1_000_000) / 1_000_000.0)
                )
                phase_fit = 1.0 - abs(phase_bits / 7.0 - slider)
                score = hash_term * 0.5 + emotional_alignment * 0.3 + phase_fit * 0.15 + name_proximity * 0.05
                if score > best_score:
                    best_score = score
                    best_hex = hexagram_id
                    best_phase = phase_bits
        winning_entry = self._resolve_ternary_entry(best_hex, best_phase)
        tongue = self._resolve_emotion_tongue(best_hex, session_id)
        return {
            "best_hex": best_hex,
            "best_phase": best_phase,
            "score": best_score,
            "winning_entry": winning_entry,
            "emotional_tongue": tongue,
        }

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
        emotional_input: int = 50,
    ) -> Dict[str, Any]:
        """Return a deterministic emotional-state response for prompt injection."""
        if not text:
            raise ValueError("King Wen consult requires non-empty text for deterministic session-state derivation.")
        collapse = self._collapse(text, session_id, emotional_input)
        hexagram_id = int(collapse.get("best_hex") or 1)
        phase_bits = int(collapse.get("best_phase") or 0)
        record = self._registry[str(hexagram_id)]
        weights = self._weights.get(str(hexagram_id), {})
        reflections = self._reflections.get(str(hexagram_id), {})
        ternary_entry = collapse.get("winning_entry") or {}
        if not ternary_entry:
            ternary_entry = self._resolve_ternary_entry(hexagram_id, phase_bits)
        primary_name = record.get("name", "")
        primary_unicode = record.get("unicode", "")
        secondary_id = ternary_entry.get("hexagram_id")
        secondary_name = ternary_entry.get("hexagram_name") if secondary_id != hexagram_id else ""
        secondary_unicode = ternary_entry.get("hexagram_unicode") if secondary_id != hexagram_id else ""
        hexagram_sequence = [primary_name]
        if secondary_name and secondary_name != primary_name:
            hexagram_sequence.append(secondary_name)
        payload: Dict[str, Any] = {
            "hexagram_id": hexagram_id,
            "hexagram_name": primary_name,
            "hexagram_unicode": primary_unicode,
            "binary": record.get("binary", ""),
            "upper_trigram": record.get("upper_trigram", ""),
            "lower_trigram": record.get("lower_trigram", ""),
            "category": record.get("category", ""),
            "action": record.get("action", ""),
            "hexagram_sequence": hexagram_sequence,
            "phase_bits": phase_bits,
            "phase_temporal": ternary_entry.get("phase_temporal", ""),
            "phase_description": ternary_entry.get("phase_description", ""),
            "ternary_str": ternary_entry.get("ternary_str", ""),
            "ternary_lines_top_to_bottom": ternary_entry.get("ternary_lines_top_to_bottom", []),
            "phase_changing_lines": ternary_entry.get("phase_changing_lines") or [],
            "reaction_frame": self._format_reaction_frame(ternary_entry) if ternary_entry else "",
            "emotional_deltas": {
                "chaos": float(weights.get("chaos", 0.0)),
                "whimsy": float(weights.get("whimsy", 0.0)),
                "darkTone": float(weights.get("darkTone", 0.0)),
                "coherence": float(weights.get("coherence", 0.0)),
                "voiceWeight": float(weights.get("voiceWeight", 0.0)),
            },
            "reflections": {
                "past": reflections.get("past", ""),
                "present": reflections.get("present", ""),
                "future": reflections.get("future", ""),
            },
            "trainingNotes": weights.get("trainingNotes", ""),
            "emotional_tongue": collapse.get("emotional_tongue") or {},
        }
        if secondary_name:
            payload["secondary_hexagram"] = {
                "id": secondary_id,
                "name": secondary_name,
                "unicode": secondary_unicode,
            }
        return payload

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

    def getHexagram(self, text: str = "", session_id: str = "openjarvis", emotional_input: int = 50) -> Dict[str, Any]:
        """Return the current hexagram state resolved from the active consult.

        This is the King Wen “now” signal: full ternary entry plus registry
        metadata, without re-emitting the full Oracle Console formatting.
        """
        if not text:
            raise ValueError("King Wen getHexagram requires non-empty text for deterministic state derivation.")
        collapse = self._collapse(text, session_id, emotional_input)
        hexagram_id = int(collapse.get("best_hex") or 1)
        phase_bits = int(collapse.get("best_phase") or 0)
        record = self._registry[str(hexagram_id)]
        weights = self._weights.get(str(hexagram_id), {})
        ternary_entry = collapse.get("winning_entry") or self._resolve_ternary_entry(hexagram_id, phase_bits)
        return {
            "hexagram_id": hexagram_id,
            "hexagram_name": record.get("name", ""),
            "hexagram_unicode": record.get("unicode", ""),
            "binary": record.get("binary", ""),
            "upper_trigram": record.get("upper_trigram", ""),
            "lower_trigram": record.get("lower_trigram", ""),
            "category": record.get("category", ""),
            "action": record.get("action", ""),
            "phase_bits": phase_bits,
            "phase_temporal": ternary_entry.get("phase_temporal", ""),
            "ternary_str": ternary_entry.get("ternary_str", ""),
            "ternary_lines_top_to_bottom": ternary_entry.get("ternary_lines_top_to_bottom") or [],
            "phase_changing_lines": ternary_entry.get("phase_changing_lines") or [],
            "call_sign": self.get_kingwen_call_sign(text, session_id, hexagram_id, phase_bits),
            "voice_weight": float(weights.get("voiceWeight", 0.0)),
            "coherence": float(weights.get("coherence", 0.0)),
            "chaos": float(weights.get("chaos", 0.0)),
            "whimsy": float(weights.get("whimsy", 0.0)),
            "dark_tone": float(weights.get("darkTone", 0.0)),
        }

    def getEmotionalState(self, text: str = "", session_id: str = "openjarvis", emotional_input: int = 50) -> Dict[str, Any]:
        """Return the active emotional weight vectors for the current consult.

        The returned vectors are the exact values applied by the 512-state
        collapse, suitable for direct consumption by voice/routing layers.
        """
        if not text:
            raise ValueError("King Wen getEmotionalState requires non-empty text for deterministic state derivation.")
        collapse = self._collapse(text, session_id, emotional_input)
        hexagram_id = int(collapse.get("best_hex") or 1)
        weights = self._weights.get(str(hexagram_id), {})
        ternary_entry = collapse.get("winning_entry") or self._resolve_ternary_entry(hexagram_id, int(collapse.get("best_phase") or 0))
        return {
            "hexagram_id": hexagram_id,
            "phase_bits": int(collapse.get("best_phase") or 0),
            "phase_temporal": ternary_entry.get("phase_temporal", ""),
            "voice_weight": float(weights.get("voiceWeight", 0.0)),
            "coherence": float(weights.get("coherence", 0.0)),
            "chaos": float(weights.get("chaos", 0.0)),
            "whimsy": float(weights.get("whimsy", 0.0)),
            "dark_tone": float(weights.get("darkTone", 0.0)),
            "vectors": {
                "voiceWeight": float(weights.get("voiceWeight", 0.0)),
                "coherence": float(weights.get("coherence", 0.0)),
                "chaos": float(weights.get("chaos", 0.0)),
                "whimsy": float(weights.get("whimsy", 0.0)),
                "darkTone": float(weights.get("darkTone", 0.0)),
            },
            "call_sign": self.get_kingwen_call_sign(text, session_id, hexagram_id, int(collapse.get("best_phase") or 0)),
        }

    def inject_state(self, text: str, session_id: str, call_sign: str) -> Dict[str, Any]:
        """Inject a tagged King Wen state into the provider stream.

        The call sign must have been produced by :meth:`get_kingwen_call_sign`
        from a prior consult on the same text/session.  The tagged state is
        appended to the provider’s internal consult history so downstream
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
            "source": "inject_state",
        }
        history.append(entry)
        if len(history) > 64:
            del history[:-64]
        return entry
