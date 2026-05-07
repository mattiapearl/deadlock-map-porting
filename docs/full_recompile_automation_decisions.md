# Full-source CS2 map -> Deadlock automation decisions

Date: 2026-05-07

The `bhop_soulscape` success proves the process can be headless and scriptable. The correct next step is to turn the map-specific script into a generic batchable converter, while keeping failure classification strict and explicit.

Recommended tool target:

```txt
tools/full_recompile_workshop_map.py \
  --workshop-root C:/Code/deadlock-map-porting/new_workshop_maps/3605179998 \
  --map bhop_soulscape \
  --addon bhop_soulscape_full_recompile \
  --install-pak pak72_dir.vpk
```

Outputs per run:

```txt
work/full_recompile_<map>/
logs/compile_<addon>_*.log
reports/full_recompile_<map>_<timestamp>.md
exports/<map>_full_recompile_<timestamp>_dir.vpk
optional live backup + installed pak
```

## 1. Material rewrite rules

### Problem

Unsupported CS2 shaders cannot be left active in Deadlock/CSDK:

```txt
csgo_complex.vfx
csgo_static_overlay.vfx
csgo_glass.vfx
csgo_water_fancy.vfx
csgo_lightmappedgeneric.vfx
csgo_moondome.vfx
```

Even if shader VPKs are mounted, these are not reliable runtime targets. They must be rewritten before compile.

### Recommended deterministic rule set

Use a table-driven material converter. First preserve original VMAT as `*.bak`, then emit a known Deadlock-compatible VMAT.

#### Generic opaque materials

For:

```txt
csgo_lightmappedgeneric.vfx
csgo_complex.vfx
csgo_static_overlay.vfx
csgo_simple.vfx
unknown csgo_* opaque shaders
```

Rewrite to:

```txt
pbr.vfx
```

Texture selection priority:

1. `TextureColor`
2. `TextureLayer1Color`
3. `g_tColor`
4. first plausible color/base/albedo texture parameter
5. `materials/default/default_color.tga`

Minimal output:

```kv2
"Layer0"
{
    "shader" "pbr.vfx"
    "TextureColor1" "<selected color texture>"
}
```

Optional later improvement:

- preserve normal maps into PBR normal/roughness if parameter names are known
- preserve self-illum for glowing materials:

```kv2
"F_UNLIT" "1"
"F_SELF_ILLUM" "1"
"TextureSelfIllumMask1" or "g_tSelfIllumMask"
```

Decision: **implement minimal PBR first**, then add feature-preserving enrichments after batch success rate is good.

#### Glass

For:

```txt
csgo_glass.vfx
```

Rewrite to:

```txt
pbr.vfx + F_GLASS + TextureGlassMask1
```

If no glass mask exists, use a generated/default white or grey mask. Preserve `TextureColor` when available.

Decision: **separate glass rule**, not generic PBR, because glass readability/collision expectations are different.

#### Water

For:

```txt
csgo_water_fancy.vfx
```

Initial safe rule:

```txt
pbr.vfx, optionally translucent/glass-like if compile-tested
```

Do not attempt to preserve Source 2 CS2 water behavior in first automation pass. If it fails or looks bad, mark as `water_degraded` in report.

Decision: **degrade safely, report loudly**.

#### Sky/moondome

For:

```txt
csgo_moondome.vfx
sky.vfx with missing/non-cubemap source
```

Handle in skybox subsystem, not generic material subsystem.

### Compile validation loop

For every rewritten VMAT:

1. compile individually
2. on failure, parse log
3. classify:
   - unsupported shader remains
   - missing texture source
   - invalid texture type/cubemap
   - unknown material compiler failure
4. apply only deterministic fallback rules
5. record final rule used in report

## 2. Skybox handling

### Problem

VRF often decompiles CS2 skies into face textures while the VMAT points to a logical cubemap name that does not exist as a compileable CSDK source. Example failure:

```txt
Unable to read file ... materials/skybox/skybox.png
Error reading texture ... for "SkyTexture"
```

### Recommended two-tier strategy

#### Tier A: Try to preserve original sky when clearly compileable

If the VMAT uses `sky.vfx` and `SkyTexture` points to an existing source that compiles as required, keep it.

