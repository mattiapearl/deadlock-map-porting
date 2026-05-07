# movementmap.rar vs current bhop_emevaelx3 port comparison

Date: 2026-05-03

## Artifacts inspected

Working reference archive:

```txt
C:/Users/User/Downloads/movementmap.rar
```

Extracted research workspace:

```txt
C:/Code/deadlock-map-porting/research/movementmap/
```

Current non-working package compared:

```txt
C:/Code/deadlock-map-porting/exports/bhop_emevaelx3_deadlock_test_20260502_234856.zip
C:/Code/deadlock-map-porting/tmp_live_hideout_zone_verify/default_ents.txt
```

## Package layout differences

### movementmap.rar

`movementmap.rar` contains two top-level VPKs:

```txt
pak03_dir.vpk  6,863,018 bytes
pak04_dir.vpk  101,194,511 bytes
```

`pak03_dir.vpk` is not map geometry. It is a global gameplay/script override VPK:

```txt
scripts/heroes.vdata_c
scripts/abilities.vdata
cache_209848250.soc
```

`pak04_dir.vpk` is the actual map/content VPK:

```txt
sounds/vo/forge/forge_ally_astro_killed_in_lane_01.vsnd_c
sounds/aintnostoppingusnow.vsnd_c
soundevents/new_player_vo.vsndevts_c
materials/skybox/*.vtex_c
materials/default/*.vtex_c
materials/*.vtex_c
materials/skybox/*.vmat_c
materials/*.vmat_c
maps/movementmap.vpk
cache_209848250.soc
```

Nested `maps/movementmap.vpk` is small and complete:

```txt
9,372,454 bytes
```

It contains expected compiled Source 2 map resources:

```txt
maps/movementmap/world.vwrld_c
maps/movementmap/world.vrman_c
maps/movementmap/world_visibility.vvis_c
maps/movementmap/worldnodes/*.vwnod_c
maps/movementmap/worldnodes/*.vrman_c
maps/movementmap/worldnodes/*.vmdl_c
maps/movementmap/world_physics.vmdl_c
maps/movementmap/world_physics.vrman_c
maps/movementmap/lightmaps/*.vtex_c
maps/movementmap/entities/default_ents.vents_c
maps/movementmap.vmap_c
maps/movementmap.nav
```

### current bhop_emevaelx3 export

The current export contains:

```txt
addons/pak71_dir.vpk                                      153,834,231 bytes
citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vpk 86,708,334 bytes
citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.los  8,933,716 bytes
README_INSTALL_TEST.txt
SHA256SUMS.txt
docs/compile_bhop_emevaelx3_hideout_zone_test.log
docs/PORTING_FINDINGS.md
```

`pak71_dir.vpk` also contains `maps/bhop_emevaelx3.vpk`, so the loose addon copy can shadow the addon VPK copy if stale.

Current nested `maps/bhop_emevaelx3.vpk` is also structurally complete and has the expected resources:

```txt
maps/bhop_emevaelx3/world.vwrld_c
maps/bhop_emevaelx3/world.vrman_c
maps/bhop_emevaelx3/world_visibility.vvis_c
maps/bhop_emevaelx3/worldnodes/*.vwnod_c
maps/bhop_emevaelx3/worldnodes/*.vrman_c
maps/bhop_emevaelx3/worldnodes/*.vmdl_c
maps/bhop_emevaelx3/world_physics.vmdl_c
maps/bhop_emevaelx3/world_physics.vrman_c
maps/bhop_emevaelx3/lightmaps/*
maps/bhop_emevaelx3/entities/default_ents.vents_c
maps/bhop_emevaelx3.vmap_c
maps/bhop_emevaelx3.nav
```

Conclusion: the **current** bhop package is no longer failing because `world.vwrld_c`/`world.vrman_c` is missing. That older failure was stale loose-addon shadowing. The current failure is runtime behavior after spawn.

## Global script/data differences

This is one of the biggest differences.

`movementmap` ships a separate `pak03_dir.vpk` with:

