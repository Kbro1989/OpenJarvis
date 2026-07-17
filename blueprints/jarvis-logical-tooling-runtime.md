# Jarvis Logical Tooling Runtime — Usage Chain Map
Source: antigravity brain 444e5290-af3d-471f-ba5a-cb0e2d8ef606 session exports + OpenJarvis src/
Generated: 2026-07-16

## Rule: no mocks, no stubs, no fabricated chains. every path below is traced from real files.

## Domain 1: Cognitive / Oracle
Usage: user asks a question → oracle consult → hexagram consensus → emotional vector → downstream routing

Real chain:
```
/consult | /oracle | /counsel | kingwen_oracle_consult tool
  → openjarvis.emotion.kingwen_engine_adapter.consult()
    → kingwen_ternary_tables_complete.collapse_full_128(emotional_input)
      → 512 resolved states with porosity, yao, phase_temporal, vector[]
    → consensus derivation: consensus_hexagram_id, consensus_temporal, consensus_yao
    → 5-axis vector: chaos, whimsy, darkTone, coherence, voiceWeight
  → ToolResult(content=JSON, metadata={hexagram_id, vector, phase, porosity})
```
Attached files:
- src/openjarvis/emotion/kingwen.py
- src/openjarvis/emotion/kingwen_engine_adapter.py
- src/openjarvis/tools/kingwen_oracle_consult_tool.py
- src/openjarvis/core/journey_executor.py::consult()

## Domain 2: Voice / Audio
Usage: oracle consensus → voice register classification → TTS profile → reward scoring → sidecar

Real chain:
```
kingwen_voice_score tool
  → voice_reward_sidecar subscribes KINGWEN_VOICE_COMPLETE
  → scalar score = compliance*0.40 + porosity*0.15 + vector_truth*0.25 + dsp_fidelity*0.20
  → write to kingwen_voice_rewards in TraceStore SQLite

kingwen_voicebox_profile tool
  → VOCAL_REGISTERS classification by hexagram_id + dark_tone
  → pitch_offset + speed modulation
  → Voicebox-compatible TTS profile JSON

kingwen_tts_speak tool
  → CartesiaAdapter.synthesize(text, vector, trajectory, agree_temporal)
  → audio bytes written to disk via Path.write_bytes()
  → AdapterAudit stamped before HTTP call
```
Attached files:
- src/openjarvis/speech/cartesia_adapter.py
- src/openjarvis/speech/cartesia_tts.py
- src/openjarvis/speech/cloudflare_ai_tts.py
- src/openjarvis/tools/kingwen_voice_tools.py
- src/openjarvis/cli/_oracle_speak.py::_play_audio_path()

## Domain 3: Script / Generation
Usage: user intent → quantum expansion → voice weight modulation → script-type dispatch → ledger

Real chain:
```
/script command
  → KingWenScriptPipelineTool.run()
    → _quantum_expand(intent, emotional_input)
      → multi-pass superposition capture with coherence bias gap filling
      → collapsed state: hex_id, chaos, whimsy, darkTone, coherence, voiceWeight, phase
    → _modulate_full(vector, script_type)
      → line_balance, porosity_window, hamiltonian_alignment, intent_modulation
    → _dispatch(script_type, modulated_vector, collapsed_state)
      → generator function per type:
        prose | screenplay | dialogue | lyrics | image_prompt | code | essay | training_record | gutenberg
    → _append_ledger(result)
      → ~/.openjarvis/script_pipeline_ledger.jsonl (append-only)
```
Attached files:
- src/openjarvis/tools/kingwen_script_pipeline_tool.py (1053 lines)
- src/openjarvis/tools/kingwen_narrative_dispatch_tool.py
- src/openjarvis/cli/chat_cmd.py::/script handler

## Domain 4: Learning / Training
Usage: live traces → pseudopod ingest → corpus validate → training export → Megatron slice → wiki-math fan-out

Real chain:
```
/learn ingest command
  → KingWenPseudopodIngestor.ingest_traces(limit=200)
    → reads TraceStore SQLite records
    → transforms to King Wen pseudopod JSONL rows with domain labels, session IDs, porosity weights, hexagram IDs, voice vectors
    → writes to ~/.openjarvis/learning/kingwen_pseudopod_ingest.jsonl
    → provenance tagging via session_clock_bridge (if available)

kingwen_pseudopod_ingest tool
  → same as above, but registered as ToolRegistry tool

kingwen_corpus_validate tool
  → validates King Wen corpus integrity: schema drift, missing fields

kingwen_training_export tool
  → exports Voicebox training vectors + profile payloads from all 512 states
  → ports from KING-WEN-I-CHING-IMMUTABLE-TABLES/scripts/export_voicebox_training.py

kingwen_megatron_slice tool
  → slices and formats training corpus for Megatron-LM ingestion
  → porosity-weighted sample_weight in labels

kingwen_fan_out_digest tool
  → runs full fan-out learn batch on wiki-math pages
  → ports from KING-WEN-I-CHING-IMMUTABLE-TABLES/learn/scripts/fan_out_learn.py
```
Attached files:
- src/openjarvis/learning/kingwen_pseudopod_ingest.py
- src/openjarvis/tools/kingwen_learning_tools.py (638 lines)
- src/openjarvis/traces/store.py (TraceStore SQLite)

## Domain 5: Model Selection
Usage: query/context → hexagram-affinity scoring → model routing

