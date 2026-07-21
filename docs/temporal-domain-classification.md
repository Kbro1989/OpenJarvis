# Temporal Domain Classification

Classification scheme:
- cns: consciousness/King Wen inward-directed state
- pns: perceptual/reflexive runtime state
- mcp: model-context/planning state
- api: external-facing transport state

| File | Line | Call | Domain | Rationale | Action |
|---|---|---|---|---|---|
| core/session_clock_bridge.py | 24,32 | `datetime.now(timezone.utc)` | cns | Session provenance/causality | migrate |
| emotion/kingwen.py | 1185 | `time.time()` | cns | Injected state timestamp | migrate |
| agents/_stubs.py | 324 | `time.time()` | pns | Turn-start envelope timestamp | quarantine |
| routing/model_router.py | 146,165,182 | `time.time()` | mcp | Slot cooldown/last_seen ordering | migrate |
| core/kingwen_swarm_store.py | 97 | `time.time()` | cns | Swarm event ordering | migrate |
| scheduler/scheduler.py | 288 | `datetime.now(timezone.utc)` | mcp | Task scheduling decision | migrate |
| workflow/engine.py | 70 | `time.time()` | pns | Step duration measurement | quarantine |
| hermes/delegate.py | 23 | `time.time()` | pns | Delegation event timestamp | quarantine |
| channels/twitter_channel.py | 60 | `time.time()` | api | OAuth external protocol | quarantine |
