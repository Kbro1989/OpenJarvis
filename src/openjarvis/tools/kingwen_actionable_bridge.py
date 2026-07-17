"""King Wen Actionable Bridge — Volition Translation Layer for Jarvis.

Bridges the 512-state King Wen oracle collapses directly into executable
Jarvis tools/actionables, and bundles research artifacts from:
  - Hermes (VHDL priority constraints and fault transitions)
  - Megatron (reputation and state capture mapping)
  - Voicebox (training profile payload exporter)
  - Schauberger (implosion mechanics and resonance tuning)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from enum import IntFlag
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nominal operational voice states from VHDL constraints
# ---------------------------------------------------------------------------
NOMINAL_STATES = {
    1: "idle",          # Creative - ready to speak
    2: "stealth",       # Receptive - listening mode
    8: "transit",       # Holding Together - consensus forming
    11: "tr_salt",      # Peace - stable advice
    12: "tr_crit",      # Standstill - high-stakes deliberation
    29: "limp",         # The Abysmal - degraded voice, minimal output
    58: "purge",        # The Joyous - channel reset
    52: "st_crit",      # Keeping Still - critical hold
}

# ---------------------------------------------------------------------------
# Fault Vector Flags (46-bit VHDL system mapped to 8-bit flag)
# ---------------------------------------------------------------------------
class FaultVector(IntFlag):
    NONE = 0x00
    INVALID_TRANSITION = 0x01
    ELEC_MISMATCH = 0x02
    SAFETY_VIOLATION = 0x04
    THERMAL_OVERRUN = 0x08
    PRESSURE_OUT = 0x10
    ARC_SUPPRESS = 0x20
    CHOKE_FAULT = 0x40
    SIC_FAULT = 0x80
    IMU_DECOHERENCE = 0x03
    GHOSTSPLAT_DIVERGENCE = 0x05
    TELEMETRY_TIMEOUT = 0x09
    UNKNOWN_STATE = 0xFF


# ---------------------------------------------------------------------------
# VHDL Transition Rules
# ---------------------------------------------------------------------------
def is_valid_transition(current_hex: int, next_hex: int) -> bool:
    """Validate transitions using constraints extracted from the VHDL machine.

    Ensures we don't jump between incompatible volition modes.
    """
    # Nominal transitions have strict paths
    if current_hex == 1:
        return next_hex in (2, 58)
    if current_hex == 2:
        return next_hex in (1, 8, 58)
    if current_hex == 8:
        return next_hex in (11, 12, 29)
    if current_hex == 11:
        return next_hex in (1, 8, 12)
    if current_hex == 12:
        return next_hex in (52, 29, 58)
    if current_hex == 58:
        return next_hex in (1, 2)
    
    # Fault states (not in NOMINAL_STATES) can transition to purge or stealth
    return next_hex in (2, 58, current_hex)


# ---------------------------------------------------------------------------
# The Actionable Bridge Tool
# ---------------------------------------------------------------------------
@ToolRegistry.register("kingwen_actionable_bridge")
class KingWenActionableBridgeTool(BaseTool):
    """Bridge King Wen oracle telemetry to Jarvis tools & training formats."""

    tool_id = "kingwen_actionable_bridge"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_actionable_bridge",
            description=(
                "Bridges King Wen hexagram states to Jarvis actionables, "
                "verifies VHDL transitions, and generates Voicebox/Schauberger resonance profiles."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "king_wen_id": {
                        "type": "integer",
                        "description": "King Wen Hexagram ID (1 to 64).",
                    },
                    "previous_king_wen_id": {
                        "type": "integer",
                        "description": "Previous King Wen Hexagram ID for VHDL checks.",
                        "default": 1,
                    },
                    "temporal_phase": {
                        "type": "string",
                        "enum": ["past", "present", "future"],
                        "description": "Temporal phase of the oracle collapse.",
                    },
                    "chaos": {
                        "type": "number",
                        "description": "Intent chaos sub-vector weight [0-1].",
                        "default": 0.5,
                    },
                    "whimsy": {
                        "type": "number",
                        "description": "Intent whimsy sub-vector weight [0-1].",
                        "default": 0.5,
                    },
                    "darkTone": {
                        "type": "number",
                        "description": "Intent darkTone sub-vector weight [0-1].",
                        "default": 0.5,
                    },
                    "coherence": {
                        "type": "number",
                        "description": "Intent coherence sub-vector weight [0-1].",
                        "default": 0.5,
                    },
                    "voiceWeight": {
                        "type": "number",
                        "description": "Intent voiceWeight sub-vector weight [0-1].",
                        "default": 0.5,
                    },
                },
                "required": ["king_wen_id", "temporal_phase"],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            king_wen_id = int(params.get("king_wen_id", 1))
            prev_id = int(params.get("previous_king_wen_id", 1))
            phase = str(params.get("temporal_phase", "present"))
            
            chaos = float(params.get("chaos", 0.5))
            whimsy = float(params.get("whimsy", 0.5))
            dark_tone = float(params.get("darkTone", 0.5))
            coherence = float(params.get("coherence", 0.5))
            voice_weight = float(params.get("voiceWeight", 0.5))

            # 1. TRANSLATION TO JARVIS ACTIONABLE
            actionable = self._map_to_actionable(king_wen_id, phase, chaos, whimsy, dark_tone, coherence)

            # 2. HERMES VHDL TRANSITION VALIDITY CHECK
            transition_ok = is_valid_transition(prev_id, king_wen_id)
            faults = FaultVector.NONE
            if not transition_ok:
                faults |= FaultVector.INVALID_TRANSITION
            if chaos > 0.8:
                faults |= FaultVector.THERMAL_OVERRUN
            if coherence < 0.2:
                faults |= FaultVector.ELEC_MISMATCH

            # 3. SCHAUBERGER IMPLOSION RESONANCE CALCULATIONS
            schauberger = self._compute_schauberger(king_wen_id, chaos, whimsy, coherence)

            # 4. VOICEBOX PROFILE PAYLOAD GENERATION
            voicebox = self._generate_voicebox_payload(king_wen_id, phase, chaos, whimsy, dark_tone, coherence, voice_weight)

            result_data = {
                "king_wen_id": king_wen_id,
                "temporal_phase": phase,
                "volition_bridge": {
                    "mapped_tool": actionable["tool"],
                    "parameters": actionable["parameters"],
                    "confidence": round(coherence * (1 - chaos), 4),
                },
                "hermes_layer": {
                    "previous_id": prev_id,
                    "transition_valid": transition_ok,
                    "voice_mode": NOMINAL_STATES.get(king_wen_id, "recovery/fault_hold"),
                    "fault_vector": int(faults),
                    "fault_names": [f.name for f in FaultVector if f != FaultVector.NONE and f in faults],
                },
                "schauberger_metrics": schauberger,
                "voicebox_payload": voicebox,
                "timestamp": time.time(),
            }

            return ToolResult(
                success=True,
                output=json.dumps(result_data, indent=2),
                metadata=result_data,
            )

        except Exception as exc:
            LOGGER.error("Failed to execute King Wen actionable bridge: %s", exc)
            return ToolResult(
                success=False,
                error=f"Bridge execution failed: {exc}",
            )

    def _map_to_actionable(
        self,
        hex_id: int,
        phase: str,
        chaos: float,
        whimsy: float,
        dark_tone: float,
        coherence: float,
    ) -> Dict[str, Any]:
        """Translates King Wen parameters into specific Jarvis tool invocations."""
        
        # Categorize action profile based on hexagram properties
        is_sovereign = hex_id in (1, 11, 26, 34, 43, 58)
        is_boundary = hex_id in (2, 8, 12, 18, 33, 52)
        is_transformer = not (is_sovereign or is_boundary)

        # Decide dominant volition pattern
        if coherence > 0.7:
            # ASSERTIVE pattern
            if is_sovereign:
                return {
                    "tool": "shell_exec",
                    "parameters": {
                        "command": f"echo 'Executing sovereign assertion for hexagram #{hex_id} ({phase})'",
                    }
                }
            elif is_boundary:
                return {
                    "tool": "file_write",
                    "parameters": {
                        "path": f"C:/Users/krist/Desktop/OpenJarvis/scratch/volition_hex_{hex_id}.txt",
                        "content": f"Volition boundary write. Coherence={coherence:.2f}\n",
                        "overwrite": True,
                    }
                }
            else:
                return {
                    "tool": "code_interpreter",
                    "parameters": {
                        "code": f"print('Executing code completion for hexagram {hex_id}')\n",
                    }
                }
        elif chaos > 0.6:
            # ADAPTIVE/DIVERGENT pattern
            if whimsy > 0.5:
                return {
                    "tool": "web_search",
                    "parameters": {
                        "query": f"King Wen hexagram {hex_id} narrative analogy",
                    }
                }
            else:
                return {
                    "tool": "think",
                    "parameters": {
                        "thought": f"Oracle state {hex_id} is in high-chaos ({chaos:.2f}) tension. Deferring to analysis loop.",
                    }
                }
        else:
            # PASSIVE/YIELDING pattern
            if dark_tone > 0.6:
                return {
                    "tool": "digest_collect",
                    "parameters": {
                        "mode": "detailed",
                    }
                }
            else:
                return {
                    "tool": "file_read",
                    "parameters": {
                        "path": "C:/Users/krist/Desktop/OpenJarvis/README.md",
                    }
                }

    def _compute_schauberger(
        self,
        hex_id: int,
        chaos: float,
        whimsy: float,
        coherence: float,
    ) -> Dict[str, float]:
        """Calculates Viktor Schauberger implosion/resonance vectors from weights."""
        
        # Spiral vortex tension: interaction between upper and lower halves of hexagram ID
        upper = (hex_id >> 3) & 0b111
        lower = hex_id & 0b111
        vortex_tension = round((upper * lower) / 49.0, 4)

        # Suction coefficient (biological vacuum)
        suction = round(chaos * whimsy * (1.0 - coherence), 4)

        # Temperature deviation from 4C anomaly point
        temp_dev = round(abs(chaos * 10.0 - 4.0), 4)
        anomaly_resonance = round(math.exp(-temp_dev), 4)

        # Egg-form resonance (peaked at center-weighted hexagram IDs)
        dist_to_center = abs(hex_id - 32.5)
        egg_resonance = round(math.exp(-dist_to_center / 16.0), 4)

        # Motion type: centripetal (creative/converging) vs centrifugal (entropy/diverging)
        motion_balance = coherence - chaos
        motion_type = "centripetal" if motion_balance >= 0 else "centrifugal"

        return {
            "vortex_tension": vortex_tension,
            "biological_suction": suction,
            "temperature_deviation": temp_dev,
            "anomaly_resonance": anomaly_resonance,
            "egg_form_resonance": egg_resonance,
            "motion_balance": round(motion_balance, 4),
            "motion_type_label": 1.0 if motion_type == "centripetal" else 0.0,
        }

    def _generate_voicebox_payload(
        self,
        hex_id: int,
        phase: str,
        chaos: float,
        whimsy: float,
        dark_tone: float,
        coherence: float,
        voice_weight: float,
    ) -> Dict[str, Any]:
        """Exposes Voicebox compatible profile metadata payload for speech synthesis."""
        return {
            "profile_id": f"kingwen_{hex_id}_{phase}",
            "pitch_modulator": round(1.0 + (whimsy - 0.5) * 0.4, 4),
            "speed_rate": round(1.0 - (dark_tone - 0.5) * 0.3, 4),
            "amplitude_gain": round(0.5 + voice_weight * 0.5, 4),
            "spectral_tilt": round((chaos - 0.5) * 0.2, 4),
            "vocal_register": "sovereign" if hex_id in (1, 11) else "whisper" if dark_tone > 0.7 else "normal",
        }
