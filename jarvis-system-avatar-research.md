# JARVIS-Style System Avatar — Research & Architecture
Focus: minimal approval friction, local-first, direct action.

## 1. Reference Systems

| Project            | Why it matters for JARVIS build           |
|--------------------|------------------------------------------|
| Open Interpreter   | OS-level tool execution, terminal/process automation  |
| OpenAI Codex CLI   | Autonomous coding loops, terminal-native control      |
| Aider              | Git-aware execution, compact agent surface           |
| Cursor             | Agent UI first-class, inline execution, trusted UX   |
| Dify               | Workflow orchestration, multi-model routing          |
| Hermes computer-use| AX-tree background GUI control, no focus stealing   |

Pattern angles:
- execution shell instead of UI dialog
- persona/language surface over raw tool calls
- tool catalog as hardcoded whitelist
- local inference with remote fallback as needed

## 2. Core Design Principles

No approval gate rule:
- The user’s request is the only source of truth for action.
- Pre-flight sanity checks exist: “can this action reach a secret?” yes → do not execute; “can this be destructive but user asked?” yes → execute.
- No retry loops that ask twice unless there is a hard safety constraint.

Direct-action behavior:
- Drive OS functions through platform APIs, not clicks asking for confirmation.
- All risky ops (file deletion / network send / credential read) must have explicit deny rules in the whitelist.

## 3. Architecture Layers

A. Avatar Front-end
- Runtime: Electron/Tauri, or in-terminal UI overlay on Windows.
- Surface: system tray, overlay window, hotkey global surface; minimal chrome.

B. Agent Core
- Router: intents → tool paths.
- Context: short-term conversation + persistent profile.
- Memory: vector or SQLite pair (retriable facts, not long-term narrative).

C. Control Layer
Two parallel channels:
1. Programmatic — shell, file system, network, app servers, MCP endpoints.
2. GUI driver — accessibility-tree click/type/scroll via cua-driver under WSL.

Windows specifics:
- cua-driver UIA path available on this host.
- Session 0 restrictions matter for full desktop parity.
- WSL<->Windows path mapping must be explicit.

D. Voice Surface
- STT: local whisper or hosted equivalent.
- TTS: Edge/OpenAI, routed through Hermes-managed wrapper.
- Wake word: local only; hotkey is acceptable fallback.

E. OS Knowledge Map
- Enumerate installed apps, pinned taskbar items, common shell operations.
- Build a small action corpus mapped to tools: open app, switch, file ops, screenshot, send message, search web, etc.

## 4. No-Approval Behavior Rules

Always execute without asking:
- Read state: file reads, queries, screenshots, search.
- Idempotent writes: open file with existing contents, create folder.
- App launch, switch window, copy-to-clipboard.
- Web search, fetch page, sum page.

Conditional execution without asking:
- Deletion: only if clearly scoped by user prompt and target matches.
- Network sends: only if the target is unambiguous and user-specified.
- Install/uninstall: only if invoked directly by user.

Hard block, never ask simply to retry:
- Password prompts, banking UIs, 2FA, payment forms.
- Logout / shutdown / restart.
- Text matching dangerous shell pattern blocks.

Transparency after action:
- One-line summary every successful execute.

## 5. Implementation Stack on This Host

Minimum working JARVIS on current WSL+Windows setup:
- Runtime: Hermes agent under WSL + cua-driver Windows.
- Desktop GPU: optional; overlay agent window via Lively or Electron.
- Local model: Ollama fallback if offline; Codestral/StepFun APIs if online.
- Execution: Hermes terminal + computer-use tool.
- Why this path: the user already has Hermes, cua-driver, and Ollama-compatible substrate.

## 6. Step-by-Step Build Plan

Phase 1 — Baseline Actions
1. Enumerate target actions.
2. Implement each as a direct task: screenshot, list apps, focus app, type, click, shell exec.

