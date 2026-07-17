"""kingwen_oracle_consult_tool.py — Registered Jarvis tool for King Wen oracle consultation.

Wraps the full kingwen_engine_adapter.consult() pipeline.
Produces crowd votes, temporal distributions, emotional vectors, hexagram color,
Yao vocabulary labels, and the consensus winner — all as a ToolResult.

No mock. No stub. Real collapse_full_128 → consensus.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

def _ok(tool_id: str, output: str, metadata: dict = None) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=output, success=True, metadata=metadata or {})


def _err(tool_id: str, msg: str) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=f"ERROR: {msg}", success=False)


LOGGER = logging.getLogger(__name__)


@ToolRegistry.register("kingwen_oracle_consult")
class KingWenOracleConsultTool(BaseTool):
    """Consult the King Wen 512-state oracle and return a full deliberative breakdown."""

    tool_id = "kingwen_oracle_consult"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_oracle_consult",
            description=(
                "Consult the King Wen I-Ching 512-state oracle with an emotional input weight "
                "and a query. Returns the consensus hexagram, temporal phase, emotional vectors, "
                "crowd vote breakdown, Yao vocabulary, and hexagram color. Used as the volition "
                "authority for routing decisions, training label generation, and narrative output."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or intent to consult the oracle about.",
                        "default": "",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context string enriching the consultation.",
                        "default": "",
                    },
                    "emotional_input": {
                        "type": "integer",
                        "description": "Emotional input seed value [0–100]. 50 = neutral.",
                        "default": 50,
                    },
                    "include_crowd_votes": {
                        "type": "boolean",
                        "description": "If true, include the full 64-hexagram crowd vote breakdown.",
                        "default": False,
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session identifier for provenance tracking.",
                        "default": "jarvis",
                    },
                },
                "required": [],
            },
            category="knowledge",
            latency_estimate=0.5,
        )

    def execute(self, **params: Any) -> ToolResult:
        query = str(params.get("query", ""))
        context = str(params.get("context", ""))
        emotional_input = int(params.get("emotional_input", 50))
        include_crowd_votes = bool(params.get("include_crowd_votes", False))
        session_id = str(params.get("session_id", "jarvis"))

        try:
            from openjarvis.emotion.kingwen_engine_adapter import consult
            result = consult(
                query,
                session_id=session_id,
                emotional_input=emotional_input,
                include_crowd_votes=include_crowd_votes,
            )
            result["context"] = context
            result["timestamp"] = time.time()

            summary = (
                f"Hexagram #{result.get('hexagram_id')} — {result.get('hexagram_name')} "
                f"{result.get('hexagram_symbol', '')} | Phase: {result.get('phase_temporal')} | "
                f"Action: {result.get('action')} | Category: {result.get('category')}"
            )
            return _ok(self.tool_id, summary, result)
        except Exception as exc:
            LOGGER.exception("KingWen oracle consult failed")
            return _err(self.tool_id, str(exc))
