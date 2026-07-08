"""King Wen consensus router — execution-layer policy for Jarvis workflows.

Subscribes to King Wen consult/voice events on the EventBus,
computes porosity/vector-based routing decisions, and republishes
KINGWEN_CONSENSUS_UPDATE events for workflow tooling to consume.

Constraints:
- No hard dependency on Cloudflare bindings from this module.
- No mock/stub/placeholder.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)


def _get_event_bus() -> tuple[Any, Any]:
    from openjarvis.core.events import EventBus, EventType, get_event_bus
    return get_event_bus(), EventType


class KingWenConsensusRouter:
    def __init__(self) -> None:
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        bus, EventType = _get_event_bus()
        bus.subscribe(EventType.KINGWEN_VOICE_COMPLETE, self._on_voice_complete)
        bus.subscribe(EventType.KINGWEN_VOICE_COMPLETE, self._on_consensus_update)
        self._started = True
        LOGGER.info("KingWenConsensusRouter started")

    def _on_voice_complete(self, event: Any) -> None:
        data = event.data if hasattr(event, "data") else event
        if not isinstance(data, dict):
            return
        decision = self._route(data)
        data["kingwen_route"] = decision

    def _on_consensus_update(self, event: Any) -> None:
        data = event.data if hasattr(event, "data") else event
        if not isinstance(data, dict):
            return
        bus, EventType = _get_event_bus()
        bus.publish(
            EventType.KINGWEN_CONSENSUS_UPDATE,
            {
                "hexagram_id": data.get("hexagram_id"),
                "phase_temporal": data.get("phase_temporal"),
                "voice_vector": data.get("voice_vector", {}),
                "porosity": data.get("porosity"),
                "backend": data.get("backend", ""),
                "compliance": data.get("compliance", "compliant"),
                "violations": data.get("violations", []),
                "dsp_meta": data.get("dsp_meta", {}),
                "session_id": data.get("session_id", ""),
                "timestamp": time.time(),
            },
        )

    def _route(self, event: Dict[str, Any]) -> Dict[str, Any]:
        porosity = self._clamp(event.get("porosity"))
        vector = self._extract_vector(event)
        compliance = self._normalize_compliance(event.get("compliance"))
        dominant = self._dominant_axis(vector)
        trajectory = self._trajectory(vector, porosity)

        route_channel = self._channel(porosity, trajectory, dominant, compliance)
        tool_hint = self._tool_hint(route_channel, dominant, porosity)
        rule = self._rule(route_channel, dominant, porosity, trajectory, event.get("phase_temporal"))

        return {
            "route_channel": route_channel,
            "tool_hint": tool_hint,
            "rule": rule,
            "dominant": dominant,
            "trajectory": trajectory,
            "porosity": porosity,
            "voice_vector": vector,
            "compliance": compliance,
            "session_id": event.get("session_id"),
            "timestamp": event.get("timestamp", time.time()),
        }

    def _extract_vector(self, event: Dict[str, Any]) -> Dict[str, float]:
        tongue = event.get("emotional_tongue") or {}
        raw = tongue.get("training_weight_vectors") or event.get("voice_vector") or {}
        return {
            "chaos": float(raw.get("chaos", 0.0) or 0.0),
            "whimsy": float(raw.get("whimsy", 0.0) or 0.0),
            "darkTone": float(raw.get("darkTone", 0.0) or 0.0),
            "coherence": float(raw.get("coherence", 0.0) or 0.0),
            "voiceWeight": float(raw.get("voiceWeight", 0.0) or 0.0),
        }

    def _dominant_axis(self, vector: Dict[str, float]) -> str:
        best = "coherence"
        best_val = 0.0
        for k, v in vector.items():
            if v > best_val:
                best_val = v
                best = k
        return best

    def _trajectory(self, vector: Dict[str, float], porosity: float) -> str:
        if vector.get("chaos", 0.0) > 0.6 or vector.get("whimsy", 0.0) > 0.7:
            return "diverging"
        if vector.get("coherence", 0.0) >= 0.7 and porosity >= 0.55:
            return "converging"
        return "still"

    def _channel(self, porosity: float, trajectory: str, dominant: str, compliance: float) -> str:
        if compliance < 0.6 and porosity > 0.7:
            return "guided_hold"
        if trajectory == "diverging" and porosity < 0.35:
            return "high_chaos"
        if dominant == "voiceWeight" and porosity >= 0.8 and compliance >= 0.85:
            return "authoritative"
        if dominant == "coherence" and porosity >= 0.55:
            return "coherent_execute"
        if porosity <= 0.25:
            return "decisive"
        if dominant == "whimsy" and porosity >= 0.6:
            return "exploratory"
        if porosity >= 0.75:
            return "suggest"
        return "local_default"

    def _tool_hint(self, route_channel: str, dominant: str, porosity: float) -> Optional[str]:
        mapping = {
            "authoritative": "assert",
            "coherent_execute": "hold_and_execute",
            "decisive": "decisive",
            "high_chaos": "wait",
            "exploratory": "begin",
            "suggest": "suggest",
            "guided_hold": "hold",
            "local_default": None,
        }
        return mapping.get(route_channel)

    def _rule(self, route_channel: str, dominant: str, porosity: float, trajectory: str, temporal: Optional[str]) -> str:
        return " | ".join(
            part
            for part in [
                f"channel={route_channel}",
                f"dominant={dominant}",
                f"porosity={porosity:.3f}",
                f"trajectory={trajectory}",
                f"temporal={temporal or 'present'}",
            ]
            if part
        )

    @staticmethod
    def _clamp(value: Optional[float], lo: float = 0.0, hi: float = 1.0) -> float:
        if value is None:
            return 0.35
        return max(lo, min(hi, float(value)))

    @staticmethod
    def _normalize_compliance(compliance: Optional[str]) -> float:
        return 1.0 if str(compliance or "").lower() == "compliant" else 0.0


__all__ = ["KingWenConsensusRouter"]
