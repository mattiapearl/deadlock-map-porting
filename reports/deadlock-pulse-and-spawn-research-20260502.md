# Deadlock Pulse / Spawn / Map Coordinate Research Notes

Date: 2026-05-02

## Corrected understanding from user screenshots

The user's `ok` screenshot is an empirical in-game coordinate sample above the map:

```text
pos: 1668.59 9922.59 2117.34
```

This must be treated as a real coordinate in Deadlock's loaded level context, not dismissed because it falls outside my previously computed polygon-vertex AABB. The computed mesh AABB is insufficient as the sole truth source for gameplay placement.

The spawn-cycle screenshot is a different state:

```text
pos: -10631.50 -5668.66 105.16
```

That corresponds to the injected spawn shell area, not the visually centered/over-map camera area.

Conclusion: the problem is not a tiny spawn offset. The gameplay shell is being built around a coordinate interpretation that does not match what the player observes in game.

## Important correction

Do not keep moving the entire map. The full-map recenter was done once. Later attempts moved only injected entities, but those entities were still derived from an incomplete model of map space.

The next pass should be empirical:

1. collect multiple in-game `pos` samples above/inside the visible map;
2. place play bounds and spawn using those samples;
3. validate live artifact after every install;
4. stop trusting source mesh AABB as gameplay-space center.

## Pulse research

Deadlock and newer Source 2 games use Pulse (`.vpulse`) for visual scripting.

Useful source found:

```text
https://github.com/LionDoge/vpulse-editor
```

The README defines `point_pulse` as:

```text
@PointClass base(Targetname) tags( Logic ) iconsprite("editor/point_pulse.vmat") = point_pulse : "An entity that acts as a container for pulse graphs"
[
    graph_def(string) : "Graph path" : "" :
]
```

Pulse assets are `.vpulse` and compile as KV3 resources. The tool warns that Deadlock/CSDK Pulse definitions can diverge because Deadlock updates frequently.

Deadlock Pulse bindings include `CCitadelPointPulseAPI` functions such as:

```text
SetFastCooldownsEnabled
SetFastStaminaEnabled
GetFastCooldownsEnabled
GetFastStaminaEnabled
```

This matters because Deadlock-native custom maps can use Pulse to coordinate map/game logic instead of CS2 `point_servercommand` or raw entity I/O.

## Working custom movement map evidence

`pp_aero` contains a Pulse-driven timer shell:

```text
classname = "point_pulse"
targetname = "[PR#]timer"
graph_def = "scripts/vscripts/timer.vpulse"
```

It also uses:

```text
point_template
filter_activator_attribute_int
trigger_multiple / trigger_teleport style course logic
info_team_spawn
hero_testing_controller
```

So a working Deadlock parkour/movement map is not only `info_team_spawn + hero_testing_controller`; Pulse participates in the logic stack.

## Official Deadlock Pulse evidence

GameTracking Deadlock contains official Pulse files such as:

```text
pulse/maps/hideout_sandbox.vpulse
pulse/maps/prefabs/gameplay/small_route.vpulse
```

These are `ServerEntity` domain graphs attached to `point_pulse`. They use:

```text
CPulseCell_Inflow_GraphHook: CPulseGraphInstance_ServerEntity::GraphStart
CPulseCell_Inflow_Method
CPulseCell_Inflow_EntOutputHandler
CPulseCell_Step_EntFire
```

Official logic also uses `CCitadelPointPulseAPI` for Deadlock-specific operations.

## Immediate implications for bhop_emevaelx3

1. The current imported map renders and can start a game, so packaging/graphics are no longer the dominant issue.
2. The kill/spawn cycle is a Deadlock gameplay-shell issue.
3. The shell should be modeled after a working parkour map (`pp_aero` or MOG BHOP), including Pulse where needed.
4. The shell's boundary/spawn coordinates should be based on empirical in-game samples, not only on source mesh vertices.
5. `citadel_minimap_boundary` should be expanded enough to include the user's over-map coordinate (`y≈9922`) before further spawn tests.
6. The compile log still reports no walkable seeds; this may be part of Deadlock's out-of-play validation.

## Proposed next technical pass

### A. Coordinate calibration

Ask the user for or collect 3-5 in-game `pos` samples:

```text
- above visible map center
- above intended spawn/start
- over a known solid floor
- map far left/right/front/back as viewed in spectator/flycam
```

Use those to define the Deadlock gameplay envelope.

### B. Expand play boundary from empirical space

Temporary broad test envelope:

```text
citadel_minimap_boundary min: -16000 -16000 -5000
citadel_minimap_boundary max:  16000  16000  5000
```

This is intentionally oversized to determine whether the death loop is caused by boundary clipping.

### C. Clone working Pulse shell

From `pp_aero`, preserve/copy the entity pattern around:

```text
point_pulse timer -> scripts/vscripts/timer.vpulse
point_template timer_template
filter_activator_attribute_int has_timer_filter
```

Then include the corresponding compiled `.vpulse_c` resources if available, or rebuild with `vpulse-editor` if source is needed.

### D. Stop treating CS2 triggers as gameplay

Keep CS2 trigger data as source references, but implement actual timer/teleport/kill-zone behavior with Deadlock-compatible Pulse or Deadworks runtime.
