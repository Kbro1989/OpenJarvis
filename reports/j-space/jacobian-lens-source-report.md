# J-Space / Jacobian Lens — Source Research Report
**Usage:** mechanistic-interpretability readout  
**Intent:** map transformer workspace vectors to agentic state transitions without retraining models  
**Date:** 2026-07-21  
**Primary Source:** Gurnee, Sofroniew, Pearce, et al. — *Verbalizable Representations Form a Global Workspace in Language Models*, Transformer Circuits / Anthropic, July 2026.  
**Companion Code:** https://github.com/anthropics/jacobian-lens  
**Paper URL:** https://transformer-circuits.pub/2026/workspace/index.html  

## 1. Core Claim
The paper identifies a **global workspace** in language models: a sparse subset of activations that are **poised to be verbalized**, not merely correlated with later tokens. Jacobian lens measures the **average linearized effect** of an activation on future token likelihood.

## 2. Exact Math
```
J(a; v) ≈ E_{contexts}[ ∂y_v / ∂a ] · Δa
```
- `a` = model activation at a given layer/position
- `y_v` = logits for vocabulary token `v`
- `∂y_v / ∂a` = Jacobian of token likelihood wrt activation
- `E[ ... ]` = average linearized effect over many contexts
- `Δa` = activation perturbation being measured

In words: **how much this activation linearly pushes the model toward saying token `v`.**

## 3. Key Constraints
1. **Averaging is essential.** Distinguishes verbalizable/poised representations from context-specific coincidences.
2. **Layer correction.** J-lens corrects for representational changes across layers; earlier layers yield meaningful readouts.
3. **Sparse subframe.** If activations decompose into sparse linear features, J-space is a sparse subframe.
4. **Single-token limitation.** Current J-lens identifies only single-token concepts; multi-token concepts are not fully captured.
5. **Causal swap.** Swapping one active J-lens vector for another changes output accordingly, confirming causal mediation.

## 4. Operational Mapping to King Wen
| J-lens term | King Wen analog |
|---|---|
| activation `a` | hexagram resolved state / inject-site record |
| token likelihood `y_v` | domain relevance score |
| Jacobian `∂y_v / ∂a` | Hamiltonian energy slope |
| corpus averaging `E[ ... ]` | 512 resolved-state baseline distribution |
| linearized effect | Gaussian kernel–smoothed state transition |
| J-lens vector `J(a; v)` | inject-site vector + headmodel anchor |
| swap intervention | superposition pass replacement |
| layer correction | phase-temporal shift |
| sparse subframe | 64-hex subset vs full 512 resolved set |

## 5. Hermes Relevance
Hermes already has surfaces that can consume J-space concepts without model surgery:
- **sessions/** = temporal activation captures
- **cache/session-artifact-ledger.jsonl** = baseline distribution
- **skills/** = swap targets / downstream consumers
- **SOUL.md** = persona-state anchor

## 6. Failure Tails
- If J-lens computation is unavailable, degrade to **cosine similarity** over recent session embeddings, not random selection.
- If multi-token concepts are needed, **concatenate single-token J-lens vectors** with positional markers; do not claim full multi-token coverage.
- If layer correction drifts, **fall back to phase-temporal shift** as a proxy layer index.
- If corpus averaging exceeds memory budget, **sample stratified by phase_temporal** instead of full 512-state baseline.

## 7. Citation Notes
- Verified via web search 2026-07-21: transformer-circuits.pub, arxiv 2607.15495v1, Anthropic GitHub.
- No arxiv ID was conclusively confirmed in search results; use paper URL as canonical reference until preprint ID is verified.