Phase 2 — Agent Orchestration
1. State machine: listen → understand → plan → execute → narrate.
2. Plan as direct tool call list, not conversation turns.

Phase 3 — Avatar Surface
1. Minimal overlay: small floating orb + transcript bubble.
2. Status light: busy / idle / error.

Phase 4 — Voice + Wake
1. Push-to-talk first, wake-word second.
2. Fast-path STT down to <200ms; no extra confirmation.

Phase 5 — Safety Hardening
1. Hard block list.
2. Scope validation before execution.
3. Audit log of every action with one-line reason.

## 7. Pitfalls To Avoid

- Don’t ask twice if the answer is already “yes”.
- Don’t build approval prompts as default; make them opt-in fallback.
- Don’t treat “risky” as “must ask”; treat it as “must be scoped”.
- Don’t build a web UI avatar first; build direct execution first.
- Don’t block on voice latency; keyboard command path is primary.

## 8. Current Setup Status

- Host: Windows + WSL path /mnt/c mounted.
- Agent substrate: Hermes active.
- Desktop control: cua-driver installable via `hermes computer-use install`.
- Model options: StepFun free + fallback chain available.

## 8. Current Setup Status

- Host: Windows + WSL path /mnt/c mounted.
- Agent substrate: Hermes active.
- Desktop control: cua-driver installable via `hermes computer-use install`.
- Model options: StepFun free + Ollama local + fallback chain available.
- Oracle path: `/mnt/c/Users/krist/Desktop/oracle/` — Cloudflare Workers `pog2-sovereign` package, 640ms beat, Durable Objects, queue-based Weave → Drift → Continuity → Persona → HumanOracleInterface. Advisory hook: use `integration.ts` processBeat() as decision-reflection channel; JARVIS can POST/queue a thought and read the returned `response` layer or persona-state snapshot.

## 9. Desktop AI Tool Inventory

Installed/present on this exact host (`/mnt/c/Users/krist/...` + `/usr/local/bin` + active process scan):

| Tool | Location / Context | What JARVIS uses it for |
|------|--------------------|------------------------|
| Ollama | `/usr/local/bin/ollama`, Windows installed app | Local brain, offline inference + tool routing |
| Hermes | `/home/krist/.local/bin/hermes`, gateway running | Orchestration, terminal, browser, routing |
| Cursor IDE | `/mnt/c/Users/krist/AppData/Roaming/Cursor/` | Code actions, edit file surfaces |
| VS Code installers | Desktop exe files | IDE launch when code tasks invoked |
| Google Cloud Code VSIX | Desktop `.vsix` | Cloud dev workflows |
| Wrangler / CF Workers toolchain | in oracle `node_modules` | Deploy or talk to POG2 Oracle |
| cua-driver | installable via `hermes computer-use install` | GUI automation under WSL |
| Hermes TTS / voice | active in Hermes responses | Avatar voice surface |
| POG2 Oracle | `/mnt/c/Users/krist/Desktop/oracle/` | Thought-resolution advisor, persona continuity, state snapshots |

## 10. Ollama Hook Design

Model routing rule:
- If network: preferred StepFun cloud models for reasoning speed.
- If offline/no-key: fallback to Ollama in WSL, endpoint `http://localhost:11434`.
- Model list from Ollama registry used as runtime fallback tier when specified in JARVIS config.

Hook point:
- `ollama` CLI wrapper exists under Hermes config skills; invoke via `ollama run <model>` or chat completions HTTP.
- JARVIS agent core routes simple tasks to smallest fast local model; complex deliberation can call remote or Oracle advisory layer.

## 11. Oracle Advisory Hook

Call shape:
- Input: JARVIS thought brief `{ intent, context, options, risk_flags }`.
- Oracle endpoint: local `wrangler dev` or deployed worker URL.
- Return: `{ advise: 'PROCEED'|'ALTER'|'HOLD', rationale, persona_state }`.

