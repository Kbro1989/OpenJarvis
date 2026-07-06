# Oracle Voice–Emotion Interface Contract

> **Status:** Draft  
> **Scope:** Normalize voice substrate selection and parameterization across
> Cartesia, OpenAI TTS, and Kokoro backends using POG2 `RenderEmotionParameters`
> as the upstream emotion signal.  
> **Consumer King Wen provider:** `src/openjarvis/emotion/kingwen.py`  
> **Voice backends:** `src/openjarvis/speech/cartesia_tts.py`,
> `src/openjarvis/speech/openai_tts.py`, `src/openjarvis/speech/kokoro_tts.py`  
> **Abstract base:** `src/openjarvis/speech/tts.py`

---

## 1. Purpose

POG2's rendering layer emits `RenderEmotionParameters` as a structured emotion
state before each speech frame. Voice backends currently accept only `voice_id`
and `speed` from `KingWenEmotionProvider.VOICE_PRESETS`, leaving
`pitch_variance`, `timbre_depth`, `volume_authority`, `playful_timing`, and
`prosodic_smoothness` entirely unexpressed.

This document defines:

1. The **canonical voice-emotion parameter set** (backend-agnostic).
2. The **mapping contract** from POG2 `RenderEmotionParameters` → voice params.
3. The **King Wen weight vector translation** that feeds the same contract when
   POG2 is not the upstream source.
4. **Backend adaptation notes** for each current substrate.

---

## 2. Canonical Voice–Emotion Parameter Set

| Parameter | Type | Range | Description |
|---|---|---|---|
| `voice_id` | `str` | backend-specific | Canonical voice/substrate identifier |
| `speed` | `float` | `[0.5, 2.0]` | Words-per-minute multiplier; `1.0` = neutral |
| `pitch_variance` | `float` | `[0.0, 1.0]` | Micro-pitch excursion width; `0.0` = flat, `1.0` = wide vibrato/portamento |
| `timbre_depth` | `float` | `[0.0, 1.0]` | Spectral richness / warmth; `0.0` = thin/breathy, `1.0` = full/bodied |
| `volume_authority` | `float` | `[0.0, 1.0]` | Perceived loudness and presence; `0.0` = whisper, `1.0` = commanding |
| `playful_timing` | `float` | `[0.0, 1.0]` | Rhythmic irregularity for levity; `0.0` = metronomic, `1.0` = staccato/toy-like |
| `prosodic_smoothness` | `float` | `[0.0, 1.0]` | Phrase-cohesion and glide; `0.0` = staccato/choppy, `1.0` = legato/fluid |

**Default** (no emotion signal): all float params at `0.5`, `speed` at `1.0`,
`voice_id` at the backend's warm-neutral default (Cartesia: "British Butler",
OpenAI: `alloy`, Kokoro: `af_heart`).

---

## 3. POG2 `RenderEmotionParameters` Source Shape

```python
# Emitted once per speech frame by the POG2 rendering layer.

@dataclass
class RenderEmotionParameters:
    dominantAxis: str   # e.g. "firm", "gentle", "anxious", "playful", "resolute", ...
    trajectory: float   # [-1.0, 1.0] — -1.0 descending/collapsing, 0.0 neutral, +1.0 ascending/building
    tension: float      # [0.0, 1.0] — low tension = calm, high tension = aroused/strained
    resolution: float   # [0.0, 1.0] — low = fragmented/chaotic, high = coherent/crystalline
    speed: float        # [0.5, 2.0] — direct words-per-minute multiplier reference
    auraJitter: float   # [0.0, 1.0] — temporal/rhythmic unpredictability
    auraPulse: float    # [0.0, 1.0] — regularity of prosodic contour; 0 = random, 1 = heart-beat-like
```

All POG2 floats are **pre-clamped** to their documented ranges by the upstream
renderer.

---

## 4. Interface Contract: POG2 → Voice Params

### 4.1 `voice_id` ← `dominantAxis`

**Rule:** Combine `dominantAxis` + `tension + resolution` to select a voice
substrate bucket. The axis label determines which branch is active; intensity
pushes toward premium/stronger voices.

