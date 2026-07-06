"""Windows SAPI COM TTS backend — zero external dependencies.

Uses the OS built-in speech synthesiser. No network, no packages,
no model download. Just win32com.shell and the SAPI ISpVoice interface.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult


@TTSRegistry.register("sapi")
class SapiTTSBackend(TTSBackend):
    """Windows Speech API backend — local, offline, zero dependencies."""

    backend_id = "sapi"

    # Default to a known-good Zira voice; caller can override by token/name.
    _DEFAULT_VOICE = "Zira"
    _SAMPLE_RATE = 24000

    def __init__(self) -> None:
        self._voice = None
        self._stream = None
        self._ensure_init()

    def _ensure_init(self) -> None:
        try:
            import win32com.client  # type: ignore[import-untyped]
            from win32com.shell import shell  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "pywin32 is required for SAPI backend. "
                "It ships with the standard CPython install on Windows; "
                f"if missing, install it or fall back to another backend. ({exc})"
            ) from exc

        # Prefer a ZIP-stream format so we can seek/reset without temp files.
        # SSFMCreateForWrite = 2 — gives a real stream with seek/write.
        SPFM_CREATE_ALWAYS = 3
        SPFMT_WAVEFORMATEX = 100  # WAVE audio

        sp_voice = win32com.client.Dispatch("SAPI.SpVoice")
        sp_stream = win32com.client.Dispatch("SAPI.SpFileStream")
        sp_stream.Format.Type = SPFMT_WAVEFORMATEX
        sp_stream.Open(Path(tempfile.gettempdir()) / "jarvissapi.wav", SPFM_CREATE_ALWAYS)

        self._voice = sp_voice
        self._stream = sp_stream

    def _set_voice_by_name(self, name_hint: str) -> None:
        if not name_hint or not self._voice:
            return
        for token in self._voice.GetVoices():
            try:
                desc = token.GetDescription()
            except Exception:
                continue
            if name_hint.lower() in desc.lower():
                self._voice.Voice = token
                return

    def _force_voice(self, desired: str) -> None:
        name = desired or self._DEFAULT_VOICE
        if not self._voice:
            return
        # Try exact match first
        for token in self._voice.GetVoices():
            try:
                desc = token.GetDescription()
            except Exception:
                continue
            if desc.strip().lower() == name.lower() or token.Id.lower().endswith(name.lower()):
                self._voice.Voice = token
                return

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
        language: str = "en",
    ) -> TTSResult:
        if not text:
            raise ValueError("synthesize requires non-empty text.")

        if not self._voice:
            self._ensure_init()

        if voice_id:
            self._force_voice(voice_id)

        # SAPI Rate is -10..+10; 0 is default. Map float speed to that range.
        #   speed 0.0 -> -10
        #   speed 1.0 ->  0
        #   speed 2.0 -> +10
        try:
            rate = int(round((speed - 1.0) * 10.0))
        except Exception:
            rate = 0
        self._voice.Rate = rate

        # Close and reopen the stream to flush the previous utterance.
        if self._stream:
            try:
                self._stream.Close()
            except Exception:
                pass

        tmp_path = Path(tempfile.gettempdir()) / f"jarvis-sapi-{os.getpid()}.wav"
        try:
            self._stream.Open(str(tmp_path), 3)  # SSFMCreateAlways
            self._voice.AudioOutputStream = self._stream
            self._voice.Speak(
                text,
                0,  # notify via event — omitted, run synchronously
            )
            self._stream.Close()
            audio = tmp_path.read_bytes()
        except Exception as exc:
            try:
                self._stream.Close()
            except Exception:
                pass
            raise RuntimeError(f"SAPI synthesis failed: {exc}") from exc
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        return TTSResult(
            audio=audio,
            format="wav",
            voice_id=voice_id or self._DEFAULT_VOICE,
            sample_rate=self._SAMPLE_RATE,
            duration_seconds=0.0,
            metadata={
                "backend": "sapi",
                "engine": "SAPI5",
                "rate": rate,
            },
        )

    def available_voices(self) -> List[str]:
        if not self._voice:
            try:
                self._ensure_init()
            except Exception:
                return [self._DEFAULT_VOICE]
        voices = []
        for token in self._voice.GetVoices():
            try:
                desc = token.GetDescription()
            except Exception:
                continue
            if desc:
                voices.append(desc.strip())
        if not voices:
            voices = [self._DEFAULT_VOICE]
        return voices

    def health(self) -> bool:
        try:
            self._ensure_init()
            return True
        except Exception:
            return False


__all__ = ["SapiTTSBackend"]
