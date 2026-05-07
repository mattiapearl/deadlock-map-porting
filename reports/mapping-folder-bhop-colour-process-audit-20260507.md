# Mapping folder bhop_colour process audit - 2026-05-07

Source folder audited:

```txt
C:/Users/User/Downloads/mapping
```

## Important documents read

- `CLAUDE.md`
- `README.md`
- `PORTING_CS2_MATERIALS_TO_DEADLOCK_CSDK.md`
- `docs/ENVIRONMENT.md`
- `docs/FINDINGS.md`
- `docs/PIPELINE.md`
- `docs/NEXT_SESSION_PROMPT.md`
- `work/bhop_colour_fix/BHOP_COLOUR_FIX_REPORT.md`

Important scripts read:

- `tools/convert_workshop.py`
- `tools/pack_addon.py`
- `tools/pack_deps.py`
- `tools/inject_shaders.py`
- `tools/deploy_to_ddsm.py`
- `inject_cs2_shaders.ps1`
- `force_recompile_glass.ps1`
- `force_recompile_material.ps1`
- `force_recompile_stages.ps1`
- `work/bhop_colour_fix/splice.py`
- `work/bhop_colour_fix/add_team_spawns.py`
- `work/bhop_colour_fix/new_entities.txt`

## Key files and hashes

```txt
cs2 maps/bhop_colour/3071726325.vpk
  size 279,186,368
  sha256 3a5b7ec1c86bee301eb612bd61a88bec8b5bad4a8428dd2a37808d0a8d986a01

dl maps/pak33_dir_bhop_colour.vpk
  size 315,223,413
  sha256 d431926bc6222167f3f5dbbe6d7bc44a4e8e32fbf408c633d051ef6e426ec31e

dl maps/pak33_dir_bhop_colour_v4.vpk
  size 270,403,571
  sha256 21882fd0e28e837f4252983cd0b498948da713a8e635a52932814d0ca3ea6b44

Reduced_CSDK_12/game/citadel_addons/bhop_colour/maps/bhop_colour.vpk
  size 122,369,374
  sha256 858791218b1f98a28756227b00a5248a437d4f53b625cd56a4b25ddada623aac

Reduced_CSDK_12/content/citadel_addons/bhop_colour/maps/bhop_colour.vmap
  size 171,517,773
  sha256 2d71684434fd2b2c49a578e89c90e83347bd41928b98b765c8a8275cc6ac7c5f
```

## Correct bhop_colour process inferred from mapping folder

The working `bhop_colour` was not produced by only preserving the CS2 compiled map VPK. It used a full decompile/edit/recompile/package workflow:

1. Start from CS2 workshop VPK `3071726325.vpk`.
2. Decompile via VRF/Source2Viewer-CLI to source assets in `work/bhop_colour`.
3. Stage source VMAP and decompiled map assets into:
   - `Reduced_CSDK_12/content/citadel_addons/bhop_colour/maps/...`
4. Stage compiled/material outputs into:
   - `Reduced_CSDK_12/game/citadel_addons/bhop_colour/materials/...`
5. Rewrite CS2 VMATs away from unsupported `csgo_*` shaders to Deadlock/CSDK-supported shaders.
6. Patch missing runtime entities into source VMAP using binary DMX -> KV2 -> splice -> binary DMX:
   - `point_servercommand` named `panel`
   - `logic_auto` with `OnMapSpawn -> panel -> Command` bhop command
   - `info_team_spawn` for team 2, later cloned to teams 3 and 4
7. Compile the source VMAP with:
   - `Reduced_CSDK_12/game/bin_cs2/win64/resourcecompiler.exe`
   - `-game Reduced_CSDK_12/game/citadel`
   - `-nop4`
8. The successful build log shows actual VRAD3-GPU baked lighting ran and wrote fresh lightmaps / probe atlas / octrees.
9. Pack outer addon with `tools/pack_addon.py`, including:
   - `materials/**`
   - `maps/bhop_colour.vpk` inner compiled map
   - `maps/bhop_colour.los`
   - `postprocess/**`
   - `lighting/**`
   - `README.txt`
   and excluding `_vrad3`, `_bakeresourcecache`, addoninfo/editor caches.

