"""SQLite-backed cache to avoid re-running OCR + LLM on unchanged files."""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Optional

from config import CACHE_DB


def _connect() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS classification (
            key           TEXT PRIMARY KEY,
            source_path   TEXT NOT NULL,
            category      TEXT NOT NULL,
            ocr_text      TEXT,
            created_at    REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def make_key(path: Path) -> str:
    stat = path.stat()
    fingerprint = f"{path}|{stat.st_mtime_ns}|{stat.st_size}"
    return hashlib.sha1(fingerprint.encode()).hexdigest()


def get(key: str) -> Optional[tuple[str, str]]:
    """Return (category, ocr_text) if cached, else None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT category, ocr_text FROM classification WHERE key = ?",
            (key,),
        ).fetchone()
    return row if row else None


def put(key: str, source_path: Path, category: str, ocr_text: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO classification
                (key, source_path, category, ocr_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, str(source_path), category, ocr_text, time.time()),
        )
        conn.commit()


def reset() -> None:
    if CACHE_DB.exists():
        CACHE_DB.unlink()
