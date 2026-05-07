#!/usr/bin/env python3
"""Build a Deadlock test package for workshop 3071726325 / bhop_colour.

This is the precompiled-map equivalent of the bhop_emevaelx3 correction:
keep the original compiled map/content and patch only the entity lump. The entity
patch removes unsupported CS2 point-prefabs, converts CS2 player spawns to
Deadlock info_team_spawn, preserves the original trigger_teleport / destination
network, and adds one real hideout/free-roam modifier volume.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(r"C:/Code/deadlock-map-porting")
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import automate_map_port as amp  # noqa: E402

WORKSHOP_DIR = Path(r"C:/Users/User/Downloads/730/3071726325")
SOURCE_VPK = WORKSHOP_DIR / "3071726325.vpk"
EXTRACTED_DECOMPILE_ROOT = Path(r"C:/Users/User/Downloads/730")
MAP_NAME = "bhop_colour"
MOVEMENT_SCRIPT_PAK = ROOT / "research/movementmap/archive/pak03_dir.vpk"
PLUGIN_DLL = ROOT / "plugins/DeadlockBhopRuntime/bin/Release/net10.0/DeadlockBhopRuntime.dll"
RESOURCEINFO = amp.CSDK / "game/bin_cs2/win64/resourceinfo.exe"
CONCRETE_MATERIAL = amp.CSDK / "game/citadel/materials/blends/blend_concrete_02.vmat_c"
CONCRETE_DEPENDENCIES = [
    amp.CSDK / "game/citadel/materials/blends/blend_concrete_02.vmat_c",
    amp.CSDK / "game/citadel/materials/blends/blend_concrete_02_vmat_g_tcolor_76dae843.vtex_c",
    amp.CSDK / "game/citadel/materials/blends/blend_concrete_02_vmat_g_tnormalroughness_613e1c56.vtex_c",
    amp.CSDK / "game/citadel/materials/default/default_ao_tga_559f1ac6.vtex_c",
    amp.CSDK / "game/citadel/materials/default/default_mask_tga_344101f8.vtex_c",
]
VISUAL_MATRIX = ROOT / "research/visual_compatibility_matrix/bhop_colour_visual_matrix.csv"
DEADLOCK_GAME_CITADEL = amp.CSDK / "game/citadel"
DEADLOCK_DEFAULT_TEXTURE_DEPS = [
    DEADLOCK_GAME_CITADEL / "materials/default/default_ao_tga_559f1ac6.vtex_c",
    DEADLOCK_GAME_CITADEL / "materials/default/default_mask_tga_344101f8.vtex_c",
    DEADLOCK_GAME_CITADEL / "materials/default/default_normal_tga_7be61377.vtex_c",
]
DEADLOCK_STOCK_MATERIAL_REPLACEMENTS = {
    "glass_default01": [
        "materials/glass/glass_default01.vmat_c",
        "materials/glass/glass_default01_vmat_g_tcolor_7d46cca1.vtex_c",
        "materials/glass/glass_default01_vmat_g_tglass_2b2ebb3f.vtex_c",
        "models/props_structures/materials/city_intergallactic_glass_normal_psd_a828cf2f.vtex_c",
        "materials/default/default_ao_tga_559f1ac6.vtex_c",
        "materials/default/default_mask_tga_344101f8.vtex_c",
    ],
    "water_stream_02": [
        "materials/water/water_stream_02.vmat_c",
        "materials/water/water_stream_02_ao_psd_c23db81d.vtex_c",
        "materials/water/water_stream_02_trans_psd_b7a81d4d.vtex_c",
        "materials/water/water_stream_02_trans_psd_7359baf5.vtex_c",
        "materials/water/water_stream_02_vmat_g_tmetalness_bdaa4c92.vtex_c",
        "materials/water/water_stream_02_normal_psd_ad835003.vtex_c",
        "materials/default/default_mask_tga_344101f8.vtex_c",
    ],
}

PREFAB_CLASSES = {
    "team_select",
    "terrorist_team_intro",
    "counterterrorist_team_intro",
    "end_of_match",
}


def run(cmd: list[str], *, stdout: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(str(x) for x in cmd))
    cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if stdout:
        stdout.parent.mkdir(parents=True, exist_ok=True)
        stdout.write_text(cp.stdout, encoding="utf-8", errors="replace")
    if cp.returncode != 0:
        if cp.stdout:
            print(cp.stdout[-4000:])
        raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
    if cp.stdout:
        print(cp.stdout[-2000:])
    return cp


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_vec3(value: str | None, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if not value:
        return default
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value)[:3]]
    if len(nums) != 3:
        return default
    return nums[0], nums[1], nums[2]


def fmt_vec3(v: tuple[float, float, float]) -> str:
    return f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}"


def iter_values_blocks(resourceinfo_text: str):
    pos = 0
    while True:
        idx = resourceinfo_text.find("values =", pos)
        if idx < 0:
            break
        open_idx = resourceinfo_text.find("{", idx)
        if open_idx < 0:
            break
        depth = 0
        end = None
        for i in range(open_idx, len(resourceinfo_text)):
            ch = resourceinfo_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            break
        yield resourceinfo_text[open_idx + 1:end]
        pos = end + 1


def parse_values_block(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in block.splitlines():
        line = raw.strip().rstrip(",")
        if not line or " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("[") and value.endswith("]"):
            # VMAP entity_properties store typed arrays as space-separated strings.
            # Feeding resourceinfo's '[ a, b, c ]' text back as a string makes
            # resourcecompiler fail conversion for colors/float arrays.
            value = " ".join(part for part in re.split(r"[\s,\[\]]+", value) if part)
        value = value.replace("\\\\", "/").replace("\\", "/")
        out[key] = value
    return out


def kv_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def make_entity_from_values(values: dict[str, str], node_id: int) -> tuple[str, str, int] | None:
    classname = values.get("classname", "")
    if not classname or classname == "worldspawn" or classname in PREFAB_CLASSES:
        return None

    origin = parse_vec3(values.get("origin"))
    angles = parse_vec3(values.get("angles"))

    extra: dict[str, str] = {}
    target_class = classname
    teamnumber: int | None = None
    lane_num: int | None = None
    initial_spawn: bool | None = None

    if classname.startswith("info_player_"):
        target_class = "info_team_spawn"
        teamnumber = 2 if classname == "info_player_terrorist" else 3
        lane_num = 0
        initial_spawn = False
    else:
        skip = {"classname", "origin", "angles", "scales"}
        for key, value in values.items():
            if key in skip:
                continue
            if key == "hammerUniqueId":
                # make_cmap_entity emits its own node ids; keeping source hammer ids
                # is useful in source text but not necessary for the compiled lump.
                extra[key] = kv_escape(value)
                continue
            extra[key] = kv_escape(value)

    ent_id, block = amp.make_cmap_entity(
        classname=target_class,
        origin=origin,
        node_id=node_id,
        teamnumber=teamnumber,
        lane_num=lane_num,
        initial_spawn=initial_spawn,
        angles=angles,
        extra_props=extra,
    )
    return ent_id, block, node_id + 1


def patch_worldspawn(kv_text: str, worldspawn: dict[str, str]) -> str:
    # Preserve high-value original worldspawn fields in the template CMapWorld.
    props_idx = kv_text.rfind('"classname" "string" "worldspawn"')
    if props_idx < 0:
        return kv_text
    start = kv_text.rfind('"entity_properties" "EditGameClassProps"', 0, props_idx)
    if start < 0:
        return kv_text
    open_idx = kv_text.find("{", start)
    depth = 0
    end = None
    for i in range(open_idx, len(kv_text)):
        if kv_text[i] == "{":
            depth += 1
        elif kv_text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return kv_text

    existing = kv_text[open_idx + 1:end]
    id_match = re.search(r'"id" "elementid" "([^"]+)"', existing)
    props_id = id_match.group(1) if id_match else str(__import__("uuid").uuid4())
    keep_keys = [
        "classname", "targetname", "skyname", "startdark", "startcolor", "pvstype", "newunit",
        "maxpropscreenwidth", "minpropscreenwidth", "vrchaperone", "vrmovement",
        "baked_light_index_min", "baked_light_index_max", "max_lightmap_resolution", "lightmap_queries",
        "worldname", "mapusagetype",
    ]
    lines = [f'\n\t\t\t"id" "elementid" "{props_id}"\n']
    for key in keep_keys:
        if key in worldspawn:
            lines.append(f'\t\t\t"{key}" "string" "{kv_escape(worldspawn[key])}"\n')
    if "classname" not in worldspawn:
        lines.append('\t\t\t"classname" "string" "worldspawn"\n')
    replacement = "".join(lines) + "\t\t"
    return kv_text[:open_idx + 1] + replacement + kv_text[end:]


def replace_colour_materials_with_concrete(outer_extract: Path) -> int:
    """Replace workshop material definitions with a known Deadlock concrete VMAT.

    The original workshop ships CS2-compiled colour materials. On Deadlock these
    can render black/missing. Keeping the same material paths but replacing the
    VMAT payloads lets existing VMDLs resolve their original resource names while
    using Deadlock-native concrete shading/textures.
    """
    if not CONCRETE_MATERIAL.exists():
        raise FileNotFoundError(CONCRETE_MATERIAL)

    replaced = 0
    material_root = outer_extract / "materials/colour_base"
    for vmat in material_root.rglob("*.vmat_c"):
        rel = vmat.relative_to(material_root).as_posix().lower()
        # Keep actual sky/water materials; concrete skyboxes/water are worse than
        # missing decals. Replace all stage/world/platform colour materials.
        if rel.startswith("water/") or rel.startswith("skybox/"):
            continue
        shutil.copy2(CONCRETE_MATERIAL, vmat)
        replaced += 1

    # Include concrete's real dependency paths in this addon too, so the copied
    # VMAT payload does not depend on base-game availability/version.
    for src in CONCRETE_DEPENDENCIES:
        if not src.exists():
            continue
        rel = src.relative_to(amp.CSDK / "game/citadel")
        dst = outer_extract / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return replaced


def parse_source_vmat_string(text: str, key: str) -> str | None:
    m = re.search(rf'"?{re.escape(key)}"?\s+"([^"]+)"', text)
    return m.group(1) if m else None


def make_deadlock_pbr_vmat(texture: str, color_tint: str = "[1.000000 1.000000 1.000000 0.000000]") -> str:
    return f'''Layer0
{{
    shader "pbr.vfx"

    TextureColor1 "{texture}"
    g_vColorTint1 "{color_tint}"
    g_vAlbedoTexcoordScale1 "[1.000000 1.000000 0.000000 0.000000]"
    g_vAlbedoTexcoordOffset1 "[0.000000 0.000000 0.000000 0.000000]"
    g_vNormalTexcoordScale1 "[1.000000 1.000000 0.000000 0.000000]"
    g_flOpacityScale1 "1.000000"
    g_flSelfIllumScale1 "0.000000"
}}
'''


def parse_float_vmat(text: str, key: str, default: float = 0.0) -> float:
    value = parse_source_vmat_string(text, key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def make_deadlock_visual_compat_vmat(src_text: str, rel_posix: str) -> str | None:
    """Generate a Deadlock-native VMAT using the visual compatibility matrix.

    This is intentionally conservative: it preserves original texture/tint inputs,
    maps unsupported CS2 shaders to pbr.vfx, and turns on only broadly observed
    Deadlock flags. Water/glass are handled by compiled stock-material copy below.
    """
    shader = (parse_source_vmat_string(src_text, "shader") or "").lower()
    if shader in {"csgo_glass.vfx", "csgo_water_fancy.vfx", "sky.vfx"}:
        return None

    texture = (
        parse_source_vmat_string(src_text, "TextureColor")
        or parse_source_vmat_string(src_text, "TextureGlassDust")
        or "materials/default/default_color_tga_61c2da90.png"
    ).replace("\\", "/")
    if texture.lower() == "materials/default/default_color.tga":
        texture = "materials/default/default_color_tga_61c2da90.png"
    normal = (parse_source_vmat_string(src_text, "TextureNormal") or "materials/default/default_normal_tga_7be61377.png").replace("\\", "/")
    if normal.lower() == "materials/default/default_normal.tga":
        normal = "materials/default/default_normal_tga_7be61377.png"
    color_tint = parse_source_vmat_string(src_text, "g_vColorTint") or "[1.000000 1.000000 1.000000 0.000000]"
    tex_scale = parse_source_vmat_string(src_text, "g_vTexCoordScale") or "[1.000000 1.000000 0.000000 0.000000]"
    tex_offset = parse_source_vmat_string(src_text, "g_vTexCoordOffset") or "[0.000000 0.000000 0.000000 0.000000]"
    tex_scroll = parse_source_vmat_string(src_text, "g_vTexCoordScrollSpeed") or "[0.000000 0.000000 0.000000 0.000000]"
    metalness = parse_float_vmat(src_text, "g_flMetalness", 0.0)
    translucent = parse_source_vmat_string(src_text, "F_TRANSLUCENT") == "1" or shader == "csgo_static_overlay.vfx"
    additive = parse_source_vmat_string(src_text, "F_BLEND_MODE") == "1"
    alpha_ref = parse_float_vmat(src_text, "g_flAlphaTestReference", 0.35)

    lines = [
        "Layer0",
        "{",
        '    shader "pbr.vfx"',
    ]
    if translucent:
        lines.append('    F_TRANSLUCENT "1"')
        lines.append('    F_RENDER_BACKFACES "1"')
    if additive:
        lines.append('    F_ADDITIVE_BLEND "1"')
    if metalness > 0.01 or "metal" in rel_posix.lower() or "gloss" in rel_posix.lower():
        lines.append('    F_SPECULAR "1"')
    lines.extend([
        f'    TextureColor1 "{texture}"',
        f'    TextureNormal1 "{normal}"',
        f'    g_vColorTint1 "{color_tint}"',
        f'    g_vAlbedoTexcoordScale1 "{tex_scale}"',
        f'    g_vAlbedoTexcoordOffset1 "{tex_offset}"',
        f'    g_vAlbedoScrollSpeed1 "{tex_scroll}"',
        f'    g_vNormalTexcoordScale1 "{tex_scale}"',
        f'    g_vNormalTexcoordOffset1 "{tex_offset}"',
        f'    g_vNormalAndRoughnessScrollSpeed1 "{tex_scroll}"',
        f'    g_flOpacityScale1 "{parse_float_vmat(src_text, "g_flOpacityScale", 1.0):.6f}"',
        f'    g_flAlphaAnglePower1 "{max(0.01, min(8.0, alpha_ref * 4.0)):.6f}"',
        '    g_flSelfIllumScale1 "0.000000"',
        '    TextureRoughness1 "[0.350000 0.350000 0.350000 0.000000]"',
        f'    TextureMetalness1 "[{metalness:.6f} {metalness:.6f} {metalness:.6f} 0.000000]"',
        "}",
        "",
    ])
    return "\n".join(lines)


def copy_compiled_stock_material(outer_extract: Path, replacement_key: str, target_rel: Path) -> int:
    deps = DEADLOCK_STOCK_MATERIAL_REPLACEMENTS[replacement_key]
    src_material = DEADLOCK_GAME_CITADEL / deps[0]
    if not src_material.exists():
        raise FileNotFoundError(src_material)
    target = outer_extract / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_material, target)
    copied = 1
    for rel in deps:
        src = DEADLOCK_GAME_CITADEL / rel
        if not src.exists():
            continue
        dst = outer_extract / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def replace_colour_materials_with_source_pbr(outer_extract: Path, extracted_root: Path, stamp: str, log_dir: Path) -> tuple[int, list[str]]:
    """Re-author decompiled CS2 colour VMATs as Deadlock-native pbr.vfx VMATs.

    Visual Source 2 Explorer gives us source VMAT/PNG files, but most VMATs use
    CS2-only shaders such as csgo_complex.vfx / csgo_static_overlay.vfx. Deadlock
    does not ship those shaders, so pass-through compiled CS2 VMATs can render
    black/missing. This keeps every material path the map models reference and
    swaps only the VMAT payloads to Deadlock pbr.vfx compiled resources.
    """
    source_material_root = extracted_root / "materials"
    source_colour_root = source_material_root / "colour_base"
    if not source_colour_root.exists():
        raise FileNotFoundError(source_colour_root)

    addon_name = f"bhop_colour_material_reauth_{stamp}"
    content_root = amp.CSDK / "content/citadel_addons" / addon_name
    game_root = amp.CSDK / "game/citadel_addons" / addon_name
    for p in [content_root, game_root]:
        if p.exists():
            shutil.rmtree(p)
    content_root.mkdir(parents=True)

    def is_power_of_two(n: int) -> bool:
        return n > 0 and (n & (n - 1)) == 0

    def next_power_of_two(n: int) -> int:
        return 1 << (n - 1).bit_length()

    # Copy source textures used by generated VMATs. This is small enough to copy
    # all extracted material images and avoids per-VMAT dependency guessing.
    # Deadlock's compiler rejects non-power-of-two textures with mipmaps enabled;
    # resize only the copied staging texture, never the user's decompile output.
    for pattern in ["*.png", "*.tga", "*.exr"]:
        for src in source_material_root.rglob(pattern):
            rel = src.relative_to(extracted_root)
            dst = content_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix.lower() == ".png":
                try:
                    from PIL import Image

                    with Image.open(src) as im:
                        w, h = im.size
                        if not is_power_of_two(w) or not is_power_of_two(h):
                            resampling = getattr(Image, "Resampling", Image).LANCZOS
                            im.resize((next_power_of_two(w), next_power_of_two(h)), resampling).save(dst)
                            continue
                except Exception:
                    # Fall back to a plain copy; resourcecompiler will fail loudly
                    # if the texture really is unusable.
                    pass
            shutil.copy2(src, dst)

    generated: list[Path] = []
    skipped: list[str] = []
    for src_vmat in sorted(source_colour_root.rglob("*.vmat")):
        rel = src_vmat.relative_to(source_material_root)
        rel_posix = rel.as_posix()
        text = src_vmat.read_text(encoding="utf-8", errors="replace")
        shader = (parse_source_vmat_string(text, "shader") or "").lower()
        if shader == "sky.vfx" or shader.startswith("csgo_water"):
            skipped.append(f"{rel_posix} ({shader or 'unknown shader'})")
            continue
        texture = (
            parse_source_vmat_string(text, "TextureColor")
            or parse_source_vmat_string(text, "TextureGlassDust")
            or parse_source_vmat_string(text, "SkyTexture")
        )
        if not texture:
            skipped.append(f"{rel_posix} (no source texture key)")
            continue
        texture_path = extracted_root / texture.replace("/", "\\")
        if not texture_path.exists():
            # Path may already be POSIX on this platform; try without conversion.
            texture_path = extracted_root / texture
        if not texture_path.exists():
            skipped.append(f"{rel_posix} (missing texture {texture})")
            continue
        color_tint = parse_source_vmat_string(text, "g_vColorTint") or "[1.000000 1.000000 1.000000 0.000000]"
        dst_vmat = content_root / "materials" / rel
        dst_vmat.parent.mkdir(parents=True, exist_ok=True)
        dst_vmat.write_text(make_deadlock_pbr_vmat(texture.replace("\\", "/"), color_tint), encoding="utf-8")
        generated.append(dst_vmat)

    compile_log = log_dir / f"compile_bhop_colour_source_pbr_materials_{stamp}.log"
    compile_log.parent.mkdir(parents=True, exist_ok=True)
    compile_log.write_text("", encoding="utf-8")
    for vmat in generated:
        cmd = [
            str(amp.RESOURCECOMPILER),
            "-game", str(amp.GAME_DIR),
            "-i", str(vmat),
            "-f",
        ]
        with compile_log.open("a", encoding="utf-8", errors="replace") as log:
            log.write("+ " + " ".join(cmd) + "\n")
            cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=amp.CSDK / "game/bin_cs2/win64")
            log.write(cp.stdout)
            log.write("\n")
        if cp.returncode != 0:
            print(cp.stdout[-4000:])
            raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)

    copied_vmat = 0
    if game_root.exists():
        for compiled in sorted((game_root / "materials").rglob("*")):
            if not compiled.is_file():
                continue
            rel = compiled.relative_to(game_root)
            dst = outer_extract / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(compiled, dst)
            if compiled.name.endswith(".vmat_c"):
                copied_vmat += 1
    return copied_vmat, skipped


def replace_colour_materials_with_visual_matrix(outer_extract: Path, extracted_root: Path, stamp: str, log_dir: Path) -> tuple[int, int, list[str]]:
    """Apply the bhop_colour visual compatibility matrix.

    Unsupported CS2 shaders are replaced at the exact material paths referenced by
    the original compiled models. Basic/overlay materials are reauthored as
    Deadlock pbr.vfx source VMATs. Water/glass use known-good Deadlock compiled
    material payloads because Source 2 glass/water flags are more fragile than
    plain PBR and these stock resources already carry the correct masks.
    """
    source_material_root = extracted_root / "materials"
    source_colour_root = source_material_root / "colour_base"
    if not source_colour_root.exists():
        raise FileNotFoundError(source_colour_root)

    addon_name = f"bhop_colour_visual_compat_{stamp}"
    content_root = amp.CSDK / "content/citadel_addons" / addon_name
    game_root = amp.CSDK / "game/citadel_addons" / addon_name
    for p in [content_root, game_root]:
        if p.exists():
            shutil.rmtree(p)
    content_root.mkdir(parents=True)

    def is_power_of_two(n: int) -> bool:
        return n > 0 and (n & (n - 1)) == 0

    def next_power_of_two(n: int) -> int:
        return 1 << (n - 1).bit_length()

    for pattern in ["*.png", "*.tga", "*.exr"]:
        for src in source_material_root.rglob(pattern):
            rel = src.relative_to(extracted_root)
            dst = content_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix.lower() == ".png":
                try:
                    from PIL import Image

                    with Image.open(src) as im:
                        w, h = im.size
                        if not is_power_of_two(w) or not is_power_of_two(h):
                            resampling = getattr(Image, "Resampling", Image).LANCZOS
                            im.resize((next_power_of_two(w), next_power_of_two(h)), resampling).save(dst)
                            continue
                except Exception:
                    pass
            shutil.copy2(src, dst)

    for dep in DEADLOCK_DEFAULT_TEXTURE_DEPS:
        if dep.exists():
            rel = dep.relative_to(DEADLOCK_GAME_CITADEL)
            dst = outer_extract / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dep, dst)

    generated: list[Path] = []
    skipped: list[str] = []
    stock_copies = 0
    for src_vmat in sorted(source_colour_root.rglob("*.vmat")):
        rel = src_vmat.relative_to(source_material_root)
        rel_posix = rel.as_posix()
        text = src_vmat.read_text(encoding="utf-8", errors="replace")
        shader = (parse_source_vmat_string(text, "shader") or "").lower()
        target_rel = Path("materials") / rel.with_suffix(rel.suffix + "_c")
        if shader == "csgo_water_fancy.vfx":
            stock_copies += copy_compiled_stock_material(outer_extract, "glass_default01", target_rel)
            continue
        if shader == "csgo_glass.vfx":
            stock_copies += copy_compiled_stock_material(outer_extract, "glass_default01", target_rel)
            continue
        if shader == "sky.vfx":
            skipped.append(f"{rel_posix} (sky.vfx kept original)")
            continue
        generated_text = make_deadlock_visual_compat_vmat(text, rel_posix)
        if generated_text is None:
            skipped.append(f"{rel_posix} ({shader or 'unknown shader'})")
            continue
        dst_vmat = content_root / "materials" / rel
        dst_vmat.parent.mkdir(parents=True, exist_ok=True)
        dst_vmat.write_text(generated_text, encoding="utf-8")
        generated.append(dst_vmat)

    compile_log = log_dir / f"compile_bhop_colour_visual_compat_materials_{stamp}.log"
    compile_log.parent.mkdir(parents=True, exist_ok=True)
    compile_log.write_text("", encoding="utf-8")
    for vmat in generated:
        cmd = [
            str(amp.RESOURCECOMPILER),
            "-game", str(amp.GAME_DIR),
            "-i", str(vmat),
            "-f",
        ]
        with compile_log.open("a", encoding="utf-8", errors="replace") as log:
            log.write("+ " + " ".join(cmd) + "\n")
            cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=amp.CSDK / "game/bin_cs2/win64")
            log.write(cp.stdout)
            log.write("\n")
        if cp.returncode != 0:
            print(cp.stdout[-4000:])
            raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)

    copied_vmat = 0
    if game_root.exists():
        for compiled in sorted((game_root / "materials").rglob("*")):
            if not compiled.is_file():
                continue
            rel = compiled.relative_to(game_root)
            dst = outer_extract / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(compiled, dst)
            if compiled.name.endswith(".vmat_c"):
                copied_vmat += 1
    return copied_vmat, stock_copies, skipped


def insert_entities_into_empty_vmap(output_vmap: Path, entities: list[tuple[str, str]], worldspawn: dict[str, str]) -> None:
    amp.make_empty_vmap_from_template(output_vmap)
    with tempfile.TemporaryDirectory(prefix="bhop_colour_entity_vmap_") as tmp_s:
        tmp = Path(tmp_s)
        kv = tmp / "empty.keyvalues2.vmap"
        patched = tmp / "patched.keyvalues2.vmap"
        run([str(amp.DMXCONVERT), "-i", str(output_vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        lines = patch_worldspawn(kv.read_text(encoding="utf-8", errors="replace"), worldspawn).splitlines(keepends=True)
        close_idx = amp.find_world_children_close(lines)
        refs = []
        for idx, (ent_id, _) in enumerate(entities):
            comma = "," if idx < len(entities) - 1 else ""
            refs.append(f'\t\t\t"element" "{ent_id}"{comma}\n')
        patched.write_text("".join(lines[:close_idx] + refs + lines[close_idx:]) + "\n" + "\n".join(block for _, block in entities), encoding="utf-8", errors="replace")
        kept = output_vmap.with_suffix(output_vmap.suffix + ".entity_patch.keyvalues2.txt")
        shutil.copy2(patched, kept)
        print(f"Kept entity patch text: {kept}")
        run([str(amp.DMXCONVERT), "-i", str(patched), "-o", str(output_vmap), "-oe", "binary", "-of", "vmap"])


def compile_entity_patch_vpk(vmap: Path) -> Path:
    log_dir = ROOT / "logs"
    return amp.compile_vmap(vmap, log_dir=log_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bhop_colour Deadlock preserve-port package")
    parser.add_argument(
        "--material-mode",
        choices=["concrete", "source-pbr", "visual-compat", "original"],
        default="visual-compat",
        help="material strategy: visual compatibility matrix, concrete fallback, Deadlock pbr.vfx reauth from Visual Source 2 Explorer output, or original CS2 compiled materials",
    )
    parser.add_argument(
        "--extracted-root",
        default=str(EXTRACTED_DECOMPILE_ROOT),
        help="Visual Source 2 Explorer extraction root used by --material-mode source-pbr",
    )
    parser.add_argument(
        "--no-extra-lights",
        action="store_true",
        help="do not add Deadlock citadel_volume_omni helper lights over checkpoint/start volumes",
    )
    parser.add_argument(
        "--convert-omni-lights",
        action="store_true",
        help="convert original CS2 light_omni2 entities into subdued Deadlock citadel_volume_omni lights using original origins/colors/ranges",
    )
    parser.add_argument(
        "--drop-original-omni-lights",
        action="store_true",
        help="when --convert-omni-lights is used, omit original light_omni2 entities from patched entity lump",
    )
    parser.add_argument(
        "--omni-brightness-scale",
        type=float,
        default=0.25,
        help="scale factor for converted CS2 light_omni2 brightness before clamping",
    )
    parser.add_argument(
        "--omni-range-scale",
        type=float,
        default=0.75,
        help="scale factor for converted CS2 light_omni2 range before clamping",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extracted_root = Path(args.extracted_root)
    if not SOURCE_VPK.exists():
        raise FileNotFoundError(SOURCE_VPK)
    if not MOVEMENT_SCRIPT_PAK.exists():
        raise FileNotFoundError(MOVEMENT_SCRIPT_PAK)
    if not PLUGIN_DLL.exists():
        raise FileNotFoundError(PLUGIN_DLL)
    if args.material_mode in {"source-pbr", "visual-compat"} and not extracted_root.exists():
        raise FileNotFoundError(extracted_root)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "work" / f"bhop_colour_preserve_{stamp}"
    out = ROOT / "exports" / f"bhop_colour_preserve_port_{stamp}"
    nested_extract = work / "nested_original"
    outer_extract = work / "outer_original"
    patch_extract = work / "patch_vpk"
    docs = out / "docs"
    addons = out / "game/citadel/addons"
    plugin_dir = out / "game/bin/win64/managed/plugins"
    for p in [work, out]:
        if p.exists():
            shutil.rmtree(p)
    nested_extract.mkdir(parents=True)
    outer_extract.mkdir(parents=True)
    patch_extract.mkdir(parents=True)
    docs.mkdir(parents=True)
    addons.mkdir(parents=True)
    plugin_dir.mkdir(parents=True)

    # Extract original package.
    run(["vpk", "-x", str(outer_extract), str(SOURCE_VPK)])
    concrete_replacements = 0
    source_pbr_replacements = 0
    source_pbr_skipped: list[str] = []
    visual_compat_replacements = 0
    visual_compat_stock_copies = 0
    visual_compat_skipped: list[str] = []
    material_strategy = "original CS2 compiled material pass-through"
    if args.material_mode == "concrete":
        concrete_replacements = replace_colour_materials_with_concrete(outer_extract)
        material_strategy = f"Deadlock concrete fallback ({concrete_replacements} VMAT payloads replaced)"
    elif args.material_mode == "source-pbr":
        source_pbr_replacements, source_pbr_skipped = replace_colour_materials_with_source_pbr(
            outer_extract,
            extracted_root,
            stamp,
            ROOT / "logs",
        )
        material_strategy = f"Deadlock pbr.vfx reauth from `{extracted_root}` ({source_pbr_replacements} VMAT payloads replaced)"
    elif args.material_mode == "visual-compat":
        visual_compat_replacements, visual_compat_stock_copies, visual_compat_skipped = replace_colour_materials_with_visual_matrix(
            outer_extract,
            extracted_root,
            stamp,
            ROOT / "logs",
        )
        material_strategy = (
            f"visual compatibility matrix `{VISUAL_MATRIX}` "
            f"({visual_compat_replacements} generated VMAT payloads, {visual_compat_stock_copies} stock material/dependency copies)"
        )
    nested_vpk = outer_extract / "maps" / f"{MAP_NAME}.vpk"
    if not nested_vpk.exists():
        raise FileNotFoundError(nested_vpk)
    run(["vpk", "-x", str(nested_extract), str(nested_vpk)])

    ents_c = nested_extract / "maps" / MAP_NAME / "entities/default_ents.vents_c"
    ri = work / "default_ents_resourceinfo.txt"
    run([str(RESOURCEINFO), "-game", str(amp.GAME_DIR), "-i", str(ents_c), "-all"], stdout=ri)
    ri_text = ri.read_text(encoding="utf-8", errors="replace")
    values_blocks = [parse_values_block(block) for block in iter_values_blocks(ri_text)]
    entities_values = [v for v in values_blocks if "classname" in v]
    worldspawn = next((v for v in entities_values if v.get("classname") == "worldspawn"), {"classname": "worldspawn", "worldname": MAP_NAME})

    # Build entity-only VMAP preserving original runtime entities except unsupported prefabs and converting CS2 spawns.
    entities: list[tuple[str, str]] = []
    node_id = 1000
    skipped: list[str] = []
    converted_spawns = 0
    preserved = 0
    for values in entities_values:
        cls = values.get("classname", "")
        if cls in PREFAB_CLASSES or cls == "worldspawn":
            if cls in PREFAB_CLASSES:
                skipped.append(cls)
            continue
        if cls == "light_omni2" and args.convert_omni_lights and args.drop_original_omni_lights:
            skipped.append(cls)
            continue
        made = make_entity_from_values(values, node_id)
        if made is None:
            continue
        ent_id, block, node_id = made
        entities.append((ent_id, block))
        if cls.startswith("info_player_"):
            converted_spawns += 1
        else:
            preserved += 1

    # Optionally convert original CS2 light_omni2 points to Deadlock-native omni
    # volumes. This preserves the authored light positions/colors/ranges much
    # better than the earlier coarse checkpoint helper lights. Keep volumetric
    # media off to avoid the surreal foggy look.
    converted_omni_lights = 0
    if args.convert_omni_lights:
        for values in entities_values:
            if values.get("classname") != "light_omni2":
                continue
            x, y, z = parse_vec3(values.get("origin"))
            color = values.get("color", "255 255 255")
            src_range = parse_vec3(values.get("range"), (542.0, 0.0, 0.0))[0]
            try:
                src_brightness = float(values.get("brightness", "1.0"))
            except ValueError:
                src_brightness = 1.0
            # Deadlock's citadel_volume_omni brightness is not the same unit as
            # CS2 light_omni2. Start conservative: enough to tint neutral PBR
            # surfaces, but far below the previous 10.0 helper lights.
            deadlock_brightness = max(0.02, min(1.0, src_brightness * args.omni_brightness_scale))
            ent_id, block = amp.make_cmap_entity(
                classname="citadel_volume_omni",
                origin=(x, y, z),
                node_id=node_id,
                targetname=f"bhop_colour_src_omni_{converted_omni_lights:03d}",
                extra_props={
                    "useLocalOffset": "0",
                    "lightcolor": f"{color} 255" if len(color.split()) == 3 else color,
                    "lightbrightness": f"{deadlock_brightness:.3f}",
                    "lightrange": f"{max(64.0, min(1200.0, src_range * args.omni_range_scale)):.3f}",
                    "mediacolor": "0 0 0 0",
                    "mediabrightness": "0",
                    "mediadensity": "0",
                    "animated": "0",
                },
            )
            node_id += 1
            converted_omni_lights += 1
            entities.append((ent_id, block))

    # Add optional Deadlock-native light spots over the original checkpoint/start
    # trigger volumes. Original light_omni2 entities and lightmaps are preserved;
    # this helper pass is useful when the map is too dark, but can look surreal
    # in Deadlock because it stacks dynamic volumetric lights over CS2 lighting.
    added_light_spots = 0
    if not args.no_extra_lights:
        light_spot_origins: list[tuple[float, float, float]] = []
        for values in entities_values:
            if values.get("classname") == "trigger_multiple" and values.get("targetname", "").startswith("[PR#]map_"):
                x, y, z = parse_vec3(values.get("origin"))
                light_spot_origins.append((x, y, z + 360.0))
        # Keep deterministic order and cap to avoid excessive dynamic light cost.
        seen_light_spots: set[tuple[int, int, int]] = set()
        for origin in light_spot_origins[:24]:
            key = (round(origin[0]), round(origin[1]), round(origin[2]))
            if key in seen_light_spots:
                continue
            seen_light_spots.add(key)
            ent_id, block = amp.make_cmap_entity(
                classname="citadel_volume_omni",
                origin=origin,
                node_id=node_id,
                targetname=f"bhop_colour_light_spot_{added_light_spots:02d}",
                extra_props={
                    "useLocalOffset": "0",
                    "lightcolor": "255 244 214 255",
                    "lightbrightness": "10",
                    "lightrange": "1400",
                    "mediacolor": "255 220 160 255",
                    "mediabrightness": "0.35",
                    "mediadensity": "0.0015",
                    "animated": "0",
                },
            )
            node_id += 1
            added_light_spots += 1
            entities.append((ent_id, block))

    # Broad map bounds plus known start/damage fallback anchors.
    for team, y, yaw in [(2, 4984.0, 180.0), (3, 4600.0, 0.0)]:
        # Extra Deadlock spawn row at original start, in case converted spawns are ignored by team rules.
        for i, x in enumerate([3536.0, 3600.0, 3664.0, 3728.0, 3792.0, 3856.0, 3920.0]):
            ent_id, block = amp.make_cmap_entity(
                classname="info_team_spawn",
                origin=(x, y + (64.0 if i % 2 else 0.0), 112.0),
                node_id=node_id,
                teamnumber=team,
                lane_num=0,
                initial_spawn=False,
                angles=(0.0, yaw, 0.0),
            )
            node_id += 1
            entities.append((ent_id, block))

    for origin in [(-16000.0, -16000.0, -5000.0), (16000.0, 16000.0, 5000.0)]:
        ent_id, block = amp.make_cmap_entity(classname="citadel_minimap_boundary", origin=origin, node_id=node_id)
        node_id += 1
        entities.append((ent_id, block))

    for targetname, origin in [
        ("bhop_course_start", (3720.0, 4792.0, 128.0)),
        ("rebels_vanguard_spawn", (3720.0, 4792.0, 128.0)),
        ("combine_vanguard_spawn", (3720.0, 4600.0, 128.0)),
    ]:
        ent_id, block = amp.make_cmap_entity(
            classname="info_target_server_only",
            origin=origin,
            node_id=node_id,
            targetname=targetname,
            extra_props={"useLocalOffset": "0"},
        )
        node_id += 1
        entities.append((ent_id, block))

    # A real compiled hideout/free-roam modifier volume covering world physics bounds.
    hideout_id, hideout_block, node_id = amp.make_solid_box_entity_from_template(
        classname="citadel_trigger_suspend_modifier",
        mins=(-3840.0, -6000.0, -1024.0),
        maxs=(7900.0, 10000.0, 2048.0),
        node_id_start=node_id,
        targetname="bhop_colour_roam_hideout_volume",
        modifier_name="modifier_citadel_in_hideout_zone",
    )
    entities.append((hideout_id, hideout_block))

    vmap = amp.CSDK / "content/citadel_addons/bhop_colour_preserve_patch/maps/bhop_colour.vmap"
    if vmap.parent.parent.parent.exists():
        shutil.rmtree(vmap.parent.parent.parent)
    insert_entities_into_empty_vmap(vmap, entities, worldspawn)
    patch_vpk = compile_entity_patch_vpk(vmap)
    run(["vpk", "-x", str(patch_extract), str(patch_vpk)])

    # Replace only the entity lump and any generated hideout entity model in the original nested VPK payload.
    patched_ents = patch_extract / "maps" / MAP_NAME / "entities/default_ents.vents_c"
    if not patched_ents.exists():
        raise FileNotFoundError(patched_ents)
    shutil.copy2(patched_ents, nested_extract / "maps" / MAP_NAME / "entities/default_ents.vents_c")
    for model in (patch_extract / "maps" / MAP_NAME / "entities").glob("bhop_colour_roam_hideout_volume_*.vmdl_c"):
        shutil.copy2(model, nested_extract / "maps" / MAP_NAME / "entities" / model.name)

    patched_nested = work / "maps" / f"{MAP_NAME}.vpk"
    patched_nested.parent.mkdir(parents=True, exist_ok=True)
    run(["vpk", "-c", str(nested_extract), str(patched_nested)])
    shutil.copy2(patched_nested, outer_extract / "maps" / f"{MAP_NAME}.vpk")

    patched_outer = addons / "pak72_dir.vpk"
    run(["vpk", "-c", str(outer_extract), str(patched_outer)])
    shutil.copy2(MOVEMENT_SCRIPT_PAK, addons / "pak70_dir.vpk")
    shutil.copy2(PLUGIN_DLL, plugin_dir / "DeadlockBhopRuntime.dll")

    # Verification artifacts.
    shutil.copy2(ri, docs / "original_default_ents_resourceinfo.txt")
    latest_logs = sorted((ROOT / "logs").glob("compile_bhop_colour_*.log"), key=lambda p: p.stat().st_mtime)
    for log in latest_logs[-3:]:
        shutil.copy2(log, docs / log.name)
    report = docs / "BHOP_COLOUR_PATCH_NOTES.md"
    report.write_text(f"""# bhop_colour preserve-port notes

