# bhop_colour final translation audit

## Artifacts

- Final map VPK: `C:/Users/User/Downloads/bhop_colour.vpk`
  - SHA256 `8cfbb2443a89c14e0aab67d144812750fe122909483f4064dc50070db6d5809b`
  - 98 MB
  - 335 entries
- Final addon/content VPK: `C:/Users/User/Downloads/pak33_dir.vpk`
  - SHA256 `d431926bc6222167f3f5dbbe6d7bc44a4e8e32fbf408c633d051ef6e426ec31e`
  - 301 MB
  - 107 entries

Extracted/audit files are in this directory.

## High-level split

`bhop_colour.vpk` is the compiled map container. It contains:

- `maps/bhop_colour.vmap_c`
- `maps/bhop_colour/entities/default_ents.vents_c`
- `maps/bhop_colour/world.vwrld_c`
- `maps/bhop_colour/worldnodes/n0.vwnod_c`
- 232 compiled worldnode `vmdl_c` resources
- 82 compiled entity/checkpoint `vmdl_c` resources
- cubemap/lightmap/probe atlas resources
- nav + physics + vrman resources

`pak33_dir.vpk` is the mount/package VPK. It contains:

- `README.txt`
- `maps/bhop_colour.vpk` nested map VPK
- `maps/bhop_colour.los`
- 30 compiled VMATs
- 71 compiled VTEX resources
- 3 postprocess resources

## Entities in final `default_ents.vents_c`

Counted from `resourceinfo` output:

- 677 `light_omni2`
- 42 `trigger_teleport`
- 22 `env_combined_light_probe_volume`
- 22 `trigger_multiple`
- 21 `info_teleport_destination`
- 17 `func_water`
- 1 `worldspawn`
- 1 `light_environment`
- 1 `env_sky`
- 1 `post_processing_volume`

Important: the final artifact keeps CS2-ish classnames (`light_omni2`, `func_water`) rather than converting all of them to Deadlock-native classnames. This is a major difference from our earlier attempted transfer, where `light_omni2` became `citadel_volume_omni` and water/glass handling was lossy.

## World geometry/material distribution

Compiled worldnode VMDLs reference 30 material paths. Top refs:

- 137 `materials/colour_base/colour_glass.vmat`
- 20 `materials/colour_base/skybox/bhop_colour_decal.vmat`
- 18 `materials/colour_base/skybox/qr_code.vmat`
- 9 `materials/colour_base/water/custom_water.vmat`
- 3 `materials/colour_base/stage_decals/stage_5.vmat`
- 3 `materials/colour_base/skybox/stage_3.vmat`
- 3 `materials/colour_base/stage_decals/stage_9.vmat`
- 1 each for the big aggregate materials: `white`, `dark_grey`, `floor_detail`, `white_light`

This final result is *not* a one-material or generic Deadlock-native rewrite. It preserves the original map material namespace and stage/decal naming.

## Material translation pattern

Most final VMATs are Deadlock-compatible `pbr.vfx` resources that preserve original texture intent:

- `white.vmat_c`: `pbr.vfx`, original white color VTEX, default AO/normal/masks
- `dark_grey.vmat_c`: `pbr.vfx`, original dark grey VTEX, default AO/normal/masks
- stage decals / QR / bhop decal: `pbr.vfx` + `F_GLASS`, color texture + mask texture
- `colour_glass.vmat_c`: `pbr.vfx` + `F_GLASS`, glass color + glass mask
- `white_light.vmat_c`: `pbr.vfx` + `F_SELF_ILLUM`
- `skybox_colour.vmat_c`: remains `sky.vfx` with compiled EXR skybox texture

This is a better material strategy than our earlier pbr fallback generation because it uses final compiled CS2-derived texture names and keeps glass/mask/selfillum feature flags.

## Key lesson for future maps

The successful final artifact is closer to a **resource-preserving compatibility mount** than to a full source rewrite into Deadlock entity/material idioms.

For new maps, the likely pipeline should be:

1. Start from VS2 Explorer extracted CS2 resources / compiled map resources.
2. Preserve original map namespace and material paths.
3. Package compiled map VPK as the primary map asset.
4. Package all needed compiled VMAT/VTEX/postprocess/LOS resources in a separate addon VPK.
5. Avoid converting working CS2 entities if Deadlock can load them (`light_omni2`, `func_water`, triggers, teleport destinations).
6. Translate only shader/material features Deadlock truly rejects.
7. Use `resourceinfo` dependency closure to validate packaged resources.
8. Use Hammer views as inspection aids, not as the primary runtime source of truth.

## Files generated in this audit

- `final_bhop_colour_vpk_listing.txt`
- `final_pak33_listing.txt`
- `extracted_final_map/`
- `extracted_final_pak33/`
- `final_bhop_colour_vmap_c_resourceinfo.txt`
- `final_world_vwrld_resourceinfo.txt`
- `final_default_ents_resourceinfo.txt`
- `final_material_summary.txt`
