# DeadlockBhopRuntime

Deadworks runtime shim for imported CS2 bhop maps.

Build status: compiles against local `_research_deadworks` API snapshot.

```powershell
cd C:/Code/deadlock-map-porting/plugins/DeadlockBhopRuntime
dotnet build
```

Output:

```text
bin/Debug/net10.0/DeadlockBhopRuntime.dll
```

Purpose:

- apply Deadlock-side bhop-ish movement/server cvars;
- disable NPC spawning for imported course maps;
- force a default team/hero;
- collect start/checkpoint-ish entities as they spawn;
- support `!r` / `!restart` and `!cp`;
- teleport to checkpoint/start after death.

This does not replace proper map-specific trigger parsing. It is the first runtime shim so map geometry can be validated before deeper checkpoint/finish logic.
