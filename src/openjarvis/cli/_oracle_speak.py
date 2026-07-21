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
import platform
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

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


def _http_request_json(url: str, body: dict, *, timeout: float = 30.0) -> dict:
    import httpx

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.post(url, json=body, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()


def _consult_worker(
    text: str,
    session_id: str,
    emotional_input: int,
    timeout: float = 30.0,
    vision_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "text": text,
        "session_id": session_id,
        "emotional_input": emotional_input,
    }
    if vision_data is not None:
        payload["vision_data"] = vision_data
    return _http_request_json(
        f"{_KINGWEN_WORKER_URL}/consult",
        payload,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Cloudflare AI TTS
# ---------------------------------------------------------------------------
_KINGWEN_TTS_URL = os.environ.get(
    "KINGWEN_TTS_URL",
    "https://kingwen-oracle.kristain33rs.workers.dev/tts",
)


def _is_cloud_endpoint(url: str) -> bool:
    host = (url or "").lower()
    return "workers.dev" in host or "cloudflare" in host


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
    import httpx

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

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.post(
            _KINGWEN_TTS_URL,
            json=payload,
            headers={"Accept": "audio/mpeg"},
        )
        resp.raise_for_status()
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
    tried = set()
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
    tried.add("kingwen_worker")

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
    tried.add("cloudflare_ai")

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
    tried.add("cartesia")

    # Fallback: try additional available backends from the registry in order.
    try:
        from openjarvis.speech.backend_registry import available_backends
        for desc in available_backends():
            name = desc.get("name")
            if name in tried or not desc.get("available"):
                continue
            try:
                mod = __import__(desc["module_path"], fromlist=[desc["class_name"]])
                cls = getattr(mod, desc["class_name"])
                instance = cls() if callable(cls) else cls
                if hasattr(instance, "health") and not instance.health():
                    continue
                synthesize_fn = getattr(instance, "synthesize", None)
                if not callable(synthesize_fn):
                    continue
                result = synthesize_fn(text=text)
                audio = getattr(result, "audio", None) or (
                    result.get("audio") if isinstance(result, dict) else None
                )
                if audio:
                    return {
                        "audio": audio,
                        "backend": name,
                        "speaker": speaker,
                        "model": name,
                    }
            except Exception:
                continue
    except Exception:
        pass

    return {
        "audio": None,
        "backend": "none",
        "error": "; ".join(errors) if errors else "No TTS backend available",
    }


# ---------------------------------------------------------------------------
# Playback — closes the oracle-to-speaker circuit
# ---------------------------------------------------------------------------
def _playback_instructions_for(porosity: float | None) -> dict:
    porosity_value = 0.35 if porosity is None else float(porosity)
    if porosity_value < 0.3:
        return {"level": "low", "route": "default", "action": "play_once"}
    if porosity_value < 0.8:
        return {"level": "medium", "route": "secondary", "action": "loop_soft"}
    return {"level": "high", "route": "network", "action": "broadcast"}


def _play_audio_path(audio_path: str, porosity: float | None = None) -> bool:
    """Play an audio artifact through the local system.

    Optional porosity-gated routing via winappaudiorouter when available:
    - low porosity: default endpoint
    - medium porosity: secondary endpoint if present
    - high porosity: network endpoint if present

    Falls back to existing ffplay/winsound/PowerShell chain.
    """
    path = Path(audio_path)
    if not path.exists() or not path.is_file():
        return False

    porosity_value = 0.35 if porosity is None else float(porosity)

    def _default_playback() -> bool:
        system = platform.system()
        try:
            if system == "Windows":
                if shutil.which("ffplay"):
                    subprocess.run(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                    return True
                try:
                    import winsound

                    winsound.PlaySound(str(path), winsound.SND_FILENAME)
                    return True
                except Exception:
                    pass
                ps_cmd = (
                    "Add-Type -AssemblyName presentationCore; "
                    "$p = New-Object System.Windows.Media.MediaPlayer; "
                    f"$p.Open('{path.as_uri()}'); "
                    "$p.Play(); Start-Sleep -Seconds 1; $p.Close()"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True

            if shutil.which("ffplay"):
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                return True
            players = ["aplay", "afplay", "paplay"]
            for player in players:
                if shutil.which(player):
                    subprocess.run(
                        [player, str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                    return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

        return False

    try:
        import winappaudiorouter as war  # type: ignore

        target_device = None
        try:
            if porosity_value < 0.3:
                target_device = None  # default endpoint
            elif porosity_value < 0.8:
                input_devs = war.list_output_devices()
                if len(input_devs) > 1:
                    target_device = input_devs[1]
            else:
                input_devs = war.list_output_devices()
                if len(input_devs) > 1:
                    target_device = input_devs[-1]

            if target_device is not None:
                device_id = getattr(target_device, "id", None) or getattr(target_device, "device_id", None) or str(target_device)
                war.set_app_output_device(process_name="python.exe", device=device_id)
        except Exception:
            # Routing best-effort only; fall back to default playback
            pass

        return _default_playback()
    except ImportError:
        return _default_playback()


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


def _dominant_axis(vector: Dict[str, float]) -> str | None:
    best = None
    best_val = 0.0
    for k, v in (vector or {}).items():
        try:
            fv = float(v or 0.0)
        except Exception:
            continue
        if best is None or fv > best_val:
            best_val = fv
            best = k
    return best


def _select_speaker(vector: Dict[str, float]) -> str:
    return _SPEAKER_MAP.get(_dominant_axis(vector), "luna")


# ---------------------------------------------------------------------------
# King Wen action router — chat vs do split
# ---------------------------------------------------------------------------
def _kingwen_router(consult: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    """Route consult result into chat or do path.

    Returns:
      mode: "chat" | "do"
      text: what to speak/print
      scenes: optional scene-shaped metadata list for expressive rendering
      tool_hint: optional downstream tool/action hint
      rule: short explanation for audit/training
      vision_block: optional vision facts when consult includes parsed image data
    """
    tongue = consult.get("emotional_tongue") or {}
    raw = tongue.get("training_weight_vectors") or {}
    vector = {
        "voiceWeight": raw.get("voiceWeight", 0.0),
        "coherence": raw.get("coherence", 0.0),
        "chaos": raw.get("chaos", 0.0),
        "whimsy": raw.get("whimsy", 0.0),
        "darkTone": raw.get("darkTone", 0.0),
    }
    dominant = _dominant_axis(vector)
    porosity = tongue.get("porosity") if isinstance(tongue, dict) else None
    porosity_value = 0.35 if porosity is None else float(porosity)
    trajectory = (consult.get("trajectory") or "still").lower()
    agree = consult.get("phase_temporal") or consult.get("agree_temporal") or "present"

    vision_block = None
    if consult.get("_vision"):
        _v = consult["_vision"]
        sf = _v.get("scene_facts") or {}
        vision_block = {
            "width": _v.get("width"),
            "height": _v.get("height"),
            "part_count": sf.get("part_count"),
            "visual_prompts": sf.get("visual_prompts") or [],
            "palette": _v.get("palette") or [],
            "labeled_regions": _v.get("labeled_regions") or [],
        }

    # Default to chat
    mode = "chat"
    tool_hint = None
    rule = "default_chat"

    # Do-path signals
    if dominant == "voiceWeight" and vector["coherence"] >= 0.65 and vector["chaos"] <= 0.25:
        mode = "do"
        tool_hint = "assert"
        rule = "voice_directive_assert"
    elif dominant == "coherence" and porosity_value >= 0.55 and trajectory in {"still", "converging"}:
        mode = "do"
        tool_hint = "hold_and_execute"
        rule = "coherent_focus_execute"
    elif porosity_value <= 0.2:
        mode = "do"
        tool_hint = "decisive"
        rule = "low_porosity_decisive"
    elif trajectory == "diverging" and vector["chaos"] > 0.35:
        mode = "chat"
        tool_hint = "wait"
        rule = "diverging_chaos_chat"
    elif dominant == "whimsy" and vector["whimsy"] >= 0.6:
        mode = "chat"
        tool_hint = "begin"
        rule = "whimsy_narrative"

    # Vision-aware adjustment: if image shows actionable structure,
    # prefer do mode when coherence is already high.
    if vision_block and vision_block.get("part_count") and int(vision_block["part_count"]) > 0:
        if mode == "chat" and vector["coherence"] >= 0.5:
            mode = "do"
            tool_hint = tool_hint or "inspect"
            rule = "vision_coherent_execute"

    # Text selection keeps minimal map on do path, richer text on chat path
    if mode == "do":
        text = {
            "voiceWeight": "Assert.",
            "darkTone": "Yield.",
            "chaos": "Wait.",
            "coherence": "Hold.",
            "whimsy": "Begin.",
        }.get(dominant, "Do.")
    else:
        text = consult.get("unified_weave") or consult.get("trainingNotes") or user_text

    scenes = [
        {
            "index": 1,
            "description": text,
            "visualPrompt": consult.get("unified_weave") or user_text,
            "styleInfluence": f"King Wen router mode={mode}, dominant={dominant}, porosity={porosity_value:.3f}, trajectory={trajectory}",
            "hexagram_color": consult.get("hexagram_color"),
            "prosody": {
                "chaos": vector["chaos"],
                "whimsy": vector["whimsy"],
                "darkTone": vector["darkTone"],
                "coherence": vector["coherence"],
            },
            "voice_status": "ready" if mode == "chat" else "action",
        }
    ]

    return {
        "mode": mode,
        "text": text,
        "scenes": scenes,
        "tool_hint": tool_hint,
        "rule": rule,
        "dominant": dominant,
        "porosity": porosity_value,
        "trajectory": trajectory,
        "agree_temporal": agree,
        "vision_block": vision_block,
    }


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
    vision_data: Optional[Dict[str, Any]] = None,
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
            vision_data=vision_data,
        )
    except Exception as exc:
        return _error_result(f"Worker consult failed: {exc}", user_text, text_source)

    if "error" in consult:
        return _error_result(
            consult["error"], user_text, text_source, consult.get("hexagram_id")
        )

    # ------------------------------------------------------------------
    # Upgrade: use local 512-state collapse consensus as the primary
    # deliberative source. The worker remains the audio/TTS endpoint.
    # ------------------------------------------------------------------
    local_consult: Dict[str, Any] = {}
    try:
        from openjarvis.emotion.kingwen_engine_adapter import consult as local_consult  # noqa: E402

        local_consult = local_consult(
            user_text,
            session_id=session_id,
            emotional_input=emotional_input,
        )
    except Exception:
        local_consult = {}

    if local_consult:
        consult.setdefault("_local_consensus", local_consult)
        consult["hexagram_id"] = local_consult.get("hexagram_id") or consult.get("hexagram_id") or 0
        consult["hexagram_name"] = local_consult.get("hexagram_name") or consult.get("hexagram_name") or ""
        consult["phase_temporal"] = local_consult.get("phase_temporal") or consult.get("phase_temporal") or "present"
        consult["agree_temporal"] = local_consult.get("agree_temporal") or consult.get("agree_temporal") or consult.get("phase_temporal") or "present"
        consult["trajectory"] = local_consult.get("trajectory") or consult.get("trajectory") or "still"
        consult["action"] = local_consult.get("action") or consult.get("action") or ""
        consult["category"] = local_consult.get("category") or consult.get("category") or ""
        consult["reaction_frame"] = local_consult.get("reaction_frame") or consult.get("reaction_frame") or ""
        consult["emotional_deltas"] = local_consult.get("emotional_deltas") or consult.get("emotional_deltas") or {}
        consult["unified_weave"] = local_consult.get("unified_weave") or consult.get("unified_weave") or ""
        consult["trainingNotes"] = local_consult.get("trainingNotes") or consult.get("trainingNotes") or ""
        consult["consensus_hexagram_id"] = local_consult.get("consensus_hexagram_id")
        consult["consensus_hexagram_name"] = local_consult.get("consensus_hexagram_name")
        consult["consensus_temporal"] = local_consult.get("consensus_temporal")
        consult["consensus_yao"] = local_consult.get("consensus_yao")
        consult["consensus_porosity_mean"] = local_consult.get("consensus_porosity_mean")
        consult["consensus_porosity_mode"] = local_consult.get("consensus_porosity_mode")
        consult["consensus_vector"] = local_consult.get("consensus_vector")
        consult["consensus_intent"] = local_consult.get("consensus_intent")
        consult["consensus_explanation"] = local_consult.get("consensus_explanation")
        consult["temporal_distribution"] = local_consult.get("temporal_distribution")
        consult["emotional_input"] = local_consult.get("emotional_input", emotional_input)
        consult["hexagram_color"] = local_consult.get("hexagram_color") or consult.get("hexagram_color") or _hexagram_color(
            int(consult.get("hexagram_id") or 0),
            chinese_text=local_consult.get("hexagram_chinese"),
            unicode_symbol_text=local_consult.get("hexagram_symbol"),
        )
        tongue = consult.get("emotional_tongue") or {}
        if isinstance(tongue, dict):
            tongue["porosity"] = local_consult.get("consensus_porosity_mean")
            tongue["training_weight_vectors"] = local_consult.get("consensus_vector") or tongue.get("training_weight_vectors") or {}
        else:
            consult["emotional_tongue"] = {
                "porosity": local_consult.get("consensus_porosity_mean"),
                "training_weight_vectors": local_consult.get("consensus_vector") or {},
            }

    vector = _extract_vector(consult)
    hexagram_id = int(consult.get("hexagram_id") or 0)
    if not hexagram_id:
        try:
            hexagram_id = int(
                consult.get("consensus_hexagram_id")
                or consult.get("_local_consensus", {}).get("consensus_hexagram_id")
                or 0
            )
        except (TypeError, ValueError):
            hexagram_id = 0

    # ------------------------------------------------------------------
    # VHDL-mined voice router: priority routing + constraint masking +
    # deliberation window + CRIT countdown. King Wen remains the voice;
    # this layer decides whether the voice should be heard, held, or
    # forced to a safe default.
    # ------------------------------------------------------------------
    _voice_router = _ensure_voice_router()
    _router_eval = _voice_router.evaluate_advice(
        consult,
        user_direct_input=bool(user_text.strip()),
        safety_ok=True,
        sensor_variance=abs(float(consult.get("consensus_vector", {}).get("voiceWeight", 0.5) or 0.5) - 0.5),
    )
    consult.setdefault("_voice_router", _router_eval)
    consult["voice_router_advice_hexagram"] = _router_eval.get("advice_hexagram")
    consult["voice_router_mode"] = _router_eval.get("voice_mode")
    consult["voice_router_priority"] = _router_eval.get("priority")
    consult["voice_router_hold"] = _router_eval.get("hold_in_state")
    consult["voice_router_deliberation"] = _router_eval.get("deliberation")
    consult["voice_router_fault_vector"] = int(_router_eval.get("fault_vector", 0) or 0)
    consult["voice_router_crit_countdown"] = _router_eval.get("crit_countdown")
    consult["voice_router_reasoning"] = _router_eval.get("reasoning")

    # ------------------------------------------------------------------
    # Vision bridge: carry optional image-analysis facts through the same
    # King Wen route without changing chat/do behavior.
    # ------------------------------------------------------------------
    if vision_data is not None:
        consult.setdefault("_vision", {})
        consult["_vision"].update(
            {
                "width": vision_data.get("width"),
                "height": vision_data.get("height"),
                "palette": vision_data.get("palette"),
                "labeled_regions": vision_data.get("labeled_regions"),
                "scene_facts": vision_data.get("scene_facts"),
            }
        )
        consult["source_ingestion"] = consult.get("source_ingestion") or "vision://ingest"
        consult.setdefault("_sources", []).append("vision")

    route = _kingwen_router(consult, user_text)
    text_spoken = route["text"]
    speaker = _select_speaker(vector)
    dominant = _dominant_axis(vector)
    porosity = (
        consult.get("emotional_tongue", {}).get("porosity")
        if isinstance(consult.get("emotional_tongue"), dict)
        else None
    )
    porosity_value = 0.35 if porosity is None else float(porosity)
    trajectory = (consult.get("trajectory") or "still").lower()
    agree_temporal = consult.get("phase_temporal") or consult.get("agree_temporal") or "present"
    hexagram_id = consult.get("hexagram_id") or consult.get("consensus_hexagram_id") or 0

    audio_bytes = None
    backend = "none"
    dsp_meta: Dict[str, Any] = {}
    headers: Dict[str, str] = {}

    if route["mode"] == "chat":
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
                    "mode": route["mode"],
                    "tool_hint": route["tool_hint"],
                    "rule": route["rule"],
                    "scenes": route["scenes"],
                    "dsp_meta": {},
                }
    else:
        # do path: no artifact, action payload only
        return {
            "audio_path": "",
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
            "mode": route["mode"],
            "tool_hint": route["tool_hint"],
            "rule": route["rule"],
            "scenes": route["scenes"],
            "dsp_meta": {},
        }

    if audio_bytes:
        try:
            from openjarvis.cli.audio_dsp import modulate_with_headers

            if _is_cloud_endpoint(_KINGWEN_TTS_URL):
                compliance = headers.get("X-Kingwen-Compliance", "compliant")
                if compliance == "reject":
                    dsp_meta = {
                        "error": "compliance=reject",
                        "violations": (headers.get("X-Kingwen-Violations") or "").split(",") if headers.get("X-Kingwen-Violations") else [],
                    }
                    backend = f"{backend}+compliance-reject"
                else:
                    audio_bytes, dsp_meta = modulate_with_headers(audio_bytes, headers)
                    backend = f"{backend}+dsp"
            else:
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
        "played": False,
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
        "mode": route.get("mode"),
        "tool_hint": route.get("tool_hint"),
        "rule": route.get("rule"),
        "scenes": route.get("scenes"),
        "director_payload": {
            "source": "kingwen_router",
            "dominant": dominant,
            "consensus_hexagram_id": consult.get("consensus_hexagram_id"),
            "consensus_yao": consult.get("consensus_yao"),
            "consensus_temporal": consult.get("consensus_temporal"),
            "emotional_input": consult.get("emotional_input"),
            "porosity": porosity_value,
            "trajectory": trajectory,
            "agree_temporal": agree_temporal,
            "voice_vector": vector,
            "all_hexagrams_count": consult.get("all_hexagrams_count"),
            "all_resolved_count": consult.get("all_resolved_count"),
            "expanded": consult.get("expanded") or [],
            "resolved": consult.get("resolved") or [],
            "scene": {
                "description": text_spoken,
                "visualPrompt": consult.get("unified_weave") or consult.get("trainingNotes") or user_text,
                "styleInfluence": (route.get("scenes") or [{}])[0].get("styleInfluence") if route.get("scenes") else "",
                "prosody": {
                    "chaos": vector.get("chaos", 0.0),
                    "whimsy": vector.get("whimsy", 0.0),
                    "darkTone": vector.get("darkTone", 0.0),
                    "coherence": vector.get("coherence", 0.0),
                    "voiceWeight": vector.get("voiceWeight", 0.0),
                },
                "voicePath": final_path,
                "voiceStatus": "ready" if compliance == "compliant" else "reject",
                "imagePath": consult.get("source_ingestion") if str(consult.get("source_ingestion", "")).startswith("vision://") else None,
            },
            "playback_instructions": _playback_instructions_for(porosity_value),
        },
    }
    try:
        result["played"] = _play_audio_path(final_path, porosity=porosity)
    except Exception:
        result["played"] = False
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
    mode: str = "chat",
    tool_hint: Optional[str] = None,
    rule: str = "error",
    scenes: Optional[list[dict[str, Any]]] = None,
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
        "mode": mode,
        "tool_hint": tool_hint,
        "rule": rule,
        "scenes": scenes or [],
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


def get_emotional_input(default: int = 50, minimum: int = 0, maximum: int = 100) -> int:
    try:
        raw = input("King Wen emotional_input (0-100) [50]: ").strip()
    except EOFError:
        return default
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


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


# --------------------------------------------------------------------------- #
# VHDL-mined voice router singleton                                           #
# --------------------------------------------------------------------------- #
_voice_router_instance: object | None = None


def _ensure_voice_router() -> object:
    global _voice_router_instance
    if _voice_router_instance is None:
        try:
            from kingwen_voice_router import KingWenVoiceRouter

            _voice_router_instance = KingWenVoiceRouter()
        except Exception:
            _voice_router_instance = None
    return _voice_router_instance
