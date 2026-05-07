#!/usr/bin/env python3
"""Audit extracted Source 2 map visuals against Deadlock replacement matrix."""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT = Path(r"C:/Users/User/Downloads/730")
DEFAULT_MATRIX = Path(r"C:/Code/deadlock-map-porting/research/visual_compatibility_matrix/bhop_colour_visual_matrix.csv")
DEADLOCK_UNAVAILABLE_SOURCE_SHADERS = {
    "csgo_complex.vfx",
    "csgo_static_overlay.vfx",
    "csgo_glass.vfx",
    "csgo_water_fancy.vfx",
}


def parse_shader(text: str) -> str:
    m = re.search(r'"?shader"?\s+"([^"]+)"', text)
    return m.group(1).lower() if m else "unknown"


def load_matrix(path: Path) -> dict[str, list[dict[str, str]]]:
    rows_by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return rows_by_key
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows_by_key[row.get("source_shader_or_class", "").lower()].append(row)
    return rows_by_key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extracted-root", default=str(DEFAULT_ROOT))
    ap.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = Path(args.extracted_root)
    matrix = load_matrix(Path(args.matrix))
    material_root = root / "materials"
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    missing_matrix: set[str] = set()

    for vmat in sorted(material_root.rglob("*.vmat")):
        rel = vmat.relative_to(material_root).as_posix()
        shader = parse_shader(vmat.read_text(encoding="utf-8", errors="replace"))
        counts[shader] += 1
        if len(examples[shader]) < 8:
            examples[shader].append(rel)
        if shader in DEADLOCK_UNAVAILABLE_SOURCE_SHADERS and shader not in matrix:
            missing_matrix.add(shader)

    lines = ["# Visual compatibility audit", "", f"Extracted root: `{root}`", f"Matrix: `{args.matrix}`", ""]
    lines.append("## Material shaders")
    for shader, count in counts.most_common():
        unavailable = "UNAVAILABLE" if shader in DEADLOCK_UNAVAILABLE_SOURCE_SHADERS else "check"
        repl = matrix.get(shader, [{}])[0].get("chosen_replacement", "no matrix row") if matrix.get(shader) else "no matrix row"
        lines.append(f"- `{shader}`: {count} ({unavailable}) -> {repl}")
        for ex in examples[shader]:
            lines.append(f"  - `{ex}`")
    lines.append("")
    if missing_matrix:
        lines.append("## Missing matrix rows")
        for shader in sorted(missing_matrix):
            lines.append(f"- `{shader}`")
    else:
        lines.append("## Missing matrix rows")
        lines.append("none")

    text = "\n".join(lines) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
