#!/usr/bin/env python3
"""Automate repeatable CS2/Source 2 -> Deadlock map-port fixups.

Currently handles the first fatal Deadlock local-load issue we hit:
CS2 point-prefab entities such as prefabs/misc/team_select are compiled into
maps and Deadlock disconnects with NETWORK_DISCONNECT_CLIENT_NO_MAP when those
prefab map VPKs are absent.

The tool converts a binary .vmap to keyvalues2 text with dmxconvert, removes
unsupported CS2 point-prefab CMapEntity blocks, converts back to binary, compiles
with the CSDK bin_cs2 resourcecompiler, and can install the resulting CSDK addon
into the live Deadlock install.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

CSDK = Path(r"C:/Users/User/Documents/Reduced_CSDK_12")
DEADLOCK = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Deadlock")
DMXCONVERT = CSDK / "game/bin_cs2/win64/dmxconvert.exe"
RESOURCECOMPILER = CSDK / "game/bin_cs2/win64/resourcecompiler.exe"
GAME_DIR = CSDK / "game/citadel"

CS2_POINT_PREFAB_PREFIXES = (
    "prefabs/misc/",
)

CS2_GAMEPLAY_CLASS_PREFIXES = (
    "info_player_",
)

DEADLOCK_GENERATED_SHELL_CLASSES = {
    "citadel_minimap_boundary",
    "citadel_trigger_suspend_modifier",
    "hero_testing_controller",
    "info_team_spawn",
    "point_nav_walkable",
    "trigger_modifier",
}

CS2_GAMEPLAY_CLASSES = {
    "game_player_equip",
    "game_player_team",
    "game_round_end",
    "game_score",
    "game_text",
    "info_deathmatch_spawn",
    "info_player_start",
    "info_teleport_destination",
    "logic_auto",
    "logic_branch",
    "logic_case",
    "logic_compare",
    "logic_eventlistener",
    "logic_measure_movement",
    "logic_relay",
    "logic_timer",
    "point_clientcommand",
    "point_servercommand",
    "team_select",
    "terrorist_team_intro",
    "counterterrorist_team_intro",
    "end_of_match",
    "trigger_hurt",
    "trigger_multiple",
    "trigger_once",
    "trigger_push",
    "trigger_teleport",
}


def run(cmd: list[str], *, cwd: Path | None = None, log: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(str(x) for x in cmd))
    cp = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(cp.stdout, encoding="utf-8", errors="replace")
    if cp.returncode != 0:
        if cp.stdout:
            print(cp.stdout[-4000:])
        raise subprocess.CalledProcessError(cp.returncode, cmd, output=cp.stdout)
    if cp.stdout:
        print(cp.stdout[-4000:])
    return cp


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def matching_brace_block(lines: list[str], object_line: int) -> tuple[int, int] | None:
    """Return [start,end) for a DMX object whose type is at object_line."""
    if object_line + 1 >= len(lines) or lines[object_line + 1].strip() != "{":
        return None
    depth = 0
    for i in range(object_line + 1, len(lines)):
        stripped = lines[i].strip().rstrip(",")
        if stripped == "{":
            depth += 1
        elif stripped == "}":
            depth -= 1
            if depth == 0:
                return object_line, i + 1
    return None


def should_strip_entity(block: str) -> bool:
    target = re.search(r'"targetmapname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
    is_point_prefab = re.search(r'"ispointprefab"\s+"string"\s+"true"', block, re.IGNORECASE)
    if target and target.group(1).lower().startswith(CS2_POINT_PREFAB_PREFIXES):
        return True
    # Some converted CS2 maps carry point-prefab metadata under slightly different
    # casing. Restrict this fallback to known CS2 prefab classes to avoid stripping
    # normal map logic.
    classname = re.search(r'"classname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
    if is_point_prefab and classname and classname.group(1).lower() in {
        "team_select",
        "terrorist_team_intro",
        "counterterrorist_team_intro",
        "end_of_match",
    }:
        return True
    return False


def strip_cs2_point_prefabs_from_keyvalues(text: str) -> tuple[str, list[dict[str, str]]]:
    lines = text.splitlines(keepends=True)
    remove_ranges: list[tuple[int, int]] = []
    removed: list[dict[str, str]] = []
    remove_ids: set[str] = set()

    i = 0
    while i < len(lines):
        if lines[i].strip() == '"CMapEntity"':
            block_range = matching_brace_block(lines, i)
            if not block_range:
                i += 1
                continue
            start, end = block_range
            block = "".join(lines[start:end])
            if should_strip_entity(block):
                entity_id = re.search(r'"id"\s+"elementid"\s+"([^"]+)"', block)
                classname = re.search(r'"classname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
                target = re.search(r'"targetmapname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
                node_id = re.search(r'"nodeID"\s+"int"\s+"([^"]+)"', block)
                if entity_id:
                    remove_ids.add(entity_id.group(1))
                removed.append({
                    "id": entity_id.group(1) if entity_id else "",
                    "nodeID": node_id.group(1) if node_id else "",
                    "classname": classname.group(1) if classname else "",
                    "targetmapname": target.group(1) if target else "",
                })
                remove_ranges.append((start, end))
            i = end
            continue
        i += 1

    if not remove_ranges:
        return text, []

    output: list[str] = []
    range_idx = 0
    i = 0
    while i < len(lines):
        if range_idx < len(remove_ranges) and i == remove_ranges[range_idx][0]:
            i = remove_ranges[range_idx][1]
            range_idx += 1
            continue

        line = lines[i]
        # Remove parent/selection references to stripped entities. Leaving dangling
        # element references can make dmxconvert/resourcecompiler reject the map.
        if any(f'"element" "{entity_id}"' in line for entity_id in remove_ids):
            i += 1
            continue
        output.append(line)
        i += 1

    return "".join(output), removed


def strip_sidecar_vents(vmap: Path) -> list[str]:
    """Keep extracted/generated plaintext entity sidecars consistent for audits/manual GUI work."""
    sidecar = vmap.parent / vmap.stem / "entities/default_ents.vents"
    if not sidecar.exists():
        return []
    text = sidecar.read_text(encoding="utf-8", errors="replace")
    if "prefabs/misc/" not in text:
        return []
    backup = sidecar.with_suffix(sidecar.suffix + f".bak_cs2_prefabs_{timestamp()}")
    shutil.copy2(sidecar, backup)
    parts = re.split(r'(?m)^====(\d+)====\n', text)
    output = [parts[0]]
    removed: list[str] = []
    for i in range(1, len(parts), 2):
        number = parts[i]
        body = parts[i + 1]
        if "targetmapname" in body.lower() and "prefabs/misc/" in body.lower():
            removed.append(number)
            continue
        output.append(f"===={number}====\n")
        output.append(body)
    if removed:
        sidecar.write_text("".join(output), encoding="utf-8", errors="replace")
        print(f"Stripped sidecar entity blocks {removed}: {sidecar}")
        print(f"Sidecar backup: {backup}")
    return removed


def make_cmap_entity(
    *,
    classname: str,
    origin: tuple[float, float, float],
    node_id: int,
    targetname: str | None = None,
    teamnumber: int | None = None,
    lane_num: int | None = None,
    initial_spawn: bool | None = None,
    angles: tuple[float, float, float] = (0.0, 0.0, 0.0),
    extra_props: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Return (entity_id, keyvalues2 CMapEntity block) for simple point entities."""
    ent_id = str(uuid.uuid4())
    relay_id = str(uuid.uuid4())
    props_id = str(uuid.uuid4())
    lines = [
        '"CMapEntity"\n',
        '{\n',
        f'\t"id" "elementid" "{ent_id}"\n',
        '\t"hitNormal" "vector3" "0 0 0"\n',
        '\t"isProceduralEntity" "bool" "0"\n',
        '\t"relayPlugData" "DmePlugList"\n',
        '\t{\n',
        f'\t\t"id" "elementid" "{relay_id}"\n',
        '\t\t"names" "string_array" \n',
        '\t\t[\n',
        '\t\t]\n',
        '\t\t"dataTypes" "int_array" \n',
        '\t\t[\n',
        '\t\t]\n',
        '\t\t"plugTypes" "int_array" \n',
        '\t\t[\n',
        '\t\t]\n',
        '\t\t"descriptions" "string_array" \n',
        '\t\t[\n',
        '\t\t]\n',
        '\t}\n',
        '\n',
        '\t"connectionsData" "element_array" \n',
        '\t[\n',
        '\t]\n',
        '\t"entity_properties" "EditGameClassProps"\n',
        '\t{\n',
        f'\t\t"id" "elementid" "{props_id}"\n',
        '\t\t"enabled" "string" "1"\n',
        '\t\t"priority" "string" "0"\n',
    ]
    if targetname is not None:
        lines.append(f'\t\t"targetname" "string" "{targetname}"\n')
    if lane_num is not None:
        # Official Deadlock entity lumps use lowercase lanenum/initialspawn.
        # Keep casing identical; some KV consumers are not guaranteed case-insensitive.
        lines.append(f'\t\t"lanenum" "string" "{lane_num}"\n')
    if initial_spawn is not None:
        lines.append(f'\t\t"initialspawn" "string" "{str(initial_spawn).lower()}"\n')
    if teamnumber is not None:
        lines.append(f'\t\t"teamnumber" "string" "{teamnumber}"\n')
    for key, value in (extra_props or {}).items():
        lines.append(f'\t\t"{key}" "string" "{value}"\n')
    lines.extend([
        f'\t\t"classname" "string" "{classname}"\n',
        '\t}\n',
        '\n',
        f'\t"origin" "vector3" "{origin[0]:.6f} {origin[1]:.6f} {origin[2]:.6f}"\n',
        f'\t"angles" "qangle" "{angles[0]:.6f} {angles[1]:.6f} {angles[2]:.6f}"\n',
        '\t"scales" "vector3" "1 1 1"\n',
        f'\t"nodeID" "int" "{node_id}"\n',
        '\t"referenceID" "uint64" "0x0"\n',
        '\t"children" "element_array" \n',
        '\t[\n',
        '\t]\n',
        '\t"editorOnly" "bool" "0"\n',
        '\t"force_hidden" "bool" "0"\n',
        '\t"transformLocked" "bool" "0"\n',
        '\t"variableTargetKeys" "string_array" \n',
        '\t[\n',
        '\t]\n',
        '\t"variableNames" "string_array" \n',
        '\t[\n',
        '\t]\n',
        '}\n',
    ])
    return ent_id, "".join(lines)


