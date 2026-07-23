"""Static configuration for ss-organizer."""
from __future__ import annotations

import os
import re
from pathlib import Path

# Source root: override via PHOTO_SOURCE_ROOT env var atau --source flag.
DEFAULT_SOURCE_ROOT = Path.home() / "storage/shared/Pictures"
SOURCE_ROOT = Path(os.environ.get("PHOTO_SOURCE_ROOT", str(DEFAULT_SOURCE_ROOT)))
DEST_ROOT = Path(os.environ.get("PHOTO_DEST_ROOT", str(SOURCE_ROOT / "Organized")))

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic")

# Mapping pattern filename -> nama folder output.
# Urutan penting: match pertama yang menang.
# Ekstensi regex (case-insensitive) dicocokkan terhadap nama file.
RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^FB_IMG_", re.IGNORECASE),           "Facebook"),
    (re.compile(r"com\.facebook\.(katana|lite)", re.I), "Facebook"),
    (re.compile(r"-WA\d+", re.IGNORECASE),              "WhatsApp"),
    (re.compile(r"com\.whatsapp", re.IGNORECASE),       "WhatsApp"),
    (re.compile(r"com\.instagram\.android", re.I),      "Instagram"),
    (re.compile(r"com\.instander\.android", re.I),      "Instagram"),
    (re.compile(r"com\.instagram\.barcelona", re.I),    "Threads"),
    (re.compile(r"com\.twitter\.android", re.I),         "Twitter"),
    (re.compile(r"com\.x\.corp", re.IGNORECASE),         "Twitter"),
]

DEFAULT_CATEGORY = "Other"


def categorize(filename: str) -> str:
    """Return category name based on filename. First matching rule wins."""
    for pattern, label in RULES:
        if pattern.search(filename):
            return label
    return DEFAULT_CATEGORY
