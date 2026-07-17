# OpenJarvis Implementation Checklist
Updated: 2026-07-16
Root: C:\Users\krist\Desktop\OpenJarvis

## State Legend
- [ ] pending
- [~] in progress
- [x] complete
- [!] blocker
- [r] needs review
- [d] deprecated/remove

## Project Files Tracked

### Core Config
- [x] `.gitignore` — 132 lines, 2538 bytes [FEED]
- [x] `.pre-commit-config.yaml` — 7 lines, 159 bytes [FEED]
- [x] `pyproject.toml` — 249 lines, 9032 bytes [FEED]
- [x] `uv.lock` — 8650 lines, 1444730 bytes [FEED]
- [ ] `Makefile` — 19 lines, 505 bytes [FEED]

### Documentation
- [x] `README.md` — 169 lines, 8364 bytes [FEED] real project description present
- [x] `CHANGELOG.md` — 356 lines, 19822 bytes [FEED]
- [x] `CODE_OF_CONDUCT.md` — 85 lines, 5622 bytes [FEED]
- [x] `CONTRIBUTING.md` — 201 lines, 7234 bytes [FEED]
- [x] `REVIEW.md` — 43 lines, 2632 bytes [FEED]
- [r] `mkdocs.yml` — 205 lines, 6584 bytes [FEED]

### Research / Artifacts
- [x] `jarvis-system-avatar-research.md` — 523 lines, 22621 bytes [FEED]
- [x] `king_wen_codebasemap.md` — 156 lines, 7473 bytes [FEED]
- [x] `ollama_docs_complete_tree.txt` — 467 lines, 22002 bytes [FEED]
- [x] `ollama_launch_specs.txt` — 339 lines, 11301 bytes [FEED]
- [x] `ollama_multi_service_routing_guide.txt` — 1074 lines, 31435 bytes [FEED]
- [x] `openjarvis_windows_already_installed.txt` — 123 lines, 4550 bytes [FEED]
- [x] `membrane-path.html` — 354 lines, 12866 bytes [FEED]
- [x] `jarvis-capture-returns.json` — 139 lines, 5534 bytes [FEED]

### Capture Artifacts
- [x] `consult-capture.headers` — 11 lines, 573 bytes [FEED]
- [d] `consult-capture.body` — 0 lines, 2398 bytes [FEED] ⚠ EMPTY
- [x] `verify_oracle_worker.py` — 178 lines, 5909 bytes [FEED]

### Temp / Debug Scripts
- [d] `tmp_kingwen_debug_console.py` — 115 lines, 4046 bytes [FEED] ⚠ TEMP
- [d] `tmp_kingwen_smoke_agent_tails.py` — 222 lines, 7392 bytes [FEED] ⚠ TEMP
- [d] `tmp_kingwen_tail_probe.py` — 299 lines, 11944 bytes [FEED] ⚠ TEMP
- [d] `test_store.py` — 34 lines, 1333 bytes [FEED] ⚠ TEMP
- [d] `gen_expansion.py` — 137 lines, 5164 bytes [FEED] ⚠ TEMP
- [d] `--help` — 0 lines, usage text [FEED] ⚠ MISNAMED
- [d] `nul` — 0 lines, 0 bytes [FEED] ⚠ WINDOWS NULL DEVICE ARTIFACT

### License
- [x] `LICENSE` — 190 lines, 10963 bytes [FEED]

## Source Code Structure

