"""Classify OCR text via glm-air exposed through the Anthropic-compatible endpoint."""
from __future__ import annotations

import json
import logging
import os

from anthropic import Anthropic

from config import LLM_MAX_TOKENS, LLM_MODEL_ENV, OCR_TEXT_TRUNCATE, SYSTEM_PROMPT

log = logging.getLogger(__name__)


def _client() -> Anthropic:
    return Anthropic()


def _model() -> str:
    return os.environ[LLM_MODEL_ENV]


def classify_batch(entries: list[dict]) -> dict[int, str]:
    """Return {id: category} for a batch of entries.

    entries: [{"id": int, "text": str}, ...]
    """
    if not entries:
        return {}

    lines = []
    for e in entries:
        eid = e["id"]
        text = (e["text"] or "").strip()[:OCR_TEXT_TRUNCATE]
        lines.append(f"[{eid}] {text}")

    user_content = "OCR_TEXT:\n" + "\n\n".join(lines)

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
        messages=[{"role": "user", "content": user_content}],
    )

    raw = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip()

    results: dict[int, str] = {}
    parsed = _parse_json(raw)
    if parsed is None:
        log.warning("unparsable batch LLM response, defaulting all to other: %r", raw[:200])
        for e in entries:
            results[e["id"]] = "other"
        return results

    seen: set[int] = set()
    for item in parsed:
        eid = item.get("id")
        cat = str(item.get("category", "")).strip().lower()
        if eid is None:
            continue
        if "discussion" in cat:
            results[eid] = "discussion"
        else:
            results[eid] = "other"
        seen.add(eid)

    for e in entries:
        if e["id"] not in seen:
            results[e["id"]] = "other"

    return results


def _parse_json(raw: str) -> list[dict] | None:
    raw = raw.strip()
    for candidate in (raw, raw.lstrip("```json").rstrip("```"), raw.lstrip("```").rstrip("```")):
        try:
            return json.loads(candidate.strip())
        except json.JSONDecodeError:
            continue
    return None