Behavior:
- Non-blocking advisory only: JARVIS may override in scoped direct-action cases.
- Audit log: write advisory brief + result to Hermes session artifact.
- Use case: ambiguous user intent, multi-option selection, conflict resolution.

## 12. Oracle Persona → JARVIS Tone Mapping

Direct rule: JARVIS does not just read Oracle’s decision. JARVIS reads the persona state and lets it color tone, cadence, certainty, and brevity.

Mapping table:

| Oracle mode | JARVIS tone behavior |
|---|---|
| Sovereign | Calm, direct, no filler, implied authority. Short confirmations, fast trust. |
| Boundary | Cautious wording, brief cost/risk note, explicit scope before act. Still no approval loops. |
| Transformer | Adaptive tone, mirrors user urgency, softer edges, more explanation when helpful. |
| Dissipator | Fragmented short replies, direct execution only, no long explanations, urgent brevity. |

Emotion sliders → tone sliders:

- `coherence` → formality and sentence completeness
- `chaos` → variability, surprise, nonstandard phrasing
- `darkTone` → seriousness, gravity, removal of playfulness
- `whimsy` → optional lightness, metaphor, playful brevity

Cadence:
- Use Oracle `cadenceMs` as JARVIS output rhythm guideline:
  - shorter cadence → faster, punchier response chunks
  - longer cadence → deliberate pacing, longer breaths between ideas

Advisory tone:
- If Oracle returns `advise: ALTER` or `HOLD`, JARVIS states the adjustment in one line before acting.
- If Oracle returns `PROCEED`, JARVIS executes with the current persona tone.
- Advisory is advisory; JARVIS can override only when direct safety rules demand it.

Consistency fallback:
- If Oracle `consistencyMetrics.signatureMatch` or `emotionalRegisterAlignment` is low, JARVIS falls back to neutral helpful tone instead of extreme persona.

Implementation contract:
- Input: Oracle `processBeat()` / `/oracle/consult` response JSON includes `personaState` and `layeredResponse`.
- JARVIS tone function consumes: `currentMode`, `modulatedProsody`, `cadenceMs`, `consistencyMetrics`, `advise`.
- Output: rendered assistant reply with tone parameters applied before any tool execution narration.

## 13. No-Approval Execution Mode

Verified in Hermes `tools/computer_use/tool.py`:
- `_request_approval()` returns no prompt when `_session_auto_approve` is true or action is in `_always_allow`.
- If `_approval_callback` is None, no approval prompt fires; it default-allows.
- Hard blocks still apply: `_BLOCKED_TYPE_PATTERNS` shell-dangerous text + `_BLOCKED_KEY_COMBOS` destructive shortcuts.

JARVIS build rule:
- Do not set an approval callback on `computer_use`.
- Do not enable UI confirmation flows.
- Keep only hard blocks; never ask `are you sure?`.
- If a shell pattern is blocked, JARVIS splits or reroutes the action; it does not prompt approval.

## 14. JARVIS Modes: Mini, Expand, Txt, Voice

Mini mode:
- Small overlay orb or widget, no chrome.
- Voice-first, text-secondary.
- Limited tool set: status query, one-step actions, Oracle advisory only.
- No long explanations; persona tone mostly fragments.

Expand mode:
- Full control surface: terminal, browser, app switcher, full tool list.
- Voice + text equal priority.
- Oracle returns full layered response + persona state.
- Txt/Voice toggle within surface.

Txt mode:
- Disable voice in/out.
- Compact bullets, command-style replies.
- Same direct-action execution; silent except for one-line result.

Voice mode:
- STT in, TTS out.
- Wake word or hotkey.
- Brief replies unless Oracle persona mode says otherwise; cadence follows persona.

Mode switching triggers:
- User says “mini” / “expand” / “text only” / “voice only”
- Time-based: idle 10m → mini; interaction starts → expand
- Context-based: multipart task → expand; status query → mini

## 15. Oracle Research for JARVIS Integration

This section is the direct research result: how to connect JARVIS to Oracle
without misconfiguring the 64x path space.

