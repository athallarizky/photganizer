---
name: photganizer-rsync-backup
description: Back up photos from a remote phone to this computer via Tailscale SSH + rsync. Use when the user wants to transfer photos/images from a phone to their computer, or asks for "backup phone", "pull photos from phone", "sync gallery".
---

# SKILL: rsync-backup

Guide for an LLM/Claude driving this script when a user wants to back up
photos from their phone to the computer.

## When to use

User triggers (examples):
- "back up photos from my phone"
- "transfer images from phone to computer"
- "pull folder X from the phone"
- "sync the phone gallery here"

## How to invoke

This script runs on the **computer** (the side the user is currently on),
not on the phone.

```bash
# Always start with a dry-run to preview:
python3 <path-to-photganizer>/rsync-backup/backup.py --dry-run

# After user confirmation, run without --dry-run:
python3 <path-to-photganizer>/rsync-backup/backup.py
```

## Session reuse

After the first successful run, a session file is saved at
`<repo>/.photganizer-session.json`. Subsequent runs auto-detect it and offer
to reuse the saved config. For repeat runs:

```bash
# Reuse saved session (default behavior):
python3 rsync-backup/backup.py
# Just press Enter / "y" at the prompts to accept defaults.

# Force fresh prompts:
python3 rsync-backup/backup.py --no-session
```

## What to validate with the user

The script will prompt interactively. You can help the user answer, or run
with `--from-json` if you already know all values.

### 1. Mode: copy or move?

- **`copy`** (recommended default) — duplicates files to computer, leaves
  them on phone.
- **`move`** — deletes from phone after transfer. Risky if transfer fails.

**Always recommend `copy`** unless the user explicitly asks for move.

### 2. Phone connection (required user input)

The script needs:
- **Host** (Tailscale IP / hostname)
- **SSH user**
- **SSH port** (default 22, or 8022 for Termux)
- **Source root path** on the phone

There are **no defaults** for host/user/path — the user must provide them.
Do not guess or hallucinate IPs.

If the user doesn't know the source path, the script will auto-scan common
Android locations and offer to browse the filesystem interactively.

### 3. Which folders to back up?

The script SSHes into the phone and lists subfolders of the source root.
The user will see something like:

```
  1. [All folders]
  2. Threads
  3. Instander
  4. Facebook
  ...
```

Pick:
- `0` = all folders (full mirror)
- `1,3,5` = specific folders

### 4. Destination path

Default: `<cwd>/photganizer-backup`. User can override to any path.

**Validate**: ensure the disk has enough space. Check with `df -h <dest>`.

## Before execution

The script prints a summary:

```
=== Confirmation ===
  Mode       : COPY
  Phone      : user@<host>:<port>
  Source     : <source_root>
  Folders    : Threads, Facebook
  Destination: /home/user/photganizer-backup
```

**Always show this to the user and ask for explicit confirmation** before
proceeding with `y`.

## Common pitfalls

1. **Wrong direction**: the script PULLs (computer fetches from phone). Not push.
2. **Wrong SSH key direction**: needs key **computer → phone** (already set up
   if the user can SSH to the phone).
3. **Source path on remote**: use absolute path valid on the phone side. For
   Termux/Android: `/sdcard/...` or `/storage/emulated/0/...`.
4. **Move = destructive**: always preview with `--dry-run` before move.

## Error handling

| Error message | Meaning | Fix |
|---------------|---------|-----|
| `Connection refused` | sshd not running / unreachable | Check phone: sshd running, Tailscale connected |
| `Permission denied (publickey)` | Computer's key not in phone's authorized_keys | Add to `~/.ssh/authorized_keys` |
| `No such file or directory` on source | Wrong remote path | Verify with `ssh user@host ls /path` |

## After backup completes

The user may want to:
- **Organize**: run `screenshot-organizer/organize_screenshots.py` on the
  computer to categorize the backup output.
- **Verify**: compare source vs dest file counts.
- **Delete source** (if copy mode): manually after verifying.

## Example LLM-driven session

```
User: "back up Threads and Facebook photos from my phone to /mnt/external/photos"

You:
1. Check connectivity: `ssh <user>@<host> ls /path/to/photos/`
2. Preview: `python3 rsync-backup/backup.py --dry-run`
   - At host/user/port prompt: use values from user
   - At source root prompt: scan results or user-provided path
   - At folder prompt: enter numbers for Threads + Facebook
   - At dest prompt: /mnt/external/photos
3. Show summary to user, ask for confirmation
4. Real run: `python3 rsync-backup/backup.py` (session auto-loaded)
5. Verify count in dest
```

## Non-interactive mode (LLM-friendly)

If you already know all the answers (e.g. from a prior session), skip prompts:

```bash
# First, create the config JSON
cat > backup-config.json <<EOF
{
  "mode": "copy",
  "folders": ["Threads", "Facebook"],
  "dest": "/mnt/external/photos",
  "phone_host": "<user-provided-ip>",
  "phone_user": "<user>",
  "phone_port": 22,
  "source_root": "/path/on/phone"
}
EOF

# Run non-interactively
python3 rsync-backup/backup.py --from-json backup-config.json
```

Good for:
- Cron jobs
- Repeated runs
- Automation

## Security notes

- **Never hardcode IP/user in scripts or configs committed to git.**
- **Never share a user's specific Tailscale IP publicly.**
- For automation, use environment variables (see README) or a config file
  that's already in `.gitignore`.