```txt
scripts/heroes.vdata_c
scripts/abilities.vdata
```

`heroes.vdata_c` resource name is `heroes.vdata`; `resourceinfo` shows it was compiled from/searches under:

```txt
citadel_addons/movementheroes
```

It contains 60 top-level keys, including:

```txt
hero_base
hero_inferno
hero_gigawatt
...
hero_viscous
...
```

Example `hero_viscous` data in the movementmap override:

```txt
m_bPlayerSelectable = true
m_HeroID = 35
m_strModelName = resource_name:"models/heroes_staging/viscous/viscous.vmdl"
m_mapStartingStats:
  EMaxMoveSpeed = 7.3
  ESprintSpeed = 2.0
  ECrouchSpeed = 4.75
  EMoveAcceleration = 4
  EStamina = 1
  EGroundDashDistanceInMeters = 10.0
  EGroundDashDuration = 0.68
  EAirDashDistanceInMeters = 8.0
  EAirDashDuration = 0.47
```

`abilities.vdata` is plain text KV3, about 6.8 MB, and overrides many ability/weapon/movement-related definitions.

The current bhop export does **not** ship equivalent `scripts/heroes.vdata_c` or `scripts/abilities.vdata` overrides.

Likely impact:

- These script overrides are unlikely to be required for loading `world.vwrld_c`, but they can be required for the same hero selection/spawn/movement behavior as movementmap.
- They can mask/default hero data issues on custom maps.
- They likely tune movement behavior, stamina, dash/slide, weapon slowdown, etc.
- If our map relies only on stock Deadlock data while movementmap relies on custom global data, they are not equivalent runtime environments.

Recommended test: install movementmap's script VPK alongside our bhop map, or build our own minimal script override, and retest. This is a high-value A/B test, but the script override is broad/global and should be treated as risky outside a test install.

## Entity-lump differences

### Class counts

movementmap entity class counts:

```txt
1  env_sky
2  func_button
15 info_team_spawn
4  info_teleport_destination
2  light_environment
1  point_servercommand
19 point_worldtext
1  snd_event_point
7  trigger_teleport
1  worldspawn
```

current bhop entity class counts:

```txt
2  citadel_trigger_suspend_modifier
1  env_combined_light_probe_volume
1  env_sky
2  hero_testing_controller
2  info_team_spawn
1  light_environment
44 light_omni2
2  trigger_modifier
1  worldspawn
```

### Spawns

movementmap has 15 spawns, spread around its start area:

```txt
team 2: 237.072021 785.998352 -3847.000000
team 3: 256.000000 640.000000 -3840.000000
team 3: 9.029205 735.688171 -3897.000000
team 3: 35.391083 443.185303 -3897.000000
team 3: 209.506546 468.559418 -3897.000000
...
```

The entities are plain `info_team_spawn` with:

```txt
grouptag = 0
initialspawn = false
teamnumber = "2" / "3"
lanenum = "0"
```

current bhop has only 2 spawns:

```txt
team 2 info_team_spawn -14952 -13856 81
team 3 info_team_spawn -14992 -13784 81
```

and includes extra keys:

```txt
hero_model = "hero_viscous"
priority = "0"
enabled = "1"
```

Likely impact:

- Two spawns are enough for a one-person test, so this does not explain a solo player loading and then dying.
- It is still fragile for a server/custom lobby because FGD says 6 per team is typical and spawns should be spaced at least 128 units apart.
- `hero_model` is documented in `citadel.fgd` as only a reference-scale model, not required gameplay data. movementmap does not use it.

### hero_testing_controller

current bhop includes two `hero_testing_controller` entities. movementmap includes none.

`citadel.fgd` says:

```txt
hero_testing_controller: Enables Hero Testing Features in any map it is placed on.
```

Likely impact:

- This can alter sandbox/testing behavior.
- It is not present in the working movementmap reference, so it should be considered non-essential and removable for a clean movement-map baseline.
- It does not directly explain native `out of play area` damage, but it is an unnecessary variable.