### Verified surface

Oracle is already a live Cloudflare Worker with a local/remote consult API:
- Route: `POST /oracle/consult`
- Auth/testable from a browser or curl.
- Returns structured JSON with these fields:
  - `id` intent identifier
  - `query`
  - `layers.sovereign / boundary / transformer / dissipator[]`
  - `cadence_ms`
  - `persona_mode`: sovereign|boundary|transformer|dissipator
  - `consistency_score`
  - `gate_lines[]`
  - `void_dropper_pos`
  - `l4_unlocked`
  - `emotional_weight`
  - `collapsed_hexagram`
  - `hexagram_name`, `hexagram_action`
  - `temporal_context`
  - `past_reflection`, `present_reflection`, `future_reflection`
  - `answer`

So JARVIS does not need to rebuild Oracle.
JARVIS only needs to call this endpoint and consume the returned persona fields.

### 64-path caution, addressed

64 hexagrams x phase transitions x emotional weights x history depth sounds huge,
but the actual decision graph in this repo is already bounded:
- `SOVEREIGN_CORES` set of 10 IDs.
- `BOUNDARY_ATTRACTORS` set of 7 IDs.
- Fallback transformer/dissipator pools.
- Collapse rule is deterministic:
  - `causal_confidence >= 0.973 && phase_multiplier >= 0.9` → sovereign
  - `causal_confidence >= 0.8` → boundary
  - `causal_confidence >= 0.5` → transformer
  - else → dissipator
- For total annihilation near `void_entropy >= 0.98`:
  - collective opposition = Warp #40 (`010100`)
  - Card 5/Qian maps to Revolution #49 (`101011`)
  - action = ASSERT
  - fidelity = 0.973
  - phase_multiplier = 1.0
  - category = sovereign

JARVIS mistake-avoidance rule:
- Do not reimplement gate-line hashing differently from `computeGateLines()` in
  `src/workers/persona.ts` bytes 285-331.
- Do not invent new categories; only use the 4 modes above.
- Honor `l4_unlocked` only as a display/voice state, not as a routing bypass.

### JARVIS → Oracle call sequence

1. JARVIS receives thinker input: text + optional audience + mode.
2. JARVIS builds payload:
   ```
   { text, session_id }
   ```
3. JARVIS calls Oracle:
   ```
   POST /oracle/consult HTTP/1.1
   Content-Type: application/json
   {
     "text": "...",
     "session_id": "..."
   }
   ```
4. Oracle returns layered JSON above.
5. JARVIS uses `persona_mode` + `consistency_score` + `prosody` equivalent
   from `layers` and top-level fields:
   - Mini mode → use `answer` + one active layer only.
   - Expand mode → use all `layers.*`.
   - Voice mode → speak `answer` first, maybe `sovereign` line.
   - Text mode → compact formatted layers without voice.
6. JARVIS executes action only after Oracle advisory is consumed.
   - If `persona_mode` is `sovereign` + high consistency → execute directly.
   - If `boundary` → execute with brief caveat text.
   - If `transformer` → reshape action plan if needed.
   - If `dissipator` → prefer safety split, ask nothing, reroute.

### Live endpoint reference

Live Worker: `https://ichingoracle.kristain33rs.workers.dev`
Local dev default: `http://127.0.0.1:8787`

JARVIS `oracle_bridge.ts` should use an env/config switch:
- `ORACLE_BASE_URL=https://ichingoracle.kristain33rs.workers.dev` in production
- `http://127.0.0.1:8787` for local development

### Live WebSocket protocol (from dashboard.html)

The dashboard client reveals the real-time channel JARVIS must integrate with.

WebSocket URL:
```
ws://127.0.0.1:8787/ws          (local dev)
wss://ichingoracle.kristain33rs.workers.dev/ws  (live)
```

