"""
cartesia_adapter.py

Prosthetic voice adapter: translates King Wen emotional truth into
Cartesia's discrete API constraints.

Dependency direction:
    KingWenEmotionProvider -> oracle payload -> THIS FILE -> Cartesia API

The oracle never imports Cartesia. This adapter imports truth only.
The adapter is isolated, audited, versioned, and swappable.

Hard-coded mapping rationale: Cartesia's /tts/bytes supports only discrete
emotion tags + numeric speed via generation_config. Continuous latent control
is not exposed. This adapter is the minimum-necessary conversion tolerated
because the system must speak through a throat that does not understand
continuous emotion.

Jiminy Cricket effect: unlimited refill from immutable truth, acting upon it.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ── Minimal pure types ──────────────────────────────────────────────────

class TemporalPhase(str, Enum):
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"

class Trajectory(str, Enum):
    STILL = "still"
    CONVERGING = "converging"
    DIVERGING = "diverging"
    CYCLING = "cycling"

class VECKey(str, Enum):
    CHAOS = "chaos"
    WHIMSY = "whimsy"
    DARK_TONE = "darkTone"
    COHERENCE = "coherence"
    VOICE_WEIGHT = "voiceWeight"

# 5-axis continuous vector sourced from King Wen tables
EmotionalVector = dict[VECKey, float]

# ── Audit record ────────────────────────────────────────────────────────

@dataclass
class AdapterAudit:
    timestamp: float
    input_vector: EmotionalVector
    input_trajectory: Trajectory
    input_agree_temporal: TemporalPhase
    output_emotion: str
    output_level: str
    output_speed: float
    mapping_version: str
    oracle_hexagram_id: Optional[int] = None
    truth_source: str = ""  # path to actual weights file used
    training_notes: str = ""  # from King Wen table

# ── King Wen truth table loader ─────────────────────────────────────────
#
# Loads the actual King Wen JSON tables. This is the only place where
# the adapter touches truth. The JSON structure is:
# {
#   "<hexagram_id>": {
#     "chaos": float, "whimsy": float, "darkTone": float,
#     "coherence": float, "voiceWeight": float,
#     "trainingNotes": str
#   }, ...
# }
#
# If table is missing or corrupted, adapter falls back to empty vector.

class KingWenTruth:
    """Loads and indexes the King Wen immutable emotional weights."""

    _instance: Optional["KingWenTruth"] = None

    def __init__(self, weights_path: str | Path) -> None:
        self._weights: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._path = Path(weights_path)
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._weights = raw
                self._loaded = True
        except (json.JSONDecodeError, OSError):
            pass

    @classmethod
    def get(cls, weights_path: str | Path) -> "KingWenTruth":
        if cls._instance is None or str(cls._instance._path) != str(Path(weights_path)):
            cls._instance = cls(weights_path)
        return cls._instance

    def vector_for_hexagram(self, hexagram_id: int) -> EmotionalVector:
        if not self._loaded:
            return {k: 0.0 for k in VECKey}
        entry = self._weights.get(str(hexagram_id), {})
        if not entry:
            return {k: 0.0 for k in VECKey}
        return {
            VECKey.CHAOS: float(entry.get("chaos", 0.0)),
            VECKey.WHIMSY: float(entry.get("whimsy", 0.0)),
            VECKey.DARK_TONE: float(entry.get("darkTone", 0.0)),
            VECKey.COHERENCE: float(entry.get("coherence", 0.0)),
            VECKey.VOICE_WEIGHT: float(entry.get("voiceWeight", 0.0)),
        }

    def training_notes(self, hexagram_id: int) -> str:
        if not self._loaded:
            return ""
        entry = self._weights.get(str(hexagram_id), {})
        return entry.get("trainingNotes", "")

# ── Hard-coded mapping configuration ────────────────────────────────────
#
# This table is the ONLY place where the oracle's continuous topology
# touches Cartesia's discrete constraints. It is versioned, audited,
# and isolated. The oracle never sees these labels. The adapter never
# feeds back into emotional topology.
#
# If Cartesia adds continuous controls, replace this adapter class.
# Do NOT remove or rename fields — bump mapping_version instead.

CARTESIA_EMOTION_MAP: dict[VECKey, dict[str, Any]] = {
    # High chaos -> expressive surprise
    VECKey.CHAOS:       {"tag": "surprise",  "threshold": 0.5},
    # High whimsy -> exploratory curiosity
    VECKey.WHIMSY:      {"tag": "curiosity", "threshold": 0.5},
    # High darkTone -> somber sadness
    VECKey.DARK_TONE:   {"tag": "sadness",   "threshold": 0.5},
    # High coherence -> stable positivity
    VECKey.COHERENCE:   {"tag": "positivity", "threshold": 0.5},
    # High voiceWeight -> authoritative anger (volume/weight)
    VECKey.VOICE_WEIGHT:{"tag": "anger",     "threshold": 0.5},
}

LEVEL_THRESHOLDS = [
    (0.2,  "lowest"),
    (0.4,  "low"),
    (0.7,  "moderate"),
    (0.9,  "high"),
    (1.001, "highest"),  # anything > 0.9
]

TRAJECTORY_SPEED_DELTA: dict[Trajectory, float] = {
    Trajectory.STILL:      0.0,
    Trajectory.CONVERGING: 0.08,
    Trajectory.DIVERGING: -0.12,
    Trajectory.CYCLING:    0.0,  # oscillates at call time
}

# ── Helper functions ────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def _select_dominant(vector: EmotionalVector) -> VECKey:
    """Select dominant axis above threshold with highest value. Fallback: coherence."""
    dominant: VECKey = VECKey.COHERENCE
    max_val = 0.0
    for axis, meta in CARTESIA_EMOTION_MAP.items():
        val = float(vector.get(axis, 0.0))
        if val > meta["threshold"] and val > max_val:
            max_val = val
            dominant = axis
    return dominant

def _map_level(value: float) -> str:
    """Continuous magnitude -> discrete Cartesia level string."""
    for threshold, label in LEVEL_THRESHOLDS:
        if value <= threshold:
            return label
    return "highest"

def _speed_to_label(speed: float) -> str:
    """Numeric speed [-1..1] -> Cartesia speed label."""
    if speed <= -0.6:
        return "slowest"
    if speed <= -0.2:
        return "slow"
    if speed <= 0.2:
        return "normal"
    if speed <= 0.6:
        return "fast"
    return "fastest"

# ── Adapter class ───────────────────────────────────────────────────────

class CartesiaAdapter:
    """
    Prosthetic voice adapter.

    Reads King Wen immutable truth by path. Translates continuous emotional
    topology into Cartesia's discrete API constraints.

    Does NOT depend on POG2. Does NOT depend on OpenJarvis core.
    Only depends on: King Wen JSON tables, emotional vector, trajectory,
    agree_temporal, base voice ID.
    """

    mapping_version: str = "cartesia-adapter-v1"
    _api_base: str = "https://api.cartesia.ai"
    _cartesia_version: str = "2026-03-01"
    _model: str = "sonic-3.5"

    def __init__(
        self,
        api_key: str,
        kingwen_weights_path: str | Path | None = None,
    ) -> None:
        self._api_key = api_key
        self._audit: AdapterAudit | None = None
        self._http_client = None  # httpx client injected at runtime

        # Load actual King Wen truth tables by path.
        # If not provided, tries env KING_WEN_IMMUTABLE_TABLES or
        # defaults to the canonical folder beside this file's repo.
        if kingwen_weights_path is None:
            env_path = os.environ.get("KING_WEN_IMMUTABLE_TABLES")
            if env_path:
                kingwen_weights_path = Path(env_path) / "data" / "emotional-weights.json"
            else:
                kingwen_weights_path = (
                    Path(__file__).resolve().parent.parent.parent.parent
                    / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
                    / "data"
                    / "emotional-weights.json"
                )
        self._truth = KingWenTruth.get(kingwen_weights_path)

    # ── Truth access ───────────────────────────────────────────────────

    def lookup_vector_from_truth(self, hexagram_id: int) -> EmotionalVector:
        """Pull the actual 5-axis vector from King Wen tables."""
        return self._truth.vector_for_hexagram(hexagram_id)

    def lookup_training_notes(self, hexagram_id: int) -> str:
        """Pull the immutable training notes from King Wen tables."""
        return self._truth.training_notes(hexagram_id)

    # ── Audit surface ──────────────────────────────────────────────────

    def last_audit(self) -> AdapterAudit | None:
        """Return the audit record from the most recent call."""
        return self._audit

    def set_http_client(self, client: Any) -> None:
        """Allow injection of httpx client (testability)."""
        self._http_client = client

    # ── Public API ────────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        vector: EmotionalVector,
        trajectory: Trajectory = Trajectory.STILL,
        agree_temporal: TemporalPhase = TemporalPhase.PRESENT,
        base_voice_id: str = "c8f7835e-28a3-4f0c-80d7-c1302ac62aae",
        oracle_hexagram_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Translate pure oracle emotional vector -> Cartesia API call.

        If oracle_hexagram_id is provided AND the King Wen truth table
        is loaded, the vector is overridden with the actual table entry
        before mapping. This guarantees the adapter acts upon immutable
        truth, not generic inputs.

        Speed comes entirely from trajectory delta + emotional velocity.
        Cartesia base is 0.0 ("normal").

        Returns:
            dict with:
              - audio: bytes
              - voice_id: str
              - backend: str
              - model: str
              - audit: AdapterAudit
        """
        if not self._api_key:
            raise RuntimeError("CARTESIA_API_KEY not set on CartesiaAdapter")

        # ── Resolve vector from truth tables ─────────────────────────
        truth_source = ""
        training_notes = ""
        static_vec = {k: 0.0 for k in VECKey}
        if oracle_hexagram_id is not None:
            static_vec = self._truth.vector_for_hexagram(oracle_hexagram_id)
            training_notes = self._truth.training_notes(oracle_hexagram_id)
            truth_source = str(self._truth._path)

        # ── Prefer caller/expansion vector; fall back to static table ──
        caller_vec = EmotionalVector({
            VECKey.CHAOS:       float(vector.get(VECKey.CHAOS, 0.0)),
            VECKey.WHIMSY:      float(vector.get(VECKey.WHIMSY, 0.0)),
            VECKey.DARK_TONE:   float(vector.get(VECKey.DARK_TONE, 0.0)),
            VECKey.COHERENCE:   float(vector.get(VECKey.COHERENCE, 0.0)),
            VECKey.VOICE_WEIGHT:float(vector.get(VECKey.VOICE_WEIGHT, 0.0)),
        })
        max_caller = max(caller_vec.values())
        if max_caller > 0.0:
            vector = caller_vec
        else:
            vector = static_vec

        # ── 1. Select dominant axis above threshold ───────────────────
        dominant_axis = _select_dominant(vector)
        axis_value = float(vector.get(dominant_axis, 0.0))
        emotion_tag = CARTESIA_EMOTION_MAP[dominant_axis]["tag"]
        emotion_level = _map_level(axis_value)

        # ── 2. Compute speed from trajectory + emotional velocity only
        trajectory_delta = TRAJECTORY_SPEED_DELTA[trajectory]
        emotional_velocity = (
            float(vector.get(VECKey.CHAOS, 0.0))
            + float(vector.get(VECKey.WHIMSY, 0.0))
            - float(vector.get(VECKey.DARK_TONE, 0.0))
        ) / 3.0
        clamped_speed = _clamp(
            trajectory_delta + emotional_velocity * 0.1, -1.0, 1.0
        )

        if trajectory == Trajectory.CYCLING:
            import random
            clamped_speed = _clamp(clamped_speed + (0.05 if random.random() > 0.5 else -0.05), -1.0, 1.0)

        # ── 3. Emit audit BEFORE the call ──────────────────────────────
        audit = AdapterAudit(
            timestamp=time.time(),
            input_vector=dict(vector),
            input_trajectory=trajectory,
            input_agree_temporal=agree_temporal,
            output_emotion=emotion_tag,
            output_level=emotion_level,
            output_speed=clamped_speed,
            mapping_version=self.mapping_version,
            oracle_hexagram_id=oracle_hexagram_id,
            truth_source=truth_source,
            training_notes=training_notes,
        )

        # ── 4. Build Cartesia request
        # generation_config.speed is authoritative numeric value.
        # __experimental_controls.speed is a hint; ensure agreement.
        controls = {
            "speed": _speed_to_label(clamped_speed),
            "emotion": [f"{emotion_tag}:{emotion_level}"],
        }

        request_body: dict[str, Any] = {
            "model_id": self._model,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": base_voice_id,
                "__experimental_controls": controls,
            },
            "output_format": {
                "container": "mp3",
                "sample_rate": 24000,
                "encoding": "mp3",
            },
            "language": "en",
            "generation_config": {
                "volume": 1,
                "speed": clamped_speed,
            },
        }

        # ── 5. Sanity-check: ensure hint and config agree
        expected_label = _speed_to_label(clamped_speed)
        if controls["speed"] != expected_label:
            raise RuntimeError(
                f"CartesiaAdapter speed mismatch: controls={controls['speed']} "
                f"vs config={expected_label} for speed={clamped_speed}"
            )

        # ── 6. Call Cartesia ───────────────────────────────────────────
        audio = self._post_cartesia(request_body)

        self._audit = audit
        return {
            "audio": audio,
            "voice_id": base_voice_id,
            "backend": "cartesia",
            "model": self._model,
            "audit": self._audit,
        }

    # ── Private ───────────────────────────────────────────────────────

    def _post_cartesia(self, body: dict[str, Any]) -> bytes:
        """POST to Cartesia /tts/bytes. Returns raw audio bytes."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for CartesiaAdapter; install it or inject a client via set_http_client()")

        client = self._http_client or httpx
        resp = client.post(
            f"{self._api_base}/tts/bytes",
            headers={
                "X-API-Key": self._api_key,
                "Cartesia-Version": self._cartesia_version,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.content

# ── Module-level convenience ────────────────────────────────────────────
#
# The Oracle engine imports this module and instantiates CartesiaAdapter
# once, passing the path to the King Wen truth tables.
#
# Usage:
#   adapter = CartesiaAdapter(api_key="...", kingwen_weights_path=".../emotional-weights.json")
#   result = adapter.synthesize(
#       text="What is the nature of this moment?",
#       vector={},  # ignored if hexagram_id provided
#       trajectory=Trajectory.CONVERGING,
#       agree_temporal=TemporalPhase.FUTURE,
#       oracle_hexagram_id=1
#   )
#   audit = adapter.last_audit()
