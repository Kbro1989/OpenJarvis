# Hermes ↔ King Wen ↔ J-Space Integration Comparison
**Usage:** cross-system architecture evaluation  
**Intent:** identify exact gaps between source research and live Hermes/OpenJarvis/King-Wen surfaces  
**Date:** 2026-07-21  
**Sources:** reports/j-space/jacobian-lens-source-report.md, reports/j-space/kingwen-mapping-report.md, reports/hermes-cognition/session-ledger-report.md, reports/kingwen-512/immutable-state-machine-report.md

## 1. Layer Alignment

| Abstract Layer | J-Space Paper | King Wen Implementation | Hermes Surface | Status |
|---|---|---|---|---|
| Activation `a` | token-level activation | hexagram resolved state / inject-site | session payload / proactive context | partial |
| Token likelihood `y_v` | vocabulary logit | domain relevance score | skill activation ranking | partial |
| Jacobian `∂y_v/∂a` | linearized effect | Hamiltonian energy slope | not implemented | gap |
| Corpus averaging `E[...]` | many contexts | 512 resolved-state baseline | session-artifact-ledger | partial |
| Layer correction | representational change | phase-temporal shift | session timestamp / phase tag | partial |
| Sparse subframe | subset of activations | 64-hex subset of 512 | skill selection / curator | partial |
| Causal swap | vector swap changes output | pass mutation / superposition replacement | skill switch / persona change | not implemented |
| Broadcast hub | composes with weights | headmodel anchor + domain routing | skill graph / /journey | partial |

## 2. Hermes-Specific Gaps

### 2.1 Missing: Reflexive Skill Ring
- **Paper/J-space analog:** J-lens vectors that are "poised to be verbalized"
- **Hermes current:** skills are static trigger lists; proactive context is generic
- **Gap:** no rolling reflex arc that converts session outcomes into skill weights

### 2.2 Missing: Hamiltonian Energy Proxy
- **Paper/J-space analog:** `∂y_v/∂a` as linearized effect
- **Hermes current:** no continuous energy/slope measurement over sessions
- **Gap:** no way to measure how much a session "pushes toward" a skill/outcome

### 2.3 Missing: Causal Swap Validation
- **Paper/J-space analog:** swapping J-lens vector changes output
- **Hermes current:** skills can be swapped, but no A/B validation of swap effect
- **Gap:** no mechanism to validate that skill replacement improved coherence

### 2.4 Missing: Multi-Token Concept Binding
- **Paper/J-space analog:** single-token limitation acknowledged
- **Hermes current:** scene-level artifacts require multi-token vectors
- **Gap:** no concatenation or positional marker scheme for multi-token concepts

### 2.5 Missing: Layer Correction Mapping
- **Paper/J-space analog:** layer correction for representational changes
- **Hermes current:** no layer/supervision analog in session processing
- **Gap:** phase-temporal shift is used, but not derived from paper math

## 3. King Wen-Specific Gaps

### 3.1 Verified: Full 512-State Expansion
- `collapse_full_128()` returns 64 expanded + 512 resolved
- Binary mode verified; ternary mode returns 729/5832
- **Status:** complete and deterministic

### 3.2 Partial: J-Space Top-K
- `j_space_top_tokens` added to OpenJarvis `kingwen_engine_adapter.py`
- Returns top-25 by coherence + porosity + phase alignment bias
- **Gap:** no downstream consumer in Hermes skill activation or proactive context

### 3.3 Partial: Emotional Input Slider
- `emotional_input` penetrates `collapse_full_128()`
- Wired into `_oracle_speak.py` and `chat_cmd.py`
- **Gap:** slider value source is stdin; no integration with session difficulty/complexity

### 3.4 Missing: Broadcast Selection
- Domain layer contract specifies `jspace_broadcast`, `jspace_coverage`, etc.
- **Gap:** no implementation of broadcast selection with domain-slot/phase/vector coverage minimums

## 4. Systems Evaluation

### 4.1 Data Flow Health
```
Session → Ledger → Cluster Seeds → /journey → Skills → Proactive Context → LLM
```
- **Health:** functional but not reflexive
- **Bottleneck:** `/journey` only fires on user query; no background reflex loop
- **Bottleneck:** proactive context is generic, not skill-weighted

### 4.2 State Coherence
- `CanonicalClock` exists in POG2 but is not integrated into Hermes session timestamps
- King Wen phase-temporal is present in adapter but not persisted in session ledger
- **Risk:** temporal misalignment between Hermes sessions and King Wen phases

### 4.3 Skill Hygiene
- `curator` is time-based (`interval_hours`, `stale_after_days`)
- No capability-based merge or decay
- **Risk:** hoarding of unused skills; no automatic capability distillation

### 4.4 Memory Limits
- `memory_char_limit`: 220M chars
- `user_char_limit`: 13.75M chars
- Current usage: well below limits
- **Opportunity:** room for reflexive skill ring without hitting compression threshold

## 5. Failure Tails (Integrated)

### 5.1 If J-Space Computation Unavailable
- **Fallback:** cosine similarity over recent session embeddings from `curated-session-extracts.jsonl`
- **No fabrication:** do not invent J-lens vectors; use real session artifacts

### 5.2 If King Wen Tables Drift
- **Fallback:** worker `/consult` at `kingwen-oracle.kristain33rs.workers.dev` as canonical
- **No local collapse:** disable `collapse_full_128()` until tables reconciled

### 5.3 If Session Ledger Corrupts
- **Fallback:** raw file glob of `sessions/` sorted by mtime
- **Recovery:** rebuild ledger from session dumps; do not restore from backup if backup contains bad paths

### 5.4 If Skill Activation Ranking Fails
- **Fallback:** alphabetical/skill-snapshot order; no learning loop until recovery
- **Preserve:** existing manual skill selection via `/tools` or slash commands

### 5.5 If Proactive Context Ingest Fails
- **Fallback:** last successful proactive context payload cached in `cache/proactive-learning-context.jsonl`
- **Recovery:** re-ingest from session ledger tail on next turn

## 6. Workspace Constants (Canonical)
- Hermes home: `C:\Users\krist\AppData\Local\hermes\`
- Hermes sessions: `C:\Users\krist\AppData\Local\hermes\sessions\`
- OpenJarvis runtime: `C:\Users\krist\Desktop\OpenJarvis\src\openjarvis\`
- King Wen tables: `C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\`
- King Wen worker: `https://kingwen-oracle.kristain33rs.workers.dev`
- Worker binding: `AI` only
- Local expand server: `http://127.0.0.1:8765/expand`
- Save-string format: `hex_id:phase:vw:ch:cc:wh:dt:porosity:timestamp:domain`
- Hermes config: `C:\Users\krist\AppData\Local\hermes\config.yaml`
- Hermes SOUL: `C:\Users\krist\AppData\Local\hermes\SOUL.md`
- Hermes memory limit: 220M chars
- Hermes user limit: 13.75M chars
- Hermes max turns: 273,000
- Hermes compression threshold: 0.9
- Hermes compression target: 0.7

## 7. Decision Points
1. **Reflex arc placement:** write reflex arcs to `cache/reflexive-skills.jsonl` or extend `session-artifact-ledger.jsonl`?
2. **Hamiltonian proxy:** implement full Hamiltonian energy, or use resolved_vector L2 norm as fallback?
3. **Broadcast selection:** implement in Hermes or delegate to King Wen engine?
4. **Curator policy:** replace time-based curation with capability-based curation entirely, or add semantic merge on top of existing time rules?
5. **Multi-token binding:** concatenate single-token J-lens vectors with positional markers, or wait for paper advancement?
