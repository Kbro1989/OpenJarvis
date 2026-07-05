# King Wen Codebasemap
Source of truth: `C:\Users\krist\Desktop\KING-WEN-I-CHING-I-MMUTABLE-TABLES`
Workspace tables expected by this codebase:
- `data/hexagram-registry.json`
- `data/emotional-weights.json`
- `data/temporal-reflections.json`

Rule: paths resolve through `get_kingwen_workspace_dir()` or `KING_WEN_IMMUTABLE_TABLES`. No hardcoded absolute paths in King Wen integration code.

---

## 1. Files, functions, and exact King Wen intent

### `src/openjarvis/core/paths.py`
- Function: `get_kingwen_workspace_dir()`
- Intent: single King Wen path-resolution entrypoint
- Behavior: `KING_WEN_IMMUTABLE_TABLES` env override; else `Path.cwd()`
- King Wen call surface: used by config, digest loader, and emotion provider

### `src/openjarvis/core/config.py`
- Class: `KingWenEmotionConfig`
- Fields:
  - `registry_path`
  - `weights_path`
  - `reflections_path`
  - `enabled`
- Intent: config schema for wiring King Wen into digest/agent paths
- Behavior: builds paths from `get_kingwen_workspace_dir()`

### `src/openjarvis/emotion/kingwen.py`
- Class: `KingWenEmotionProvider`
- Constructor intent: load live King Wen workspace tables deterministically
- Key functions:
  - `_load(registry_path, weights_path, reflections_path)` — reads live JSON tables
  - `_read_json(path)` — raises if King Wen data missing
  - `consult(text, session_id, emotional_input)` — deterministic 64-hex selection payload
  - `voice_preset(tts_backend, voice_weight)` — returns voice id/speed from emotional weights
  - `format_prompt_section(payload)` — prompt-side emotional-state Markdown section
  - `format_voice_section(preset)` — prompt-side voice preset block
  - `format_oracle_console(payload, response_text, canonical_tick_ms)` — live Oracle Console block
  - `_select(text, session_id)` — deterministic hexagram id derivation
- King Wen intent: this file is the live bridge to the workspace tables; no fake/stub allowed

### `src/openjarvis/agents/_stubs.py`
- Class: `BaseAgent`
- Constructor intent: preserve King Wen runtime state on agent instances
- King Wen fields:
  - `_kingwen_session_id`
  - `_emotion_provider`
  - `_capture_writer`
- Key functions:
  - `_build_capture_emotion()` — calls `emotion_provider.consult(...)` and `voice_preset(...)`
  - `_build_kingwen_response_block()` — appends live Oracle Console block to responses
  - `_generate(...)` capture write — logs King Wen metadata alongside inference telemetry
- King Wen intent: ensures every agent turn can attach live King Wen state and training notes without clobbering subclass state

### `src/openjarvis/prompt/builder.py`
- Component: `SystemPromptBuilder`
- King Wen intent: inject live emotional and voice sections into the system prompt when `_emotion_provider` is wired
- Exact functions:
  - builds `PromptSection(name="emotional_state", source="kingwen-emotion", ...)`
  - builds `PromptSection(name="voice_preset", source="kingwen-voice", ...)`
  - on provider error, builds `PromptSection(name="emotional_state", source="kingwen-emotion-error", ...)`
  - sets `_kingwen_voice_preset` from live provider output
- King Wen contract: uses `consult()` then `voice_preset()`; section payload must come from live tables

### `src/openjarvis/agents/morning_digest.py`
- Class: `MorningDigestAgent`
- King Wen intent: load King Wen emotion provider from digest config and apply it to voice/tone for the daily briefing
- Exact functions:
  - `_load_kingwen_emotion_provider(config)` — loads provider from `DigestConfig` registry/weights/reflections paths
  - `_resolve_voice_preset(text)` — calls `provider.consult(text="morning-digest")` and `provider.voice_preset(...)`
  - stores resulting voice id/speed on the agent instance
  - stores last emotion payload in `_last_emotion_payload`
