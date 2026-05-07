#!/usr/bin/env python3
"""Create a Hammer-friendly bhop_colour VMAP view.

The full source-transfer VMAP has ~1475 reconstructed CMapMesh nodes and a 511MB
KV2 representation. Deadlock Hammer can crash while adding those nodes to the
document. This tool creates a proxy/lite view by keeping prop_static model
proxies and gameplay volumes while removing huge editable CMapMesh nodes,
selection-set clutter, converted dynamic lights, and probe volumes.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:/Code/deadlock-map-porting")
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import automate_map_port as amp  # noqa: E402
from transfer_cs2_hammer_to_deadlock import find_matching_brace, get_classname  # noqa: E402

REMOVE_ENTITY_CLASSES = {"citadel_volume_omni", "env_combined_light_probe_volume"}


def run(cmd: list[str], timeout: int | None = None) -> None:
    print("+ " + " ".join(str(c) for c in cmd))
    cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if cp.returncode != 0:
        print(cp.stdout[-6000:])
        raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
    if cp.stdout:
        print(cp.stdout[-2000:])


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


def remove_blocks(text: str, block_type: str, predicate) -> tuple[str, int]:
    out = []
    pos = 0
    removed = 0
    for start, end, block in iter_typed_blocks(text, block_type):
        out.append(text[pos:start])
        if predicate(block):
            removed += 1
        else:
            out.append(block)
        pos = end
    out.append(text[pos:])
    text = "".join(out)
    text = re.sub(r"(?m)^\s*,\s*$\n?", "", text)
    return text, removed


def replace_root_selection_set(text: str) -> tuple[str, bool]:
    key = '"rootSelectionSet" "CMapSelectionSet"'
    idx = text.find(key)
    if idx < 0:
        return text, False
    open_idx = text.find("{", idx + len(key))
    end = find_matching_brace(text, open_idx)
    block = text[open_idx:end + 1]
    m = re.search(r'"id"\s+"elementid"\s+"([^"]+)"', block)
    root_id = m.group(1) if m else "00000000-0000-0000-0000-000000000000"
    replacement = f'''"rootSelectionSet" "CMapSelectionSet"
	{{
		"id" "elementid" "{root_id}"
		"children" "element_array" 
		[
		]
		"selectionSetName" "string" "Root"
	}}
'''
    return text[:idx] + replacement + text[end + 1:], True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-vmap", default=r"C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_colour_hammer_view/maps/bhop_colour.vmap")
    ap.add_argument("--output-vmap", default=r"C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_colour_hammer_view/maps/bhop_colour.vmap")
    ap.add_argument("--keep-full-copy", default=r"C:/Users/User/Documents/Reduced_CSDK_12/content/citadel_addons/bhop_colour_hammer_view/maps/bhop_colour_full_source_transfer.vmap")
    args = ap.parse_args()

    inp = Path(args.input_vmap)
    out = Path(args.output_vmap)
    full = Path(args.keep_full_copy)
    work = ROOT / "tmp" / "hammer_lite"
    work.mkdir(parents=True, exist_ok=True)
    kv = work / "input.keyvalues2.vmap"
    patched = work / "bhop_colour_hammer_lite.keyvalues2.vmap"

    if inp.resolve() == out.resolve() and not full.exists():
        full.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(inp, full)
        print(f"Saved full source-transfer copy: {full}")

    run([str(amp.DMXCONVERT), "-i", str(inp), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"], timeout=600)
    text = kv.read_text(encoding="utf-8", errors="replace")
    before = len(text)
    # Remove duplicate lowercase key emitted by transfer when useLocalOffset also exists.
    text = re.sub(r'(?m)^\s*"uselocaloffset"\s+"string"\s+"[^"]*"\s*\n', "", text)
    text, removed_meshes = remove_blocks(text, "CMapMesh", lambda block: True)
    text, removed_entities = remove_blocks(text, "CMapEntity", lambda block: (get_classname(block) or "") in REMOVE_ENTITY_CLASSES)
    text, replaced_sets = replace_root_selection_set(text)
    patched.write_text(text, encoding="utf-8", errors="replace")
    run([str(amp.DMXCONVERT), "-i", str(patched), "-o", str(out), "-oe", "binary", "-of", "vmap"], timeout=600)
    print(f"Wrote Hammer lite VMAP: {out}")
    print(f"KV2 size before/after: {before:,} -> {len(text):,}")
    print(f"removed CMapMesh={removed_meshes} removed light/probe entities={removed_entities} replacedSelectionSets={replaced_sets}")


if __name__ == "__main__":
    main()
