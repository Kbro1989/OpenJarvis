# Hermes–King Wen–J-Space Integration Blueprint
**Usage:** sovereign cognition loop implementation plan  
**Intent:** turn Hermes from user-inferred recall into reflexive capability ring gated by time-monitored coherence  
**Date:** 2026-07-21  
**Status:** planned, not yet executed

## Workstreams

### WS-01: J-Space Readout Adapter
**Task:** implement J-lens-inspired vector readout over session/ledger without model surgery  
**Owner:** agent  
**Dependencies:** none  
**Failure tail:** fallback to cosine similarity over `curated-session-extracts.jsonl`  
**Artifacts:**
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\routing\jspace_adapter.py`
- `reports/j-space/jacobian-lens-source-report.md`

### WS-02: King Wen Broadcast Selection
**Task:** implement `jspace_broadcast` top-K selection with domain-slot/phase/vector coverage  
**Owner:** agent  
**Dependencies:** WS-01  
**Failure tail:** fallback to fixed 64-hex expansion; no Gaussian smoothing if zero spread  
**Artifacts:**
- patch to `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\emotion\kingwen_engine_adapter.py`
- `reports/j-space/kingwen-mapping-report.md`

### WS-03: Reflexive Skill Ring Writer
**Task:** write rolling `reflexive-skills.jsonl` at session end; `session_id → triggered_skills → outcome_vector`  
**Owner:** agent  
**Dependencies:** WS-01  
**Failure tail:** fallback to existing `session-artifact-ledger.jsonl` schema  
**Artifacts:**
- `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\reflex\skill_ring_writer.py`
- `reports/hermes-cognition/session-ledger-report.md`

### WS-04: Capability-Based Curator
**Task:** add semantic merge policy on top of existing time-based curator; merge skill-weight vectors, discard raw text  
**Owner:** agent  
**Dependencies:** WS-03  
**Failure tail:** keep existing time-based curator unchanged if merge fails  
**Artifacts:**
- patch to `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\curator\merge_policy.py`
- `reports/hermes-cognition/session-ledger-report.md`

### WS-05: SOUL Live Index
**Task:** turn `SOUL.md` from static persona into live index pointing to active capability ring, dominant hexagram, skill weights  
**Owner:** agent  
**Dependencies:** WS-03  
**Failure tail:** keep static persona text; append index as YAML frontmatter only  
**Artifacts:**
- `C:\Users\krist\Desktop\OpenJarvis\SOUL.md` (patched in place)
- `reports/integration-comparison.md`

### WS-06: Journey Graph Enrichment
**Task:** extend `/journey` to output capability transitions, not just session→session edges  
**Owner:** agent  
**Dependencies:** WS-03, WS-05  
**Failure tail:** keep existing `/journey` output; append `capability_transitions` field only  
**Artifacts:**
- patch to `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\core\journey_executor.py`
- `reports/hermes-cognition/session-ledger-report.md`

### WS-07: Verification & Rollback
**Task:** py_compile + pytest + live consult probe for each workstream  
**Owner:** agent  
**Dependencies:** all above  
**Failure tail:** revert affected files from `.git` or known-good backup; do not leave partial state  
**Artifacts:**
- `C:\Users\krist\Desktop\OpenJarvis\VERIFICATION.md`

## Execution Order
WS-01 → WS-02 → WS-03 → WS-04 → WS-05 → WS-06 → WS-07

## Constraints
- Strict no-mock policy: zero stubs in `src/`
- Prefer minimal edits over rewrites
- All edits target `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\...`
- No alteration to `C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\`
- Failure tails must preserve existing behavior on error
- No push until user accepts state as shippable
