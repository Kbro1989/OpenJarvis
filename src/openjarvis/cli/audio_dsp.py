"""Oracle audio DSP — edge-side emotional modulation.

Consumes base audio from worker + King Wen vector payload.
Returns modulated MP3 bytes.

Dependencies: numpy, pydub, scipy
External tool: ffmpeg/ffprobe on PATH for MP3 decode/encode
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from pydub import AudioSegment
from scipy.signal import butter, sosfilt


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

def parse_vector_header(raw: Optional[str]) -> Dict[str, float]:
    if not raw or "|" not in raw:
        return {}
    parts = raw.split("|")
    return {
        "voiceWeight": float(parts[0]),
        "coherence": float(parts[1]),
        "chaos": float(parts[2]),
        "whimsy": float(parts[3]),
        "darkTone": float(parts[4]),
    }


def parse_headers(headers: Dict[str, str]) -> Dict[str, Any]:
    vector = parse_vector_header(headers.get("X-Kingwen-Vector") or headers.get("x-kingwen-vector"))
    porosity = headers.get("X-Kingwen-Porosity") or headers.get("x-kingwen-porosity")
    trajectory = headers.get("X-Kingwen-Trajectory") or headers.get("x-kingwen-trajectory")
    agree_temporal = headers.get("X-Kingwen-Temporal") or headers.get("x-kingwen-temporal")
    session = headers.get("X-Kingwen-Session") or headers.get("x-kingwen-session")
    return {
        "vector": vector,
        "porosity": float(porosity) if porosity is not None else None,
        "trajectory": trajectory or "",
        "agree_temporal": agree_temporal or "",
        "session_id": session or "",
    }


# ---------------------------------------------------------------------------
# DSP primitives
# ---------------------------------------------------------------------------

def _ensure_wav(audio_bytes: bytes, input_format: str = "mp3") -> AudioSegment:
    import io
    if input_format == "wav":
        return AudioSegment.from_wav(io.BytesIO(audio_bytes))
    return AudioSegment.from_mp3(io.BytesIO(audio_bytes))


def _to_numpy(segment: AudioSegment) -> np.ndarray:
    samples = np.array(segment.get_array_of_samples())
    if segment.channels > 1:
        samples = samples.reshape((-1, segment.channels))
    return samples.astype(np.float32) / (2 ** (8 * segment.sample_width - 1))


def _from_numpy(samples: np.ndarray, segment: AudioSegment) -> AudioSegment:
    if segment.channels > 1 and samples.ndim == 1:
        samples = np.tile(samples.reshape(-1, 1), (1, segment.channels))
    int_samples = (samples * (2 ** (8 * segment.sample_width - 1))).astype(
        getattr(np, {1: 'int8', 2: 'int16', 3: 'int32', 4: 'int32'}.get(segment.sample_width, 'int16'))
    )
    return segment._spawn(int_samples.tobytes())


def _butter_low_shelf(cutoff: float, fs: float, gain_db: float) -> np.ndarray:
    # simple first-order low shelf approximation via biquad SOS
    if abs(gain_db) < 0.01:
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=np.float64)
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * cutoff / fs
    alpha = np.sin(w0) / 2 * np.sqrt((A * A + 1) / A - 1) if A > 0 else np.sin(w0) / 2
    b0 = A * ((A + 1) - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha)
    b1 = 2 * A * ((A - 1) - (A + 1) * np.cos(w0))
    b2 = A * ((A + 1) - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)
    a0 = (A + 1) + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha
    a1 = -2 * ((A - 1) + (A + 1) * np.cos(w0))
    a2 = (A + 1) + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha
    sos = np.array([[b0, b1, b2, a0, a1, a2]]) / a0
    return sos.astype(np.float64)


def _apply_eq(samples: np.ndarray, sr: int, dark_tone: float) -> np.ndarray:
    # darkTone 0..1 -> low shelf boost 200Hz from -6dB to +6dB
    gain_db = -6.0 + 12.0 * max(0.0, min(1.0, dark_tone))
    sos = _butter_low_shelf(200.0, sr, gain_db)
    if samples.ndim == 1:
        shaped = sosfilt(sos, samples, axis=0, zi=None)
        return shaped
    shaped = np.stack([sosfilt(sos, samples[:, ch], axis=0) for ch in range(samples.shape[1])], axis=1)
    return shaped


def _apply_rms(samples: np.ndarray, target_rms_db: float) -> np.ndarray:
    # voiceWeight 0..1 -> RMS target -18dB .. -12dB
    current = np.sqrt(np.mean(samples ** 2))
    if current <= 0:
        return samples
    target_linear = 10 ** (target_rms_db / 20)
    gain = float(target_linear / current)
    gain = max(0.1, min(5.0, gain))
    return samples * gain


def _pitch_shift_stretch(samples: np.ndarray, sr: int, semitones: float, rate_factor: float) -> np.ndarray:
    # Minimal phase-vocoder-like pitch/time shift using librosa if present.
    try:
        import librosa
        y = samples.T if samples.ndim == 2 else samples
        y_shift = librosa.effects.pitch_shift(y=y, sr=sr, n_steps=float(semitones))
        y_stretch = librosa.effects.time_stretch(y=y_shift, rate=float(rate_factor))
        return y_stretch.T if samples.ndim == 2 else y_stretch
    except Exception:
        return samples


# ---------------------------------------------------------------------------
# Contract mapping
# ---------------------------------------------------------------------------

def modulate(audio_bytes: bytes, vector: Dict[str, float], porosity: Optional[float], trajectory: str, agree_temporal: str, input_format: str = "mp3") -> Tuple[bytes, Dict[str, Any]]:
    if not audio_bytes:
        raise ValueError("Empty audio bytes")

    segment = _ensure_wav(audio_bytes, input_format=input_format)
    samples = _to_numpy(segment)
    sr = segment.frame_rate

    chaos = float(vector.get("chaos", 0.0))
    whimsy = float(vector.get("whimsy", 0.0))
    dark_tone = float(vector.get("darkTone", 0.0))
    coherence = float(vector.get("coherence", 0.0))
    voice_weight = float(vector.get("voiceWeight", 0.0))

    # trajectory/base speed
    trajectory_map = {"still": 1.0, "converging": 1.08, "diverging": 0.93, "cycling": 1.0}
    base_rate = trajectory_map.get((trajectory or "still").lower(), 1.0)

    # chaos -> pitch variance + rate jitter
    semitones = chaos * 12.0
    rate_jitter = 1.0 + (0.3 * chaos - 0.15)
    rate = base_rate * (0.85 + 0.4 * rate_jitter)
    if abs(rate - 1.0) > 0.01 or abs(semitones) > 0.01:
        samples = _pitch_shift_stretch(samples, sr, semitones, rate)

    # darkTone -> EQ tilt at 200Hz
    samples = _apply_eq(samples, sr, dark_tone)

    # coherence -> smoothing by mild lowpass dynamics proxy: limit with simple moving average blur if high coherence
    if coherence > 0.7:
        window = max(1, int(0.001 * sr))
        if window > 1:
            kernel = np.ones(window) / window
            if samples.ndim == 1:
                samples = np.convolve(samples, kernel, mode="same")
            else:
                samples = np.stack([np.convolve(samples[:, ch], kernel, mode="same") for ch in range(samples.shape[1])], axis=1)

    # voiceWeight -> amplitude authority
    target_rms_db = -18.0 + 6.0 * max(0.0, min(1.0, voice_weight))
    samples = _apply_rms(samples, target_rms_db)

    # porosity -> transient clarity via high-pass enhancement
    porosity_value = 0.35 if porosity is None else float(porosity)
    hp_mix = max(0.0, min(1.0, porosity_value))
    if abs(hp_mix) > 0.01:
        sos_hp = butter(2, 8000 / (sr / 2), btype="highpass", output="sos")
        if samples.ndim == 1:
            hp = sosfilt(sos_hp, samples)
            samples = samples * (1.0 - hp_mix) + hp * hp_mix
        else:
            hp = np.stack([sosfilt(sos_hp, samples[:, ch]) for ch in range(samples.shape[1])], axis=1)
            samples = samples * (1.0 - hp_mix) + hp * hp_mix

    # temporal framing pre/post padding from agree_temporal is metadata only for DSP, not adjusting audio here
    # agreed temporal label is carried for downstream reasoning and audit.

    out_segment = _from_numpy(np.nan_to_num(samples), segment)
    buf = out_segment.export(format="mp3").read()
    meta = {
        "output_format": "mp3",
        "vector": vector,
        "porosity": porosity_value,
        "trajectory": trajectory,
        "agree_temporal": agree_temporal,
        "darkTone_applied_db": -6.0 + 12.0 * max(0.0, min(1.0, dark_tone)),
        "rms_target_db": target_rms_db,
        "rate_applied": rate,
        "semitones_applied": semitones,
    }
    return buf, meta


def modulate_with_headers(audio_bytes: bytes, headers: Dict[str, str]) -> Tuple[bytes, Dict[str, Any]]:
    parsed = parse_headers(headers)
    return modulate(
        audio_bytes=audio_bytes,
        vector=parsed.get("vector") or {},
        porosity=parsed.get("porosity"),
        trajectory=parsed.get("trajectory") or "",
        agree_temporal=parsed.get("agree_temporal") or "",
    )


def modulate_with_json(audio_bytes: bytes, payload: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    return modulate(
        audio_bytes=audio_bytes,
        vector=payload.get("vector") or {},
        porosity=payload.get("porosity"),
        trajectory=payload.get("trajectory") or "",
        agree_temporal=payload.get("agree_temporal") or "",
    )


__all__ = [
    "parse_vector_header",
    "parse_headers",
    "modulate",
    "modulate_with_headers",
    "modulate_with_json",
]
