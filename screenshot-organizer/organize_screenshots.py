#!/usr/bin/env python3
"""Organize screenshots/images by source app based on filename pattern.

Usage:
    python3 organize_screenshots.py --dry-run
    python3 organize_screenshots.py --apply --limit 10
    python3 organize_screenshots.py --apply --yes
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from collections import Counter
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DEFAULT_CATEGORY, DEST_ROOT, IMAGE_EXTS, RULES, SOURCE_ROOT, categorize

log = logging.getLogger("ss-organizer")


def scan(root: Path, skip_root: Path) -> list[Path]:
    """Recursively collect image files under root, skipping skip_root."""
    skip = skip_root.resolve()
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved == skip or skip in resolved.parents:
            continue
        out.append(path)
    out.sort(key=lambda p: p.name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually copy files. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Explicit dry-run (default behavior, no writes).")
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT,
                        help=f"Source root to scan. Default: {SOURCE_ROOT}")
    parser.add_argument("--dest", type=Path, default=DEST_ROOT,
                        help=f"Destination root. Default: {DEST_ROOT}")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N files (0 = all).")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt before copying.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if not args.source.exists():
        log.error("source root not found: %s", args.source)
        return 1

    files = scan(args.source, args.dest)
    if args.limit > 0:
        files = files[: args.limit]

    log.info("found %d image files", len(files))
    if not files:
        return 0

    counts: Counter[str] = Counter()
    plan: list[tuple[Path, Path, str]] = []
    skipped = 0

    for src in files:
        category = categorize(src.name)
        dest = args.dest / category / src.name
        if dest.exists():
            skipped += 1
            counts[f"{category} (exists)"] += 1
            continue
        plan.append((src, dest, category))
        counts[category] += 1

    log.info("--- summary ---")
    for key, n in sorted(counts.items()):
        log.info("  %s: %d", key, n)
    log.info("to copy: %d, already exists: %d", len(plan), skipped)

    if not args.apply:
        for src, dest, category in plan:
            log.info("[DRY] %s -> %s/%s", src.name, category, src.name)
        return 0

    if not args.yes:
        log.info("Copy %d files to %s? [y/N] ", len(plan), args.dest)
        try:
            answer = input()
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            log.info("aborted")
            return 0

    errors = 0
    done = 0
    for src, dest, category in plan:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            log.info("[OK] %s -> %s/%s", src.name, category, src.name)
            done += 1
        except Exception as exc:
            errors += 1
            log.warning("[ERR] %s: %s", src.name, exc)

    log.info("--- done ---")
    log.info("copied: %d, errors: %d", done, errors)
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
