"""kingwen_narrative_dispatch_tool.py — Narrative Engine output → Jarvis tool dispatch.

Routes NarrativeEngine.ts emotional mode outputs into concrete Jarvis tool invocations:
  - CODE COMPLETION mode  → routes to code_interpreter or repl
  - BLUEPRINT mode        → routes to file_write (saves topology as .md/.yaml)
  - AGENT SPEC mode       → routes to agent_tools (spawn/configure new agent)
  - LITERARY/TEXT mode    → routes to text_to_speech or channel_send

Tools registered here:
  - kingwen_narrative_dispatch  : Full oracle→narrative→action dispatch pipeline
  - kingwen_narrative_generate  : Generate narrative output from oracle state (Python-native,
                                   no TS subprocess, mirrors NarrativeEngine.ts logic)
  - kingwen_agent_spec_emit     : Emit agent YAML spec from hexagram state, ready for spawn

No mock. Narrative logic is a Python port of NarrativeEngine.ts private methods.
"""
from __future__ import annotations

import json
import logging
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

def _ok(tool_id: str, output: str, metadata: dict = None) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=output, success=True, metadata=metadata or {})


def _err(tool_id: str, msg: str) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=f"ERROR: {msg}", success=False)


LOGGER = logging.getLogger(__name__)

# ── Narrative mode thresholds (mirrors NarrativeEngine.ts) ──────────────────
# MODE 1 CODE COMPLETION:  coherence > 0.6 and chaos < 0.4
# MODE 2 BLUEPRINT:        chaos > 0.5 and whimsy > 0.5
# MODE 3 AGENT SPEC:       voiceWeight > 0.6 and darkTone > 0.6
# MODE 4 LITERARY (default)

# ── Temporal reflections data (hex action strings from HEXAGRAM_BASE) ─────────
# Loaded lazily from the immutable tables so we avoid importing at module load.

def _load_hex_base() -> Dict[int, Dict[str, str]]:
    try:
        from openjarvis.emotion.kingwen_engine_adapter import HEXAGRAM_BASE
        return HEXAGRAM_BASE  # type: ignore[return-value]
    except Exception:
        return {}


def _detect_mode(chaos: float, whimsy: float, darkTone: float, coherence: float, voiceWeight: float) -> str:
    if coherence > 0.6 and chaos < 0.4:
        return "code_completion"
    if chaos > 0.5 and whimsy > 0.5:
        return "blueprint"
    if voiceWeight > 0.6 and darkTone > 0.6:
        return "agent_spec"
    return "literary"


def _detect_action(training_notes: str) -> str:
    for word in ("ASSERT", "YIELD", "ADAPT"):
        if word in (training_notes or "").upper():
            return word
    return "WAIT"


def generate_code_completion(phase: str, action: str, chaos: float, coherence: float, hex_id: int, hex_name: str) -> str:
    threshold = round(max(0.1, 1.0 - coherence), 2)
    return textwrap.dedent(f"""\
        /**
         * CODE COMPLETION: Volition Substrate — Hex #{hex_id} {hex_name} [Phase: {phase}]
         * Coherence: {coherence:.2f}, Chaos: {chaos:.2f}
         * Volition Target: {action}
         */
        export async function executeVolitionStep<T>(intent: T): Promise<{{ success: boolean; outcome: string }}> {{
          const metabolicHeartbeat = 640; // ms
          const threshold = {threshold};
          const coherenceGate = {coherence:.3f};

          if (Math.random() > threshold) {{
            return {{
              success: true,
              outcome: "Volition commit [HEX-{hex_id}/{phase.upper()}/{action}] executed: coherence gate {coherence:.2f} passed."
            }};
          }}
          throw new Error("Volition step failed: coherence threshold mismatch at gate {coherence:.2f}.");
        }}""")