| `dominantAxis` | Sub-bucket axis | `voice_id` bucket |
|---|---|---|
| `"gentle"` / `"calm"` / `"yield"` | low-tension warm | default-warm |
| `"firm"` / `"assert"` / `"resolute"` | high-tension strong | strong-commanding |
| `"playful"` / `"adapt"` | high-jitter bright | bright-energetic |
| `"anxious"` / `"tense"` | high-tension high-jitter | bright-commanding |
| `"ancient"` / `"deep"` | low-tension dark | dark-resonant |
| anything else | depend on `trajectory` sign | default (trajectory>0 → warmer, <0 → darker) |

**Implementation:** Map axis to a `VoiceBucket` enum, then resolve to the
three backend-specific `voice_id` values via `VOICE_PRESETS` or a new lookup
table. When only `voiceWeight` is available (King Wen path, §5), use the
existing 3-tier weight bands.

### 4.2 `speed` ← `speed` + `trajectory`

```
speed = clamp(speed * (1.0 + trajectory * 0.25), 0.5, 2.0)
```

- Positive trajectory (ascending/rising): accelerate by up to 25 %.
- Negative trajectory (descending/falling): decelerate by up to 25 %.
- `speed` field from POG2 is the authoritative baseline.

### 4.3 `pitch_variance` ← `tension` + `auraJitter`

```
pitch_variance = clamp(
    tension * 0.70 + auraJitter * 0.30,
    0.0, 1.0
)
```

- High `tension` = wider melodic range (primary driver, 70 % weight).
- `auraJitter` adds micro-prosodic unpredictability (30 % weight).
- Low values suppress vibrato; high values evoke speech under strain or playful
  pitch play.

### 4.4 `timbre_depth` ← `resolution` + `darkTone` (or `dark_tone` King Wen)

```
timbre_depth = clamp(
    resolution * 0.75 + darkTone * 0.25,
    0.0, 1.0
)
```

- High `resolution` (coherence) = rich, full-spectrum tone (75 %).
- `darkTone` tilts toward resonant/bassy when present (25 %).
- With King Wen as upstream, substitute `weights.darkTone` (float ∈ [0,1]).

**No current backend exposes timbre control directly.** This is a future-pass
parameter: record it in `TTSResult.metadata`;路由 layer may use it to select
between voice presets when `dominantAxis` is absent.

### 4.5 `volume_authority` ← `tension` + `auraPulse`

```
volume_authority = clamp(
    tension * 0.60 + auraPulse * 0.40,
    0.0, 1.0
)
```

- `tension` raises perceived loudness and forcefulness (60 %).
- `auraPulse` adds a perceptible presence/urgency cadence (40 %).
- Neither Cartesia nor OpenAI expose a volume endpoint; this maps to a
  gain-stage outside the TTS client (to be implemented in the audio pipeline).

### 4.6 `playful_timing` ← `auraJitter` + `whimsy` (or King Wen `whimsy`)

```
playful_timing = clamp(
    auraJitter * 0.60 + whimsy * 0.40,
    0.0, 1.0
)
```

- High `auraJitter` creates staccato, irregular rhythm (60 %).
- `whimsy` adds light playfulness (40 %).
- With King Wen as upstream, substitute `weights.whimsy` (float ∈ [0,1]).
- Currently **not renderable** by any backend; used for downstream
  audio-envelope shaping (inter-word gaps, elastic timing) and console annotation.

### 4.7 `prosodic_smoothness` ← `trajectory` + `resolution` + `auraPulse`

```
prosodic_smoothness = clamp(
    trajectory * 0.35 + resolution * 0.40 + auraPulse * 0.25,
    0.0, 1.0
)
```

- Ascending trajectory + high resolution + regular pulse = legato, flowing
  delivery.
- Descending or chaotic trajectory = choppier phrasing.
- Not directly configurable on any backend; informs
  **post-synthesis audio envelope** (cross-fade between phrases, padding
  strategy) and `canonical_tick_ms` passed to `format_oracle_console`.

---

## 5. King Wen Path (No POG2 Upstream)

