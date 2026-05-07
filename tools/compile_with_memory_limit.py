#!/usr/bin/env python3
"""Run a command while enforcing a Windows process-tree memory limit."""
from __future__ import annotations

import argparse
import queue
import subprocess
import sys
import threading
import time

import psutil  # type: ignore


def pump(pipe, q: queue.Queue[str]) -> None:
    try:
        for line in iter(pipe.readline, ""):
            q.put(line)
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def tree_private_bytes(proc: psutil.Process) -> int:
    total = 0
    for p in [proc, *proc.children(recursive=True)]:
        try:
            mi = p.memory_full_info()
            total += getattr(mi, "private", mi.rss)
        except psutil.Error:
            pass
    return total


def kill_tree(proc: psutil.Process) -> None:
    for p in proc.children(recursive=True):
        try:
            p.kill()
        except psutil.Error:
            pass
    try:
        proc.kill()
    except psutil.Error:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-gb", type=float, default=24.0)
    ap.add_argument("--timeout-sec", type=float, default=0.0, help="0 disables timeout")
    ap.add_argument("--priority", default="below_normal", choices=["idle", "below_normal", "normal"])
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        ap.error("missing command")

    limit = int(args.limit_gb * 1024**3)
    print("+ " + " ".join(cmd), flush=True)
    print(f"[memlimit] limit={args.limit_gb:.1f} GiB timeout={args.timeout_sec or 'off'}s priority={args.priority}", flush=True)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1)
    proc = psutil.Process(p.pid)
    try:
        if args.priority == "idle":
            proc.nice(psutil.IDLE_PRIORITY_CLASS)
        elif args.priority == "below_normal":
            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass

    q: queue.Queue[str] = queue.Queue()
    t = threading.Thread(target=pump, args=(p.stdout, q), daemon=True)
    t.start()
    start = time.monotonic()
    peak = 0
    while True:
        while True:
            try:
                print(q.get_nowait(), end="", flush=True)
            except queue.Empty:
                break
        rc = p.poll()
        mem = tree_private_bytes(proc) if rc is None else 0
        peak = max(peak, mem)
        if rc is not None:
            while True:
                try:
                    print(q.get_nowait(), end="", flush=True)
                except queue.Empty:
                    break
            print(f"[memlimit] peak observed: {peak/1024**3:.2f} GiB", flush=True)
            return rc
        if mem > limit:
            print(f"\n[memlimit] killing process tree: {mem/1024**3:.2f} GiB > {args.limit_gb:.1f} GiB", flush=True)
            kill_tree(proc)
            print(f"[memlimit] peak observed: {peak/1024**3:.2f} GiB", flush=True)
            return 99
        if args.timeout_sec and time.monotonic() - start > args.timeout_sec:
            print(f"\n[memlimit] killing process tree: timeout {args.timeout_sec:.0f}s", flush=True)
            kill_tree(proc)
            print(f"[memlimit] peak observed: {peak/1024**3:.2f} GiB", flush=True)
            return 98
        time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
