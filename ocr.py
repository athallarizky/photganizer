"""OCR extraction via pytesseract."""
from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

from config import IMAGE_MAX_SIDE


def extract_text(image_path: Path, lang: str = "eng") -> str:
    """Run tesseract on an image, return cleaned text."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img = ImageOps.autocontrast(img)
        scale = IMAGE_MAX_SIDE / max(img.size)
        if scale < 1.0:
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)
        raw = pytesseract.image_to_string(img, lang=lang)
    lines = [ln.strip() for ln in raw.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return text
