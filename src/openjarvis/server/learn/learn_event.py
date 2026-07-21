"""Learn Event — capture contract for OpenJarvis chat interactions.

Every /command handler emits a LearnEvent after execution.
Events are stored in SQLite and feed into the Hermes learning graph.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class LearnEvent:
    """A single learning capture from a chat interaction."""
    event_id: str
    timestamp: str
    session_id: str
    handler: str
    user_input: str
    query: str
    response_summary: str
    response_full: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    save_string_before: Optional[str] = None
    save_string_after: Optional[str] = None
    hexagram_id: Optional[int] = None
    domain: Optional[str] = None
    valence: Optional[float] = None
    arousal: Optional[float] = None
    coherence: Optional[float] = None
    tool_used: Optional[str] = None
    agent_used: Optional[str] = None
    artifact_path: Optional[str] = None
    duration_ms: Optional[int] = None
    token_count: Optional[int] = None
    tags: Optional[List[str]] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def create(cls, session_id: str, handler: str, user_input: str,
               query: str, response_summary: str = "", status: str = "success",
               **kwargs) -> "LearnEvent":
        """Factory: create with auto ID and timestamp."""
        return cls(
            event_id=f"learn-{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id, handler=handler,
            user_input=user_input, query=query,
            response_summary=response_summary, status=status,
            **kwargs,
        )


HANDLER_CATEGORIES = {
    "/oracle": ["divination", "question", "insight"],
    "/counsel": ["advice", "guidance", "support"],
    "/blueprint": ["automation", "schedule", "task"],
    "/agents": ["swarm", "delegation", "multi-agent"],
    "/learn": ["meta-learning", "retrieval", "pattern"],
}


def derive_tags(handler: str, query: str, status: str) -> List[str]:
    """Derive searchable tags from handler + query + status."""
    tags = list(HANDLER_CATEGORIES.get(handler, []))
    if status != "success":
        tags.append(status)
    keywords = [w.lower() for w in query.split() if len(w) > 4]
    tags.extend(keywords[:3])
    return list(dict.fromkeys(tags))