### Core Modules
- [x] `src/openjarvis/core/` — config, registry, journey_executor, session_clock_bridge, events, types
- [x] `src/openjarvis/cli/` — chat_cmd, blueprint_cmd, _oracle_speak, serve, audio_dsp, scheduler_cmd
- [x] `src/openjarvis/agents/` — agent registry, _stubs, monitor_operative, orchestrator
- [x] `src/openjarvis/speech/` — cartesia_adapter, cartesia_tts, cloudflare_ai_tts, voice_reward_sidecar
- [x] `src/openjarvis/learning/` — kingwen_pseudopod_ingest
### King Wen Tool Modules (real artifacts, verified py_compile + 21/21 pytest)
- [x] `src/openjarvis/tools/kingwen_script_pipeline_tool.py` — 1053 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_oracle_consult_tool.py` — 109 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_voice_tools.py` — 389 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_learning_tools.py` — 638 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_model_select_tool.py` — 317 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_narrative_dispatch_tool.py` — 489 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_vhdl_router_tool.py` — 521 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_consensus_router.py` — 174 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_consensus_tailer.py` — 90 lines [FEED]
- [x] `src/openjarvis/tools/kingwen_actionable_bridge.py` — 348 lines [FEED]
- [x] `src/openjarvis/tools/task_engine.py` — 358 lines, real artifact, py_compile + pytest + live verified [FEED]
- [x] `src/openjarvis/tools/process_registry.py` — 4544 bytes [FEED]
- [x] `src/openjarvis/tools/async_delegation.py` — 346 bytes [FEED]
- [x] `src/openjarvis/tools/kanban_staging_bridge.py` — 328 lines, ports antigravity kanban-staging-queue watcher+ticker+skill_sync, py_compile + pytest + live verified [FEED]
- [x] `src/openjarvis/save/jarvis_save_string.py` — save string encoder/decoder, ported from openrsc-vinilla player_save.json, py_compile + live verified [FEED]
- [x] `src/openjarvis/save/save_string_bin.py` — local bin with tick-based CF push, usage-aware throttling, py_compile + live verified [FEED]
- [x] `src/openjarvis/engine/` — ollama, cloud, litellm, openai_compat, multi
- [x] `src/openjarvis/channels/` — 30+ messaging channels
- [x] `src/openjarvis/connectors/` — 30+ external service connectors
- [x] `src/openjarvis/evals/` — eval configs, core, backends, comparison
- [x] `src/openjarvis/daemon/` — gateway, service, session_expiry
- [x] `src/openjarvis/a2a/` — agent-to-agent protocol
- [x] `src/openjarvis/analytics/` — aggregator, bridge, events, identity, redaction

### Directories
- [x] `src/` — 1606 files [FEED]
- [x] `tests/` — 2556 files [FEED]
- [x] `tools/` — 2 files [FEED]
- [x] `scripts/` — 18 files [FEED]
- [x] `skills/` — 2 files [FEED]
- [x] `docs/` — 97 files [FEED]
- [x] `deploy/` — 14 files [FEED]
- [x] `cloudflare/` — 2 files [FEED]
- [x] `configs/` — 11 files [FEED]
- [x] `data/` — 3 files [FEED]
- [x] `emotion/` — 3 files [FEED]
- [x] `examples/` — 31 files [FEED]
- [x] `frontend/` — 50420 files [FEED]
- [x] `rust/` — 4661 files [FEED]
- [x] `assets/` — 4 files [FEED]
- [x] `blueprints/` — 1 file [FEED]
- [x] `desktop/` — 2 files [FEED]
- [x] `scratch/` — 1 file [FEED]

### Hidden Directories
- [x] `.git/` — 45 files [FEED]
- [x] `.github/` — 21 files [FEED]
- [x] `.hermes/` — 3 files [FEED]
- [x] `.openjarvis/` — 1 file [FEED]
- [x] `.pytest_cache/` — 5 files [FEED]
- [x] `.venv/` — 9696 files [FEED]
- [x] `.wrangler/` — 1 file [FEED]
- [d] `MagicMock/` — 6 files [FEED] ⚠ REVIEW: mock data in repo?
- [d] `~/` — 2 files [FEED] ⚠ TEMP DIR

## Slash Command Parity Targets

### Implemented (Jarvis-native)
- [x] `/oracle` — consult King Wen, synthesize voice to file
- [x] `/counsel` — same as /oracle with PPF framing
- [x] `/blueprint` — Hermes-shaped catalog/seed/create
- [x] `/learn` — status/run/ingests/ingest with provenance
- [x] `/journey` — lookup/replay/weave/consult/leaderboard
- [x] `/agents` — process_registry + async delegations + agent state + registered agent inventory
- [x] `/rules` — scans OpenJarvis `src/` and Hermes skills for placeholders/mocks/NotImplementedError
- [x] `/script` — universal script pipeline: 9 types, quantum expansion, voice modulation, ledger
- [x] `/task` — deterministic task decomposition + real tool execution + verification gates + artifact ledger
- [x] `/save` — save string append/stats/tick/reset via local bin
- [x] `/load` — load save state by session_id

### In Progress
- [x] `/tools` — enable/disable tools, reset session (chat_cmd.py)
- [x] `/cron` — list/status/pause/enable/disable via hermes/cron/jobs.json (chat_cmd.py)
- [x] `/memory` — queue/approve/reject/flush approval gate via ~/.openjarvis/memory_approvals.jsonl (chat_cmd.py)
- [x] `/rules` — load and enforce rules skill

