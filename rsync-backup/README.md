# rsync-backup

Back up photos from a remote phone to this computer via **Tailscale SSH + rsync**.

## Architecture

```
[Computer]                       [Phone]
                  Tailscale / LAN
   rsync  ─────────SSH─────────►  sshd:22 (or custom)
   (pull)                          |
                                   v
                                /path/to/photos/
                                    ├── Folder1/
                                    ├── Folder2/
                                    └── ...
```

**Direction**: pull (the computer fetches from the phone). Not push.

**Why pull?** The SSH key you already have set up is usually computer → phone.
This script runs on the computer and uses that existing key, so there's no
extra setup.

## Prerequisites

1. **SSH server running on the phone** (Termux / sshd), reachable via Tailscale
   or LAN.
2. **Computer's SSH key already registered** on the phone's
   `~/.ssh/authorized_keys`.
3. **`rsync` installed on BOTH ends**:
   - **Computer**: macOS (pre-installed) / Linux (`apt install rsync` /
     `dnf install rsync`) / Windows (WSL or Git Bash usually pre-installed)
   - **Phone (Termux)**: `pkg install rsync` — Termux does **not** ship rsync
     by default; this is required because SSH invokes `rsync` on the remote
     side to speak the rsync protocol.

## Install

```bash
git clone <repo-photganizer> ~/photganizer
cd ~/photganizer
```

Only Python 3.10+ stdlib is needed (no external dependencies).

## Usage

```bash
# Interactive (default), preview without transfer:
python3 rsync-backup/backup.py --dry-run

# Interactive, real run:
python3 rsync-backup/backup.py

# Non-interactive (replay from saved config):
python3 rsync-backup/backup.py --from-json backup-config.json

# Ignore the auto-loaded session file:
python3 rsync-backup/backup.py --no-session
```

## Session persistence

After a successful interactive run, the script saves the chosen config to
`.photganizer-session.json` at the repo root (gitignored — never committed).

On the next run, it detects the session and offers to reuse it — no need to
re-enter IP/user/path each time.

| Flag | Behavior |
|------|----------|
| _(default)_ | Load session if present, prompt to reuse |
| `--no-session` | Ignore session, prompt for everything |
| `--from-json FILE` | Skip session + prompts, load from explicit file |

## Interactive flow

1. **Mode**: `copy` or `move`
   - `copy` — keeps files on phone (recommended)
   - `move` — deletes from phone after transfer (`--remove-source-files`)
2. **Phone connection**: host, user, port
3. **Source root discovery** (one of):
   - Auto-scan common Android photo paths (`/sdcard/Pictures`, `/sdcard/DCIM/Camera`, etc.)
   - Browse filesystem interactively (navigate up/down)
   - Custom path input
4. **Folder selection**: multi-select via comma-separated numbers
5. **Destination**: local path on this computer
6. **Confirmation**: review before execute

## Environment variables (optional)

All env vars are optional and only used to pre-fill defaults in prompts.

| Var | Default | Purpose |
|-----|---------|---------|
| `PHONE_TAILSCALE_HOST` | _(empty, required input)_ | Phone host/IP |
| `PHONE_TAILSCALE_USER` | _(empty, required input)_ | SSH user |
| `PHONE_TAILSCALE_PORT` | `22` | SSH port |
| `PHOTO_SOURCE_ROOT` | _(empty)_ | Source path on phone (skips scan) |
| `BACKUP_DEST_ROOT` | `<cwd>/photganizer-backup` | Destination default |

Example:
```bash
PHONE_TAILSCALE_HOST=100.x.x.x PHONE_TAILSCALE_USER=user \
  python3 rsync-backup/backup.py
```

## Output

```
<dest>/
├── Folder1/
│   ├── image1.jpg
│   └── ...
├── Folder2/
│   └── ...
└── ...
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused` | sshd not running / unreachable | Check phone: sshd running, Tailscale connected |
| `Permission denied (publickey)` | Computer's key not registered | Add to phone's `~/.ssh/authorized_keys` |
| `rsync: command not found` (or similar) | rsync not installed on phone | On Termux: `pkg install rsync` (required on **both** ends) |
| `find: ... Permission denied` | Source path not readable via SSH | Check path is correct & SSH user has access |
| Empty output folder | rsync skipped because files already match | Add `--delete` to mirror (use with caution) |
| No common paths found in scan | Phone uses non-standard layout | Use "Browse" or "Custom path input" |

## Tips

- **First run**: always use `--dry-run` to preview what will be transferred.
- **Mode `move` is destructive** — if rsync fails mid-transfer, files are
  already deleted from the phone. Use `copy` first, delete manually after
  verifying.
- **Resume**: rsync resumes automatically via `--partial`. You can Ctrl+C and
  re-run safely.
- **Large transfers**: `-z` (compression) is on by default. For already-compressed
  files (JPG/PNG) the effect is minimal.

## See also

- [`SKILL.md`](./SKILL.md) — Guide for LLM/Claude to drive this script.