When the emotion source is `KingWenEmotionProvider.consult()` (or
`getEmotionalState()`), derive the 7 voice params from King Wen weight vectors
plus porosity/direction.

### 5.1 Available King Wen Vectors

| King Wen output | Voice-param surrogate | Notes |
|---|---|---|
| `voiceWeight` ∈ [0,1] | → `voice_id` bucket (3-tier), `speed` | Already active in `VOICE_PRESETS` |
| `coherence` ∈ [0,1] | → `resolution`, `prosodic_smoothness`, `timbre_depth` | Proxy for resolution |
| `chaos` ∈ [0,1] | → `auraJitter`, `pitch_variance` | High chaos = jittery/tense |
| `whimsy` ∈ [0,1] | → `playful_timing` | Direct pass-through |
| `darkTone` ∈ [0,1] | → `timbre_depth`, `volume_authority` | Tilt toward dark timbre |
| `porosity` ∈ [0,1] | → `prosodic_smoothness` discount | More porosity = less smooth; apply -0.3 factor |
| `direction` ∈ {"yield","adapt","assert","wait","neutral"} | → `trajectory` sign | assert/yield → +1/–1 polarity; adapt/wait → 0 |

### 5.2 King Wen → Voice Params Pseudocode

```python
def kingwen_to_voice_params(emotional_tongue: dict, backend: str) -> VoiceParams:
    v = emotional_tongue.get("training_weight_vectors", {})
    voice_weight = float(v.get("voiceWeight", 0.0))
    coherence    = float(v.get("coherence", 0.0))
    chaos        = float(v.get("chaos", 0.0))
    whimsy       = float(v.get("whimsy", 0.0))
    dark_tone    = float(v.get("darkTone", 0.0))
    porosity     = float(emotional_tongue.get("porosity", 0.35))

    direction_map = {"assert": 1.0, "yield": -1.0, "neutral": 0.0,
                     "adapt": 0.0, "wait": 0.0}
    trajectory = float(direction_map.get(
        emotional_tongue.get("direction", "neutral").lower(), 0.0))

    # Speed: preserve existing VOICE_PRESETS logic; override with trajectory
    preset = kingwen.voice_preset(backend, voice_weight)
    base_speed = float(preset.get("speed", 1.0))
    speed = clamp(base_speed * (1.0 + trajectory * 0.15), 0.5, 2.0)

    return VoiceParams(
        voice_id=preset["voice_id"],
        speed=round(speed, 3),
        pitch_variance = round(clamp(chaos * 0.7 + 0.15, 0.0, 1.0), 3),
        timbre_depth   = round(clamp(coherence * 0.6 + dark_tone * 0.4, 0.0, 1.0), 3),
        volume_authority = round(clamp(
            (voice_weight * 0.5 + dark_tone * 0.5), 0.0, 1.0), 3),
        playful_timing = round(clamp(whimsy * 0.8, 0.0, 1.0), 3),
        prosodic_smoothness = round(clamp(
            coherence * 0.6 - porosity * 0.3 + 0.5, 0.0, 1.0), 3),
    )
```

---

## 6. Backend Adaptation Notes

| Param | Cartesia API | OpenAI API | Kokoro (KPipeline) | Gap |
|---|---|---|---|---|
| `voice_id` | ✅ `voice.id` (UUID) | ✅ `voice` (named) | ✅ `voice` (named) | — |
| `speed` | ✅ `speed` (≥1.0 sentinel) | ✅ `speed` | ✅ `speed` | — |
| `pitch_variance` | ❌ not exposed | ❌ not exposed | ❌ not exposed | post-synthesis / future feature |
| `timbre_depth` | ❌ not exposed | ❌ not exposed | ❌ not exposed | future; use voice_id proxy now |
| `volume_authority` | ❌ not exposed | ❌ not exposed | ❌ not exposed | audio-pipeline gain stage |
| `playful_timing` | ❌ not exposed | ❌ not exposed | ❌ not exposed | audio-pipeline timing/elasticity |
| `prosodic_smoothness` | ❌ not exposed | ❌ not exposed | ❌ not exposed | post-synthesis phrase padding |