- King Wen contract: provider must expose `consult()` returning `hexagram_id`, `emotional_deltas`, `reflections`; voice preset must return `backend`, `voice_id`, `speed`

### `src/openjarvis/sdk.py`
- Functionality: SDK/runtime agent construction path
- King Wen intent: when `digest.emotion_enabled` is true, inject `_load_kingwen_emotion_provider()` into `morning_digest` agent kwargs
- Provider wiring: sets `emotion_provider` so digest agent can call King Wen live

### `src/openjarvis/system/orchestrator.py`
- Functionality: orchestrator agent construction path
- King Wen intent: same as SDK path — load King Wen emotion provider for `morning_digest` when enabled
- Provider wiring: `emotion_provider` passed to digest agent kwargs

### `src/openjarvis/cli/ask.py`
- Functionality: `jarvis ask` response path
- King Wen intent: append live Oracle Console side block to plain `ask` responses
- Exact behavior:
  - after `agent.run(query_text, context=ctx)`, appends `agent._build_kingwen_response_block()`
- King Wen contract: side block must be produced by live `consult()` + `format_oracle_console()`

### `src/openjarvis/cli/chat_cmd.py`
- Functionality: `jarvis chat` REPL response path
- King Wen intent: append live Oracle Console side block to each chat reply
- Exact behavior:
  - after agent/content generation, appends `agent._build_kingwen_response_block()`

### `src/openjarvis/agents/channel_agent.py`
- Functionality: channel messaging response path
- King Wen intent: append live Oracle Console side block to channel replies
- Exact behavior:
  - calls `self._agent._build_kingwen_response_block()` and appends to reply text

### `src/openjarvis/cli/ollama_launch_cmd.py`
- Functionality: Ollama wrapper/launch CLI
- King Wen intent: task-aware model selection owns a `kingwen` task fit
- Exact behavior:
  - `_OLLAMA_TASK_FIT["kingwen"]` route includes King Wen-oriented candidate models
  - task annotation in integration metadata: `"kingwen": "... King Wen oracle persona"`
- King Wen contract: `run-query` accepts `--task kingwen`; model selection should favor context-capable local models

### `src/openjarvis/engine/ollama_model_usage.py`
- Class: `OllamaModelUsageStore`
- King Wen intent: latency-aware model selection supports runtime model sorting usable by King Wen routing
- Exact functions:
  - `record(usage)` — writes model usage with latency, tokens, success/failure
  - `sorted_by_latency(models)` — returns candidates ranked by observed latency
- King Wen contract: stores runtime evidence; does not hardcode model priorities

---

## 2. Provider contract summary

Expected `KingWenEmotionProvider` interface:
- `consult(text, session_id)` → dict with at least:
  - `hexagram_id`
  - `hexagram_name`
  - `emotional_deltas.voiceWeight`
  - `reflections.past/present/future`
- `voice_preset(tts_backend, voice_weight)` → dict with:
  - `backend`
  - `voice_id`
  - `speed`
- `format_prompt_section(payload)` → Markdown prompt section
- `format_voice_section(preset)` → voice block text
- `format_oracle_console(payload, response_text, canonical_tick_ms)` → live response block

---

## 3. Response injection points

Plain-user-facing response paths that must include live King Wen data:
- `cli/ask.py` → `_run_agent()` return value
- `cli/chat_cmd.py` → REPL rendered Markdown content
- `agents/channel_agent.py` → channel `send()` reply text

---

## 4. Hard rules

- No hardcoded King Wen absolute paths.
- Only `KING_WEN_IMMUTABLE_TABLES` env override is allowed.
- All usages must pass the live King Wen prompt/tables expected by the workspace API.
- Zero mock/stub/fabrication allowed in King Wen integration paths.