Source: `{SOURCE_VPK}`

This package preserves the original compiled workshop map/content and replaces only the nested `maps/{MAP_NAME}/entities/default_ents.vents_c` entity lump, plus one generated hideout trigger model.

Patched entity rules:

- removed unsupported CS2 point prefabs / omitted original classes: `{', '.join(sorted(set(skipped)))}`
- converted original CS2 player spawns to Deadlock `info_team_spawn`: {converted_spawns}
- preserved non-prefab original entities, including `trigger_teleport`, `info_teleport_destination`, `trigger_multiple`, lights, water, postprocess: {preserved}
- material strategy: {material_strategy}
- concrete VMAT payload replacements: {concrete_replacements}
- source-pbr VMAT payload replacements: {source_pbr_replacements}
- source-pbr skipped materials: {', '.join(source_pbr_skipped) if source_pbr_skipped else 'none'}
- visual-compat generated VMAT payload replacements: {visual_compat_replacements}
- visual-compat stock material/dependency copies: {visual_compat_stock_copies}
- visual-compat skipped materials: {', '.join(visual_compat_skipped) if visual_compat_skipped else 'none'}
- converted original `light_omni2` to subdued Deadlock `citadel_volume_omni`: {converted_omni_lights}
- converted omni brightness scale/range scale: {args.omni_brightness_scale} / {args.omni_range_scale}
- added bright `citadel_volume_omni` light spots over checkpoint/start volumes: {added_light_spots}
- added broad `citadel_minimap_boundary` pair
- added model-backed `citadel_trigger_suspend_modifier` with `modifier_citadel_in_hideout_zone`
- included `pak70_dir.vpk` movementmap script override for A/B parity
- included roam-only `DeadlockBhopRuntime.dll` fallback

