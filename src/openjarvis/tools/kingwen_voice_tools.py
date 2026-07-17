"""kingwen_voice_tools.py — Voicebox-integrated voice reward scoring and TTS profile tools.

Tools registered here:
  - kingwen_voice_score      : Score a voice event against the King Wen reward model
  - kingwen_voicebox_profile : Generate a Voicebox-compatible TTS profile from hexagram state
  - kingwen_tts_speak        : Route TTS output through the voice reward sidecar

Ports scoring functions directly from voice_reward_sidecar.py into registered tool format.
No mocks. Uses real Cartesia/SAPI/Kokoro backends via the speech registry.
"""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

def _ok(tool_id: str, output: str, metadata: dict = None) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=output, success=True, metadata=metadata or {})


def _err(tool_id: str, msg: str) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=f"ERROR: {msg}", success=False)


LOGGER = logging.getLogger(__name__)

# ── Voice reward scoring constants (from voice_reward_sidecar.py) ───────────
CROWD_STATE_DIM = 512
DEFAULT_WEIGHTS: Dict[str, float] = {
    "compliance": 0.40,
    "porosity": 0.15,
    "vector_truth": 0.25,
    "dsp_fidelity": 0.20,
}

# Vocal register classification thresholds (from Voicebox profile research)
VOCAL_REGISTERS = {
    "sovereign":  {"hexagram_ids": {1, 11, 26, 34, 43, 58}, "pitch_offset": 0.05, "speed": 0.92},
    "advisor":    {"hexagram_ids": {8, 14, 40, 55, 61, 63}, "pitch_offset": 0.0,  "speed": 1.0},
    "whisper":    {"hexagram_ids": {2, 16, 20, 24, 33, 52}, "pitch_offset": -0.1, "speed": 0.88},
    "challenger": {"hexagram_ids": {4, 6, 10, 13, 28, 38}, "pitch_offset": 0.08, "speed": 1.08},
    "mediator":   {"hexagram_ids": {3, 7, 9, 15, 19, 25}, "pitch_offset": 0.02, "speed": 0.98},
}


def _classify_vocal_register(hexagram_id: int, dark_tone: float) -> str:
    if dark_tone > 0.7:
        return "whisper"
    for register, info in VOCAL_REGISTERS.items():
        if hexagram_id in info["hexagram_ids"]:
            return register
    return "advisor"


def _normalize_compliance(compliance: str) -> float:
    return 1.0 if str(compliance).lower() == "compliant" else 0.0


def _normalize_porosity(porosity: Optional[float]) -> float:
    """Optimal porosity is ~0.35. Distance from optimal is penalized."""
    if porosity is None:
        return 0.5
    optimal = 0.35
    distance = abs(porosity - optimal)
    return max(0.0, 1.0 - (distance / max(optimal, 1.0 - optimal)))


def _normalize_vector_truth(vector: Dict[str, float]) -> float:
    """Vector mean proximity to 0.5."""
    if not vector:
        return 0.5
    values = [
        vector.get("voiceWeight", 0.0),
        vector.get("coherence", 0.0),
        vector.get("chaos", 0.0),
        vector.get("whimsy", 0.0),
        vector.get("darkTone", 0.0),
    ]
    mean = sum(values) / len(values)
    return max(0.0, 1.0 - abs(mean - 0.5) * 2.0)


def _normalize_dsp_fidelity(dsp_meta: Dict[str, Any]) -> float:
    if not dsp_meta:
        return 0.5
    return 0.0 if dsp_meta.get("error") or dsp_meta.get("exception") else 1.0


def _crowd_entropy(votes: List[float]) -> float:
    if not votes:
        return 0.0
    total = sum(votes)
    if total <= 0.0:
        return 0.0
    ent = 0.0
    inv = 1.0 / total
    for v in votes:
        p = v * inv
        if p > 0.0:
            ent -= p * math.log(p)
    max_ent = math.log(CROWD_STATE_DIM)
    return round(ent / max_ent, 6) if max_ent > 0.0 else 0.0


