# Visual compatibility audit

Extracted root: `C:\Users\User\Downloads\730`
Matrix: `C:\Code\deadlock-map-porting\research\visual_compatibility_matrix\bhop_colour_visual_matrix.csv`

## Material shaders
- `csgo_static_overlay.vfx`: 23 (UNAVAILABLE) -> pbr.vfx + F_TRANSLUCENT + F_RENDER_BACKFACES + original alpha texture
  - `colour_base/skybox/bhop_colour_decal.vmat`
  - `colour_base/skybox/qr_code.vmat`
  - `colour_base/skybox/stage_2.vmat`
  - `colour_base/skybox/stage_3.vmat`
  - `colour_base/skybox/stage_4.vmat`
  - `colour_base/stage_decals/finished.vmat`
  - `colour_base/stage_decals/stage_10.vmat`
  - `colour_base/stage_decals/stage_11.vmat`
- `csgo_complex.vfx`: 8 (UNAVAILABLE) -> pbr.vfx + original color/normal + F_SPECULAR for metal/gloss
  - `colour_base/dark_grey.vmat`
  - `colour_base/metal_white.vmat`
  - `colour_base/skybox/can_detail.vmat`
  - `colour_base/skybox/floor_detail.vmat`
  - `colour_base/skybox/white_grey.vmat`
  - `colour_base/skybox/white_light.vmat`
  - `colour_base/stage_decals/last_stage_special.vmat`
  - `colour_base/white.vmat`
- `csgo_glass.vfx`: 1 (UNAVAILABLE) -> materials/glass/glass_default01.vmat_c
  - `colour_base/colour_glass.vmat`
- `sky.vfx`: 1 (check) -> keep original compiled sky material
  - `colour_base/skybox/skybox_colour.vmat`
- `csgo_water_fancy.vfx`: 1 (UNAVAILABLE) -> materials/glass/glass_default01.vmat_c with glass mask
  - `colour_base/water/custom_water.vmat`

## Missing matrix rows
none
