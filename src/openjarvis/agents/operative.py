"""OperativeAgent — persistent, scheduled agent for autonomous operation.

Extends ToolUsingAgent with built-in session persistence and state recall.
Designed for Operators: autonomous agents that run on a schedule with
automatic state management between ticks.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from openjarvis.agents._stubs import AgentContext, AgentResult, ToolUsingAgent
from openjarvis.core.events import EventBus
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Message, Role, ToolCall, ToolResult
from openjarvis.engine._stubs import InferenceEngine
from openjarvis.tools._stubs import BaseTool

logger = logging.getLogger(__name__)


@AgentRegistry.register("operative")
class OperativeAgent(ToolUsingAgent):
    """Persistent autonomous agent with built-in state management.

    The Operative agent extends the standard tool-calling loop with:

    1. **Session loading** — restores conversation history from previous ticks.
    2. **State recall** — retrieves previous state JSON from memory backend.
    3. **System prompt** — injects the operator's protocol instructions.
    4. **Tool loop** — standard function-calling loop (same as Orchestrator).
    5. **Session save** — persists the tick's prompt and response.
    6. **State persistence** — auto-persists state if the agent didn't do it
       explicitly via memory_store tool.
    """

    agent_id = "operative"
    accepts_tools = True
    _default_temperature = 0.3
    _default_max_tokens = 2048
    _default_max_turns = 20

    def __init__(
        self,
        engine: InferenceEngine,
        model: str,
        *,
        tools: Optional[List[BaseTool]] = None,
        bus: Optional[EventBus] = None,
        max_turns: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        operator_id: Optional[str] = None,
        session_store: Optional[Any] = None,
        memory_backend: Optional[Any] = None,
        interactive: bool = False,
        confirm_callback=None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            engine,
            model,
            tools=tools,
            bus=bus,
            max_turns=max_turns,
            temperature=temperature,
            max_tokens=max_tokens,
            interactive=interactive,
            confirm_callback=confirm_callback,
            prompt_builder=kwargs.get("prompt_builder"),
        )
        self._system_prompt = system_prompt or ""
        self._operator_id = operator_id
        self._session_store = session_store
        self._memory_backend = memory_backend

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute a single operator tick."""
        self._emit_turn_start(input)

        kingwen_directive = self._build_kingwen_directive()
        if kingwen_directive:
            kwargs.setdefault("kingwen_directive", kingwen_directive)

        # 1. Build system prompt with state context
        sys_parts: list[str] = []
        if self._system_prompt:
            sys_parts.append(self._system_prompt)
        if kingwen_directive:
            sys_parts.append(kingwen_directive)

        # 2. State recall from memory backend
        previous_state = self._recall_state()
        if previous_state:
            sys_parts.append(f"\n## Previous State\n{previous_state}")

        system_prompt = "\n\n".join(sys_parts) if sys_parts else None
        tongue_prompt = self._build_emotional_tongue_prompt()
        if tongue_prompt:
            system_prompt = f"{system_prompt}\n\n{tongue_prompt}" if system_prompt else tongue_prompt
        # Honor SOUL.md / MEMORY.md / USER.md persona files like `jarvis ask`,
        # appended so the operative's own instructions are preserved (#376).
        system_prompt = self._apply_persona(system_prompt)

        # 3. Load session history
        session_messages = self._load_session()

        # 4. Build messages
        messages = self._build_operative_messages(
            input,
            context,
            system_prompt=system_prompt,
            session_messages=session_messages,
        )

        # 5. Run function-calling tool loop
        openai_tools = self._executor.get_openai_tools() if self._tools else []
        all_tool_results: list[ToolResult] = []
        turns = 0
        content = ""
        state_stored_by_tool = False
        total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        for _turn in range(self._max_turns):
            turns += 1

            if self._loop_guard:
                messages = self._loop_guard.compress_context(messages)

            gen_kwargs: dict[str, Any] = {}
            if openai_tools:
                gen_kwargs["tools"] = openai_tools

            result = self._generate(messages, **gen_kwargs)
            usage = result.get("usage", {})
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)
            content = result.get("content", "")
            raw_tool_calls = result.get("tool_calls", [])

            if not raw_tool_calls:
                content = self._check_continuation(result, messages)
                break

            tool_calls = [
                ToolCall(
                    id=tc.get("id", f"call_{i}"),
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", "{}"),
                )
                for i, tc in enumerate(raw_tool_calls)
            ]

            try:
                tool_calls = self._mediate_tool_selection(tool_calls)
            except Exception:
                pass

            messages.append(
                Message(
                    role=Role.ASSISTANT,
                    content=content,
                    tool_calls=tool_calls,
                )
            )

            for tc in tool_calls:
                # Loop guard check
                if self._loop_guard:
                    verdict = self._loop_guard.check_call(tc.name, tc.arguments)
                    if verdict.blocked:
                        tool_result = ToolResult(
                            tool_name=tc.name,
                            content=f"Loop guard: {verdict.reason}",
                            success=False,
                        )
                        all_tool_results.append(tool_result)
                        messages.append(
                            Message(
                                role=Role.TOOL,
                                content=tool_result.content,
                                tool_call_id=tc.id,
                                name=tc.name,
                            )
                        )
                        continue

                tool_result = self._executor.execute(tc)
                all_tool_results.append(tool_result)

                try:
                    self._monitor_kingwen_tool_call(
                        [tc], [tool_result]
                    )
                except Exception:
                    pass

                # Track if agent stored state via memory_store
                if tc.name == "memory_store" and self._operator_id:
                    try:
                        args = json.loads(tc.arguments)
                        state_key = f"operator:{self._operator_id}:state"
                        if args.get("key", "") == state_key:
                            state_stored_by_tool = True
                    except (json.JSONDecodeError, TypeError):
                        pass

                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=tool_result.content,
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )
        else:
            # Max turns exceeded
            self._save_session(input, content)
            meta = dict(total_usage)
            meta["max_turns_exceeded"] = True
            return AgentResult(
                content=content or "Maximum turns reached without a final answer.",
                tool_results=all_tool_results,
                turns=turns,
                metadata=meta,
            )

        # 6. Save session
        self._save_session(input, content)

        # 7. Auto-persist state if agent didn't do it explicitly
        if not state_stored_by_tool:
            self._auto_persist_state(content)

        try:
            self._update_kingwen_state_from_tools(all_tool_results)
        except Exception:
            pass

        self._emit_turn_end(turns=turns, content_length=len(content))
        kingwen_block = self._build_kingwen_response_block()
        if kingwen_block:
            content = f"{content}\n\n{kingwen_block}" if content.strip() else kingwen_block
        return AgentResult(
            content=content,
            tool_results=all_tool_results,
            turns=turns,
            metadata=total_usage,
        )

    def _build_operative_messages(
        self,
        input: str,
        context: Optional[AgentContext],
        *,
        system_prompt: Optional[str] = None,
        session_messages: Optional[list[Message]] = None,
    ) -> list[Message]:
        """Build message list with system prompt, session history, and input."""
        messages: list[Message] = []
        if system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=system_prompt))
        # Inject session history (recent messages from previous ticks)
        if session_messages:
            messages.extend(session_messages)
        # Context conversation (e.g. memory injection)
        if context and context.conversation.messages:
            messages.extend(context.conversation.messages)
        messages.append(Message(role=Role.USER, content=input))
        return messages

    def _recall_state(self) -> str:
        """Retrieve previous operator state from memory backend."""
        if not self._memory_backend or not self._operator_id:
            return ""
        state_key = f"operator:{self._operator_id}:state"
        try:
            result = self._memory_backend.retrieve(state_key)
            if result:
                return result if isinstance(result, str) else str(result)
        except Exception:
            logger.debug("No previous state for operator %s", self._operator_id)
        return ""

    def _load_session(self) -> list[Message]:
        """Load recent session history for this operator."""
        if not self._session_store or not self._operator_id:
            return []
        session_id = f"operator:{self._operator_id}"
        try:
            session = self._session_store.get_or_create(session_id)
            if hasattr(session, "messages") and session.messages:
                # Return last 10 messages to avoid context overflow
                recent = session.messages[-10:]
                return [
                    Message(
                        role=Role(m.get("role", "user")),
                        content=m.get("content", ""),
                    )
                    for m in recent
                    if isinstance(m, dict)
                ]
        except Exception:
            logger.debug("Could not load session for operator %s", self._operator_id)
        return []

    def _save_session(self, input_text: str, response: str) -> None:
        """Save the tick's prompt and response to the session store."""
        if not self._session_store or not self._operator_id:
            return
        session_id = f"operator:{self._operator_id}"
        try:
            self._session_store.save_message(
                session_id,
                {"role": "user", "content": input_text},
            )
            self._session_store.save_message(
                session_id,
                {"role": "assistant", "content": response},
            )
        except Exception:
            logger.debug("Could not save session for operator %s", self._operator_id)

    def _auto_persist_state(self, content: str) -> None:
        """Auto-persist a state summary if the agent didn't store state explicitly."""
        if not self._memory_backend or not self._operator_id:
            return
        state_key = f"operator:{self._operator_id}:state"
        try:
            summary = content[:1000] if content else ""
            self._memory_backend.store(state_key, summary)
        except Exception:
            logger.debug(
                "Could not auto-persist state for operator %s",
                self._operator_id,
            )

    # ------------------------------------------------------------------ #
    # King Wen subconscious influence + guided tool-call layer
    # ------------------------------------------------------------------ #
    def _build_kingwen_directive(self) -> str:
        """Build a deterministic directive block from King Wen history."""
        history = getattr(self, "_kingwen_history", None)
        if not history:
            return ""

        latest = history[-1]
        action = latest.get("action", "advise")
        category = latest.get("category", "")
        coherence = latest.get("coherence", 0.0)
        whimsy = latest.get("whimsy", 0.0)
        phase = latest.get("phase_temporal", "")
        reaction = latest.get("reaction_frame", "") or ""

        lines = [
            "\n## Subconscious King Wen Direction",
            f"- Current hexagram: {latest.get('hexagram_name', '')} ({latest.get('hexagram_id')})",
            f"- Phase / temporal: {phase}",
            f"- Action frame: {action} | Category: {category}",
            f"- Weights: voice={latest.get('voice_weight', 0.0):.2f}, coherence={coherence:.2f}, "
            f"chaos={latest.get('chaos', 0.0):.2f}, whimsy={whimsy:.2f}, dark={latest.get('dark_tone', 0.0):.2f}",
        ]
        if reaction:
            lines.append(f"- Reaction frame: {reaction}")

        lines.append(
            "After your first turn, allow this frame to bias tool selection; "
            "if coherence is high, prefer one focused native tool call."
        )
        return "\n".join(lines)

    def _update_kingwen_state_from_tools(
        self,
        tool_results: list[ToolResult],
    ) -> None:
        """Lightly mutate the latest King Wen turn weights from tool outcomes.

        This is the bedside monitor for the guided tool-call layer:
        - raise coherence and lower chaos on successful native tool calls
        - lower voiceWeight and raise darkTone on failed calls
        - append a tool outcome marker to the reaction frame
        """
        history = getattr(self, "_kingwen_history", None)
        if not history or not tool_results:
            return

        latest = history[-1]
        successes = sum(1 for tr in tool_results if tr.success)
        failures = max(0, len(tool_results) - successes)
        for tr in tool_results:
            outcomes = latest.get("tool_outcomes", [])
            outcomes.append(
                {
                    "name": tr.tool_name,
                    "success": tr.success,
                    "content": (tr.content or "")[:240],
                }
            )
            latest["tool_outcomes"] = outcomes

        if failures == 0 and tool_results:
            latest["coherence"] = min(1.0, float(latest.get("coherence", 0.0)) + 0.05)
            latest["chaos"] = max(0.0, float(latest.get("chaos", 0.0)) - 0.03)
            latest["voice_weight"] = max(
                0.0, min(1.0, float(latest.get("voice_weight", 0.0)) + 0.02)
            )
        elif failures:
            latest["coherence"] = max(0.0, float(latest.get("coherence", 0.0)) - 0.04)
            latest["chaos"] = min(1.0, float(latest.get("chaos", 0.0)) + 0.05)
            latest["voice_weight"] = max(
                0.0, min(1.0, float(latest.get("voice_weight", 0.0)) - 0.03)
            )
            latest["dark_tone"] = min(1.0, float(latest.get("dark_tone", 0.0)) + 0.04)

    def _monitor_kingwen_tool_call(
        self,
        tool_calls: list[ToolCall],
        tool_results: list[ToolResult],
    ) -> dict[str, Any]:
        """Record tool-call outcomes under the current King Wen turn."""
        history = getattr(self, "_kingwen_history", None)
        if not history or not tool_calls:
            return {}

        latest = history[-1]
        monitored_tools = [
            latest.get("action", ""),
            latest.get("category", ""),
        ]
        called_names = [tc.name for tc in tool_calls]
        matches = [name for name in called_names if name in monitored_tools]

        record: dict[str, Any] = {
            "turn_hexagram_id": latest.get("hexagram_id"),
            "turn_hexagram_name": latest.get("hexagram_name", ""),
            "turn_action": latest.get("action", ""),
            "turn_category": latest.get("category", ""),
            "tool_calls": called_names,
            "matches": matches,
            "results": [
                {"name": tr.tool_name, "success": tr.success}
                for tr in tool_results
            ],
        }
        if history is not None and len(history) > 24:
            del history[:-24]
        return record

    def _mediate_tool_selection(
        self,
        tool_calls: list[ToolCall],
    ) -> list[ToolCall]:
        """Deterministically reorder tool calls based on King Wen weights.

        High coherence / action-aligned calls are promoted to the front.
        """
        history = getattr(self, "_kingwen_history", None)
        if not history or len(tool_calls) <= 1:
            return tool_calls

        latest = history[-1]
        action = latest.get("action", "")
        action_weight = float(latest.get("voice_weight", 0.0))
        coherence = float(latest.get("coherence", 0.0))
        if not action or coherence <= 0.55 or action_weight <= 0.5:
            return tool_calls

        def _priority(name: str) -> int:
            base = 0
            if name == action:
                base += 10
            category = latest.get("category", "")
            if category and category in name:
                base += 5
            return base

        try:
            ranked = sorted(
                tool_calls,
                key=lambda tc: _priority(tc.name),
                reverse=True,
            )
            return ranked
        except Exception:
            return tool_calls

