# BACKUP.md — Prosedur Backup & Restore (Draft Final)

**Status: DRAFT untuk review user — belum dieksekusi.** Tujuan backup dipilih user 1 Nov 2026: **Google Drive pribadi user**.

## Kenapa backup mandiri itu wajib

- Project Supabase **free tier tidak menyediakan backup harian otomatis** dan dapat di-pause karena inaktivitas (lihat ARCHITECTURE §8 & §11). Hosting bukan pengganti backup.
- Source of truth tetap PostgreSQL; backup adalah salinan logis untuk pemulihan, bukan sumber data operasional.

## Apa yang dibackup

| Item | Termasuk? | Catatan |
|---|---|---|
| Data tabel `expenses` + `expense_categories` | ✅ | Ekspor logis terstruktur (SQL/CSV terkompresi) |
| File migration di `supabase/migrations/` | ✅ | Sudah terversi di Git repo proyek; backup DB tanpa migration tidak lengkap |
| `.env` / kredensial | ❌ **TIDAK PERNAH** | Kredensial tidak boleh ada di Drive backup; pemulihan memakai penyerahan ulang via Secure Vault |
| Foto struk / audio mentah | ❌ | Secara default tidak disimpan sistem (kebijakan privasi spec) |

## Prosedur backup (Phase 1: manual terpicu; Phase 2: otomasi cron)

1. Agent menjalankan skrip backup (`scripts/backup.sh`, dibuat pada Phase 1) dari venv proyek:
   - Ekspor baris kedua tabel lewat repository (HTTPS Data API, filter owner) ke berkas dump lokal di `~/workspace/expense-tracker/backups/` (folder lokal ini hanya staging sementara).
   - Hitung checksum SHA-256 dan catat jumlah baris + rentang tanggal data sebagai manifest.
   - Enkripsi berkas dump sebelum keluar dari workspace (metode & kunci enkripsi disepakati saat implementasi Phase 1; kunci enkripsi **tidak** disimpan di Drive yang sama).
2. Upload berkas terenkripsi ke Google Drive folder **`Expense Tracker Backups/`** pada akun Google pribadi user (koneksi Drive disiapkan di SETUP.md Langkah 4).
3. Verifikasi upload: ukuran + checksum cocok; catat entri di log backup lokal (tanggal, jumlah baris, checksum) — tanpa isi data keuangan.
4. Retensi usulan: simpan 8 backup mingguan terakhir + 6 backup bulanan; penghapusan backup lama hanya dengan persetujuan user (tindakan destruktif).

Frekuensi usulan Phase 1: setiap selesai sesi pencatatan besar atau minimal **1× seminggu** dijalankan manual oleh agent atas perintah user. Otomasi via Hatch cron = Phase 2, perlu persetujuan jadwal terpisah.

## Prosedur restore (drill wajib — TEST_PLAN T30)

1. Buat **project Supabase free sementara** (project uji, bukan project produksi).
2. Terapkan seluruh migration dari Git ke project uji.
3. Impor dump backup terakhir; verifikasi: jumlah baris, total per bulan contoh (fixture laporan), dan checksum manifest cocok.
4. Jalankan subset test integrasi (laporan + RLS) terhadap project uji.
5. Hapus project uji setelah drill selesai dan hasilnya dicatat di laporan verifikasi.

Drill pertama dilakukan sebelum tracker dipakai untuk data asli secara rutin; berikutnya usulan tiap kuartal atau setelah perubahan skema besar.

## Kegagalan & batasan yang harus diingat

- Backup yang belum pernah di-restore = backup yang belum terbukti. Status drill selalu dilaporkan apa adanya.
- Jika koneksi Google Drive terputus, backup berhenti dan dilaporkan gagal — tidak dialihkan diam-diam ke tujuan lain.
- Dump berisi data keuangan pribadi: meski di Drive milik user sendiri, enkripsi sebelum upload adalah syarat, bukan opsi.
