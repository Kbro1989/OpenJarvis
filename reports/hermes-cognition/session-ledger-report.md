# Hermes Session / Ledger / Skills — Source Research Report
**Usage:** persistent cognition substrate  
**Intent:** trace how Hermes stores sessions, skills, extracts, and journey clusters  
**Date:** 2026-07-21  
**Primary Sources:** `C:\Users\krist\AppData\Local\hermes\` live store, Hermes docs, GitHub issues  

## 1. Session Storage
- **Path:** `C:\Users\krist\AppData\Local\hermes\sessions\`
- **Format:** `request_dump_<session>_<start>_<end>.json`
- **Count observed:** 257 files
- **Content:** full request/response payloads including system prompts, tool outputs, user messages
- **Retention:** no automatic prune observed; files persist indefinitely unless manually deleted
- **Recall surface:** `session_search()` indexes these via FTS5; `/journey` uses them as raw edges

## 2. Session Artifact Ledger
- **Path:** `cache/session-artifact-ledger.jsonl`
- **Format:** JSONL with `ts`, `session_id`, `surface`, `artifact_type`, `artifact_id`, `path`, `consumer`, `parent_artifact_id`, `cluster`, `synaptic_weight`, `tags`
- **Role:** canonical trace of every significant artifact created during a session
- **Current uses:** `/journey` graph, `/learn` training extracts, session cluster seeds

## 3. Session Cluster Seeds
- **Path:** `cache/session-cluster-seeds.jsonl`
- **Format:** JSONL mapping `session_id → clusters → related_sessions`
- **Current uses:** `/journey` discovery, `/learn` topic extraction

## 4. Proactive Learning Context
- **Path:** `cache/proactive-learning-context.jsonl` and `cache/proactive-learning-context-full.jsonl`
- **Role:** injected into prompt before each LLM call as proactive context
- **Current content:** generic session summaries; no skill-weight decay or reflex arcs

## 5. Curated Session Extracts
- **Path:** `cache/curated-session-extracts.jsonl`
- **Role:** batch-curated knowledge from session dumps
- **Current uses:** `/learn` pipeline, skill activation hints

## 6. Learn Extracts
- **Path:** `cache/learn-extracts.jsonl`
- **Format:** high-weight artifact chains for training
- **Synaptic weights:** 1.0 for user_first intents, 0.85 user_last, 0.5 system_review, 0.4 max_retries_exhausted, 0.3 non_retryable_client_error

## 7. Skills Baseline / Snapshot
- **Path:** `cache/skills-baseline.json`, `cache/skills-snapshot.json`
- **Role:** installed skill inventory, activation rankings
- **Current uses:** skill discovery, `/skills` panel, curator pruning decisions

## 8. Curator Config
- **Config:** `config.yaml` → `curator.*`
- **Settings:** `enabled: true`, `interval_hours: 168`, `stale_after_days: 30`, `archive_after_days: 90`, `prune_builtins: true`
- **Gap:** no semantic merge policy; curation is time-based, not capability-based

## 9. Hermes Web Research Corroboration
- GitHub issue #500 proposes “Proactive Agent Context Loop — Signal-Driven” architecture.
- Public docs confirm Hermes has four-layer memory and session resume.
- No evidence found that Hermes currently implements **reflexive skill rings** or **capability-versioned SOUL indices**.

## 10. Failure Tails
- If `session_search()` index corrupts, **fallback to raw file glob** of `sessions/` sorted by mtime.
- If `session-artifact-ledger.jsonl` exceeds parse budget, **tail-read last N lines** instead of full load.
- If `curated-session-extracts.jsonl` is stale, **fallback to ad-hoc summarization** of recent session files.
- If skill snapshot mismatches installed skills, **fallback to directory scan** of `skills/`.

## 11. Workspace Constants
- `config.yaml` `memory.memory_char_limit`: 220,000,000
- `config.yaml` `memory.user_char_limit`: 13,750,000
- `config.yaml` `agent.max_turns`: 273,000
- `config.yaml` `compression.threshold`: 0.9
- `config.yaml` `compression.target_ratio`: 0.7
