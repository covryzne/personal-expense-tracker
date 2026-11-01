# SETUP.md — Panduan Instalasi Expense Tracker (Draft Final)

**Status: DRAFT untuk review user — belum ada langkah yang dieksekusi.**
Prinsip keselamatan: tidak ada file konfigurasi/rahasia yang ditimpa. Semua aset di wilayah persisten `~/workspace/expense-tracker/`. Kredensial **tidak pernah** dikirim lewat chat.

---

## Ringkasan siapa mengerjakan apa

| Langkah | Dikerjakan oleh | Kenapa |
|---|---|---|
| 1. Buat akun + project Supabase | **User (manual, ±5 menit)** | Akun & kepemilikan project harus atas nama user; agent tidak membuat akun pihak ketiga |
| 2. Buat Auth user owner | User, dipandu langkah di dokumen ini | Email pribadi user; password dibuat user sendiri |
| 3. Serahkan API keys | User lewat **Secure Vault Muse** (kartu aman), dipandu agent | Nilai kunci tidak melewati chat dan tidak dibaca agent |
| 4. Hubungkan Google Drive (backup) | User tap link connect resmi, agent memandu | Otorisasi akun Google adalah tindakan user |
| 5. Venv, dependencies, `.env` dari template | Agent (setelah langkah 1–3) | Pekerjaan teknis di workspace |
| 6. Migration schema + RLS + RPC | Agent menulis file SQL; **apply menunggu persetujuan eksplisit user** | Mengubah database = tindakan konsekuensial |
| 7. Verifikasi & smoke test | Agent + user (kirim pesan uji di WhatsApp) | Pembuktian end-to-end |

---

## Langkah 1 — Buat project Supabase (manual oleh user)

1. Buka https://supabase.com → **Start your project** → daftar/masuk (boleh pakai GitHub atau email pribadi).
2. **New project** dengan isian yang disarankan:
   - **Name:** `personal-expense-tracker` (bebas, sarankan ini agar mudah dikenali)
   - **Database password:** buat password kuat dan simpan di password manager. Password ini *bukan* untuk agent di MVP (koneksi memakai HTTPS Data API), tetapi wajib disimpan user untuk keadaan darurat/masa depan.
   - **Region:** `Singapore (ap-southeast-1)` — paling dekat ke Indonesia.
   - **Plan:** Free.
3. Tunggu provisioning selesai (±2 menit) sampai dashboard project terbuka.
4. Catat (untuk diri sendiri dulu, jangan kirim ke chat):
   - **Project URL**: Settings → API → `Project URL` (bentuk `https://<ref>.supabase.co`). URL ini bukan rahasia tingkat tinggi, tapi tetap serahkan bersama kunci lewat jalur aman di Langkah 3.
   - **Project ref**: bagian `<ref>` dari URL.

> Keputusan anti-overengineering (disepakati 1 Nov 2026): **satu project saja**. Tidak ada project staging terpisah. Pengujian memakai Auth user kedua khusus test + data fixture yang dibersihkan setelahnya (lihat Langkah 6 dan TEST_PLAN). Drill migration-dari-nol/restore (T30) memakai project free sementara yang dibuat saat pengujian lalu dihapus.

## Langkah 2 — Buat Auth user owner (identitas permanen)

1. Di dashboard project: **Authentication → Users → Add user → Create new user**.
2. Email: **email pribadi user** (Gmail utama yang sama dengan akun Muse: `<owner-email>`).
3. Password: buat yang kuat, simpan di password manager. (Login ini kelak dipakai juga untuk dashboard Next.js Phase 3.)
4. Setelah user dibuat, catat **UUID** user tersebut (kolom `User UID`) — ini yang menjadi `FINANCE_OWNER_USER_ID`. UUID bukan kredensial rahasia, tapi tetap serahkan lewat jalur aman sekalian agar tidak tercecer.
5. Opsional untuk test RLS (T22): buat user kedua `+test` (mis. `<owner-email-plus-test>`) sebagai "user B" penguji. User ini tidak pernah diberi data asli.

## Langkah 3 — Serahkan kredensial TANPA lewat chat (Secure Vault)

Yang dibutuhkan sistem (lihat `.env.example` untuk daftar lengkap):

| Nilai | Diambil dari | Tingkat sensitivitas |
|---|---|---|
| `SUPABASE_URL` | Settings → API | Rendah |
| `SUPABASE_PUBLISHABLE_KEY` | Settings → API (publishable `sb_publishable_...`) | Rendah–sedang (aman untuk browser, tetap jangan disebar) |
| `SUPABASE_SECRET_KEY` | Settings → API (secret `sb_secret_...`) | **SANGAT TINGGI** — melewati RLS; setara akses penuh database |
| `FINANCE_OWNER_USER_ID` | Authentication → Users (UUID Langkah 2) | Rendah |

