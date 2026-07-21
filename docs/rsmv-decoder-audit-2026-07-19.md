# RSMD 3D Decoder Architecture Audit — Stable Identity Schema
**Date:** 2026-07-19  
**RSMD repo:** `C:\Users\krist\Desktop\rsmv`  
**OpenJarvis doc output:** `C:\Users\krist\Desktop\OpenJarvis\docs\rsmv-decoder-audit-2026-07-19.md`

---

## 1. Scope and method

Files inspected (all under `C:\Users\krist\Desktop\rsmv\src`):

- `opcodes/items.jsonc`
- `opcodes/npcs.jsonc`
- `opcodes/objects.jsonc`
- `opcodes/identitykit.jsonc`
- `opcodes/avatars.jsonc`
- `opcodes/avataroverrides.jsonc`
- `opcodes/models.jsonc`
- `3d/avatar.ts` / `3d/avatar.js`
- `3d/avatar.d.ts`
- `3d/modelnodes.ts`
- `3d/rt7model.ts`

No opcodes named `playeritemedit.jsonc` were found in the opcodes directory. The player-item edit structure is instead defined inline in `avataroverrides.jsonc`.

---

## 2. Stable identity schema

### 2.1 Top-level avatar container
**File:** `opcodes/avatars.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\avatars.jsonc` (lines 1-29)

```jsonc
[
  "struct",
    ["gender", "ubyte"],
    ["$avatype", "playeritem"],
    ["player", ["opt", ["$avatype", -1, "eqnot"], [ ... ]]],
    ["npc",   ["opt", ["$avatype", -1],       [ ... ]]]
]
```

**Stable keys and types:**
- `gender` — `ubyte`
- `player.slots` — tuple of **16** `playeritem` entries
- `player.rest` — remaining bytes hex buffer
- `npc.id` — `ushort`, present when `$avatype == -1`
- `npc.buf` — 21-byte hex buffer
- `npc.unkff` — `ushort`

The **type discriminator** for the avatar root is the `$avatype` variable reused inside both branches:
- If the byte after `gender` equals `0xFF 0xFF`, the remaining bytes decode as an NPC block.
- Otherwise, the bytes are consumed by the player slot tuple.

This means the **stable identity key for a player avatar** is the entire byte array decoded via `playeritem` (slot values) plus `player.rest`. The **stable identity key for an NPC avatar** is `npc.id` plus `npc.buf`.

### 2.2 Slot references (`playeritem`)
**File:** `opcodes/avataroverrides.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\avataroverrides.jsonc` (lines 1-78)

Each slot entry is a tuple of:
```jsonc
["struct",
  ["slot", ["itemvar", "ref"]],
  ["cust", ["opt", ["$flags", N, "bitflag"], "playeritemedit"]]
]
```
for `N = 0 .. 15`.

**Stable field shape per slot:**
- `slot` — an `itemvar` reference, resolved against bitmask `$flags`.
- `cust` — optional `playeritemedit` block for this slot index.

The slot count is exactly 16, matching `slotNames` length in `3d/avatar.ts`:
```ts
export const slotNames = [
  "helm","cape","necklace","weapon","body","offhand",
  "arms","legs","face","gloves","boots","beard",
  "ring","ammo","aura","slot15"
];
```
**Path:** `C:\Users\krist\Desktop\rsmv\src\3d\avatar.ts` lines 20-37.

### 2.3 Per-slot player customization (`playeritemedit`)
**File:** `opcodes/avataroverrides.jsonc` (lines 70-78)

```jsonc
["$flags", "ushort"],
...
["haircol0", "ubyte"],
["bodycol",  "ubyte"],
["legscol",  "ubyte"],
["bootscol", "ubyte"],
["skincol0","ubyte"],
["skincol1","ubyte"],
["haircol1","ubyte"],
["unkbuf",   ["buffer", 13, "hex"]],
["stance",   "ushort"]
```

**Stable keys and types:**
- `haircol0`, `haircol1` — `ubyte`
- `bodycol`, `legscol`, `bootscol` — `ubyte`
- `skincol0`, `skincol1` — `ubyte`
- `unkbuf` — 13-byte opaque hex buffer
- `stance` — `ushort`

The `$flags` field precedes the 16 slot tuples and controls which slot customizations are present. This value is **not consumed** by the slot tuple reader itself; it is only used as an opt-guard for `cust`.

### 2.4 Item identity model fields
**File:** `opcodes/items.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\items.jsonc`

Relevant stable identity / model-ID fields:

