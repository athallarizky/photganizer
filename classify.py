"""Classify OCR text via glm-air exposed through the Anthropic-compatible endpoint."""
from __future__ import annotations

import logging
import os

from anthropic import Anthropic

from config import LLM_MAX_TOKENS, LLM_MODEL_ENV, OCR_TEXT_TRUNCATE, SYSTEM_PROMPT

log = logging.getLogger(__name__)


def _client() -> Anthropic:
    return Anthropic()


def _model() -> str:
    return os.environ[LLM_MODEL_ENV]


def classify_text(text: str) -> str:
    """Return 'discussion' or 'meme'. Defaults to 'meme' on ambiguity."""
    text = (text or "").strip()[:OCR_TEXT_TRUNCATE]
    resp = _client().messages.create(
        model=_model(),
        max_tokens=LLM_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": f"OCR_TEXT:\n{text}"}],
    )
    raw = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip().lower()
    if "discussion" in raw:
        return "discussion"
    if "meme" in raw:
        return "meme"
    log.warning("unparsable LLM response: %r — defaulting to meme", raw)
    return "meme"