If the VMAT references a missing logical name but VRF emitted cubemap faces, try deterministic reconstruction only if known safe:

```txt
*_ft.png
*_bk.png
*_lf.png
*_rt.png
*_up.png
*_dn.png
```

But do not block the map on this in initial automation.

#### Tier B: Fallback to known Deadlock sky

Fallback VMAT:

```kv2
"Layer0"
{
    "shader" "sky.vfx"
    "g_flBrightnessExposureBias" "-1"
    "g_flRenderOnlyExposureBias" "0"
    "SkyTexture" "materials/skybox/sky_dl_dusk03_exr_9dd50fb1.png"
}
```

Known successful texture:

```txt
materials/skybox/sky_dl_dusk03_exr_9dd50fb1.png
```

Decision: **default automation should use fallback sky after one failed preserve attempt**. Geometry/playability and lighting validity are higher priority than exact sky fidelity.

Report fields:

```txt
sky_original_material
sky_original_texture
sky_preserve_attempted: true/false
sky_preserve_result: compiled/failed/skipped
sky_fallback_used: true/false
```

## 3. Entity patch insertion

### Problem

CS2 maps usually lack Deadlock-specific spawn/runtime shell entities. Deadlock can load the world but player spawning/game state may fail or be wrong.

### Recommended entity shell

Minimum shell proven useful:

```txt
point_servercommand targetname=panel
logic_auto OnMapSpawn -> panel.Command(<bhop cvar command string>)
info_team_spawn teamnumber=2
info_team_spawn teamnumber=3
info_team_spawn teamnumber=4
info_teleport_destination targetname=stage1
```

Optional shell, from preserve-port experiments, should be feature-gated:

```txt
info_target_server_only
rebels_vanguard_spawn
combine_vanguard_spawn
bhop_course_start
citadel_minimap_boundary
citadel_trigger_suspend_modifier
```

Decision: **keep the full-source default shell minimal until runtime evidence says more is required**. Extra unsupported keys/classes can create new error classes.

### Robust origin detection

Use this ordered detection policy:

1. `info_teleport_destination` with targetname matching:
   ```txt
   Start, start, stage1, Stage1, map_start, MapStart, bonus_start
   ```
2. any `info_teleport_destination` whose targetname contains:
   ```txt
   start, stage, spawn
   ```
3. first `info_player_terrorist` or `info_player_counterterrorist`
4. first `info_player_start`
5. compute world bounds from mesh/entity origins and choose:
   - center X/Y
   - low-but-not-min Z, e.g. P5/P10 Z + 64
6. final fallback:
   ```txt
   0 0 128
   ```

The report must record which method selected the origin.

### KV2 insertion method

Current successful method:

1. `dmxconvert` binary VMAP -> KeyValues2 text
2. append top-level `CMapEntity` blocks
3. add their element IDs to first `CMapWorld.children` array
4. `dmxconvert` KeyValues2 -> binary VMAP

Decision: **keep text KV2 patching** for now. It is ugly but deterministic and proven.

## 4. Bad decompile artifacts

### Problem

VRF can emit aggregate prop_static proxy entities that duplicate reconstructed Hammer/world geometry. `bhop_soulscape` and `bhop_rose` both had this pattern.

Example removed from soulscape:

```txt
prop_static model = maps/bhop_soulscape/worldnodes/n0_lr0_c2_s_cb_mesh.vmdl
entity id = 056fd23f-6b65-419b-90f8-059e91b34a51
```

### Detection rule

Remove top-level `CMapEntity` if all are true:

1. `classname == prop_static`
2. model path matches:
   ```txt
   maps/<map>/worldnodes/*_cb_mesh*.vmdl
   maps/<map>/worldnodes/*agg*.vmdl
   maps/<map>/n0_lr*_cb_mesh*.vmdl
   ```
3. model is a generated/decompiled worldnode aggregate, not a custom gameplay prop
4. equivalent `CMapMesh`/worldnode geometry exists in the VMAP or source tree

### Safety rules

Do not remove:

```txt
prop_dynamic
prop_physics
prop_static with custom model paths outside maps/<map>/worldnodes
props with targetnames/connections/gameplay inputs
```

