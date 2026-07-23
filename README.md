# photganizer

Kumpulan tool untuk **organize** dan **backup** foto/screenshot Android.

## Komponen

| Folder | Fungsi |
|--------|--------|
| [`screenshot-organizer/`](./screenshot-organizer/) | Kategorikan screenshot berdasarkan pattern filename (WhatsApp, Facebook, Instagram, Threads, Twitter/X) |
| [`rsync-backup/`](./rsync-backup/) | Backup foto dari remote device (HP/Termux/SSH) ke komputer via Tailscale SSH + rsync |

## screenshot-organizer

Kategorisasi murni dari **pattern filename** — tidak butuh OCR/LLM/network.
File di-copy (bukan move), jadi aman untuk re-run.

```bash
python3 screenshot-organizer/organize_screenshots.py --dry-run
python3 screenshot-organizer/organize_screenshots.py --apply --limit 10
python3 screenshot-organizer/organize_screenshots.py --apply --yes
```

Override source/dest via flag atau env var:

```bash
python3 screenshot-organizer/organize_screenshots.py \
  --source /path/to/photos --dest /path/to/output --apply
```

Detail: [`screenshot-organizer/`](./screenshot-organizer/) — lihat source.

## rsync-backup

Interactive prompt → rsync via Tailscale SSH. Mode copy atau move.
Multi-select folder yang ingin di-backup.

```bash
python3 rsync-backup/backup.py --dry-run
python3 rsync-backup/backup.py
```

Detail: [`rsync-backup/README.md`](./rsync-backup/README.md),
[`rsync-backup/SKILL.md`](./rsync-backup/SKILL.md).

## Requirements

- Python 3.10+
- Untuk rsync-backup: `rsync` di komputer + SSH server di remote

## Privacy

Tidak ada telemetri, tidak ada network call selain SSH (untuk rsync-backup).
Tidak ada hardcoded credentials/IPs/personal info — semua via interactive
prompt atau env vars.
