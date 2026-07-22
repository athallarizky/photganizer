# ss-organizer

Group screenshots by source app (WhatsApp, Threads, Facebook) and split each app's
screenshots into **Discussion** (chat / conversation / comments) vs **Meme**
(single image, photo, or graphic).

The source app is parsed from the filename (Android embeds the package name).
Discussion-vs-meme classification uses Tesseract OCR + the configured Anthropic-
compatible LLM (env: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`,
`ANTHROPIC_DEFAULT_HAIKU_MODEL` — points at glm-air by default).

## Install

```
pkg install tesseract rust
pip install -r requirements.txt
```

`rust` is required because the `anthropic` SDK pulls in `jiter`, which has no
prebuilt wheel for aarch64-Android and must be built from source.

## Usage

```
# Preview matches without OCR / LLM / writes:
python3 organize_screenshots.py --dry-run

# Test on 5 files, prompt before sending to LLM:
python3 organize_screenshots.py --apply --limit 5

# Full run, no prompt:
python3 organize_screenshots.py --apply --yes
```

## Flags

- `--apply` — actually OCR + classify + copy. Default mode is dry-run.
- `--limit N` — process at most N files.
- `--since YYYY-MM-DD` — only files dated this day or later.
- `--lang eng+ind` — Tesseract language(s). Default `eng`. Add `ind` for Indonesian.
- `--yes` — skip the cost-estimate confirmation prompt.
- `--reset-cache` — wipe `~/.cache/screenshot_organizer.sqlite` before running.
- `-v` — verbose logging.

## Output layout

```
~/storage/shared/Pictures/Gallery/owner/Organized/
├── WhatsApp/
│   ├── Discussion/   *.jpg
│   └── Meme/         *.jpg
├── Threads/
│   ├── Discussion/
│   └── Meme/
└── Facebook/
    ├── Discussion/
    └── Meme/
```

Originals are **copied**, never moved — re-running is safe and idempotent.