**Near-term strategy:** Render `voice_id` + `speed` directly via existing API;
carry all 7 params in `TTSResult.metadata` so the audio pipeline, console
formatter, and future POG2 frame alignment can consume them.

**Long-term:** When Cartesia / OpenAI / Kokoro add pitch/timbre/gain controls,
update their `synthesize()` signatures to accept the full `VoiceParams` payload.

---

## 7. Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  POG2 RenderLayer                                                  │
│  emits: dominantAxis, trajectory, tension, resolution,             │
│         speed, auraJitter, auraPulse                               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
             ┌─────────────▼─────────────┐
             │  VoiceEmotionMapper        │
             │  (new; see §8)             │
             │  Translates POG2 params    │
             │  → VoiceParams dataclass   │
             └─────────────┬─────────────┘
                           │
              ┌────────────┴────────────┐
              │  KingWenPath            │
              │  (no POG2 upstream)     │
              │  consult()/             │
              │  getEmotionalState()    │
              └────────────┬────────────┘
                           │  VoiceParams
              ┌────────────┴────────────────────────┐
              │  AudioPipeline / TTSRouter           │
              │  resolve(backend) → voice_id, speed   │
              │  emit rest → TTSResult.metadata       │
              ├──────────────┬──────────────┬─────────┤
              │  CartesiaTTS │  OpenAITTS  │ Kokoro │
              │  Backend     │  Backend    │ Backend│
              └──────────────┴──────────────┴─────────┘
                           │
                    TTSResult(audio, voice_id,
                              metadata={full VoiceParams})
                           │
              ┌────────────┴────────────┐
              │  Oracle Console         │
              │  format_oracle_console  │
              │  + format_voice_section │
              │  Annotates all 7 params│
              └─────────────────────────┘
```

---

## 8. Proposed Code: `VoiceParams` + `VoiceEmotionMapper`

```python
# src/openjarvis/emotion/voice_params.py

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VoiceParams:
    """Backend-agnostic voice-emotion parameter bundle."""
    voice_id: str = ""
    speed: float = 1.0
    pitch_variance: float = 0.5
    timbre_depth: float = 0.5
    volume_authority: float = 0.5
    playful_timing: float = 0.5
    prosodic_smoothness: float = 0.5
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, float | str]:
        return {
            "voice_id": self.voice_id,
            "speed": self.speed,
            "pitch_variance": self.pitch_variance,
            "timbre_depth": self.timbre_depth,
            "volume_authority": self.volume_authority,
            "playful_timing": self.playful_timing,
            "prosodic_smoothness": self.prosodic_smoothness,
        }

    @classmethod
    def from_pog2(cls, p: RenderEmotionParameters) -> VoiceParams:
        return cls(
            voice_id=p.voice_id,
            speed=cls._pog2_speed(p.speed, p.trajectory),
            pitch_variance=cls._clamp(p.tension * 0.70 + p.auraJitter * 0.30),
            timbre_depth=cls._clamp(p.resolution * 0.75),  # darkTone added by caller
            volume_authority=cls._clamp(p.tension * 0.60 + p.auraPulse * 0.40),
            playful_timing=cls._clamp(p.auraJitter * 0.60),  # whimsy added by caller
            prosodic_smoothness=cls._clamp(
                p.trajectory * 0.35 + p.resolution * 0.40 + p.auraPulse * 0.25
            ),
            metadata={"source": "pog2", "dominantAxis": p.dominantAxis},
        )

    @classmethod
    def from_kingwen(cls, tongue: dict, backend: str, kingwen: KingWenEmotionProvider) -> VoiceParams:
        # (implemented per §5.2; calls kingwen.voice_preset() for voice_id + base_speed)
        ...

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, float(v)))

    @staticmethod
    def _pog2_speed(raw: float, trajectory: float) -> float:
        return VoiceParams._clamp(raw * (1.0 + trajectory * 0.25), 0.5, 2.0)
