# bhop_rose full-source recompile attempt - 2026-05-07

## Request

Try making `bhop_rose` with the upgraded `bhop_soulscape` pipeline. User allowed memory cap up to 28 GiB.

## Script upgraded

Copied the upgraded material classifier / postprocess / VMDL precompile / 28 GiB compile flow from soulscape into:

```txt
C:/Code/deadlock-map-porting/tools/full_recompile_bhop_rose_from_mapping_recipe.py
```

## Successful stages

The headless source process completed all pre-map-compile stages:

```txt
stage decompiled source into CSDK addon
material rewrite
source VMAP entity patch
material compile
postprocess compile
VMDL precompile
```

Material classification:

```txt
translucent_pbr: 1
enriched_pbr: 7
sky: 2
```

Aggregate decompile artifact removed:

```txt
id: 206c7370-b6c9-4804-9612-786b1bd4bb36
model: maps/bhop_rose/worldnodes/n0_lr0_c2_s_cb_mesh.vmdl
```

Deadlock shell inserted at origin:

```txt
-36 0 -60
```

Compiled individually:

```txt
10 VMATs OK
2 VPOSTs OK
60 VMDLs OK
```

## Blocking stage

Full map compile is blocked by memory at/just above the 28 GiB cap.

Runs attempted:

```txt
normal compile, 28 GiB:
C:/Code/deadlock-map-porting/logs/compile_bhop_rose_full_recompile_1778176367.log
[memlimit] peak observed: 28.41 GiB

-fshallow2, 28 GiB:
C:/Code/deadlock-map-porting/logs/compile_bhop_rose_full_recompile_fshallow2_28.log
[memlimit] peak observed: 28.06 GiB

-fshallow, 28 GiB:
C:/Code/deadlock-map-porting/logs/compile_bhop_rose_full_recompile_fshallow_28.log
[memlimit] peak observed: 28.19 GiB

-fshallow2, 28.2 GiB probe:
C:/Code/deadlock-map-porting/logs/compile_bhop_rose_full_recompile_fshallow2_28_2.log
[memlimit] peak observed: 28.54 GiB
```

I also tested a stripped-entity-model source variant to determine whether entity model refs were the main memory driver. It did not help:

```txt
C:/Code/deadlock-map-porting/logs/compile_bhop_rose_full_recompile_strip_entity_models_28.log
[memlimit] peak observed: 28.36 GiB
```

The staged VMAP was restored to the normal patched source after that diagnostic.

## Diagnosis

This is `FAILED_MEMORY_CAP`, not a material/entity/resource failure.

Evidence:

- all VMATs compile
- all VPOSTs compile
- all VMDLs compile
- dmxconvert source patch succeeds
- map compile dies from memlimit during early world build/loading, before a compiler content error

`bhop_rose` source is substantially heavier than `bhop_soulscape`:

```txt
bhop_rose patched KV2: ~22.2 MB, 507 CMapMesh, 96 CMapEntity
bhop_soulscape patched KV2: ~11.9 MB, 123 CMapMesh, 128 CMapEntity
```

## Current output state

No new live install was made for `bhop_rose`.

Staged addon exists but map compile failed:

```txt
content: C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_rose_full_recompile
work:    C:/Code/deadlock-map-porting/work/full_recompile_bhop_rose
```

## Options

1. Explicitly allow a higher cap, likely at least 30 GiB, and rerun. This is the cleanest path and preserves source geometry.
2. Build a geometry-slim/lite variant by removing or merging some `CMapMesh` geometry. This risks losing fidelity and should not be automatic.
3. Hybrid approach: use the existing preserved compiled `bhop_rose` world for runtime, and only replace materials/entity shell. This does not solve stale lightmap metadata.
4. Full source rebuild on a machine/session with more memory headroom.