### Pending
- [ ] `/background` — background task spawning with event-bus completion
- [ ] `/moa` — mixture of agents slot state + journey bias
- [ ] `/journey` graph renderer for dashboard/desktop
- [ ] `/skills` — search/install/inspect/audit skills
- [ ] `/config` — show/edit configuration
- [ ] `/model` — switch model with provider routing
- [ ] `/voice` — TTS mode toggle + Cartesia adapter
- [ ] `/status` — session/model/token/context info
- [ ] `/compress` — conversation compression with preview
- [ ] `/undo` — backup N turns and re-prompt
- [ ] `/goal` + `/subgoal` — standing goals with criteria
- [ ] `/queue` + `/steer` — prompt queue and injection
- [ ] `/sessions` + `/resume` — session management

## Verification Status

### Last Verified
- [x] `py_compile` — chat_cmd.py, journey_executor.py, session_clock_bridge.py, blueprint_cmd.py
- [x] `pytest` — 21 passed in 3.45s
- [x] `/blueprint` catalog — matches Hermes upstream contract
- [x] `/agents` — process_registry.list_sessions() resolves
- [x] `/learn ingest` — 31 rows written to kingwen_pseudopod_ingest.jsonl
- [x] `/journey consult` — calls _consult_worker() against kingwen-oracle worker
- [x] `session_clock_bridge` — all 4 functions callable, graceful Hermes fallback

### Unverified
- [ ] `/rules` — skills_hub/rules import path (scan works, import path TBD)

### Verified This Session
- [x] `/cron` — reads hermes/cron/jobs.json, pause/enable/disable write-back; AST clean
- [x] `/tools` — ToolRegistry._session_disabled set, list/enable/disable/reset; AST clean
- [x] `/memory` — jsonl queue at ~/.openjarvis/memory_approvals.jsonl, queue/approve/reject/flush; AST clean

## Dependencies to Remove (Independence Rule)

### Hard Dependencies
- [x] `session_clock_bridge.py` imports `agent.session_clock` from Hermes runtime (Decoupled!)
  - Fix: replace with contract-only interface (Done)
  - Path: `src/openjarvis/core/session_clock_bridge.py`
  - Attachment: `JourneyExecutor.consult()`, `/learn ingest`

### Awareness-Only (Allowed)
- [x] `process_registry.py` — mirrors Hermes `tools/process_registry.py` shape, no import
- [x] `blueprint_cmd.py` — reimplements Hermes `hermes_cli/blueprint_cmd.py` contract, no import
- [x] `async_delegation.py` — mirrors Hermes `tools/async_delegation.py` shape, no import

## Next Actions (Priority Order)

1. [x] Remove `session_clock_bridge.py` Hermes import, replace with contract interface
2. [x] Port `/cron` from Hermes cron/jobs.json contract
3. [x] Port `/tools` enable/disable with session reset
4. [x] Port `/memory` approval-gate system
5. [ ] Port `/background` task spawning
6. [ ] Build `/journey` graph renderer for dashboard/desktop
7. [ ] Clean up temp files: `tmp_*.py`, `test_store.py`, `gen_expansion.py`, `--help`, `nul`
8. [ ] Review `MagicMock/` directory — mock data should not ship in product
9. [ ] Expand `README.md` from 6 lines to full project description
10. [ ] Add `kingwen` script runner mode to rsmv Model Viewer

## Artifacts Created This Session
- `C:\Users\krist\Desktop\OpenJarvas\hermes-fork-middleware-map-2026-07-16.md` — middleware attachment map
- `C:\Users\krist\Desktop\OpenJarvas\hermes-session-clock-provenance-map-2026-07-16.md` — session clock mapping
- `C:\Users\krist\Desktop\OpenJarvas\openjarvas-kingwen-io-ports-audit-2026-07-07.md` — King Wen I/O audit
- `C:\Users\krist\Desktop\OpenJarvis\blueprints\jarvis-slash-parity.md` — slash parity blueprint
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\core\session_clock_bridge.py` — temporal authority bridge
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\cli\blueprint_cmd.py` — Jarvis-native blueprint handler
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\core\journey_executor.py` — consult with provenance tagging
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\cli\chat_cmd.py` — /agents, /blueprint, /rules, /learn ingest

## Notes
- Strict no-mock policy: zero placeholder/stub/mock in src/tests/workers/tools
- No undo/restore/checkout/reset/revert without explicit user authorization
- Git push only after explicit acceptance as shippable
- Jarvis and Hermes are independent programs, aware of each other via contracts only
- Domain boundaries: King Wen scripts live only in KING-WEN-I-CHING-IMMUTABLE-TABLES/scripts/
- Source of truth: immutable tables are read-only; no edits to KING_WEN_TABLES.py or kingwen_ternary_tables_complete.py
