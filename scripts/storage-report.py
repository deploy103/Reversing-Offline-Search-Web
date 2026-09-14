#!/usr/bin/env python3
"""
Storage usage report for Reversing-Offline-Search-Web.

Walks the repository and buckets on-disk size by top-level area (content,
assets, dist, offline-kit, tools, research, other), then compares the total
against the project's storage limits (40 GB hard limit, 30-35 GB soft target).

Stdlib only. Run from repo root:

    python3 scripts/storage-report.py

Exit code 0 always (this is a report, not a validator) unless the hard limit
is exceeded, in which case it exits 1 so CI/dev-log automation can notice.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HARD_LIMIT_GB = 40
SOFT_TARGET_GB = 35

# Top-level areas are listed in reporting order. Anything not under one of
# these is bucketed as "other".
BUCKETS = [
    ("content", ROOT / "content"),
    ("assets", ROOT / "assets"),
    ("dist", ROOT / "dist"),
    ("offline-kit", ROOT / "offline-kit"),
    ("tools", ROOT / "tools"),
    ("research", ROOT / "research"),
    ("state", ROOT / "state"),
    ("scripts", ROOT / "scripts"),
    ("tests", ROOT / "tests"),
]

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules"}


def dir_size(path):
    total = 0
    file_count = 0
    if not path.exists():
        return 0, 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            fp = os.path.join(dirpath, name)
            try:
                total += os.path.getsize(fp)
            except OSError:
                continue
            file_count += 1
    return total, file_count


def human(nbytes):
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if nbytes < step:
            return "{:.2f} {}".format(nbytes, unit)
        nbytes /= step
    return "{:.2f} PB".format(nbytes)


def main():
    print("=" * 60)
    print("Reversing-Offline-Search-Web storage report")
    print("=" * 60)

    total_bytes = 0
    rows = []
    for label, path in BUCKETS:
        size, count = dir_size(path)
        total_bytes += size
        rows.append((label, size, count))

    # "other": everything at repo root not covered by a known bucket and not .git
    known_names = {p.name for _, p in BUCKETS} | SKIP_DIR_NAMES
    other_bytes = 0
    other_count = 0
    for entry in ROOT.iterdir():
        if entry.name in known_names:
            continue
        if entry.is_dir():
            s, c = dir_size(entry)
        elif entry.is_file():
            s, c = entry.stat().st_size, 1
        else:
            continue
        other_bytes += s
        other_count += c
    total_bytes += other_bytes
    rows.append(("other (repo root files/dirs)", other_bytes, other_count))

    width = max(len(label) for label, _, _ in rows)
    for label, size, count in rows:
        print("  {:<{w}}  {:>12}  ({} files)".format(label, human(size), count, w=width))

    print("-" * 60)
    total_gb = total_bytes / (1024 ** 3)
    print("  {:<{w}}  {:>12}".format("TOTAL", human(total_bytes), w=width))
    print("  Hard limit: {} GB   Soft target: {} GB   Current: {:.2f} GB".format(
        HARD_LIMIT_GB, SOFT_TARGET_GB, total_gb))

    if total_gb > HARD_LIMIT_GB:
        print("  !! OVER HARD LIMIT -- deduplicate large binaries/images in priority order.")
        return 1
    elif total_gb > SOFT_TARGET_GB:
        print("  ! over soft target, still under hard limit -- keep an eye on offline-kit/tools growth.")
    else:
        print("  OK -- within soft target.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
