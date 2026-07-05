from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(r"C:\Users\krist\Desktop\OpenJarvis")
sys.path.insert(0, str(ROOT / "src"))


class FakeResult:
    def __init__(self, content="", tool_results=None):
        self.content = content
        self.tool_results = tool_results or []


class FakeEngine:
    engine_id = "fake"


def main() -> int:
    from openjarvis.agents._stubs import BaseAgent
    from openjarvis.cli.ask import _append_kingwen_block
    from openjarvis.emotion.kingwen import KingWenEmotionProvider
    from openjarvis.core.paths import get_kingwen_workspace_dir

    provider = KingWenEmotionProvider(
        registry_path=str(get_kingwen_workspace_dir() / "data" / "hexagram-registry.json"),
        weights_path=str(get_kingwen_workspace_dir() / "data" / "emotional-weights.json"),
        reflections_path=str(get_kingwen_workspace_dir() / "data" / "temporal-reflections.json"),
    )
    print("provider ok:", get_kingwen_workspace_dir())
    history = [
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
            "emotional_tongue": {
                "hexagram_id": 34,
                "voice_weight": 0.78,
                "coherence": 0.91,
                "chaos": 0.12,
                "whimsy": 0.08,
                "dark_tone": 0.05,
                "porosity": 0.41,
                "direction": "assert",
                "states": {"past": "old yang", "present": "present yang", "future": "old yin"},
                "training_weight_vectors": {
                    "voiceWeight": 0.78,
                    "coherence": 0.91,
                    "chaos": 0.12,
                    "whimsy": 0.08,
                    "darkTone": 0.05,
                },
            },
            "states": {"past": "old yang", "present": "present yang", "future": "old yin"},
            "training_weight_vectors": {
                "voiceWeight": 0.78,
                "coherence": 0.91,
                "chaos": 0.12,
                "whimsy": 0.08,
                "darkTone": 0.05,
                "porosity": 0.41,
                "direction": "assert",
            },
            "porosity": 0.41,
            "direction": "assert",
        }
    ]

    agent = BaseAgent.__new__(BaseAgent)
    agent._kingwen_history = history
    agent._emotion_provider = provider
    agent._emotion_text = "Tail test input"
    agent._kingwen_session_id = "smoke"
    for key, value in {
        "_engine": FakeEngine(),
        "_model": "qwen3.6:27b",
        "_bus": None,
        "_temperature": 0.7,
        "_max_tokens": 1024,
        "_capture_writer": None,
        "_prompt_builder": None,
        "_kingwen_voice_preset": None,
        "_kingwen_voice_section": "",
        "_current_emotional_tongue": history[-1].get("emotional_tongue") or {},
        "__dict__": {},
    }.items():
        object.__setattr__(agent, key, value)
    object.__setattr__(agent, "_kingwen_history", history)
    object.__setattr__(agent, "_kingwen_voice_history", [])

    result = FakeResult(content="Answer to user.", tool_results=[])
    _append_kingwen_block(agent, result, user_input="Tail test input")
    print("result.content=", repr(result.content))
    print("contains Power:", "Power" in result.content)
    print("contains 34:", "34" in result.content)
    print("contains reaction frame:", "Changing lines: [1, 3, 4]" in result.content or "Changing lines" in result.content)
    block = result.content.splitlines()[:30]
    print("block head:")
    for line in block:
        print("  ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
