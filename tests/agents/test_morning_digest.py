"""Tests for MorningDigestAgent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from openjarvis.agents._stubs import AgentResult
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import ToolResult


def test_morning_digest_registered():
    from openjarvis.agents.morning_digest import MorningDigestAgent

    AgentRegistry.register_value("morning_digest", MorningDigestAgent)
    assert AgentRegistry.contains("morning_digest")


def test_morning_digest_run(tmp_path):
    from openjarvis.agents.morning_digest import MorningDigestAgent

    mock_engine = MagicMock()
    mock_engine.generate.return_value = {
        "content": "Good morning sir. You have 3 emails and 2 meetings today.",
        "finish_reason": "stop",
        "usage": {},
    }

    # Mock collect result
    mock_collect_result = ToolResult(
        tool_name="digest_collect",
        content='=== MESSAGES ===\n[gmail] From: alice@co.com — "Budget" (1h ago)\n',
        success=True,
        metadata={"total_items": 2},
    )

    # Mock TTS result
    mock_tts_result = ToolResult(
        tool_name="text_to_speech",
        content=str(tmp_path / "digest.mp3"),
        success=True,
        metadata={"audio_path": str(tmp_path / "digest.mp3")},
    )

    agent = MorningDigestAgent(
        mock_engine,
        "test-model",
        tools=[],
        persona="neutral",
        digest_store_path=str(tmp_path / "digest.db"),
        emotion_provider=None,
    )

    with patch.object(
        agent._executor,
        "execute",
        side_effect=[mock_collect_result, mock_tts_result],
    ):
        result = agent.run("Generate morning digest")

    assert isinstance(result, AgentResult)
    assert "Good morning" in result.content
    assert result.turns == 1
    assert len(result.tool_results) == 2


def test_morning_digest_emotion_provider_wires_voice(tmp_path):
    from openjarvis.agents.morning_digest import MorningDigestAgent

    class DummyProvider:
        def consult(self, text, session_id):
            return {
                "hexagram_id": 31,
                "emotional_deltas": {"voiceWeight": 0.75},
            }

        def voice_preset(self, tts_backend, voice_weight):
            return {
                "backend": "cartesia",
                "voice_id": "kingwen-voice",
                "speed": 1.05,
            }

    mock_engine = MagicMock()
    mock_engine.generate.return_value = {
        "content": "Good morning sir.",
        "finish_reason": "stop",
        "usage": {},
    }

    mock_collect_result = ToolResult(
        tool_name="digest_collect",
        content="no sources",
        success=True,
        metadata={"total_items": 0},
    )
    mock_tts_result = ToolResult(
        tool_name="text_to_speech",
        content=str(tmp_path / "digest.mp3"),
        success=True,
        metadata={"audio_path": str(tmp_path / "digest.mp3")},
    )

    agent = MorningDigestAgent(
        mock_engine,
        "test-model",
        tools=[],
        persona="neutral",
        digest_store_path=str(tmp_path / "digest.db"),
        emotion_provider=DummyProvider(),
    )

    with patch.object(
        agent._executor,
        "execute",
        side_effect=[mock_collect_result, mock_tts_result],
    ):
        result = agent.run("Generate morning digest")

    assert agent._voice_id == "kingwen-voice"
    assert agent._voice_speed == 1.05
    assert agent._last_emotion_payload is not None
    assert agent._last_emotion_payload["emotional_deltas"]["voiceWeight"] == 0.75
    assert isinstance(result, AgentResult)


def test_load_persona():
    from openjarvis.agents.morning_digest import _load_persona

    # Nonexistent persona returns empty string
    result = _load_persona("nonexistent_persona_xyz")
    assert result == ""
