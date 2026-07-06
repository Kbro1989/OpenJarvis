"""Oracle voice helper — King Wen worker consult + Cloudflare aura-2-en synthesis.

Interface contract with chat_cmd.py:
- oracle_speak_async(text, *, on_done=None) -> Future
  Result dict keys: audio_path, hexagram_id, hexagram_name, phase_temporal,
  trajectory, text_spoken, backend, dominant_axis, agree_temporal, error
- shutdown() -> None
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# ---------------------------------------------------------------------------
# Deterministic output directory
# ---------------------------------------------------------------------------
_ORACLE_VOICE_DIR = (
    Path(os.environ.get("OPENJARVIS_HOME", "~/.openjarvis")).expanduser()
    / "oracle-voice"
)
_ORACLE_VOICE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# King Wen worker
# ---------------------------------------------------------------------------
_KINGWEN_WORKER_URL = os.environ.get(
    "KINGWEN_WORKER_URL",
    "https://kingwen-oracle.kristain33rs.workers.dev",
)


def _consult_worker(
    text: str,
    session_id: str,
    emotional_input: int,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    import urllib.request

    body = json.dumps(
        {
            "text": text,
            "session_id": session_id,
            "emotional_input": emotional_input,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{_KINGWEN_WORKER_URL}/consult",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Cloudflare AI TTS
# ---------------------------------------------------------------------------
_KINGWEN_TTS_URL = os.environ.get(
    "KINGWEN_TTS_URL",
    "https://kingwen-oracle.kristain33rs.workers.dev/tts",
)


def _tts_worker(text: str, speaker: str = "luna", timeout: float = 30.0) -> bytes:
    import urllib.request

    payload = json.dumps({"text": text, "speaker": speaker}).encode("utf-8")
    req = urllib.request.Request(
        _KINGWEN_TTS_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _tts_worker_with_vector(
    text: str,
    vector: Dict[str, float],
    porosity: Optional[float],
    trajectory: str,
    agree_temporal: str,
    session_id: str = "openjarvis",
    timeout: float = 30.0,
) -> Tuple[bytes, Dict[str, str]]:
    import urllib.request

    payload: Dict[str, Any] = {
        "text": text,
        "vector": {
            "voiceWeight": vector.get("voiceWeight", 0.0),
            "coherence": vector.get("coherence", 0.0),
            "chaos": vector.get("chaos", 0.0),
            "whimsy": vector.get("whimsy", 0.0),
            "darkTone": vector.get("darkTone", 0.0),
        },
        "session_id": session_id,
    }
    if porosity is not None:
        payload["porosity"] = porosity
    if trajectory:
        payload["trajectory"] = trajectory
    if agree_temporal:
        payload["agree_temporal"] = agree_temporal

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _KINGWEN_TTS_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.read(), headers


def _get_cloudflare_tts() -> Any:
    try:
        from openjarvis.speech.cloudflare_ai_tts import CloudflareAITTSBackend

        backend = CloudflareAITTSBackend()
        if backend.health():
            return backend
    except Exception:
        pass
    raise RuntimeError(
        "Cloudflare AI TTS not available. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN, "
        "or install httpx."
    )


def _get_cartesia_adapter() -> Any:
    from openjarvis.speech.cartesia_tts import CartesiaTTSBackend

    backend = CartesiaTTSBackend()
    if not backend.health():
        raise RuntimeError("Cartesia backend not available: missing CARTESIA_API_KEY or adapter setup.")
    return backend.get_adapter()


def _synthesize(text: str, speaker: str, vector: Dict[str, float]) -> Dict[str, Any]:
    errors = []
    try:
        audio = _tts_worker(text, speaker)
        if audio:
            return {
                "audio": audio,
                "backend": "kingwen-worker-tts",
                "speaker": speaker,
                "model": "@cf/deepgram/aura-2-en",
            }
    except Exception as exc:
        errors.append(f"kingwen-worker:{exc}")

    try:
        backend = _get_cloudflare_tts()
        result = backend.synthesize(text, voice_id=speaker)
        audio = getattr(result, "audio", None) or result.get("audio")
        if audio:
            return {
                "audio": audio,
                "backend": "cloudflare_workers_ai",
                "speaker": speaker,
                "model": "@cf/deepgram/aura-2-en",
            }
    except Exception as exc:
        errors.append(f"cloudflare:{exc}")

    try:
        adapter = _get_cartesia_adapter()
        result = adapter.synthesize(
            text=text,
            vector=vector,
            trajectory="still",
            agree_temporal="present",
        )
        audio = result.get("audio")
        if audio:
            return {
                "audio": audio,
                "backend": "cartesia",
                "speaker": speaker,
                "model": "sonic-3.5",
            }
    except Exception as exc:
        errors.append(f"cartesia:{exc}")

    return {
        "audio": None,
        "backend": "none",
        "error": "; ".join(errors) if errors else "No TTS backend available",
    }


# ---------------------------------------------------------------------------
# Speaker mapping — dominant axis → aura-2 voice
# ---------------------------------------------------------------------------
_SPEAKER_MAP: Dict[str, str] = {
    "voiceWeight": "zeus",
    "darkTone": "orion",
    "chaos": "apollo",
    "coherence": "athena",
    "whimsy": "hermes",
}


def _dominant_axis(vector: Dict[str, float]) -> str:
    best = "coherence"
    best_val = 0.0
    for k, v in vector.items():
        if v > best_val:
            best_val = v
            best = k
    return best


def _select_speaker(vector: Dict[str, float]) -> str:
    return _SPEAKER_MAP.get(_dominant_axis(vector), "luna")


# ---------------------------------------------------------------------------
# Vector extraction
# ---------------------------------------------------------------------------
def _extract_vector(consult: Dict[str, Any]) -> Dict[str, float]:
    tongue = consult.get("emotional_tongue") or {}
    raw = tongue.get("training_weight_vectors") or {}
    return {
        "chaos": raw.get("chaos", 0.0),
        "whimsy": raw.get("whimsy", 0.0),
        "darkTone": raw.get("darkTone", 0.0),
        "coherence": raw.get("coherence", 0.0),
        "voiceWeight": raw.get("voiceWeight", 0.0),
    }


# ---------------------------------------------------------------------------
# Text selection
# ---------------------------------------------------------------------------
def _select_text(consult: Dict[str, Any], user_text: str, text_source: str) -> str:
    if text_source == "unified_weave":
        return consult.get("unified_weave", "") or user_text
    if text_source == "training_notes":
        return consult.get("trainingNotes", "") or user_text
    if text_source == "user_query":
        return user_text

    vector = _extract_vector(consult)
    dominant = _dominant_axis(vector)
    minimal_map = {
        "voiceWeight": "Assert.",
        "darkTone": "Yield.",
        "chaos": "Wait.",
        "coherence": "Hold.",
        "whimsy": "Begin.",
    }
    return minimal_map.get(dominant, "Listen.")


# ---------------------------------------------------------------------------
# Core synchronous path
# ---------------------------------------------------------------------------
def oracle_speak(
    user_text: str,
    *,
    text_source: str = "unified_weave",
    session_id: str = "openjarvis",
    emotional_input: int,
) -> Dict[str, Any]:
    """Run consult → synthesize → write artifact. Returns result dict."""
    _ensure_voice_reward_sidecar()
    if not user_text.strip():
        return _error_result("Empty text", text_source)

    try:
        consult = _consult_worker(
            user_text,
            session_id=session_id,
            emotional_input=emotional_input,
        )
    except Exception as exc:
        return _error_result(f"Worker consult failed: {exc}", user_text, text_source)

    if "error" in consult:
        return _error_result(
            consult["error"], user_text, text_source, consult.get("hexagram_id")
        )

    vector = _extract_vector(consult)
    hexagram_id = int(consult.get("hexagram_id") or 0)
    text_spoken = _select_text(consult, user_text, text_source)
    speaker = _select_speaker(vector)
    dominant = _dominant_axis(vector)
    porosity = (
        consult.get("emotional_tongue", {}).get("porosity")
        if isinstance(consult.get("emotional_tongue"), dict)
        else None
    )
    trajectory = consult.get("trajectory") or "still"
    agree_temporal = consult.get("phase_temporal") or "present"

    audio_bytes = None
    backend = "none"
    dsp_meta: Dict[str, Any] = {}
    headers: Dict[str, str] = {}

    try:
        audio_bytes, headers = _tts_worker_with_vector(
            text_spoken,
            vector,
            porosity=porosity,
            trajectory=trajectory,
            agree_temporal=agree_temporal,
            session_id=session_id,
        )
        backend = "kingwen-worker-tts"
    except Exception as exc:
        audio_bytes = None
        dsp_meta = {"error": f"kingwen-worker-vector:{exc}"}

    if not audio_bytes:
        try:
            synth = _synthesize(text_spoken, speaker, vector)
            audio_bytes = synth.get("audio")
            backend = synth.get("backend", "unknown")
            headers = {}
            dsp_meta = synth.get("error") or {}
        except Exception as exc:
            return {
                "audio_path": "",
                "error": f"TTS synthesis failed: {exc}",
                "hexagram_id": hexagram_id,
                "hexagram_name": consult.get("hexagram_name", ""),
                "phase_temporal": agree_temporal,
                "trajectory": trajectory,
                "text_spoken": text_spoken,
                "backend": "none",
                "dominant_axis": dominant,
                "agree_temporal": agree_temporal,
                "voice_vector": vector,
                "porosity": porosity,
                "compliance": "reject",
                "violations": [],
                "session_id": session_id,
                "dsp_meta": {},
            }

    if audio_bytes:
        try:
            from openjarvis.cli.audio_dsp import modulate_with_headers

            audio_bytes, dsp_meta = modulate_with_headers(audio_bytes, headers)
            backend = f"{backend}+dsp"
        except Exception as exc:
            dsp_meta = {"error": f"dsp:{exc}"}

    dst = _ORACLE_VOICE_DIR / f"hex-{hexagram_id:02d}-{agree_temporal}.mp3"
    try:
        dst.write_bytes(audio_bytes)
        final_path = str(dst)
    except Exception as exc:
        return {
            "audio_path": "",
            "error": f"write_bytes failed: {exc}",
            "hexagram_id": hexagram_id,
            "hexagram_name": consult.get("hexagram_name", ""),
            "phase_temporal": agree_temporal,
            "trajectory": trajectory,
            "text_spoken": text_spoken,
            "backend": backend,
            "dominant_axis": dominant,
            "agree_temporal": agree_temporal,
            "voice_vector": vector,
            "porosity": porosity,
            "compliance": headers.get("X-Kingwen-Compliance", "reject"),
            "violations": (headers.get("X-Kingwen-Violations") or "").split(",") if headers.get("X-Kingwen-Violations") else [],
            "session_id": session_id,
            "dsp_meta": dsp_meta,
        }

    compliance = headers.get("X-Kingwen-Compliance", "compliant")
    violations = (headers.get("X-Kingwen-Violations") or "").split(",") if headers.get("X-Kingwen-Violations") else []
    result = {
        "audio_path": final_path,
        "hexagram_id": hexagram_id,
        "hexagram_name": consult.get("hexagram_name", ""),
        "phase_temporal": agree_temporal,
        "trajectory": trajectory,
        "text_spoken": text_spoken,
        "backend": backend,
        "dominant_axis": dominant,
        "agree_temporal": agree_temporal,
        "voice_vector": vector,
        "porosity": porosity,
        "compliance": compliance,
        "violations": violations,
        "session_id": session_id,
        "dsp_meta": dsp_meta,
    }
    _publish_kingwen_voice_event(result)
    return result


def _error_result(
    error: str,
    user_text: str,
    text_source: str,
    hexagram_id: int = 0,
    voice_vector: Optional[Dict[str, float]] = None,
    porosity: Optional[float] = None,
    compliance: str = "reject",
    violations: Optional[list[str]] = None,
    session_id: str = "",
) -> Dict[str, Any]:
    return {
        "audio_path": "",
        "error": error,
        "hexagram_id": hexagram_id,
        "hexagram_name": "",
        "phase_temporal": "",
        "trajectory": "",
        "text_spoken": user_text if text_source == "user_query" else "",
        "backend": "cloudflare_workers_ai",
        "dominant_axis": "",
        "agree_temporal": "",
        "voice_vector": voice_vector or {},
        "porosity": porosity,
        "compliance": compliance,
        "violations": violations or [],
        "session_id": session_id,
        "dsp_meta": {},
    }


# --------------------------------------------------------------------------- #
# King Wen training loop bridge                                               #
# --------------------------------------------------------------------------- #
def _publish_kingwen_voice_event(result: Dict[str, Any]) -> None:
    """Publish King Wen voice completion to EventBus for training loop.

    No global trace context exists. EventBus is the sole channel.
    Trace attachment, if needed later, must be explicit.
    """
    try:
        from openjarvis.core.events import EventBus, EventType, get_event_bus

        bus = get_event_bus()
        event_data = {
            "hexagram_id": result.get("hexagram_id"),
            "phase_temporal": result.get("phase_temporal"),
            "voice_vector": result.get("voice_vector", {}),
            "porosity": result.get("porosity"),
            "backend": result.get("backend", ""),
            "compliance": result.get("compliance", "compliant"),
            "violations": result.get("violations", []),
            "dsp_meta": result.get("dsp_meta", {}),
            "session_id": result.get("session_id", ""),
            "timestamp": time.time(),
        }
        bus.publish(EventType.KINGWEN_VOICE_COMPLETE, event_data)
    except Exception:
        # Training bridge must never break voice synthesis
        pass


# --------------------------------------------------------------------------- #
# Async wrapper — matches chat_cmd.py interface                               #
# --------------------------------------------------------------------------- #
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oracle-voice")


def oracle_speak_async(
    text: str,
    *,
    on_done: Optional[Callable[[Any], None]] = None,
    **kwargs: Any,
) -> Any:
    """Submit oracle_speak to background thread. Returns Future."""
    future = _executor.submit(oracle_speak, text, **kwargs)
    if on_done is not None:
        future.add_done_callback(lambda fut: on_done(fut))
    return future


def shutdown() -> None:
    """Shutdown the background executor. Call on process exit."""
    _executor.shutdown(wait=False)


# --------------------------------------------------------------------------- #
# Voice reward sidecar                                                         #
# --------------------------------------------------------------------------- #
_started_voice_reward_sidecar = False


def _ensure_voice_reward_sidecar() -> None:
    global _started_voice_reward_sidecar
    if _started_voice_reward_sidecar:
        return
    try:
        from openjarvis.speech.voice_reward_sidecar import start_voice_reward_sidecar

        start_voice_reward_sidecar()
        _started_voice_reward_sidecar = True
    except Exception as exc:
        LOGGER.warning("Voice reward sidecar failed to start: %s", exc)