```

---

## 9. Console Serialization: `format_voice_section`

Update `format_voice_section` (currently in `kingwen.py:531`) to serialize all
7 voice params, not just `backend`, `voice_id`, and `speed`. This keeps
`oracle_console` and `format_oracle_console` in sync with the richer params.

```python
# New format_voice_section signature
def format_voice_section(self, voice_params: VoiceParams) -> str:
    return (
        "## Voice Preset\n"
        f"- backend: {voice_params.metadata.get('backend', 'unknown')}\n"
        f"- voice_id: {voice_params.voice_id}\n"
        f"- speed: {voice_params.speed:.3f}\n"
        f"- pitch_variance: {voice_params.pitch_variance:.3f}\n"
        f"- timbre_depth: {voice_params.timbre_depth:.3f}\n"
        f"- volume_authority: {voice_params.volume_authority:.3f}\n"
        f"- playful_timing: {voice_params.playful_timing:.3f}\n"
        f"- prosodic_smoothness: {voice_params.prosodic_smoothness:.3f}\n"
    )
```

---

## 10. Mapping Summary Table

| POG2 Param | King Wen Surrogate | float formula | Voice Param | Notes |
|---|---|---|---|---|
| `dominantAxis` | — (none) | bucket lookup | `voice_id` | Axis label → voice archetype → UUID/name |
| `trajectory` | `direction` polarity | `clamp(speed*(1+t*0.25), 0.5, 2.0)` | `speed` | Also contributes 35 % to prosodic_smoothness |
| `tension` | `coherence` inverse, `chaos` | `tension*0.70 + auraJitter*0.30` | `pitch_variance` | — |
| — | `coherence` | `resolution*0.75 + darkTone*0.25` | `timbre_depth` | Not exposed by backends yet |
| `tension` | `voiceWeight`+`darkTone` | `tension*0.60 + auraPulse*0.40` | `volume_authority` | Gain stage in audio pipeline |
| `auraJitter` | `chaos` | `auraJitter*0.60 + whimsy*0.40` | `playful_timing` | Elasticity in audio pipeline |
| `resolution` | `coherence` | `t*0.35 + res*0.40 + pulse*0.25` | `prosodic_smoothness` | Phrase-padding strategy |
| — | `porosity` | `-0.3 * porosity` | smoothness discount | Smooths less when frame is porous |
| `speed` | `voiceWeight` band | `preset.speed * (1+t*0.15)` | `speed` (King Wen fallback) | Slower when direction=yield |

---

## 11. State Tick Alignment

Tie this spec to the existing Oracle Console timing:

- `canonical_tick_ms` passed to `format_oracle_console` is the natural insertion
  point for `prosodic_smoothness`-based phrase padding:
  ```
  padded_tick = canonical_tick_ms * (0.8 + 0.4 * (1.0 - prosodic_smoothness))
  ```
  - Fully smooth (`1.0`): near-canonical tick.
  - Choppy (`0.0`): ~40 % padding overhead (silences between words).

- `Reaction Frame` speech cadence strings from `_format_reaction_frame`
  (steady/hesitation/fractured) can be annotated with corresponding
  `prosodic_smoothness` and `pitch_variance` values, giving the console a
  quantifiable voice-anxiety link.

---

## 12. Open Questions & Future Work

1. **Timbre / pitch backend support** — Monolithic TTS APIs (Cartesia, OpenAI,
   Kokoro) do not currently expose pitch or gain controls. A post-synthesis DSP
   stage or a multi-layer audio pipeline is required before `pitch_variance`,
   `timbre_depth`, `volume_authority`, and `playful_timing` are audible.
2. **Voice-ID expansion** — `KingWenEmotionProvider.VOICE_PRESETS` has 3 tiers
   per backend (9 entries). A 7-parameter `VoiceParams` would benefit from a
   larger preset table keyed by `(backend, dominantAxis_variant)`, with
   `default` + `strong` + `bright` + `dark` naming.
3. **POG2 integration ordering** — This spec is written so that `VoiceParams`
   can be constructed from either POG2 `RenderEmotionParameters` or King Wen
   `emotional_tongue` without breaking either path; the two flows converge at
   `TTSResult.metadata`.

---

*Generated from source reads of cartesia_tts.py, kokoro_tts.py, openai_tts.py,
and kingwen.py (lines 1–908).*
