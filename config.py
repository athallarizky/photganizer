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

CATEGORY_DIRS = ("Discussion", "Meme")

DEFAULT_LANG = "eng"
IMAGE_MAX_SIDE = 1568
OCR_TEXT_TRUNCATE = 2000

LLM_MODEL_ENV = "ANTHROPIC_DEFAULT_HAIKU_MODEL"
LLM_MAX_TOKENS = 10

SYSTEM_PROMPT = (
    "You classify screenshots based on OCR-extracted text. "
    "Reply with exactly one lowercase word: "
    "`discussion` if the text contains chat, conversation, messages, comments, "
    "threaded replies, status updates with replies, or DMs (typical of WhatsApp, "
    "Threads, or Facebook feeds or inboxes), or "
    "`meme` if the text is empty, very short, a single caption, a meme headline, "
    "or non-conversational (typical of a shared photo, meme, sticker, or graphic). "
    "Respond with ONLY the word, nothing else."
)
