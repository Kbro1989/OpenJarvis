"""King Wen Avatar Service — FastAPI routes.

Implements the full Jarvis adherence contract:
  GET  /v1/kingwen/avatar/{session_id}/state
  POST /v1/kingwen/avatar/{session_id}/inject
  POST /v1/kingwen/avatar/{session_id}/tick
  GET  /v1/kingwen/avatar/{session_id}/usage
  GET  /v1/kingwen/avatar/{session_id}/time
  GET  /v1/kingwen/avatar/{session_id}/domain/{world}
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .service import AvatarService, InMemoryStorage
from .save_string import AvatarSaveString, validate_save_string

router = APIRouter(prefix="/v1/kingwen/avatar", tags=["kingwen-avatar"])

# Initialize with in-memory storage (replace with KV in production)
_storage = InMemoryStorage()
service = AvatarService(_storage)


# ── Request/Response Models ──

class StateResponse(BaseModel):
    saveString: str
    allHexagrams: list
    dominant: dict
    temporalAnchor: dict


class InjectRequest(BaseModel):
    hexagram_id: int
    phase: str
    domain: str
    verb_cluster: Optional[str] = None
    tool: Optional[str] = None


class InjectResponse(BaseModel):
    newSaveString: str
    transitionTone: dict
    actionablePaths: list[str]


class TickRequest(BaseModel):
    tickCount: int
    event: Optional[str] = None


class TickResponse(BaseModel):
    saveString: str
    journeyMarkers: list[dict]


class UsageResponse(BaseModel):
    count: int
    lastUsed: Optional[int] = None
    verbClusters: list[str]
    skills: list[str]


class TimeResponse(BaseModel):
    sessionStart: int
    elapsedMs: int
    tickCount: int
    markers: list[dict]


class DomainResponse(BaseModel):
    domain: str
    hexagrams: list[dict]
    skills: list[str]
    injectSites: list[str]


# ── Routes ──

@router.get("/{session_id}/state", response_model=StateResponse)
async def get_state(session_id: str) -> StateResponse:
    """Get current save string + all hexagrams + dominant + temporal anchor."""
    result = await service.get_state(session_id)
    return StateResponse(**result)


@router.post("/{session_id}/inject", response_model=InjectResponse)
async def inject_state(session_id: str, req: InjectRequest) -> InjectResponse:
    """Inject state change from Jarvis action. Returns new save string + transition tone."""
    result = await service.inject(
        session_id=session_id,
        hexagram_id=req.hexagram_id,
        phase=req.phase,
        domain=req.domain,
        verb_cluster=req.verb_cluster,
        tool=req.tool,
    )
    return InjectResponse(**result)


@router.post("/{session_id}/tick", response_model=TickResponse)
async def tick_state(session_id: str, req: TickRequest) -> TickResponse:
    """Advance clock, capture state. Returns save string + journey markers."""
    result = await service.tick(
        session_id=session_id,
        tick_count=req.tickCount,
        event=req.event,
    )
    return TickResponse(**result)


@router.get("/{session_id}/usage", response_model=UsageResponse)
async def get_usage(
    session_id: str,
    hexagram_id: int = Query(..., ge=1, le=512),
    domain: str = Query(...),
) -> UsageResponse:
    """Get usage history for a hexagram/domain combination."""
    result = await service.get_usage(session_id, hexagram_id, domain)
    return UsageResponse(**result)


@router.get("/{session_id}/time", response_model=TimeResponse)
async def get_time(session_id: str) -> TimeResponse:
    """Get temporal anchor + tick history."""
    result = await service.get_time(session_id)
    return TimeResponse(**result)


@router.get("/{session_id}/domain/{world}", response_model=DomainResponse)
async def get_domain(session_id: str, world: str) -> DomainResponse:
    """Get all hexagrams mapped to a game domain (e.g. lumbridge, varrock)."""
    result = await service.get_domain(session_id, world)
    return DomainResponse(**result)


# ── Validation Utility ──

@router.get("/{session_id}/validate")
async def validate_save(session_id: str) -> dict:
    """Validate the current save string format."""
    state = await service.get_state(session_id)
    save_str = state["saveString"]
    is_valid = validate_save_string(save_str)
    try:
        parsed = AvatarSaveString.from_compact(save_str)
        return {
            "valid": is_valid,
            "saveString": save_str,
            "parsed": {
                "hex_id": parsed.hex_id,
                "phase": parsed.phase_full,
                "domain": parsed.domain,
                "timestamp": parsed.iso_timestamp,
            },
        }
    except ValueError as exc:
        return {"valid": False, "saveString": save_str, "error": str(exc)}
