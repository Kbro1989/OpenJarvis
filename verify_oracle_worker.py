"""Standalone King Wen worker client — new vector-header + DSP verify.

Zero dependency on openjarvis package internals.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_KINGWEN_WORKER_URL = os.environ.get(
    "KINGWEN_WORKER_URL",
    "https://kingwen-oracle.kristain33rs.workers.dev",
)
_KINGWEN_TTS_URL = os.environ.get(
    "KINGWEN_TTS_URL",
    "https://kingwen-oracle.kristain33rs.workers.dev/tts",
)
_ORACLE_VOICE_DIR = Path(os.environ.get("OPENJARVIS_HOME", "~/.openjarvis")).expanduser() / "oracle-voice"
_ORACLE_VOICE_DIR.mkdir(parents=True, exist_ok=True)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def _load_audio_dsp():
    repo_root = Path(__file__).resolve().parent
    module_path = repo_root / "src" / "openjarvis" / "cli" / "audio_dsp.py"
    spec = importlib.util.spec_from_file_location("audio_dsp", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audio_dsp"] = mod
    spec.loader.exec_module(mod)
    return mod


def consult(text: str, *, session_id: str = "standalone", emotional_input: int = 50) -> dict:
    import httpx

    payload = {
        "text": text,
        "session_id": session_id,
        "emotional_input": emotional_input,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _BROWSER_UA,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{_KINGWEN_WORKER_URL}/consult", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def synthesize_with_vector(text: str, vector: dict, porosity, trajectory: str, agree_temporal: str, session_id: str = "standalone-ci") -> tuple[bytes, dict]:
    import httpx

    payload = {
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

    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
        "User-Agent": _BROWSER_UA,
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(_KINGWEN_TTS_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content, dict(resp.headers)


def extract_vector(consult: dict) -> dict:
    tongue = consult.get("emotional_tongue") or {}
    raw = tongue.get("training_weight_vectors") or {}
    return {
        "chaos": raw.get("chaos", 0.0),
        "whimsy": raw.get("whimsy", 0.0),
        "darkTone": raw.get("darkTone", 0.0),
        "coherence": raw.get("coherence", 0.0),
        "voiceWeight": raw.get("voiceWeight", 0.0),
    }


def dominant_axis(vector: dict) -> str:
    return max(vector, key=vector.get) if vector else "coherence"


def user_text_fallback(vector: dict) -> str:
    minimal_map = {
        "voiceWeight": "Assert.",
        "darkTone": "Yield.",
        "chaos": "Wait.",
        "coherence": "Hold.",
        "whimsy": "Begin.",
    }
    return minimal_map.get(dominant_axis(vector), "Listen.")


def main() -> int:
    user_query = "Will the committee resolve with porosity preserved?"
    consult_data = consult(user_query, session_id="standalone-ci")
    vector = extract_vector(consult_data)
    hexagram_id = int(consult_data.get("hexagram_id") or 0)
    phase = consult_data.get("phase_temporal", "")
    tongue = consult_data.get("emotional_tongue") or {}
    porosity = tongue.get("porosity")
    unified = consult_data.get("unified_weave", "")
    text_spoken = unified or user_text_fallback(vector)

    print(f"[query] {user_query}")
    print(f"[consult] hex={hexagram_id} {consult_data.get('hexagram_name', '')}")
    print(f"[consult] phase={phase}  dominant={dominant_axis(vector)}")
    print(f"[consult] vector={json.dumps(vector, ensure_ascii=False)}")
    print(f"[consult] porosity={porosity}")
    print(f"[consult] text={text_spoken[:160]!r}")

    audio_bytes, resp_headers = synthesize_with_vector(
        text_spoken,
        vector=vector,
        porosity=porosity,
        trajectory="still",
        agree_temporal=phase,
        session_id="standalone-ci",
    )
    print(f"[tts] bytes={len(audio_bytes)}  backend=kingwen-worker-tts+vector-headers")

    dsp = _load_audio_dsp()
    parsed = dsp.parse_headers(resp_headers)
    print(f"[headers] vector={parsed.get('vector')}  porosity={parsed.get('porosity')}  trajectory={parsed.get('trajectory')}  temporal={parsed.get('agree_temporal')}")

    modulated, meta = dsp.modulate_with_headers(audio_bytes, resp_headers)
    print(f"[dsp] meta={json.dumps(meta, ensure_ascii=False)}")

    dst = _ORACLE_VOICE_DIR / f"hex-{hexagram_id:02d}-{phase}-dsp.mp3"
    dst.write_bytes(modulated)
    print(f"[artifact] {dst}")

    payload = {
        "audio_path": str(dst),
        "hexagram_id": hexagram_id,
        "hexagram_name": consult_data.get("hexagram_name", ""),
        "phase_temporal": phase,
        "trajectory": "still",
        "text_spoken": text_spoken,
        "backend": "kingwen-worker-tts+dsp",
        "dominant_axis": dominant_axis(vector),
        "agree_temporal": phase,
        "voice_vector": vector,
        "porosity": porosity,
        "dsp_meta": meta,
    }
    print("[result] " + json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
