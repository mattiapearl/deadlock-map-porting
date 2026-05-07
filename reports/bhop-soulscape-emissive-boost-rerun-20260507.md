# bhop_soulscape F_SELF_ILLUM + emissive boost rerun - 2026-05-07

## Change

Updated the material classifier in:

```txt
C:/Code/deadlock-map-porting/tools/full_recompile_bhop_soulscape_from_mapping_recipe.py
```

For original CS2 self-illum materials, the rewrite now emits:

```txt
F_UNLIT "1"
F_SELF_ILLUM "1"
g_flSelfIllumScale1 = max(original, 2.5)
TextureSelfIllumMask1 = original TextureSelfIllumMask or color texture
```

This targets the remaining dimness seen after the previous upgrade.

## Rerun

Material classification:

```txt
enriched_pbr: 12
emissive_pbr: 5
sky: 1
```

Full map compile:

```txt
C:/Code/deadlock-map-porting/logs/compile_bhop_soulscape_full_recompile_1778175109.log
OK: 36 compiled, 0 failed, 0 skipped, 6m:28s
[memlimit] limit=28.0 GiB
[memlimit] peak observed: 13.50 GiB
```

## Export

```txt
C:/Code/deadlock-map-porting/exports/bhop_soulscape_full_recompile_emissive_boost_20260507_dir.vpk
SHA256: 20cb9924b3ec11ab8fe4f7352964eb9cfb62a99bcd8116afb7f3c1d51f9066f1
Size: 88,044,650 bytes
```

## Live install

Backup before install:

```txt
C:/Code/deadlock-map-porting/live_backups/install_bhop_soulscape_emissive_boost_20260507/pak72_dir.vpk
SHA256: 6e24531cfd10e33656bc3c0181569e61397a70f9ea7b117a3bf0671c26d18d4d
```

Installed:

```txt
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk
SHA256: 4856507fc0f6c23890edb3ce19b98c3ceed8df653b68d8d8565b270aa552cacb
Size: 579,894,444 bytes
```

## Verification

Live inner map VPK matches rebuilt game addon inner map VPK:

```txt
e1be5ea3842746a3e93ff47c330bf1dd4b6a16d5694f50b4b727a4a90b459773
```

Live `glowingblue.vmat_c` contains:

```txt
F_SELF_ILLUM
F_UNLIT
g_flSelfIllumAlbedoFactor1
g_flSelfIllumScale1
g_vSelfIllumTint1
g_tSelfIllumMask
```

World lighting remains Deadlock-native:

```txt
m_worldLightingInfo.m_nLightmapGameVersionNumber = 4
m_worldLightingInfo.m_bHasLightmaps = true
m_worldLightingInfo.m_bSHLightmaps = true
```

## Test command

```txt
map bhop_soulscape
```
