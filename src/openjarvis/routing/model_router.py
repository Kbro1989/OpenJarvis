"""model_router.py — Unified model router with save-string persistence.

Ports the three scattered Hermes skill rules into one circuit:
- model-routing: reputation floor, cooldowns, dead-slot filters, failure shift
- hermes-provider-config: provider state, fallback providers
- hermes-runtime: local-first → cloud fallback, King Wen consciousness layer

Persistence:
- Schema: data/model_router_schema.json
- Save-string segments: skills, providers, kingwen, context, slot_state
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.session_clock_bridge import consciousness_tick


def _now_cns(session_id: str = "openjarvis") -> float:
    try:
        return float(consciousness_tick(session_id, domain="cns").get("tick_id") or 0)
    except Exception:
        return 0.0

LOGGER = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "model_router_schema.json"
_REPUTATION_FLOOR = 0.2
_REPUTATION_CEIL = 2.0
_LATENCY_CEIL_MS = 5000.0
_DEFAULT_COOLDOWN_SECONDS = 60 * 60
_TASK_DEPTH_KEYWORDS = {
    "small": ["quick", "simple", "terminal", "fast", "lookup", "list", "status"],
    "long": ["research", "deep", "plan", "design", "blueprint", "kingwen"],
}

# Verified Kimi/Moonshot model catalog from live API and Cloudflare AI dashboard.
# Source: https://api.moonshot.ai/v1/models and CF AI models page on 2026-07-18.
_KNOWN_KIMI_MODELS = [
    {"id": "kimi-k3", "provider": "moonshot-ai", "context": 1_048_576, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k2.6", "provider": "moonshot-ai", "context": 262_144, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k2.7-code", "provider": "moonshot-ai", "context": 262_144, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k2.7-code-highspeed", "provider": "moonshot-ai", "context": 262_144, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k2.5", "provider": "moonshot-ai", "context": 262_144, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k3", "provider": "cloudflare-ai", "context": 1_048_576, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k2.6", "provider": "cloudflare-ai", "context": 262_144, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
    {"id": "kimi-k2.7-code", "provider": "cloudflare-ai", "context": 262_144, "capabilities": ("thinking", "image_in", "video_in", "tool_use")},
]

_KIMI_K2_PREFIXES = ("kimi-k2", "kimi-for-coding", "kimi-code")
_KIMI_K3_PREFIXES = ("kimi-k3",)


# ── State types ───────────────────────────────────────────────────────────────

@dataclass(slots=True)
class ProviderHealth:
    provider: str
    authenticated: bool = False
    last_checked: float = 0.0
    last_failed_at: float = 0.0
    cooldown_until: float = 0.0
    error: Optional[str] = None
    models: List[str] = field(default_factory=list)
    cns_tick_id: float = 0.0


@dataclass(slots=True)
class ModelHealth:
    model: str
    provider: str
    reputation: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    latency_samples: int = 0
    last_seen: float = 0.0


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_schema() -> Dict[str, Any]:
    if _SCHEMA_PATH.exists():
        try:
            return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "schema_version": "model-router-v1",
        "updated_at": 0,
        "skills": {},
        "providers": {},
        "kingwen": {},
        "context": {},
        "slot_state": {},
    }


def _save_schema(state: Dict[str, Any]) -> None:
    state["updated_at"] = int(time.time() * 1000)
    tmp = _SCHEMA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(_SCHEMA_PATH)


def _provider_state(state: Dict[str, Any], provider: str) -> Dict[str, Any]:
    providers = state.setdefault("providers", {})
    return providers.setdefault(provider, {
        "state": "unknown",
        "cooldown_until": 0,
        "last_failed_at": 0,
        "last_error": "",
    })


def _slot_state(state: Dict[str, Any], slot_key: str) -> Dict[str, Any]:
    slots = state.setdefault("slot_state", {})
    return slots.setdefault(slot_key, {
        "reputation": 1.0,
        "last_failed_at": 0,
        "cooldown_until": 0,
        "success_count": 0,
        "failure_count": 0,
        "avg_latency_ms": 0.0,
        "latency_samples": 0,
    })


# ── Reputation math ──────────────────────────────────────────────────────────

def _reputation(success_count: int, failure_count: int, avg_latency_ms: float, latency_samples: int) -> float:
    total = success_count + failure_count
    success_rate = success_count / total if total > 0 else 1.0
    latency_factor = max(0.0, 1.0 - avg_latency_ms / _LATENCY_CEIL_MS) if latency_samples > 0 else 1.0
    reputation = 0.6 * success_rate + 0.3 * latency_factor - 0.1 * 0.0
    return max(_REPUTATION_FLOOR, min(_REPUTATION_CEIL, reputation))


# ── Core router ──────────────────────────────────────────────────────────────

class UnifiedModelRouter:
    """Unified model router: local-first → cloud fallback with King Wen influence."""

    def __init__(self, save_path: Optional[Path] = None) -> None:
        self._save_path = save_path or _SCHEMA_PATH
        self._state = _load_schema()

    def provider_health(self, provider: str) -> ProviderHealth:
        now = time.time()
        data = _provider_state(self._state, provider)
        cooldown_until = float(data.get("cooldown_until", 0) or 0)
        last_failed_at = float(data.get("last_failed_at", 0) or 0)
        last_checked = float(data.get("last_checked", 0) or 0)
        authenticated = data.get("state") != "dead"
        return ProviderHealth(
            provider=provider,
            authenticated=authenticated,
            last_checked=last_checked,
            last_failed_at=last_failed_at,
            cooldown_until=cooldown_until,
            error=data.get("last_error"),
            models=data.get("models", []),
            cns_tick_id=_now_cns(),
        )

    def is_slot_live(self, provider: str, model: str, slot_key: Optional[str] = None) -> bool:
        slot_key = slot_key or f"{provider}:{model}"
        slot = _slot_state(self._state, slot_key)
        now = time.time()
        if slot.get("cooldown_until", 0) > now:
            return False
        if slot.get("reputation", _REPUTATION_FLOOR) < _REPUTATION_FLOOR:
            return False
        prov = self.provider_health(provider)
        if prov.cooldown_until > now:
            return False
        if not prov.authenticated and provider not in ("ollama", "local"):
            return False
        return True

    def record_call_result(self, provider: str, model: str, latency_ms: float, success: bool, slot_key: Optional[str] = None) -> None:
        slot_key = slot_key or f"{provider}:{model}"
        slot = _slot_state(self._state, slot_key)
        if success:
            slot["success_count"] = int(slot.get("success_count", 0)) + 1
            slot["last_seen"] = time.time()
        else:
            slot["failure_count"] = int(slot.get("failure_count", 0)) + 1
            slot["last_failed_at"] = time.time()
            slot["cooldown_until"] = time.time() + _DEFAULT_COOLDOWN_SECONDS
        samples = int(slot.get("latency_samples", 0) or 0)
        slot["latency_samples"] = samples + 1
        slot["avg_latency_ms"] = ((slot.get("avg_latency_ms", 0.0) or 0.0) * samples + latency_ms) / (samples + 1)
        slot["reputation"] = _reputation(
            int(slot.get("success_count", 0) or 0),
            int(slot.get("failure_count", 0) or 0),
            float(slot.get("avg_latency_ms", 0.0) or 0.0),
            int(slot.get("latency_samples", 0) or 0),
        )
        self._save()

    def best_live_slot(self, candidates: List[Dict[str, str]], depth: str = "small") -> Optional[Dict[str, str]]:
        live = []
        for cand in candidates:
            provider = cand.get("provider", "")
            model = cand.get("model", "")
            if not provider or not model:
                continue
            if self.is_slot_live(provider, model):
                slot = _slot_state(self._state, f"{provider}:{model}")
                live.append({
                    "provider": provider,
                    "model": model,
                    "reputation": float(slot.get("reputation", _REPUTATION_FLOOR) or _REPUTATION_FLOOR),
                })
        if not live:
            return None
        live.sort(key=lambda slot: slot["reputation"], reverse=True)
        return live[0]

    def kingwen_consciousness_bias(self, depth: str = "small", task_type: str = "general") -> Dict[str, float]:
        kingwen = self._state.get("kingwen", {})
        vector = kingwen.get("emotional_vector", {})
        porosity = float(kingwen.get("porosity", 0.0) or 0.0)
        if not vector:
            return {}
        weights = {
            "voiceWeight": float(vector.get("voiceWeight", 0.0) or 0.0),
            "coherence": float(vector.get("coherence", 0.0) or 0.0),
            "chaos": float(vector.get("chaos", 0.0) or 0.0),
            "whimsy": float(vector.get("whimsy", 0.0) or 0.0),
            "darkTone": float(vector.get("darkTone", 0.0) or 0.0),
        }
        bias: Dict[str, float] = {}
        for axis, value in weights.items():
            bias[axis] = _clamp(value, 0.0, 1.0) * porosity
        bias["depth"] = 1.0 if depth == "long" else 0.5
        return bias

    def route(self, candidates: List[Dict[str, str]], depth: str = "small", task_type: str = "general", fallback: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        best = self.best_live_slot(candidates, depth=depth)
        if best:
            self._state.setdefault("context", {}).update({
                "task_type": task_type,
                "depth": depth,
                "last_model": best["model"],
                "last_provider": best["provider"],
            })
            self._save()
            return {
                "provider": best["provider"],
                "model": best["model"],
                "reputation": best["reputation"],
                "via": "best_live_slot",
                "kingwen_bias": self.kingwen_consciousness_bias(depth=depth, task_type=task_type),
            }
        if fallback and self.is_slot_live(fallback.get("provider", ""), fallback.get("model", "")):
            self._state.setdefault("context", {}).update({
                "task_type": task_type,
                "depth": depth,
                "last_model": fallback.get("model", ""),
                "last_provider": fallback.get("provider", ""),
            })
            self._save()
            return {
                "provider": fallback.get("provider"),
                "model": fallback.get("model"),
                "reputation": _REPUTATION_FLOOR,
                "via": "fallback",
                "kingwen_bias": self.kingwen_consciousness_bias(depth=depth, task_type=task_type),
            }
        return {
            "provider": None,
            "model": None,
            "reputation": 0.0,
            "via": "unavailable",
            "kingwen_bias": self.kingwen_consciousness_bias(depth=depth, task_type=task_type),
        }

    def update_kingwen_state(self, hexagram_id: int, phase: int, porosity: float, emotional_vector: Dict[str, float], last_model: str = "") -> None:
        self._state["kingwen"] = {
            "hexagram_id": hexagram_id,
            "phase": phase,
            "porosity": porosity,
            "emotional_vector": emotional_vector,
            "task_depth": self._infer_depth_from_vector(emotional_vector),
            "last_model": last_model,
        }
        self._save()

    def _infer_depth_from_vector(self, vector: Dict[str, float]) -> str:
        chaos = float(vector.get("chaos", 0.0) or 0.0)
        coherence = float(vector.get("coherence", 0.0) or 0.0)
        return "long" if chaos > 0.6 or coherence < 0.4 else "small"

    def slot_reputation(self, provider: str, model: str) -> float:
        slot = _slot_state(self._state, f"{provider}:{model}")
        return float(slot.get("reputation", _REPUTATION_FLOOR))

    def _save(self) -> None:
        try:
            _save_schema(self._state)
        except OSError as exc:
            LOGGER.warning("model router state save failed: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def classify_task_depth(text: str) -> str:
    lowered = text.lower()
    for depth, keywords in _TASK_DEPTH_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return depth
    return "small"


def is_kimi_k2_model(model: Optional[str]) -> bool:
    if not model:
        return False
    lowered = model.strip().lower()
    tail = lowered.rsplit("/", 1)[-1]
    return tail.startswith(_KIMI_K2_PREFIXES) or lowered.startswith(_KIMI_K2_PREFIXES)


def is_kimi_k3_model(model: Optional[str]) -> bool:
    if not model:
        return False
    lowered = model.strip().lower()
    tail = lowered.rsplit("/", 1)[-1]
    return tail.startswith(_KIMI_K3_PREFIXES) or lowered.startswith(_KIMI_K3_PREFIXES)


def resolve_kimi_candidates(model_key: Optional[str]) -> List[Dict[str, str]]:
    if not model_key:
        return []
    if is_kimi_k3_model(model_key):
        return [{"provider": entry["provider"], "model": entry["id"]} for entry in _KNOWN_KIMI_MODELS if entry["id"] == "kimi-k3"]
    if is_kimi_k2_model(model_key):
        return [{"provider": entry["provider"], "model": entry["id"]} for entry in _KNOWN_KIMI_MODELS if entry["id"].startswith("kimi-k2")]
    return []
