#!/usr/bin/env python3
"""Export the current bhop_emevaelx3 roam-fix build without duplicate shadow paths.

The output intentionally uses only game/citadel/addons/pak*.vpk style install
artifacts. It does not include a game/citadel_addons/bhop_emevaelx3_port loose
copy, because that loose root can shadow pak71_dir.vpk and was the cause of a
previous stale-map load failure.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(r"C:/Code/deadlock-map-porting")
CSDK_ADDON = Path(r"C:/Users/User/Documents/Reduced_CSDK_12/game/citadel_addons/bhop_emevaelx3_port")
MOVEMENT_SCRIPT_PAK = ROOT / "research/movementmap/archive/pak03_dir.vpk"
PLUGIN_DLL = ROOT / "plugins/DeadlockBhopRuntime/bin/Release/net10.0/DeadlockBhopRuntime.dll"
FINDINGS = ROOT / "PORTING_FINDINGS.md"
REPORT = ROOT / "reports/movementmap-vs-bhop-comparison-20260503.md"


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree_filtered(src: Path, dst: Path) -> None:
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if any(part.startswith("_") for part in rel.parts):
            continue
        if p.suffix.lower() in {".tmp", ".log", ".bak"}:
            continue
        if rel.name == "addoninfo.txt":
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "exports" / f"bhop_emevaelx3_roamfix_{stamp}"
    stage = out / "_stage_pak71"
    addons = out / "game/citadel/addons"
    docs = out / "docs"
    plugin_dir = out / "game/bin/win64/managed/plugins"

    if out.exists():
        shutil.rmtree(out)
    addons.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    if not MOVEMENT_SCRIPT_PAK.exists():
        raise FileNotFoundError(MOVEMENT_SCRIPT_PAK)
    if not (CSDK_ADDON / "maps/bhop_emevaelx3.vpk").exists():
        raise FileNotFoundError(CSDK_ADDON / "maps/bhop_emevaelx3.vpk")
    if not PLUGIN_DLL.exists():
        raise FileNotFoundError(PLUGIN_DLL)

    shutil.copy2(MOVEMENT_SCRIPT_PAK, addons / "pak70_dir.vpk")
    copy_tree_filtered(CSDK_ADDON, stage)
    run(["vpk", "-c", str(stage), str(addons / "pak71_dir.vpk")])
    shutil.rmtree(stage)

    shutil.copy2(PLUGIN_DLL, plugin_dir / "DeadlockBhopRuntime.dll")
    latest_logs = sorted((ROOT / "logs").glob("compile_bhop_emevaelx3_*.log"), key=lambda p: p.stat().st_mtime)
    doc_sources = ([latest_logs[-1]] if latest_logs else []) + [FINDINGS, REPORT]
    for src in doc_sources:
        if src.exists():
            shutil.copy2(src, docs / src.name)

    readme = out / "README_INSTALL_TEST.txt"
    readme.write_text(f"""# bhop_emevaelx3 roam-fix test package

Generated: {stamp}

Install on a Deadlock/Deadworks test server by copying this package's `game` folder over the Deadlock install root.

This package intentionally contains ONLY addon VPK install paths:

```txt
game/citadel/addons/pak70_dir.vpk  # movementmap-style scripts/heroes + scripts/abilities override
game/citadel/addons/pak71_dir.vpk  # recentered bhop_emevaelx3 map/content
```

It intentionally does NOT include:

```txt
game/citadel_addons/bhop_emevaelx3_port/...
```

Before installing, delete or rename stale copies of:

```txt
game/citadel_addons/bhop_emevaelx3_port*
game/citadel/addons/pak70_dir.vpk
game/citadel/addons/pak71_dir.vpk
```

Then run:

```txt
map bhop_emevaelx3
```

Map-side fixes included:

- full bhop geometry translated by +3104 +7632 0 so the course is centered around world origin;
- clean movementmap-style Deadlock spawns: 20 `info_team_spawn`, no `hero_testing_controller`, no `hero_model` forcing;
- no `point_nav_walkable`; nav remains the same tiny 232-byte style that movementmap uses;
- real compiled `citadel_trigger_suspend_modifier` volume with `modifier_citadel_in_hideout_zone` and model `maps/bhop_emevaelx3/entities/bhop_roam_hideout_volume_26554.vmdl`;
- movementmap-style `scripts/heroes.vdata_c` and `scripts/abilities.vdata` override from `pak03_dir.vpk` included as `pak70_dir.vpk` for A/B parity.

Runtime fallback included at the Deadworks plugin load path:

```txt
game/bin/win64/managed/plugins/DeadlockBhopRuntime.dll
```

Use that plugin if map-side fixes still show:

```txt
Player ... is out of the play area
CLASS_DAMAGETYPE_ENVIRONMENTAL
```

The plugin is roam-only: it blocks pawn damage on bhop/movement maps and does not implement timers/checkpoints.
""", encoding="utf-8")

    cleanup = out / "CLEAN_STALE_BHOP_PATHS.bat"
    cleanup.write_text(r"""@echo off
setlocal
set DEADLOCK=%~1
if "%DEADLOCK%"=="" set DEADLOCK=C:\Program Files (x86)\Steam\steamapps\common\Deadlock

echo Cleaning stale bhop install paths under: %DEADLOCK%
for /d %%D in ("%DEADLOCK%\game\citadel_addons\bhop_emevaelx3_port*") do ren "%%~fD" "%%~nxD.stale.%RANDOM%"
if exist "%DEADLOCK%\game\citadel\addons\pak71_dir.vpk" ren "%DEADLOCK%\game\citadel\addons\pak71_dir.vpk" "pak71_dir.vpk.stale.%RANDOM%"
if exist "%DEADLOCK%\game\citadel\addons\pak70_dir.vpk" ren "%DEADLOCK%\game\citadel\addons\pak70_dir.vpk" "pak70_dir.vpk.stale.%RANDOM%"
echo Done. Now copy this package's game folder over %DEADLOCK%.
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

    print(out)
    print(zip_path)


if __name__ == "__main__":
    main()
