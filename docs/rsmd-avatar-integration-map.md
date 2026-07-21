# RSMD→KingWen Avatar Integration Map

> **Ground rule:** map only fields that exist in both systems. Where a requested
> concept has no source in this repo, it is marked **NOT PRESENT** instead of
> invented.

## 1. Sources read for this map

- `docs/oracle-voice-emotion-spec.md`
- `src/openjarvis/emotion/kingwen.py`
- `src/openjarvis/server/api_routes.py`
- `src/openjarvis/prompt/builder.py`

**Missing source:** `docs/rsmv-decoder-audit-2026-07-19.md` does not exist at the
path given in the task brief. Nothing in this map is inferred from that
nonexistent file.

## 2. King Wen avatar node shape

`/v1/kingwen/avatar/{session_id}` returns a fixed payload whose node-visual
surface is:

- `session_id`
- `hexagram_id`
- `hexagram_name`
- `unicode`
- `binary`
- `upper_trigram`
- `lower_trigram`
- `category`
- `action`
- `emotional_deltas`
- `reflections`
- `voice_preset`
- `oracle_console`
- `canonical_tick_ms`
- `avalokiteshvara_arm`
- `compassionate_observer`

These are the only deterministic fields that can be surfaced in an avatar node
today.

## 3. RSMD-style model identity → King Wen avatar fields

There is **no RSMD source** in this repo, but the closest standing "model
identity" substrate is the King Wen registry/weight model, because the codebase
uses `hexagram-registry.json` + `emotional-weights.json` + `temporal-reflections.json`
as the canonical identity table:

| King Wen source | Avatar node field | Notes |
|---|---|---|
| `hexagram-registry[hexagram_id].name` | `hexagram_name` | label |
| `hexagram-registry[hexagram_id].unicode` | `unicode` | glyph |
| `hexagram-registry[hexagram_id].binary` | `binary` | structural identity |
| registry-derived `upper_trigram` | `upper_trigram` | trigram identity |
| registry-derived `lower_trigram` | `lower_trigram` | trigram identity |
| `hexagram-registry[hexagram_id].category` | `category` | action class |
| `hexagram-registry[hexagram_id].action` | `action` | operational intent |

These map directly because the provider/API already derives them from the same
registry object.

## 4. Kit-mesh/score-like scoring → avatar visual properties

**NOT PRESENT as "kit-mesh"** anywhere in this repo.

Actual scoring infrastructure present in `kingwen.py`:
- `_compute_consensus()` produces `vectors_mean`, `vectors_median`,
  `vectors_mode`, `porosity_mean/median/mode`, and inject-site aggregates.
- `_resolve_emotion_tongue()` returns `training_weight_vectors`
  (`voiceWeight`, `coherence`, `chaos`, `whimsy`, `darkTone`, `porosity`).

Translatable into avatar visuals:

| Scoring substrate | Avatar visual property | Rule |
|---|---|---|
| `emotional_deltas.voiceWeight` | node intensity / size | mapped in `VOICE_PRESETS` speed + voice tier |
| `emotional_deltas.coherence` | node hue | high→warm/bodied, low→fractured |
| `emotional_deltas.chaos` | node edge noise | high→busy, low→clean |
| `emotional_deltas.whimsy` | node ornamentation | direct float |
| `emotional_deltas.darkTone` | node baseline shade | bass tilt |
| `emotional_tongue.porosity` | frame diffuseness | openness in display |
| `category` | node palette bucket | semantic color class |
| `action` | node icon/action badge | operational intent |

If a front-end gains a 2-D node renderer, these are the only scored dimensions
that have an upstream source today.

## 5. Cache-crossref → `session_context.actionable_paths`

**NOT PRESENT** as `session_context.actionable_paths` in this repo.

Current `session_context` is plain text only:

- `src/openjarvis/prompt/builder.py` declares `session_context: Optional[str]`
  and injects it verbatim into the prompt under `## Session Context`.

There is **no** `session_context` object, no dict with `actionable_paths`,
and no cache-crossref module in this workspace. Nothing can be mapped here.

## 6. Measured adhesion of `/v1/kingwen/avatar/{session_id}` to both systems

Fields present by construction on every call:
- All registry-derived identity fields (§2 + §3) ✅
- Weight-vector derived `emotional_deltas` and `reflections` ✅
- Voice preset ✅

Fields that are **not** currently produced by the avatar route:
- any `model_identity.rsmd` envelope ❌ — no source
- any `kit_mesh` score envelope ❌ — no source
- `session_context.actionable_paths` ❌ — no source

## 7. Interface contract summary

The only verifiable shared surface between "RSMD model-identity fields" and the
King Wen avatar today is the registry-weight payload already emitted by
`/v1/kingwen/avatar/{session_id}`.  Any expansion into RSMD kit-mesh or cache-
crossref concepts would require the missing `docs/rsmv-decoder-audit-2026-07-19.md`
and related source artifacts; they cannot be mapped without fabrication.
