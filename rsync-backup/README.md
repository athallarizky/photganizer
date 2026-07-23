# rsync-backup

Backup foto dari perangkat remote (HP/Termux/SSH server) ke komputer ini via
**Tailscale SSH + rsync**.

## Arsitektur

```
[Computer]                       [Remote device]
                  Tailscale / LAN
   rsync  ─────────SSH─────────►  sshd:22 (or custom)
   (pull)                          |
                                   v
                                /path/to/photos/
                                    ├── Folder1/
                                    ├── Folder2/
                                    └── ...
```

**Arah**: pull (komputer mengambil dari remote device). Bukan push.

**Kenapa pull?** Karena SSH key yang sudah ter-setup biasanya di arah
komputer → remote. Script ini jalan di komputer, memakai key tersebut,
jadi tidak perlu setup tambahan.

## Prasyarat

1. **SSH server running di remote device** (HP/termux/server), reachable
   via Tailscale atau LAN.
2. **SSH key komputer sudah terdaftar di remote device**
   (`~/.ssh/authorized_keys` di remote).
3. **`rsync` terinstall** di komputer:
   - macOS: sudah pre-installed
   - Linux: `apt install rsync` / `dnf install rsync`
   - Windows (WSL/Git Bash): biasanya sudah
4. **Path sumber di remote device** — perlu tahu folder foto berada dimana.

## Install

```bash
# Tidak ada dependency eksternal, hanya Python 3.10+ stdlib.
git clone <repo-photganizer> ~/photganizer
cd ~/photganizer
```

## Cara Pakai

```bash
# Interactive (default), preview tanpa transfer:
python3 rsync-backup/backup.py --dry-run

# Interactive, eksekusi nyata:
python3 rsync-backup/backup.py

# Non-interactive (replay dari config sebelumnya):
python3 rsync-backup/backup.py --from-json rsync-backup/last-run.json

# Simpan config tanpa run (untuk replay nanti):
python3 rsync-backup/backup.py --save-json rsync-backup/last-run.json
```

## Env Vars (opsional)

| Var | Default | Kegunaan |
|-----|---------|----------|
| `HP_TAILSCALE_HOST` | _(kosong, wajib input)_ | IP/hostname remote |
| `HP_TAILSCALE_USER` | _(kosong, wajib input)_ | SSH user remote |
| `HP_TAILSCALE_PORT` | `22` | Port SSH remote |
| `PHOTO_SOURCE_ROOT` | _(kosong, wajib input)_ | Path sumber di remote |
| `BACKUP_DEST_ROOT` | `<cwd>/photganizer-backup` | Destinasi default |

Contoh (untuk skip prompt env):
```bash
HP_TAILSCALE_HOST=100.x.x.x HP_TAILSCALE_USER=user \
  python3 rsync-backup/backup.py
```

## Prompt yang Muncul (Interactive)

1. **Mode**: `copy` atau `move`
   - `copy` — file tetap di remote (rekomendasi)
   - `move` — hapus dari remote setelah transfer (`--remove-source-files`)
2. **Remote connection**: host, user, port, source root
3. **Pilih folder**: daftar subfolder di source root, multi-select via
   comma-separated numbers
4. **Destination**: path lokal di komputer
5. **Konfirmasi**: review sebelum execute

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

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| `SSH error: Connection refused` | remote sshd mati / unreachable | Cek remote: sshd running, Tailscale connected |
| `SSH error: Permission denied` | SSH key tidak terdaftar di remote | Tambah ke `~/.ssh/authorized_keys` remote |
| `find: ... Permission denied` | Source path tidak readable via SSH | Cek path benar & SSH user punya akses |
| Folder kosong di output | rsync skip karena sudah ada & sama | Tambah `--delete` kalau mau mirror (hati-hati) |

## Tips

- **Test pertama kali** selalu pakai `--dry-run` untuk lihat apa yang akan
  ditransfer.
- **Mode `move` berbahaya** — jika rsync gagal di tengah, file sudah terhapus
  di remote. Pakai `copy` dulu, hapus manual setelah verifikasi.
- **Resume transfer**: rsync otomatis resume via `--partial`. Bisa di-Ctrl+C
  dan re-run aman.
- **Besar transfer**: gunakan `--compress` (-z) sudah default. Untuk file
  JPG/PNG yang sudah compressed, efek minimal.

## Lihat Juga

- [`SKILL.md`](./SKILL.md) — Panduan untuk LLM/Claude memakai script ini.
