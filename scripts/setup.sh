#!/usr/bin/env bash
# setup.sh — bootstrap lingkungan Expense Tracker (DRAFT — belum dijalankan)
#
# ATURAN KESELAMATAN (sesuai instruksi owner):
# - Idempotent: aman dijalankan berulang; langkah yang sudah ada dilewati, bukan ditimpa.
# - TIDAK PERNAH menimpa file konfigurasi/rahasia yang sudah ada (.env hanya dibuat bila belum ada).
# - Semua aset di wilayah persisten ($HOME/workspace/...). Skrip menolak berjalan di luar itu.
# - Skrip ini TIDAK menangani kredensial asli: .env dibuat dari .env.example ber-placeholder.
#   Nilai asli diserahkan lewat Secure Vault (docs/SETUP.md Langkah 3), bukan lewat skrip/chat.
# - Tidak menyentuh Supabase sama sekali (tidak ada migration/apply di skrip ini).
set -euo pipefail

PROJECT_DIR="$HOME/workspace/expense-tracker"
VENV_DIR="$PROJECT_DIR/.venv"
PACKAGES=("pydantic" "supabase" "pytest" "httpx")

# --- Guard: wilayah persisten -------------------------------------------------
case "$PROJECT_DIR" in
  "$HOME"/workspace/*) : ;;
  *) echo "ERROR: PROJECT_DIR di luar wilayah persisten: $PROJECT_DIR" >&2; exit 1 ;;
esac

echo "== Expense Tracker setup (idempotent) =="
mkdir -p "$PROJECT_DIR" "$PROJECT_DIR/backups" "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"

# --- Python venv ---------------------------------------------------------------
if [ -d "$VENV_DIR" ]; then
  echo "[skip] Venv sudah ada: $VENV_DIR (tidak ditimpa)"
else
  echo "[make] Membuat venv: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# --- Dependencies ---------------------------------------------------------------
echo "[deps] Memastikan paket Python terpasang di venv: ${PACKAGES[*]}"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet "${PACKAGES[@]}"

# --- .env dari template (HANYA bila belum ada) -----------------------------------
if [ -f "$PROJECT_DIR/.env" ]; then
  echo "[skip] .env sudah ada — TIDAK ditimpa. Isi tetap tanggung jawab provisioning aman."
else
  if [ -f "$PROJECT_DIR/.env.example" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"
    echo "[make] .env dibuat dari .env.example (masih PLACEHOLDER — isi lewat jalur Secure Vault, lihat docs/SETUP.md)"
  else
    echo "ERROR: .env.example tidak ditemukan; tidak membuat .env." >&2; exit 1
  fi
fi

# --- .gitignore perlindungan rahasia ----------------------------------------------
if [ -f "$PROJECT_DIR/.gitignore" ]; then
  echo "[skip] .gitignore sudah ada (tidak ditimpa)"
else
  printf '%s\n' '.env' '.venv/' 'backups/' 'logs/' '__pycache__/' '*.pyc' > "$PROJECT_DIR/.gitignore"
  echo "[make] .gitignore dibuat (.env, .venv, backups, logs terproteksi)"
fi

# --- Git repo (inisialisasi hanya bila belum ada) ----------------------------------
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "[skip] Repo git sudah ada (tidak diubah)"
else
  git init --quiet "$PROJECT_DIR"
  echo "[make] Repo git diinisialisasi (belum ada commit yang dibuat skrip ini)"
fi

echo "== Setup dasar selesai. Langkah berikutnya BUKAN bagian skrip ini: =="
echo "   1) Provisioning Supabase oleh owner (docs/SETUP.md Langkah 1-2)"
echo "   2) Penyerahan kredensial via Secure Vault (docs/SETUP.md Langkah 3)"
echo "   3) Migration ditulis & di-apply hanya dengan persetujuan eksplisit owner"