### Trigger volumes

movementmap has real brush triggers. Example:

```txt
classname = "trigger_teleport"
origin = "752.144226 768.000000 -3776.000000"
model = "maps/movementmap/entities/unnamed_29.vmdl"
```

Nested `maps/movementmap.vpk` contains the matching trigger model resources:

```txt
maps/movementmap/entities/unnamed_29.vmdl_c
maps/movementmap/entities/unnamed_378.vmdl_c
maps/movementmap/entities/unnamed_380.vmdl_c
maps/movementmap/entities/unnamed_395.vmdl_c
maps/movementmap/entities/unnamed_460.vmdl_c
maps/movementmap/entities/unnamed_1041.vmdl_c
maps/movementmap/entities/unnamed_1042.vmdl_c
maps/movementmap/entities/unnamed_1050.vmdl_c
maps/movementmap/entities/unnamed_1052.vmdl_c
```

current bhop hideout-zone test entities are point-form only:

```txt
classname = "trigger_modifier"
origin = "-14952 -13856 81"
modifier_name = "modifier_citadel_in_hideout_zone"
# no model key

classname = "citadel_trigger_suspend_modifier"
origin = "-14952 -13856 81"
modifier_name = "modifier_citadel_in_hideout_zone"
# no model key
```

`citadel.fgd` explicitly defines `trigger_modifier` as:

```txt
@SolidClass base(Trigger, Targetname,TeamNumber, EnableDisable) = trigger_modifier
```

Official `dl_hideout` also uses a model-backed volume:

```txt
classname = "citadel_trigger_suspend_modifier"
modifier_name = "modifier_citadel_in_hideout_zone"
model = "maps/dl_hideout/entities/unnamed_56930.vmdl"
```

Likely impact:

- This is a confirmed break in our hideout-zone attempt: point-form `trigger_modifier` / `citadel_trigger_suspend_modifier` has no volume, so it cannot reliably touch/apply anything.
- A real compiled brush/model trigger is required if we want a map-side modifier zone.
- This explains why the point-form hideout test did not stop native out-of-play/environmental damage.

### Teleport/buttons/worldtext

movementmap has movement-course QoL entities:

```txt
trigger_teleport
info_teleport_destination
func_button
point_servercommand
point_worldtext
snd_event_point
```

current bhop has none of those from the original CS2 map because most CS2 gameplay entities were stripped.

Likely impact:

- Missing timers/checkpoints are not current priority.
- Missing teleport/reset triggers may matter for course usability but do not explain instant native environmental death immediately after spawn.

## Coordinate/play-area differences

movementmap spawn/entity origin AABB:

```txt
min: -2083.574463 -4454.855469 -3965.352539
max:  3328.000000  1306.622314     0.000000
```

movementmap player spawns are close to the map origin in XY:

```txt
x roughly -390..256
y roughly  410..1113
z roughly -3897..-3840
```

current bhop entity origin AABB:

```txt
min: -15049 -14912 -1248
max:   7072      0   256
```

current bhop spawns are far in negative XY:

```txt
-14952 -13856 81
-14992 -13784 81
```

Physics/visual bounds are both structurally valid and large:

```txt
movementmap world_physics sample bounds:
  min -16000.032227 -16320.031250 -4032.031250
  max  16000.030273  16640.031250  -447.968750

bhop world_physics sample bounds:
  min -15104.031250 -15200.031250 -2720.031250
  max   8896.031250    -63.968750   264.031250
```

Likely impact:

- The current log symptom is native Deadlock runtime behavior:

```txt
Player ... is out of the play area
#Citadel_DamageType_CLASS_DAMAGETYPE_ENVIRONMENTAL
```