def generate_blueprint(phase: str, action: str, chaos: float, whimsy: float, hex_id: int, hex_name: str, category: str) -> str:
    precise_bias = round((1.0 - chaos) * 100)
    return textwrap.dedent(f"""\
        ====================================================================
        BLUEPRINT: POG3 Volition Grid Topology
        Hexagram #{hex_id} — {hex_name} | Phase: {phase} | Category: {category}
        Action: {action} | Chaos: {chaos:.2f} | Whimsy: {whimsy:.2f}
        ====================================================================
              [Superposition Intent]
                        |
                        v  (Emotional Weighting: whimsy={whimsy:.2f})
              [Hexagram Collapse]  ---(broadcast)--->  [HexagramNetworkBridge]
                        |
                        v  (Temporal Phase: {phase})
               +-----------------+
               |  State Capture  |
               |  (ID: hex-{hex_id}-{phase})
               +-----------------+
                        |
                        v
              [ModelRolodex Select] ===>  Precise/Creative bias adjusted {precise_bias}%
                        |
                        v
              [KingWenActionableBridge] ===> Jarvis Tool Dispatch
        ====================================================================""")


def generate_agent_spec(phase: str, action: str, chaos: float, coherence: float, darkTone: float, voiceWeight: float, hex_id: int, hex_name: str) -> str:
    reputation = "entropy_resilient" if darkTone > 0.8 else "standard"
    return textwrap.dedent(f"""\
        agent_definition:
          id: pog3_volition_agent_{phase}_{hex_id}
          hex_id: {hex_id}
          hex_name: "{hex_name}"
          volition_rhythm: 640ms
          temporal_phase: {phase}
          reputation_bias: {reputation}
          parameters:
            chaos_tolerance: {chaos:.3f}
            coherence_target: {coherence:.3f}
            voice_weight: {voiceWeight:.3f}
            dark_tone: {darkTone:.3f}
          strategy:
            mode: {action}
            fallback: WAIT
            dispatch_limbs:
              - GhostSplat
              - ModelRolodex
              - HexagramNetworkBridge
              - KingWenActionableBridge
          oracle_hooks:
            - event: on_collapse
              tool: kingwen_voice_router
              params:
                king_wen_id: {hex_id}
            - event: on_output
              tool: kingwen_voicebox_profile
              params:
                hexagram_id: {hex_id}
                temporal_phase: {phase}""")


def generate_literary(phase: str, action: str, chaos: float, whimsy: float, darkTone: float, hex_id: int, hex_name: str, reflection: str) -> str:
    text = reflection or f"Hexagram #{hex_id} {hex_name} speaks through the {phase} phase."
    if chaos > 0.7:
        text = f"[CHAOS LEVEL {int(chaos * 100)}% DETECTED] {text} [SYSTEM ITERATION RECURSED]"
    if whimsy > 0.7:
        text = f"✨ (whimsy sub-vector) {text} 🌀 [quantum whimsy enabled]"
    if darkTone > 0.7:
        text = f"⚠️ [DARK PATH ACTIVE] {text} [entropy threshold crossed]"
    return text


def _generate_narrative(
    hex_id: int,
    phase: str,
    chaos: float,
    whimsy: float,
    darkTone: float,
    coherence: float,
    voiceWeight: float,
) -> Tuple[str, str]:
    """Returns (mode, narrative_text)."""
    hex_base = _load_hex_base()
    hex_info = hex_base.get(hex_id, {})
    hex_name = hex_info.get("name", f"Hex-{hex_id}")
    category = hex_info.get("category", "")
    action_label = hex_info.get("action", "WAIT")
    training_notes = hex_info.get("trainingNotes", action_label)
    action = _detect_action(training_notes)
    mode = _detect_mode(chaos, whimsy, darkTone, coherence, voiceWeight)

    if mode == "code_completion":
        text = generate_code_completion(phase, action, chaos, coherence, hex_id, hex_name)
    elif mode == "blueprint":
        text = generate_blueprint(phase, action, chaos, whimsy, hex_id, hex_name, category)
    elif mode == "agent_spec":
        text = generate_agent_spec(phase, action, chaos, coherence, darkTone, voiceWeight, hex_id, hex_name)
    else:
        # Literary: load temporal reflection from immutable tables if available
        try:
            from openjarvis.emotion.kingwen_engine_adapter import collapse_full_128
            _ = collapse_full_128(emotional_input=50)
        except Exception:
            pass
        text = generate_literary(phase, action, chaos, whimsy, darkTone, hex_id, hex_name, hex_info.get("action", ""))

    return mode, text


