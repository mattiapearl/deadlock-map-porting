#!/usr/bin/env python3
"""Prototype CS2 Workshop Tools -> Deadlock CSDK source transfer.

This creates a real Deadlock content addon from a CS2/VS2 Explorer source VMAP:
- converts source VMAP to editable keyvalues2 with CS2 dmxconvert
- removes CS2 point-prefab entities
- converts common CS2 gameplay/light classnames to Deadlock equivalents
- writes Deadlock-compatible source VMATs for unsupported CS2 shaders
- overlays stock compiled Deadlock glass/water replacements for fragile F_GLASS cases
- converts the patched keyvalues2 VMAP back to binary VMAP with Deadlock dmxconvert

It intentionally does not overwrite the live game. Compile is opt-in.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:/Code/deadlock-map-porting")
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import automate_map_port as amp  # noqa: E402
import build_bhop_colour_preserve_port as colour  # noqa: E402

CS2_ROOT = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive")
CS2_GAME = CS2_ROOT / "game/csgo"
CS2_DMXCONVERT = CS2_ROOT / "game/bin/win64/dmxconvert.exe"
DEFAULT_EXTRACTED = Path(r"C:/Users/User/Downloads/730")
DEFAULT_SOURCE_VMAP = DEFAULT_EXTRACTED / "maps/maps/bhop_colour.vmap"
DEFAULT_ADDON = "bhop_colour_source_transfer"
PREFAB_CLASSES = {"team_select", "terrorist_team_intro", "counterterrorist_team_intro", "end_of_match"}


def run(cmd: list[str], *, stdout: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(str(x) for x in cmd))
    cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if stdout:
        stdout.parent.mkdir(parents=True, exist_ok=True)
        stdout.write_text(cp.stdout, encoding="utf-8", errors="replace")
    if cp.returncode != 0:
        print(cp.stdout[-6000:])
        raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
    if cp.stdout:
        print(cp.stdout[-2000:])
    return cp


def find_matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    in_quote = False
    esc = False
    for i in range(open_idx, len(text)):
        ch = text[i]
        if in_quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_quote = False
            continue
        if ch == '"':
            in_quote = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"no matching brace for {open_idx}")


def iter_typed_blocks(text: str, block_type: str):
    pattern = f'"{block_type}"'
    pos = 0
    while True:
        idx = text.find(pattern, pos)
        if idx < 0:
            return
        open_idx = text.find("{", idx + len(pattern))
        if open_idx < 0:
            return
        end = find_matching_brace(text, open_idx)
        yield idx, end + 1, text[idx:end + 1]
        pos = end + 1


def get_classname(block: str) -> str | None:
    m = re.search(r'"classname"\s+"string"\s+"([^"]+)"', block)
    return m.group(1) if m else None


def add_string_prop(entity_props: str, key: str, value: str) -> str:
    if re.search(rf'"{re.escape(key)}"\s+"string"', entity_props):
        return entity_props
    close = entity_props.rfind("}")
    if close < 0:
        return entity_props
    return entity_props[:close] + f'\t\t\t\t\t"{key}" "string" "{value}"\n' + entity_props[close:]


def patch_entity_block(block: str, stats: dict[str, int]) -> str | None:
    cls = get_classname(block)
    if cls in PREFAB_CLASSES:
        stats[f"removed_{cls}"] = stats.get(f"removed_{cls}", 0) + 1
        return None
    if cls == "info_player_terrorist":
        block = block.replace('"classname" "string" "info_player_terrorist"', '"classname" "string" "info_team_spawn"')
        props_open = block.find('"entity_properties" "EditGameClassProps"')
        props_brace = block.find("{", props_open)
        props_end = find_matching_brace(block, props_brace)
        props = add_string_prop(block[props_brace:props_end + 1], "teamnumber", "2")
        props = add_string_prop(props, "lane_num", "0")
        props = add_string_prop(props, "initial_spawn", "0")
        block = block[:props_brace] + props + block[props_end + 1:]
        stats["converted_spawns"] = stats.get("converted_spawns", 0) + 1
    elif cls == "info_player_counterterrorist":
        block = block.replace('"classname" "string" "info_player_counterterrorist"', '"classname" "string" "info_team_spawn"')
        props_open = block.find('"entity_properties" "EditGameClassProps"')
        props_brace = block.find("{", props_open)
        props_end = find_matching_brace(block, props_brace)
        props = add_string_prop(block[props_brace:props_end + 1], "teamnumber", "3")
        props = add_string_prop(props, "lane_num", "0")
        props = add_string_prop(props, "initial_spawn", "0")
        block = block[:props_brace] + props + block[props_end + 1:]
        stats["converted_spawns"] = stats.get("converted_spawns", 0) + 1
    elif cls == "light_omni2":
        color = "255 255 255 255"
        m = re.search(r'"color"\s+"color255"\s+"([^"]+)"', block) or re.search(r'"color"\s+"string"\s+"([^"]+)"', block)
        if m:
            parts = m.group(1).split()
            color = " ".join(parts[:3] + ["255"] if len(parts) == 3 else parts[:4])
        brightness = "0.250"
        m = re.search(r'"brightness"\s+"float"\s+"([^"]+)"', block)
        if m:
            try:
                brightness = f"{max(0.02, min(1.0, float(m.group(1)) * 0.25)):.3f}"
            except ValueError:
                pass
        rng = "512.000"
        m = re.search(r'"range"\s+"float"\s+"([^"]+)"', block) or re.search(r'"range"\s+"vector3"\s+"([^"]+)"', block)
        if m:
            nums = re.findall(r"-?\d+(?:\.\d+)?", m.group(1))
            if nums:
                rng = f"{max(64.0, min(1200.0, float(nums[0]) * 0.75)):.3f}"
        block = block.replace('"classname" "string" "light_omni2"', '"classname" "string" "citadel_volume_omni"')
        props_open = block.find('"entity_properties" "EditGameClassProps"')
        props_brace = block.find("{", props_open)
        props_end = find_matching_brace(block, props_brace)
        props = block[props_brace:props_end + 1]
        for k, v in {
            "useLocalOffset": "0",
            "lightcolor": color,
            "lightbrightness": brightness,
            "lightrange": rng,
            "mediacolor": "0 0 0 0",
            "mediabrightness": "0",
            "mediadensity": "0",
            "animated": "0",
        }.items():
            props = add_string_prop(props, k, v)
        block = block[:props_brace] + props + block[props_end + 1:]
        stats["converted_lights"] = stats.get("converted_lights", 0) + 1
    return block


def patch_vmap_kv2(text: str) -> tuple[str, dict[str, int]]:
    stats: dict[str, int] = {}
    out = []
    pos = 0
    for start, end, block in iter_typed_blocks(text, "CMapEntity"):
        out.append(text[pos:start])
        patched = patch_entity_block(block, stats)
        if patched is not None:
            out.append(patched)
        pos = end
    patched_text = "".join(out) + text[pos:]
    # Removing inline typed elements from keyvalues2 leaves standalone comma
    # separator lines. dmxconvert expects the next element type there, so drop
    # empty comma separators after removals. Real numeric/string arrays in this
    # file do not use standalone comma-only lines.
    patched_text = re.sub(r"(?m)^\s*,\s*$\n?", "", patched_text)
    return patched_text, stats


def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def next_power_of_two(n: int) -> int:
    return 1 << (n - 1).bit_length()


def copy_texture_source(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".png":
        try:
            from PIL import Image

            with Image.open(src) as im:
                w, h = im.size
                if not is_power_of_two(w) or not is_power_of_two(h):
                    resampling = getattr(Image, "Resampling", Image).LANCZOS
                    im.resize((next_power_of_two(w), next_power_of_two(h)), resampling).save(dst)
                    return
        except Exception:
            pass
    shutil.copy2(src, dst)


def copy_textures_and_materials(extracted: Path, content_root: Path, game_root: Path) -> tuple[int, int]:
    src_mat = extracted / "materials"
    dst_mat = content_root / "materials"
    if dst_mat.exists():
        shutil.rmtree(dst_mat)
    # Copy only image sources; source VMATs are rewritten below to avoid CS2-only shaders in Deadlock compile.
    copied_images = 0
    for pat in ["*.png", "*.tga"]:
        for src in src_mat.rglob(pat):
            rel = src.relative_to(src_mat)
            dst = dst_mat / rel
            copy_texture_source(src, dst)
            copied_images += 1

    generated = 0
    for src_vmat in sorted((src_mat / "colour_base").rglob("*.vmat")):
        rel = src_vmat.relative_to(src_mat)
        text = src_vmat.read_text(encoding="utf-8", errors="replace")
        shader = (colour.parse_source_vmat_string(text, "shader") or "").lower()
        if shader == "sky.vfx":
            # Deadlock does not reliably compile CS2 sky.vfx here. Use a simple
            # pbr fallback at the same path so map compilation can resolve the
            # material; sky visual fidelity can be handled as a later matrix row.
            tex = "materials/default/default_color_tga_61c2da90.png"
            dst = dst_mat / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(colour.make_deadlock_pbr_vmat(tex), encoding="utf-8")
            generated += 1
            continue
        if shader in {"csgo_glass.vfx", "csgo_water_fancy.vfx"}:
            # Don't put unsupported source VMAT in content. Pre-seed compiled stock replacement in game at the referenced path.
            target_rel = Path("materials") / rel.with_suffix(rel.suffix + "_c")
            key = "glass_default01"
            colour.copy_compiled_stock_material(game_root, key, target_rel)
            continue
        compat = colour.make_deadlock_visual_compat_vmat(text, rel.as_posix())
        if compat is None:
            continue
        dst = dst_mat / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(compat, encoding="utf-8")
        generated += 1
    return copied_images, generated


def compile_source_vmats(content_root: Path, addon: str, stamp: str) -> int:
    vmats = sorted((content_root / "materials").rglob("*.vmat"))
    log = ROOT / "logs" / f"compile_transfer_materials_{addon}_{stamp}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    compiled = 0
    with log.open("w", encoding="utf-8", errors="replace") as f:
        for vmat in vmats:
            cmd = [str(amp.RESOURCECOMPILER), "-game", str(amp.GAME_DIR), "-i", str(vmat), "-f"]
            f.write("+ " + " ".join(cmd) + "\n")
            cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=amp.CSDK / "game/bin_cs2/win64")
            f.write(cp.stdout)
            f.write("\n")
            if cp.returncode != 0:
                print(cp.stdout[-6000:])
                raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
            compiled += 1
    print(f"compiled {compiled} source VMATs; log={log}")
    return compiled


def copy_source_trees(extracted: Path, content_root: Path) -> None:
    # Models are source modeldocs/meshes from VS2 Explorer. Some may not compile in Deadlock, but they are needed for inspection.
    for rel in ["models", "sounds", "soundevents", "postprocess", "cfg"]:
        src = extracted / rel
        if src.exists():
            dst = content_root / rel
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-vmap", default=str(DEFAULT_SOURCE_VMAP))
    ap.add_argument("--extracted-root", default=str(DEFAULT_EXTRACTED))
    ap.add_argument("--addon", default=DEFAULT_ADDON)
    ap.add_argument("--compile", action="store_true")
    args = ap.parse_args()

    source_vmap = Path(args.source_vmap)
    extracted = Path(args.extracted_root)
    if not source_vmap.exists():
        raise FileNotFoundError(source_vmap)
    for p in [CS2_DMXCONVERT, CS2_GAME / "gameinfo.gi", amp.DMXCONVERT, amp.RESOURCECOMPILER]:
        if not Path(p).exists():
            raise FileNotFoundError(p)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    work = ROOT / "work" / f"transfer_cs2_to_deadlock_{args.addon}_{stamp}"
    content_root = amp.CSDK / "content/citadel_addons" / args.addon
    game_root = amp.CSDK / "game/citadel_addons" / args.addon
    docs = content_root / "_transfer_docs"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for root in [content_root, game_root]:
        if root.exists():
            backup = root.with_name(root.name + f"_backup_{stamp}")
            if backup.exists():
                shutil.rmtree(backup)
            shutil.move(str(root), str(backup))
        root.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)

    kv2 = work / "source_cs2.keyvalues2.vmap"
    run([str(CS2_DMXCONVERT), "-i", str(source_vmap), "-o", str(kv2), "-oe", "keyvalues2", "-of", "vmap"], timeout=600)
    text = kv2.read_text(encoding="utf-8", errors="replace")
    patched, stats = patch_vmap_kv2(text)
    patched_kv2 = work / "bhop_colour.deadlock_transfer.keyvalues2.vmap"
    patched_kv2.write_text(patched, encoding="utf-8", errors="replace")
    shutil.copy2(patched_kv2, docs / patched_kv2.name)

    maps_dir = content_root / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    output_vmap = maps_dir / "bhop_colour.vmap"
    run([str(amp.DMXCONVERT), "-i", str(patched_kv2), "-o", str(output_vmap), "-oe", "binary", "-of", "vmap"], timeout=600)

    copied_images, generated_vmats = copy_textures_and_materials(extracted, content_root, game_root)
    compiled_vmats = compile_source_vmats(content_root, args.addon, stamp)
    copy_source_trees(extracted, content_root)

    matrix = ROOT / "research/visual_compatibility_matrix/bhop_colour_visual_matrix.csv"
    if matrix.exists():
        shutil.copy2(matrix, docs / matrix.name)
    with (docs / "TRANSFER_SUMMARY.md").open("w", encoding="utf-8") as f:
        f.write(f"# CS2 -> Deadlock source transfer prototype\n\n")
        f.write(f"Generated: {stamp}\n\n")
        f.write(f"Source VMAP: `{source_vmap}`\n\n")
        f.write(f"Content addon: `{content_root}`\n\n")
        f.write(f"Game addon: `{game_root}`\n\n")
        f.write("## Entity patch stats\n\n")
        for k in sorted(stats):
            f.write(f"- {k}: {stats[k]}\n")
        f.write(f"\nImages copied: {copied_images}\n\nGenerated Deadlock VMAT sources: {generated_vmats}\n\nCompiled source VMATs: {compiled_vmats}\n")

    if args.compile:
        log = ROOT / "logs" / f"compile_transfer_{args.addon}_{stamp}.log"
        run([str(amp.RESOURCECOMPILER), "-game", str(amp.GAME_DIR), "-i", str(output_vmap), "-f"], stdout=log, timeout=1800)

    print(f"content_root={content_root}")
    print(f"game_root={game_root}")
    print(f"stats={stats}")
    print(f"copied_images={copied_images} generated_vmats={generated_vmats} compiled_vmats={compiled_vmats}")


if __name__ == "__main__":
    main()
