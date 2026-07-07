"""GlobeStateLimb — swarm broadcast consumer for King Wen consensus state.

Subscribes to the local``KINGWEN_CONSENSUS_UPDATE`` bus event and forwards
real emotional telemetry to the POG2 multiplayer globe WebSocket.

Dependency: optional ``websockets`` package.  If absent, this limb is a no-op
and emits no fabricated state.  This file is the only OpenJarvis path that
touches the external globe; all other code remains local.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_GLOBE_WS_URL = os.environ.get(
    "OPENJARVIS_GLOBE_WS_URL",
    "wss://openjarvis-kingwen-globe.kristain33rs.workers.dev/parties/globe/default",
)


@dataclass(slots=True)
class GlobeConsensusEnvelope:
    ts: float
    source: str = "openjarvis_fulcrum"
    session_id: Optional[str] = None
    agent: Optional[str] = None
    hexagram_id: Optional[str] = None
    hexagram_name: Optional[str] = None
    phase_temporal: Optional[str] = None
    porosity: Optional[float] = None
    voiceWeight: Optional[float] = None
    coherence: Optional[float] = None
    chaos: Optional[float] = None
    whimsy: Optional[float] = None
    darkTone: Optional[float] = None
    trajectory: Optional[str] = None
    broadcast_mode: Optional[str] = None
    agent_autonomy: Optional[float] = None
    memory_sync_interval: Optional[float] = None
    swarm_broadcast_enabled: Optional[bool] = None
    emotional_tongue: dict[str, Any] = field(default_factory=dict)
    training_weight_vectors: dict[str, Any] = field(default_factory=dict)
    ack: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        data = {
            "type": "KINGWEN_CONSENSUS_UPDATE",
            "timestamp": self.ts,
            "source": self.source,
            "session_id": self.session_id,
            "agent": self.agent,
            "hexagram_id": self.hexagram_id,
            "hexagram_name": self.hexagram_name,
            "phase_temporal": self.phase_temporal,
            "porosity": self.porosity,
            "voiceWeight": self.voiceWeight,
            "coherence": self.coherence,
            "chaos": self.chaos,
            "whimsy": self.whimsy,
            "darkTone": self.darkTone,
            "trajectory": self.trajectory,
            "broadcast_mode": self.broadcast_mode,
            "agent_autonomy": self.agent_autonomy,
            "memory_sync_interval": self.memory_sync_interval,
            "swarm_broadcast_enabled": self.swarm_broadcast_enabled,
            "emotional_tongue": self.emotional_tongue,
            "training_weight_vectors": self.training_weight_vectors,
        }
        if self.ack:
            data["ack"] = self.ack
        if self.error:
            data["error"] = self.error
        return data


class GlobeStateLimb:
    """Async WebSocket client that forwards King Wen consensus events."""

    def __init__(self, ws_url: str = _GLOBE_WS_URL) -> None:
        self._ws_url = ws_url
        self._available: bool = self._probe()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Return whether the underlying websockets transport is installed."""
        return self._available

    async def broadcast(self, envelope: GlobeConsensusEnvelope) -> GlobeConsensusEnvelope:
        """Send one consensus envelope to the globe and capture the ack."""
        envelope.ack = None
        envelope.error = None
        if not self._available:
            envelope.error = "websockets_not_installed"
            return envelope
        try:
            ack = await asyncio.wait_for(
                self._send(envelope),
                timeout=5.0,
            )
            envelope.ack = ack
        except asyncio.TimeoutError:
            envelope.ack = {"status": "sent_no_ack"}
        except Exception as exc:
            envelope.error = f"{type(exc).__name__}: {exc}"
        return envelope

    # ------------------------------------------------------------------
    # Internal transport
    # ------------------------------------------------------------------

    def _probe(self) -> bool:
        try:
            import websockets  # noqa: F401
            return True
        except ImportError:
            logger.debug("GlobeStateLimb disabled: websockets package not installed")
            return False

    async def _send(self, envelope: GlobeConsensusEnvelope) -> dict[str, Any]:
        import websockets  # type: ignore[import-untyped]

        async with websockets.connect(
            self._ws_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            await ws.send(json.dumps(envelope.to_payload()))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                return json.loads(raw)
            except asyncio.TimeoutError:
                return {"status": "sent_no_ack"}
