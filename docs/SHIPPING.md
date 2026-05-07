# Shipping the Deadlock map porting pipeline

This document is the operator checklist for moving the pipeline to another machine.

## 1. Install/copy dependencies

Required:

```txt
Python 3.11+
Python vpk package/CLI
VRF Source2Viewer-CLI.exe
Reduced_CSDK_12
Deadlock install
```

Check tools:

```bash
python --version
python -c "import vpk; print('vpk ok')"
vpk -h
"<Source2Viewer-CLI.exe>" --help
"<Reduced_CSDK_12>/game/bin_cs2/win64/resourcecompiler.exe" -help
"<Reduced_CSDK_12>/game/bin_cs2/win64/dmxconvert.exe" -h
"<Reduced_CSDK_12>/game/bin_cs2/win64/resourceinfo.exe" -h
```

## 2. Configure environment

Bind paths through environment variables; do not edit scripts for machine-specific paths.

```powershell
$env:DEADLOCK_PORT_ROOT="C:/Code/deadlock-map-porting"
$env:DEADLOCK_CSDK_ROOT="C:/Users/User/Documents/Reduced_CSDK_12"
$env:DEADLOCK_VRF_CLI="C:/Code/tools/vrf/Source2Viewer-CLI.exe"
$env:DEADLOCK_GAME_ROOT="C:/Program Files (x86)/Steam/steamapps/common/Deadlock"
$env:DEADLOCK_MEMORY_GB="28"
$env:DEADLOCK_INSTALL_PAK="C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk"
```

Reference config:

```txt
config/porting_paths.example.json
```

## 3. Prepare workshop input

Expected input shape after extracting a CS2 workshop addon:

```txt
<workshop-root>/extract/maps/<map>.vpk
<workshop-root>/extract/materials/...
<workshop-root>/extract/postprocess/...
<workshop-root>/extract/soundevents/...
<workshop-root>/extract/sounds/...
```

The script also accepts roots where `maps/<map>.vpk` is directly under the root.

## 4. Run one map

```bash
python tools/full_recompile_workshop_map.py \
  --workshop-root <workshop-root> \
  --map <map_name> \
  --addon <map_name>_full_recompile \
  --memory-gb 28
```

For a near-threshold map, a documented compile retry is:

```bash
python tools/full_recompile_workshop_map.py \
  --workshop-root <workshop-root> \
  --map <map_name> \
  --compile-flag -fshallow2 \
  --memory-gb 28
```

## 5. Install one map

Only install into a known mounted live pak. The current working target was `pak72_dir.vpk`.

```bash
python tools/full_recompile_workshop_map.py \
  --workshop-root <workshop-root> \
  --map <map_name> \
  --addon <map_name>_full_recompile \
  --memory-gb 28 \
  --install \
  --install-pak "$DEADLOCK_INSTALL_PAK" \
  --force-stop-deadlock
```

Installer behavior:

1. Detects Deadlock process.
2. Stops Deadlock only when `--force-stop-deadlock` is set.
3. Backs up target pak.
4. Extracts target pak to temp.
5. Overlays generated resources.
6. Repacks target pak.
7. Replaces live pak.
8. Writes report.

Steam does not need to be stopped for normal installs.

## 6. Batch mode

Create a manifest like:

```txt
manifests/maps.example.json
```

Run:

```bash
python tools/batch_full_recompile.py --manifest manifests/maps.example.json
```

Extra args after `--extra` are appended to each map invocation.

## 7. Verify output

For every successful map:

```txt
reports/full_recompile_<map>_<timestamp>.json
reports/full_recompile_<map>_<timestamp>.md
exports/<map>_full_recompile_<timestamp>_dir.vpk
```

Required checks:

```txt
m_worldLightingInfo.m_nLightmapGameVersionNumber = 4
m_worldLightingInfo.m_bHasLightmaps = true
0 active csgo_* shaders
maps/<map>.vpk present in outer VPK
```

Runtime:

```txt
map <map_name>
```

## 8. Known reference maps

### bhop_soulscape

Successful full-source rebuild. Use it as the golden reference.

Key report:

```txt
reports/bhop-soulscape-emissive-boost-rerun-20260507.md
```

### bhop_rose

All material/entity/model precompile stages pass, but full map compile exceeds 28 GiB.

Status:

```txt
FAILED_MEMORY_CAP
```

Key report:

```txt
reports/bhop-rose-full-recompile-attempt-20260507.md
```

Likely next steps for rose:

1. Try explicit higher cap, likely 30 GiB+.
2. Compile on a machine with more headroom.
3. Only after approval, create a geometry-slim variant.

## 9. Failure handling

Do not patch blindly. Each failure is classified:

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

Use the JSON report and compiler logs to decide the next action.

## 10. Do not ship generated/private artifacts by default

Git excludes generated/heavy/live files:

```txt
work/
exports/
logs/
live_backups/
new_workshop_maps/
tmp*/
*.vpk
*.vpk.*
```

Ship source scripts, docs, examples, and tests. Distribute built VPKs as releases/artifacts only when intended.