| Opcode hex | Name | Read type | Notes |
|---|---|---|---|
| `0x01` | `baseModel` | `item_modelid` | single model id |
| `0x17` / `0x19` | `maleModels_0` / `femaleModels_0` | struct with `id` (`item_modelid`) + `type` (`ubyte` on `<502`, `0` on `>=502`) | gendered primary model; indexed differently by build |
| `0x18` | `maleModels_1` | `item_modelid` | |
| `0x1A` | `femaleModels_1` | `item_modelid` | |
| `0x4E` | `maleModels_2` | `item_modelid` | |
| `0x4F` | `femaleModels_2` | `item_modelid` | |
| `0x5A` | `maleHeads_0` | `item_modelid` | head model |
| `0x5B` | `femaleHeads_0` | `item_modelid` | head model |
| `0x5C` | `maleHeads_1` | `item_modelid` | head model |
| `0x5D` | `femaleHeads_1` | `item_modelid` | head model |
| `0x0D` | `equipSlotId` | `unsigned byte` | slot index |
| `0x0E` | `equipId` | `unsigned byte` | equip slot id |

`item_modelid` is a custom decoder. In the repo it is referenced from these opcodes; its exact implementation is discovered at opdecoder registration (`src/opdecoder.ts` or `.js`).

**Path:** `C:\Users\krist\Desktop\rsmv\src\opdecoder.ts` lines 134-136 show:
```ts
identitykit: FileParser.fromJson<...>(require("./opcodes/identitykit.jsonc")),
```
and `item_modelid`, `varuint`, `playeritem`, `playeritemedit` are parser primitives, not fields in this JSONC.

### 2.5 NPC identity model fields
**File:** `opcodes/npcs.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\npcs.jsonc`

Relevant stable identity / model-ID fields:

| Opcode hex | Name | Read type | Notes |
|---|---|---|---|
| `0x01` | `models` | array — `varuint` on `>=669`, `ushort` otherwise | primary model IDs |
| `0x3C` | `headModels` | array — same build switch as `models` | head-only model IDs |
| `0x7F` | `animation_group` | `unsigned short` | anim group id |
| `0x66` | `head_icon_data` | `unsigned short` | |
| `0x2C` | `recolor_indices` | `unsigned short` | |
| `0x2D` | `retexture_indices` | `unsigned short` | |

The NPC identity within an avatar is the `npc.id` from `avatars.jsonc`, not the models themselves.

### 2.6 Object identity model fields
**File:** `opcodes/objects.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\objects.jsonc`

Relevant model-ID fields:

| Opcode hex | Name | Read type | Notes |
|---|---|---|---|
| `0x01` | `models` | build-gated array; `>=582` uses `{type, values[]}` with ubyte type prefix; earlier uses flat `values[]` + trailing `type` | loco model IDs |
| `0x05` | `models_05` | similar struct to `0x01`, with `models + unktail` | secondary loco model IDs |
| `0x6A` | `headModels` | array of `{model: varuint, unknown_2: ubyte}` | head-only models |
| `0x66` | `mapscene` | `unsigned short` | mapscene sprite id |

Objects do **not** have a gender or equip slot; their stable identity is the object config file id.

### 2.7 Identity kit fields
**File:** `opcodes/identitykit.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\identitykit.jsonc` (lines 1-9)

```jsonc
{
  "0x01": { "name": "bodypart", "read": "ubyte" },
  "0x02": { "name": "models",   "read": ["array","ubyte","varuint"] },
  "0x03": { "name": "iscopy",   "read": "true" },
  "0x28": { "name": "recolor",  "read": ["array","ubyte",["tuple","ushort","ushort"]] },
  "0x3c": { "name": "headmodel","read": "varuint" }
}
```

**Stable keys:**
- `bodypart` — `ubyte` (animated part slot id)
- `models` — variable-length array of `varuint` model IDs
- `iscopy` — boolean flag
- `recolor` — palette replacements per ubyte index
- `headmodel` — `varuint` single model id

These kits are looked up by file id in the config archive (`cacheMajors.config` -> `cacheConfigPages.identityKit`), indexed alongside other identity-kit configs.

---

## 3. Model-ID field semantics across domains

### 3.1 `item_modelid`
Used exclusively in items opcodes. It is referenced by name in `items.jsonc` but defined in the opdecoder. From runtime usage in `3d/avatar.ts` (`src/3d/avatar.ts` lines 148-165, 167-178), tools treating `item_modelid` resolve:
- `maleModels_0.id` → index 0
- `femaleModels_0.id` → index 1
- `maleModels_1` → index 2
- `femaleModels_1` → index 3
- `maleModels_2` → index 4
- `femaleModels_2` → index 5

