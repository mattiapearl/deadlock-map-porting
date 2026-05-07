#!/usr/bin/env python3
"""Headless CS2/Source 2 workshop map -> Deadlock full-source recompile pipeline.

Environment bindings (all overridable by CLI):
  DEADLOCK_PORT_ROOT       repo/work root
  DEADLOCK_CSDK_ROOT       Reduced_CSDK_12 root
  DEADLOCK_VRF_CLI         Source2Viewer-CLI.exe
  DEADLOCK_GAME_ROOT       live Deadlock root
  DEADLOCK_MEMORY_GB       memory cap for map compile
  DEADLOCK_INSTALL_PAK     live pak*_dir.vpk to overlay when --install is used

The pipeline intentionally prefers valid Deadlock full-source recompiles over exact
CS2 material fidelity. It classifies failures instead of silently guessing.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    import vpk  # type: ignore
except Exception:  # pragma: no cover - reported at runtime for pack/install paths
    vpk = None

STATUSES = {
    "SUCCESS",
    "FAILED_UNSUPPORTED_SHADER",
    "FAILED_MISSING_RESOURCE",
    "FAILED_ENTITY_PATCH",
    "FAILED_MALFORMED_VMAP",
    "FAILED_MEMORY_CAP",
    "FAILED_TIMEOUT",
    "FAILED_UNKNOWN_COMPILER",
}

BHOP_COMMAND = (
    "sv_cheats 1; sv_enablebunnyhopping 1; sv_maxvelocity 99999; "
    "sv_staminamax 0; sv_staminalandcost 0; sv_staminajumpcost 0; "
    "sv_accelerate_use_weapon_speed 0; sv_staminarecoveryrate 60; "
    "sv_autobunnyhopping 1; sv_airaccelerate 1000; mp_roundtime 60; "
    "mp_freezetime 1; sv_falldamage_scale 0; impulse 101; "
    "sv_accelerate 255; sv_maxspeed 99999; game_mode 2; game_type 1"
)


@dataclass
class Paths:
    repo_root: Path
    csdk_root: Path
    vrf_cli: Path
    deadlock_root: Path | None = None

    @property
    def rc(self) -> Path:
        return self.csdk_root / "game/bin_cs2/win64/resourcecompiler.exe"

    @property
    def dmx(self) -> Path:
        return self.csdk_root / "game/bin_cs2/win64/dmxconvert.exe"

    @property
    def resourceinfo(self) -> Path:
        return self.csdk_root / "game/bin_cs2/win64/resourceinfo.exe"

    @property
    def game(self) -> Path:
        return self.csdk_root / "game/citadel"


@dataclass
class RunReport:
    map: str
    addon: str
    status: str = "FAILED_UNKNOWN_COMPILER"
    started: int = field(default_factory=lambda: int(time.time()))
    material_counts: dict[str, int] = field(default_factory=dict)
    removed_aggregate_props: list[str] = field(default_factory=list)
    origin: str | None = None
    origin_method: str | None = None
    logs: list[str] = field(default_factory=list)
    export_vpk: str | None = None
    export_sha256: str | None = None
    installed_pak: str | None = None
    installed_sha256: str | None = None
    backup_pak: str | None = None
    peak_gib: float | None = None
    error: str | None = None

    def fail(self, status: str, error: str | None = None) -> None:
        assert status in STATUSES
        self.status = status
        self.error = error


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], log: Path | None = None, timeout: int | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(map(str, cmd)), flush=True)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8", errors="replace") as f:
            p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    else:
        p = subprocess.run(cmd, text=True, timeout=timeout)
    print("  rc=", p.returncode, flush=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed rc={p.returncode}: {' '.join(map(str, cmd))}; see {log}")
    return p


def vmat_param(text: str, *names: str) -> str | None:
    for name in names:
        m = re.search(rf'"{re.escape(name)}"\s+"([^"]+)"', text)
        if m:
            return m.group(1)
    return None


def vmat_flag(text: str, name: str) -> bool:
    return bool(re.search(rf'"{re.escape(name)}"\s+"?(?:1|true)"?', text, re.I))


def write_sky_fallback(path: Path, text: str, reason: str) -> str:
    path.with_suffix(path.suffix + f".{reason}.bak").write_text(text, encoding="utf-8")
    path.write_text(
        f"// Rebound to CSDK sky texture for Deadlock compile compatibility ({reason})\n\n"
        '"Layer0"\n{\n\t"shader"\t"sky.vfx"\n'
        '\t"g_flBrightnessExposureBias"\t"-1"\n'
        '\t"g_flRenderOnlyExposureBias"\t"0"\n'
        '\t"SkyTexture"\t"materials/skybox/sky_dl_dusk03_exr_9dd50fb1.png"\n'
        "}\n",
        encoding="utf-8",
    )
    return "sky"


def write_pbr(path: Path, text: str, shader: str, mode: str) -> str:
    color = vmat_param(text, "TextureColor", "TextureLayer1Color", "g_tColor") or "materials/default/default_color.tga"
    normal = vmat_param(text, "TextureNormal", "TextureLayer1NormalRoughness", "g_tNormal", "g_tLayer1NormalRoughness")
    self_mask = vmat_param(text, "TextureSelfIllumMask", "g_tSelfIllumMask")
    tint = vmat_param(text, "g_vColorTint", "g_vLayer1Tint") or "[1.000000 1.000000 1.000000 0.000000]"
    metal = vmat_param(text, "g_flMetalness") or "0.000000"
    opacity = vmat_param(text, "g_flOpacityScale") or "1.000000"
    self_scale = vmat_param(text, "g_flSelfIllumScale", "g_flSelfIllumBrightness") or "1.000000"
    self_tint = vmat_param(text, "g_vSelfIllumTint") or tint

    is_emissive = vmat_flag(text, "F_SELF_ILLUM") or self_mask is not None or "SelfIllum" in text
    if is_emissive:
        try:
            self_scale = f"{max(float(self_scale), 2.5):.6f}"
        except ValueError:
            self_scale = "2.500000"
    is_translucent = vmat_flag(text, "F_TRANSLUCENT") or opacity not in ("1", "1.0", "1.00", "1.000000")
    is_glass = "glass" in shader.lower() or "glass" in path.stem.lower()

    path.with_suffix(path.suffix + f".{shader.replace('.vfx', '')}.bak").write_text(text, encoding="utf-8")
    lines = [
        f"// Ported from CS2 {shader} to Deadlock pbr.vfx ({mode})",
        '"Layer0"',
        "{",
        '\t"shader"\t"pbr.vfx"',
    ]
    if is_emissive:
        lines += ['\t"F_UNLIT"\t"1"', '\t"F_SELF_ILLUM"\t"1"']
    if is_glass:
        lines.append('\t"F_GLASS"\t"1"')
    if is_translucent and not is_glass:
        lines.append('\t"F_TRANSLUCENT"\t"1"')
    lines += [
        f'\t"TextureColor1"\t"{color}"',
        f'\t"g_vColorTint1"\t"{tint}"',
        f'\t"g_flOpacityScale1"\t"{opacity}"',
        f'\t"TextureNormal1"\t"{normal or "materials/default/default_normal.tga"}"',
    ]
    if is_emissive:
        lines += [
            '\t"g_flSelfIllumAlbedoFactor1"\t"1.000000"',
            f'\t"g_flSelfIllumScale1"\t"{self_scale}"',
            f'\t"g_vSelfIllumTint1"\t"{self_tint}"',
            f'\t"TextureSelfIllumMask1"\t"{self_mask or color}"',
        ]
    if is_glass:
        lines.append(f'\t"TextureGlassMask1"\t"{self_mask or color}"')
    lines += [
        '\t"TextureRoughness1"\t"[0.350000 0.350000 0.350000 0.000000]"',
        f'\t"TextureMetalness1"\t"[{metal} {metal} {metal} 0.000000]"',
        "}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    if is_emissive:
        return "emissive_pbr"
    if is_glass:
        return "glass_pbr"
    if is_translucent:
        return "translucent_pbr"
    if normal or tint != "[1.000000 1.000000 1.000000 0.000000]" or metal not in ("0", "0.0", "0.000000"):
        return "enriched_pbr"
    return "pbr"


def rewrite_vmat(path: Path) -> str | None:
    text = path.read_text(errors="replace")
    shader = vmat_param(text, "shader")
    if shader == "csgo_moondome.vfx":
        return write_sky_fallback(path, text, "csgo_moondome")
    if shader == "sky.vfx":
        return write_sky_fallback(path, text, "custom_sky")
    if shader and shader.startswith("csgo_"):
        if shader == "csgo_water_fancy.vfx":
            return write_pbr(path, text, shader, "water_degraded")
        return write_pbr(path, text, shader, "classified")
    return None


def make_texture_settings(materials_root: Path) -> None:
    if not materials_root.exists():
        return
    for img in list(materials_root.rglob("*.png")) + list(materials_root.rglob("*.tga")) + list(materials_root.rglob("*.exr")):
        txt = img.with_suffix(".txt")
        if not txt.exists():
            txt.write_text('"settings"\n{\n}\n', encoding="utf-8")


def decompile_if_needed(args: argparse.Namespace, paths: Paths, work: Path, report: RunReport) -> tuple[Path, Path]:
    inner = work / "decompile_inner"
    outer = work / "decompile_outer"
    if args.skip_decompile:
        return inner, outer
    if inner.exists():
        shutil.rmtree(inner)
    if outer.exists():
        shutil.rmtree(outer)
    inner.mkdir(parents=True)
    outer.mkdir(parents=True)
    map_vpk = Path(args.workshop_root) / "extract" / "maps" / f"{args.map}.vpk"
    outer_root = Path(args.workshop_root) / "extract"
    if not map_vpk.exists():
        map_vpk = Path(args.workshop_root) / "maps" / f"{args.map}.vpk"
        outer_root = Path(args.workshop_root)
    if not map_vpk.exists():
        raise FileNotFoundError(f"inner map VPK not found for {args.map} under {args.workshop_root}")
    log1 = work / "vrf_inner.log"
    log2 = work / "vrf_outer_folder.log"
    run([str(paths.vrf_cli), "-i", str(map_vpk), "-o", str(inner), "--vpk_decompile", "--threads", str(args.vrf_threads)], log=log1, timeout=3600)
    run([str(paths.vrf_cli), "-i", str(outer_root), "-o", str(outer), "--vpk_decompile", "--recursive", "--threads", str(args.vrf_threads)], log=log2, timeout=3600)
    report.logs += [str(log1), str(log2)]
    return inner, outer


def stage(args: argparse.Namespace, paths: Paths, inner: Path, outer: Path, report: RunReport) -> tuple[Path, Path]:
    content_addon = paths.csdk_root / "content/citadel_addons" / args.addon
    game_addon = paths.csdk_root / "game/citadel_addons" / args.addon
    if content_addon.exists():
        shutil.rmtree(content_addon)
    if game_addon.exists():
        shutil.rmtree(game_addon)
    (content_addon / "maps").mkdir(parents=True)
    game_addon.mkdir(parents=True)
    (game_addon / "addoninfo.txt").write_text('"addoninfo"\n{\n\t"IsPlayable"\t"1"\n}\n', encoding="utf-8")
    shutil.copytree(inner / "maps", content_addon / "maps", dirs_exist_ok=True)
    for sub in ["materials", "postprocess", "soundevents", "sounds"]:
        s = outer / sub
        if s.exists():
            shutil.copytree(s, content_addon / sub, dirs_exist_ok=True)
    mats = content_addon / "materials"
    make_texture_settings(mats)
    counts = collections.Counter()
    for vmat in mats.rglob("*.vmat") if mats.exists() else []:
        kind = rewrite_vmat(vmat)
        if kind:
            counts[kind] += 1
    report.material_counts = dict(counts)
    return content_addon, game_addon


def convert_vmap_to_kv2(paths: Paths, src: Path, dst: Path, log: Path) -> None:
    run([str(paths.dmx), "-i", str(src), "-o", str(dst), "-oe", "keyvalues2", "-of", "vmap"], log=log, timeout=600)


def convert_kv2_to_vmap(paths: Paths, src: Path, dst: Path, log: Path) -> None:
    run([str(paths.dmx), "-i", str(src), "-o", str(dst), "-oe", "binary", "-of", "vmap"], log=log, timeout=600)


def find_origin(text: str) -> tuple[str, str]:
    names = ["Start", "start", "stage1", "Stage1", "map_start", "MapStart", "bonus_start"]
    for name in names:
        idx = text.find(f'"targetname" "string" "{name}"')
        if idx >= 0:
            origin = origin_from_entity_block(text, idx)
            if origin:
                return origin, f"targetname:{name}"
    for token in ["start", "stage", "spawn"]:
        for m in re.finditer(r'"targetname" "string" "([^"]+)"', text):
            if token in m.group(1).lower():
                origin = origin_from_entity_block(text, m.start())
                if origin:
                    return origin, f"targetname_contains:{token}"
    for cls in ["info_teleport_destination", "info_player_terrorist", "info_player_counterterrorist", "info_player_start"]:
        idx = text.find(f'"classname" "string" "{cls}"')
        if idx >= 0:
            origin = origin_from_entity_block(text, idx)
            if origin:
                return origin, f"classname:{cls}"
    origins = [tuple(map(float, m.group(1).split())) for m in re.finditer(r'"origin" "vector3" "([\-0-9\. ]+)"', text)]
    if origins:
        xs, ys, zs = zip(*origins)
        return f"{(min(xs)+max(xs))/2:.3f} {(min(ys)+max(ys))/2:.3f} {sorted(zs)[max(0, len(zs)//10)] + 64:.3f}", "bounds"
    return "0 0 128", "fallback"


def origin_from_entity_block(text: str, idx: int) -> str | None:
    start = text.rfind('"CMapEntity"', 0, idx)
    end = text.find('\n\t\t\t"CMapEntity"', idx)
    block = text[start:end if end > 0 else idx + 5000]
    m = re.search(r'"origin" "vector3" "([^"]+)"', block)
    return m.group(1) if m else None


def next_node_id(text: str) -> int:
    nums = [int(x) for x in re.findall(r'"nodeID" "int" "(\d+)"', text)]
    return max(nums) + 1000 if nums else 99000


def make_entity(classname: str, props: dict[str, str], origin: str, node_id: int, connections: str = "") -> tuple[str, str]:
    eid_top, eid_plug, eid_ep = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    ref = f"0x{random.getrandbits(64):016x}"
    seed = random.randint(1, 2**31 - 1)
    prop_lines = [f'\t\t\t"classname" "string" "{classname}"'] + [f'\t\t\t"{k}" "string" "{v}"' for k, v in props.items()]
    block = f'''
"CMapEntity"
{{
\t"id" "elementid" "{eid_top}"
\t"nodeID" "int" "{node_id}"
\t"referenceID" "uint64" "{ref}"
\t"children" "element_array" \n\t[
\t]
\t"relayPlugData" "DmePlugList"
\t{{
\t\t"id" "elementid" "{eid_plug}"
\t}}
\t"connectionsData" "element_array" \n\t[
{connections}\t]
\t"entity_properties" "EditGameClassProps"
\t{{
\t\t"id" "elementid" "{eid_ep}"
{chr(10).join(prop_lines)}
\t}}
\t"origin" "vector3" "{origin}"
\t"angles" "qangle" "0 0 0"
\t"scales" "vector3" "1 1 1"
\t"nodeID" "int" "{node_id}"
\t"referenceID" "uint64" "{ref}"
\t"children" "element_array" \n\t[
\t]
\t"editorOnly" "bool" "0"
\t"force_hidden" "bool" "0"
\t"randomSeed" "int" "{seed}"
}}
'''
    return eid_top, block


def make_connection() -> str:
    return f'''\t\t"DmeConnectionData"
\t\t{{
\t\t\t"id" "elementid" "{uuid.uuid4()}"
\t\t\t"outputName" "string" "OnMapSpawn"
\t\t\t"targetType" "int" "7"
\t\t\t"targetName" "string" "panel"
\t\t\t"inputName" "string" "Command"
\t\t\t"overrideParam" "string" "{BHOP_COMMAND}"
\t\t\t"delay" "float" "0"
\t\t\t"timesToFire" "int" "-1"
\t\t}}
'''


def remove_aggregate_proxy(text: str, map_name: str, report: RunReport) -> str:
    patterns = [
        rf'"model" "string" "maps/{re.escape(map_name)}/worldnodes/[^"]*(?:agg|cb_mesh)[^"]*\.vmdl"',
        rf'"model" "string" "maps/{re.escape(map_name)}/n0_lr[^"]*cb_mesh[^"]*\.vmdl"',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        block_start = text.rfind('\n"CMapEntity"', 0, m.start())
        if block_start < 0:
            continue
        brace = text.find('{', block_start)
        depth = 1
        j = brace + 1
        while j < len(text) and depth:
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
            j += 1
        block = text[block_start:j]
        if '"classname" "string" "prop_static"' not in block:
            continue
        eid = re.search(r'"id" "elementid" "([^"]+)"', block)
        if eid:
            report.removed_aggregate_props.append(eid.group(1))
            text = text[:block_start] + text[j:]
            text = re.sub(r'\n\s*"element" "' + re.escape(eid.group(1)) + r'",?', '', text, count=1)
    return text


def patch_entities(args: argparse.Namespace, paths: Paths, content_addon: Path, work: Path, report: RunReport) -> None:
    vmap = content_addon / "maps" / f"{args.map}.vmap"
    kv2 = work / f"{args.map}.kv2.txt"
    patched = work / f"{args.map}.patched.kv2.txt"
    convert_vmap_to_kv2(paths, vmap, kv2, work / "dmx_to_kv2.log")
    text = kv2.read_text(errors="replace")
    text = remove_aggregate_proxy(text, args.map, report)
    origin, method = find_origin(text)
    report.origin, report.origin_method = origin, method
    nid = next_node_id(text)
    ents: list[tuple[str, str]] = []
    if '"classname" "string" "point_servercommand"' not in text:
        ents.append(make_entity("point_servercommand", {"targetname": "panel", "vscripts": ""}, "0 0 0", nid)); nid += 1
    if '"classname" "string" "logic_auto"' not in text:
        ents.append(make_entity("logic_auto", {"spawnflags": "0", "vscripts": "", "targetname": "", "globalstate": ""}, "0 0 0", nid, make_connection())); nid += 1
    for team in (2, 3, 4):
        ents.append(make_entity("info_team_spawn", {"grouptag": "0", "initialspawn": "0", "teamnumber": str(team), "lanenum": "6", "vscripts": "", "targetname": "", "hero_model": ""}, origin, nid)); nid += 1
    if '"targetname" "string" "stage1"' not in text:
        ents.append(make_entity("info_teleport_destination", {"targetname": "stage1"}, origin, nid)); nid += 1
    ck = text.find('"children" "element_array"')
    arr_open = text.find('[', ck)
    arr_close = text.find('\n\t\t]', arr_open)
    if ck < 0 or arr_open < 0 or arr_close < 0:
        raise RuntimeError("could not find CMapWorld children array")
    before_close = text[:arr_close].rstrip()
    sep = ",\n" if not before_close.endswith('[') else "\n"
    ref_text = sep + ",\n".join(f'\t\t\t"element" "{eid}"' for eid, _ in ents)
    text = text[:arr_close] + ref_text + text[arr_close:]
    text = text.rstrip() + "\n" + "\n".join(block for _, block in ents) + "\n"
    patched.write_text(text, encoding="utf-8", errors="replace")
    convert_kv2_to_vmap(paths, patched, vmap, work / "dmx_to_binary.log")


def compile_inputs(args: argparse.Namespace, paths: Paths, content_addon: Path, work: Path, report: RunReport) -> None:
    log_dir = paths.repo_root / "logs"
    for pattern, timeout in [("materials/**/*.vmat", 300), ("postprocess/**/*.vpost", 300), (f"maps/{args.map}/**/*.vmdl", 300)]:
        for src in sorted(content_addon.glob(pattern)):
            rel = src.relative_to(content_addon)
            log = log_dir / f"compile_{args.addon}_{str(rel).replace(os.sep, '_')}.log"
            run([str(paths.rc), "-i", str(src), "-game", str(paths.game), "-nop4"], log=log, timeout=timeout)
            report.logs.append(str(log))


def classify_failed_compile(log: Path) -> tuple[str, float | None, str]:
    text = log.read_text(errors="replace") if log.exists() else ""
    peak = None
    m = re.search(r'peak observed: ([0-9\.]+) GiB', text)
    if m:
        peak = float(m.group(1))
    if "[memlimit] killing process tree" in text:
        return "FAILED_MEMORY_CAP", peak, "memory cap exceeded"
    if "No valid vcs file found for shader" in text or "Feature combo not found" in text:
        return "FAILED_UNSUPPORTED_SHADER", peak, "unsupported shader/material"
    if "ERROR_FILEOPEN" in text or "Unable to read file" in text:
        return "FAILED_MISSING_RESOURCE", peak, "missing resource"
    return "FAILED_UNKNOWN_COMPILER", peak, "compiler failed"


def compile_map(args: argparse.Namespace, paths: Paths, content_addon: Path, report: RunReport) -> None:
    log = paths.repo_root / "logs" / f"compile_{args.addon}_{int(time.time())}.log"
    cmd = [sys.executable, str(paths.repo_root / "tools/compile_with_memory_limit.py"), "--limit-gb", str(args.memory_gb), "--", str(paths.rc), "-i", str(content_addon / "maps" / f"{args.map}.vmap"), "-game", str(paths.game), "-nop4"]
    if args.compile_flag:
        cmd.append(args.compile_flag)
    p = run(cmd, log=log, timeout=args.compile_timeout, check=False)
    report.logs.append(str(log))
    if p.returncode != 0:
        status, peak, msg = classify_failed_compile(log)
        report.peak_gib = peak
        report.fail(status, msg)
        raise RuntimeError(msg)
    status, peak, _ = classify_failed_compile(log)
    report.peak_gib = peak


def pack_export(args: argparse.Namespace, game_addon: Path, paths: Paths, report: RunReport) -> Path:
    if vpk is None:
        raise RuntimeError("Python vpk package is required for packing")
    out_dir = paths.repo_root / "exports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{args.map}_full_recompile_{int(time.time())}_dir.vpk"
    stage = Path(tempfile.mkdtemp(prefix=f"pack_{args.map}_"))
    for sub in ["materials", "postprocess", "lighting", "soundevents", "sounds"]:
        if (game_addon / sub).exists():
            shutil.copytree(game_addon / sub, stage / sub)
    (stage / "maps").mkdir(parents=True, exist_ok=True)
    shutil.copy2(game_addon / "maps" / f"{args.map}.vpk", stage / "maps" / f"{args.map}.vpk")
    (stage / "README.txt").write_text(f"{args.map} full-source Deadlock recompile\n", encoding="utf-8")
    if out.exists():
        out.unlink()
    vpk.new(str(stage)).save(str(out))
    report.export_vpk = str(out)
    report.export_sha256 = sha256_file(out)
    return out


def stop_deadlock_if_needed(force: bool) -> None:
    if os.name != "nt":
        return
    ps = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process deadlock -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"], capture_output=True, text=True)
    ids = [x.strip() for x in ps.stdout.splitlines() if x.strip()]
    if ids and not force:
        raise RuntimeError("Deadlock is running; rerun with --force-stop-deadlock to install")
    for pid in ids:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"], check=False)
    if ids:
        time.sleep(2)


def install(args: argparse.Namespace, export_vpk: Path, report: RunReport) -> None:
    if vpk is None:
        raise RuntimeError("Python vpk package is required for install")
    target = Path(args.install_pak)
    stop_deadlock_if_needed(args.force_stop_deadlock)
    backup_dir = Path(args.backup_dir) if args.backup_dir else Path("live_backups") / f"install_{args.map}_{int(time.time())}"
    if not backup_dir.is_absolute():
        backup_dir = Path.cwd() / backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / target.name
    shutil.copy2(target, backup)
    work = Path(tempfile.mkdtemp(prefix=f"install_{args.map}_"))
    live_x, src_x = work / "live", work / "src"
    live_x.mkdir(); src_x.mkdir()
    run(["vpk", "-x", str(live_x), str(target)], check=True)
    run(["vpk", "-x", str(src_x), str(export_vpk)], check=True)
    for p in src_x.rglob("*"):
        if p.is_file():
            rel = p.relative_to(src_x)
            dst = live_x / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    out = work / target.name
    vpk.new(str(live_x)).save(str(out))
    shutil.copy2(out, target)
    report.backup_pak = str(backup)
    report.installed_pak = str(target)
    report.installed_sha256 = sha256_file(target)


def write_reports(paths: Paths, report: RunReport) -> None:
    reports = paths.repo_root / "reports"
    reports.mkdir(exist_ok=True)
    base = reports / f"full_recompile_{report.map}_{report.started}"
    (base.with_suffix(".json")).write_text(json.dumps(report.__dict__, indent=2), encoding="utf-8")
    md = [f"# {report.map} full recompile report", "", f"Status: `{report.status}`", "", "```json", json.dumps(report.__dict__, indent=2), "```", ""]
    (base.with_suffix(".md")).write_text("\n".join(md), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    env = os.environ
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workshop-root", required=True)
    p.add_argument("--map", required=True)
    p.add_argument("--addon")
    p.add_argument("--repo-root", default=env.get("DEADLOCK_PORT_ROOT", str(Path.cwd())))
    p.add_argument("--csdk-root", default=env.get("DEADLOCK_CSDK_ROOT", r"C:/Users/User/Documents/Reduced_CSDK_12"))
    p.add_argument("--vrf-cli", default=env.get("DEADLOCK_VRF_CLI", r"C:/Code/tools/vrf/Source2Viewer-CLI.exe"))
    p.add_argument("--deadlock-root", default=env.get("DEADLOCK_GAME_ROOT"))
    p.add_argument("--memory-gb", type=float, default=float(env.get("DEADLOCK_MEMORY_GB", "28")))
    p.add_argument("--compile-timeout", type=int, default=7200)
    p.add_argument("--compile-flag", choices=["-fshallow", "-fshallow2"])
    p.add_argument("--vrf-threads", type=int, default=8)
    p.add_argument("--skip-decompile", action="store_true")
    p.add_argument("--no-pack", action="store_true")
    p.add_argument("--install", action="store_true")
    p.add_argument("--install-pak", default=env.get("DEADLOCK_INSTALL_PAK"))
    p.add_argument("--force-stop-deadlock", action="store_true")
    p.add_argument("--backup-dir")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    args.addon = args.addon or f"{args.map}_full_recompile"
    paths = Paths(Path(args.repo_root), Path(args.csdk_root), Path(args.vrf_cli), Path(args.deadlock_root) if args.deadlock_root else None)
    work = paths.repo_root / "work" / f"full_recompile_{args.map}"
    work.mkdir(parents=True, exist_ok=True)
    report = RunReport(args.map, args.addon)
    try:
        inner, outer = decompile_if_needed(args, paths, work, report)
        content_addon, game_addon = stage(args, paths, inner, outer, report)
        patch_entities(args, paths, content_addon, work, report)
        compile_inputs(args, paths, content_addon, work, report)
        compile_map(args, paths, content_addon, report)
        export = None if args.no_pack else pack_export(args, game_addon, paths, report)
        if args.install:
            if not args.install_pak:
                raise RuntimeError("--install requires --install-pak or DEADLOCK_INSTALL_PAK")
            if export is None:
                raise RuntimeError("--install requires packing")
            install(args, export, report)
        report.status = "SUCCESS"
    except RuntimeError as e:
        if report.status == "FAILED_UNKNOWN_COMPILER":
            report.error = str(e)
        print(f"ERROR: {report.status}: {e}", file=sys.stderr)
    finally:
        write_reports(paths, report)
    return 0 if report.status == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