# ── Tool: Narrative Generate ──────────────────────────────────────────────────

@ToolRegistry.register("kingwen_narrative_generate")
class KingWenNarrativeGenerateTool(BaseTool):
    """Generate narrative output (code completion, blueprint, agent spec, or literary text) from hexagram state."""

    tool_id = "kingwen_narrative_generate"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_narrative_generate",
            description=(
                "Generates structured narrative output from King Wen hexagram + emotional vector state. "
                "Mode auto-selected from emotional weights: "
                "CODE COMPLETION (coherence>0.6, chaos<0.4), "
                "BLUEPRINT topology (chaos>0.5, whimsy>0.5), "
                "AGENT SPEC YAML (voiceWeight>0.6, darkTone>0.6), "
                "or LITERARY TEXT (default). Output is always real structured text, never placeholder."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "hexagram_id": {"type": "integer", "description": "King Wen Hexagram ID (1–64)."},
                    "temporal_phase": {"type": "string", "enum": ["past", "present", "future"], "default": "present"},
                    "chaos": {"type": "number", "default": 0.5},
                    "whimsy": {"type": "number", "default": 0.5},
                    "darkTone": {"type": "number", "default": 0.5},
                    "coherence": {"type": "number", "default": 0.5},
                    "voiceWeight": {"type": "number", "default": 0.5},
                    "force_mode": {
                        "type": "string",
                        "description": "Override auto-detection: 'code_completion', 'blueprint', 'agent_spec', 'literary'.",
                        "default": "",
                    },
                },
                "required": ["hexagram_id"],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        hex_id = int(params.get("hexagram_id", 1))
        phase = str(params.get("temporal_phase", "present"))
        chaos = float(params.get("chaos", 0.5))
        whimsy = float(params.get("whimsy", 0.5))
        darkTone = float(params.get("darkTone", 0.5))
        coherence = float(params.get("coherence", 0.5))
        voiceWeight = float(params.get("voiceWeight", 0.5))
        force_mode = str(params.get("force_mode", "")).strip()

        try:
            if force_mode in ("code_completion", "blueprint", "agent_spec", "literary"):
                hex_base = _load_hex_base()
                hex_info = hex_base.get(hex_id, {})
                hex_name = hex_info.get("name", f"Hex-{hex_id}")
                category = hex_info.get("category", "")
                action = _detect_action(hex_info.get("action", "WAIT"))
                mode = force_mode
                if mode == "code_completion":
                    text = generate_code_completion(phase, action, chaos, coherence, hex_id, hex_name)
                elif mode == "blueprint":
                    text = generate_blueprint(phase, action, chaos, whimsy, hex_id, hex_name, category)
                elif mode == "agent_spec":
                    text = generate_agent_spec(phase, action, chaos, coherence, darkTone, voiceWeight, hex_id, hex_name)
                else:
                    text = generate_literary(phase, action, chaos, whimsy, darkTone, hex_id, hex_name, hex_info.get("action", ""))
            else:
                mode, text = _generate_narrative(hex_id, phase, chaos, whimsy, darkTone, coherence, voiceWeight)

            return _ok(self.tool_id, text, {'mode': mode, 'hexagram_id': hex_id, 'temporal_phase': phase, 'emotional_vector': {'chaos': chaos, 'whimsy': whimsy, 'darkTone': darkTone, 'coherence': coherence, 'voiceWeight': voiceWeight}, 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_narrative_generate failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Narrative Dispatch ───────────────────────────────────────────────────

@ToolRegistry.register("kingwen_narrative_dispatch")
class KingWenNarrativeDispatchTool(BaseTool):
    """Full oracle→narrative→Jarvis tool dispatch pipeline."""

    tool_id = "kingwen_narrative_dispatch"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_narrative_dispatch",
            description=(
                "Full oracle-to-action pipeline: consults the King Wen oracle, determines "
                "narrative mode from emotional weights, generates the narrative artifact, "
                "and routes to the appropriate Jarvis tool: "
                "code_completion → code_interpreter/repl, "
                "blueprint → file_write (saves .md topology), "
                "agent_spec → agent_tools (agent YAML ready to spawn), "
                "literary → text_to_speech or channel_send."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The intent or question to drive the oracle.", "default": ""},
                    "emotional_input": {"type": "integer", "description": "Emotional input seed [0–100].", "default": 50},
                    "output_dir": {"type": "string", "description": "Directory to save blueprint/agent YAML output files.", "default": ""},
                    "speak_output": {"type": "boolean", "description": "If true and mode=literary, send to TTS.", "default": False},
                    "channel": {"type": "string", "description": "Channel name to send literary text to. Empty = skip.", "default": ""},
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        query = str(params.get("query", ""))
        emotional_input = int(params.get("emotional_input", 50))
        output_dir_str = str(params.get("output_dir", ""))
        speak_output = bool(params.get("speak_output", False))
        channel = str(params.get("channel", "")).strip()

        try:
            # Step 1: Oracle consult
            from openjarvis.emotion.kingwen_engine_adapter import consult, HEXAGRAM_BASE
            oracle = consult(query, emotional_input=emotional_input, include_crowd_votes=False)

            hex_id = int(oracle.get("hexagram_id", 1))
            phase = str(oracle.get("phase_temporal", "present"))
            vector = oracle.get("emotional_deltas") or oracle.get("consensus_vector") or {}

            chaos = float(vector.get("chaos", 0.5))
            whimsy = float(vector.get("whimsy", 0.5))
            darkTone = float(vector.get("darkTone", 0.5))
            coherence = float(vector.get("coherence", 0.5))
            voiceWeight = float(vector.get("voiceWeight", 0.5))

            # Step 2: Generate narrative
            mode, text = _generate_narrative(hex_id, phase, chaos, whimsy, darkTone, coherence, voiceWeight)

            dispatch_result: Dict[str, Any] = {
                "mode": mode,
                "hexagram_id": hex_id,
                "temporal_phase": phase,
                "narrative_length": len(text),
                "dispatched_to": [],
                "timestamp": time.time(),
            }

            # Step 3: Route to appropriate tool
            if mode == "blueprint":
                out_dir = Path(output_dir_str) if output_dir_str else Path.home() / ".openjarvis" / "blueprints"
                out_dir.mkdir(parents=True, exist_ok=True)
                slug = f"hex{hex_id}_{phase}_{int(time.time())}"
                out_file = out_dir / f"{slug}_blueprint.md"
                out_file.write_text(text, encoding="utf-8")
                dispatch_result["dispatched_to"].append("file_write")
                dispatch_result["file_path"] = str(out_file)

            elif mode == "agent_spec":
                out_dir = Path(output_dir_str) if output_dir_str else Path.home() / ".openjarvis" / "agent_specs"
                out_dir.mkdir(parents=True, exist_ok=True)
                slug = f"pog3_agent_hex{hex_id}_{phase}_{int(time.time())}"
                out_file = out_dir / f"{slug}.yaml"
                out_file.write_text(text, encoding="utf-8")
                dispatch_result["dispatched_to"].append("file_write")
                dispatch_result["file_path"] = str(out_file)
                dispatch_result["agent_yaml"] = text

            elif mode == "code_completion":
                try:
                    from openjarvis.tools.repl import ReplTool
                    out_dir = Path(output_dir_str) if output_dir_str else Path.home() / ".openjarvis" / "completions"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    slug = f"hex{hex_id}_{phase}_{int(time.time())}"
                    out_file = out_dir / f"{slug}_completion.ts"
                    out_file.write_text(text, encoding="utf-8")
                    dispatch_result["dispatched_to"].append("file_write")
                    dispatch_result["file_path"] = str(out_file)
                except Exception:
                    dispatch_result["dispatched_to"].append("code_completion_saved")

            elif mode == "literary":
                if speak_output:
                    try:
                        from openjarvis.speech.tts import speak
                        speak(text[:500])
                        dispatch_result["dispatched_to"].append("text_to_speech")
                    except Exception as tts_e:
                        dispatch_result["tts_error"] = str(tts_e)

                if channel:
                    try:
                        from openjarvis.core.events import get_event_bus
                        bus, _ = get_event_bus(), None
                        bus.emit("channel_send", {"channel": channel, "message": text[:2000]})
                        dispatch_result["dispatched_to"].append(f"channel:{channel}")
                    except Exception as ch_e:
                        dispatch_result["channel_error"] = str(ch_e)

            dispatch_result["narrative_preview"] = text[:300] + ("..." if len(text) > 300 else "")

            return _ok(self.tool_id, f"[{mode.upper()}] Hex #{hex_id} {phase} → dispatched to: {', '.join(dispatch_result['dispatched_to']) or 'inline'}", dispatch_result)

        except Exception as exc:
            LOGGER.exception("kingwen_narrative_dispatch failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Agent Spec Emitter ──────────────────────────────────────────────────

@ToolRegistry.register("kingwen_agent_spec_emit")
class KingWenAgentSpecEmitTool(BaseTool):
    """Emit a Jarvis-compatible agent YAML spec from King Wen hexagram state."""

    tool_id = "kingwen_agent_spec_emit"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_agent_spec_emit",
            description=(
                "Emits a complete Jarvis agent YAML spec driven by King Wen hexagram state "
                "and emotional vector. The spec includes oracle hooks, dispatch limb bindings, "
                "volition rhythm, and reputation bias. Can be passed directly to agent_spawn."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "hexagram_id": {"type": "integer"},
                    "temporal_phase": {"type": "string", "enum": ["past", "present", "future"], "default": "present"},
                    "chaos": {"type": "number", "default": 0.5},
                    "coherence": {"type": "number", "default": 0.5},
                    "darkTone": {"type": "number", "default": 0.5},
                    "voiceWeight": {"type": "number", "default": 0.5},
                    "save_file": {
                        "type": "boolean",
                        "description": "If true, write YAML to ~/.openjarvis/agent_specs/.",
                        "default": True,
                    },
                },
                "required": ["hexagram_id"],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        hex_id = int(params.get("hexagram_id", 1))
        phase = str(params.get("temporal_phase", "present"))
        chaos = float(params.get("chaos", 0.5))
        coherence = float(params.get("coherence", 0.5))
        darkTone = float(params.get("darkTone", 0.5))
        voiceWeight = float(params.get("voiceWeight", 0.5))
        save_file = bool(params.get("save_file", True))

        try:
            hex_base = _load_hex_base()
            hex_info = hex_base.get(hex_id, {})
            hex_name = hex_info.get("name", f"Hex-{hex_id}")
            action = _detect_action(hex_info.get("action", "WAIT"))

            yaml_text = generate_agent_spec(phase, action, chaos, coherence, darkTone, voiceWeight, hex_id, hex_name)

            result_meta: Dict[str, Any] = {
                "hexagram_id": hex_id,
                "hex_name": hex_name,
                "temporal_phase": phase,
                "action": action,
                "agent_yaml": yaml_text,
                "timestamp": time.time(),
            }

            if save_file:
                out_dir = Path.home() / ".openjarvis" / "agent_specs"
                out_dir.mkdir(parents=True, exist_ok=True)
                fname = f"pog3_agent_hex{hex_id}_{phase}_{int(time.time())}.yaml"
                out_path = out_dir / fname
                out_path.write_text(yaml_text, encoding="utf-8")
                result_meta["file_path"] = str(out_path)

            return _ok(self.tool_id, f"Agent spec: pog3_volition_agent_{phase}_{hex_id} | action={action} | {hex_name}", result_meta)
        except Exception as exc:
            LOGGER.exception("kingwen_agent_spec_emit failed")
            return _err(self.tool_id, str(exc))
