# Deadlock CS2 Map Porting Root-Cause Report

Date: 2026-05-02

## Executive summary

The current `bhop_emevaelx3` state is **not** a simple "map did not update" problem anymore. The visual map is loading, textures are mostly resolved, and the package is no longer shadowed by the stale outer `maps/bhop_emevaelx3/...` worldnode folder. The current failure is the **Deadlock gameplay/spawn layer** failing on top of a shifted Source 2 map.

The latest screenshot shows:

```text
pos: -24.84 -45.97 -1272.38
ang: 4.22 8.62 0.00
vel: 240.64 (249.32)
```

That position is horizontally near our injected start area, but far below the start floor/spawn Z. The console then shows:

```text
C_BasePlayerPawn::OnPostPredictionError( ) prediction distance 1350.774 - teleporting
[Server] Loaded hero 356/hero_werewolf
Player Surprising Lepton Button Carver is out of the play area
```

This means the client/server are repeatedly correcting or moving a pawn/camera that Deadlock considers invalid/outside play. The `~250 velocity` is not evidence that the player is intentionally running through the map; it is a symptom of a pawn/camera in a failed spawn/correction/death loop.

Separately, the current map placement is bad: we moved the CS2 start close to origin, which pushed the far end of the course to very large positive coordinates. The current shifted mesh AABB is:

```text
mesh mins: -104, -1400, -2720
mesh maxs: 23896, 13736, 264
mesh center: 11896, 6168, -1228
mesh size: 24000 x 15136 x 2984
```

That explains why the course appears to be "far away" even though the start is near origin. We anchored the **start** near origin, not the **entire map** around origin. That also produced Deadlock network-origin warnings:

```text
citadel_minimap_boundary::m_vecOrigin ... m_cellX cell 39 is outside of cell bounds (0->32) @(24529.212891 0.000000 0.000000)
light_omni2::m_vecOrigin ... cell 32/36/37 is outside of cell bounds
```

The next correct move is **not another small step**. The right fix is to rebuild from a known-good Deadlock map shell and center the entire imported course AABB in Deadlock-safe space, then make spawning deterministic with both map entities and a runtime fallback.

---

## Evidence from current local artifacts

### Screenshot evidence

Latest screenshot:

```text
C:/Users/User/Pictures/Screenshots/Screenshot 2026-05-02 175159.png
```

Observed overlay:

```text
name: Surprising Lepton Button Carver
pos: -24.84 -45.97 -1272.38
ang: 4.22 8.62 0.00
vel: 240.64 (249.32)
```

Important interpretation:

- XY is close to our injected start shell.
- Z is around `-1272`, far below our intended spawns at `z=192` and below the visible start floor region.
- The UI shows `Testing Tools`, so `hero_testing_controller` logic is active.
- The player is not in a stable, alive, controllable spawn state.

### Console evidence

Runtime log around the latest test:

```text
05/02 17:51:31 [Server] SV: Spawn Server: bhop_emevaelx3
05/02 17:51:31 [Client] Map: "bhop_emevaelx3"
05/02 17:51:31 [Server] Created physics for bhop_emevaelx3
05/02 17:51:31 [Server] 351:citadel_minimap_boundary::m_vecOrigin CNetworkOriginCellCoordQuantizedVector m_cellX cell 39 is outside of cell bounds (0->32) @(24529.212891 0.000000 0.000000)
05/02 17:51:31 Missing info_target named rebels_vanguard_spawn
05/02 17:51:31 Missing info_target named combine_vanguard_spawn
05/02 17:51:37 C_BasePlayerPawn::OnPostPredictionError( ) prediction distance 1350.774 - teleporting
05/02 17:51:37 [Server] Loaded hero 356/hero_werewolf
05/02 17:51:37 Player Surprising Lepton Button Carver is out of the play area
```

Key points:

1. The map is loading and physics are created.
2. The hero loads late, several seconds after map activation.
3. Deadlock then reports out-of-play immediately.
4. The map has network-origin/coordinate warnings from large positive coordinates.
5. Missing vanguard targets still happen; working custom movement maps can omit these, but for our deterministic pipeline we should add safe anchors anyway.

### Current injected entities

