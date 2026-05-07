# bhop_soulscape upgraded material classifier rerun - 2026-05-07

## Why

The first successful full-source recompile used a too-lossy material rewrite:

```txt
any csgo_* -> pbr.vfx + TextureColor1 only
```

This degraded self-illuminated spawn cubes: original `csgo_complex.vfx` materials had `F_SELF_ILLUM`, `TextureSelfIllumMask`, and self-illum brightness/scale/tint fields, but the replacement dropped them.

## Upgrade made

Updated:

```txt
C:/Code/deadlock-map-porting/tools/full_recompile_bhop_soulscape_from_mapping_recipe.py
```

Material rewrite now classifies instead of doing one generic replacement:

```txt
sky/moondome -> sky fallback
self-illum/emissive -> pbr.vfx + F_UNLIT + self-illum mask/scale/tint
translucent/opacity -> pbr.vfx + F_TRANSLUCENT-ish path
possible glass -> pbr.vfx + F_GLASS-ish path
enriched opaque -> pbr.vfx preserving tint, normal/roughness source, opacity, metalness
minimal opaque -> pbr.vfx + TextureColor1
```

## Rerun

Ran the full two-part process again from decompiled source/staged content:

```txt
stage materials/maps/postprocess
rewrite materials
patch source VMAP entities
compile 18 VMATs
compile 2 VPOSTs
precompile 26 VMDLs
full VMAP compile with --limit-gb 28
pack export
install into live pak72
verify live install
```

Material classification counts:

```txt
enriched_pbr: 12
emissive_pbr: 5
sky: 1
```

Full map compile log:

```txt
C:/Code/deadlock-map-porting/logs/compile_bhop_soulscape_full_recompile_1778173596.log
```

Compile result:

```txt
OK: 36 compiled, 0 failed, 0 skipped, 12m:55s
[memlimit] limit=28.0 GiB
[memlimit] peak observed: 13.46 GiB
```

## Export

```txt
C:/Code/deadlock-map-porting/exports/bhop_soulscape_full_recompile_upgraded_materials_20260507_dir.vpk
SHA256: 4a43517228c5dc8335715e46018209bfe9b465f5a7bf765fb51a3a96e8f5e980
Size: 88,042,989 bytes
Listing: C:/Code/deadlock-map-porting/exports/bhop_soulscape_full_recompile_upgraded_materials_20260507_listing.txt
```

## Live install

Deadlock was running and held the live VPK open, so it was stopped before replacing the VPK.

Live backup before upgraded install:

```txt
C:/Code/deadlock-map-porting/live_backups/install_bhop_soulscape_upgraded_materials_20260507/pak72_dir.vpk
SHA256: c5595ef02edb47a3576a5b2c0d081e45816f1004f9afd6bfb97d52adaafc31ca
```

Installed live VPK:

```txt
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk
SHA256: 6e24531cfd10e33656bc3c0181569e61397a70f9ea7b117a3bf0671c26d18d4d
Size: 579,892,783 bytes
```

## Verification

Live extracted inner map VPK matches rebuilt game addon inner map VPK:

```txt
feee893f5d405b88ab67994390530900162655733189aceed01d23e49c09972f
```

Live world lighting metadata remains Deadlock-native:

```txt
m_worldLightingInfo.m_nLightmapVersionNumber = 8
m_worldLightingInfo.m_nLightmapGameVersionNumber = 4
m_worldLightingInfo.m_bHasLightmaps = true
m_worldLightingInfo.m_bSHLightmaps = true
```

Live `materials/rbx/glowingblue.vmat_c` now contains emissive-preserving parameters:

```txt
F_UNLIT = 1
m_shaderName = "pbr.vfx"
F_UNLIT
g_flSelfIllumScale1
g_flSelfIllumAlbedoFactor1
g_vSelfIllumTint1
g_tSelfIllumMask
```

## Test command

```txt
map bhop_soulscape
```
