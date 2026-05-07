# bhop_soulscape successful full-source Deadlock recompile process

Date: 2026-05-07

## Result

Installed live into:

```txt
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk
SHA256: c5595ef02edb47a3576a5b2c0d081e45816f1004f9afd6bfb97d52adaafc31ca
```

Standalone packed export:

```txt
C:/Code/deadlock-map-porting/exports/bhop_soulscape_full_recompile_mapping_recipe_20260507_dir.vpk
SHA256: 5b4e2a412023f9e27ff55cb3feea1adcad1a8751f7cd74d7b8e21a3cc5e8fb4c
```

Live backup before install:

```txt
C:/Code/deadlock-map-porting/live_backups/install_bhop_soulscape_full_recompile_20260507/pak72_dir.vpk
SHA256: 6d5c846ea9d0c4e610c21d14dbaa1b9a5efd0959d583617bc4ffac573a895a18
```

## Source inputs

```txt
Workshop root:
C:/Code/deadlock-map-porting/new_workshop_maps/3605179998/extract

Inner map VPK:
C:/Code/deadlock-map-porting/new_workshop_maps/3605179998/extract/maps/bhop_soulscape.vpk
```

## Tools

```txt
VRF / Source2Viewer CLI:
C:/Code/tools/vrf/Source2Viewer-CLI.exe

CSDK resourcecompiler:
C:/Users/User/Documents/Reduced_CSDK_12/game/bin_cs2/win64/resourcecompiler.exe

CSDK dmxconvert:
C:/Users/User/Documents/Reduced_CSDK_12/game/bin_cs2/win64/dmxconvert.exe

CSDK resourceinfo:
C:/Users/User/Documents/Reduced_CSDK_12/game/bin_cs2/win64/resourceinfo.exe

Memory wrapper:
C:/Code/deadlock-map-porting/tools/compile_with_memory_limit.py
```

## Working directories

```txt
Decompile/work root:
C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape

Content addon:
C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_soulscape_full_recompile

Game addon:
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_soulscape_full_recompile

Automation script used:
C:/Code/deadlock-map-porting/tools/full_recompile_bhop_soulscape_from_mapping_recipe.py
```

## Headless process

### 1. Decompile inner map VPK

Decompiled `maps/bhop_soulscape.vpk` to source VMAP and generated source model/entity resources:

```txt
C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape/decompile_inner
```

### 2. Decompile outer workshop payload

Decompiled outer extracted folder recursively for materials/postprocess/sounds:

```txt
C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape/decompile_outer
```

### 3. Stage CSDK addon

Copied decompiled `maps/` from inner decompile to the content addon. Copied `materials/`, `postprocess/`, `soundevents/`, and `sounds/` from outer decompile when present.

Created:

```txt
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_soulscape_full_recompile/addoninfo.txt
```

### 4. Add texture settings

For every decompiled `*.png`, `*.tga`, and `*.exr` under staged materials, generated a sibling `.txt` texture settings file if missing:

```txt
"settings"
{
}
```

This lets CSDK compile textures emitted by VRF.

### 5. Rewrite unsupported CS2 materials

Rewrote active `csgo_*` shaders to Deadlock-compatible shaders before compile.

Observed for soulscape:

```txt
17 VMATs -> pbr.vfx
1 VMAT  -> sky.vfx
0 active csgo_* shaders after rewrite
```

Generic PBR rewrite shape used:

```kv2
"Layer0"
{
    "shader" "pbr.vfx"
    "TextureColor1" "<TextureColor or TextureLayer1Color or default>"
}
```

Sky rewrite shape used:

```kv2
"Layer0"
{
    "shader" "sky.vfx"
    "g_flBrightnessExposureBias" "-1"
    "g_flRenderOnlyExposureBias" "0"
    "SkyTexture" "materials/skybox/sky_dl_dusk03_exr_9dd50fb1.png"
}
```

