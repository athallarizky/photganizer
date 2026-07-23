"""Static configuration for ss-organizer."""
from __future__ import annotations

from pathlib import Path

SOURCE_ROOT = Path.home() / "storage/shared/Pictures/Gallery/owner"
DEST_ROOT = SOURCE_ROOT / "Organized"
CACHE_DB = Path.home() / ".cache/screenshot_organizer.sqlite"

APP_MAP = {
    "com.whatsapp": "WhatsApp",
    "com.instagram.barcelona": "Threads",
    "com.facebook.katana": "Facebook",
}


def app_name(package: str) -> str:
    """Derive human-readable app name from Android package name."""
    if package in APP_MAP:
        return APP_MAP[package]
    parts = package.split(".")
    return parts[-2].capitalize() if len(parts) >= 3 else parts[-1].capitalize()


CATEGORY_DIRS = ("Discussion", "Other")

DEFAULT_LANG = "eng"
IMAGE_MAX_SIDE = 1568
OCR_TEXT_TRUNCATE = 2000

LLM_MODEL_ENV = "ANTHROPIC_DEFAULT_HAIKU_MODEL"
LLM_MAX_TOKENS = 2000
LLM_BATCH_SIZE = 50

PRE_FILTER_MIN_CHARS = 50

PRE_FILTER_CHAT_SIGNALS = [
    r"\b\d{1,2}[:.]\d{2}\b",
    r"\b(AM|PM)\b",
]

SYSTEM_PROMPT = (
    "You classify OCR-extracted text from screenshots. "
    "You will receive a list of entries, each labeled [ID] with its text. "
    "For each entry, decide: `discussion` if the text contains a real conversation — "
    "chat messages, threaded replies, comments, DMs, or group discussion. "
    "`other` if the text is a single caption, headline, meme, empty, or non-conversational. "
    "Reply with ONLY a valid JSON array: "
    '[{"id": 1, "category": "discussion"}, {"id": 2, "category": "other"}, ...] '
    "Include every ID from the input. No other text."
)
