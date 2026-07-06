---
name: kingwen-voice-bridge
description: "EventBus bridge for King Wen voice synthesis outcomes. Publishes KINGWEN_VOICE_COMPLETE events from _oracle_speak.py to the OpenJarvis EventBus for training loop consumption."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kingwen, voice, eventbus, tts, training-loop, compliance]
    source: hermes
---

# King Wen Voice Bridge

Publish King Wen voice synthesis outcomes onto the OpenJarvis `EventBus` so the training loop can consume them without coupling voice code to trace infrastructure.

## What it provides

- `KINGWEN_VOICE_COMPLETE` event publication from `_oracle_speak.py`
- Structured payload with `hexagram_id`, `phase_temporal`, `voice_vector`, `porosity`, `backend`, `compliance`, `violations`, `dsp_meta`, `session_id`, `timestamp`
- No global trace context dependency. Trace attachment, if needed later, must be explicit.

## Event contract

```python
{
    "type": "kingwen_voice_complete",
    "hexagram_id": int,
    "phase_temporal": str,           # "past" | "present" | "future"
    "voice_vector": {
        "voiceWeight": float,
        "coherence": float,
        "chaos": float,
        "whimsy": float,
        "darkTone": float,
    },
    "porosity": float | None,
    "backend": str,                  # "kingwen-worker-tts+dsp" | "cloudflare_workers_ai+dsp" | ...
    "compliance": str,               # "compliant" | "reject"
    "violations": list[str],         # empty list if compliant
    "dsp_meta": dict,                # pitch/rate/EQ/RMS/temporal mapping from audio_dsp
    "session_id": str,
    "timestamp": float,
}
```

## Usage

Subscribe on the OpenJarvis `EventBus`:

```python
from openjarvis.core.events import EventBus, EventType, get_event_bus

bus = get_event_bus()
bus.subscribe(EventType.KINGWEN_VOICE_COMPLETE, lambda event: print(event.data))
```

## Source files

- `src/openjarvis/core/events.py` — adds `KINGWEN_VOICE_COMPLETE = "kingwen_voice_complete"`
- `src/openjarvis/core/types.py` — adds `KINGWEN_VOICE = "kingwen_voice"` to `StepType`
- `src/openjarvis/cli/_oracle_speak.py` — `_publish_kingwen_voice_event(result)` after audio write

## Constraints

- Training bridge must never break voice synthesis. Event publication is wrapped in `try/except`.
- No global trace context. If trace attachment is needed, it must be explicit.
- Compliance/violations are derived from worker `/tts` response headers (`X-Kingwen-Compliance`, `X-Kingwen-Violations`). Do not recompute client-side.