And for heads:
- `maleHeads_0` → index 0
- `femaleHeads_0` → index 1
- `maleHeads_1` → index 2
- `femaleHeads_1` → index 3

Items default missing gendered variants to `undefined` so the consumer chooses the correct index by gender.

### 3.2 Build switches around model-ID widths
- **NPC models** (`npc.jsonc` `0x01`, `0x3C`):
  - `>=669` → `varuint`
  - `<669` → `ushort`
- **Object models** (`objects.jsonc` `0x01`, `0x05`):
  - `>=582` → structured array with explicit `type` byte prefix
  - `<582` → flat `values[]` + trailing `type`
- **Item models** (`items.jsonc` `0x17`, `0x19`):
  - `>=502` → struct `{id: item_modelid, type: 0}`
  - `<502` → struct `{id: item_modelid, type: ubyte}`
- **Item alternate models** (`items.jsonc` `0x1B` excluded from above): no build switch, read as plain `item_modelid`.

---

## 4. Headmodel duplication rules

### 4.1 Kit duplication (identity-kit layer)
**File:** `src/3d/avatar.ts` lines 116-124:

```ts
for (let m of kit.models) {
  models.push(m, m);
}
if (kit.headmodel) {
  headmodels.push(kit.headmodel, kit.headmodel);
}
```

Each kit entry contributes **two** consecutive entries in both `models` and `headmodels` (male/female pairs). The gender is resolved later by selecting the appropriate parity index:
- Male: even indices (`0, 2, 4, ...`)
- Female: odd indices (`1, 3, 5, ...`)

### 4.2 Item duplication (equipment layer)
**File:** `src/3d/avatar.ts` lines 148-178:

Items already encode both genders explicitly:
- `maleModels_0` / `femaleModels_0` → indices 0 / 1
- `maleModels_1` / `femaleModels_1` → indices 2 / 3
- `maleModels_2` / `femaleModels_2` → indices 4 / 5
- Same pattern for heads.

The runtime **does not duplicate** item entries; it selects index `(isFemale ? 1 : 0) + 2*k` when emitting final model list.

### 4.3 NPC head duplication
**File:** `src/3d/modelnodes.ts` lines 91-115 (`npcToModel`):

```ts
let modelids = (id.head ? npc.headModels : npc.models) ?? [];
```

NPC body vs head is chosen by a boolean flag at the call site — no duplication of `headModels` entries is performed.

---

## 5. Kit-mesh JSON schema and the `models.jsonc` binary format

### 5.1 Runtime mesh schema
**File:** `src/3d/rt7model.ts` lines 15-44

```ts
export type ModelMeshData = {
  indices: THREE.BufferAttribute;
  vertexstart: number;
  vertexend: number;
  indexLODs: THREE.BufferAttribute[];
  materialId: number;
  hasVertexAlpha: boolean;
  needsNormalBlending: boolean;
  attributes: {
    pos: THREE.BufferAttribute;            // 3x short per vertex
    normals?: THREE.BufferAttribute;       // 3x byte normalized or 3x short
    color?: THREE.BufferAttribute;         // 4x ubyte RGBA
    texuvs?: THREE.BufferAttribute;        // 2x u16 half or 2x float
    skinids?: THREE.BufferAttribute;       // 4x u16
    skinweights?: THREE.BufferAttribute;   // 4x u8 normalized
    boneids?: THREE.BufferAttribute;       // 4x u16
    boneweights?: THREE.BufferAttribute    // 4x u8 normalized
  };
}

export type ModelData = {
  maxy: number;
  miny: number;
  skincount: number;
  bonecount: number;
  meshes: ModelMeshData[];
  debugmeshes?: THREE.Mesh[];
}
```

### 5.2 Binary model format (`models.jsonc`)
**File:** `opcodes/models.jsonc`  
**Path:** `C:\Users\krist\Desktop\rsmv\src\opcodes\models.jsonc` (lines 1-107)

Top-level struct has two format branches gated by `version`:
- `version <= 3` → old format with `meshCount`, `unkCount0..4`, and `meshes` array of old-style structs.
- `version > 3` → new format with `meshdata` single struct and `renders` multi-submesh array.