Install by copying `game/` over the Deadlock/Deadworks install root, after removing stale loose `game/citadel_addons/bhop_colour*` roots and stale `pak72_dir.vpk`.

Run:

```text
map bhop_colour
```
""", encoding="utf-8")

    readme = out / "README_INSTALL_TEST.txt"
    readme.write_text(f"""# bhop_colour Deadlock preserve-port test

Generated: {stamp}

Install by copying this package's `game` folder over the Deadlock install root.

Files:

```text
game/citadel/addons/pak70_dir.vpk  # movementmap scripts/heroes + scripts/abilities override
game/citadel/addons/pak72_dir.vpk  # original bhop_colour workshop content with patched entity lump
game/bin/win64/managed/plugins/DeadlockBhopRuntime.dll
```

Before installing, stop Deadlock and remove/rename stale paths:

```text
game/citadel_addons/bhop_colour*
game/citadel/addons/pak72_dir.vpk
```

Then run:

```text
map bhop_colour
```

This is intentionally a preserve-port: original teleports/checkpoint volumes/content are kept. Only CS2 point-prefabs were removed, CS spawns were converted to Deadlock spawns, material strategy is `{material_strategy}`, converted omni lights = {converted_omni_lights}, extra light spots = {added_light_spots}, and a real hideout/free-roam modifier volume was added.
""", encoding="utf-8")

    sums = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS.txt":
            sums.append(f"{sha256(p)}  {p.relative_to(out).as_posix()}")
    (out / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out.parent))

    print("preserved original non-prefab entities:", preserved)
    print("converted spawns:", converted_spawns)
    print("material strategy:", material_strategy)
    print("concrete material replacements:", concrete_replacements)
    print("source-pbr material replacements:", source_pbr_replacements)
    print("source-pbr skipped materials:", source_pbr_skipped)
    print("visual-compat generated material replacements:", visual_compat_replacements)
    print("visual-compat stock material/dependency copies:", visual_compat_stock_copies)
    print("visual-compat skipped materials:", visual_compat_skipped)
    print("converted omni lights:", converted_omni_lights)
    print("omni brightness/range scales:", args.omni_brightness_scale, args.omni_range_scale)
    print("added light spots:", added_light_spots)
    print("removed prefabs:", sorted(set(skipped)))
    print(out)
    print(zip_path)


if __name__ == "__main__":
    main()
