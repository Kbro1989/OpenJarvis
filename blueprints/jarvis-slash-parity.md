# Jarvis Slash Parity Blueprint
Created: 2026-07-16
Source: Hermes live command surfaces + OpenJarvis runtime

## Goal
Functional parity for `/agents`, `/blueprint`, `/rules`, `/journey`, `/learn` across dashboard | CLI | desktop as one runtime.

## Verified Hermes Surfaces
- `/blueprint`: `hermes_cli/blueprint_cmd.handle_blueprint_command`
  - Returns `BlueprintCommandResult(text, agent_seed=None|str)`
  - Catalog: `cron.blueprint_catalog.CATALOG`
  - Matching: exact → prefix → substring → fuzzy
- `/agents`: gateway slash handler `_handle_agents_command`
  - Shows active agents, running processes, background tasks
- `/journey`: renders skill/memory timeline; supports `list|delete|edit`
- `/rules`: loaded skill `rules`; not a standalone slash command

## OpenJarvis Current State
- `/oracle`, `/counsel`: director payload + audio playback wired
- `/blueprint`: custom King Wen handler; NOT using Hermes catalog/result contract
- `/agents`: registry listing only; no active-task surface
- `/journey`: lookup/replay/weave/consult/leaderboard wired
- `/learn`: status/run/ingests/ingest wired
- `/rules`: not present as command or skill in Jarvis

## Parity Gaps
1. `/blueprint` must consume `handle_blueprint_command` result, not print custom help
2. `/agents` must surface active/running/background state, not just registry names
3. `/rules` must load and enforce the `rules` skill in Jarvis runtime
4. `/journey` must render timeline/graph in desktop and dashboard, not only CLI JSON
5. Shell startup must initialize Hermes command registry first, then layer Jarvis extensions

## Next Actions
- Patch `chat_cmd.py` `/blueprint` to call `handle_blueprint_command`
- Patch `chat_cmd.py` `/agents` to mirror Hermes active-task output shape
- Add `/rules` handler that loads `rules` skill and runs enforcement scan
- Add `/journey` graph renderer for desktop/dashboard
- Verify with `py_compile` + pytest after each patch
