"""Learn Capture — one-line event emission for chat handlers.

Usage:
    from openjarvis.server.learn.capture import capture_learn
    capture_learn(session_id="...", handler="/oracle", user_input="...", query="...")
"""
from __future__ import annotations

import logging
from typing import Optional

from .learn_event import LearnEvent, derive_tags
from .learn_store import LearnStore

logger = logging.getLogger(__name__)
_store: Optional[LearnStore] = None


def _get_store() -> LearnStore:
    global _store
    if _store is None:
        _store = LearnStore()
    return _store


def capture_learn(session_id: str, handler: str, user_input: str, query: str,
                  response_summary: str = "", status: str = "success",
                  save_string_before: Optional[str] = None,
                  save_string_after: Optional[str] = None,
                  hexagram_id: Optional[int] = None,
                  domain: Optional[str] = None,
                  valence: Optional[float] = None,
                  arousal: Optional[float] = None,
                  coherence: Optional[float] = None,
                  tool_used: Optional[str] = None,
                  agent_used: Optional[str] = None,
                  artifact_path: Optional[str] = None,
                  duration_ms: Optional[int] = None,
                  token_count: Optional[int] = None) -> LearnEvent:
    """Capture a learning event. One line per handler."""
    tags = derive_tags(handler, query, status)
    event = LearnEvent.create(
        session_id=session_id, handler=handler, user_input=user_input, query=query,
        response_summary=response_summary, status=status,
        save_string_before=save_string_before, save_string_after=save_string_after,
        hexagram_id=hexagram_id, domain=domain,
        valence=valence, arousal=arousal, coherence=coherence,
        tool_used=tool_used, agent_used=agent_used, artifact_path=artifact_path,
        duration_ms=duration_ms, token_count=token_count, tags=tags,
    )
    try:
        _get_store().save(event)
    except Exception as exc:
        logger.warning("Learn capture failed (non-blocking): %s", exc)
    return event