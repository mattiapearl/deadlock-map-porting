# CS2/Source2 Maps -> Deadlock Porting Findings

## Inputs inspected

- Translated map package: `C:/Users/User/Downloads/bhop_emevaelx3_hammer.zip`
- CS2 workshop map package: `C:/Users/User/Downloads/730/3071726325/3071726325.vpk`
- Deadlock install used for dependency checks: `C:/Program Files (x86)/Steam/steamapps/common/Deadlock`

## Key finding

The practical way to make a CS2 map open in Deadlock is **not** to only copy the nested `maps/<map>.vpk`. CS2 workshop packages are usually a top-level VPK containing:

- `maps/<map>.vpk` — the compiled map container;
- `materials/.../*.vmat_c` and `*.vtex_c` — material/texture resources the map references;
- models/sounds/postprocess/cfg files.

Deadlock only sees resources mounted through its search paths. Therefore the referenced materials must be mounted in Deadlock too. Renaming/copying the **whole top-level VPK** into `game/citadel/addons/pakNN_dir.vpk` preserves those references.

## Produced staged addon VPKs

### Bhop_Colour / CS2 workshop package

Source VPK:

```text
C:/Users/User/Downloads/730/3071726325/3071726325.vpk
```

Staged Deadlock addon:

```text
C:/Code/deadlock-map-porting/staging/bhop_colour_deadlock_addon/pak70_dir.vpk
```

Try after install:

```text
map bhop_colour
```

This is a direct mount of the whole workshop VPK, so its top-level material/model/sound resources stay available to the nested map VPK.

### bhop_emevaelx3 translated package

The zip contains both raw Hammer-ish resources and compiled VPKs:

- `bhop_emevaelx3.vpk`
- `bhop_emevaelx3_environment_prefab.vpk`
- `bhop_emevaelx3_prefab.vpk`

But the compiled map VPK references 36 material paths that are **not included** in the package, such as:

- `materials/stone_blocks_bugga/*.vmat`
- `materials/stonetiles/*.vmat`
- `materials/stoneblocks/*.vmat`
- `materials/stuccopack3/crash_bandicoot/*.vmat`
- `materials/logo/logo.vmat`
- `materials/skybox/sh_starry_sky.vmat`

Staged Deadlock addon with placeholder materials:

```text
C:/Code/deadlock-map-porting/staging/bhop_emevaelx3_deadlock_addon/pak71_dir.vpk
```

Try after install:

```text
map bhop_emevaelx3
```

The placeholder strategy preserves the missing CS2 material paths but fills them with compiled Deadlock material files, e.g. Deadlock stone/default/sky/tool materials. This should avoid missing-material checkerboards and maximize chance of loadability, but it is not visually faithful. For faithful visuals, we need the original VPK/addon that contains those exact `stone_blocks_bugga`, `stonetiles`, `stuccopack3`, and `logo` resources.

## Live Deadlock gameinfo enablement

The first invalid-map-name failure was because `game/citadel/addons` was not mounted in live Deadlock `gameinfo.gi`. Existing local addon VPKs can override Panorama because prior tooling patched gameinfo in some contexts; the current Steam install did not have the addon search path.

I stopped the running `deadlock.exe` process because it locked `gameinfo.gi`, backed up the file, and patched:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/gameinfo.gi
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/gameinfo.gi.bak_deadlock_map_porting_20260502
```

Added inside `SearchPaths`:

```text
Game                citadel/addons
AddonRoot           citadel/addons
OfficialAddonRoot   citadel/community_addons
Mod                 citadel
Write               citadel
```

Also added an `AddonConfig` block matching the Reduced_CSDK setup. Restart Deadlock after this patch before trying `map ...` again.

## CSDK project setup

Found local CSDK:

```text
C:/Users/User/Documents/Reduced_CSDK_12
```

Created source/compile project for the translated map:

```text
C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_emevaelx3_port
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_emevaelx3_port
```

Copied `bhop_emevaelx3.vmap` and the raw `maps/bhop_emevaelx3/` resource tree there. Added 36 placeholder source `.vmat` files so Hammer/resourcecompiler has material names to resolve.

Build-tested with the CS2-bin compiler, as CSDK README says GUIMapCompiler uses `bin_cs2` for maps:

```powershell
C:/Users/User/Documents/Reduced_CSDK_12/game/bin_cs2/win64/resourcecompiler.exe `
  -game C:\Users\User\Documents\Reduced_CSDK_12\game\citadel `
  -i C:\Users\User\Documents\Reduced_CSDK_12\content\citadel_addons\bhop_emevaelx3_port\maps\bhop_emevaelx3.vmap `
  -fshallow2 -pc
```