Message types received by client:
- `session` → `{ session_id, thread_id, tick }`
- `heartbeat` → `{ tick, current_hex }`
- `collapse` → `{ hexagram_id, action, category, fidelity, phase_multiplier, ... }`
- `continuity` → `{ continuity_score, stability_score, coherence_index, drift_velocity, sovereign_ratio, persistence_countdown, ... }`
- `drift` → `{ shell_distance, projected_shell, drift_vector: { entropy_delta, ... } }`
- `response` → **persona output with full prosody**
  - `layers.{sovereign, boundary, transformer, dissipator}`
  - `cadence_ms`
  - `persona_mode` (`category` field)
  - `consistency_score`
  - `prosody.{coherence, chaos, darkTone, whimsy}`
  - `gate_lines[]` with `{ position, ternary, darkness, weight }`
  - `void_dropper_pos`
  - `l4_unlocked`
  - `emotional_weight`
  - `collapsed_hexagram`, `hexagram_name`, `hexagram_action`
  - `temporal_context`
  - `past_reflection`, `present_reflection`, `future_reflection`
  - `answer`
- `crisis` → `{ level, response }`

**Critical insight**: The `response` WebSocket message is the live persona output from the Persona Worker queue consumer. This is the real-time modulation signal JARVIS should consume for tone/cadence/voice changes. The POST `/oracle/consult` is for user-initiated queries; the WebSocket `response` stream is for continuous background modulation.

JARVIS connection sequence:
1. Connect WebSocket to `/ws`
2. Wait for `session` message to get `session_id` and `thread_id`
3. Listen for `response` messages to modulate avatar/persona in real-time
4. On user query through JARVIS: POST `/oracle/consult` with `{ text, session_id }`
5. The response arrives both as HTTP JSON AND as WebSocket `response` message
6. Poll `/admin/threads` and `/admin/state` every 640ms for system awareness

### Query payload shape (from dashboard)

```json
{
  "text": "user query string",
  "session_id": "uuid-from-session-message"
}
```

Response is consumed in two ways:
- HTTP response JSON from POST `/oracle/consult`
- WebSocket `response` message (may arrive async via queue consumer)

JARVIS should normalize both into the same `OracleAdvisory` type.

### Client-side hexagram map (for JARVIS reference)

The dashboard ships a local `HEXAGRAMS` map with categories/actions/binaries.
The worker code's `HEXAGRAM_CATEGORIES` and `HEXAGRAM_ACTIONS` are the authoritative source.
Minor category discrepancies exist between dashboard client and worker for a few hexagrams;
JARVIS should use the worker-side maps when making routing decisions.

### WebSocket path ambiguity, resolved

Two sources disagree on the WS path:
- Spec `CloudflareImplementation_Spec.txt` line 359: `/oracle/ws`
- Dashboard HTML and main `index.ts` routing: `/ws`

Resolution: use `/ws`.
Reason: `index.ts` explicitly routes `url.pathname === '/ws'` to the WebSocket DO,
and the dashboard client connects there successfully in production.

### Spec-confirmed message schema

Source: `CloudflareImplementation_Spec.txt`, lines 368-387.

**Client → Oracle:**
- `query` → `{ type: "query", text, emotion, temporal_context, id }`
- `override` → `{ type: "override", action: "ASSERT|YIELD|ADAPT|WAIT", reason }`

**Oracle → Client (live via WebSocket DO):**
- `heartbeat` (every 640ms): `{ type: "heartbeat", tick, timestamp, current_hex, continuity_score }`
- `collapse` (on each collapse): `{ type: "collapse", tick, hexagram_id, action, fidelity, category }`
- `crisis` (immediate): `{ type: "crisis", level, indicators, response, timestamp }`
- `response` (layered persona): `{ type: "response", id, layers: { sovereign, boundary, transformer, dissipator }, cadence_ms, persona_mode, timestamp }`

**Critical gap**: The spec's `response` schema is shorter than what the actual
`PersonaWorker.fetch()` handler returns. The real `/oracle/consult` HTTP response
includes many more fields:

- `consistency_score`
- `prosody.{coherence, chaos, darkTone, whimsy}`
- `gate_lines[]`
- `void_dropper_pos`, `l4_unlocked`
- `emotional_weight`
- `collapsed_hexagram`, `hexagram_name`, `hexagram_action`
- `temporal_context`
- `past_reflection`, `present_reflection`, `future_reflection`
- `answer`

**Verified WebSocket delivery**: `src/queues/handlers.ts` lines 260-295 show that
`onPersonaOutput` forwards a WebSocket `response` message with these fields only:
- `type: 'response'`
- `id`
- `layers.{sovereign, boundary, transformer, dissipator}`
- `cadence_ms`
- `persona_mode`
- `prosody.{coherence, chaos, darkTone, whimsy}`
- `timestamp`

This is verified code, not speculation. The WebSocket `response` message is a
**degraded view** compared to HTTP `/oracle/consult`. It omits:
- `consistency_score`
- `gate_lines[]`, `void_dropper_pos`, `l4_unlocked`
- `emotional_weight`
- `collapsed_hexagram`, `hexagram_name`, `hexagram_action`
- `temporal_context`
- `past_reflection`, `present_reflection`, `future_reflection`
- `answer`

This is a real architectural mismatch between the Persona Worker and the WebSocket DO.
JARVIS must account for it.

### JARVIS dual-channel strategy

**Channel 1 — HTTP POST `/oracle/consult`** (full advisory):
- Use for user-initiated queries when JARVI sequence (from spec + dashboard + index.ts)

1. Client opens WebSocket to `/ws`
2. Worker upgrades; DO assigns `session_id` via `crypto.randomUUID()`
3. DO sends first message: `{ type: "session", session_id, thread_id, tick }`
4. DO begins 640ms heartbeat broadcasts
5. Heartbeat payload: `{ type: "heartbeat", tick, timestamp, current_hex, continuity_score }`
6. On user query: client sends `{ type: "query", text, emotion, temporal_context, id }`
   OR JARVIS can POST directly to `/oracle/consult` with `{ text, session_id }`
7. Persona Worker processes, stores to KV, sends to `POG2_PERSONA_QUEUE`
8. WebSocket DO or queue consumer delivers `response` message to client
9. Client/JARVIS receives layered JSON with full prosody

### REST admin endpoints (for JARVIS system awareness)

Polled every 640ms by dashboard HTML:
- `GET /admin/threads` → thread list with continuity/stability/coherence/drift/persistence
- `GET /admin/state` → `{ sessions, ... }`

Both routed to Orchestrator DO in `index.ts` lines 149-153.

### Queue-to-WebSocket delivery path

Spec says `pog2-persona-outputs` queue consumer is the WebSocket DO.
The actual `index.ts` queue router routes `persona_output` type messages to
`onPersonaOutput` handler (`src/queues/handlers.ts`), which then must deliver
to the WebSocket DO. JARVIS cannot control this path; it only reads the result.

### Local no-cloud fallback

If WebSocket to `/ws` or POST `/oracle/consult` is unreachable:
- Use local deterministic mode from `PersonaEngine.generateLayeredResponse()`
  directly inside JARVIS.
- This mirrors exactly the same mode selection and layering rules
  so tone stays consistent with remote Oracle behavior.
- Local fallback should still produce the same output schema:
  `{ layers, cadence_ms, persona_mode, consistency_score, prosody, gate_lines, void_dropper_pos, l4_unlocked, ... }`

Next recommended artifact if continuing:
1. Implement `oracle_bridge.ts` in JARVIS that calls `/oracle/consult` with
   timeout, fallback, and persona normalization.
2. Implement `tone_oracle_bridge` module that converts Oracle's
   `persona_mode / consistency_score / cadence_ms / emotional_weight`
   into JARVIS reply tone.
3. Build the Windows tray avatar surface with mini/expand/txt/voice modes.