- movementmap proves a tiny 232-byte nav is not fatal, but it does **not** prove arbitrary spawn coordinates are safe.
- bhop spawns at about `x=-15k, y=-14k`, which is outside/near the edge of known official practical play regions and much farther from origin than movementmap's course start.
- Earlier broad `citadel_minimap_boundary` tests did not fix this, so the native play-area check probably does not use only the point-form minimap boundary entities, or there are additional runtime/nav/lane/game-mode rules.
- Moving only the spawn is not enough if it puts the player in empty space. A valid test would translate the whole bhop geometry and all gameplay entities together so the playable course start is near movementmap's coordinate style.

## Nav differences

No meaningful nav difference for the current bug:

```txt
movementmap.nav      232 bytes
bhop_emevaelx3.nav   232 bytes
```

Likely impact:

- This strongly de-prioritizes `point_nav_walkable` / nav generation for the immediate free-roam problem.
- movementmap works with the same tiny placeholder-sized nav.

## Material/resource differences

movementmap is simple:

- 35 external refs in `movementmap.vmap_c`.
- Few custom materials/sounds.
- Entity VMDLs for brush triggers/buttons.

current bhop is much larger:

- 76 external refs in `bhop_emevaelx3.vmap_c`.
- Many material refs.
- Light probe/cubemap baked resources.
- No model-backed modifier/hideout trigger entities.

Likely impact:

- Missing/bad materials affect visuals/checkerboards/lighting, not instant native environmental death.
- The map currently loads and spawns, so resource completeness is no longer the primary failure.

## Differences most likely to break loading/behavior

High confidence:

1. **Point-form modifier/hideout triggers are invalid for the intended purpose.**
   - `trigger_modifier` is a SolidClass.
   - Official hideout uses `model = maps/dl_hideout/entities/unnamed_56930.vmdl`.
   - movementmap trigger entities also all have model-backed volumes.
   - Our point entities have no volume, so they cannot create a real zone.

2. **The current bhop package runs without movementmap's global hero/ability script VPK.**
   - movementmap's working runtime is not just a map VPK; it includes global `scripts/heroes.vdata_c` and `scripts/abilities.vdata` overrides.
   - Our bhop package does not.
   - This can affect hero spawning, hero validity, movement tuning, and whether the same map works in a bare client/server runtime.

3. **The bhop start is very far from movementmap's working start coordinates and native runtime is killing the player as out-of-play.**
   - The exact death reason is native Deadlock out-of-play/environmental damage.
   - movementmap starts players close to origin; bhop starts around `-15k, -14k`.
   - Boundary/nav tests have not fixed it, so runtime damage blocking or translating the whole course toward a safe area are stronger next tests than more point entities.

Medium confidence:

4. **`hero_testing_controller` is an unnecessary variable.**
   - movementmap does not need it.
   - FGD says it enables sandbox controls.
   - Remove for a clean baseline unless specifically needed.

5. **Only two spawns are too few/too fragile for real multiplayer.**
   - Not the solo instant-death root cause, but should be fixed for scrims/customs.

Low confidence / mostly visual:

6. **Material/light/probe differences.**
   - Can break visuals/performance.
   - Not a good explanation for `CLASS_DAMAGETYPE_ENVIRONMENTAL` out-of-play death.

7. **Nav size.**
   - Both maps have 232-byte nav, so nav is not the immediate blocker.

## Recommended next A/B tests

1. Test bhop with movementmap's `pak03_dir.vpk` script override installed alongside it.
   - Goal: prove/disprove whether hero/ability data differences are required for stable spawn/free-roam.

2. Build a clean bhop entity baseline:
   - many `info_team_spawn` entities for team 2 and 3,
   - no `hero_testing_controller`,
   - no point-form fake trigger modifiers,
   - no timers/checkpoints.

3. Either:
   - translate the whole bhop map/course and all gameplay entities near a known-safe region, **or**
   - use Deadworks/runtime-side blocking of native environmental/out-of-play damage.

4. If staying map-side for hideout/free-roam, compile a real brush/model volume for:

```txt
classname = "citadel_trigger_suspend_modifier"
modifier_name = "modifier_citadel_in_hideout_zone"
model = "maps/<map>/entities/<compiled_volume>.vmdl"
```

Do not rely on point-form `trigger_modifier` for this.