Mekanisme penyerahan yang akan dipandu agent saat eksekusi:

1. Agent membuka **kartu Secure Vault** di chat ini (formulir aman Muse). User mengetik/menempel nilai **di halaman aman tersebut** — nilai masuk ke brankas terenkripsi Muse, **tidak tampil di percakapan, tidak dibaca agent sebagai teks**.
2. Agent kemudian menyiapkan akses API Supabase sebagai *custom connector* berbasis kredensial vault tersebut (mengikuti skill `custom_connector_setup`), dan memverifikasi koneksi dengan satu panggilan baca yang aman.
3. **Hasil verifikasi Phase 0 (1 Nov 2026, parsial):** mekanisme vault **terbukti** — kredensial tersimpan di koneksi terdaftar `custom.supabase` dan helper Python memanggil API lewat surrogate (`dynamic_credentials.py`); kunci asli tidak pernah menjadi file/env/teks yang dibaca agent. Satu koreksi terbukti dari uji pertama: gateway Supabase membaca kunci dari header `apikey`, bukan `Authorization: Bearer` — registrasi awal (`bearer_header`) ditolak HTTP 401 "No API key found in request", dan reconnect dengan placement `custom_header:apikey` sudah diterbitkan untuk diisi ulang user dengan kunci yang sama. Verifikasi penerimaan final (probe `GET /auth/v1/users` + kecocokan UUID owner) menunggu pengisian ulang tersebut. Detail operasional dicatat di `~/workspace/custom-connectors/custom.supabase/CONNECTOR.md`.
4. Yang tidak akan pernah dilakukan: meminta kunci di chat, menulis kunci ke file yang dibuat dari teks chat, mencetak kunci ke log, atau menyimpannya di repo Git.

## Langkah 4 — Hubungkan Google Drive untuk backup

1. Agent membagikan link resmi **Connect Google Drive** dari connector Muse.
2. User tap link → masuk akun Google pribadi → setujui akses.
3. Agent verifikasi status `connected`, lalu membuat folder tujuan backup: `Expense Tracker Backups/` (dibuat saat fase backup, bukan sekarang).
4. Detail prosedur ada di `docs/BACKUP.md`. Ringkasnya: dump logis terenkripsi → upload ke folder tersebut → restore drill berkala di project uji sementara.

## Langkah 5 — Bootstrap lingkungan lokal (agent, via script draft)

Prasyarat: Langkah 1–3 selesai. Agent menjalankan (setelah user menyetujui draft script-nya):

```bash
bash ~/workspace/expense-tracker/scripts/check_env.sh   # verifikasi read-only
bash ~/workspace/expense-tracker/scripts/setup.sh       # buat venv + install deps + siapkan .env dari template
```

`setup.sh` bersifat idempotent dan aman: membuat `.venv` bila belum ada, memasang `pydantic`, `supabase`, `pytest`, `httpx` ke venv proyek, menyalin `.env.example` → `.env` **hanya bila `.env` belum ada**, dan berhenti dengan pesan jelas bila menemukan file existing (tidak menimpa).

## Langkah 6 — Migration & verifikasi (agent, dengan gerbang persetujuan)

1. Agent menulis migration berversi di `supabase/migrations/` (`0001_schema.sql`, `0002_rls_grants.sql`, `0003_report_rpc.sql`) sesuai `docs/DATA_MODEL.md`.
2. User mereview ringkasan migration → **persetujuan eksplisit** → agent menerapkan (jalur apply diverifikasi di Phase 0: Supabase CLI binary atau SQL Editor dashboard).
3. Agent menjalankan test suite (unit + integrasi memakai user test & fixture TEST_PLAN, data uji dibersihkan sesudahnya).
4. Smoke test live opt-in: user mengirim 1 teks, 1 voice note, 1 foto struk di chat WhatsApp ini → konfirmasi berisi ID persisten → laporan "hari ini" cocok.
5. Baru setelah itu tracker dinyatakan live untuk data asli.

## Checklist keputusan yang sudah dikunci (1 Nov 2026)

- [x] Supabase: belum ada project — user membuat manual, agent memandu.
- [x] Owner: email pribadi user (`<owner-email>`); UUID-nya = `FINANCE_OWNER_USER_ID`.
- [x] Anti-overengineering: satu project, tanpa staging permanen, tanpa FastAPI/n8n/dashboard di MVP.
- [x] Backup off-platform: Google Drive, agent membantu setup koneksinya.
- [x] Kredensial: lewat Secure Vault dengan panduan agent; tidak lewat chat.
- [ ] Batas maksimum range laporan custom (usulan default 366 hari) — konfirmasi saat Phase 1.
- [ ] Format konfirmasi WhatsApp (TOOL_CONTRACT §10) — konfirmasi saat Phase 1.
