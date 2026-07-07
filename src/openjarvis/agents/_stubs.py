"""ABC for agent implementations.

Adapted from IPW's ``BaseAgent`` at ``src/agents/base.py``.
Provides ``BaseAgent`` with concrete helper methods for event emission,
message building, and generation, plus ``ToolUsingAgent`` intermediate
base for agents that accept tools.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.core.config import load_config
from openjarvis.core.events import EventBus, EventType
from openjarvis.core.types import Conversation, Message, Role, ToolResult
from openjarvis.engine._stubs import InferenceEngine


@dataclass(slots=True)
class AgentContext:
    """Runtime context handed to an agent on each invocation."""

    conversation: Conversation = field(default_factory=Conversation)
    tools: List[str] = field(default_factory=list)
    memory_results: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    """Result returned after an agent completes a run."""

    content: str
    tool_results: List[ToolResult] = field(default_factory=list)
    turns: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all agent implementations.

    Subclasses must be registered via
    ``@AgentRegistry.register("name")`` to become discoverable.

    Provides concrete helper methods that eliminate boilerplate in
    subclasses:

    - :meth:`_emit_turn_start` / :meth:`_emit_turn_end` -- event bus
    - :meth:`_build_messages` -- conversation + system prompt assembly
    - :meth:`_generate` -- delegates to engine with stored defaults
    - :meth:`_max_turns_result` -- standard max-turns-exceeded result
    - :meth:`_strip_think_tags` -- remove ``<think>`` blocks
    """

    agent_id: str
    accepts_tools: bool = False

    def __init__(
        self,
        engine: InferenceEngine,
        model: str,
        *,
        bus: Optional[EventBus] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_builder: Optional[Any] = None,
        capture_writer: Optional[Any] = None,
        emotion_provider: Optional[Any] = None,
        kingwen_session_id: str = "openjarvis",
    ) -> None:
        self._engine = engine
        self._model = model
        self._bus = bus
        self._prompt_builder = prompt_builder
        if not hasattr(self, "_capture_writer"):
            self._capture_writer = capture_writer
        if not hasattr(self, "_emotion_provider"):
            self._emotion_provider = emotion_provider
        if not hasattr(self, "_kingwen_session_id"):
            self._kingwen_session_id = kingwen_session_id
        if not hasattr(self, "_kingwen_history"):
            self._kingwen_history: list[dict[str, Any]] = []
        self._current_emotional_tongue: dict[str, Any] = {}

        # Three-tier resolution: explicit arg > config > class default > hardcoded
        if temperature is not None and max_tokens is not None:
            self._temperature = temperature
            self._max_tokens = max_tokens
        else:
            try:
                cfg = load_config()
                self._temperature = (
                    temperature
                    if temperature is not None
                    else cfg.intelligence.temperature
                )
                self._max_tokens = (
                    max_tokens
                    if max_tokens is not None
                    else cfg.intelligence.max_tokens
                )
            except Exception:
                self._temperature = (
                    temperature
                    if temperature is not None
                    else getattr(self, "_default_temperature", 0.7)
                )
                self._max_tokens = (
                    max_tokens
                    if max_tokens is not None
                    else getattr(self, "_default_max_tokens", 1024)
                )

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def _emit_turn_start(self, input: str) -> None:
        """Publish ``AGENT_TURN_START`` if an event bus is available."""
        if self._bus:
            self._bus.publish(
                EventType.AGENT_TURN_START,
                {"agent": self.agent_id, "input": input},
            )
        self._emotion_text = input
        if not hasattr(self, "_emotion_input"):
            self._emotion_input = 50
        provider = getattr(self, "_emotion_provider", None)
        if provider is not None and input:
            try:
                payload = provider.consult(
                    text=input,
                    session_id=getattr(self, "_kingwen_session_id", "openjarvis"),
                    emotional_input=getattr(self, "_emotion_input"),
                )
                self._kingwen_consult_payload = payload
                preset = provider.voice_preset(
                    tts_backend=getattr(self, "_tts_backend", None) or "cartesia",
                    voice_weight=float(
                        payload.get("emotional_deltas", {}).get("voiceWeight", 0.0)
                    ),
                )
                self._kingwen_voice_preset = preset
                self._kingwen_voice_section = provider.format_voice_section(preset)
                tongue = payload.get("emotional_tongue") or {}
                self._current_emotional_tongue = tongue
                try:
                    self._kingwen_call_sign = provider.get_kingwen_call_sign(
                        text=input,
                        session_id=getattr(self, "_kingwen_session_id", "openjarvis"),
                        hexagram_id=int(payload.get("hexagram_id") or 0) or None,
                        phase_bits=int(payload.get("phase_bits") or 0),
                    )
                except Exception:
                    self._kingwen_call_sign = None
                self._kingwen_save_string = provider.encode_tongue(tongue or {})
                self._kingwen_wait = bool(
                    payload.get("wait")
                    or payload.get("_wait")
                    or ((payload.get("emotional_deltas", {}) or {}).get("coherence", 1.0) < 0.25)
                    or ((payload.get("emotional_deltas", {}) or {}).get("voiceWeight", 1.0) < 0.35)
                )
                tongue_data = tongue or {}
                porosity_value = float(tongue_data.get("porosity", 0.35))
                self._current_porosity = porosity_value
                self._current_emotional_input = getattr(self, "_emotion_input", 50)
                if porosity_value < 0.3:
                    self._kingwen_broadcast_mode = "whisper"
                    self._agent_autonomy = 1.0
                    self._memory_sync_interval = 10
                    self._swarm_broadcast_enabled = False
                elif porosity_value < 0.8:
                    self._kingwen_broadcast_mode = "suggest"
                    self._agent_autonomy = 0.7
                    self._memory_sync_interval = 3
                    self._swarm_broadcast_enabled = False
                else:
                    self._kingwen_broadcast_mode = "command"
                    self._agent_autonomy = 0.3
                    self._memory_sync_interval = 0
                    self._swarm_broadcast_enabled = True
                history = getattr(self, "_kingwen_history", None)
                if history is not None:
                    history.append(
                        {
                            "text": input,
                            "hexagram_id": payload.get("hexagram_id"),
                            "hexagram_name": payload.get("hexagram_name", ""),
                            "phase_temporal": payload.get("phase_temporal", ""),
                            "voice_weight": float(
                                payload.get("emotional_deltas", {}).get("voiceWeight", 0.0)
                            ),
                            "coherence": float(
                                payload.get("emotional_deltas", {}).get("coherence", 0.0)
                            ),
                            "chaos": float(
                                payload.get("emotional_deltas", {}).get("chaos", 0.0)
                            ),
                            "whimsy": float(
                                payload.get("emotional_deltas", {}).get("whimsy", 0.0)
                            ),
                            "dark_tone": float(
                                payload.get("emotional_deltas", {}).get("darkTone", 0.0)
                            ),
                            "action": payload.get("action", ""),
                            "category": payload.get("category", ""),
                            "reaction_frame": payload.get("reaction_frame", "") or "",
                            "emotional_tongue": tongue,
                            "porosity": float(tongue.get("porosity", 0.35)),
                            "direction": str(tongue.get("direction", "") or ""),
                            "states": tongue.get("states") or {},
                            "training_weight_vectors": tongue.get("training_weight_vectors") or {},
                        }
                    )
                    if len(history) > 24:
                        del history[:-24]
            except Exception:
                self._kingwen_voice_preset = None
                self._kingwen_voice_section = ""
        else:
            self._kingwen_voice_preset = None
            self._kingwen_voice_section = ""

    def _emit_turn_end(self, **data: Any) -> None:
        """Publish ``AGENT_TURN_END`` and, when broadcast mode is active,
        publish ``KINGWEN_CONSENSUS_UPDATE`` with real agent state captured
        from the current turn."""
        if self._bus:
            payload: Dict[str, Any] = {"agent": self.agent_id}
            payload.update(data)
            self._bus.publish(EventType.AGENT_TURN_END, payload)
            if self._swarm_broadcast_enabled:
                history = getattr(self, "_kingwen_history", None)
                latest = history[-1] if history else {}
                ed = latest.get("emotional_deltas") or {}
                tongue = latest.get("emotional_tongue") or {}
                consensus_data = {
                    "agent": self.agent_id,
                    "hexagram_id": latest.get("hexagram_id"),
                    "hexagram_name": latest.get("hexagram_name"),
                    "phase_temporal": latest.get("phase_temporal"),
                    "porosity": float(tongue.get("porosity", self._current_porosity or 0.35)),
                    "voiceWeight": float(ed.get("voiceWeight", latest.get("voice_weight", 0.0) or 0.0)),
                    "coherence": float(ed.get("coherence", latest.get("coherence", 0.0) or 0.0)),
                    "chaos": float(ed.get("chaos", latest.get("chaos", 0.0) or 0.0)),
                    "whimsy": float(ed.get("whimsy", latest.get("whimsy", 0.0) or 0.0)),
                    "darkTone": float(ed.get("darkTone", latest.get("dark_tone", 0.0) or 0.0)),
                    "trajectory": tongue.get("trajectory"),
                    "training_weight_vectors": tongue.get("training_weight_vectors") or {},
                    "emotional_tongue": tongue,
                    "kingwen_broadcast_mode": getattr(self, "_kingwen_broadcast_mode", None),
                    "agent_autonomy": float(getattr(self, "_agent_autonomy", 0.7)),
                    "memory_sync_interval": float(getattr(self, "_memory_sync_interval", 3)),
                    "swarm_broadcast_enabled": bool(getattr(self, "_swarm_broadcast_enabled", False)),
                }
                try:
                    self._bus.publish(EventType.KINGWEN_CONSENSUS_UPDATE, consensus_data)
                except Exception:
                    pass
                try:
                    asyncio.get_running_loop()
                    self._schedule_globe_broadcast(consensus_data)
                except RuntimeError:
                    pass

    def _schedule_globe_broadcast(self, consensus_data: Dict[str, Any]) -> None:
        limb = getattr(self, "_globe_limb", None)
        if limb is None or not limb.available():
            return
        try:
            envelope = GlobeConsensusEnvelope(
                ts=time.time(),
                session_id=getattr(self, "_kingwen_session_id", None),
                agent=consensus_data.get("agent"),
                hexagram_id=consensus_data.get("hexagram_id"),
                hexagram_name=consensus_data.get("hexagram_name"),
                phase_temporal=consensus_data.get("phase_temporal"),
                porosity=consensus_data.get("porosity"),
                voiceWeight=consensus_data.get("voiceWeight"),
                coherence=consensus_data.get("coherence"),
                chaos=consensus_data.get("chaos"),
                whimsy=consensus_data.get("whimsy"),
                darkTone=consensus_data.get("darkTone"),
                trajectory=consensus_data.get("trajectory"),
                broadcast_mode=consensus_data.get("kingwen_broadcast_mode"),
                agent_autonomy=consensus_data.get("agent_autonomy"),
                memory_sync_interval=consensus_data.get("memory_sync_interval"),
                swarm_broadcast_enabled=consensus_data.get("swarm_broadcast_enabled"),
                emotional_tongue=consensus_data.get("emotional_tongue") or {},
                training_weight_vectors=consensus_data.get("training_weight_vectors") or {},
            )
        except Exception:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._fire_and_forget_globe(limb, envelope))
        except RuntimeError:
            pass

    async def _fire_and_forget_globe(self, limb, envelope: GlobeConsensusEnvelope) -> None:
        try:
            await limb.broadcast(envelope)
        except Exception:
            pass

    def _apply_persona(self, system_prompt: Optional[str]) -> Optional[str]:
        """Append SOUL/MEMORY/USER persona to a self-assembled system prompt.

        Agents like ``monitor_operative`` / ``operative`` build their own
        system prompt and bypass ``_build_messages`` (and thus the prompt
        builder). This lets them honor the same persona files as one-shot
        ``jarvis ask`` (#376) by *appending* persona to — never replacing —
        their specialized instructions. No-op when no ``prompt_builder`` is
        wired or no persona files exist.
        """
        if self._prompt_builder is None:
            return system_prompt
        persona = self._prompt_builder.persona_sections()
        if not persona:
            return system_prompt
        return f"{system_prompt}\n\n{persona}" if system_prompt else persona

    def _build_messages(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        *,
        system_prompt: Optional[str] = None,
    ) -> list[Message]:
        """Assemble the message list for a generate call.

        Optionally prepends a system prompt, then appends any context
        conversation messages, and finally the user input.
        """
        messages: list[Message] = []
        # Check if the context already supplies a system message
        _context_has_system = (
            context
            and context.conversation.messages
            and any(m.role == Role.SYSTEM for m in context.conversation.messages)
        )

        if self._prompt_builder is not None:
            effective_system_prompt = self._prompt_builder.build()
        elif system_prompt:
            effective_system_prompt = system_prompt
        elif _context_has_system:
            effective_system_prompt = None
        else:
            # Fall back to the config-level default (grounds local models)
            try:
                cfg = load_config()
                effective_system_prompt = cfg.agent.default_system_prompt or None
            except Exception:
                effective_system_prompt = None
        if effective_system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=effective_system_prompt))
        tongue_prompt = self._build_emotional_tongue_prompt()
        if tongue_prompt:
            messages.append(Message(role=Role.SYSTEM, content=tongue_prompt))
        meta_prompt = self._build_kingwen_meta_awareness_prompt()
        if meta_prompt:
            messages.append(Message(role=Role.SYSTEM, content=meta_prompt))
        if context and context.conversation.messages:
            messages.extend(context.conversation.messages)
        messages.append(Message(role=Role.USER, content=input))
        return messages

    def _generate(self, messages: list[Message], **extra_kwargs: Any) -> dict:
        """Call ``engine.generate()`` with stored defaults.

        Extra kwargs (e.g. ``tools``) are forwarded to the engine.
        Publishes INFERENCE_START/END events on the bus when the engine
        does not publish its own (i.e. non-instrumented engines).
        """
        if self._bus and not getattr(self._engine, "_publishes_events", False):
            engine_id = getattr(self._engine, "engine_id", "")
            self._bus.publish(
                EventType.INFERENCE_START,
                {"model": self._model, "engine": engine_id},
            )

        result = self._engine.generate(
            messages,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            **extra_kwargs,
        )

        if self._capture_writer and hasattr(self._capture_writer, "write"):
            try:
                self._capture_writer.write(
                    prompt=self._serialize_messages(messages),
                    response=result.get("content", ""),
                    model=self._model,
                    engine=getattr(self._engine, "engine_id", ""),
                    agent=getattr(self, "agent_id", ""),
                    session_id=getattr(self, "_kingwen_session_id", "openjarvis"),
                    tool_calls=result.get("tool_calls", []),
                    tool_results=result.get("tool_results", []),
                    messages=messages,
                    emotion=self._build_capture_emotion(),
                    prompt_tokens=result.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=result.get("usage", {}).get("completion_tokens", 0),
                    total_tokens=result.get("usage", {}).get("total_tokens", 0),
                    latency_seconds=result.get("_telemetry", {}).get("latency", 0.0),
                    ttft=result.get("_telemetry", {}).get("ttft", 0.0),
                    success=not result.get("error"),
                    error=result.get("error"),
                )
            except Exception:
                pass

        if self._bus and not getattr(self._engine, "_publishes_events", False):
            usage = result.get("usage", {})
            self._bus.publish(
                EventType.INFERENCE_END,
                {
                    "model": self._model,
                    "usage": usage,
                    "content": result.get("content", ""),
                    "tool_calls": result.get("tool_calls", []),
                    "finish_reason": result.get("finish_reason", ""),
                },
            )

        return result

    def _build_capture_emotion(self) -> Any:
        provider = getattr(self, "_emotion_provider", None)
        if provider is None:
            return None
        try:
            payload = provider.consult(
                text=getattr(self, "_emotion_text", "") or "",
                session_id=getattr(self, "_kingwen_session_id", "openjarvis"),
                emotional_input=getattr(self, "_emotion_input"),
            )
            return type(
                "KingWenEmotionPayload",
                (),
                {
                    "hexagram_id": payload.get("hexagram_id"),
                    "hexagram_name": payload.get("hexagram_name", ""),
                    "hexagram_sequence": payload.get("hexagram_sequence", []),
                    "binary": payload.get("binary", ""),
                    "category": payload.get("category", ""),
                    "action": payload.get("action", ""),
                    "phase_bits": payload.get("phase_bits"),
                    "phase_temporal": payload.get("phase_temporal", ""),
                    "reaction_frame": payload.get("reaction_frame", ""),
                    "voice_weight": payload.get("emotional_deltas", {}).get("voiceWeight"),
                    "kingwen_voice_preset": getattr(self, "_kingwen_voice_preset", None),
                    "kingwen_voice_section": getattr(self, "_kingwen_voice_section", "") or None,
                    "emotional_deltas": payload.get("emotional_deltas", {}),
                    "reflections": payload.get("reflections", {}),
                    "training_notes": payload.get("trainingNotes", ""),
                    "emotional_tongue": payload.get("emotional_tongue") or {},
                    "porosity": float((payload.get("emotional_tongue") or {}).get("porosity", 0.35)),
                    "direction": str((payload.get("emotional_tongue") or {}).get("direction", "")),
                    "states": (payload.get("emotional_tongue") or {}).get("states") or {},
                    "training_weight_vectors": (payload.get("emotional_tongue") or {}).get("training_weight_vectors") or {},
                },
            )()
        except Exception:
            return None

    def _build_kingwen_response_block(self) -> str:
        provider = getattr(self, "_emotion_provider", None)
        if provider is None:
            return ""
        try:
            history = getattr(self, "_kingwen_history", None)
            if history:
                latest = history[-1]
                tongue = latest.get("emotional_tongue") or {}
                states = latest.get("states") or tongue.get("states") or {}
                payload = {
                    "hexagram_id": latest.get("hexagram_id"),
                    "hexagram_name": latest.get("hexagram_name", ""),
                    "phase_temporal": latest.get("phase_temporal", ""),
                    "emotional_deltas": {
                        "voiceWeight": latest.get("voice_weight", 0.0),
                        "coherence": latest.get("coherence", 0.0),
                        "chaos": latest.get("chaos", 0.0),
                        "whimsy": latest.get("whimsy", 0.0),
                        "darkTone": latest.get("dark_tone", 0.0),
                    },
                    "reaction_frame": latest.get("reaction_frame", "") or "",
                    "trainingNotes": "",
                    "emotional_tongue": tongue,
                    "porosity": float(latest.get("porosity", 0.35)),
                    "direction": str(latest.get("direction", "") or ""),
                    "states": states,
                    "training_weight_vectors": latest.get("training_weight_vectors") or {},
                }
                return provider.format_oracle_console_with_tongue(payload)
            tongue = getattr(self, "_current_emotional_tongue", {}) or {}
            fallback_payload = {
                "hexagram_id": None,
                "hexagram_name": "",
                "phase_temporal": "",
                "emotional_deltas": {
                    "voiceWeight": float(tongue.get("voice_weight", 0.0) or 0.0),
                    "coherence": float(tongue.get("coherence", 0.0) or 0.0),
                    "chaos": float(tongue.get("chaos", 0.0) or 0.0),
                    "whimsy": float(tongue.get("whimsy", 0.0) or 0.0),
                    "darkTone": float(tongue.get("dark_tone", 0.0) or 0.0),
                },
                "reaction_frame": str(tongue.get("reaction_frame", "") or ""),
                "trainingNotes": "",
                "emotional_tongue": tongue,
                "porosity": float(tongue.get("porosity", 0.35)),
                "direction": str(tongue.get("direction", "") or ""),
                "states": tongue.get("states") or {},
                "training_weight_vectors": tongue.get("training_weight_vectors") or {},
            }
            return provider.format_oracle_console_with_tongue(fallback_payload)
        except Exception:
            return ""

    def _build_emotional_tongue_prompt(self) -> str:
        """Build a compact deterministic tongue prompt block for every turn."""
        tongue = getattr(self, "_current_emotional_tongue", {}) or {}
        if not tongue:
            return ""
        states = tongue.get("states") or {}
        past_state = states.get("past", "") if isinstance(states, dict) else ""
        present_state = states.get("present", "") if isinstance(states, dict) else ""
        future_state = states.get("future", "") if isinstance(states, dict) else ""
        direction = str(tongue.get("direction", "") or "")
        porosity = float(tongue.get("porosity", 0.0) or 0.0)
        vectors = tongue.get("training_weight_vectors") or {}
        voice = float(vectors.get("voiceWeight", tongue.get("voice_weight", 0.0) or 0.0))
        coherence = float(vectors.get("coherence", tongue.get("coherence", 0.0) or 0.0))
        chaos = float(vectors.get("chaos", tongue.get("chaos", 0.0) or 0.0))
        whimsy = float(vectors.get("whimsy", tongue.get("whimsy", 0.0) or 0.0))
        dark = float(vectors.get("darkTone", tongue.get("dark_tone", 0.0) or 0.0))
        lines = [
            "## Emotional Tongue",
            "",
            f"- Past: {past_state}",
            f"- Present: {present_state}",
            f"- Future: {future_state}",
            f"- Direction: {direction}",
            f"- Porosity: {porosity:.2f}",
            "- Vectors:",
            f"  - voiceWeight: {voice:.2f}",
            f"  - coherence: {coherence:.2f}",
            f"  - chaos: {chaos:.2f}",
            f"  - whimsy: {whimsy:.2f}",
            f"  - darkTone: {dark:.2f}",
            "",
            "Use this tongue as the dominant tonal and routing constraint for this thought.",
        ]
        return "\n".join(lines)

    def _build_kingwen_intent_guidance(self, user_input: str) -> str:
        """Build intent-grounded guidance from the current save-string tongue and user message."""
        tongue = getattr(self, "_current_emotional_tongue", {}) or {}
        if not tongue or not user_input:
            return ""
        states = tongue.get("states") or {}
        present_state = states.get("present", "") if isinstance(states, dict) else ""
        direction = str(tongue.get("direction", "") or "")
        porosity = float(tongue.get("porosity", 0.0) or 0.0)
        vectors = tongue.get("training_weight_vectors") or {}
        voice = float(vectors.get("voiceWeight", tongue.get("voice_weight", 0.0) or 0.0))
        coherence = float(vectors.get("coherence", tongue.get("coherence", 0.0) or 0.0))
        lines = [
            "## Intent Guidance",
            "",
            f"- User intent: {user_input}",
            f"- Present state: {present_state}",
            f"- Direction: {direction}",
            f"- Porosity: {porosity:.2f}",
            f"- voiceWeight: {voice:.2f}, coherence: {coherence:.2f}",
            "",
            "Derive actionables from this consult, ordered by King Wen emotional routing.",
        ]
        return "\n".join(lines)

    def _build_kingwen_meta_awareness_prompt(self) -> str:
        """Make the model aware of what King Wen selected and why for this turn."""
        provider = getattr(self, "_emotion_provider", None)
        if provider is None:
            return ""
        tongue = getattr(self, "_current_emotional_tongue", {}) or {}
        history = getattr(self, "_kingwen_history", None) or []
        if not tongue and not history:
            return ""
        latest = history[-1] if history else {}
        payload = {
            "hexagram_id": latest.get("hexagram_id") or tongue.get("hexagram_id"),
            "hexagram_name": latest.get("hexagram_name", ""),
            "action": latest.get("action", "") or tongue.get("action", ""),
            "category": latest.get("category", "") or tongue.get("category", ""),
            "phase_temporal": latest.get("phase_temporal", "") or tongue.get("phase_temporal", ""),
            "reaction_frame": latest.get("reaction_frame", "") or tongue.get("reaction_frame", ""),
            "emotional_deltas": {
                "voiceWeight": latest.get("voice_weight", tongue.get("voice_weight", 0.0)),
                "coherence": latest.get("coherence", tongue.get("coherence", 0.0)),
                "chaos": latest.get("chaos", tongue.get("chaos", 0.0)),
                "whimsy": latest.get("whimsy", tongue.get("whimsy", 0.0)),
                "darkTone": latest.get("dark_tone", tongue.get("dark_tone", 0.0)),
            },
            "save_string": getattr(self, "_kingwen_save_string", "") or provider.encode_tongue(tongue or {}),
        }
        formatted = provider.format_oracle_console_with_tongue(payload)
        if not formatted:
            return ""
        lines = [
            "## King Wen Meta Awareness",
            "",
            "You are not just responding to the user. You are responding through an active "
            "King Wen consult that selected this hexagram and emotional state from the user's input. "
            "The model output should explicitly reflect this state, including tone, caution, certainty, "
            "and style. It should understand why this state is active from the input.",
            "",
            "Oracle Frame",
            formatted,
            "",
            "Apply this frame directly: short-term emotion drives tone and style; long-term structural "
            "orientation drives intent and action. Do not narrate the oracle in third person — embody "
            "this frame as the first-person reasoning context for what you are about to say.",
        ]
        return "\n".join(lines)

    def _build_kingwen_tail_with_intent(self, user_input: str) -> str:
        """Unified tail renderer: intent guidance + directive + Oracle Console response block.

        This is the single entry point for every live return path that wants the
        King Wen save-string tail without duplicating block assembly.
        """
        parts: list[str] = []
        intent_block = self._build_kingwen_intent_guidance(user_input)
        if intent_block:
            parts.append(intent_block)
        directive = self._build_kingwen_directive()
        if directive:
            parts.append(directive)
        response_block = self._build_kingwen_response_block()
        if response_block:
            parts.append(response_block)
        return "\n\n".join(parts) if parts else ""

    def _max_turns_result(
        self,
        tool_results: list[ToolResult],
        turns: int,
        content: str = "",
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Build the standard result for when ``max_turns`` is exceeded."""
        self._emit_turn_end(turns=turns, max_turns_exceeded=True)
        md: Dict[str, Any] = {"max_turns_exceeded": True}
        if metadata:
            md.update(metadata)
        return AgentResult(
            content=content or "Maximum turns reached without a final answer.",
            tool_results=tool_results,
            turns=turns,
            metadata=md,
        )

    def _check_continuation(
        self,
        result: dict,
        messages: list,
        *,
        max_continuations: int = 2,
    ) -> str:
        """Re-prompt on ``finish_reason == "length"`` to get complete output.

        Returns the concatenated content after up to *max_continuations*
        follow-up generate calls.
        """
        content = result.get("content", "")
        finish_reason = result.get("finish_reason", "")

        for _ in range(max_continuations):
            if finish_reason != "length":
                break
            # Append what we have so far and ask the model to continue
            from openjarvis.core.types import Message, Role

            messages.append(Message(role=Role.ASSISTANT, content=content))
            messages.append(
                Message(
                    role=Role.USER,
                    content="Continue from where you left off.",
                ),
            )
            cont = self._generate(messages)
            continuation = cont.get("content", "")
            content += continuation
            finish_reason = cont.get("finish_reason", "")

        return content

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """Remove ``<think>...</think>`` blocks from model output.

        Handles both ``<think>...</think>`` and the common distilled-model
        pattern where the opening ``<think>`` is absent and the response
        begins directly with reasoning text followed by ``</think>``.
        """
        # Full <think>...</think> blocks
        text = re.sub(
            r"<think>.*?</think>\s*",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Leading content before a bare </think> (no opening tag)
        text = re.sub(r"^.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()

    @abstractmethod
    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute the agent on *input* and return an ``AgentResult``."""


class ToolUsingAgent(BaseAgent):
    """Intermediate base for agents that accept and use tools.

    Sets ``accepts_tools = True`` for CLI/SDK introspection, and
    initialises a :class:`ToolExecutor` from the provided tools.
    """

    accepts_tools: bool = True

    def __init__(
        self,
        engine: InferenceEngine,
        model: str,
        *,
        tools: Optional[List["BaseTool"]] = None,  # noqa: F821
        bus: Optional[EventBus] = None,
        max_turns: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        loop_guard_config: Optional[Any] = None,
        capability_policy: Optional[Any] = None,
        agent_id: Optional[str] = None,
        interactive: bool = False,
        confirm_callback: Optional[Any] = None,
        skill_few_shot_examples: Optional[List[str]] = None,
        prompt_builder: Optional[Any] = None,
    ) -> None:
        super().__init__(
            engine,
            model,
            bus=bus,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_builder=prompt_builder,
        )
        from openjarvis.tools._stubs import ToolExecutor

        self._tools = tools or []
        # Plan 2B I3: store optimized few-shot examples for agents to inject
        # into their own system prompt templates as appropriate.
        self._skill_few_shot_examples = list(skill_few_shot_examples or [])
        _aid = agent_id or getattr(self, "agent_id", "")
        self._executor = ToolExecutor(
            self._tools,
            bus=bus,
            capability_policy=capability_policy,
            agent_id=_aid,
            interactive=interactive,
            confirm_callback=confirm_callback,
            managed_agent=self,
        )
        # Resolve max_turns: explicit arg > config > class default > 10
        if max_turns is not None:
            self._max_turns = max_turns
        else:
            try:
                cfg = load_config()
                self._max_turns = cfg.agent.max_turns
            except Exception:
                self._max_turns = getattr(self, "_default_max_turns", 10)

        # Loop guard
        self._loop_guard = None
        try:
            from openjarvis.agents.loop_guard import LoopGuard, LoopGuardConfig

            if loop_guard_config is None:
                loop_guard_config = LoopGuardConfig()
            elif isinstance(loop_guard_config, dict):
                loop_guard_config = LoopGuardConfig(**loop_guard_config)
            if loop_guard_config.enabled:
                self._loop_guard = LoopGuard(loop_guard_config, bus=bus)
        except ImportError:
            pass


__all__ = ["AgentContext", "AgentResult", "BaseAgent", "ToolUsingAgent"]
