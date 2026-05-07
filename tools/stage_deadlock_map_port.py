#!/usr/bin/env python3
"""Stage CS2/Source2 custom map assets as Deadlock addon VPKs.

This is intentionally conservative: it never writes into the Deadlock install
unless --install is supplied. It creates staging directories and addon VPKs that
can be copied to game/citadel/addons/pakNN_dir.vpk.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

WORK = Path(r"C:/Code/deadlock-map-porting")
DEADLOCK = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Deadlock")
DEADLOCK_PAK01 = DEADLOCK / "game/citadel/pak01_dir.vpk"
BS = chr(92)

REF_PATTERNS = {
    "materials": rb"materials/[A-Za-z0-9_./\\-]+\.vmat(?:_c)?",
    "textures": rb"materials/[A-Za-z0-9_./\\-]+\.vtex(?:_c)?",
    "models": rb"(?:models|maps)/[A-Za-z0-9_./\\-]+\.vmdl(?:_c)?",
    "entities": rb"\b(?:info_player_terrorist|info_player_counterterrorist|info_player_start|info_teleport_destination|trigger_teleport|trigger_multiple|logic_auto|point_servercommand|env_sky|light_environment|func_[A-Za-z0-9_]+|trigger_[A-Za-z0-9_]+|point_[A-Za-z0-9_]+)\b",
    "commands": rb"(?:sv_[A-Za-z0-9_]+|mp_[A-Za-z0-9_]+|game_mode|game_type|impulse) [^\x00\n\r]{0,160}",
}


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def list_vpk(vpk: Path) -> list[str]:
    cp = run(["vpk", "-l", str(vpk)], stdout=subprocess.PIPE)
    return [line.strip().replace(BS, "/") for line in cp.stdout.splitlines() if line.strip()]


def extract_one_from_vpk(vpk: Path, rel: str, out: Path) -> Path | None:
    before = set(out.rglob("*")) if out.exists() else set()
    out.mkdir(parents=True, exist_ok=True)
    run(["vpk", "-x", str(out), "-f", rel, str(vpk)], stdout=subprocess.DEVNULL)
    target = out / rel
    if target.exists():
        return target
    after = set(out.rglob("*"))
    new_files = [p for p in after - before if p.is_file()]
    return new_files[0] if new_files else None


def scan_refs(paths: list[Path]) -> dict[str, set[str]]:
    refs = {k: set() for k in REF_PATTERNS}
    for p in paths:
        if p.is_dir():
            files = [x for x in p.rglob("*") if x.is_file()]
        else:
            files = [p]
        for f in files:
            if f.stat().st_size > 300_000_000:
                continue
            try:
                data = f.read_bytes()
            except OSError:
                continue
            for label, pat in REF_PATTERNS.items():
                for m in re.findall(pat, data):
                    refs[label].add(m.decode("utf-8", "ignore").replace(BS, "/").removesuffix("_c"))
    return refs


def compiled_name(path: str) -> str:
    return path if path.endswith("_c") else path + "_c"


def stage_workshop_vpk(args: argparse.Namespace) -> None:
    src = Path(args.workshop_vpk)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    dest = out_root / f"pak{args.pak_id:02d}_dir.vpk"
    shutil.copy2(src, dest)
    files = list_vpk(src)
    maps = [p for p in files if p.startswith("maps/") and p.endswith(".vpk")]
    report = [
        "# Staged workshop VPK for Deadlock",
        "",
        f"Source: `{src}`",
        f"Output addon: `{dest}`",
        "",
        "Install by copying the output VPK to `Deadlock/game/citadel/addons/`.",
        "",
        "Map commands to try:",
        "",
    ]
    for m in maps:
        name = Path(m).stem
        report.append(f"- `map {name}`  (`{m}`)")
    report += ["", f"Contained files: `{len(files)}`.", ""]
    (out_root / "README.md").write_text("\n".join(report), encoding="utf-8")
    print(dest)


def stage_emevael(args: argparse.Namespace) -> None:
    src_dir = Path(args.source_dir)
    out_root = Path(args.out)
    stage = out_root / "stage"
    addon = out_root / f"pak{args.pak_id:02d}_dir.vpk"
    refs_dir = WORK / "extracted/deadlock_refs"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)

    # Copy compiled map VPKs from the translated package.
    copied_maps: list[str] = []
    for name in ["bhop_emevaelx3.vpk", "bhop_emevaelx3_environment_prefab.vpk", "bhop_emevaelx3_prefab.vpk"]:
        p = src_dir / name
        if p.exists():
            (stage / "maps").mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, stage / "maps" / name)
            copied_maps.append(f"maps/{name}")

    # Scan the main map VPK and raw extracted folder for material dependencies.
    scan_inputs = [src_dir / "bhop_emevaelx3.vpk", src_dir / "bhop_emevaelx3"]
    refs = scan_refs([p for p in scan_inputs if p.exists()])
    mats = sorted(refs["materials"])

    # Extract a small set of known-good Deadlock compiled materials and duplicate
    # them under missing CS2 material names. This is a visual placeholder strategy:
    # geometry opens with non-checkerboard material while preserving paths.
    placeholder_map: dict[str, str] = {}
    for mat in mats:
        if mat.startswith("materials/tools/"):
            placeholder_map[mat] = compiled_name(mat)
        elif "sky" in mat:
            placeholder_map[mat] = "materials/skybox/sky_dl_sandbox.vmat_c"
        elif "stone" in mat:
            placeholder_map[mat] = "materials/stone/stone_tile_01/stone_tile_01_grey.vmat_c"
        else:
            placeholder_map[mat] = "materials/dev/default.vmat_c"

    staged_mats: list[tuple[str, str, str]] = []
    missing_source: list[tuple[str, str]] = []
    for mat, deadlock_ref in placeholder_map.items():
        src_mat = extract_one_from_vpk(DEADLOCK_PAK01, deadlock_ref, refs_dir)
        target_rel = compiled_name(mat)
        target = stage / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src_mat and src_mat.exists():
            shutil.copy2(src_mat, target)
            staged_mats.append((target_rel, deadlock_ref, "copied"))
        else:
            missing_source.append((target_rel, deadlock_ref))

    # Add map cfg files if present.
    for extra in src_dir.glob("bhop_emevaelx3*.*"):
        if extra.suffix.lower() in {".txt", ".los"}:
            (stage / "maps").mkdir(parents=True, exist_ok=True)
            shutil.copy2(extra, stage / "maps" / extra.name)

    # Build VPK.
    if addon.exists():
        addon.unlink()
    run(["vpk", "-c", str(stage), str(addon)], stdout=subprocess.PIPE)

    commands = sorted(refs["commands"])
    entities = sorted(refs["entities"])
    report = [
        "# bhop_emevaelx3 Deadlock staging report",
        "",
        f"Source: `{src_dir}`",
        f"Output addon VPK: `{addon}`",
        "",
        "Install by copying the output VPK to `Deadlock/game/citadel/addons/` and try:",
        "",
        "```text",
        "map bhop_emevaelx3",
        "```",
        "",
        "## Copied map VPKs",
        "",
        *[f"- `{x}`" for x in copied_maps],
        "",
        "## Material placeholders",
        "",
        "These preserve the referenced CS2 material paths but use compiled Deadlock placeholder materials.",
        "",
        "| Target path | Placeholder source | Status |",
        "|---|---|---|",
        *[f"| `{t}` | `{s}` | {status} |" for t, s, status in staged_mats],
        "",
        "## Map entity / logic references found",
        "",
        *[f"- `{e}`" for e in entities],
        "",
        "## CS2 commands found in map logic",
        "",
        *[f"- `{c}`" for c in commands],
        "",
        "Note: CS2 point_servercommand logic is not a reliable Deadlock gameplay layer. Use a Deadworks plugin for bhop respawn, teleports, checkpoints, and movement convars.",
    ]
    if missing_source:
        report += ["", "## Missing placeholder sources", ""]
        report += [f"- `{target}` wanted `{src}`" for target, src in missing_source]
    (out_root / "README.md").write_text("\n".join(report), encoding="utf-8")
    print(addon)


def audit(args: argparse.Namespace) -> None:
    inputs = [Path(p) for p in args.inputs]
    refs = scan_refs(inputs)
    for label, vals in refs.items():
        print(f"## {label} ({len(vals)})")
        for v in sorted(vals):
            print(v)


def install(args: argparse.Namespace) -> None:
    addon = Path(args.addon_vpk)
    deadlock = Path(args.deadlock)
    dest_dir = deadlock / "game/citadel/addons"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / addon.name
    shutil.copy2(addon, dest)
    print(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)
    p = sub.add_parser("stage-workshop-vpk", help="rename/copy a CS2 workshop VPK as a Deadlock addon VPK")
    p.add_argument("--workshop-vpk", default=r"C:/Users/User/Downloads/730/3071726325/3071726325.vpk")
    p.add_argument("--out", default=str(WORK / "staging/bhop_colour_deadlock_addon"))
    p.add_argument("--pak-id", type=int, default=70)
    p.set_defaults(func=stage_workshop_vpk)

    p = sub.add_parser("stage-emevael", help="stage provided translated bhop_emevaelx3 map with Deadlock placeholder materials")
    p.add_argument("--source-dir", default=str(WORK / "extracted/bhop_emevaelx3_hammer"))
    p.add_argument("--out", default=str(WORK / "staging/bhop_emevaelx3_deadlock_addon"))
    p.add_argument("--pak-id", type=int, default=71)
    p.set_defaults(func=stage_emevael)

    p = sub.add_parser("audit", help="scan resources for material/entity/command references")
    p.add_argument("inputs", nargs="+")
    p.set_defaults(func=audit)

    p = sub.add_parser("install", help="copy a staged addon VPK into a Deadlock install")
    p.add_argument("addon_vpk")
    p.add_argument("--deadlock", default=str(DEADLOCK))
    p.set_defaults(func=install)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
