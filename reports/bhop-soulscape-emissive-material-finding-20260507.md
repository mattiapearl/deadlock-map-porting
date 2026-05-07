# bhop_soulscape emissive material finding - 2026-05-07

User compared CS2 and Deadlock screenshots at spawn. The cyan/glowing cubes are visibly degraded in Deadlock: they are present and lit by scene light, but their material is not preserving the original full self-illuminated/glowing look.

## Root cause

The full-recompile script used a minimal generic rewrite for all `csgo_*` materials:

```kv2
"Layer0"
{
    "shader" "pbr.vfx"
    "TextureColor1" "<TextureColor>"
}
```

For normal opaque materials that is acceptable. For `rbx/glowing*.vmat`, it is lossy.

Original `materials/rbx/glowingblue.vmat` had:

```kv2
"shader" "csgo_complex.vfx"
"F_SELF_ILLUM" "1"
"g_flSelfIllumAlbedoFactor" "1"
"g_flSelfIllumBrightness" "1"
"g_flSelfIllumScale" "1"
"g_vSelfIllumTint" "[1.000000 1.000000 1.000000 0.000000]"
"TextureColor" "materials/rbx/glowingblue.png"
"TextureSelfIllumMask" "materials/rbx/glowingblue.png"
```

Current generated Deadlock VMAT dropped all self-illum fields:

```kv2
"shader" "pbr.vfx"
"TextureColor1" "materials/rbx/glowingblue.png"
```

Compiled current material confirms no useful self-illum authored params; it falls back to default `g_tSelfIllumMask` and has no self-illum scale/tint params.

## Affected soulscape materials

Detected original self-illum materials:

```txt
materials/rbx/glowingblue.vmat
materials/rbx/glowinggreen.vmat
materials/rbx/glowingornage.vmat
materials/rbx/glowingred.vmat
materials/rbx/glowingyellow.vmat
```

## Better replacement

Use an emissive-preserving PBR rewrite when original VMAT contains `F_SELF_ILLUM`, `TextureSelfIllumMask`, or self-illum params.

Compile-tested replacement shape:

```kv2
Layer0
{
    shader "pbr.vfx"
    F_UNLIT "1"
    TextureColor1 "materials/rbx/glowingblue.png"
    TextureNormal1 "materials/default/default_normal.tga"
    g_vColorTint1 "[1.000000 1.000000 1.000000 0.000000]"
    g_flSelfIllumAlbedoFactor1 "1.000000"
    g_flSelfIllumScale1 "1.000000"
    g_vSelfIllumTint1 "[1.000000 1.000000 1.000000 0.000000]"
    TextureSelfIllumMask1 "materials/rbx/glowingblue.png"
    TextureRoughness1 "[0.350000 0.350000 0.350000 0.000000]"
    TextureMetalness1 "[0.000000 0.000000 0.000000 0.000000]"
}
```

Test compile succeeded:

```txt
C:/Code/deadlock-map-porting/logs/test_compile_soulscape_emissive_glowingblue.log
OK: 5 compiled, 0 failed
```

Compiled resource contains:

```txt
F_UNLIT = 1
g_flSelfIllumAlbedoFactor1
g_flSelfIllumScale1
g_vSelfIllumTint1
g_tSelfIllumMask
```

## Light source nuance

There are two separate concepts:

1. **Visible emissive material**: the cube itself appears bright/flat/glowing. This was degraded by our bad replacement and is fixable by recompiling materials.
2. **Actual light cast onto nearby surfaces**: this comes from baked lighting and/or `light_omni2` entities. Soulscape has many `light_omni2` entities and the Deadlock screenshot still shows wall halos, so the primary missing piece appears to be material emission/readability, not total absence of lighting.

If we want material emission to affect baked lightmaps too, rerun the full map compile after fixing emissive VMATs. If we only care about the cube looking bright in runtime, recompiling/repacking just the five VMATs may be enough.

## Decision

The generic material converter should split `csgo_complex.vfx` into at least two paths:

- if original has self-illum fields: `pbr.vfx + F_UNLIT + self-illum mask/scale/tint`
- otherwise: ordinary `pbr.vfx`

This should be fixed before generalizing the automation.
