#!/usr/bin/env python3
"""Build a Deadlock-loadable package from a CS2 workshop compiled map VPK.

This preserves the nested compiled map VPK and replaces unsupported CS2 VMAT shaders
with simple Deadlock pbr.vfx VMATs at the same material paths.
"""
from __future__ import annotations

import argparse, collections, re, shutil, subprocess, sys, time, zipfile
from pathlib import Path

ROOT = Path("C:/Code/deadlock-map-porting")
CSDK = Path("C:/Users/User/Documents/Reduced_CSDK_12")
GAME = CSDK / "game/citadel"
RC = CSDK / "game/bin_cs2/win64/resourcecompiler.exe"
RI = CSDK / "game/bin_cs2/win64/resourceinfo.exe"
WORKSHOP = Path("C:/Program Files (x86)/Steam/steamapps/workshop/content/730")

COLOR_HINTS = [
    ("red", (1.0, 0.05, 0.03)), ("rouge", (1.0, 0.05, 0.03)),
    ("green", (0.05, 0.85, 0.10)), ("blue", (0.05, 0.20, 1.0)),
    ("cyan", (0.0, 0.85, 1.0)), ("yellow", (1.0, 0.85, 0.05)), ("jaune", (1.0, 0.85, 0.05)),
    ("orange", (1.0, 0.42, 0.05)), ("ornage", (1.0, 0.42, 0.05)), ("organe", (1.0, 0.42, 0.05)),
    ("magenta", (1.0, 0.25, 0.85)), ("white", (1.0, 1.0, 1.0)),
    ("grey", (0.45, 0.45, 0.45)), ("gray", (0.45, 0.45, 0.45)),
    ("black", (0.02, 0.02, 0.02)), ("dark", (0.08, 0.08, 0.08)),
]

def run(cmd, **kw):
    print("$", " ".join(map(str, cmd)))
    cp = subprocess.run([str(c) for c in cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    if cp.returncode:
        print(cp.stdout[-4000:])
        raise SystemExit(cp.returncode)
    return cp.stdout

def infer_color(rel: Path, info: str) -> tuple[float,float,float]:
    m = re.search(r'm_name = "g_v(?:Layer1)?Tint"\s+.*?m_pValue = \[\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)', info, re.S)
    if m:
        return tuple(float(m.group(i)) for i in range(1,4))
    s = rel.as_posix().lower()
    for key, col in COLOR_HINTS:
        if key in s: return col
    return (0.55, 0.55, 0.55)

def write_vmat(dst: Path, color, selfillum=False, translucent=False):
    dst.parent.mkdir(parents=True, exist_ok=True)
    r,g,b = color
    lines = [
        "Layer0", "{", '    shader "pbr.vfx"',
        f'    TextureColor1 "[{r:.4f} {g:.4f} {b:.4f} 1.0]"',
        '    TextureNormal1 "[0.5 0.5 1.0 0.0]"',
        '    TextureRoughness1 "[0.55 0.55 0.55 0.0]"',
        '    TextureMetalness1 "[0.0 0.0 0.0 0.0]"',
        f'    g_vColorTint1 "[{r:.4f} {g:.4f} {b:.4f} 0.0]"',
    ]
    if selfillum:
        lines += ['    F_SELF_ILLUM "1"', '    TextureSelfIllumMask1 "[1.0 1.0 1.0 0.0]"', '    g_flSelfIllumScale1 "1.5"']
    if translucent:
        lines += ['    F_TRANSLUCENT "1"', '    g_flOpacityScale1 "0.55"']
    lines += ["}", ""]
    dst.write_text("\n".join(lines), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workshop_id")
    ap.add_argument("--install-live", action="store_true")
    args = ap.parse_args()
    wid = args.workshop_id
    src = WORKSHOP / wid / f"{wid}_dir.vpk"
    if not src.exists(): raise FileNotFoundError(src)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    work = ROOT / "work" / f"compiled_preserve_{wid}_{stamp}"
    extract = work / "extract"
    content = CSDK / "content/citadel_addons" / f"cs2_{wid}_deadlock_pbr"
    gameaddon = CSDK / "game/citadel_addons" / f"cs2_{wid}_deadlock_pbr"
    stage = work / "stage"
    for p in [extract, content, gameaddon, stage]:
        if p.exists(): shutil.rmtree(p)
        p.mkdir(parents=True)
    run(["vpk", "-x", extract, src])
    nested = next((extract/"maps").glob("*.vpk"))
    mapname = nested.stem
    print("map", mapname)

    summary=[]
    for mat in sorted(extract.rglob("*.vmat_c")):
        relc = mat.relative_to(extract)
        rel = Path(str(relc)[:-2])  # .vmat_c -> .vmat
        info = run([RI, "-game", GAME, "-i", mat, "-all"])
        shader = re.search(r'm_shaderName = "([^"]+)"', info)
        col = infer_color(rel, info)
        selfillum = "F_SELF_ILLUM = 1" in info or "glowing" in rel.as_posix().lower() or "neon" in rel.as_posix().lower()
        translucent = "F_TRANSLUCENT = 1" in info or "opac" in rel.as_posix().lower()
        write_vmat(content / rel, col, selfillum, translucent)
        summary.append((rel.as_posix(), shader.group(1) if shader else "?", col, selfillum, translucent))
    # compile all generated vmats in one pass
    vmats = [str(p) for p in content.rglob("*.vmat")]
    run([RC, "-game", GAME, "-nop4", *vmats], timeout=600)

    shutil.copytree(extract, stage, dirs_exist_ok=True)
    # remove original CS2-shader vmat_c and copy replacement compiled outputs/deps
    for p in stage.rglob("*.vmat_c"): p.unlink()
    if gameaddon.exists():
        shutil.copytree(gameaddon, stage, dirs_exist_ok=True)
    # pack outer addon vpk
    outdir = ROOT / "exports"
    outdir.mkdir(exist_ok=True)
    pak = outdir / f"{mapname}_deadlock_preserve_{wid}_{stamp}_dir.vpk"
    run(["vpk", "-c", stage, pak])
    readme = work / "README.txt"
    readme.write_text(
        f"Map: {mapname}\nWorkshop: {wid}\nPackage: {pak}\n"
        f"Strategy: preserve nested compiled CS2 map VPK; replace outer CS2-shader VMATs with flat Deadlock pbr.vfx VMATs at same paths.\n"
        f"Generated materials: {len(summary)}\n\n" + "\n".join(f"{a} <- {b} color={c} selfillum={d} translucent={e}" for a,b,c,d,e in summary),
        encoding="utf-8")
    z = outdir / f"{mapname}_deadlock_preserve_{wid}_{stamp}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zz:
        zz.write(pak, f"addons/{pak.name}")
        zz.write(readme, "README.txt")
    print("WROTE", pak)
    print("WROTE", z)
    if args.install_live:
        live = Path("C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons")
        live.mkdir(parents=True, exist_ok=True)
        dst = live / pak.name
        shutil.copy2(pak, dst)
        print("INSTALLED", dst)

if __name__ == "__main__": main()
