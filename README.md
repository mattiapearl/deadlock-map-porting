# Deadlock CS2 bhop map porting

Headless tooling for porting CS2/Source 2 bhop workshop maps into Deadlock by decompiling to source assets, rewriting incompatible materials, patching Deadlock runtime entities, recompiling with Deadlock CSDK, packing, and optionally installing into a live Deadlock addon VPK.

Golden reference: `bhop_soulscape` was successfully rebuilt and loaded in Deadlock with valid Deadlock lightmap metadata.

## What this does

For each map:

1. Decompile inner `maps/<map>.vpk` with VRF/Source2Viewer CLI.
2. Decompile outer workshop payload for materials/postprocess/sounds.
3. Stage a CSDK content/game addon.
4. Rewrite unsupported `csgo_*` VMAT shaders to Deadlock-compatible `pbr.vfx` / `sky.vfx`.
5. Preserve important material variants, including self-illum/emissive blocks.
6. Convert binary VMAP to KV2, patch entities, convert back to binary VMAP.
7. Remove high-confidence aggregate decompile proxy artifacts.
8. Compile VMAT/VPOST/VMDL resources.
9. Compile the full VMAP under a memory cap.
10. Pack an outer VPK.
11. Optionally install into live Deadlock with backup.
12. Emit JSON and Markdown reports.

## Requirements

- Windows recommended for Deadlock/CSDK tools.
- Python 3.11+
- Python package / CLI: `vpk`
- VRF Source2Viewer CLI
- Reduced Deadlock CSDK
- Deadlock install for live testing/install
- GitHub CLI only if publishing/maintaining the repo

Current expected tools:

```txt
Source2Viewer-CLI.exe
resourcecompiler.exe
dmxconvert.exe
resourceinfo.exe
```

## Environment variables

All important paths can be bound through env vars:

```txt
DEADLOCK_PORT_ROOT       repo/work root
DEADLOCK_CSDK_ROOT       Reduced_CSDK_12 root
DEADLOCK_VRF_CLI         Source2Viewer-CLI.exe path
DEADLOCK_GAME_ROOT       live Deadlock root
DEADLOCK_MEMORY_GB       default map compile memory cap
DEADLOCK_INSTALL_PAK     live pak*_dir.vpk to overlay on install
```

PowerShell example:

```powershell
$env:DEADLOCK_PORT_ROOT="C:/Code/deadlock-map-porting"
$env:DEADLOCK_CSDK_ROOT="C:/Users/User/Documents/Reduced_CSDK_12"
$env:DEADLOCK_VRF_CLI="C:/Code/tools/vrf/Source2Viewer-CLI.exe"
$env:DEADLOCK_GAME_ROOT="C:/Program Files (x86)/Steam/steamapps/common/Deadlock"
$env:DEADLOCK_MEMORY_GB="28"
$env:DEADLOCK_INSTALL_PAK="C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk"
```

See:

```txt
config/porting_paths.example.json
```

## Single-map usage

```bash
python tools/full_recompile_workshop_map.py \
  --workshop-root C:/Code/deadlock-map-porting/new_workshop_maps/3605179998 \
  --map bhop_soulscape \
  --addon bhop_soulscape_full_recompile \
  --memory-gb 28
```

Install into a mounted live pak with backup:

```bash
python tools/full_recompile_workshop_map.py \
  --workshop-root C:/Code/deadlock-map-porting/new_workshop_maps/3605179998 \
  --map bhop_soulscape \
  --addon bhop_soulscape_full_recompile \
  --memory-gb 28 \
  --install \
  --install-pak "C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk" \
  --force-stop-deadlock
```

If the map has already been decompiled into `work/full_recompile_<map>/decompile_inner` and `decompile_outer`:

```bash
python tools/full_recompile_workshop_map.py --skip-decompile --workshop-root unused --map bhop_soulscape
```

## Batch usage

```bash
python tools/batch_full_recompile.py --manifest manifests/maps.example.json
```

## Material conversion policy

Unsupported CS2 shaders must not remain active:

```txt
csgo_complex.vfx
csgo_static_overlay.vfx
csgo_glass.vfx
csgo_water_fancy.vfx
csgo_lightmappedgeneric.vfx
csgo_moondome.vfx
csgo_simple.vfx
```

Classifier order:

```txt
sky/moondome -> sky.vfx fallback
glass -> pbr.vfx + F_GLASS
water -> safe degraded pbr path, reported
self-illum/emissive -> pbr.vfx + F_UNLIT + F_SELF_ILLUM + boosted mask/scale/tint
translucent/opacity -> pbr.vfx + translucent path
enriched opaque -> pbr.vfx preserving tint/normal/metalness/opacity
minimal opaque -> pbr.vfx + TextureColor1
```

## Success verification

A successful full-source recompile should have:

```txt
m_worldLightingInfo.m_nLightmapGameVersionNumber = 4
m_worldLightingInfo.m_bHasLightmaps = true
0 active csgo_* shaders in compiled VMATs
```

Runtime test:

```txt
map <map_name>
```

## Known statuses

Each run produces `reports/full_recompile_<map>_<timestamp>.json` and `.md` with one status:

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

Known examples:

- `bhop_soulscape`: `SUCCESS` at 28 GiB, peak about 13.5 GiB.
- `bhop_rose`: `FAILED_MEMORY_CAP` at 28 GiB. Best probe exceeded 28 GiB slightly; likely needs a higher cap or geometry-slim strategy.

## Important docs

```txt
docs/bhop_soulscape_successful_full_recompile_process.md
docs/full_recompile_automation_decisions.md
docs/SHIPPING.md
reports/bhop-soulscape-emissive-boost-rerun-20260507.md
reports/bhop-rose-full-recompile-attempt-20260507.md
```
