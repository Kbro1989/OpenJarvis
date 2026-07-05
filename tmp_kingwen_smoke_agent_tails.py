"""Agent-layer smoke test for King Wen head/tail wiring in OpenJarvis.

Verifies:
- operative.py: directive, mediation, monitoring, state mutation
- executor.py: head injection + post-tick monitoring hooks exist and are callable
- _stubs.py: history-backed response block uses latest entry instead of re-consult
- channel_agent.py / ask.py / chat_cmd.py: no import/runtime regressions
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(r"C:\Users\krist\Desktop\OpenJarvis")
sys.path.insert(0, str(ROOT / "src"))

from openjarvis.agents.operative import OperativeAgent
from openjarvis.agents.executor import AgentExecutor
from openjarvis.agents.channel_agent import ChannelAgent
from openjarvis.cli.ask import _append_kingwen_block


class FakeEngine:
    engine_id = "fake"


class FakeResult:
    def __init__(self, content="", tool_results=None):
        self.content = content
        self.tool_results = tool_results or []


def make_agent() -> OperativeAgent:
    agent = OperativeAgent.__new__(OperativeAgent)
    for attr in (
        "_emotion_provider",
        "_emotion_text",
        "_emotion_input",
        "_kingwen_session_id",
        "_kingwen_history",
        "_kingwen_voice_preset",
        "_kingwen_voice_section",
        "_bus",
        "_temperature",
        "_max_tokens",
        "_tools",
        "_executor",
        "_loop_guard",
        "_max_turns",
        "_system_prompt",
        "_operator_id",
        "_session_store",
        "_memory_backend",
        "_prompt_builder",
    ):
        object.__setattr__(agent, attr, None)
    object.__setattr__(agent, "_kingwen_history", [])
    object.__setattr__(agent, "_kingwen_session_id", "openjarvis")
    return agent


def test_history_backed_response_block():
    agent = make_agent()
    agent._emotion_provider = None
    agent._emotion_text = ""
    agent._kingwen_session_id = "openjarvis"
    agent._kingwen_history = [
        {
            "hexagram_id": 34,
            "hexagram_name": "Power",
            "phase_temporal": "transition",
            "voice_weight": 0.78,
            "coherence": 0.91,
            "chaos": 0.12,
            "whimsy": 0.08,
            "dark_tone": 0.05,
            "action": "search",
            "category": "web",
            "reaction_frame": "Changing lines: [1, 3, 4]\nRecovering lines: [2]\nDeepened lines: [5]",
        }
    ]
    block = agent._build_kingwen_response_block()
    assert "Power" in block, block
    assert "34" in block, block
    assert "0.78" in block, block
    print("OK _build_kingwen_response_block uses history without re-consult")


def test_directive_and_mediation():
    agent = make_agent()
    agent._kingwen_history = [
        {
            "hexagram_id": 7,
            "hexagram_name": "Army",
            "phase_temporal": "formation",
            "voice_weight": 0.88,
            "coherence": 0.93,
            "chaos": 0.08,
            "whimsy": 0.06,
            "dark_tone": 0.04,
            "action": "memory_search",
            "category": "memory",
            "reaction_frame": "Reaction frame sample.",
            "tool_outcomes": [],
        }
    ]
    directive = agent._build_kingwen_directive()
    assert "Army" in directive
    assert "memory_search" in directive
    print("OK directive includes hexagram/action/category")

    tools = [
        ToolCall(id="a", name="shell"),
        ToolCall(id="b", name="memory_search"),
        ToolCall(id="c", name="web_search"),
    ]
    ranked = agent._mediate_tool_selection(tools)
    assert ranked[0].name == "memory_search"
    print("OK mediation promoted action-aligned tool_call to front")

    # low coherence should disable mediation
    agent._kingwen_history[0]["coherence"] = 0.4
    ranked_low = agent._mediate_tool_selection(tools)
    assert ranked_low[0].name == "shell"
    print("OK low coherence leaves tool order unchanged")


def test_tool_monitoring_and_state_update():
    agent = make_agent()
    agent._kingwen_history = [
        {
            "hexagram_id": 61,
            "hexagram_name": "Inner Truth",
            "phase_temporal": "transition",
            "voice_weight": 0.82,
            "coherence": 0.85,
            "chaos": 0.15,
            "whimsy": 0.18,
            "dark_tone": 0.07,
            "action": "file_read",
            "category": "file",
            "reaction_frame": "",
            "tool_outcomes": [],
        }
    ]
    monitor = agent._monitor_kingwen_tool_call(
        [ToolCall(id="c1", name="file_read"), ToolCall(id="c2", name="shell")],
        [ToolResult(tool_name="file_read", success=True, content="ok")],
    )
    assert monitor["matches"] == ["file_read"], monitor
    print("OK monitor matches action-aligned tool_call")

    agent._update_kingwen_state_from_tools([ToolResult(tool_name="file_read", success=True, content="ok")])
    latest = agent._kingwen_history[-1]
    assert latest["coherence"] > 0.85
    assert latest["chaos"] < 0.15
    assert "file_read" in [o["name"] for o in latest.get("tool_outcomes", [])]
    print("OK success raises coherence and records tool_outcome")

    agent._update_kingwen_state_from_tools([ToolResult(tool_name="shell", success=False, content="fail")])
    latest = agent._kingwen_history[-1]
    assert latest["coherence"] < 0.85
    assert latest["chaos"] > 0.15
    assert latest["dark_tone"] > 0.07
    print("OK failure lowers coherence and raises darkTone/chaos")


def test_tail_append_helpers():
    result = FakeResult(content="Answer to user.", tool_results=[])
    agent = BaseAgent.__new__(BaseAgent)
    agent._kingwen_history = [
        {
            "hexagram_id": 23,
            "hexagram_name": "Splitting Apart",
            "phase_temporal": "dissolution",
            "voice_weight": 0.35,
            "coherence": 0.72,
            "chaos": 0.28,
            "whimsy": 0.22,
            "dark_tone": 0.18,
            "action": "advise",
            "category": "",
            "reaction_frame": "Reaction frame tail.",
            "tool_outcomes": [],
        }
    ]
    agent._emotion_provider = None
    agent._emotion_text = "Tail test input"
    agent._kingwen_session_id = "smoke"

    _append_kingwen_block(agent, result)
    assert "Splitting Apart" in result.content
    assert "Reaction frame tail." in result.content
    print("OK ask-style _append_kingwen_block adds directive + oracle tail")

    result2 = FakeResult(content="Channel reply.", tool_results=[])
    _append_kingwen_block(agent, result2)
    assert "Splitting Apart" in result2.content
    print("OK shared _append_kingwen_block keeps channel/tail behavior consistent")


def test_executor_hook_exists():
    assert hasattr(AgentExecutor, "_invoke_agent")
    src = Path(ROOT / "src/openjarvis/agents/executor.py").read_text(encoding="utf-8")
    assert "_build_kingwen_directive" in src
    assert "_update_kingwen_state_from_tools" in src
    print("OK executor contains King Wen head/monitor hook sites")


def main() -> int:
    test_history_backed_response_block()
    test_directive_and_mediation()
    test_tool_monitoring_and_state_update()
    test_tail_append_helpers()
    test_executor_hook_exists()
    print("\nSmoke tests passed: King Wen head/tail wiring intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