Result: compile succeeded and wrote:

```text
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

Log:

```text
C:/Code/deadlock-map-porting/csdk_compile_bhop_emevaelx3_bincs2.log
```

The normal CSDK `game/bin/win64/resourcecompiler.exe` failed with a particle schema mismatch; `game/bin_cs2/win64/resourcecompiler.exe` worked.

Created precompiled CSDK-style project for Bhop_Colour:

```text
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_colour_precompiled
```

This one has no source `.vmap`; it is a precompiled workshop package passthrough.

## Install commands

Conservative install, one addon at a time:

```powershell
python C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py install C:/Code/deadlock-map-porting/staging/bhop_colour_deadlock_addon/pak70_dir.vpk
python C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py install C:/Code/deadlock-map-porting/staging/bhop_emevaelx3_deadlock_addon/pak71_dir.vpk
```

This copies to:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/
```

Installed into local Deadlock addons on 2026-05-02:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak70_dir.vpk
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk
```

Hashes/size at install time:

```text
pak70_dir.vpk 279186368 bytes sha256 3a5b7ec1c86bee30...
pak71_dir.vpk 100699759 bytes sha256 30a26ee58b211bf9...
```

## Automated CS2 point-prefab fixups

Deadlock now discovers the custom maps, but CS2 maps can still immediately return to hideout with:

```text
NETWORK_DISCONNECT_CLIENT_NO_MAP (prefabs/misc/...)
```

`console.log` showed missing CS2 point-prefab map VPKs:

```text
maps\prefabs\misc\team_select.vpk
maps\prefabs\misc\terrorist_team_intro.vpk
maps\prefabs\misc\counterterrorist_team_intro.vpk
maps\prefabs\misc\end_of_match.vpk
```

Automation added:

```powershell
python C:/Code/deadlock-map-porting/tools/automate_map_port.py fix-compile-install
python C:/Code/deadlock-map-porting/tools/automate_map_port.py build-empty-prefabs bhop_colour_precompiled
```

Current results:

- `bhop_emevaelx3_port`: stripped `team_select` point-prefab from source `.vmap`, recompiled with CSDK `bin_cs2`, and reinstalled live addon.
- `bhop_colour_precompiled`: no source `.vmap` available, so generated tiny empty CSDK-built placeholder VPKs for the four referenced CS2 prefabs and reinstalled live addon.

Follow-up log review after the map loaded showed additional issues:

- both imported maps log `Unknown sub-version number` after `Created physics`, so some compiled physics/world resource is still not fully Deadlock-native;
- both maps spam `Missing info_target named rebels_vanguard_spawn` / `combine_vanguard_spawn`, meaning Deadlock-specific spawn/vanguard anchors are absent;
- `bhop_emevaelx3` repeatedly logs `Player ... is out of the play area`, so Deadlock gameplay bounds do not recognize the CS2 course as valid play space;
- `bhop_emevaelx3` first compile missed `maps/bhop_emevaelx3/worldnodes/node000_lr0_c1077_s_cb_mesh_mat0_9.vmdl_c`, which likely broke brush/entity collision/trigger mesh. Explicitly compiling that VMDL made the later map compile include lightmap resources and removed that missing-worldnode error;
- the source map has no lightmap resolution volume, so lighting quality remains suspect: `WARNING! No lightmap resolution volumes set for this geometry!`;
- map HUD/minimap integration is invalid: `materials/minimap/bhop_emevaelx3.vmat_c` missing and Panorama reports `flChildWidth = inf` for `HudMinimap`.

On 2026-05-02, explicitly compiled the missing `node000_lr0_c1077...vmdl`, recompiled `bhop_emevaelx3`, and reinstalled the live addon. This improved packaging but did not solve Deadlock gameplay bounds/spawn entities.

After retesting, both maps still showed the gameplay-layer failure: the match enters `GameInProgress`, then the player only gets a hero a few seconds later, the pawn is teleported, and `Player ... is out of the play area` spam starts. This is not a material/prefab packaging problem; the imported maps lack Deadlock-native play bounds and team spawns. Added automation command:

```powershell
python C:/Code/deadlock-map-porting/tools/automate_map_port.py fix-compile-install --inject-gameplay-entities
```

For source-backed maps this injects minimal `citadel_minimap_boundary`, `info_team_spawn`, and vanguard target anchors near the CS2 spawn. `bhop_emevaelx3_port` has been rebuilt with those entities in the CSDK game output, but live installation was intentionally deferred while `deadlock.exe` was still running to avoid file-lock/corrupt-addon issues.

For precompiled-only `bhop_colour`, built a tiny entity-lump patch map and repacked the original `bhop_colour.vpk` with only `maps/bhop_colour/entities/default_ents.vents_c` replaced. The patched CSDK addon VPK now also contains `citadel_minimap_boundary`, `info_team_spawn`, and vanguard target anchors. Original CSDK VPK backup:

```text
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_colour_precompiled/maps/bhop_colour.vpk.bak_gameplay_20260502_144653
```

This approach was still the wrong direction: it tried to coerce a CS2 map into stock Deadlock match rules. After comparing against `pp_aero`, the better model is a **Deadlock movement map shell**:

- package as `game/citadel/addons/pakNN_dir.vpk` or mounted addon with nested `maps/<map>.vpk`;
- preserve world geometry, compiled world physics, materials, lightmaps, and simple visual entities;
- discard CS2 gameplay entities (`info_player_*`, `trigger_teleport`, `point_servercommand`, `logic_auto`, etc.);
- add only Deadlock-native movement-map bootstrap entities:
  - `info_team_spawn` with `hero_model = "hero_viscous"`;
  - `hero_testing_controller`;
- defer timers/checkpoints/teleports to Deadlock-specific logic later.

Added automation:

```powershell
python C:/Code/deadlock-map-porting/tools/automate_map_port.py movement-shell <vmap> --keep-text --compile
```

`bhop_emevaelx3_port` has now been rebuilt and installed live with this pp_aero-style shell. The live entity lump verifies only `info_team_spawn` + `hero_testing_controller` remain from gameplay bootstrap; CS2 spawns/teleports/servercommand/logic were stripped.

Important correction after log review: the 15:29 test was still loading stale addon VPKs from `game/citadel/addons` because `Game citadel/addons` appears before the loose CSDK addon roots in `gameinfo.gi`. The stale files contained old map payloads and shadowed the rebuilt loose addons:

```text
game/citadel/addons/pak70_dir.vpk -> maps/bhop_colour.vpk
game/citadel/addons/pak71_dir.vpk -> maps/bhop_emevaelx3.vpk
```

Moved them out of the active addon search path:

```text
game/citadel/addons/unusedVPKs/pak70_dir.vpk.disabled_stale_map_port_20260502_153758
game/citadel/addons/unusedVPKs/pak71_dir.vpk.disabled_stale_map_port_20260502_153758
```

Retest after this move is required before interpreting hero/runtime behavior; previous test results were contaminated by stale VPK shadowing.

Backups created under:

```text
C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_emevaelx3_port/maps/*.bak_cs2_prefabs_*
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel_addons/*.bak_*
```

## Runtime/gameplay logic

The map logic is CS2-flavored. `bhop_emevaelx3` contains these entity/class references:

- `info_player_terrorist`
- `info_player_counterterrorist`
- `trigger_teleport`
- `info_teleport_destination`
- `logic_auto`
- `point_servercommand`
- `env_sky`
- `light_environment`

It also has CS2 server commands embedded in `point_servercommand`:

```text
sv_cheats 1; sv_enablebunnyhopping 1; sv_maxvelocity 99999; sv_staminamax 0; sv_staminalandcost 0; sv_staminajumpcost 0; sv_accelerate_use_weapon_speed 0; sv_staminarecoveryrate 60; sv_autobunnyhopping 1; sv_airaccelerate 1000; mp_roundtime 60; mp_freezetime 1; sv_falldamage_scale 0; impulse 101; sv_accelerate 255; sv_maxspeed 99999; game_mode 2; game_type 1
```

Do **not** rely on this for Deadlock. Deadlock may ignore some classes/commands or reject game-mode-specific logic. For a real bhop mode, use a Deadworks plugin to:

- force team/hero/spawn;
- set Deadlock movement cvars that actually exist;
- respawn/teleport players after death/fall;
- implement checkpoints and finish triggers from entity touches;
- optionally disable NPC/objective systems.

## Runtime shim plugin

Created and build-verified:

```text
C:/Code/deadlock-map-porting/plugins/DeadlockBhopRuntime/DeadlockBhopRuntime.csproj
C:/Code/deadlock-map-porting/plugins/DeadlockBhopRuntime/BhopRuntimePlugin.cs
```

Build command:

```powershell
cd C:/Code/deadlock-map-porting/plugins/DeadlockBhopRuntime
dotnet build
```

Output:

```text
C:/Code/deadlock-map-porting/plugins/DeadlockBhopRuntime/bin/Debug/net10.0/DeadlockBhopRuntime.dll
```

It currently:

- applies Deadlock-side bhop-ish cvars;
- disables NPC spawning;
- forces a default team/hero for movement testing;
- records start/checkpoint-ish entity touches;
- supports `!r`, `!restart`, and `!cp`;
- teleports to checkpoint/start after death.

This is a first shim for geometry/openability validation, not a polished timer/checkpoint system yet.

## Programmatic tool

Created:

```text
C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py
```

Useful commands:

```powershell
# Stage direct CS2 workshop VPK as Deadlock addon
python C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py stage-workshop-vpk

# Stage bhop_emevaelx3 with placeholder Deadlock materials
python C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py stage-emevael

# Scan arbitrary files/folders for materials/entities/commands
python C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py audit <paths...>

# Install a staged addon VPK into local Deadlock
python C:/Code/deadlock-map-porting/tools/stage_deadlock_map_port.py install <pakNN_dir.vpk>
```

## Next validation step

Install only one staged VPK, launch Deadlock/Deadworks with `-console -dev -insecure`, run `map <name>`, and capture `game/bin/win64/console.log` / crash output. The next fixes should be driven by actual missing-resource/class errors from that log, not guesses.

## 2026-05-02 actual-map coordinate-space rebuild

After the root-cause sweep, `bhop_emevaelx3` was rebuilt using the **actual imported map mesh coordinate space**, not a spawn-centered approximation.

Measured source mesh AABB before recentering:

```text
mins:   -104 -1400 -2720
maxs:  23896 13736   264
center: 11896 6168 -1228
```

Applied XY-only full-map recenter:

```text
delta: -11896 -6168 0
```

Resulting actual mesh AABB:

```text
mins: -12000 -7568 -2720
maxs:  12000  7568   264
```

Rebuilt the Deadlock movement shell with start/spawn in the recentered course coordinates:

```text
bhop_course_start:       -11776 -6192 224
rebels_vanguard_spawn:   -11776 -6192 224
combine_vanguard_spawn:  -11648 -6192 224
info_team_spawn team 2:  -11720 -6320 208
info_team_spawn team 3:  -11760 -6248 208
info_team_spawn team 4:  -11824 -6248 208
hero_testing_controller: -11800 -6370 200
hero_testing_controller: -11817 -6369 204
citadel_minimap_boundary corners:
  -12512 -8080 192
   12512  8080 192
```

Tooling added:

```powershell
python C:/Code/deadlock-map-porting/tools/automate_map_port.py recenter-map <vmap> --axes xy --keep-text
python C:/Code/deadlock-map-porting/tools/automate_map_port.py movement-shell <vmap> --spawn -11776 -6192 192 --hero viscous --keep-text --compile
```

The recenter command transforms coordinate-bearing VMAP fields only: entity origins, local origins, precomputed bounds/origins, and polygon mesh position streams. It intentionally does not translate normals, colors, scales, or qangles.

Compiled successfully:

```text
C:/Code/deadlock-map-porting/logs/compile_bhop_emevaelx3_20260502_184435.log
C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

Installed live addon:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk
```

Live backup:

```text
pak71_dir.vpk.bak_before_actual_map_center_20260502_185137
```

Live verification:

- outer `pak71_dir.vpk` contains `maps/bhop_emevaelx3.vpk`
- outer package has `0` stale top-level `maps/bhop_emevaelx3/*` files
- nested `default_ents.vents_c` contains the recentered boundaries, spawns, hero testing controllers, and vanguard/start anchors listed above

Next test:

```text
map bhop_emevaelx3
```

## 2026-05-02 spawn-inside-start-pad patch

User retested the actual-map-centered package: game starts and hero spawns, but dies immediately because spawn bootstrap is still not on/in the playable map.

Root cause found in generated shell: pp_aero-style `hero_testing_controller` offsets placed controllers just outside the small `bhop_emevaelx3` start pad. The real start pad vertices are around:

```text
x: -11936 .. -11616
y: -6352 .. -6032
floor z: 64
```

Patched movement shell generation to keep all bootstrap entities inside this pad and lowered spawn Z closer to the floor:

```text
citadel_minimap_boundary:
  -12512 -8080 80
   12512  8080 80
bhop_course_start:      -11776 -6192 112
rebels_vanguard_spawn:  -11776 -6192 112
combine_vanguard_spawn: -11648 -6192 112
team 2 spawn:           -11824 -6240 96
team 3 spawn:           -11728 -6240 96
team 4 spawn:           -11776 -6144 96
hero_testing_controller -11776 -6192 88
hero_testing_controller -11744 -6160 92
```

Compiled successfully:

```text
C:/Code/deadlock-map-porting/logs/compile_bhop_emevaelx3_20260502_185742.log
```

Installed live:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk
```

Live backup:

```text
pak71_dir.vpk.bak_before_spawn_in_pad_20260502_190517
```

Next retest:

```text
map bhop_emevaelx3
```

## 2026-05-02 research/test pass: Pulse, nav seeds, broad bounds

User requested deeper research and tests. Findings:

- The apparent `ok` screenshot at `1668 9922 2117` should not be dismissed as source-AABB-invalid; it is an empirical in-game camera/play coordinate. However previous console evidence around that moment showed `dl_hideout`, so screenshots must always be tied to the current loaded map in `console.log`.
- Official/custom Deadlock maps use Pulse (`point_pulse` + `.vpulse`) for map logic. `pp_aero` has `point_pulse` with `graph_def = scripts/vscripts/timer.vpulse`; official maps have `pulse/maps/*.vpulse` graphs.
- Server/client strings prove relevant native systems/classes:
  - `Player %s is out of the play area`
  - `MODIFIER_STATE_IGNORE_OUT_OF_PLAY_AREA_CHECK`
  - `Citadel_Walkable`
  - `point_nav_walkable`
  - `CNavWalkable`
  - `CCitadelPlayerPawn::SelectSpawnSpot: couldn't find valid info_team_spawn, falling back to spawning at the world.`
- CSDK `base.fgd` defines `point_nav_walkable`: "Causes nav mesh to be generated here and at all points that are reachable via ground movement from here."
- Official `onelane` includes `point_nav_walkable` and broad `citadel_minimap_boundary` corners around y `11776` and `-12288`.

Applied test patch:

```text
citadel_minimap_boundary:
  -16000 -16000 -5000
   16000  16000  5000
point_nav_walkable:
  -10500 -5500 128
spawns/controllers unchanged from moved-in-map test:
  course_start           -10500 -5500 1552
  team 2 info_team_spawn -10548 -5548 1536
  team 3 info_team_spawn -10452 -5548 1536
  team 4 info_team_spawn -10500 -5452 1536
  hero_testing_controller -10500 -5500 1528
  hero_testing_controller -10468 -5468 1532
```

Compile now no longer says `NAVGEN: Skipped... no walkable seeds present`. It runs 31 navgen stages and produces polygons, proving the walkable seed is recognized. But the final nav remains tiny (`232 bytes`) after island removal / flowmap, so the seed alone may not create usable Citadel nav/flow space.

Compile log:

```text
C:/Code/deadlock-map-porting/logs/compile_bhop_emevaelx3_20260502_214206.log
```

Installed live after stopping Deadlock:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk
```

Backup:

```text
pak71_dir.vpk.bak_before_navseed_broadbounds_20260502_215449
```

Live verification confirms broad bounds + point_nav_walkable + spawns are in nested entity lump.

Next manual test:

```text
map bhop_emevaelx3
```

Immediately after test, inspect console for:

```text
Spawn Server: bhop_emevaelx3
Map: "bhop_emevaelx3"
Player ... is out of the play area
Created physics for bhop_emevaelx3
NAV / walkable / spawn messages
```

### Shadowing root cause for 2026-05-02 navseed failed load

User reported map no longer opened after navseed/broad-bound install. Console showed:

```text
Failed loading resource "maps/bhop_emevaelx3/world.vrman_c" (ERROR_FILEOPEN)
RESOURCE_TYPE_WORLD resource 'maps/bhop_emevaelx3/world.vwrld' requested but is not in the system
NETWORK_DISCONNECT_CREATE_SERVER_FAILED
```

The installed `pak71_dir.vpk` was valid and its nested `maps/bhop_emevaelx3.vpk` contained `world.vrman_c`, `world.vwrld_c`, etc. The actual cause was search-path shadowing by the live loose CSDK addon root:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

That loose map VPK was stale (`86819963` bytes, timestamp `17:45`) and was selected before/alongside the addon pak. It lacked/manifested resources differently, causing `world.vrman_c` file-open failure even though the pak71 nested map had the file.

Fix applied: stopped Deadlock and copied current compiled nested map VPK into the loose addon root too.

Backup:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk.bak_before_navseed_shadowfix_20260502_220026
```

Current loose map:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
87616113 bytes
```

Verification extracted from loose map confirms:

```text
maps/bhop_emevaelx3/world.vrman_c
maps/bhop_emevaelx3/entities/default_ents.vents_c
```

Important operational rule: live loose addon roots in `game/citadel_addons/*` can shadow `game/citadel/addons/pakNN_dir.vpk`. Keep both synchronized or disable one; otherwise logs can appear impossible because the pak contains a resource but the engine loaded a stale loose nested VPK instead.

### 2026-05-02 spawn/death loop correction: high spawn was bad, no CS2 death triggers remain

After the map-open shadowing fix, user reported the original spawn/die bug was back and the moved distance did not appear improved. Console confirms gameplay now loads but repeatedly logs:

```text
Player Caesar is out of the play area
#Citadel_DamageType_CLASS_DAMAGETYPE_ENVIRONMENTAL
```

This is Deadlock native out-of-play/environmental damage, not a CS2 `trigger_hurt`: live `default_ents.vents_c` has no `trigger_*`, `hurt`, `damage`, `teleport`, `logic_*`, or `point_servercommand` entities after stripping.

Important correction: current recentered mesh vertices near the tested spawn show real floor around `z=64`, not `z=1520`:

```text
near -10631 -5669: nearest vertices z=0/64, many within radius 256, top z=64
near -10500 -5500: nearest vertices z=0/64, with some nearby raised geometry z=256/264
```

So the previous `z=1536` spawn shell was indeed a bad point: it put `info_team_spawn` and `hero_testing_controller` far above the real floor and let the pawn fall back down. This explains why the visual distance did not feel improved.

Applied a floor-level test shell:

```text
point_nav_walkable      -10631 -5669 128
course_start            -10631 -5669 160
team 2 info_team_spawn  -10679 -5717 144
team 3 info_team_spawn  -10583 -5717 144
team 4 info_team_spawn  -10631 -5621 144
hero_testing_controller -10631 -5669 136
hero_testing_controller -10599 -5637 140
citadel_minimap_boundary remains broad: +/-16000 xy, +/-5000 z
```

Also fixed generated property casing to match official/pp_aero maps:

```text
lanenum       not LaneNum
initialspawn  not InitialSpawn
```

and added `point_nav_walkable` to the generated-shell stripping set so stale seeds are removed on each reinjection.

Compile still produces only a tiny nav (`232 bytes`) after island removal, so if this floor-level spawn still dies, the remaining root cause is likely not spawn height or CS2 death zones. It is likely that imported CS2 world geometry is not producing a usable Deadlock `Citadel_Walkable`/flow/nav island. Then next test should clone pp_aero's minimal shell more closely (possibly no minimap boundary, only 2 team spawns + hero controllers + point_pulse timer), or add proper Deadlock nav/walkable markup/geometry rather than relying on imported brush mesh.

Installed live synchronized to both search paths:

```text
game/citadel/addons/pak71_dir.vpk
game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

Live entity verification confirms only one `point_nav_walkable` and floor-level spawn/controller entities.

### 2026-05-02 permissive no-boundary/no-nav test installed

To test the hypothesis that the earlier error-mesh build allowed walking because Deadlock had no explicit custom play-area validation entities, installed a permissive shell:

Removed / absent in live verified entity lump:

```text
citadel_minimap_boundary
point_nav_walkable
trigger_*
trigger_hurt
trigger_teleport
logic_*
point_servercommand
```

Kept only bootstrap/player entities at the current recentered floor-level start area:

```text
course_start            -10631 -5669 160
rebels_vanguard_spawn   -10631 -5669 160
combine_vanguard_spawn  -10503 -5669 160
team 2 info_team_spawn  -10679 -5717 144
team 3 info_team_spawn  -10583 -5717 144
team 4 info_team_spawn  -10631 -5621 144
hero_testing_controller -10631 -5669 136
hero_testing_controller -10599 -5637 140
```

Compile intentionally returns to old behavior:

```text
NAVGEN: Skipped... no walkable seeds present
```

Compile log:

```text
C:/Code/deadlock-map-porting/logs/compile_bhop_emevaelx3_20260502_224638.log
```

Installed synchronized to both active search paths after stopping Deadlock:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

Live backup prefix:

```text
bak_before_permissive_no_boundary_20260502_2253xx
```

Manual test:

```text
map bhop_emevaelx3
```

Expected diagnostic:

- If walking works / out-of-play stops: `citadel_minimap_boundary`/`point_nav_walkable` validation path caused the death loop.
- If out-of-play continues even with no boundary/nav seed: Deadlock is using another native out-of-play source, probably game rules / hidden map defaults / hero-testing state, and we should restore the older pre-recenter package or clone the exact older entity shell coordinates rather than continuing to mutate the current recentered map.

### 2026-05-02 rollback to known earlier error-mesh/walkable package

The permissive no-boundary/no-nav mutation of the current recentered build did not change behavior. To remove all accumulated variables, restored the actual earlier package from the period when the user reported walking on the buggy/error-mesh map:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk.bak_before_material_repack_20260502_160800
```

Installed as live:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak71_dir.vpk
```

Also extracted its nested map VPK and synchronized loose shadowing path:

```text
C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

Live/current backup before rollback:

```text
pak71_dir.vpk.bak_before_restore_error_mesh_walkable_20260502_2256xx
bhop_emevaelx3.vpk.bak_before_restore_error_mesh_walkable_20260502_2256xx
```

Restored live verification:

- no `citadel_minimap_boundary`
- no `point_nav_walkable`
- no `trigger_*` / `hurt` / `logic_*` / `point_servercommand`
- old spawn shell:

```text
team 2 info_team_spawn  -14952 -13856 81
team 3 info_team_spawn  -14992 -13784 81
hero_testing_controller -15032 -13906 73
hero_testing_controller -15049 -13905 77
```

This is now an A/B test against the actual old artifact, not a reconstructed approximation. If this works, the breakage came from later map-coordinate/worldnode/package changes. If it still fails, the earlier walking state depended on some other live state/search-path/cache/addon not captured by the pak71 backup.

### 2026-05-02 hideout-zone modifier point-entity test installed

User asked to add the hideout/free-roam modifier idea. Built from the old-position source backup:

```text
bhop_emevaelx3.vmap.bak_deadlock_movement_shell_20260502_160244
```

Added four test entities at/above the old working spawn:

```text
trigger_modifier                  -14952 -13856  81  modifier_citadel_in_hideout_zone
trigger_modifier                  -14952 -13856 256  modifier_citadel_in_hideout_zone
citadel_trigger_suspend_modifier  -14952 -13856  81  modifier_citadel_in_hideout_zone
citadel_trigger_suspend_modifier  -14952 -13856 256  modifier_citadel_in_hideout_zone
```

Caveat: these are point-form test entities with no brush `model`, because creating a new proper SolidClass trigger brush programmatically in VMAP is nontrivial. Official `dl_hideout` uses `citadel_trigger_suspend_modifier` with a compiled brush model. This test determines whether either class has any useful effect without a model. If it does not, the next implementation must add/clone a real brush volume or use runtime/native damage blocking.

Compile log:

```text
C:/Code/deadlock-map-porting/logs/compile_bhop_emevaelx3_20260502_231308.log
```

Installed synchronized to:

```text
game/citadel/addons/pak71_dir.vpk
game/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk
```

Live verification confirms the four entities are present in the nested `default_ents.vents_c`.

Retest:

```text
map bhop_emevaelx3
```

### 2026-05-03 roam-fix build: real trigger volume + script override + corrected recenter

Implemented the three remaining high-signal fixes in the repeatable automation:

- translated actual bhop geometry by `+3104 +7632 0`, but fixed the translator so CMapMesh `origin`/`local.origin` are not double-applied;
- stripped CS2 gameplay/timer/teleport entities and generated a movementmap-style baseline: 20 plain `info_team_spawn` entities, no `hero_testing_controller`, no forced `hero_model`, no fake point-form trigger modifiers;
- cloned a real `CMapEntity`/`CMapMesh` trigger template from `content/citadel/maps/climbrope.vmap`, rewrote GUIDs/node IDs, resized it to cover the whole course, and retargeted it to:

```text
classname = citadel_trigger_suspend_modifier
modifier_name = modifier_citadel_in_hideout_zone
targetname = bhop_roam_hideout_volume
model = maps/bhop_emevaelx3/entities/bhop_roam_hideout_volume_26554.vmdl
```

Verification from the compiled nested map VPK:

```text
world_physics AABB: -12000.03125 -7568.03125 -2720.03125 -> 12000.03125 7568.03125 264.03125
hideout volume:     -13024 -8592 -5000 -> 13024 8592 5000
entity classes:     20 info_team_spawn, 1 citadel_trigger_suspend_modifier, 0 trigger_modifier, 0 hero_testing_controller
nav:                232 bytes; no point_nav_walkable seed, matching movementmap-style tiny nav behavior
```

Current corrected compile log:

```text
C:/Code/deadlock-map-porting/logs/compile_bhop_emevaelx3_20260503_005550.log
```

Built a clean external test package that avoids duplicate shadowing paths and includes the movementmap script override as a separate addon VPK:

```text
C:/Code/deadlock-map-porting/exports/bhop_emevaelx3_roamfix_<timestamp>.zip
```

Package contents intentionally use only:

```text
game/citadel/addons/pak70_dir.vpk  # movementmap scripts/heroes + scripts/abilities override
game/citadel/addons/pak71_dir.vpk  # corrected recentered bhop map/content
```

It intentionally does **not** include `game/citadel_addons/bhop_emevaelx3_port/...`, because that loose addon root previously shadowed the live `pak71_dir.vpk` and caused stale `world.vrman_c` load failures. The package also carries a roam-only Deadworks plugin fallback:

```text
game/bin/win64/managed/plugins/DeadlockBhopRuntime.dll
```

The plugin blocks pawn damage on bhop/movement maps and has no timers/checkpoints.