Latest verified live entity lump had:

```text
citadel_minimap_boundary:
  -1022.819336 -3589.560547 -4904
  24529.212891 14347.766602 3085

info_team_spawn:
  team 2: 120 -24 192
  team 3: 168 -24 192
  team 4: 72 -24 192

hero_testing_controller:
  120 -96 192
  168 -96 192
```

The Z-expanded minimap boundaries were probably a misread: working maps suggest `citadel_minimap_boundary` is primarily a paired coarse 2D/rectangular map/play boundary, not a true 3D volume. The bigger issue is the far positive coordinate (`x=24529`).

---

## Deadlock map structure learned locally

Official Deadlock maps are loose files under:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/maps/<map>.vpk
```

Examples:

```text
dl_hideout.vpk
dl_midtown.vpk
dl_streets.vpk
hero_testing.vpk
1v1_test.vpk
onelane.vpk
```

A nested map VPK typically contains:

```text
maps/<map>.vmap_c
maps/<map>.nav
maps/<map>/entities/default_ents.vents_c
maps/<map>/world_physics.vmdl_c
maps/<map>/worldnodes/*.vmdl_c
```

Custom Deadlock maps can be installed either as direct `game/citadel/maps/<map>.vpk` files or inside an addon VPK/search path. Our current active route is:

```text
game/citadel/addons/pak71_dir.vpk
  maps/bhop_emevaelx3.vpk
  materials/...
```

Important packaging rule: a CS2 map VPK is not enough by itself if its materials/models/sounds live in the outer workshop VPK. The outer/supporting resources must also be mounted in Deadlock's search path.

---

## Working Deadlock map entity patterns

### Official `hero_testing`

Extracted official `hero_testing` has:

```text
worldspawn worldname = "hero_testing"
mapUsageType = "standard"

citadel_minimap_boundary:
  1280 2816 -64
  -1280 -1280 0

many info_team_spawn entities:
  team 2 at z 128 / z -128 areas
  team 3 at z 0 / z -128 areas

hero_testing_controller present
```

This is an important baseline: use the official shell shape and exact entity patterns where possible.

### Green Screen Map

Extracted community map `green_screen` has:

```text
info_team_spawn team 2/3/4
lanenum = 0
origin = 0 0 7
hero_testing_controller
citadel_minimap_boundary:
  960 2048 0
  -3136 -2048 0
```

It uses two boundary points with the same Z, reinforcing that `citadel_minimap_boundary` is not a 3D kill volume.

### pp_aero

Extracted community movement map `pp_aero` has:

```text
info_team_spawn team 2/3
hero_model = hero_viscous
lanenum = 0
spawn origins around z = -1792
hero_testing_controller x2 near the spawns
trigger_teleport and trigger_multiple for course/timer logic
```

`pp_aero` proves that a valid Deadlock movement map can spawn below `z=0`. Negative Z alone is not fatal.

### MOG BHOP `bhop_bubblegum`

Extracted MOG BHOP map has:

```text
info_team_spawn team 2/3/4
lanenum = 6
spawn origins around:
  -6384 -418 122
  -6313 -416 122
  -6246 -415 122
```

It also has a large course but generally stays within a more reasonable centered coordinate envelope than our current `x=24529` placement.

---

## CS2 map structure and why CS2 gameplay logic does not port directly

CS2 Source 2 maps use CS2-specific entities such as:

```text
info_player_terrorist
info_player_counterterrorist
trigger_teleport
info_teleport_destination
trigger_hurt
trigger_multiple
logic_auto
point_servercommand
team_select / terrorist_team_intro / counterterrorist_team_intro / end_of_match point prefabs
```

For `bhop_emevaelx3`, the CS2 `point_servercommand` included commands like:

```text
sv_enablebunnyhopping 1
sv_autobunnyhopping 1
sv_airaccelerate 1000
mp_roundtime 60
mp_freezetime 1
game_mode 2
game_type 1
```

Those are not Deadlock game rules. They may be ignored, rejected, or produce undefined behavior. Deadlock needs `CCitadelGameRules`, heroes, teams, and its own spawn/play-area logic.

Source 2 entity references checked during the sweep:

- `info_player_terrorist` / `info_player_counterterrorist`: CS2 team starts, one per CS2 player, at least 128 units apart from each other/walls.
- `trigger_teleport`: trigger volume that teleports touching entities to a remote destination.
- `trigger_hurt`: trigger volume that damages touching entities every half-second.
- `trigger_multiple`: trigger volume that fires repeatedly.

These entity classes exist in Source 2, but their gameplay meaning is game-specific. For Deadlock, relying on CS2 map triggers and CS2 server commands is unsafe. We should translate those into Deadlock-specific map entities or a Deadworks runtime plugin.

---

## Hammer / VMAP / compile process implications

`resourcecompiler.exe` compiles source assets from `content/...` into runtime resources under `game/...`. Compiled assets get `_c` suffixes or are packed into a map VPK. Source 2 Wiki's Resource Compiler docs confirm the general model:

- source assets must be under a content directory;
- compiled output is written for runtime use;
- `-novpk` can emit loose files instead of VPK;
- `-vpkincr` can update an existing VPK, but this can keep stale files if not carefully cleaned.

For maps, the source `.vmap` is a scene graph containing:

- world geometry / mesh streams;
- entity origins and properties;
- precomputed bounds/origins;
- parent/child relationships;
- references to materials, models, prefabs, triggers, volumes, etc.

Moving a Source 2 map correctly means moving **all coordinate-bearing source data before compile**, then recompiling map, physics, worldnodes, entity lump, and generated map VPK. Moving only `info_team_spawn` entities, or only mesh vertices, creates split/mixed worlds.

A robust transform must cover at least:

```text
CMapEntity origin
local.origin if used by parented entities
precomputedobborigin
precomputedboundsmins / precomputedboundsmaxs
mesh position streams
point/volume origins for triggers/lights/particles/sound/probes
spawn/teleport targets/timer/checkpoint targets if retained
nav data or regenerate/remove old nav
world physics via recompile
worldnodes via recompile
```

The live nested VPK must always be the source of truth after compile. Source files alone are not enough.

---

## Why the red/error map could be playable while the textured map is not

These are separate axes:

### Red/error but physically playable

Likely state:

- the original compiled CS2 map/world physics loaded;
- collision and some CS2 triggers still existed;
- materials were missing, so everything rendered red/checker/error;
- Deadlock was not fully happy with gameplay bounds/death areas, but the pawn/camera could still physically interact enough to feel playable.

### Textured/visible but not playable

Likely state now:

- materials are compiled and mounted, so visuals improved;
- stale worldnodes were removed, so visual package is cleaner;
- the start was moved near origin, but the whole course now extends far positive (`x~24k`);
- Deadlock spawn/play-area logic is still invalid;
- current runtime falls into out-of-play correction/death loop.

So visuals and playability are not the same problem. The material pass fixed only asset resolution. The spawn/play pass is still wrong.

---

## Current root-cause ranking

### 1. We are not getting a stable alive hero pawn at a deterministic course start

Evidence:

```text
Loaded hero 356/hero_werewolf
C_BasePlayerPawn::OnPostPredictionError prediction distance 1350.774 - teleporting
Player ... is out of the play area
```

The screenshot position is below the map and the game clock/UI are not in a normal running state. That is a spawn lifecycle failure, not merely a camera angle issue.

### 2. We centered the wrong thing

We moved the CS2 **start** close to origin, not the **whole map**. The current course is:

```text
x: -104 .. 23896
y: -1400 .. 13736
z: -2720 .. 264
```

A whole-map-centered transform would use approximately:

```text
translate x by -11896
translate y by -6168
```

Then geometry becomes roughly:

```text
x: -12000 .. 12000
y: -7568 .. 7568
z: unchanged, or optionally shifted separately
```

The start would no longer be near world origin; it would be near:

```text
current start: 120 -24 192
centered start: about -11776 -6192 192
```

That is fine if the spawns are deliberately placed there and the play boundary surrounds the centered course. The goal is not "spawn at origin". The goal is "entire course inside a sane coordinate envelope, and spawn at the real start platform."

### 3. Current coordinate envelope causes network-origin warnings

Deadlock already shows official-map logs with `CNetworkOriginCellCoordQuantizedVector` warnings in some situations, so the warning is not always instant-fatal. However, our custom map has avoidable large positive entity origins (`x=24529`, lights >16k, boundary >24k). Those should be eliminated.

### 4. Map-only spawn shell is probably insufficient for deterministic testing

Deadlock can choose/randomize heroes and spawns through `hero_testing_controller` and game state. Current log loaded `hero_werewolf`, not the intended `hero_viscous` shell. The runtime plugin, if used, also currently has a flaw: it records CS2 spawn entities, but the movement shell stripped them, and it teleports only once after 2 seconds. The hero in the log loaded around 5-6 seconds after map activation, so the one-shot teleport can easily no-op before a pawn exists.

The deterministic solution needs a repeated or event-driven runtime correction:

- force team/hero;
- wait until `GetHeroPawn()` exists;
- teleport to a known `bhop_course_start` point;
- zero velocity;
- retry for several seconds after full connect / hero load / death / out-of-play.

### 5. CS2 death/teleport/timer areas are not yet translated

CS2 `trigger_hurt`, `trigger_teleport`, `trigger_multiple`, `point_servercommand`, and checkpoint/timer names should be treated as source data for a Deadlock-specific runtime, not as entities we expect Deadlock to honor correctly.

---

## Recommended rebuild pipeline

### Phase 0: stop trusting contaminated tests

Before each test:

1. Stop `deadlock.exe`.
2. Delete or quarantine stale loose compiled folders and stale top-level map folders.
3. Install one active package only.
4. After install, extract live `pak71_dir.vpk` and nested `maps/bhop_emevaelx3.vpk`; inspect that extracted package, not source files.

### Phase 1: prove a minimal Deadlock-native shell

Create a tiny test map or clone the structure of `hero_testing`/`green_screen`:

- one floor at origin;
- exact copied `info_team_spawn` blocks from a working Deadlock map;
- exact copied `hero_testing_controller` pattern;
- two `citadel_minimap_boundary` corners;
- optional `rebels_vanguard_spawn` / `combine_vanguard_spawn` `info_target_server_only` anchors;
- no CS2 gameplay entities.

Verify this loads, gives a stable hero, clock advances, and movement works. If this fails, the problem is our Deadlock shell, not the CS2 course.

### Phase 2: center the entire imported course, not the start

Use current mesh AABB:

```text
mins = -104, -1400, -2720
maxs = 23896, 13736, 264
center = 11896, 6168, -1228
```

Apply a whole-map transform approximately:

```text
x -= 11896
y -= 6168
```

Do not hand-edit only the spawn points. Transform coordinate-bearing VMAP fields comprehensively, then compile from source.

Expected geometry after XY centering:

```text
x: -12000 .. 12000
y: -7568 .. 7568
```

This directly addresses the user's "actual entire map" requirement.

### Phase 3: choose spawn from actual start platform

The current start floor is around:

```text
x: -40 .. 280
y: -184 .. 136
z: 64
```

After whole-map centering, this becomes roughly:

```text
x: -11936 .. -11616
y: -6352 .. -6032
z: 64
```

Place Deadlock spawns around:

```text
course_start ~= -11776 -6192 192
```

Use multiple spawns, separated like official maps. Do not rely on a single arbitrary origin.

### Phase 4: copy exact working entity shapes

Do not keep generating approximate KeyValues until we know which keys Deadlock ignores/rejects. Copy known-good blocks from:

```text
/tmp/hero_testing_ents.txt
C:/Code/deadlock-map-porting/research/green_screen_ents.txt
C:/Code/deadlock-map-porting/research/pp_aero/nested_extract/maps/pp_aero/entities/default_ents.vents_c.txt
C:/Code/deadlock-map-porting/research/bhop_bubblegum_ents.txt
```

Then only change origins/team/lanenum where necessary.

Recommended initial shell:

```text
worldspawn mapUsageType = standard
citadel_minimap_boundary two XY corners around centered course
info_team_spawn team 2 and team 3, many copies, on start floor
info_team_spawn team 4 only if using MOG/lane-6 testing pattern
hero_testing_controller near start
info_target_server_only rebels_vanguard_spawn near start
info_target_server_only combine_vanguard_spawn near start
```

### Phase 5: add runtime deterministic spawn fallback

Map-only spawn will probably remain brittle while we are using Deadlock testing/game rules. The Deadworks runtime should:

- store a configured start position, not depend on stripped CS2 `info_player_*` entities;
- use a named `info_target_server_only` like `bhop_course_start` if possible;
- retry teleport until a hero pawn exists;
- run again after hero change, death, and out-of-play symptoms;
- zero velocity;
- log every forced spawn with old/new position.

### Phase 6: reimplement CS2 kill/teleport/timer logic

Treat CS2 triggers as data:

- `trigger_hurt` / kill zones -> Deadlock plugin fall/kill/respawn volumes or controlled `trigger_multiple` touch callbacks;
- `trigger_teleport` -> plugin teleport to named destination;
- timer start/end/checkpoints -> plugin timer state;
- `point_servercommand` -> Deadlock cvars/plugin config only.

Also make `materials/tools/toolstrigger.vmat_c` invisible or strip trigger visual meshes, because source trigger surfaces should not be rendered as visible geometry.

---

## External sources checked

Web search/fetch was done through DuckDuckGo/direct HTTP because the built-in search tool failed. Useful sources:

- Source2 Wiki, Resource Compiler: `https://www.source2.wiki/EngineTools/ResourceCompiler`
  - confirms `resourcecompiler.exe`, source assets under content directory, compiled runtime `_c` output, VPK/loose options.
- Source2 Wiki, `trigger_hurt`: `https://www.source2.wiki/Entities/trigger_hurt`
  - trigger volume damages touching entities every half-second.
- Source2 Wiki, `trigger_teleport`: `https://www.source2.wiki/Entities/trigger_teleport`
  - trigger volume teleports touching entities to a remote destination.
- Source2 Wiki, `trigger_multiple`: `https://www.source2.wiki/Entities/trigger_multiple`
  - reusable trigger volume.
- Source2 Wiki, `info_player_terrorist` / `info_player_counterterrorist`:
  - CS2-specific team start entities; one per team member, placed with spacing.
- CounterStrikeSharp docs for `CNetworkOriginCellCoordQuantizedVector`: `https://docs.cssharp.dev/api/CounterStrikeSharp.API.Core.CNetworkOriginCellCoordQuantizedVector.html`
  - exposes cell X/Y/Z and OutsideWorld fields, matching the console warning type.
- Deadlock forum thread with similar `CNetworkOriginCellCoordQuantizedVector` warnings: `https://forums.playdeadlock.com/threads/whole-match-red-dot-very-bad-hit-reg.8454/`
  - shows Deadlock itself can emit these warnings for large/out-of-cell unit overlay origins; correlated with bad client state.
- ValveResourceFormat project: `https://github.com/ValveResourceFormat/ValveResourceFormat`
  - Source 2 VPK/resource viewer/decompiler supporting maps/materials/models/entity lumps.
- ONE Esports custom Deadlock map guide: `https://www.oneesports.gg/gaming/custom-deadlock-maps-how-to-play-guide/`
  - confirms custom Deadlock maps are launched via `map <name>` and installed into Deadlock map/addon paths.
- Deadlock Mod Manager pages for known custom maps:
  - `https://deadlockmods.app/mod/659570` pp_aero
  - `https://deadlockmods.app/mod/667411` MOG BHOP maps
  - `https://deadlockmods.app/mod/670124` Green Screen Map
  - `https://deadlockmods.app/mod/669781` Map Timers Base

---

## Bottom line

We should stop treating this as one more spawn-coordinate tweak. The evidence says:

1. The package now renders.
2. The pawn is entering a Deadlock out-of-play/prediction correction loop.
3. The current map is centered incorrectly: start near origin, far course at +24k.
4. Deadlock-native spawn/gameplay entities need to be copied from working maps and backed by a runtime deterministic spawn fallback.
5. CS2 triggers/timers/kill boxes must be translated, not trusted directly.

The next implementation should rebuild from a known-good Deadlock shell, center the **entire** course around origin, then force spawn at the real centered start platform.
