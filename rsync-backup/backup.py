#!/usr/bin/env python3
"""Backup photos from a remote phone to this computer via Tailscale SSH + rsync.

Runs on the COMPUTER side. Uses the SSH key already registered in the phone's
authorized_keys (computer -> phone direction).

Interactive flow:
  1. Mode: copy or move
  2. Phone connection: host, user, port
  3. Source root on phone: scan common Android photo paths, browse, or custom
  4. Folder selection: multi-select via comma-separated numbers
  5. Destination: local path on this computer

Session config (host/user/port/source_root/dest) is auto-saved to
.photganizer-session.json at the repo root, and offered on next run.

Usage:
    python3 backup.py                          # interactive
    python3 backup.py --dry-run                # preview without transfer
    python3 backup.py --from-json config.json  # non-interactive
    python3 backup.py --no-session             # ignore saved session
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------- Paths ----------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SESSION_FILE = REPO_ROOT / ".photganizer-session.json"

# ---------- Config (env-overridable, no hardcoded personal defaults) ----------
DEFAULT_PHONE_HOST = os.environ.get("PHONE_TAILSCALE_HOST", "")
DEFAULT_PHONE_USER = os.environ.get("PHONE_TAILSCALE_USER", "")
DEFAULT_PHONE_PORT = int(os.environ.get("PHONE_TAILSCALE_PORT", "22"))
DEFAULT_SOURCE_ROOT = os.environ.get("PHOTO_SOURCE_ROOT", "")
DEFAULT_DEST = os.environ.get("BACKUP_DEST_ROOT", "")

# Common Android photo locations (checked via SSH scan).
COMMON_PHOTO_PATHS = [
    "/sdcard/Pictures",
    "/sdcard/Pictures/Screenshots",
    "/sdcard/Pictures/Gallery",
    "/sdcard/DCIM/Camera",
    "/sdcard/DCIM/Screenshots",
    "/storage/emulated/0/Pictures",
    "/storage/emulated/0/Pictures/Screenshots",
    "/storage/emulated/0/DCIM/Camera",
    "/storage/emulated/0/DCIM/Screenshots",
]


def eprint(*a: Any, **k: Any) -> None:
    print(*a, file=sys.stderr, **k)


@dataclass
class Config:
    mode: str                                   # "copy" or "move"
    folders: list[str]                          # folder names, or ["*"] for all
    dest: str                                   # local destination path
    phone_host: str
    phone_user: str
    phone_port: int
    source_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "folders": self.folders,
            "dest": self.dest,
            "phone_host": self.phone_host,
            "phone_user": self.phone_user,
            "phone_port": self.phone_port,
            "source_root": self.source_root,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Config":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


# ---------- Prompts ----------
def prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{msg}{suffix}: ").strip() or default


def prompt_required(msg: str, default: str = "") -> str:
    """Prompt that cannot be empty."""
    while True:
        val = prompt(msg, default)
        if val:
            return val
        eprint("  cannot be empty")


def prompt_select(msg: str, options: list[str]) -> str:
    print(f"\n{msg}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        choice = input(f"Pick 1-{len(options)}: ").strip()
        try:
            return options[int(choice) - 1]
        except (ValueError, IndexError):
            eprint("  invalid")


def prompt_multi(msg: str, options: list[str]) -> list[str]:
    """Multi-select via comma-separated numbers. '0' = all."""
    print(f"\n{msg}")
    print("  Enter numbers separated by commas (e.g. 1,3,5). '0' = all.")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        choice = input("Pick: ").strip()
        if not choice:
            continue
        picked: list[str] = []
        for part in choice.split(","):
            part = part.strip()
            try:
                n = int(part)
                if n == 0:
                    return list(options)
                if 1 <= n <= len(options) and options[n - 1] not in picked:
                    picked.append(options[n - 1])
            except ValueError:
                pass
        if picked:
            return picked
        eprint("  invalid")


def confirm(msg: str, default_yes: bool = False) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    val = input(f"{msg} {suffix}: ").strip().lower()
    if not val:
        return default_yes
    return val in ("y", "yes")


# ---------- SSH helpers ----------
def ssh_quiet(host: str, user: str, port: int, cmd: str) -> tuple[int, str, str]:
    args = ["ssh", "-p", str(port), f"{user}@{host}", cmd]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def list_remote_dirs(host: str, user: str, port: int, path: str) -> list[str]:
    """List subdirectory names at remote path (one level deep)."""
    cmd = f"find {shlex.quote(path)} -maxdepth 1 -mindepth 1 -type d 2>/dev/null"
    code, out, _ = ssh_quiet(host, user, port, cmd)
    if code != 0:
        return []
    return sorted(os.path.basename(line.strip()) for line in out.splitlines() if line.strip())


def remote_path_exists(host: str, user: str, port: int, path: str) -> bool:
    code, _, _ = ssh_quiet(host, user, port, f"test -d {shlex.quote(path)}")
    return code == 0


# ---------- Path discovery ----------
def scan_common_paths(host: str, user: str, port: int) -> list[str]:
    """Return which COMMON_PHOTO_PATHS exist on the remote."""
    checks = " ".join(f"-d {shlex.quote(p)}" for p in COMMON_PHOTO_PATHS)
    # Build: for p in <paths>; do [ -d "$p" ] && echo "$p"; done
    paths_quoted = " ".join(shlex.quote(p) for p in COMMON_PHOTO_PATHS)
    cmd = f"for p in {paths_quoted}; do [ -d \"$p\" ] && echo \"$p\"; done"
    code, out, _ = ssh_quiet(host, user, port, cmd)
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def browse_path(host: str, user: str, port: int, start: str) -> str:
    """Interactively navigate the remote filesystem. Returns the selected path."""
    current = start.rstrip("/") or "/"
    while True:
        cmd = f"find {shlex.quote(current)} -maxdepth 1 -mindepth 1 -type d 2>/dev/null"
        code, out, _ = ssh_quiet(host, user, port, cmd)
        dirs = sorted(line.strip() for line in out.splitlines() if line.strip())

        print(f"\nCurrent: {current}")
        for i, d in enumerate(dirs, 1):
            short = os.path.basename(d)
            print(f"  {i}. {short}/")
        print(f"  u. ..  (go up)")
        print(f"  s. select this path")
        print(f"  c. custom path input")

        choice = input("> ").strip().lower()
        if choice == "s":
            return current
        if choice == "c":
            custom = input("Path: ").strip()
            if custom and remote_path_exists(host, user, port, custom):
                current = custom.rstrip("/")
            elif custom:
                eprint(f"  not a directory or not accessible: {custom}")
        elif choice == "u":
            parent = os.path.dirname(current)
            current = parent if parent else "/"
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(dirs):
                    current = dirs[idx].rstrip("/")
            except ValueError:
                pass


def discover_source_root(host: str, user: str, port: int) -> str:
    """Scan + browse to let the user pick a source root on the remote."""
    print("\nScanning common Android photo paths via SSH...")
    found = scan_common_paths(host, user, port)
    if found:
        print(f"Found {len(found)} location(s):")
        options = found + ["[Browse filesystem]", "[Custom path input]"]
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            choice = input(f"Pick 1-{len(options)}: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    picked = options[idx]
                    if picked == "[Browse filesystem]":
                        start = found[0] if found else "/"
                        return browse_path(host, user, port, start)
                    if picked == "[Custom path input]":
                        return _prompt_custom_path(host, user, port)
                    return picked
            except ValueError:
                pass
            eprint("  invalid")
    else:
        eprint("No common paths found. Falling back to browse.")
        start = "/"
        return browse_path(host, user, port, start) or _prompt_custom_path(host, user, port)


def _prompt_custom_path(host: str, user: str, port: int) -> str:
    while True:
        path = prompt_required("Enter path on phone")
        if remote_path_exists(host, user, port, path):
            return path
        eprint(f"  not a directory or not accessible: {path}")


# ---------- Session ----------
def load_session() -> dict[str, Any] | None:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_session(cfg: Config) -> None:
    try:
        SESSION_FILE.write_text(json.dumps(cfg.to_dict(), indent=2))
        print(f"\nSession saved to {SESSION_FILE}")
    except OSError as exc:
        eprint(f"Failed to save session: {exc}")


# ---------- rsync ----------
def run_rsync(cfg: Config, dry_run: bool = False) -> int:
    is_all = cfg.folders == ["*"]
    src_paths = (
        [cfg.source_root.rstrip("/")]
        if is_all
        else [f"{cfg.source_root.rstrip('/')}/{f}" for f in cfg.folders]
    )

    dest_root = Path(cfg.dest).expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    rc = 0
    for src in src_paths:
        folder_name = src.rsplit("/", 1)[-1]
        dest_sub = dest_root if is_all else dest_root / folder_name
        if not is_all:
            dest_sub.mkdir(parents=True, exist_ok=True)

        cmd = [
            "rsync", "-avz", "--partial", "--human-readable", "--progress",
            "-e", f"ssh -p {cfg.phone_port}",
        ]
        if cfg.mode == "move":
            cmd.append("--remove-source-files")
        if dry_run:
            cmd.append("--dry-run")
        cmd.extend([f"{cfg.phone_user}@{cfg.phone_host}:{src}/", f"{dest_sub}/"])

        print(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}")
        result = subprocess.run(cmd)
        rc = rc or result.returncode

    return rc


# ---------- Interactive ----------
def interactive(dry_run: bool, use_session: bool) -> Config:
    session = load_session() if use_session else None
    if session:
        print(f"Found saved session: {SESSION_FILE}")
        if confirm("Load saved session?", default_yes=True):
            return Config.from_dict(session)

    print("=== Photo Backup: Phone -> Computer ===")

    # 1. Mode
    mode_label = prompt_select(
        "1. Backup mode:",
        ["copy (keep files on phone)", "move (delete from phone after transfer)"],
    )
    mode = "move" if mode_label.startswith("move") else "copy"

    # 2. Phone connection
    print("\n--- Phone connection ---")
    phone_host = prompt_required("Phone Tailscale IP/host", DEFAULT_PHONE_HOST)
    phone_user = prompt_required("Phone SSH user", DEFAULT_PHONE_USER)
    phone_port = int(prompt("Phone SSH port", str(DEFAULT_PHONE_PORT)))

    # 3. Source root discovery
    print("\n--- Source root on phone ---")
    if DEFAULT_SOURCE_ROOT and remote_path_exists(phone_host, phone_user, phone_port, DEFAULT_SOURCE_ROOT):
        if confirm(f"Use default source root '{DEFAULT_SOURCE_ROOT}'?", default_yes=True):
            source_root = DEFAULT_SOURCE_ROOT
        else:
            source_root = discover_source_root(phone_host, phone_user, phone_port)
    else:
        source_root = discover_source_root(phone_host, phone_user, phone_port)

    # 4. Folder selection
    print(f"\nReading subfolders of {source_root} via SSH...")
    dirs = list_remote_dirs(phone_host, phone_user, phone_port, source_root)
    if not dirs:
        eprint("No subfolders found. Source root itself will be backed up as a single folder.")
        folders = [""]
        sel_display = "(root)"
    else:
        print(f"Found {len(dirs)} subfolder(s).")
        options = ["[All folders]"] + dirs
        selected = prompt_multi("2. Folders to back up:", options)
        if "[All folders]" in selected:
            folders = ["*"]
            sel_display = "All"
        else:
            folders = [s for s in selected if s != "[All folders]"]
            sel_display = ", ".join(folders)

    # 5. Destination
    print("\n--- Destination ---")
    dest_default = DEFAULT_DEST or str(Path.cwd() / "photganizer-backup")
    dest = prompt("3. Save to where on this computer?", dest_default)

    # 6. Confirm
    print("\n=== Confirmation ===")
    print(f"  Mode       : {mode.upper()}")
    print(f"  Phone      : {phone_user}@{phone_host}:{phone_port}")
    print(f"  Source     : {source_root}")
    print(f"  Folders    : {sel_display}")
    print(f"  Destination: {dest}")
    if mode == "move":
        print("\n  ! MOVE: files will be deleted from phone after transfer!")

    if not dry_run:
        if not confirm("\nProceed?", default_yes=False):
            eprint("aborted")
            sys.exit(130)

    cfg = Config(
        mode=mode, folders=folders, dest=dest,
        phone_host=phone_host, phone_user=phone_user, phone_port=phone_port,
        source_root=source_root,
    )
    if use_session:
        save_session(cfg)
    return cfg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Preview rsync without transferring/deleting.")
    p.add_argument("--from-json", type=str,
                   help="Skip prompts; load config from JSON file.")
    p.add_argument("--save-json", type=str,
                   help="Save chosen config to JSON file (for replay).")
    p.add_argument("--no-session", action="store_true",
                   help="Ignore the auto-loaded session file.")
    args = p.parse_args()

    if args.from_json:
        with open(args.from_json) as f:
            cfg = Config.from_dict(json.load(f))
    else:
        cfg = interactive(dry_run=args.dry_run, use_session=not args.no_session)

    if args.save_json:
        with open(args.save_json, "w") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        print(f"Config saved to {args.save_json}")

    return run_rsync(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
