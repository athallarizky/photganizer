#!/usr/bin/env python3
"""Backup foto dari HP (Termux) ke komputer ini via Tailscale SSH + rsync.

Dirun DI KOMPUTER (bukan HP). Memakai SSH key yang sudah terdaftar
di authorized_keys HP (komputer -> HP).

Interactive prompts:
  1. Mode: copy atau move
  2. Folder/galeri mana yang di-backup (multi-select, auto-discover via SSH)
  3. Destination path di komputer ini

Setelah konfirmasi, jalankan rsync per folder terpilih.

Cara pakai:
    python3 backup.py              # interactive
    python3 backup.py --dry-run    # preview tanpa transfer
    python3 backup.py --from-json config.json   # non-interactive
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

# ---------- Config (env-overridable, no hardcoded personal defaults) ----------
DEFAULT_HP_HOST = os.environ.get("HP_TAILSCALE_HOST", "")
DEFAULT_HP_USER = os.environ.get("HP_TAILSCALE_USER", "")
DEFAULT_HP_PORT = int(os.environ.get("HP_TAILSCALE_PORT", "22"))
DEFAULT_SOURCE_ROOT = os.environ.get("PHOTO_SOURCE_ROOT", "")
DEFAULT_DEST = os.environ.get("BACKUP_DEST_ROOT", "")


def eprint(*a: Any, **k: Any) -> None:
    print(*a, file=sys.stderr, **k)


@dataclass
class Config:
    mode: str                       # "copy" atau "move"
    folders: list[str]              # nama folder, atau ["*"] untuk semua
    dest: str                       # path lokal di komputer
    hp_host: str
    hp_user: str
    hp_port: int
    source_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "folders": self.folders,
            "dest": self.dest,
            "hp_host": self.hp_host,
            "hp_user": self.hp_user,
            "hp_port": self.hp_port,
            "source_root": self.source_root,
        }


# ---------- Prompts ----------
def prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{msg}{suffix}: ").strip()
    return val or default


def prompt_required(msg: str, default: str = "") -> str:
    """Prompt yang tidak boleh kosong."""
    while True:
        val = prompt(msg, default)
        if val:
            return val
        eprint("  tidak boleh kosong")


def prompt_select(msg: str, options: list[str]) -> str:
    print(f"\n{msg}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        choice = input(f"Pilih 1-{len(options)}: ").strip()
        try:
            return options[int(choice) - 1]
        except (ValueError, IndexError):
            eprint("  invalid")


def prompt_multi(msg: str, options: list[str]) -> list[str]:
    """Multi-select via comma-separated numbers. 0 = semua."""
    print(f"\n{msg}")
    print("  Ketik nomor dipisah koma (mis: 1,3,5). '0' = semua.")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        choice = input("Pilih: ").strip()
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


# ---------- SSH ----------
def ssh_quiet(host: str, user: str, port: int, cmd: str) -> tuple[int, str, str]:
    args = ["ssh", "-p", str(port), f"{user}@{host}", cmd]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def list_remote_dirs(host: str, user: str, port: int, path: str) -> list[str]:
    """List subdirectory names at remote path (one level deep)."""
    cmd = f"find {shlex.quote(path)} -maxdepth 1 -mindepth 1 -type d 2>/dev/null"
    code, out, err = ssh_quiet(host, user, port, cmd)
    if code != 0:
        eprint(f"SSH error: {err.strip()}")
        eprint(f"  Cek: HP online di Tailscale? IP/user/port benar?")
        sys.exit(2)
    names = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            names.append(os.path.basename(line))
    return sorted(names)


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
            "rsync",
            "-avz",
            "--partial",
            "--human-readable",
            "--progress",
            "-e", f"ssh -p {cfg.hp_port}",
        ]
        if cfg.mode == "move":
            cmd.append("--remove-source-files")
        if dry_run:
            cmd.append("--dry-run")
        cmd.extend([f"{cfg.hp_user}@{cfg.hp_host}:{src}/", f"{dest_sub}/"])

        print(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}")
        result = subprocess.run(cmd)
        rc = rc or result.returncode

    return rc


# ---------- Interactive ----------
def interactive(dry_run: bool) -> Config:
    print("=== Photo Backup: HP -> Computer ===")

    # 1. Mode
    mode_label = prompt_select(
        "1. Mode backup:",
        ["copy (file tetap di HP)", "move (hapus dari HP setelah transfer)"],
    )
    mode = "move" if mode_label.startswith("move") else "copy"

    # 2. HP connection
    print("\n--- HP Connection ---")
    hp_host = prompt_required("HP Tailscale IP/host", DEFAULT_HP_HOST)
    hp_user = prompt_required("HP SSH user", DEFAULT_HP_USER)
    hp_port = int(prompt("HP SSH port", str(DEFAULT_HP_PORT)))
    source_root = prompt_required("Source root di HP", DEFAULT_SOURCE_ROOT)

    print(f"\nMembaca daftar folder di {source_root} via SSH...")
    dirs = list_remote_dirs(hp_host, hp_user, hp_port, source_root)
    if not dirs:
        eprint("Tidak ada subfolder di source root. Cek path.")
        sys.exit(2)
    print(f"Ditemukan {len(dirs)} folder.")

    options = ["[Semua folder]"] + dirs
    selected = prompt_multi("2. Folder yang di-backup:", options)
    if "[Semua folder]" in selected:
        folders = ["*"]
        sel_display = "Semua"
    else:
        folders = [s for s in selected if s != "[Semua folder]"]
        sel_display = ", ".join(folders)

    # 3. Destination
    print("\n--- Destination ---")
    dest_default = DEFAULT_DEST or str(Path.cwd() / "photganizer-backup")
    dest = prompt("3. Simpan ke mana di komputer ini?", dest_default)

    # Confirm
    print("\n=== Konfirmasi ===")
    print(f"  Mode       : {mode.upper()}")
    print(f"  HP         : {hp_user}@{hp_host}:{hp_port}")
    print(f"  Source     : {source_root}")
    print(f"  Folder     : {sel_display}")
    print(f"  Destination: {dest}")
    if mode == "move":
        print("\n  ! MOVE: file akan dihapus dari HP setelah transfer!")

    if not dry_run:
        confirm = input("\nLanjut? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            eprint("aborted")
            sys.exit(130)

    return Config(
        mode=mode, folders=folders, dest=dest,
        hp_host=hp_host, hp_user=hp_user, hp_port=hp_port,
        source_root=source_root,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Preview rsync tanpa transfer/hapus.")
    p.add_argument("--from-json", type=str,
                   help="Skip prompt, load config dari file JSON.")
    p.add_argument("--save-json", type=str,
                   help="Simpan config yang dipilih ke file JSON (untuk replay).")
    args = p.parse_args()

    if args.from_json:
        with open(args.from_json) as f:
            cfg = Config(**json.load(f))
    else:
        cfg = interactive(dry_run=args.dry_run)

    if args.save_json:
        with open(args.save_json, "w") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        print(f"Config disimpan ke {args.save_json}")

    return run_rsync(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
