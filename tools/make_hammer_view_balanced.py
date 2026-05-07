#!/usr/bin/env python3
"""Create higher-fidelity Hammer views for bhop_colour.

Modes:
- balanced: keeps native CMapMesh floors/walls/platforms, removes source-VMDL
  worldnode proxies plus fragile water/glass/tool meshes.
- balanced-tools: same, but keeps tool/nodraw/playerclip meshes so the bhop
  collision/platform language remains visible in Hammer.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:/Code/deadlock-map-porting")
sys.path.insert(0, str(ROOT / "tools"))
import automate_map_port as amp  # noqa: E402
from transfer_cs2_hammer_to_deadlock import find_matching_brace, get_classname  # noqa: E402
from make_hammer_view_lite import replace_root_selection_set  # noqa: E402

FRAGILE_MATERIAL_MARKERS = (
    "materials/colour_base/water/",
    "materials/colour_base/colour_glass.vmat",
)
TOOL_MATERIAL_MARKERS = (
    "materials/tools/",
    "materials/tools_",
)
PROXY_MODEL_MARKER = "maps/bhop_colour/worldnodes/node000_world_"
LIGHT_CLASSES = {"citadel_volume_omni", "env_combined_light_probe_volume"}


def run(cmd: list[str], timeout: int | None = None) -> None:
    print("+ " + " ".join(str(c) for c in cmd), flush=True)
    cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if cp.returncode != 0:
        print(cp.stdout[-6000:])
        raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
    if cp.stdout:
        print(cp.stdout[-1200:])


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


def filter_blocks(text: str, block_type: str, remove_pred):
    out: list[str] = []
    pos = 0
    removed = 0
    for start, end, block in iter_typed_blocks(text, block_type):
        out.append(text[pos:start])
        if remove_pred(block):
            removed += 1
        else:
            out.append(block)
        pos = end
    out.append(text[pos:])
    text = "".join(out)
    text = re.sub(r"(?m)^\s*,\s*$\n?", "", text)
    return text, removed


def is_fragile_mesh(block: str) -> bool:
    b = block.lower()
    return any(marker in b for marker in FRAGILE_MATERIAL_MARKERS)


def is_tool_mesh(block: str) -> bool:
    b = block.lower()
    return any(marker in b for marker in TOOL_MATERIAL_MARKERS)


def is_worldnode_proxy_entity(block: str) -> bool:
    return '"classname" "string" "prop_static"' in block and PROXY_MODEL_MARKER in block


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-vmap", required=True)
    ap.add_argument("--output-vmap", required=True)
    ap.add_argument("--keep-full-copy", default="")
    ap.add_argument("--keep-lights", action="store_true")
    ap.add_argument("--keep-tools", action="store_true", help="Keep tools/nodraw/playerclip meshes visible")
    ap.add_argument("--keep-fragile", action="store_true", help="Keep water/glass meshes too")
    args = ap.parse_args()

    inp = Path(args.input_vmap)
    out = Path(args.output_vmap)
    full = Path(args.keep_full_copy) if args.keep_full_copy else None
    work = ROOT / "tmp" / "hammer_balanced"
    work.mkdir(parents=True, exist_ok=True)
    kv = work / "input.keyvalues2.vmap"
    patched = work / "bhop_colour_hammer_balanced.keyvalues2.vmap"

    if full and inp.resolve() == out.resolve() and not full.exists():
        full.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inp, full)

    run([str(amp.DMXCONVERT), "-i", str(inp), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"], timeout=900)
    text = kv.read_text(encoding="utf-8", errors="replace")
    before = len(text)
    text = re.sub(r'(?m)^\s*"uselocaloffset"\s+"string"\s+"[^"]*"\s*\n', "", text)
    text, removed_proxy = filter_blocks(text, "CMapEntity", is_worldnode_proxy_entity)
    if not args.keep_lights:
        text, removed_lights = filter_blocks(text, "CMapEntity", lambda b: (get_classname(b) or "") in LIGHT_CLASSES)
    else:
        removed_lights = 0

    removed_fragile = 0
    if not args.keep_fragile:
        text, removed_fragile = filter_blocks(text, "CMapMesh", is_fragile_mesh)
    removed_tools = 0
    if not args.keep_tools:
        text, removed_tools = filter_blocks(text, "CMapMesh", is_tool_mesh)

    text, replaced_sets = replace_root_selection_set(text)
    patched.write_text(text, encoding="utf-8", errors="replace")
    run([str(amp.DMXCONVERT), "-i", str(patched), "-o", str(out), "-oe", "binary", "-of", "vmap"], timeout=900)
    print(f"Wrote Hammer balanced VMAP: {out}")
    print(f"KV2 size before/after: {before:,} -> {len(text):,}")
    print(f"removed proxy entities={removed_proxy} removed lights/probes={removed_lights} removed fragile meshes={removed_fragile} removed tool meshes={removed_tools} replacedSelectionSets={replaced_sets}")


if __name__ == "__main__":
    main()
