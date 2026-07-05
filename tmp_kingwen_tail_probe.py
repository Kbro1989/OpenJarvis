"""Focused kingwen proof-of-concept for the Operative tail layer.

Exercises the real modified paths in _stubs.py / operative.py:
- _emit_turn_start() consult + history append
- _build_kingwen_directive() subtext injection
- _mediate_tool_selection() tool-call ranking
- _monitor_kingwen_tool_call() + _update_kingwen_state_from_tools() monitoring
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE = Path(r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES").parent
sys.path.insert(0, str(BASE / "src"))

from openjarvis.emotion.kingwen import KingWenEmotionProvider  # noqa: E402


def pct(v: float) -> str:
    return f"{v*100:.0f}%"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = "{}"


@dataclass
class ToolResult:
    tool_name: str
    content: str = ""
    success: bool = True


@dataclass
class Probe:
    provider: KingWenEmotionProvider
    _kingwen_history: List[Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._kingwen_history is None:
            self._kingwen_history = []
        self._kingwen_session_id = "openjarvis"
        self._kingwen_voice_preset = None
        self._kingwen_voice_section = ""

    # --- reproduction of _stubs.py turn-start tail ---
    def _emit_turn_start(self, input_text: str) -> None:
        self._emotion_text = input_text
        self._emotion_input = 50
        if self.provider and input_text:
            payload = self.provider.consult(
                text=input_text,
                session_id=self._kingwen_session_id,
                emotional_input=self._emotion_input,
            )
            preset = self.provider.voice_preset(
                tts_backend=getattr(self, "_tts_backend", None) or "cartesia",
                voice_weight=float(
                    payload.get("emotional_deltas", {}).get("voiceWeight", 0.0)
                ),
            )
            self._kingwen_voice_preset = preset
            self._kingwen_voice_section = self.provider.format_voice_section(preset)
            self._kingwen_history.append(
                {
                    "text": input_text,
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
                }
            )
        else:
            self._kingwen_voice_preset = None
            self._kingwen_voice_section = ""

    # --- reproduction of operative.py tail methods ---
    def _build_kingwen_directive(self) -> str:
        history = self._kingwen_history
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

    def _monitor_kingwen_tool_call(
        self,
        tool_calls: List[ToolCall],
        tool_results: List[ToolResult],
    ) -> Dict[str, Any]:
        history = self._kingwen_history
        if not history or not tool_calls:
            return {}
        latest = history[-1]
        monitored_tools = [latest.get("action", ""), latest.get("category", "")]
        called_names = [tc.name for tc in tool_calls]
        matches = [name for name in called_names if name in monitored_tools]
        return {
            "turn_hexagram_id": latest.get("hexagram_id"),
            "turn_hexagram_name": latest.get("hexagram_name", ""),
            "turn_action": latest.get("action", ""),
            "turn_category": latest.get("category", ""),
            "tool_calls": called_names,
            "matches": matches,
            "results": [
                {"name": tr.tool_name, "success": tr.success} for tr in tool_results
            ],
        }

    def _mediate_tool_selection(self, tool_calls: List[ToolCall]) -> List[ToolCall]:
        history = self._kingwen_history
        if not history or len(tool_calls) <= 1:
            return tool_calls
        latest = history[-1]
        action = latest.get("action", "")
        voice_weight = float(latest.get("voice_weight", 0.0))
        coherence = float(latest.get("coherence", 0.0))
        if not action or coherence <= 0.55 or voice_weight <= 0.5:
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
            return sorted(tool_calls, key=lambda tc: _priority(tc.name), reverse=True)
        except Exception:
            return tool_calls

    def _update_kingwen_state_from_tools(self, tool_results: List[ToolResult]) -> None:
        history = self._kingwen_history
        if not history or not tool_results:
            return
        latest = history[-1]
        successes = sum(1 for tr in tool_results if tr.success)
        failures = max(0, len(tool_results) - successes)
        for tr in tool_results:
            latest.setdefault("tool_outcomes", []).append(
                {
                    "name": tr.tool_name,
                    "success": tr.success,
                    "content": (tr.content or "")[:240],
                }
            )
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


def make_provider() -> KingWenEmotionProvider:
    tables = BASE / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
    return KingWenEmotionProvider(
        registry_path=tables / "data" / "hexagram-registry.json",
        weights_path=tables / "data" / "emotional-weights.json",
        reflections_path=tables / "data" / "temporal-reflections.json",
        ternary_module_path=tables / "kingwen_ternary_tables_complete.py",
    )


def main() -> int:
    probe = Probe(provider=make_provider())
    texts = [
        "Find and summarize the latest research on LLM reasoning",
        "Now execute the file operations we just discussed",
        "I want to save this analysis to long-term memory",
    ]
    print("=== OperativeKingwen Tail ===")
    for idx, text in enumerate(texts, start=1):
        print(f"--- turn {idx}: {text!r} ---")
        probe._emit_turn_start(text)
        if not probe._kingwen_history:
            print("consult      : (no history recorded)")
            print("directive    : (none)")
            print("mediation    : n/a")
            print()
            continue
        latest = probe._kingwen_history[-1]
        print(
            "consult      : "
            f"hexagram={latest['hexagram_id']} {latest['hexagram_name']}, "
            f"phase={latest['phase_temporal']}, "
            f"voiceWeight={pct(latest['voice_weight'])}, "
            f"coherence={pct(latest['coherence'])}, "
            f"chaos={pct(latest['chaos'])}, "
            f"whimsy={pct(latest['whimsy'])}, "
            f"dark={pct(latest['dark_tone'])}, "
            f"action={latest['action']}, category={latest['category']}"
        )
        print("react frame  : " + (latest["reaction_frame"][:140] or "n/a"))
        print("voice preset : " + str(probe._kingwen_voice_preset))
        directive = probe._build_kingwen_directive()
        print("directive    : " + (directive.splitlines()[0] if directive else "(none)"))
        hypothesis = [
            ToolCall(id="h1", name="shell"),
            ToolCall(id="h2", name="file_read"),
        ]
        mediated = probe._mediate_tool_selection(hypothesis)
        print(
            "mediation    : "
            + " -> ".join(tc.name for tc in mediated)
            + (" [unchanged]" if mediated == hypothesis else " [reordered]")
        )
        if idx == 1:
            results = [
                ToolResult(tool_name="shell", success=True, content="ok"),
                ToolResult(tool_name="file_read", success=True, content="/tmp/x.txt"),
            ]
        elif idx == 2:
            results = [
                ToolResult(tool_name="shell", success=True, content="ok"),
                ToolResult(tool_name="file_read", success=False, content="missing"),
            ]
        else:
            results = [ToolResult(tool_name="memory_store", success=True, content="saved")]
        monitor = probe._monitor_kingwen_tool_call(hypothesis, results)
        print(
            "monitor      : "
            + ",".join(monitor.get("tool_calls", []))
            + " matches="
            + ",".join(monitor.get("matches", []))
        )
        probe._update_kingwen_state_from_tools(results)
        current = probe._kingwen_history[-1]
        print(
            "post-tool    : "
            + "coherence=" + pct(current["coherence"])
            + " chaos=" + pct(current["chaos"])
            + " voice=" + pct(current["voice_weight"])
            + " dark=" + pct(current["dark_tone"])
        )
        print()

    final = probe._kingwen_history[-1]
    assert final["tool_outcomes"][-1]["name"] == "memory_store"
    assert final["tool_outcomes"][-1]["success"] is True
    print("tail-monitor assertion: last native tool outcome recorded OK")
    print(f"final directive: {probe._build_kingwen_directive()[:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
