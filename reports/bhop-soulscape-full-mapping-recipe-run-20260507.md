# bhop_soulscape full mapping-recipe run - 2026-05-07

Map selected because `bhop_rose` followed the same process through material compile but full source map compile exceeded the required 24 GiB memory cap (`24.23-25.01 GiB`) even after removing the documented aggregate prop_static decompile artifact and precompiling VMDLs. I did not bypass the memory cap.

## Input

```txt
C:/Code/deadlock-map-porting/new_workshop_maps/3605179998/extract/maps/bhop_soulscape.vpk
C:/Code/deadlock-map-porting/new_workshop_maps/3605179998/extract/materials/**
```

## Process run

1. VRF/Source2Viewer-CLI decompiled the inner map VPK to source:
   ```txt
   C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape/decompile_inner
   ```
2. VRF/Source2Viewer-CLI decompiled outer materials/postprocess/sounds:
   ```txt
   C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape/decompile_outer
   ```
3. Staged as CSDK addon:
   ```txt
   content: C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_soulscape_full_recompile
   game:    C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_soulscape_full_recompile
   ```
4. Rewrote unsupported CS2 shaders to Deadlock-compatible shaders:
   - `17` VMATs -> `pbr.vfx`
   - `1` VMAT -> `sky.vfx`
5. Patched source VMAP entities:
   - removed one VRF aggregate prop_static proxy: `056fd23f-6b65-419b-90f8-059e91b34a51`
   - inserted `point_servercommand`, `logic_auto`, `info_team_spawn` x3, and `info_teleport_destination stage1`
   - spawn origin selected near existing start: `-1686.8199462891 -442.7349853516 281`
6. Compiled all VMATs and VPOSTs.
7. Full source map compile completed under the 24 GiB wrapper:
   ```txt
   C:/Code/deadlock-map-porting/logs/compile_bhop_soulscape_full_recompile_1778170834.log
   ```
8. Packed an outer VPK containing the rebuilt inner map VPK and compiled dependencies.

## Output

```txt
C:/Code/deadlock-map-porting/exports/bhop_soulscape_full_recompile_mapping_recipe_20260507_dir.vpk
SHA256: 5b4e2a412023f9e27ff55cb3feea1adcad1a8751f7cd74d7b8e21a3cc5e8fb4c
Size: 88,030,385 bytes
Listing: C:/Code/deadlock-map-porting/exports/bhop_soulscape_full_recompile_mapping_recipe_20260507_listing.txt
```

## Verification

Extract/verify folder:
```txt
C:/Code/deadlock-map-porting/tmp_verify_soulscape_full
```

Compiled world lighting metadata is Deadlock-native:
```txt
m_worldLightingInfo.m_nLightmapVersionNumber = 8
m_worldLightingInfo.m_nLightmapGameVersionNumber = 4
m_worldLightingInfo.m_bHasLightmaps = true
m_worldLightingInfo.m_bSHLightmaps = true
```

Compiled material shaders:
```txt
17 x pbr.vfx
1 x sky.vfx
0 x csgo_* active shaders
```

Compiled lightmap resources are present under inner map VPK:
```txt
maps/bhop_soulscape/lightmaps/debug_chart_color.vtex_c
maps/bhop_soulscape/lightmaps/direct_light_shadows.vtex_c
maps/bhop_soulscape/lightmaps/directional_irradiance_sh2_*.vtex_c
maps/bhop_soulscape/lightmaps/env_light_probe_volume_*.vtex_c/dat
maps/bhop_soulscape/lightmaps/lightmap_query_data.kv3
```

## Scripts

```txt
C:/Code/deadlock-map-porting/tools/full_recompile_bhop_soulscape_from_mapping_recipe.py
C:/Code/deadlock-map-porting/tools/full_recompile_bhop_rose_from_mapping_recipe.py
```