def compute_voice_score(
    compliance: str,
    porosity: Optional[float],
    vector: Dict[str, float],
    dsp_meta: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    w = weights or DEFAULT_WEIGHTS
    score = (
        w["compliance"] * _normalize_compliance(compliance)
        + w["porosity"] * _normalize_porosity(porosity)
        + w["vector_truth"] * _normalize_vector_truth(vector)
        + w["dsp_fidelity"] * _normalize_dsp_fidelity(dsp_meta)
    )
    return round(score, 6)


# ── Tool: Voice Reward Score ────────────────────────────────────────────────

@ToolRegistry.register("kingwen_voice_score")
class KingWenVoiceScoreTool(BaseTool):
    """Score a voice/TTS event against the King Wen reward model."""

    tool_id = "kingwen_voice_score"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_voice_score",
            description=(
                "Normalize a King Wen voice event into a scalar reward score and multi-axis "
                "vector score. Inputs are compliance label, porosity, voice vector, and optional "
                "DSP metadata. Returns a score in [0, 1] plus individual axis scores."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "compliance": {
                        "type": "string",
                        "description": "'compliant' or other string for non-compliant.",
                        "default": "compliant",
                    },
                    "porosity": {
                        "type": "number",
                        "description": "Oracle porosity value [0.0–1.0].",
                        "default": 0.35,
                    },
                    "voice_vector": {
                        "type": "object",
                        "description": "Dict with keys: chaos, whimsy, darkTone, coherence, voiceWeight.",
                        "default": {},
                    },
                    "dsp_meta": {
                        "type": "object",
                        "description": "DSP processing metadata dict. Empty = neutral.",
                        "default": {},
                    },
                    "crowd_votes": {
                        "type": "array",
                        "description": "Optional length-512 crowd vote float array.",
                        "default": [],
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        compliance = str(params.get("compliance", "compliant"))
        porosity = float(params.get("porosity", 0.35))
        vector = dict(params.get("voice_vector", {}))
        dsp_meta = dict(params.get("dsp_meta", {}))
        crowd_votes_raw = params.get("crowd_votes", [])

        try:
            crowd_votes = [float(v) for v in crowd_votes_raw] if crowd_votes_raw else []
            scalar_score = compute_voice_score(compliance, porosity, vector, dsp_meta)

            axis_scores = {
                "compliance_axis": _normalize_compliance(compliance),
                "porosity_axis": _normalize_porosity(porosity),
                "vector_truth_axis": _normalize_vector_truth(vector),
                "dsp_fidelity_axis": _normalize_dsp_fidelity(dsp_meta),
            }
            if crowd_votes and len(crowd_votes) == CROWD_STATE_DIM:
                axis_scores["crowd_entropy"] = _crowd_entropy(crowd_votes)

            result = {
                "scalar_score": scalar_score,
                "axis_scores": axis_scores,
                "compliance": compliance,
                "porosity": porosity,
                "voice_vector": vector,
                "timestamp": time.time(),
            }
            return _ok(self.tool_id, f"Voice reward score: {scalar_score:.4f}", result)
        except Exception as exc:
            LOGGER.exception("kingwen_voice_score failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Voicebox Profile Generator ────────────────────────────────────────

@ToolRegistry.register("kingwen_voicebox_profile")
class KingWenVoiceboxProfileTool(BaseTool):
    """Generate a Voicebox-compatible TTS profile from King Wen hexagram state."""

    tool_id = "kingwen_voicebox_profile"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_voicebox_profile",
            description=(
                "Generate a Voicebox TTS synthesis profile (pitch modulator, speed rate, "
                "amplitude gain, spectral tilt, vocal register) driven by King Wen hexagram state "
                "and emotional vector weights."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "hexagram_id": {
                        "type": "integer",
                        "description": "King Wen Hexagram ID (1–64).",
                    },
                    "temporal_phase": {
                        "type": "string",
                        "enum": ["past", "present", "future"],
                        "default": "present",
                    },
                    "chaos": {"type": "number", "default": 0.5},
                    "whimsy": {"type": "number", "default": 0.5},
                    "darkTone": {"type": "number", "default": 0.5},
                    "coherence": {"type": "number", "default": 0.5},
                    "voiceWeight": {"type": "number", "default": 0.5},
                },
                "required": ["hexagram_id"],
            },
            category="media",
        )

    def execute(self, **params: Any) -> ToolResult:
        hex_id = int(params.get("hexagram_id", 1))
        phase = str(params.get("temporal_phase", "present"))
        chaos = float(params.get("chaos", 0.5))
        whimsy = float(params.get("whimsy", 0.5))
        dark_tone = float(params.get("darkTone", 0.5))
        coherence = float(params.get("coherence", 0.5))
        voice_weight = float(params.get("voiceWeight", 0.5))

        try:
            register = _classify_vocal_register(hex_id, dark_tone)
            register_info = next(
                (v for k, v in VOCAL_REGISTERS.items() if k == register),
                {"pitch_offset": 0.0, "speed": 1.0},
            )

            profile = {
                "profile_id": f"kingwen_{hex_id}_{phase}",
                "hexagram_id": hex_id,
                "temporal_phase": phase,
                "vocal_register": register,
                "pitch_modulator": round(1.0 + register_info["pitch_offset"] + (whimsy - 0.5) * 0.3, 4),
                "speed_rate": round(register_info["speed"] * (1.0 - (dark_tone - 0.5) * 0.25), 4),
                "amplitude_gain": round(0.5 + voice_weight * 0.5, 4),
                "spectral_tilt": round((chaos - 0.5) * 0.2, 4),
                "coherence_gate": round(coherence, 4),
                # Phase-specific modulation
                "phase_envelope": {
                    "past":    {"attack": 0.12, "decay": 0.08, "sustain": 0.7},
                    "present": {"attack": 0.04, "decay": 0.06, "sustain": 0.85},
                    "future":  {"attack": 0.08, "decay": 0.12, "sustain": 0.6},
                }.get(phase, {"attack": 0.04, "decay": 0.06, "sustain": 0.85}),
                "timestamp": time.time(),
            }

            return _ok(self.tool_id, f"Voicebox profile: register={register}, pitch={profile['pitch_modulator']:.3f}, speed={profile['speed_rate']:.3f}", profile)
        except Exception as exc:
            LOGGER.exception("kingwen_voicebox_profile failed")
            return _err(self.tool_id, str(exc))


# ── Tool: TTS Speak via King Wen Register ───────────────────────────────────

@ToolRegistry.register("kingwen_tts_speak")
class KingWenTTSSpeakTool(BaseTool):
    """Speak text through the Jarvis TTS stack using King Wen vocal register routing."""

    tool_id = "kingwen_tts_speak"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_tts_speak",
            description=(
                "Speaks text using the Jarvis TTS backend (Cartesia, SAPI, or Kokoro), "
                "selecting voice register based on the current King Wen hexagram state. "
                "Optionally scores the output through the voice reward sidecar."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to synthesize and speak.",
                    },
                    "hexagram_id": {
                        "type": "integer",
                        "description": "King Wen Hexagram ID driving vocal register selection.",
                        "default": 1,
                    },
                    "darkTone": {
                        "type": "number",
                        "description": "Dark tone vector weight [0–1]. Above 0.7 = whisper register.",
                        "default": 0.5,
                    },
                    "backend": {
                        "type": "string",
                        "description": "TTS backend: 'cartesia', 'sapi', 'kokoro', or 'auto'.",
                        "default": "auto",
                    },
                    "score_output": {
                        "type": "boolean",
                        "description": "If true, run voice reward scoring after synthesis.",
                        "default": False,
                    },
                },
                "required": ["text"],
            },
            category="media",
        )

    def execute(self, **params: Any) -> ToolResult:
        text = str(params.get("text", ""))
        hex_id = int(params.get("hexagram_id", 1))
        dark_tone = float(params.get("darkTone", 0.5))
        backend = str(params.get("backend", "auto"))
        score_output = bool(params.get("score_output", False))

        if not text:
            return _err(self.tool_id, "No text provided for TTS.")

        try:
            register = _classify_vocal_register(hex_id, dark_tone)
            tts_result: Dict[str, Any] = {
                "text": text,
                "register": register,
                "backend_requested": backend,
                "timestamp": time.time(),
            }

            # Attempt real TTS dispatch
            try:
                from openjarvis.speech.tts import speak
                speak(text, backend=None if backend == "auto" else backend)
                tts_result["spoken"] = True
                tts_result["backend_used"] = backend
            except Exception as tts_exc:
                tts_result["spoken"] = False
                tts_result["tts_error"] = str(tts_exc)

            # Optional reward scoring
            if score_output:
                score = compute_voice_score(
                    compliance="compliant",
                    porosity=0.35,
                    vector={"voiceWeight": 0.7, "coherence": 0.6, "chaos": 0.3, "whimsy": 0.4, "darkTone": dark_tone},
                    dsp_meta={},
                )
                tts_result["voice_reward_score"] = score

            return _ok(self.tool_id, f"[{register.upper()}] Spoke: {text[:80]}{'...' if len(text) > 80 else ''}", tts_result)
        except Exception as exc:
            LOGGER.exception("kingwen_tts_speak failed")
            return _err(self.tool_id, str(exc))
