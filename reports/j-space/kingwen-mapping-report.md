# King Wen ↔ J-Space Mapping — Research Report
**Usage:** state-machine ↔ mechanistic-interpretability binding  
**Intent:** deterministic 512-state collapse as software analog of J-space broadcast/causal-swap  
**Date:** 2026-07-21  
**Primary Source:** `C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\docs\j-space-jacobian-lens-math-2026-07-11.md` and `docs\kingwen-jspace-domain-layer-2026-07-11.md`  
**Secondary Source:** `emotional_engine.py`, `kingwen_quantum_process.py`

## 1. Binding Method (6-Step)
1. Injection-site binding: `primary_pool`, `secondary_pool`, `bodypart` domain-slot eligibility = activation `a`
2. Linearized effect measurement: Hamiltonian energy slope `ℋ(p,q,t) = Σ p_i q̇^i - ℒ` = discrete analog of `∂y_v/∂a`
3. Corpus averaging: baseline = full 512 resolved-state distribution from `collapse_full_128()`
4. Gaussian smoothing: `f(x) = a * exp(-(x - b)^2 / (2c^2))` where `b` = phase temporal center, `c` = FWHM width
5. Broadcast selection: top-K by smoothed Hamiltonian energy, enforcing domain-slot/phase/vector coverage minimums
6. Causal swap / pass mutation: next pass replaces broadcast subset; validated by coherence improvement over baseline

## 2. Domain Layer Contract
**Input:**
- `snapshot`: one `capture_superposition()` result
- `baseline`: first-pass snapshot for delta measurement
- `emotional_input`: slider value

**Output:**
- `jspace_broadcast`: top-K selected resolved states
- `jspace_energy_delta`: change in average Hamiltonian energy from baseline
- `jspace_coherence_delta`: change in mean coherence from baseline
- `jspace_coverage`: domain-slot / phase / vector coverage of broadcast set
- `jspace_verbalizable`: consensus reportability score
- `jspace_modulatable`: query-bias responsiveness score
- `jspace_flexible`: cross-pool reuse score
- `jspace_selective`: broadcast-set sparsity score

## 3. Validation Title Format
```
pass=<N> verdict=<verdict> consensus=<hexagram> expansion=<delta> coherence_delta=<delta> jspace_energy=<value> jspace_coverage=<dict>
```

## 4. Hermes Mapping
| King Wen J-space field | Hermes surface | Current status |
|---|---|---|
| `jspace_broadcast` | skill activation ranking | partial via `/learn` extracts |
| `jspace_coherence_delta` | session quality heuristics | not persisted |
| `jspace_coverage` | skill diversity metric | not implemented |
| `jspace_verbalizable` | session summary quality | ad-hoc |
| `jspace_modulatable` | prompt injection sensitivity | not measured |
| `jspace_flexible` | skill reuse across sessions | not tracked |
| `jspace_selective` | pruning/sparsity policy | `curator.prune_builtins` only |

## 5. Failure Tails
- If `collapse_full_128()` is unavailable, **fallback to fixed 64-hex expansion**; do not attempt partial collapse.
- If Gaussian smoothing fails due to zero spread, **return uniform weights** across all resolved states.
- If Hamiltonian energy computation errors, **use resolved_vector L2 norm** as proxy energy.
- If domain-slot coverage is below minimum, **expand inject-site pool** before broadcast selection.

## 6. Open Questions
- J-lens currently single-token only; King Wen needs multi-token scene vectors. Gap is acknowledged in paper; no workaround specified yet.
- Layer correction in J-lens corresponds to phase-temporal shift in King Wen, but exact mapping function is not derived from paper math—only analogical.