## Material conversion rules actually used

CS2 shaders are not acceptable as active Deadlock materials. The folder documents that `csgo_*.vfx` can fail even when shader VPKs are mounted because they bind well-known textures incompatible with Deadlock renderer expectations.

Working material patterns:

- Opaque solid / simple textured surfaces:
  ```txt
  shader pbr.vfx
  TextureColor1 materials/.../<name>.tga
  ```
- Glass / alpha-keyed overlay replacement:
  ```txt
  shader pbr.vfx
  F_GLASS 1
  TextureColor1 materials/.../<name>.tga
  TextureGlassMask1 materials/.../<name>_mask.tga
  ```
- Sky:
  ```txt
  shader sky.vfx
  SkyTexture materials/.../skybox_climbit.exr
  ```

Important parameter trap: Deadlock `pbr.vfx` uses layer-suffixed names like `TextureColor1`, `TextureGlassMask1`, `TextureSelfIllumMask1`, not CS2-style unsuffixed names.

## Entity requirements from mapping folder

Bhop maps need:

- `info_team_spawn` for teams 2, 3, and 4. One team-2 spawn is not enough because Deadlock can assign team 3/4 before plugin/team correction.
- `logic_auto` and `point_servercommand` chain to run the bhop physics cvar string.
- `info_teleport_destination` named `stage1` at the start position.

The `new_entities.txt` initial patch added point_servercommand, logic_auto, and one team-2 spawn at `3535.1293945312 4792 96`; `add_team_spawns.py` later cloned teams 3 and 4.

## Critical lighting finding

The most important correction to the recent bad assumption:

A compiled Source 2 `world.vwrld_c` contains both `m_builderParams.m_bakedLightingInfo` and `m_worldLightingInfo`.

For the working rebuilt bhop_colour inner VPK:

```txt
m_builderParams.m_bakedLightingInfo:
  m_nLightmapVersionNumber = 0
  m_bHasLightmaps = false
  m_bSHLightmaps = false

m_worldLightingInfo:
  m_nLightmapVersionNumber = 8
  m_nLightmapGameVersionNumber = 4
  m_bHasLightmaps = true
  m_bSHLightmaps = true
```

So earlier scripts that only looked at the first `m_bHasLightmaps=false` were misleading. The render-time lighting state is in `m_worldLightingInfo`.

For the three currently preserved CS2 maps, `m_worldLightingInfo` is present but uses CS2 game version 2:

```txt
bhop_soulscape / bhop_quit_full / bhop_rose:
  m_worldLightingInfo.m_nLightmapVersionNumber = 8
  m_worldLightingInfo.m_nLightmapGameVersionNumber = 2
  m_worldLightingInfo.m_bHasLightmaps = true
```

This is a likely direct cause of Deadlock logging `Lightmap version number is out of date! Reverting to dynamic lighting`.

Working bhop_colour was fixed by full recompile/bake under the Deadlock CSDK game target, which produced game version 4 lightmaps, not by injecting more dynamic lights into a preserved CS2 world.

## Consequence for the current three-map port

The current three-map preserve-port approach is structurally weaker than the documented successful bhop_colour process. For lighting/material fidelity, the next attempt should follow the mapping-folder process:

1. VRF-decompile each workshop map to source.
2. Rewrite all materials from CS2 shaders to Deadlock-supported VMATs using original texture content and masks.
3. Patch required Deadlock/bhop runtime entities in source VMAP.
4. Compile the VMAP with Deadlock CSDK `bin_cs2` resourcecompiler targeting `game/citadel`.
5. Pack fresh inner VPK + materials outer VPK.

If full source VMAP compile is too memory-heavy for a large map, treat that as the constraint explicitly rather than pretending preserved CS2 lightmaps are good enough.
