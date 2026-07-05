---
name: kingwen-emotion-voice
description: "Deterministic King Wen emotional-state provider + voice-preset resolver for hallucination-resistant prompts and TTS backend selection."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [emotion, voice, tts, kingwen, i-ching, deterministic]
    source: hermes
---

# King Wen Emotion + Voice Skill

Deterministic 64-hex emotional-state provider from the King Wen immutable tables.
Use this for prompt emotion routing and voice-preset selection; do not replace it
with ad-hoc persona prose or mocked voice selection.

## What it provides

- `consult(...)` → deterministic hexagram + emotional deltas + reflections
- `format_prompt_section(...)` → `## Emotional State` block
- `voice_preset(tts_backend, voice_weight)` → executable `voice_id` + `speed`
- `format_voice_section(...)` → `## Voice Preset` block

## Data requirements

The following files must exist on disk and resolve relative to this skill
or the runtime `src/openjarvis/data/` shim:

- `hexagram-registry.json`
- `emotional-weights.json`
- `temporal-reflections.json`

## Usage

Call the provider, then append both sections to the system prompt:

```json
{
  "emotion_section": "<## Emotional State ...>",
  "voice_section": "<## Voice Preset ...>",
  "voice_preset": {
    "backend": "cartesia|openai_tts|kokoro",
    "voice_id": "...",
    "speed": 1.0
  }
}
```

Pass `voice_preset` as the actual TTS args; do not ignore it.

## Constraints

- No mock/stub/placeholder voice selection.
- Use `voiceWeight` from King Wen data as the reconciliation source.
- Voice decisions are configurable but deterministic.
