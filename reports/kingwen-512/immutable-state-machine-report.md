# King Wen 512-State Machine — Source Research Report
**Usage:** deterministic cognitive collapse engine  
**Intent:** 64 hexagrams × 8 phases = 512 resolved states as agent state machine  
**Date:** 2026-07-21  
**Primary Source:** `C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\`

## 1. Core Architecture
- **States:** 512 = 64 hexagrams × 8 temporal phases
- **Collapse method:** full expansion then resolution, not single-hex selection
- **Slider:** `emotional_input` 0-100 modulates bleed factor across all 64 tables simultaneously
- **Output:** `expanded[]` (64), `resolved[]` (512), `top_10`, `selected`, `consensus_*`

## 2. Verified Counts
- Binary mode: 64 expanded, 512 resolved
- Ternary mode: 729 expanded, 5,832 resolved
- 27 trigrams in ternary expansion
- 64 canonical subset always present

## 3. Immutable Tables Source
- **Path:** `C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\`
- **Status:** read-only source of truth
- **Key files:** `emotional_engine.py`, `kingwen_quantum_process.py`, `king_wen_64_verified.json`, `data/emotional-weights.json`, `data/hexagram-registry.json`

## 4. Experimental Implementations Found
| File | Role | Status |
|---|---|---|
| `emotional_engine.py` `collapse_full_128()` | full expansion + resolution | verified 64/512 |
| `kingwen_quantum_process.py` | Hamiltonian energy, Gaussian kernel, pass-tracked superposition | verified |
| `scripts/build_512_widget.py` | standalone HTML generator | verified, 1.65 MB output |
| `DATASETS/kingwen_512_oracle_widget.html` | standalone widget | previously stub, regenerated with export buttons |
| OpenJarvis `kingwen_engine_adapter.py` | consult() + j_space_top_tokens | patched, unverified runtime |
| Megatron-LM-review `kingwen_dataset.py` | SampleMeta with j_space_component | patched, unverified |

## 5. Hermes Integration Points
| King Wen field | Hermes surface | Gap |
|---|---|---|
| `consensus_hexagram_id` | session artifact payload | partial |
| `emotional_input` | `/oracle` `/counsel` slider | wired in `_oracle_speak.py` |
| `j_space_top_tokens` | skill activation ranking | added to adapter, no consumer yet |
| `resolved_vector` | proactive context vector | not ingested |
| `phase_temporal` | session temporal tag | not persisted |

## 6. Failure Tails
- If `collapse_full_128()` raises, **fallback to `consult()` worker** at `kingwen-oracle.kristain33rs.workers.dev`
- If local tables drift from worker, **use worker `/consult` as canonical** until tables are reconciled
- If `j_space_top_tokens` exceeds Hermes context, **truncate to top-25 by coherence+porosity+phase bias**
- If immutable tables are edited accidentally, **restore from git history**; tables are source of truth

## 7. Workspace Constants
- Worker URL: `https://kingwen-oracle.kristain33rs.workers.dev`
- Worker binding: `AI` only
- Local expand server: `http://127.0.0.1:8765/expand`
- Slider range: 0-100
- Save-string format: `hex_id:phase:vw:ch:cc:wh:dt:porosity:timestamp:domain` (10 segments)
