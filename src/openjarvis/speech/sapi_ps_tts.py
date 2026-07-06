"""Windows SAPI voice via PowerShell wrapper — zero external packages.

Dependencies:
- PowerShell 5+ (shipped with Windows 10/11)
- .NET System.Speech.Synthesis (built into Windows, not a NuGet package)

No pywin32, no httpx, no cloud API. Pure OS surface.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult


@TTSRegistry.register("sapi_ps")
class SapiPsTTSBackend(TTSBackend):
    """Windows Speech API via PowerShell — local, offline, zero deps."""

    backend_id = "sapi_ps"
    _DEFAULT_VOICE = "Microsoft Zira Desktop"
    _SAMPLE_RATE = 24000

    def __init__(self) -> None:
        # PowerShell path — use pwsh if present, else WindowsPowerShell.
        self._ps = self._find_powershell()
        if not self._ps:
            raise RuntimeError(
                "PowerShell not found on PATH. "
                "Install PowerShell 7+ or ensure powershell.exe is available."
            )

    @staticmethod
    def _find_powershell() -> Optional[str]:
        for candidate in ["pwsh", "powershell"]:
            try:
                subprocess.run(
                    [candidate, "-NoProfile", "-Command", "Write-Output 1"],
                    capture_output=True,
                    timeout=10,
                    check=True,
                )
                return candidate
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
        return None

    def _synthesize_ps(self, text: str, voice: str, speed: float) -> bytes:
        """Run PowerShell SAPI and return raw WAV bytes."""
        # Escape text for PowerShell string literal.
        safe = (
            text.replace("'", "''")
            .replace('"', '`"')
            .replace("\r", "`r")
            .replace("\n", "`n")
        )
        # SAPI rate: -10..+10. Map speed 0.85-1.25 -> -10..+10.
        rate = max(-10, min(10, int(round((speed - 1.0) * 10.0))))
        ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
synth.Voice = (Get-Voice | Where-Object {{ $_.Name -like '*{voice}*' }} | Select-Object -First 1)
if (-not $synth.Voice) {{ $synth.Voice = $synth.GetVoices() | Select-Object -First 1 }}
synth.Rate = {rate}
$out = Join-Path $env:TEMP ('jarvis-sapi-ps-' + [guid]::NewGuid() + '.wav')
synth.SetOutputToWaveFile($out)
synth.Speak('{safe}')
synth.Dispose()
[IO.File]::ReadAllBytes($out)
Remove-Item $out -Force
"""
        completed = subprocess.run(
            [self._ps, "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=120,
            check=True,
        )
        return completed.stdout

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

        # Voice selection: prefer hint, fallback to any installed Zira variant.
        voice = voice_id or self._DEFAULT_VOICE
        if not any(part in voice.lower() for part in ["zira", "david", "hazel"]):
            voice = self._DEFAULT_VOICE

        audio = self._synthesize_ps(text, voice=voice, speed=speed)
        return TTSResult(
            audio=audio,
            format="wav",
            voice_id=voice,
            sample_rate=self._SAMPLE_RATE,
            duration_seconds=0.0,
            metadata={"backend": "sapi_ps", "engine": "System.Speech", "rate": int(round((speed - 1.0) * 10.0))},
        )

    def available_voices(self) -> List[str]:
        ps_script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.GetVoices() | ForEach-Object { $_.Name }
$synth.Dispose()
"""
        try:
            completed = subprocess.run(
                [self._ps, "-NoProfile", "-Command", ps_script],
                capture_output=True,
                timeout=30,
                check=True,
            )
            names = [
                line.strip()
                for line in completed.stdout.decode("utf-8", errors="replace").splitlines()
                if line.strip()
            ]
            return names or [self._DEFAULT_VOICE]
        except Exception:
            return [self._DEFAULT_VOICE]

    def health(self) -> bool:
        if not self._ps:
            return False
        try:
            subprocess.run(
                [self._ps, "-NoProfile", "-Command", "Write-Output 1"],
                capture_output=True,
                timeout=5,
                check=True,
            )
            return True
        except Exception:
            return False


__all__ = ["SapiPsTTSBackend"]
