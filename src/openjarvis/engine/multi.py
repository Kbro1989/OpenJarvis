"""Multi-engine wrapper — routes requests to the right backend by model name."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Dict, List

from openjarvis.core.types import Message
from openjarvis.engine._base import InferenceEngine
from openjarvis.engine._stubs import StreamChunk
from openjarvis.routing.model_router import UnifiedModelRouter

logger = logging.getLogger(__name__)


class MultiEngine(InferenceEngine):
    """Wraps multiple engines and routes by model name.

    Uses ``UnifiedModelRouter`` for reputation/cooldown-aware selection
    with save-string persistence.
    """

    engine_id = "multi"

    def __init__(self, engines: list[tuple[str, InferenceEngine]]) -> None:
        self._engines = engines
        self._model_map: Dict[str, InferenceEngine] = {}
        self._refresh_map()
        self._router = UnifiedModelRouter()

    def _refresh_map(self) -> None:
        self._model_map.clear()
        for _key, engine in self._engines:
            try:
                for model_id in engine.list_models():
                    self._model_map[model_id] = engine
            except Exception as exc:
                logger.debug("Failed to list models for %s: %s", _key, exc)

    _CLOUD_PREFIXES = ("gpt-", "o1-", "o3-", "o4-", "claude-", "gemini-", "openrouter/")

    def select_model(self, model: str, task_type: str = "general") -> Dict[str, Any]:
        """Pick the best model/slot via UnifiedModelRouter.

        Prefers the requested model if it is live. Falls back to the router's
        best-live-slot only when the requested model is unavailable.
        """
        provider_key = None
        for key, _eng in self._engines:
            if model in self._model_map and self._model_map[model] is _eng:
                provider_key = key
                break

        candidates = [{"model": m, "provider": key} for key, _eng in self._engines for m in self._model_map.keys()]
        if provider_key and self._router.is_slot_live(provider_key, model):
            engine = self._model_map[model]
            return {
                "model": model,
                "provider": provider_key,
                "engine": engine,
                "reputation": float(self._router.slot_reputation(provider_key, model)),
                "via": "requested",
                "kingwen_bias": self._router.kingwen_consciousness_bias(depth="small", task_type=task_type or "general"),
            }

        fallback = {"provider": "cloud", "model": model} if any(model.startswith(p) for p in self._CLOUD_PREFIXES) else None
        result = self._router.route(candidates, depth="small", task_type=task_type or "general", fallback=fallback)
        selected_model = result.get("model") or model
        engine = self._model_map.get(selected_model)
        if engine is None:
            engine = self._engine_for(model)
        return {
            "model": selected_model,
            "provider": result.get("provider"),
            "engine": engine,
            "reputation": result.get("reputation", 0.0),
            "via": result.get("via", "fallback"),
            "kingwen_bias": result.get("kingwen_bias", {}),
        }

    def _engine_for(self, model: str) -> InferenceEngine:
        """Find the engine that owns a model, refreshing the map once if needed."""
        engine = self._model_map.get(model)
        if engine is not None:
            return engine
        # Refresh and retry (a new model may have been pulled)
        self._refresh_map()
        engine = self._model_map.get(model)
        if engine is not None:
            return engine
        # If model looks like a cloud model, route to the cloud engine
        # rather than falling back to the local engine (which would 404).
        if any(model.startswith(p) for p in self._CLOUD_PREFIXES):
            for key, eng in self._engines:
                if key == "cloud":
                    logger.info("Routing cloud model %r to cloud engine", model)
                    return eng
        # Non-cloud models: do NOT silently fall back to cloud. A transient
        # vLLM outage during a long agentic run would otherwise route every
        # call to cloud, producing confusing "invalid model ID" errors
        # across all tasks.
        raise ValueError(
            f"Model {model!r} not found in any engine "
            f"(known: {', '.join(sorted(self._model_map.keys())) or '<none>'}). "
            f"Check that the expected backend (e.g. vLLM server) is reachable."
        )

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._engine_for(model).generate(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        async for token in self._engine_for(model).stream(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield token

    async def stream_full(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator["StreamChunk"]:
        """Delegate stream_full() to the engine that owns the model."""
        engine = self._engine_for(model)
        async for chunk in engine.stream_full(messages, model=model, **kwargs):
            yield chunk

    def list_models(self) -> List[str]:
        self._refresh_map()
        return list(self._model_map.keys())

    def health(self) -> bool:
        return any(engine.health() for _key, engine in self._engines)

    def close(self) -> None:
        for _key, engine in self._engines:
            engine.close()


__all__ = ["MultiEngine"]
