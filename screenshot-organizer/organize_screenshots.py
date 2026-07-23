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

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from cache import get as cache_get, make_key, put as cache_put, reset as cache_reset
from classify import classify_batch
from config import (
    DEFAULT_LANG,
    DEST_ROOT,
    LLM_BATCH_SIZE,
    PRE_FILTER_CHAT_SIGNALS,
    PRE_FILTER_MIN_CHARS,
    SOURCE_ROOT,
    app_name,
)

if sys.version_info >= (3, 12):
    from itertools import batched
else:

    from itertools import islice

    def batched(iterable, n):
        it = iter(iterable)
        while batch := tuple(islice(it, n)):
            yield batch


from ocr import extract_text

log = logging.getLogger("ss-organizer")

FILENAME_RE = re.compile(
    r"^Screenshot_.*_(?P<pkg>com\.[a-z0-9_.]+)\.(?:jpg|jpeg|png)$", re.IGNORECASE
)

CHAT_SIGNAL_RE = re.compile("|".join(PRE_FILTER_CHAT_SIGNALS), re.IGNORECASE)


@dataclass
class Match:
    path: Path
    package: str
    app_name: str


@dataclass
class Entry:
    eid: int
    match: Match
    ocr_text: str


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
        if since and not _dated_after(path.name, since):
            continue
        matches.append(Match(path=path, package=pkg, app_name=app_name(pkg)))
    matches.sort(key=lambda x: x.path.name)
    return matches


def _dated_after(filename: str, since: str) -> bool:
    date_part = filename[len("Screenshot_") : len("Screenshot_") + 10]
    return date_part >= since


def pre_filter(entries: list[Entry]) -> tuple[list[Entry], dict[int, str]]:
    llm_candidates: list[Entry] = []
    auto_results: dict[int, str] = {}

    for entry in entries:
        text_len = len(entry.ocr_text)
        if text_len < PRE_FILTER_MIN_CHARS:
            auto_results[entry.eid] = "other"
            continue
        if not CHAT_SIGNAL_RE.search(entry.ocr_text):
            auto_results[entry.eid] = "other"
            continue
        llm_candidates.append(entry)

    return llm_candidates, auto_results


def batch_classify(entries: list[Entry]) -> dict[int, str]:
    all_results: dict[int, str] = {}
    for chunk in batched(entries, LLM_BATCH_SIZE):
        batch = [{"id": e.eid, "text": e.ocr_text} for e in chunk]
        try:
            results = classify_batch(batch)
        except Exception as exc:
            log.warning("LLM batch call failed: %s — defaulting chunk to other", exc)
            for e in chunk:
                all_results[e.eid] = "other"
            continue
        all_results.update(results)
    return all_results


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

    if not args.apply:
        counts: Counter[str] = Counter()
        for m in matches:
            log.info("[DRY] %s -> %s/<category>/%s", m.path.name,
                     m.app_name, m.path.name)
            counts[m.app_name] += 1
        log.info("--- summary ---")
        for key, n in sorted(counts.items()):
            log.info("  %s: %d", key, n)
        return 0

    if not args.yes:
        uncached = sum(1 for m in matches if cache_get(make_key(m.path)) is None)
        log.info(
            "--apply will process %d uncached files (%d total). "
            "Continue? [y/N] ",
            uncached,
            len(matches),
        )
        try:
            answer = input()
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            log.info("aborted")
            return 0

    category_map: dict[Path, str] = {}
    uncached_entries: list[Entry] = []
    eid = 0
    ocr_calls = 0

    for m in matches:
        key = make_key(m.path)
        cached = cache_get(key)
        if cached is not None:
            category_map[m.path] = cached[0]
            continue
        text = extract_text(m.path, lang=args.lang)
        ocr_calls += 1
        uncached_entries.append(Entry(eid=eid, match=m, ocr_text=text))
        eid += 1

    log.info("ocr done — %d uncached of %d total", ocr_calls, len(matches))

    llm_calls = 0
    auto_other_count = 0

    if uncached_entries:
        llm_candidates, auto_results = pre_filter(uncached_entries)
        auto_other_count = len(auto_results)
        for entry in uncached_entries:
            if entry.eid in auto_results:
                cat = auto_results[entry.eid]
                category_map[entry.match.path] = cat
                cache_put(make_key(entry.match.path), entry.match.path, cat, entry.ocr_text)

        log.info(
            "pre-filter: %d candidates for LLM, %d auto-classified as other",
            len(llm_candidates),
            auto_other_count,
        )

        if llm_candidates:
            num_batches = -(-len(llm_candidates) // LLM_BATCH_SIZE)
            llm_calls = num_batches
            log.info("sending %d entries to LLM in %d batch(es)",
                     len(llm_candidates), num_batches)
            llm_results = batch_classify(llm_candidates)
            for entry in llm_candidates:
                cat = llm_results.get(entry.eid, "other")
                category_map[entry.match.path] = cat
                cache_put(make_key(entry.match.path), entry.match.path, cat, entry.ocr_text)

    counts: Counter[str] = Counter()
    errors = 0

    for m in matches:
        category = category_map.get(m.path, "other")
        dest = destination_for(m, category)
        try:
            if dest.exists():
                tag = "SKIP"
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(m.path, dest)
                tag = "OK"
        except Exception as exc:
            errors += 1
            log.warning("[ERR] %s: %s", m.path.name, exc)
            continue
        log.info("[%s] %s -> %s/%s/%s", tag, m.path.name,
                 m.app_name, category.capitalize(), m.path.name)
        counts[f"{m.app_name}/{category}"] += 1

    log.info("--- summary ---")
    for key, n in sorted(counts.items()):
        log.info("  %s: %d", key, n)
    if uncached_entries:
        log.info("ocr calls: %d, llm calls: %d, auto-other: %d", ocr_calls, llm_calls, auto_other_count)
    log.info("errors: %d", errors)
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