### 6. Convert VMAP to KV2 text

Used `dmxconvert`:

```txt
source binary .vmap -> keyvalues2 .txt
```

Intermediate:

```txt
C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape/bhop_soulscape.kv2.txt
```

### 7. Remove bad decompile aggregate prop_static artifact

Removed one VRF aggregate worldnode proxy entity:

```txt
model = maps/bhop_soulscape/worldnodes/n0_lr0_c2_s_cb_mesh.vmdl
entity id = 056fd23f-6b65-419b-90f8-059e91b34a51
```

This removes duplicate aggregate proxy geometry while preserving actual reconstructed `CMapMesh` geometry.

### 8. Insert Deadlock runtime/gameplay entity shell

Detected start origin from existing teleport destination:

```txt
-1686.8199462891 -442.7349853516 281
```

Inserted entities:

```txt
point_servercommand targetname=panel
logic_auto -> panel.Command(<bhop cvar command string>)
info_team_spawn teamnumber=2
info_team_spawn teamnumber=3
info_team_spawn teamnumber=4
info_teleport_destination targetname=stage1
```

Added new top-level `CMapEntity` blocks and referenced them from `CMapWorld.children`.

### 9. Convert patched KV2 back to binary VMAP

Used `dmxconvert`:

```txt
patched keyvalues2 .txt -> binary .vmap
```

Intermediate:

```txt
C:/Code/deadlock-map-porting/work/full_recompile_bhop_soulscape/bhop_soulscape.patched.kv2.txt
```

### 10. Compile materials and postprocess

Compiled all staged VMATs individually with CSDK `resourcecompiler.exe`.

Compiled staged VPOSTs:

```txt
postprocess/basic_linear_post.vpost
postprocess/bhop_soulscape.vpost
```

### 11. Compile full source VMAP under memory cap

Used the 24 GiB memory wrapper:

```txt
python C:/Code/deadlock-map-porting/tools/compile_with_memory_limit.py --limit-gb 24 -- \
  C:/Users/User/Documents/Reduced_CSDK_12/game/bin_cs2/win64/resourcecompiler.exe \
  -i C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_soulscape_full_recompile/maps/bhop_soulscape.vmap \
  -game C:/Users/User/Documents/Reduced_CSDK_12/game/citadel \
  -nop4
```

Compile log:

```txt
C:/Code/deadlock-map-porting/logs/compile_bhop_soulscape_full_recompile_1778170834.log
```

### 12. Pack outer VPK

Packed the rebuilt inner map VPK plus compiled dependencies into an outer addon VPK.

Included key entries:

```txt
maps/bhop_soulscape.vpk
materials/rbx/*.vmat_c
materials/rbx/*.vtex_c
materials/skybox/skybox.vmat_c
materials/skybox/sky_dl_dusk03_exr_9dd50fb1_png_44abcc22.vtex_c
postprocess/basic_linear_post.vpost_c
postprocess/bhop_soulscape.vpost_c
```

### 13. Install into live pak72

Extracted live `pak72_dir.vpk`, overlaid the full-recompile soulscape resources, repacked, and copied back.

### 14. Verify live install

Verified live extracted inner map VPK hash matched rebuilt game addon inner map VPK:

```txt
211cec3b0cbc8ab0f894d69c47a4e2ee1f703af858d2851b2bab8d4c612a6979
```

Verified compiled world lighting metadata:

```txt
m_worldLightingInfo.m_nLightmapVersionNumber = 8
m_worldLightingInfo.m_nLightmapGameVersionNumber = 4
m_worldLightingInfo.m_bHasLightmaps = true
m_worldLightingInfo.m_bSHLightmaps = true
```

This is the critical difference from preserved CS2 compiled worlds that had stale Deadlock-incompatible lightmap game version `2`.

## Runtime result

User confirmed the installed map worked in Deadlock with:

```txt
map bhop_soulscape
```
