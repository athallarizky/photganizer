---
name: photganizer-rsync-backup
description: Backup photos dari remote device (HP/Termux/SSH server) ke komputer via Tailscale SSH + rsync. Pakai saat user ingin pindahkan foto/gambar dari remote ke komputer mereka, atau minta "backup HP", "tarik foto dari HP", "sinkronisasi galeri".
---

# SKILL: rsync-backup

Panduan untuk LLM/Claude saat user meminta backup foto remote → komputer.

## Kapan Dipakai

Trigger user (contoh):
- "backup foto HP saya"
- "pindahkan gambar dari HP ke komputer"
- "tarik folder X dari HP"
- "sinkron galeri HP ke sini"

## Cara Invoke

Script ini jalan di **komputer** (sisi user yang sekarang), bukan di remote.

```bash
# Selalu mulai dengan dry-run untuk preview:
python3 <path-ke-photganizer>/rsync-backup/backup.py --dry-run

# Setelah user konfirmasi, jalankan tanpa --dry-run:
python3 <path-ke-photganizer>/rsync-backup/backup.py
```

## Yang Harus Divalidasi ke User

Script akan prompt secara interactive. Anda bisa bantu user menjawab, atau
jalankan dengan `--from-json` kalau user sudah tahu maunya apa.

### 1. Mode: copy atau move?

- **`copy`** (recommended default) — file tetap di remote, hanya diduplikat
  ke komputer.
- **`move`** — hapus dari remote setelah transfer. Berbahaya kalau transfer
  gagal.

**Selalu rekomendasikan `copy`** kecuali user eksplisit minta move.

### 2. Remote connection (wajib diisi user)

Script butuh:
- **Host** (IP Tailscale / hostname)
- **SSH user**
- **SSH port** (default 22, atau 8022 untuk Termux)
- **Source root path** di remote

**Tidak ada default** untuk host/user/path — user wajib input. Jangan
menebak atau hallucinate IP.

### 3. Folder mana yang di-backup?

Script akan SSH ke remote dan list subfolder di source root. User akan
lihat daftar seperti:

```
  1. [Semua folder]
  2. Threads
  3. Instander
  4. Facebook
  ...
```

Pilihan:
- `0` = semua folder (mirror penuh)
- `1,3,5` = beberapa folder saja

### 4. Destination path

Default: `<cwd>/photganizer-backup`. User bisa override ke path lain.

**Validasi**: pastikan disk punya ruang cukup. Cek dengan `df -h <dest>`.

## Konfirmasi Sebelum Execute

Script akan print summary:

```
=== Konfirmasi ===
  Mode       : COPY
  Remote     : user@<host>:<port>
  Source     : <source_root>
  Folder     : Threads, Facebook
  Destination: /home/user/photganizer-backup
```

**Selalu tunjukkan ini ke user dan minta konfirmasi eksplisit** sebelum
tekan `y`.

## Common Pitfalls

1. **Salah arah**: script PULL (komputer mengambil dari remote). Bukan push.
2. **SSH key salah arah**: butuh key **komputer → remote** (sudah default
   tersetup kalau user sudah bisa SSH ke remote).
3. **Path source remote**: pakai absolute path yang valid di sisi remote.
   Untuk Termux/Android: `/sdcard/...` atau `/storage/emulated/0/...`.
4. **Move = destruktif**: selalu preview dulu dengan `--dry-run` sebelum move.

## Error Handling

| Pesan error | Arti | Solusi |
|-------------|------|--------|
| `Connection refused` | remote sshd mati / unreachable | Cek remote, pastikan sshd running |
| `Permission denied (publickey)` | Key komputer tidak terdaftar di remote | Tambah ke `~/.ssh/authorized_keys` remote |
| `No such file or directory` di source | Path remote salah | Verifikasi dengan `ssh user@host ls /path` |

## Setelah Backup Selesai

User mungkin ingin:
- **Organize**: jalankan `screenshot-organizer/organize_screenshots.py` di
  komputer untuk kategorikan hasil backup.
- **Verify**: bandingkan count file source vs dest.
- **Hapus source** (kalau mode copy): manual setelah verify.

## Contoh Sesi LLM-Driven

```
User: "tolong backup foto Threads dan Facebook dari HP ke /mnt/external/photos"

Anda:
1. Cek rsync & SSH reachable: `ssh <user>@<host> ls /path/to/photos/`
2. Preview: `python3 rsync-backup/backup.py --dry-run`
   - Saat prompt host/user/port: isi dari jawaban user
   - Saat prompt folder: masukkan nomor Threads + Facebook
   - Saat prompt dest: /mnt/external/photos
3. Tunjukkan summary ke user, minta konfirmasi
4. Run actual: `python3 rsync-backup/backup.py --from-json last-run.json`
5. Verify count di dest
```

## Non-Interactive Mode (LLM Friendly)

Kalau Anda sudah tahu semua jawaban (misal dari sesi sebelumnya), skip prompt:

```bash
# Buat config JSON dulu
cat > backup-config.json <<EOF
{
  "mode": "copy",
  "folders": ["Threads", "Facebook"],
  "dest": "/mnt/external/photos",
  "hp_host": "<user-provided-ip>",
  "hp_user": "<user>",
  "hp_port": 22,
  "source_root": "/path/on/remote"
}
EOF

# Run non-interactive
python3 rsync-backup/backup.py --from-json backup-config.json
```

Cocok untuk:
- Cron jobs
- Repeated runs
- Automation

## Catatan Keamanan

- **Jangan hardcode IP/user di script atau config yang di-commit ke git.**
- **Jangan share IP Tailscale spesifik user secara publik.**
- Untuk automation, pakai environment variables (lihat README) atau file
  config yang sudah di-`.gitignore`.
