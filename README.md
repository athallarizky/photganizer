# photganizer

Toolset for **organizing** and **backing up** Android photos/screenshots.

## Components

| Folder | Purpose |
|--------|---------|
| [`screenshot-organizer/`](./screenshot-organizer/) | Categorize screenshots by filename pattern (WhatsApp, Facebook, Instagram, Threads, Twitter/X) |
| [`rsync-backup/`](./rsync-backup/) | Back up photos from a remote phone to this computer via Tailscale SSH + rsync |

## screenshot-organizer

Categorization is pure **filename-pattern matching** — no OCR, no LLM, no
network calls. Files are copied (not moved), so re-running is safe.

```bash
python3 screenshot-organizer/organize_screenshots.py --dry-run
python3 screenshot-organizer/organize_screenshots.py --apply --limit 10
python3 screenshot-organizer/organize_screenshots.py --apply --yes
```

Override source/dest via CLI flags or env vars:

```bash
python3 screenshot-organizer/organize_screenshots.py \
  --source /path/to/photos --dest /path/to/output --apply
```

Rules live in [`screenshot-organizer/config.py`](./screenshot-organizer/config.py) —
edit the `RULES` list to add or reorder patterns.

## rsync-backup

Interactive prompt → rsync via Tailscale SSH. Copy or move mode. Multi-select
folders to back up.

```bash
python3 rsync-backup/backup.py --dry-run
python3 rsync-backup/backup.py
```

Details: [`rsync-backup/README.md`](./rsync-backup/README.md),
[`rsync-backup/SKILL.md`](./rsync-backup/SKILL.md).

## Requirements

- Python 3.10+
- For rsync-backup: `rsync` on the computer + SSH server on the phone

## Privacy

No telemetry, no network calls except SSH (for rsync-backup). No hardcoded
credentials/IPs/personal data — everything is via interactive prompts or
env vars.
