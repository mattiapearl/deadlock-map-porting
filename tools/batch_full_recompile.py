#!/usr/bin/env python3
"""Batch wrapper for full_recompile_workshop_map.py manifests."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--extra", nargs=argparse.REMAINDER, help="extra args passed to each map after --")
    args = ap.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    script = Path(__file__).with_name("full_recompile_workshop_map.py")
    failed = 0
    for item in manifest.get("maps", []):
        cmd = [sys.executable, str(script), "--workshop-root", item["workshopRoot"], "--map", item["map"]]
        if item.get("addon"):
            cmd += ["--addon", item["addon"]]
        if item.get("memoryGb"):
            cmd += ["--memory-gb", str(item["memoryGb"])]
        if item.get("compileFlag"):
            cmd += ["--compile-flag", item["compileFlag"]]
        if args.extra:
            cmd += args.extra
        print("\n===", item["map"], "===")
        rc = subprocess.run(cmd).returncode
        if rc:
            failed += 1
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
