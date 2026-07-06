"""Cloudflare Workers AI TTS backend — aura-2-en.

Uses the Cloudflare AI REST API for context-aware text-to-speech.
Requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN env/config.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

_AI_BASE = "https://api.cloudflare.com/client/v4/accounts"
_MODEL = "@cf/deepgram/aura-2-en"
_DEFAULT_SPEAKER = "luna"


@TTSRegistry.register("cloudflare_ai")
class CloudflareAITTSBackend(TTSBackend):
    """Cloudflare Workers AI TTS backend — context-aware voice via aura-2."""

    backend_id = "cloudflare_ai"

    def __init__(
        self,
        *,
        account_id: str = "",
        api_token: str = "",
        model: str = _MODEL,
        speaker: str = _DEFAULT_SPEAKER,
        encoding: str = "mp3",
        sample_rate: int | None = None,
        bit_rate: int | None = None,
    ) -> None:
        self._account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        self._api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN", "")
        self._model = model or _MODEL
        self._speaker = speaker or _DEFAULT_SPEAKER
        self._encoding = encoding or "mp3"
        self._sample_rate = sample_rate
        self._bit_rate = bit_rate

    def _endpoint(self) -> str:
        if not self._account_id:
            raise RuntimeError("CLOUDFLARE_ACCOUNT_ID is not set")
        return f"{_AI_BASE}/{self._account_id}/ai/run/{self._model}"

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
        language: str = "",
    ) -> TTSResult:
        if not self._api_token:
            raise RuntimeError("CLOUDFLARE_API_TOKEN not set")

        if not text.strip():
            raise RuntimeError("Empty text passed to Cloudflare AI TTS")

        speaker = voice_id or self._speaker
        encoding = output_format or self._encoding

        body: dict[str, Any] = {
            "text": text,
            "speaker": speaker,
            "encoding": encoding,
        }
        if self._sample_rate is not None:
            body["sample_rate"] = self._sample_rate
        if self._bit_rate is not None:
            body["bit_rate"] = self._bit_rate

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                self._endpoint(),
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            audio = resp.content

        return TTSResult(
            audio=audio,
            format=encoding,
            voice_id=speaker,
            metadata={
                "backend": "cloudflare_workers_ai",
                "model": self._model,
                "speaker": speaker,
            },
        )

    def available_voices(self) -> list[str]:
        return [
            "amalthea", "andromeda", "apollo", "arcas", "aries", "asteria", "athena",
            "atlas", "aurora", "callista", "cora", "cordelia", "delia", "draco",
            "electra", "harmonia", "helena", "hera", "hermes", "hyperion", "iris",
            "janus", "juno", "jupiter", "luna", "mars", "minerva", "neptune",
            "odysseus", "ophelia", "orion", "orpheus", "pandora", "phoebe", "pluto",
            "saturn", "thalia", "theia", "vesta", "zeus",
        ]

    def health(self) -> bool:
        return bool(self._account_id and self._api_token)
