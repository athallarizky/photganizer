#!/usr/bin/env python3
"""Organize screenshots by source app and content type.

Usage:
    python3 organize_screenshots.py --dry-run
    python3 organize_screenshots.py --apply --limit 5 --yes
    python3 organize_screenshots.py --apply --yes
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cache import get as cache_get, make_key, put as cache_put, reset as cache_reset
from classify import classify_text
from config import APP_MAP, CATEGORY_DIRS, DEFAULT_LANG, DEST_ROOT, SOURCE_ROOT
from ocr import extract_text

log = logging.getLogger("ss-organizer")

FILENAME_RE = re.compile(
    r"^Screenshot_.*_(?P<pkg>com\.[a-z0-9_.]+)\.(?:jpg|jpeg|png)$", re.IGNORECASE
)


@dataclass
class Match:
    path: Path
    package: str
    app_name: str


def scan(root: Path, since: str | None) -> list[Match]:
    matches: list[Match] = []
    skip_root = (SOURCE_ROOT / "Organized").resolve()
    for path in root.rglob("Screenshot_*"):
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved == skip_root or skip_root in resolved.parents:
            continue
        m = FILENAME_RE.match(path.name)
        if not m:
            continue
        pkg = m.group("pkg")
        if pkg not in APP_MAP:
            continue
        if since and not _dated_after(path.name, since):
            continue
        matches.append(Match(path=path, package=pkg, app_name=APP_MAP[pkg]))
    matches.sort(key=lambda x: x.path.name)
    return matches


def _dated_after(filename: str, since: str) -> bool:
    # filename format: Screenshot_YYYY-MM-DD-...
    date_part = filename[len("Screenshot_") : len("Screenshot_") + 10]
    return date_part >= since


def categorize(match: Match, lang: str) -> tuple[str, bool, bool]:
    """Return (category, used_ocr, used_llm)."""
    key = make_key(match.path)
    cached = cache_get(key)
    if cached is not None:
        return cached[0], False, False

    text = extract_text(match.path, lang=lang)
    category = classify_text(text)
    cache_put(key, match.path, category, text)
    return category, True, True


def destination_for(match: Match, category: str) -> Path:
    return DEST_ROOT / match.app_name / category.capitalize() / match.path.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually run OCR + LLM + copy. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Explicit dry-run (default behavior). No OCR / LLM / writes.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N matched files (0 = all).")
    parser.add_argument("--since", default=None,
                        help="Only files dated YYYY-MM-DD or later.")
    parser.add_argument("--lang", default=DEFAULT_LANG,
                        help=f"Tesseract language(s), e.g. 'eng' or 'eng+ind'. Default: {DEFAULT_LANG}")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the cost-estimate confirmation prompt.")
    parser.add_argument("--reset-cache", action="store_true",
                        help="Wipe the SQLite cache before running.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if args.reset_cache:
        cache_reset()
        log.info("[CACHE] wiped")

    if not SOURCE_ROOT.exists():
        log.error("source root not found: %s", SOURCE_ROOT)
        return 1

    matches = scan(SOURCE_ROOT, args.since)
    if args.limit > 0:
        matches = matches[: args.limit]

    log.info("found %d matching screenshots", len(matches))
    if not matches:
        return 0

    if args.apply and not args.yes:
        log.info("--apply will send %d OCR texts to glm-air. Continue? [y/N] ", end="")
        try:
            answer = input()
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            log.info("aborted");
            return 0

    counts: Counter[str] = Counter()
    ocr_calls = 0
    llm_calls = 0
    errors = 0

    for m in matches:
        try:
            if args.apply:
                category, used_ocr, used_llm = categorize(m, args.lang)
                ocr_calls += int(used_ocr)
                llm_calls += int(used_llm)
                dest = destination_for(m, category)
                if dest.exists():
                    tag = "SKIP"
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(m.path, dest)
                    tag = "OK"
                log.info("[%s] %s -> %s/%s/%s", tag, m.path.name,
                         m.app_name, category.capitalize(), m.path.name)
                counts[f"{m.app_name}/{category}"] += 1
            else:
                log.info("[DRY] %s -> %s/<category>/%s", m.path.name,
                         m.app_name, m.path.name)
                counts[m.app_name] += 1
        except Exception as exc:
            errors += 1
            log.warning("[ERR] %s: %s", m.path.name, exc)

    log.info("--- summary ---")
    for key, n in sorted(counts.items()):
        log.info("  %s: %d", key, n)
    if args.apply:
        log.info("ocr calls: %d, llm calls: %d, errors: %d", ocr_calls, llm_calls, errors)
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