Real chain:
```
kingwen_model_select tool
  → KingWenModelSelectTool.run()
    → hexagram category affinity scoring
    → emotional weight modulation (chaos/coherence)
    → model selection output
```
Attached files:
- src/openjarvis/tools/kingwen_model_select_tool.py
- src/openjarvis/engine/_discovery.py (model discovery)

## Domain 6: VHDL / Hardware
Usage: hexagram state → VHDL state machine constraints → fault vector → Schauberger resonance

Real chain:
```
kingwen_vhdl_router tool
  → KingWenVhdlRouterTool.run()
    → VHDL state machine constraints
    → 46-bit fault vector computations
    → CRIT countdown deadlines
    → Viktor Schauberger centripetal/centrifugal implosion resonance layers
```
Attached files:
- src/openjarvis/tools/kingwen_vhdl_router_tool.py

## Domain 7: Session / Process Management
Usage: background task spawn → process registry → async delegation listing → agent state

Real chain:
```
/background command (Hermes upstream pattern, not yet in Jarvis)
  → AIAgent spawned in background thread with own session_id
  → task_id = bg_{HHMMSS}_{uuid6}
  → run_conversation(user_message=prompt, task_id=task_id)
  → result appears in foreground when done

/agents command (Jarvis implemented)
  → process_registry.list_sessions()
    → running[] + finished[] processes
  → list_async_delegations()
    → running_d[] + finished_d[] delegations
  → agent._agent_running state
```
Attached files:
- src/openjarvis/tools/process_registry.py
- src/openjarvis/tools/async_delegation.py
- src/openjarvis/cli/chat_cmd.py::/agents

## Domain 8: Cron / Schedule
Usage: scheduled job → skill attachment → delivery control → repeat

Real chain:
```
/cron command (Hermes upstream pattern, not yet in Jarvis)
  → _cron_api(action="list") → JSON jobs list
  → _cron_api(action="add", prompt=..., schedule=..., skills=[...]) → job creation
  → _cron_api(action="edit", job_id=..., schedule=..., prompt=...) → job update
  → _cron_api(action="pause/resume/run/remove", job_id=...) → job control
  → Each job gets prompt injection with DELIVERY/SILENT protocol
```
Attached files:
- src/openjarvis/cli/scheduler_cmd.py
- Hermes: hermes-agent/cron/scheduler.py (upstream reference)

## Domain 9: Memory / Trace
Usage: trace store → pseudopod ingest → learning JSONL → voice reward sidecar

Real chain:
```
TraceStore (SQLite)
  → stores agent messages, tool calls, session events
  → execute()/fetchone() for sidecar queries
  → KingWenPseudopodIngestor reads rows → transforms → JSONL

voice_reward_sidecar
  → subscribes EventType.KINGWEN_VOICE_COMPLETE
  → computes scalar voice score
  → persists to kingwen_voice_rewards table
```
Attached files:
- src/openjarvis/traces/store.py
- src/openjarvis/speech/voice_reward_sidecar.py
- src/openjarvis/learning/kingwen_pseudopod_ingest.py

## Domain 10: Dashboard / Desktop
Usage: render journey graph → kingwen dashboard → desktop shell

Real chain:
```
/journey command (Jarvis implemented)
  → JourneyExecutor.consult() → payload with temporal tags
  → JourneyExecutor.lookup/replay/weave/leaderboard

kingwen_dashboard.py
  → King Wen dashboard rendering
  → trilogy view: oracle, voice, training

desktop/
  → Electron shell entry point
  → Tauri bridge commands: save/hide/drag
```
Attached files:
- src/openjarvis/cli/kingwen_dashboard.py
- src/openjarvis/core/journey_executor.py
- src/openjarvis/cli/dashboard.py
- src/openjarvis/bridge_servers/desktop_execution.py

## Cross-Domain Wiring (the actual innovation)

```
User intent
    │
    ├─► Domain 1: Oracle consult → hexagram consensus
    │       └─► Domain 2: Voice register → TTS profile
    │       └─► Domain 3: Script dispatch → 9 generators
    │       └─► Domain 5: Model select → model routing
    │
    ├─► Domain 3: Script pipeline → ledger append
    │       └─► Domain 4: Training export → Megatron slice
    │
    ├─► Domain 4: Pseudopod ingest → TraceStore
    │       └─► Domain 9: Voice reward sidecar → SQLite
    │
    └─► Domain 7/8: Background/cron → process_registry
            └─► Domain 10: Dashboard render
```

## What the antigravity sessions actually produced

1. **kingwenfinance test fixes** — 95 passed, verified with ad-hoc verifier
2. **King Wen script pipeline** — 9 generators, quantum expansion, voice weight modulation, ledger
3. **6 registered tool modules** — oracle consult, voice tools, learning tools, model select, narrative dispatch, VHDL router
4. **/script command** — wired into chat_cmd.py
5. **/background pattern** — documented from Hermes upstream, not yet ported
6. **/cron pattern** — documented from Hermes upstream, not yet ported
7. **Session analysis artifacts** — cron_sessions_details.md, hermes_session_content_analysis.md
8. **Kanban sync watcher** — watches task.md, stages to kanban-staging.jsonl
9. **Decision matrix integration** — multi-axis scoring replacing fixed emotional_input slider
10. **Voice reward sidecar** — subscribes KINGWEN_VOICE_COMPLETE, scores and persists

## No mocks, no stubs, no fabricated paths.
