"""Cartesia text-to-speech backend.

Uses the Cartesia REST API. The legacy synthesize() path is preserved for
callers that do not carry emotional state. Oracle callers should use
synthesize_with_emotion() on CartesiaAdapter directly.
"""

from __future__ import annotations

import os
from typing import List

import httpx

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult
from openjarvis.speech.cartesia_adapter import CartesiaAdapter

_CARTESIA_API_BASE = "https://api.cartesia.ai"


def _cartesia_synthesize(
    api_key: str,
    text: str,
    voice_id: str,
    model: str = "sonic",
    output_format: str = "mp3",
    speed: float = 1.0,
    language: str = "en",
) -> bytes:
    """Legacy direct synthesis shim. Does not carry emotional state."""
    resp = httpx.post(
        f"{_CARTESIA_API_BASE}/tts/bytes",
        headers={
            "X-API-Key": api_key,
            "Cartesia-Version": "2024-06-10",
        },
        json={
            "model_id": model,
            "transcript": text,
            "voice": {"mode": "id", "id": voice_id},
            "output_format": {
                "container": output_format,
                "sample_rate": 24000,
                "encoding": "mp3" if output_format == "mp3" else "pcm_f32le",
            },
            "language": language,
            **({"speed": speed} if speed != 1.0 else {}),
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.content


@TTSRegistry.register("cartesia")
class CartesiaTTSBackend(TTSBackend):
    backend_id = "cartesia"

    def __init__(
        self, *, api_key: str = "", model: str = "sonic-3.5", language: str = "en"
    ) -> None:
        self._api_key = api_key or os.environ.get("CARTESIA_API_KEY", "")
        self._model = model
        self._language = language or os.environ.get("CARTESIA_LANGUAGE", "en")
        self._adapter = CartesiaAdapter(self._api_key)
        self._adapter.set_http_client(httpx)

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
        language: str = "",
    ) -> TTSResult:
        """
        Legacy synthesis path for callers that do not carry emotional state.
        Speed is passed through directly. Emotion is not applied.
        """
        if not self._api_key:
            raise RuntimeError("CARTESIA_API_KEY not set")

        if not voice_id:
            voice_id = "a0e99841-438c-4a64-b679-ae501e7d6091"

        audio = _cartesia_synthesize(
            self._api_key,
            text,
            voice_id=voice_id,
            model=self._model,
            output_format=output_format,
            speed=speed,
            language=language or self._language,
        )

        return TTSResult(
            audio=audio,
            format=output_format,
            voice_id=voice_id,
            metadata={"backend": "cartesia", "model": self._model},
        )

    def available_voices(self) -> List[str]:
        if not self._api_key:
            return []
        resp = httpx.get(
            f"{_CARTESIA_API_BASE}/voices",
            headers={
                "X-API-Key": self._api_key,
                "Cartesia-Version": "2024-06-10",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return [v["id"] for v in resp.json()]

    def health(self) -> bool:
        return bool(self._api_key)

    def get_adapter(self) -> CartesiaAdapter:
        """Expose the prosthetic adapter for oracle callers."""
        return self._adapter