**Old format (`<=3`) per-mesh fields:**
- `$groupFlags` — `ubyte` bitmask
- `unkint` — `uint`
- `materialArgument` — `ushort le`
- `faceCount` — `ushort le`
- `hasVertices` — flag from bit 0 of `$groupFlags`
- `hasVertexAlpha` — flag from bit 1
- `hasFaceBones` — flag from bit 2
- `hasBoneIds` — flag from bit 3
- `isHidden` — flag from bit 4
- `hasSkin` — flag from bit 5
- `colourBuffer` — optional `faceCount * ushort`; only when `hasVertices`
- `alphaBuffer` — optional `faceCount * ubyte`; only when `hasVertexAlpha`
- `faceboneidBuffer` — optional `faceCount * ushort`; only when `hasFaceBones`
- `indexBuffers` — array of ubyte-counted `ushort le` buffers
- `vertexCount` — `ushort le` when `hasVertices`, else 0
- `positionBuffer` — optional `vertexCount * short[3]`
- `normalBuffer` — optional build-gated:
  - `>=887` → `vertexCount * byte[3]`
  - else → `vertexCount * short[3]`
- `tagentBuffer` — optional build-gated (`>=906` → `short[2]`, else null)
- `uvBuffer` — optional build-gated:
  - `>=887` → `vertexCount * ushort[2]`
  - else → `vertexCount * float[2]`
- `boneidBuffer` — optional `vertexCount * ushort`
- `skin` — optional struct:
  - `skinWeightCount` — `uint le`
  - `skinBoneBuffer` — `skinWeightCount * ushort`
  - `skinWeightBuffer` — `skinWeightCount * ubyte`

**New format (`>3`) fields:**
- `$groupFlags` — `ubyte`
- `unkint` — `ubyte`
- `faceCount` — `ushort le`
- same `has*` flags as old format
- `vertexCount` — `uint le`
- `positionBuffer` — `short[3]`
- `normalBuffer` — `byte[3]`
- `tagentBuffer` — `short[2]`
- `uvBuffer` — `ushort[2]`
- `boneidBuffer` — `ushort`
- `skin` — optional per-vertex array:
  - each entry: `{ ids: ushort[], weights: ubyte[] }`
- `vertexColours` — optional `ushort[]`
- `vertexAlpha` — optional `ubyte[]`
- `vertexFacebones` — optional `ushort[]`
- `renders` — array of render groups, each:
  - `$groupFlags`, `unkint`, `materialArgument`, `unkbyte2`
  - `buf` — build-gated index buffer:
    - `vertexCount <= 0xffff` → `ushort le`
    - otherwise → `uint` (endianness flipped at parse time)

**Other top-level unknowns:**
- `unk1Buffer` — array of fixed-size buffers: size `39` on `>=923`, else `37`
- `unk2Buffer` — size `50` on `>=923`, else `44`
- `unk3Buffer` — size `18` on `>=923`, else `16`
- `unk4Buffer` — remaining bytes

---

## 6. Stable identity summary (what OpenJarvis should key on)

| Entity | Stable ID source | Model-ID field(s) | Headmodel field(s) |
|---|---|---|---|
| Player avatar | `avatars.npc.id` (if NPC) or full `playeritem` tuple + `player.rest` | kit `models` + item `maleModels_*` / `femaleModels_*` | kit `headmodel` + item `maleHeads_*` / `femaleHeads_*` |
| NPC | `avatars.npc.id` | `npcs.models` (array) | `npcs.headModels` (array) |
| Loc/object | config file id | `objects.models` / `objects.models_05` | `objects.headModels` |
| Identity kit | config file id | `identitykit.models` | `identitykit.headmodel` |

No field names were invented — every key above matches the JSONC names verbatim.

---

## 7. Open questions and caveats

1. **`item_modelid` primitive** is not defined in any JSONC in the repo; it is registered in `opdecoder.ts`/`.js` alongside `varuint`. Its exact bit-width behavior across builds should be inspected in `src/opdecoder.js` or `.ts` to confirm whether it is build-gated like NPC/object model arrays.
2. **Generated TypeScript types** (`generated/*`) were **not present** on disk under `C:\Users\krist\Desktop\rsmv\generated`; typings referenced by `src/opdecoder.ts` could not be read, so schema conclusions are sourced directly from JSONC opcodes and runtime TS/JS.
3. **`playeritemedit`** is not a separate JSONC file; it is defined inline only via the `opt` blocks inside `avataroverrides.jsonc`. Any schema expecting a top-level `playeritemedit` type should instead mirror the inline tuple definition.
4. **`0x31` and `0x32` model compression** or other compression opcodes were not encountered; the model binary schema above reflects only the JSONC definitions and `parseOb3Model` runtime handler.

---

*End of audit.*