def find_world_children_close(lines: list[str]) -> int:
    world_idx = next(i for i, line in enumerate(lines) if '"world" "CMapWorld"' in line)
    child_idx = next(i for i in range(world_idx, len(lines)) if '"children" "element_array"' in lines[i])
    open_idx = next(i for i in range(child_idx + 1, len(lines)) if lines[i].strip().rstrip(",") == "[")
    depth = 0
    for i in range(open_idx, len(lines)):
        stripped = lines[i].strip().rstrip(",")
        if stripped == "[":
            depth += 1
        elif stripped == "]":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("Could not find CMapWorld children array end")


def find_cmap_entity_block_by_classname(text: str, classname: str) -> str:
    """Return a keyvalues2 CMapEntity block that contains the requested classname."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() != '"CMapEntity"':
            continue
        block_range = matching_brace_block(lines, i)
        if not block_range:
            continue
        start, end = block_range
        block = "".join(lines[start:end])
        if re.search(r'"classname"\s+"string"\s+"' + re.escape(classname) + r'"', block, re.IGNORECASE):
            return block
    raise ValueError(f"No CMapEntity classname={classname!r} found")


def load_solid_trigger_template_block() -> str:
    """Load a known-good inline SolidClass entity+mesh block from the CSDK samples.

    The climbrope sample contains a `citadel_trigger_climb_rope` with an inline
    CMapMesh child. Retargeting this is much safer than inventing CMapMesh DMX
    topology by hand, and it compiles to the model-backed trigger VMDL that
    point-form entities cannot produce.
    """
    template_vmap = CSDK / "content/citadel/maps/climbrope.vmap"
    if not template_vmap.exists():
        raise FileNotFoundError(template_vmap)
    with tempfile.TemporaryDirectory(prefix="deadlock_solid_trigger_template_") as tmp_str:
        tmp = Path(tmp_str)
        kv = tmp / "climbrope.keyvalues2.vmap"
        run([str(DMXCONVERT), "-i", str(template_vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        return find_cmap_entity_block_by_classname(kv.read_text(encoding="utf-8", errors="replace"), "citadel_trigger_climb_rope")


def replace_first_position_vector_array(block: str, vectors: list[tuple[float, float, float]]) -> str:
    """Replace the first polygon position vector3_array in a CMapMesh block."""
    lines = block.splitlines(keepends=True)
    out: list[str] = []
    seen_position_attr = False
    pending_data = False
    in_data = False
    replaced = False
    depth = 0
    for line in lines:
        stripped = line.strip()
        if not replaced and '"standardAttributeName" "string" "position"' in line:
            seen_position_attr = True
        if not replaced and seen_position_attr and '"data" "vector3_array"' in line:
            pending_data = True
            out.append(line)
            continue
        if not replaced and pending_data and stripped == "[":
            pending_data = False
            in_data = True
            depth = 1
            out.append(line)
            indent = re.match(r"^(\s*)", line).group(1) + "\t"
            for idx, vec in enumerate(vectors):
                comma = "," if idx < len(vectors) - 1 else ""
                out.append(f'{indent}"{format_vec3(vec)}"{comma}\n')
            continue
        if in_data:
            if stripped == "[":
                depth += 1
            elif stripped == "]":
                depth -= 1
                if depth == 0:
                    in_data = False
                    replaced = True
                    seen_position_attr = False
                    out.append(line)
            continue
        out.append(line)
    if not replaced:
        raise ValueError("Could not replace position vector3_array in solid trigger template")
    return "".join(out)


def make_solid_box_entity_from_template(
    *,
    classname: str,
    mins: tuple[float, float, float],
    maxs: tuple[float, float, float],
    node_id_start: int,
    targetname: str | None = None,
    modifier_name: str | None = None,
) -> tuple[str, str, int]:
    """Return (entity_id, CMapEntity block, next_node_id) for a real box trigger.

    This creates a model-backed SolidClass volume. It intentionally uses a real
    inline CMapMesh child so resourcecompiler emits maps/<map>/entities/*.vmdl;
    this is the important difference from point-form trigger_modifier tests.
    """
    block = load_solid_trigger_template_block()

    guid_map: dict[str, str] = {}

    def _new_guid(match: re.Match[str]) -> str:
        old = match.group(0)
        if old not in guid_map:
            guid_map[old] = str(uuid.uuid4())
        return guid_map[old]

    block = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", _new_guid, block)
    entity_id_match = re.search(r'"CMapEntity"\s*\{\s*\n\s*"id"\s+"elementid"\s+"([^"]+)"', block)
    if not entity_id_match:
        raise ValueError("Retargeted solid trigger template lost CMapEntity id")
    entity_id = entity_id_match.group(1)

    next_node = node_id_start

    def _node(match: re.Match[str]) -> str:
        nonlocal next_node
        value = next_node
        next_node += 1
        return f'{match.group(1)}{value}{match.group(2)}'

    block = re.sub(r'("nodeID"\s+"int"\s+")\d+(")', _node, block)
    block = re.sub(r'("referenceID"\s+"uint64"\s+")0x[0-9a-fA-F]+(")', r'\g<1>0x0\2', block)

    cx = (mins[0] + maxs[0]) / 2.0
    cy = (mins[1] + maxs[1]) / 2.0
    cz = (mins[2] + maxs[2]) / 2.0
    hx = max((maxs[0] - mins[0]) / 2.0, 1.0)
    hy = max((maxs[1] - mins[1]) / 2.0, 1.0)
    hz = max((maxs[2] - mins[2]) / 2.0, 1.0)
    center = (cx, cy, cz)
    vertices = [
        (-hx, -hy, hz),
        (hx, -hy, hz),
        (-hx, hy, hz),
        (hx, hy, -hz),
        (-hx, hy, -hz),
        (hx, hy, hz),
        (hx, -hy, -hz),
        (-hx, -hy, -hz),
    ]
    block = replace_first_position_vector_array(block, vertices)
    block = re.sub(r'("origin"\s+"vector3"\s+")[^"]+(")', lambda m: f'{m.group(1)}{format_vec3(center)}{m.group(2)}', block)
    block = re.sub(r'"materials/dev/reflectivity_30\.vmat"', '"materials/tools/toolstrigger.vmat"', block)
    block = re.sub(r'("classname"\s+"string"\s+")[^"]+(")', lambda m: f'{m.group(1)}{classname}{m.group(2)}', block, count=1)
    block = re.sub(r'("targetname"\s+"string"\s+")[^"]*(")', lambda m: f'{m.group(1)}{targetname or ""}{m.group(2)}', block, count=1)
    block = re.sub(r'("StartDisabled"\s+"string"\s+")[^"]*(")', r'\g<1>0\2', block, count=1)
    block = re.sub(r'("spawnflags"\s+"string"\s+")[^"]*(")', r'\g<1>4097\2', block, count=1)
    if modifier_name and '"modifier_name" "string"' not in block:
        block = re.sub(
            r'(\n\s*"classname"\s+"string"\s+"' + re.escape(classname) + r'"\n)',
            f'\n\t\t\t\t\t"modifier_name" "string" "{modifier_name}"\n\\1',
            block,
            count=1,
        )
    return entity_id, block, next_node


def parse_vec3(text: str) -> tuple[float, float, float]:
    parts = [float(x) for x in text.replace(",", " ").split()[:3]]
    if len(parts) != 3:
        raise ValueError(f"Expected vec3: {text!r}")
    return parts[0], parts[1], parts[2]


def format_vec3(v: tuple[float, float, float]) -> str:
    return f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}"


def add_vec3(v: tuple[float, float, float], delta: tuple[float, float, float]) -> tuple[float, float, float]:
    return v[0] + delta[0], v[1] + delta[1], v[2] + delta[2]


def compute_position_stream_aabb(text: str) -> tuple[tuple[float, float, float], tuple[float, float, float], int]:
    """Return AABB for actual polygon mesh position streams in keyvalues2 VMAP text."""
    num = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    vec_line_re = re.compile(r'^\s*"(' + num + r"\s+" + num + r"\s+" + num + r')"')
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    count = 0
    pending_stream = False
    in_stream = False
    position_stream = False
    pending_data = False
    in_position_data = False
    depth = 0
    array_depth = 0

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == '"CDmePolygonMeshDataStream"':
            pending_stream = True
            continue
        if pending_stream and stripped == "{":
            pending_stream = False
            in_stream = True
            position_stream = False
            pending_data = False
            in_position_data = False
            depth = 1
            continue
        if not in_stream:
            continue

        if stripped == "{":
            depth += 1
        elif stripped == "}":
            depth -= 1
            if depth == 0:
                in_stream = False
                position_stream = False
                in_position_data = False
            continue

        if '"standardAttributeName" "string" "position"' in line:
            position_stream = True
        if position_stream and '"data" "vector3_array"' in line:
            pending_data = True
            continue
        if pending_data and stripped == "[":
            pending_data = False
            in_position_data = True
            array_depth = 1
            continue
        if in_position_data:
            if stripped == "[":
                array_depth += 1
                continue
            if stripped == "]":
                array_depth -= 1
                if array_depth == 0:
                    in_position_data = False
                continue
            match = vec_line_re.match(line)
            if not match:
                continue
            vec = parse_vec3(match.group(1))
            count += 1
            for idx, value in enumerate(vec):
                mins[idx] = min(mins[idx], value)
                maxs[idx] = max(maxs[idx], value)

    if count == 0:
        raise ValueError("No polygon mesh position stream vertices found")
    return (mins[0], mins[1], mins[2]), (maxs[0], maxs[1], maxs[2]), count


def transform_keyvalues2_map_coordinates(text: str, delta: tuple[float, float, float]) -> tuple[str, int]:
    """Translate world-space VMAP coordinates without touching normals/scales/colors.

    This intentionally handles the fields that define actual geometry/entity map
    space: entity origins, precomputed bounds/origins, and polygon mesh position
    arrays. It does not translate arbitrary vector3 values such as normals,
    colors, scales, or qangles.
    """
    direct_keys = {
        "origin",
        "local.origin",
        "precomputedobborigin",
        "precomputedboundsmins",
        "precomputedboundsmaxs",
        "precomputedobbmins",
        "precomputedobbmaxs",
    }
    line_re = re.compile(r'^(?P<prefix>\s*"(?P<key>[^"]+)"\s+"(?P<type>vector3|string)"\s+")(?P<vec>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s+-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s+-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?P<suffix>".*)$')
    vertex_re = re.compile(r'^(?P<prefix>\s*")(?P<vec>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s+-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s+-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?P<suffix>".*)$')

    lines = text.splitlines(keepends=True)
    cmapmesh_ranges: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == '"CMapMesh"':
            block_range = matching_brace_block(lines, i)
            if block_range:
                cmapmesh_ranges.append(block_range)
                i = block_range[1]
                continue
        i += 1

    cmapmesh_line_mask = bytearray(len(lines))
    for start, end in cmapmesh_ranges:
        cmapmesh_line_mask[start:end] = b"\x01" * (end - start)

    def in_cmapmesh_range(line_index: int) -> bool:
        return bool(cmapmesh_line_mask[line_index])

    out: list[str] = []
    changed = 0
    pending_stream = False
    in_stream = False
    position_stream = False
    pending_data = False
    in_position_data = False
    depth = 0
    array_depth = 0

    for line_index, raw_line in enumerate(lines):
        newline = "\n" if raw_line.endswith("\n") else ""
        line = raw_line[:-1] if newline else raw_line
        stripped = line.strip()
        new_line = line

        if stripped == '"CDmePolygonMeshDataStream"':
            pending_stream = True
        elif pending_stream and stripped == "{":
            pending_stream = False
            in_stream = True
            position_stream = False
            pending_data = False
            in_position_data = False
            depth = 1
        elif in_stream:
            if stripped == "{":
                depth += 1
            elif stripped == "}":
                depth -= 1
                if depth == 0:
                    in_stream = False
                    position_stream = False
                    in_position_data = False
            if '"standardAttributeName" "string" "position"' in line:
                position_stream = True
            if position_stream and '"data" "vector3_array"' in line:
                pending_data = True
            elif pending_data and stripped == "[":
                pending_data = False
                in_position_data = True
                array_depth = 1
            elif in_position_data:
                if stripped == "[":
                    array_depth += 1
                elif stripped == "]":
                    array_depth -= 1
                    if array_depth == 0:
                        in_position_data = False
                else:
                    match = vertex_re.match(line)
                    if match:
                        new_line = f"{match.group('prefix')}{format_vec3(add_vec3(parse_vec3(match.group('vec')), delta))}{match.group('suffix')}"
                        changed += 1

        if new_line == line:
            match = line_re.match(line)
            if match and match.group("key").lower() in direct_keys:
                # CMapMesh vertices are translated via their position streams.
                # Translating CMapMesh origins as well double-shifts compiled
                # geometry. CMapEntity/point origins still need translation.
                if not (in_cmapmesh_range(line_index) and match.group("key").lower() in {"origin", "local.origin"}):
                    new_line = f"{match.group('prefix')}{format_vec3(add_vec3(parse_vec3(match.group('vec')), delta))}{match.group('suffix')}"
                    changed += 1
        out.append(new_line + newline)

    return "".join(out), changed


def recenter_vmap_coordinates(
    vmap: Path,
    *,
    target_center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    axes: str = "xy",
    keep_text: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """Recenter the actual imported map geometry into a Deadlock-safe coordinate space."""
    if not vmap.exists():
        raise FileNotFoundError(vmap)
    if not set(axes).issubset({"x", "y", "z"}):
        raise ValueError(f"axes must contain only x/y/z, got {axes!r}")

    with tempfile.TemporaryDirectory(prefix="deadlock_recenter_vmap_") as tmp_str:
        tmp = Path(tmp_str)
        kv = tmp / (vmap.stem + ".keyvalues2.vmap")
        patched = tmp / (vmap.stem + ".recentered.keyvalues2.vmap")
        run([str(DMXCONVERT), "-i", str(vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        text = kv.read_text(encoding="utf-8", errors="replace")
        mins, maxs, vertex_count = compute_position_stream_aabb(text)
        center = tuple((mins[i] + maxs[i]) / 2.0 for i in range(3))
        delta_list = [0.0, 0.0, 0.0]
        for idx, axis in enumerate("xyz"):
            if axis in axes:
                delta_list[idx] = target_center[idx] - center[idx]
        delta = (delta_list[0], delta_list[1], delta_list[2])
        transformed, changed = transform_keyvalues2_map_coordinates(text, delta)
        patched.write_text(transformed, encoding="utf-8", errors="replace")

        result: dict[str, object] = {
            "mins": mins,
            "maxs": maxs,
            "center": center,
            "target_center": target_center,
            "axes": axes,
            "delta": delta,
            "position_vertices": vertex_count,
            "changed_vectors": changed,
        }
        print("Actual map coordinate AABB:")
        print(f"- mins: {format_vec3(mins)}")
        print(f"- maxs: {format_vec3(maxs)}")
        print(f"- center: {format_vec3(center)}")
        print(f"- target_center: {format_vec3(target_center)} axes={axes}")
        print(f"- delta: {format_vec3(delta)}")
        print(f"- position vertices: {vertex_count}; changed vectors: {changed}")

        if keep_text or dry_run:
            kept = vmap.with_suffix(vmap.suffix + ".recentered.keyvalues2.txt")
            shutil.copy2(patched, kept)
            print(f"Kept recentered text: {kept}")
        if not dry_run:
            backup = vmap.with_suffix(vmap.suffix + f".bak_recenter_{timestamp()}")
            shutil.copy2(vmap, backup)
            print(f"Backup: {backup}")
            run([str(DMXCONVERT), "-i", str(patched), "-o", str(vmap), "-oe", "binary", "-of", "vmap"])
        return result


def inject_deadlock_gameplay_entities(
    vmap: Path,
    *,
    keep_text: bool = False,
    spawn_override: tuple[float, float, float] | None = None,
    bounds_override: tuple[float, float, float, float, float, float] | None = None,
) -> list[dict[str, str]]:
    """Add minimal Deadlock-native entities to a source-backed imported course map.

    This is not a full game-mode conversion. It only supplies the entities that
    stock Deadlock game rules complained were absent during local `map ...` tests:
    team spawns, minimap/play bounds, and vanguard target anchors.
    """
    if not vmap.exists():
        raise FileNotFoundError(vmap)
    backup = vmap.with_suffix(vmap.suffix + f".bak_deadlock_gameplay_{timestamp()}")
    shutil.copy2(vmap, backup)
    print(f"Backup: {backup}")

    with tempfile.TemporaryDirectory(prefix="deadlock_gameplay_entities_") as tmp_str:
        tmp = Path(tmp_str)
        kv = tmp / (vmap.stem + ".keyvalues2.vmap")
        patched = tmp / (vmap.stem + ".deadlock_gameplay.keyvalues2.vmap")
        run([str(DMXCONVERT), "-i", str(vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        text = kv.read_text(encoding="utf-8", errors="replace")
        if "rebels_vanguard_spawn" in text and '"classname" "string" "info_team_spawn"' in text:
            print("Deadlock gameplay entities already present.")
            return []

        if spawn_override is not None:
            spawn = spawn_override
        else:
            spawn_matches = re.findall(
                r'"classname"\s+"string"\s+"info_player_(?:terrorist|counterterrorist)"(?:(?!"CMapEntity").)*?"origin"\s+"vector3"\s+"([^"]+)"',
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if not spawn_matches:
                raise ValueError("No CS2 info_player_* spawn origins found to seed Deadlock spawns")
            spawn = parse_vec3(spawn_matches[0])

        if bounds_override is not None:
            min_x, min_y, min_z, max_x, max_y, max_z = bounds_override
        else:
            bounds = [parse_vec3(x) for x in re.findall(r'"precomputedbounds(?:mins|maxs)"\s+"string"\s+"([^"]+)"', text, re.IGNORECASE)]
            if bounds:
                min_x = min(v[0] for v in bounds)
                min_y = min(v[1] for v in bounds)
                min_z = min(v[2] for v in bounds)
                max_x = max(v[0] for v in bounds)
                max_y = max(v[1] for v in bounds)
                max_z = max(v[2] for v in bounds)
            else:
                # Fallback around spawn if the map has no precomputed brush/entity bounds.
                min_x, min_y, min_z = spawn[0] - 4096, spawn[1] - 4096, spawn[2] - 512
                max_x, max_y, max_z = spawn[0] + 4096, spawn[1] + 4096, spawn[2] + 2048

        max_node = max([int(x) for x in re.findall(r'"nodeID"\s+"int"\s+"(\d+)"', text)] or [100000])
        next_node = max_node + 1
        created: list[dict[str, str]] = []
        entities: list[tuple[str, str]] = []

        def add(classname: str, origin: tuple[float, float, float], **kwargs: object) -> None:
            nonlocal next_node
            ent_id, block = make_cmap_entity(classname=classname, origin=origin, node_id=next_node, **kwargs)  # type: ignore[arg-type]
            entities.append((ent_id, block))
            created.append({"classname": classname, "origin": f"{origin[0]:.1f} {origin[1]:.1f} {origin[2]:.1f}", "id": ent_id})
            next_node += 1

        # Large minimap boundaries appear to be used by Deadlock as coarse playable-space bounds.
        add("citadel_minimap_boundary", (min_x - 512.0, min_y - 512.0, min_z - 2048.0))
        add("citadel_minimap_boundary", (max_x + 512.0, max_y + 512.0, max_z + 2048.0))

        # Silence vanguard target lookup and give game code safe anchors near the course start.
        add("info_target_server_only", (spawn[0], spawn[1], spawn[2] + 32.0), targetname="rebels_vanguard_spawn")
        add("info_target_server_only", (spawn[0] + 128.0, spawn[1], spawn[2] + 32.0), targetname="combine_vanguard_spawn")

        # Stock Deadlock uses info_team_spawn, not CS2 info_player_* starts.
        offsets = [(-96, 0), (-64, 0), (-32, 0), (0, 0), (32, 0), (64, 0), (96, 0), (-64, -48), (0, -48), (64, -48)]
        for team, y_extra, yaw in ((2, 0.0, 90.0), (3, 96.0, 270.0)):
            for dx, dy in offsets:
                add(
                    "info_team_spawn",
                    (spawn[0] + dx, spawn[1] + dy + y_extra, spawn[2] + 16.0),
                    teamnumber=team,
                    lane_num=0,
                    initial_spawn=False,
                    angles=(0.0, yaw, 0.0),
                )

        lines = text.splitlines(keepends=True)
        close_idx = find_world_children_close(lines)
        # If the current last child reference has no trailing comma, add one
        # before appending more element refs. KeyValues2 arrays are comma-separated.
        prev_idx = close_idx - 1
        while prev_idx >= 0 and not lines[prev_idx].strip():
            prev_idx -= 1
        if prev_idx >= 0 and lines[prev_idx].strip() in ('}',) and not lines[prev_idx].rstrip().endswith(','):
            lines[prev_idx] = lines[prev_idx].rstrip() + ",\n"
        elif prev_idx >= 0 and lines[prev_idx].lstrip().startswith('"element"') and not lines[prev_idx].rstrip().endswith(','):
            lines[prev_idx] = lines[prev_idx].rstrip() + ",\n"
        ref_lines = [f'\t\t\t"element" "{ent_id}",\n' for ent_id, _ in entities]
        if ref_lines:
            ref_lines[-1] = ref_lines[-1].rstrip().rstrip(",") + "\n"
        patched.write_text("".join(lines[:close_idx] + ref_lines + lines[close_idx:]) + "\n" + "\n".join(block for _, block in entities), encoding="utf-8", errors="replace")
        if keep_text:
            kept = vmap.with_suffix(vmap.suffix + ".deadlock_gameplay.keyvalues2.txt")
            shutil.copy2(patched, kept)
            print(f"Kept patched text: {kept}")
        run([str(DMXCONVERT), "-i", str(patched), "-o", str(vmap), "-oe", "binary", "-of", "vmap"])

    print("Injected Deadlock gameplay entities:")
    for item in created:
        print(f"- {item['classname']} @ {item['origin']} id={item['id']}")
    return created


def should_strip_cs2_gameplay_entity(block: str) -> bool:
    classname_match = re.search(r'"classname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
    if not classname_match:
        return False
    classname = classname_match.group(1).lower()
    targetname_match = re.search(r'"targetname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
    targetname = targetname_match.group(1).lower() if targetname_match else ""
    return (
        classname in CS2_GAMEPLAY_CLASSES
        or classname in DEADLOCK_GENERATED_SHELL_CLASSES
        or targetname in {"rebels_vanguard_spawn", "combine_vanguard_spawn", "bhop_course_start"}
        or any(classname.startswith(prefix) for prefix in CS2_GAMEPLAY_CLASS_PREFIXES)
    )


def strip_cs2_gameplay_and_add_deadlock_movement_shell(
    vmap: Path,
    *,
    keep_text: bool = False,
    hero: str = "viscous",
    spawn_override: tuple[float, float, float] | None = None,
    nav_seed_override: tuple[float, float, float] | None = None,
    include_boundary: bool = True,
    include_nav_seed: bool = False,
    include_hideout_volume: bool = True,
) -> list[dict[str, str]]:
    """Build a Deadlock-native movement-map shell while preserving source map geometry/looks.

    This intentionally discards CS/Source gameplay metadata instead of trying to
    translate it. It follows the observed pp_aero pattern: Deadlock-native
    info_team_spawn + hero_testing_controller, while the course logic/timers are
    left for a later Deadlock-specific pass.
    """
    if not vmap.exists():
        raise FileNotFoundError(vmap)
    backup = vmap.with_suffix(vmap.suffix + f".bak_deadlock_movement_shell_{timestamp()}")
    shutil.copy2(vmap, backup)
    print(f"Backup: {backup}")

    with tempfile.TemporaryDirectory(prefix="deadlock_movement_shell_") as tmp_str:
        tmp = Path(tmp_str)
        kv = tmp / (vmap.stem + ".keyvalues2.vmap")
        patched = tmp / (vmap.stem + ".deadlock_movement_shell.keyvalues2.vmap")
        run([str(DMXCONVERT), "-i", str(vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        lines = kv.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

        remove_ranges: list[tuple[int, int]] = []
        removed: list[dict[str, str]] = []
        spawn: tuple[float, float, float] | None = None
        i = 0
        while i < len(lines):
            if lines[i].strip() == '"CMapEntity"':
                block_range = matching_brace_block(lines, i)
                if not block_range:
                    i += 1
                    continue
                start, end = block_range
                block = "".join(lines[start:end])
                classname = re.search(r'"classname"\s+"string"\s+"([^"]+)"', block, re.IGNORECASE)
                origin = re.search(r'"origin"\s+"vector3"\s+"([^"]+)"', block, re.IGNORECASE)
                if classname and classname.group(1).lower().startswith("info_player_") and origin and spawn is None:
                    spawn = parse_vec3(origin.group(1))
                if should_strip_cs2_gameplay_entity(block):
                    remove_ranges.append((start, end))
                    removed.append({"classname": classname.group(1) if classname else "", "origin": origin.group(1) if origin else ""})
                i = end
                continue
            i += 1

        if spawn_override is not None:
            spawn = spawn_override
        elif spawn is None:
            spawn = (0.0, 0.0, 128.0)

        output: list[str] = []
        range_idx = 0
        i = 0
        while i < len(lines):
            if range_idx < len(remove_ranges) and i == remove_ranges[range_idx][0]:
                i = remove_ranges[range_idx][1]
                range_idx += 1
                continue
            output.append(lines[i])
            i += 1

        max_node = max([int(x) for x in re.findall(r'"nodeID"\s+"int"\s+"(\d+)"', "".join(output))] or [100000])
        next_node = max_node + 1
        entities: list[tuple[str, str]] = []

        def add(classname: str, origin: tuple[float, float, float], **kwargs: object) -> None:
            nonlocal next_node
            ent_id, block = make_cmap_entity(classname=classname, origin=origin, node_id=next_node, **kwargs)  # type: ignore[arg-type]
            entities.append((ent_id, block))
            next_node += 1

        try:
            mesh_mins, mesh_maxs, mesh_vertices = compute_position_stream_aabb("".join(output))
            min_x, min_y, min_z = mesh_mins
            max_x, max_y, max_z = mesh_maxs
            print(f"Movement shell using actual mesh AABB from {mesh_vertices} vertices: {format_vec3(mesh_mins)} -> {format_vec3(mesh_maxs)}")
        except ValueError:
            bounds = [parse_vec3(x) for x in re.findall(r'"precomputedbounds(?:mins|maxs)"\s+"string"\s+"([^"]+)"', "".join(output), re.IGNORECASE)]
            if bounds:
                min_x = min(v[0] for v in bounds)
                min_y = min(v[1] for v in bounds)
                min_z = min(v[2] for v in bounds)
                max_x = max(v[0] for v in bounds)
                max_y = max(v[1] for v in bounds)
                max_z = max(v[2] for v in bounds)
            else:
                min_x, min_y, min_z = spawn[0] - 4096, spawn[1] - 4096, spawn[2] - 512
                max_x, max_y, max_z = spawn[0] + 4096, spawn[1] + 4096, spawn[2] + 2048

        if include_boundary:
            # Broad Deadlock play envelope. Official onelane uses y around +11776/-12288;
            # our earlier y=8080 bound was too tight for observed in-game camera/play space.
            add("citadel_minimap_boundary", (min(min_x - 1024.0, -16000.0), min(min_y - 1024.0, -16000.0), min(min_z - 1024.0, -5000.0)))
            add("citadel_minimap_boundary", (max(max_x + 1024.0, 16000.0), max(max_y + 1024.0, 16000.0), max(max_z + 1024.0, 5000.0)))

        if include_nav_seed:
            # This is the missing nav-generation seed. Without at least one
            # point_nav_walkable, resourcecompiler emits "NAVGEN: Skipped... no
            # walkable seeds present" and Deadlock has no native walkable/play space
            # to validate spawns against. Can be disabled to reproduce the earlier
            # permissive/error-mesh build that allowed walking despite no nav seed.
            nav_seed = nav_seed_override or (spawn[0], spawn[1], 128.0)
            add("point_nav_walkable", nav_seed)

        # Named anchors make the runtime fallback deterministic and silence the
        # stock vanguard target lookup in Deadlock game rules.
        add("info_target_server_only", (spawn[0], spawn[1], spawn[2] + 32.0), targetname="bhop_course_start")
        add("info_target_server_only", (spawn[0], spawn[1], spawn[2] + 32.0), targetname="rebels_vanguard_spawn")
        add("info_target_server_only", (spawn[0] + 128.0, spawn[1], spawn[2] + 32.0), targetname="combine_vanguard_spawn")

        # Match movementmap's clean spawn pattern: normal info_team_spawn points,
        # no hero_testing_controller, no point-form fake modifiers, no hero_model
        # forcing. Use enough team 2/3 spawns for multiplayer testing.
        spawn_offsets = [(-96, 0), (-64, 0), (-32, 0), (0, 0), (32, 0), (64, 0), (96, 0), (-64, -48), (0, -48), (64, -48)]
        for team, y_extra, yaw in ((2, 0.0, 90.0), (3, 96.0, 270.0)):
            for dx, dy in spawn_offsets:
                add(
                    "info_team_spawn",
                    (spawn[0] + dx, spawn[1] + dy + y_extra, spawn[2] + 16.0),
                    teamnumber=team,
                    lane_num=0,
                    initial_spawn=False,
                    angles=(0.0, yaw, 0.0),
                )

        if include_hideout_volume:
            trigger_mins = (min_x - 1024.0, min_y - 1024.0, min(min_z - 2048.0, -5000.0))
            trigger_maxs = (max_x + 1024.0, max_y + 1024.0, max(max_z + 4096.0, 5000.0))
            ent_id, block, next_node = make_solid_box_entity_from_template(
                classname="citadel_trigger_suspend_modifier",
                mins=trigger_mins,
                maxs=trigger_maxs,
                node_id_start=next_node,
                targetname="bhop_roam_hideout_volume",
                modifier_name="modifier_citadel_in_hideout_zone",
            )
            entities.append((ent_id, block))
            print(f"Added real hideout modifier volume: {format_vec3(trigger_mins)} -> {format_vec3(trigger_maxs)} id={ent_id}")

        close_idx = find_world_children_close(output)
        prev_idx = close_idx - 1
        while prev_idx >= 0 and not output[prev_idx].strip():
            prev_idx -= 1
        if prev_idx >= 0 and output[prev_idx].strip() in ('}',) and not output[prev_idx].rstrip().endswith(','):
            output[prev_idx] = output[prev_idx].rstrip() + ",\n"
        elif prev_idx >= 0 and output[prev_idx].lstrip().startswith('"element"') and not output[prev_idx].rstrip().endswith(','):
            output[prev_idx] = output[prev_idx].rstrip() + ",\n"
        ref_lines = [f'\t\t\t"element" "{ent_id}",\n' for ent_id, _ in entities]
        if ref_lines:
            ref_lines[-1] = ref_lines[-1].rstrip().rstrip(",") + "\n"
        patched.write_text("".join(output[:close_idx] + ref_lines + output[close_idx:]) + "\n" + "\n".join(block for _, block in entities), encoding="utf-8", errors="replace")
        if keep_text:
            kept = vmap.with_suffix(vmap.suffix + ".deadlock_movement_shell.keyvalues2.txt")
            shutil.copy2(patched, kept)
            print(f"Kept patched text: {kept}")
        run([str(DMXCONVERT), "-i", str(patched), "-o", str(vmap), "-oe", "binary", "-of", "vmap"])

    print(f"Removed {len(removed)} CS2 gameplay entities and added pp_aero-style Deadlock movement shell.")
    for item in removed[:50]:
        print(f"- stripped {item['classname']} @ {item['origin']}")
    if len(removed) > 50:
        print(f"... {len(removed) - 50} more stripped")
    return removed


def strip_cs2_point_prefabs(vmap: Path, *, keep_text: bool = False) -> list[dict[str, str]]:
    if not vmap.exists():
        raise FileNotFoundError(vmap)
    if not DMXCONVERT.exists():
        raise FileNotFoundError(DMXCONVERT)

    backup = vmap.with_suffix(vmap.suffix + f".bak_cs2_prefabs_{timestamp()}")
    shutil.copy2(vmap, backup)
    print(f"Backup: {backup}")

    with tempfile.TemporaryDirectory(prefix="deadlock_map_fix_") as tmp_str:
        tmp = Path(tmp_str)
        kv = tmp / (vmap.stem + ".keyvalues2.vmap")
        stripped_kv = tmp / (vmap.stem + ".stripped.keyvalues2.vmap")
        run([str(DMXCONVERT), "-i", str(vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        text = kv.read_text(encoding="utf-8", errors="replace")
        stripped_text, removed = strip_cs2_point_prefabs_from_keyvalues(text)
        if not removed:
            strip_sidecar_vents(vmap)
            print("No CS2 point-prefab entities found.")
            return []
        stripped_kv.write_text(stripped_text, encoding="utf-8", errors="replace")
        if keep_text:
            kept = vmap.with_suffix(vmap.suffix + ".stripped.keyvalues2.txt")
            shutil.copy2(stripped_kv, kept)
            print(f"Kept stripped text: {kept}")
        run([str(DMXCONVERT), "-i", str(stripped_kv), "-o", str(vmap), "-oe", "binary", "-of", "vmap"])

    strip_sidecar_vents(vmap)
    print("Removed CS2 point-prefab entities:")
    for item in removed:
        print(f"- nodeID={item['nodeID']} classname={item['classname']} target={item['targetmapname']} id={item['id']}")
    return removed


def make_empty_vmap_from_template(output_vmap: Path, *, template_vmap: Path | None = None) -> None:
    """Create a tiny valid empty .vmap by clearing the world children from a known-good CSDK map."""
    template_vmap = template_vmap or (CSDK / "content/citadel/maps/volumetric_test.vmap")
    if not template_vmap.exists():
        raise FileNotFoundError(template_vmap)
    output_vmap.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="deadlock_empty_vmap_") as tmp_str:
        tmp = Path(tmp_str)
        kv = tmp / "template.keyvalues2.vmap"
        stripped_kv = tmp / "empty.keyvalues2.vmap"
        run([str(DMXCONVERT), "-i", str(template_vmap), "-o", str(kv), "-oe", "keyvalues2", "-of", "vmap"])
        lines = kv.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        world_idx = next(i for i, line in enumerate(lines) if '"world" "CMapWorld"' in line)
        child_idx = next(i for i in range(world_idx, len(lines)) if '"children" "element_array"' in lines[i])
        open_idx = next(i for i in range(child_idx + 1, len(lines)) if lines[i].strip() == "[")
        depth = 0
        close_idx = None
        for i in range(open_idx, len(lines)):
            stripped = lines[i].strip()
            if stripped == "[":
                depth += 1
            elif stripped == "]":
                depth -= 1
                if depth == 0:
                    close_idx = i
                    break
        if close_idx is None:
            raise ValueError(f"Could not find CMapWorld children array end in {template_vmap}")
        # Keep the array brackets but remove all child map objects. The compiler
        # emits a tiny valid world VPK with no mesh/entity payload.
        stripped_kv.write_text("".join(lines[:open_idx + 1] + lines[close_idx:]), encoding="utf-8", errors="replace")
        run([str(DMXCONVERT), "-i", str(stripped_kv), "-o", str(output_vmap), "-oe", "binary", "-of", "vmap"])
    print(f"Wrote empty placeholder vmap: {output_vmap}")


def build_empty_prefab_vpks(addon_name: str, prefab_names: list[str], *, log_dir: Path) -> list[Path]:
    compiled: list[Path] = []
    for prefab in prefab_names:
        rel = Path("maps/prefabs/misc") / f"{prefab}.vmap"
        vmap = CSDK / "content/citadel_addons" / addon_name / rel
        make_empty_vmap_from_template(vmap)
        compiled.append(compile_vmap(vmap, log_dir=log_dir))
    return compiled


def compile_vmap(vmap: Path, *, log_dir: Path) -> Path:
    if not RESOURCECOMPILER.exists():
        raise FileNotFoundError(RESOURCECOMPILER)
    if not (GAME_DIR / "gameinfo.gi").exists():
        raise FileNotFoundError(GAME_DIR / "gameinfo.gi")
    log = log_dir / f"compile_{vmap.stem}_{timestamp()}.log"
    run([
        str(RESOURCECOMPILER),
        "-game", str(GAME_DIR),
        "-i", str(vmap),
        "-f",
    ], cwd=CSDK / "game/bin_cs2/win64", log=log)
    print(f"Compile log: {log}")

    content_root = CSDK / "content"
    try:
        rel = vmap.relative_to(content_root)
    except ValueError as exc:
        raise ValueError(f"vmap must be under {content_root}: {vmap}") from exc
    compiled = CSDK / "game" / rel.with_suffix(".vpk")
    if not compiled.exists():
        raise FileNotFoundError(f"Expected compiled map VPK was not written: {compiled}")
    print(f"Compiled map: {compiled}")
    return compiled


def install_addon(addon_name: str, *, deadlock: Path = DEADLOCK) -> Path:
    src = CSDK / "game/citadel_addons" / addon_name
    dst = deadlock / "game/citadel_addons" / addon_name
    if not src.exists():
        raise FileNotFoundError(src)
    if dst.exists():
        backup = dst.with_name(dst.name + f".bak_{timestamp()}")
        shutil.move(str(dst), str(backup))
        print(f"Existing live addon moved to: {backup}")
    shutil.copytree(src, dst)
    print(f"Installed addon: {dst}")
    return dst


def build_prefabs(args: argparse.Namespace) -> None:
    names = args.prefabs or [
        "team_select",
        "terrorist_team_intro",
        "counterterrorist_team_intro",
        "end_of_match",
    ]
    built = build_empty_prefab_vpks(args.addon_name, names, log_dir=Path(args.log_dir))
    for path in built:
        print(f"Built placeholder prefab VPK: {path}")
    if args.install:
        install_addon(args.addon_name, deadlock=Path(args.deadlock))


def fix_compile_install(args: argparse.Namespace) -> None:
    vmap = Path(args.vmap)
    removed = strip_cs2_point_prefabs(vmap, keep_text=args.keep_text)
    injected: list[dict[str, str]] = []
    if args.inject_gameplay_entities:
        injected = inject_deadlock_gameplay_entities(vmap, keep_text=args.keep_text)
    if args.compile:
        compile_vmap(vmap, log_dir=Path(args.log_dir))
    if args.install:
        install_addon(args.addon_name, deadlock=Path(args.deadlock))
    if removed or injected:
        print("Next test in Deadlock console: map " + vmap.stem)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)

    p = sub.add_parser("strip-cs2-prefabs", help="remove CS2 point-prefab entities from a .vmap")
    p.add_argument("vmap")
    p.add_argument("--keep-text", action="store_true")
    p.set_defaults(func=lambda a: strip_cs2_point_prefabs(Path(a.vmap), keep_text=a.keep_text))

    p = sub.add_parser("compile", help="compile a CSDK content .vmap with bin_cs2 resourcecompiler")
    p.add_argument("vmap")
    p.add_argument("--log-dir", default="C:/Code/deadlock-map-porting/logs")
    p.set_defaults(func=lambda a: compile_vmap(Path(a.vmap), log_dir=Path(a.log_dir)))

    p = sub.add_parser("install-addon", help="copy a CSDK citadel_addons addon into live Deadlock")
    p.add_argument("addon_name")
    p.add_argument("--deadlock", default=str(DEADLOCK))
    p.set_defaults(func=lambda a: install_addon(a.addon_name, deadlock=Path(a.deadlock)))

    p = sub.add_parser("build-empty-prefabs", help="build tiny placeholder VPKs for missing CS2 maps/prefabs/misc point-prefabs")
    p.add_argument("addon_name")
    p.add_argument("--prefabs", nargs="*", help="prefab basenames; defaults to common CS2 team/deathmatch prefabs")
    p.add_argument("--log-dir", default="C:/Code/deadlock-map-porting/logs")
    p.add_argument("--deadlock", default=str(DEADLOCK))
    p.add_argument("--no-install", dest="install", action="store_false")
    p.set_defaults(func=build_prefabs, install=True)

    p = sub.add_parser("inject-deadlock-gameplay", help="add minimal Deadlock team spawn/play-bound/vanguard entities to a source-backed imported .vmap")
    p.add_argument("vmap")
    p.add_argument("--keep-text", action="store_true")
    p.set_defaults(func=lambda a: inject_deadlock_gameplay_entities(Path(a.vmap), keep_text=a.keep_text))

    p = sub.add_parser("recenter-map", help="move actual imported map mesh/entity coordinate space toward a Deadlock-safe center")
    p.add_argument("vmap")
    p.add_argument("--target-center", nargs=3, type=float, default=(0.0, 0.0, 0.0), metavar=("X", "Y", "Z"))
    p.add_argument("--axes", default="xy", help="axes to recenter; default xy preserves original vertical course coordinates")
    p.add_argument("--keep-text", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--compile", action="store_true")
    p.add_argument("--log-dir", default="C:/Code/deadlock-map-porting/logs")
    def _recenter_map(a: argparse.Namespace) -> None:
        vmap = Path(a.vmap)
        recenter_vmap_coordinates(
            vmap,
            target_center=(a.target_center[0], a.target_center[1], a.target_center[2]),
            axes=a.axes.lower(),
            keep_text=a.keep_text,
            dry_run=a.dry_run,
        )
        if a.compile and not a.dry_run:
            compile_vmap(vmap, log_dir=Path(a.log_dir))
    p.set_defaults(func=_recenter_map)

    p = sub.add_parser("movement-shell", help="strip CS2 gameplay and add a pp_aero-style Deadlock movement-map shell")
    p.add_argument("vmap")
    p.add_argument("--hero", default="viscous")
    p.add_argument("--spawn", nargs=3, type=float, metavar=("X", "Y", "Z"), help="course start spawn override in current VMAP coordinate space")
    p.add_argument("--nav-seed", nargs=3, type=float, metavar=("X", "Y", "Z"), help="point_nav_walkable seed on real floor geometry; implies --with-nav-seed")
    p.add_argument("--with-nav-seed", action="store_true", help="add point_nav_walkable; default off because movementmap works with a 232-byte nav")
    p.add_argument("--no-boundary", action="store_true", help="do not add citadel_minimap_boundary; reproduces earlier permissive build behavior")
    p.add_argument("--no-nav-seed", action="store_true", help="force no point_nav_walkable even if --with-nav-seed is set")
    p.add_argument("--no-hideout-volume", action="store_true", help="do not add the real compiled citadel_trigger_suspend_modifier volume")
    p.add_argument("--keep-text", action="store_true")
    p.add_argument("--compile", action="store_true")
    p.add_argument("--log-dir", default="C:/Code/deadlock-map-porting/logs")
    def _movement_shell(a: argparse.Namespace) -> None:
        vmap = Path(a.vmap)
        spawn = (a.spawn[0], a.spawn[1], a.spawn[2]) if a.spawn else None
        nav_seed = (a.nav_seed[0], a.nav_seed[1], a.nav_seed[2]) if a.nav_seed else None
        include_nav_seed = (a.with_nav_seed or nav_seed is not None) and not a.no_nav_seed
        strip_cs2_gameplay_and_add_deadlock_movement_shell(
            vmap,
            keep_text=a.keep_text,
            hero=a.hero,
            spawn_override=spawn,
            nav_seed_override=nav_seed,
            include_boundary=not a.no_boundary,
            include_nav_seed=include_nav_seed,
            include_hideout_volume=not a.no_hideout_volume,
        )
        if a.compile:
            compile_vmap(vmap, log_dir=Path(a.log_dir))
    p.set_defaults(func=_movement_shell)

    p = sub.add_parser("fix-compile-install", help="strip CS2 prefabs, optionally inject Deadlock gameplay entities, compile, and install a CSDK addon")
    p.add_argument("vmap", nargs="?", default=str(CSDK / "content/citadel_addons/bhop_emevaelx3_port/maps/bhop_emevaelx3.vmap"))
    p.add_argument("--addon-name", default="bhop_emevaelx3_port")
    p.add_argument("--log-dir", default="C:/Code/deadlock-map-porting/logs")
    p.add_argument("--deadlock", default=str(DEADLOCK))
    p.add_argument("--keep-text", action="store_true")
    p.add_argument("--inject-gameplay-entities", action="store_true")
    p.add_argument("--no-compile", dest="compile", action="store_false")
    p.add_argument("--no-install", dest="install", action="store_false")
    p.set_defaults(func=fix_compile_install, compile=True, install=True)

    args = ap.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
