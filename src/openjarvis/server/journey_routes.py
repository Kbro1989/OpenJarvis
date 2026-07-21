"""Journey backend routes exposing learning timeline endpoints."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

journey_router = APIRouter(prefix="/v1/journey", tags=["journey"])


class JourneyQueryRequest(BaseModel):
    query: str


@journey_router.get("/timeline")
async def journey_timeline(request: Request, limit: int = 20) -> dict[str, Any]:
    """Return the journey / learning timeline for the current session.

    The backend goal is a replayable learning history; this endpoint
    returns a best-effort payload safe for dev/test when the full
    artifact pipeline is not yet wired.
    """
    try:
        from openjarvis.core.journey_executor import JourneyExecutor

        executor = JourneyExecutor()
        try:
            query = getattr(request.app.state, "journey_last_query", "") or "journey"
            matches = executor.lookup(query=query)
        except Exception as exc:  # noqa: BLE001
            logger.debug("journey lookup fallback: %s", exc)
            matches = []

        events: list[dict[str, Any]] = []
        for match in matches[: max(limit, 0)]:
            events.append(
                {
                    "session_id": match.session_id,
                    "score": match.score,
                    "synaptic_weight": match.synaptic_weight,
                    "intent": match.intent,
                    "cluster": match.cluster,
                    "related_sessions": match.related_sessions,
                    "path": match.path,
                    "artifact_type": match.artifact_type,
                    "surface": match.surface,
                    "occurred_at": time.time(),
                }
            )

        return {
            "events": events,
            "match_count": len(matches),
            "query": getattr(request.app.state, "journey_last_query", "") or "",
        }
    except Exception as exc:
        logger.warning("journey/timeline failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@journey_router.get("/stats")
async def journey_stats(request: Request) -> dict[str, Any]:
    """Return summary stats for the journey timeline."""
    try:
        summary: dict[str, Any] = {
            "total_events": 0,
            "agent_runs": 0,
            "knowledge_gaps": 0,
            "resolved_gaps": 0,
            "unique_sessions": 0,
        }

        sessions: set[str] = set()
        try:
            from openjarvis.server.agent_manager_routes import create_agent_manager_router

            mgr = getattr(request.app.state, "agent_manager", None)
            if mgr is not None:
                for agent in mgr.list_agents():
                    agent_id = agent.get("id") or agent.get("agent_id", "")
                    if not agent_id:
                        continue
                    sessions.add(agent_id)
                    summary["agent_runs"] += int(agent.get("total_runs") or 0)
                    tasks = mgr.list_tasks(agent_id)
                    for task in tasks:
                        description = task.get("description", "") or ""
                        if "gap" in description.lower():
                            summary["knowledge_gaps"] += 1
                            if task.get("status") in {"completed", "delivered"}:
                                summary["resolved_gaps"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("journey stats enrichment skipped: %s", exc)

        summary["unique_sessions"] = len(sessions)
        return summary
    except Exception as exc:
        logger.warning("journey/stats failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@journey_router.post("/query")
async def journey_query(
    request: Request,
    data: JourneyQueryRequest,
) -> dict[str, Any]:
    """Run a focused journey lookup and store the query for timeline enrichment."""
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    try:
        from openjarvis.core.journey_executor import JourneyExecutor

        request.app.state.journey_last_query = query
        executor = JourneyExecutor()
        try:
            matches = executor.lookup(query=query)
        except Exception as exc:  # noqa: BLE001
            logger.debug("journey query fallback: %s", exc)
            matches = []

        return {
            "query": query,
            "events": [
                {
                    "session_id": match.session_id,
                    "score": match.score,
                    "intent": match.intent,
                    "cluster": match.cluster,
                    "related_sessions": match.related_sessions,
                    "path": match.path,
                    "occurred_at": time.time(),
                }
                for match in matches[:20]
            ],
            "match_count": len(matches),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("journey/query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


__all__ = ["journey_router"]
