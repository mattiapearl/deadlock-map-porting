# Three new workshop bhop maps vs working `bhop_colour` package

## Input maps

- `3605179998` -> `bhop_soulscape`
- `3647098259` -> `bhop_quit_full`
- `3660240969` -> `bhop_rose`

## Console evidence read first

`C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/console.log`

Key runtime errors from the bad install/test:

```txt
[WorldRenderer] Lightmap version number is out of date! Reverting to dynamic lighting
Failed loading resource "materials/skybox/sky_de_vertigo.vmat_c" (ERROR_FILEOPEN: File not found)
[WorldRenderer] Failed to mount world vpk file maps\prefabs\misc\team_select.vpk, file could not be found.
[WorldRenderer] Failed to mount world vpk file maps\prefabs\misc\terrorist_team_intro.vpk, file could not be found.
[WorldRenderer] Failed to mount world vpk file maps\prefabs\misc\counterterrorist_team_intro.vpk, file could not be found.
[WorldRenderer] Failed to mount world vpk file maps\prefabs\misc\end_of_match.vpk, file could not be found.
[HostStateManager] Discarding pending request 'Loading (bhop_quit_full)'
[ResourceSystem] Failed loading resource "materials/minimap/bhop_quit_full.vmat_c" (ERROR_FILEOPEN: File not found)
[ResourceSystem] Failed loading resource "materials/minimap/bhop_soulscape.vmat_c" (ERROR_FILEOPEN: File not found)
Missing info_target named rebels_vanguard_spawn
Missing info_target named combine_vanguard_spawn
C_BasePlayerPawn::OnPostPredictionError( ) prediction distance 1503.094 - teleporting
```

## Exact high-level difference from the known-good `bhop_colour`

### Working `bhop_colour` final package

- Outer support VPK contains 30 VMATs / 71 VTEXs / postprocess / LOS / nested map VPK.
- Material shaders in support package:
  - `pbr.vfx`: 29
  - `sky.vfx`: 1
  - **0 `csgo_*` shaders**
- Runtime entity set:
  - 677 `light_omni2`
  - 42 `trigger_teleport`
  - 22 `env_combined_light_probe_volume`
  - 22 `trigger_multiple`
  - 21 `info_teleport_destination`
  - 17 `func_water`
  - 1 `worldspawn`, `light_environment`, `env_sky`, `post_processing_volume`
- `world.vwrld_c` lighting flags:
  - `m_bBuildBakedLighting = false`
  - `m_bHasLightmaps = false`
- It relies on dynamic entities/probes/cubemap atlas rather than a stale CS2 baked-lightmap world.

### New maps before fixing

Original workshop VMAT shaders:

- `bhop_soulscape`: `csgo_lightmappedgeneric.vfx` x11, `csgo_complex.vfx` x5, `csgo_simple.vfx` x1, `sky.vfx` x1
- `bhop_quit_full`: `csgo_lightmappedgeneric.vfx` x14, `csgo_static_overlay.vfx` x1
- `bhop_rose`: `csgo_lightmappedgeneric.vfx` x8, `csgo_moondome.vfx` x1, `sky.vfx` x1

These differ from final `bhop_colour`, which had no unsupported CS2 shaders left.

## Map-specific blockers

### `bhop_quit_full`

This map did not finish loading because the compiled entity lump contains CS2 prefab entities:

- `team_select`
- `terrorist_team_intro`
- `counterterrorist_team_intro`
- `end_of_match`

Deadlock tried to mount these prefab VPKs and failed:

```txt
maps\prefabs\misc\team_select.vpk
maps\prefabs\misc\terrorist_team_intro.vpk
maps\prefabs\misc\counterterrorist_team_intro.vpk
maps\prefabs\misc\end_of_match.vpk
```

`bhop_colour` does **not** contain these prefab entities, so it does not hit this failure path.

`bhop_quit_full` also references missing materials not present in the workshop support VPK:

- `materials/skybox/sky_de_vertigo.vmat`
- `materials/dev/dev_measuregeneric01.vmat`
- several `materials/tools/*` VMATs

### `bhop_soulscape`

It loads but has spawn/prediction problems:

```txt
Missing info_target named rebels_vanguard_spawn
Missing info_target named combine_vanguard_spawn
C_BasePlayerPawn::OnPostPredictionError( ) prediction distance 1503.094 - teleporting
```

It has only CS2 spawn entities:

- 12 `info_player_terrorist`
- 12 `info_player_counterterrorist`
- 1 `info_player_start`

It does not have the Deadlock shell spawn helpers we injected in earlier reconstructed `bhop_colour` attempts (`info_team_spawn`, `rebels_vanguard_spawn`, `combine_vanguard_spawn`).

### `bhop_rose`

It has fewer entities and no prefab blocker, but has the same shader/sky/material translation problem.

## Lighting/skybox cause

The new maps' `world.vwrld_c` differs from final `bhop_colour`:

- `bhop_colour`: `m_bBuildBakedLighting = false`
- all three new maps: `m_bBuildBakedLighting = true`

Deadlock then logs:

```txt
Lightmap version number is out of date! Reverting to dynamic lighting
```

So the new maps are carrying stale CS2 baked-lighting intent while not having a Deadlock-compatible lighting/probe/material setup like the final `bhop_colour` package.

Skybox issue is separate and concrete: `bhop_quit_full` references `materials/skybox/sky_de_vertigo.vmat_c`, which was absent.

## What I fixed live after this diagnosis

I rebuilt the mounted live `pak72_dir.vpk` with additional compatibility assets:

- Added same-path compiled skybox materials:
  - `materials/skybox/sky_de_vertigo.vmat_c`
  - `materials/skybox/skybox.vmat_c`
  - `materials/skybox/ssss.vmat_c`
  - `materials/skybox/moondome.vmat_c`
- Added same-path tool/dev fallback materials:
  - `materials/tools/toolstrigger.vmat_c`
  - `materials/tools/toolsinvisible.vmat_c`
  - `materials/tools/toolsinvisibleladder.vmat_c`
  - `materials/tools/toolsplayerclip.vmat_c`
  - `materials/tools_postprocess_volume.vmat_c`
  - `materials/dev/dev_measuregeneric01.vmat_c`
- Added minimap placeholders:
  - `materials/minimap/bhop_soulscape.vmat_c`
  - `materials/minimap/bhop_quit_full.vmat_c`
  - `materials/minimap/bhop_rose.vmat_c`
- Added empty placeholder prefab VPKs for the `bhop_quit_full` prefab-mount blocker.

Installed live:

```txt
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk
SHA256 f71e9d1ab03f9509e9b7b065ae436f9aa52849e75f212563f951dc67095387c5
```

Backup:

```txt
C:/Code/deadlock-map-porting/live_backups/fix_three_bhop_assets_pak72_20260507_135757
```

## Remaining exact gap

The remaining big gap vs a robust `bhop_colour`-style port is entity/runtime shell patching:

- Need to remove or neutralize CS2 prefab entities in `bhop_quit_full` properly, not just satisfy missing VPK mounts.
- Need to add Deadlock spawn shell entities / targets for `bhop_soulscape` and likely the other two maps.
- Need a real material conversion using original texture refs/masks like final `bhop_colour`, not flat-color fallback VMATs.
- Need to solve stale baked-lighting flags/probes if dynamic fallback is too dark.
