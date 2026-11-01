#!/usr/bin/env bash
# check_env.sh — verifikasi lingkungan Expense Tracker (READ-ONLY, DRAFT — belum dijalankan)
# Tidak mengubah apa pun: hanya memeriksa prasyarat Phase 0/1 dan melaporkannya.
set -u

PROJECT_DIR="$HOME/workspace/expense-tracker"
FAIL=0

note()  { printf '%s\n' "$*"; }
ok()    { printf '  [OK]   %s\n' "$*"; }
warn()  { printf '  [WARN] %s\n' "$*"; }
bad()   { printf '  [FAIL] %s\n' "$*"; FAIL=1; }

note "== Expense Tracker: environment check (read-only) =="

# 1. Wilayah persisten: proyek WAJIB di bawah $HOME/workspace
case "$PROJECT_DIR" in
  "$HOME"/workspace/*) ok "Project dir di wilayah persisten: $PROJECT_DIR" ;;
  *) bad "Project dir di luar wilayah persisten: $PROJECT_DIR" ;;
esac
[ -d "$PROJECT_DIR" ] && ok "Folder proyek ada" || bad "Folder proyek belum ada: $PROJECT_DIR"

# 2. Toolchain dasar
command -v python3 >/dev/null && ok "python3: $(python3 --version 2>&1)" || bad "python3 tidak ditemukan"
command -v git >/dev/null && ok "git tersedia" || warn "git tidak ditemukan (repo belum bisa diinisialisasi)"

# 3. Docker memang TIDAK diharapkan ada di runtime Muse ini (desain tanpa Docker)
command -v docker >/dev/null && warn "docker ditemukan (tidak dipakai oleh desain MVP)" || note "  [INFO] docker tidak ada — sesuai desain MVP (tanpa Docker/local Supabase stack)"

# 4. Venv proyek & ASR existing
[ -d "$PROJECT_DIR/.venv" ] && ok "Venv proyek ada (.venv)" || warn "Venv proyek belum dibuat (dibuat setup.sh pada Phase 0)"
[ -x "$HOME/workspace/.asr-venv/bin/python" ] && ok "ASR existing ditemukan: ~/workspace/.asr-venv (faster-whisper, reuse)" || warn "ASR existing tidak ditemukan — verifikasi ulang sebelum Phase 1"

# 5. Berkas konfigurasi: laporkan keberadaan TANPA membaca isinya
if [ -f "$PROJECT_DIR/.env" ]; then ok ".env ada (isi tidak dibaca skrip ini)"; else warn ".env belum ada — normal sebelum provisioning (SETUP.md Langkah 3)"; fi
[ -f "$PROJECT_DIR/.env.example" ] && ok ".env.example ada" || warn ".env.example belum ada"

# 6. Ruang disk persisten
AVAIL=$(df -h "$HOME" | awk 'NR==2 {print $4}')
note "  [INFO] Ruang kosong di volume persisten: $AVAIL"

# 7. Konektivitas egress dasar (HTTPS) — tanpa kredensial apa pun
if command -v curl >/dev/null; then
  if curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://supabase.com | grep -q '200\|301\|302'; then
    ok "Egress HTTPS ke supabase.com terjangkau"
  else
    warn "Egress HTTPS ke supabase.com tidak terkonfirmasi saat ini"
  fi
fi

note "== Selesai. FAIL=$FAIL (0 = prasyarat dasar terpenuhi; WARN bersifat informasional) =="
exit $FAIL