Decision: **auto-remove high-confidence aggregate proxies, report low-confidence candidates only**.

Report fields:

```txt
removed_aggregate_prop_static_count
removed_ids
candidate_not_removed_count
candidate_not_removed_reasons
```

## 5. Memory cap failures

### Problem

`bhop_soulscape` compiled under the 24 GiB cap. `bhop_rose` reached approximately 24.23-25.01 GiB and was killed by the wrapper. We should not silently bypass the cap.

### Required classification

Every map compile run should classify final state as one of:

```txt
SUCCESS
FAILED_UNSUPPORTED_SHADER
FAILED_MISSING_RESOURCE
FAILED_ENTITY_PATCH
FAILED_MALFORMED_VMAP
FAILED_MEMORY_CAP
FAILED_TIMEOUT
FAILED_UNKNOWN_COMPILER
```

Memory failure detector:

```txt
[memlimit] killing process tree: <N> GiB > 24.0 GiB
[memlimit] peak observed: <N> GiB
```

### Fallback strategies

#### Strategy 0: Do not bypass cap by default

Default behavior remains hard fail at 24 GiB and report `FAILED_MEMORY_CAP`.

Decision: **keep this default**.

#### Strategy 1: Precompile child resources

Precompile all `*.vmdl`, `*.vmat`, `*.vpost` before map compile. This fixed missing model log noise for `bhop_rose` but did not reduce peak enough.

Decision: **safe to include before every map compile**.

#### Strategy 2: Remove high-confidence aggregate proxies

Already required. Can reduce duplicate geometry and memory.

Decision: **include before compile**.

#### Strategy 3: Compile flag probing

Test only documented/safe resourcecompiler flags:

```txt
-fshallow
-fshallow2
```

For `bhop_rose`, `-fshallow2` still exceeded memory during visibility at about 25 GiB.

Decision: **allowed as automatic retry after normal compile memory fail**, but do not treat success as equivalent until runtime verified.

#### Strategy 4: Geometry slimming fallback

If memory still fails, generate a compile-lite variant by removing low-confidence nonessential visual-only prop_static/generated proxies while preserving CMapMesh course geometry.

Decision: **not automatic yet**. This risks geometry fidelity and needs review or strong rules.

#### Strategy 5: Manual/high-memory queue

For maps that barely exceed 24 GiB, queue them for a separate explicit approval path:

```txt
--allow-memory-gb 32
```

Decision: **requires explicit user approval per run**.

## Recommended implementation order

### Phase 1: Generic successful-path automation

Implement:

```txt
full_recompile_workshop_map.py
```

Features:

- CLI args for workshop root/map/addon/install target
- VRF inner/outer decompile
- CSDK staging
- material rewrite table
- sky fallback
- texture `.txt` generation
- aggregate proxy removal
- robust entity shell insertion
- material/VPOST/VMDL precompile
- map compile with memory wrapper
- pack export
- verify world lighting version
- optional live install with backup
- markdown report

Goal: maximize batch success for maps like `bhop_soulscape`.

### Phase 2: Failure-class ledger

For failed maps, output machine-readable JSON and human markdown:

```json
{
  "map": "bhop_rose",
  "status": "FAILED_MEMORY_CAP",
  "peak_gib": 24.79,
  "last_stage": "map_compile_visibility",
  "unsupported_shaders_remaining": [],
  "missing_resources": [],
  "removed_aggregate_props": [...]
}
```

Goal: no guessing. Every failure has a category.

### Phase 3: Fidelity improvements

After reliable batch conversion:

- preserve original sky when possible
- richer PBR conversion
- glass/water-specific material quality
- generated dynamic lights only if baked lighting not sufficient
- minimap/runtime quality additions

## Overall recommendation

Build the generic converter now using the `bhop_soulscape` process as the reference path. Keep the first version conservative:

1. prioritize valid full Deadlock recompile and runtime load
2. use safe PBR/sky fallbacks
3. preserve geometry/course shape
4. classify failures rather than improvising
5. only add visual fidelity once maps compile and load

This removes the model from the happy path. A model/operator is only needed for new failure classes and fidelity decisions.
