# Implementation Plan — Personal Expense Tracker MVP

**WhatsApp + Muse + Supabase PostgreSQL** | Status: PLAN ONLY — belum ada kode, belum ada file konfigurasi yang dibuat/diubah
Disusun: 1 Nov 2026 | Berdasarkan spec pack rev 1.0 (README, PRD, ARCHITECTURE, DATA_MODEL, TOOL_CONTRACT, TEST_PLAN, DASHBOARD_ROADMAP, AGENTS, HANDOFF_PROMPT) di `~/workspace/user/files/`
Lokasi proyek (target, semua di wilayah persisten): `~/workspace/expense-tracker/`

---

## 0. Ringkasan keputusan scope

- **MVP sekarang (Phase 0–1):** Expense tracker percakapan. Input teks / voice note / foto struk via chat WhatsApp Muse yang sudah terhubung → ekstraksi terstruktur → validasi Pydantic → tool layer Python terbatas → Supabase PostgreSQL → konfirmasi WhatsApp hanya setelah commit terverifikasi. Termasuk: multi-expense per pesan, koreksi, soft-delete/restore, laporan harian/mingguan (Senin–Minggu)/bulanan/custom per kategori, idempotency, RLS, logging terstruktur, prosedur backup.
- **Bukan sekarang:** Dashboard Next.js (Phase 3, hanya forward-compat di skema), FastAPI, n8n, income/balance, budget, recurring automation, simpan foto/audio mentah, multi-user, sinkronisasi bank.
- **Di luar scope spec ini:** Modul agregat review Dicoding — README secara eksplisit menaruhnya di daftar "not now". Agregasi review tetap layanan on-demand dari Gmail seperti keputusan 1 Nov 2026, kecuali user memutuskan modul terpisah nanti.

## 1. Analisis kondisi workspace (terverifikasi 1 Nov 2026)

| Aspek | Temuan | Bukti |
|---|---|---|
| Lokasi persisten | Hanya `/home/hatch` (termasuk `~/workspace`, btrfs 150 GB, terpakai ~1%) yang persisten. Root overlay, `/tmp`, `/run` volatile | Audit runtime 1 Nov 2026 |
| Toolchain | Python 3.12.3, Node 24.22.1, git, curl, jq tersedia. **Tidak ada Docker, tidak ada supabase CLI, tidak ada psql** | `python3 --version`, `which` |
| Python packages | `pydantic`, `supabase`, `psycopg`, `pytest`, `httpx` **belum terpasang** di Python sistem → wajib venv khusus proyek di `~/workspace/expense-tracker/.venv` (pola sama dengan `.asr-venv` yang terbukti jalan) | `importlib.util.find_spec` |
| Repo proyek | Belum ada folder proyek, `.env`, migration, atau file expense-tracker apa pun di workspace | `find` di `~/workspace` (hasil kosong) |
| Custom connectors/skills | Folder `~/workspace/custom-connectors/` dan `~/workspace/custom-skills/` kosong; **tidak ada connector Supabase/PostgreSQL bawaan** | `muse.connector_search` + `ls` |
| Internet egress | Berfungsi (pip install, web). IP egress = pool IPv6 bersama, **tidak ada port listening / IP publik inbound** | Audit jaringan 1 Nov 2026 |
| Scheduling | Tidak ada user systemd/crontab/at. Yang didukung: **Hatch cron** (agent terjadwal) — sudah terbukti jalan untuk workflow lain | Audit + cron Dicoding yang pernah aktif |
| Konfigurasi/rahasia existing | Tidak ditemukan `.env*` terkait proyek ini → tidak ada yang berisiko tertimpa; file rahasia akan **dibuat baru hanya setelah provisioning disetujui**, tidak pernah ditulis dari chat | `find` (hasil kosong) |

## 2. Integrasi Muse: terverifikasi vs belum terverifikasi

### 2.1 Terverifikasi (ada bukti langsung)

| Kapabilitas | Status | Bukti / catatan |
|---|---|---|
| Kanal WhatsApp | ✅ Terhubung, chat side-chat khusus owner | Percakapan ini sendiri; status linked (dicek 1 Nov) |
| Lampiran masuk | ✅ Teks, voice note (`.ogg`/Opus), gambar, dokumen diterima; file media tersimpan ke workspace dan bisa diakses agent | Voice note + foto struk Nescafe diterima & diproses 1 Nov 2026 |
| Vision/OCR struk | ✅ Agent membaca foto struk secara native dan mengekstrak total/tunai/kembalian dengan benar (Rp12.000 / Rp100.000 / Rp88.000 — persis fixture E1/T04 di TEST_PLAN) | Transkrip struk Nescafe 1 Nov 2026 |
| ASR voice note | ✅ **Reuse, bukan install ulang**: venv `~/workspace/.asr-venv` berisi faster-whisper (PyAV di-pin 12.3.0) + model base & small; model `small` memberi transkrip Bahasa Indonesia akurat ("gue mau ngetes nih, pake voice, bisa gak?") | Uji langsung 1 Nov 2026 |
| Eksekusi tool oleh agent | ✅ Agent menjalankan Python/CLI di workspace via terminal pada setiap turn chat dan pada Hatch cron. **Inilah mekanisme "tool calling" yang nyata di runtime ini** | Seluruh sesi ini |
| Timestamp pesan | ✅ Setiap pesan user membawa tag waktu Asia/Jakarta dari runtime (dasar `sent_at` & interpretasi "kemarin/tadi") | Tag waktu pada pesan-pesan sesi ini |
| Identitas chat | ✅ Chat terikat chat_id tetap `<whatsapp-chat-id>` untuk side-chat WhatsApp ini | Metadata sesi |

### 2.2 Belum terverifikasi / tidak tersedia (jangan diasumsikan)

| Item | Status | Dampak & mitigasi di plan |
|---|---|---|
| SDK/plugin "Muse tool registration" formal | ❌ Tidak ditemukan dokumentasi/API-nya di workspace maupun docs Muse. Tidak ada cara mendaftarkan function-calling schema ke runtime selain agent menjalankan CLI/service lewat terminal, atau custom connector (MCP/API eksternal) | Adapter MVP = **agent-orchestrated CLI**: agent memanggil CLI Python proyek dengan envelope JSON. Custom connector Supabase MCP resmi = opsi evaluasi terpisah, **bukan** MVP (berisiko mengekspos SQL bebas, melanggar TOOL_CONTRACT) |
| Envelope WhatsApp terprogram (sender_id, message_id, sent_at sebagai API untuk kode standalone) | ⚠️ Agent melihat konteks pesan saat turn berjalan, tetapi **tidak ada event/webhook yang bisa di-subscribe kode Python** (tidak ada inbound network, tidak ada daemon yang dijamin hidup). Redelivery/retry semantics WhatsApp bridge tidak terdokumentasi | Kode Python tidak pernah "mendengarkan" WhatsApp sendiri; envelope dibangun agent dari konteks runtime per turn. `message_id` memakai ID pesan runtime bila tersedia; bila tidak stabil, fallback deteksi probable-duplicate (pola T08: peringatkan, jangan suppress diam-diam) |
| Allowlist `sender_id` level provider | ⚠️ Berbeda dari asumsi spec: side-chat ini terikat ke akun WhatsApp owner yang ter-pairing — pihak lain memang tidak bisa mengirim ke chat 1:1 ini. Tetapi tidak ada `sender_id` provider yang bisa dicek kode | Kontrol diadaptasi: service memvalidasi `chat_id` == chat WhatsApp terdaftar + mapping owner dari config server-side (bukan dari isi chat). Dicatat sebagai **adaptasi kontrol**, diuji ulang bila envelope API resmi tersedia (gate Phase 0) |
| Supabase project & Auth user | ❌ Belum ada (tidak ditemukan kredensial/project di workspace) | **Blocker Phase 0** — perlu keputusan & provisioning oleh user (lihat §9). Kredensial lewat Secure Vault/connect flow, **tidak pernah lewat chat** |
| Supabase CLI untuk migration | ❌ Belum terpasang; tidak ada Docker untuk `supabase start` lokal | Migration ditulis sebagai file SQL berversi; penerapan via (a) unduh binary CLI resmi ke workspace — perlu diverifikasi saat Phase 0, atau (b) SQL Editor dashboard oleh user/dengan persetujuan eksplisit. Test integrasi memakai **project Supabase staging terpisah**, bukan local stack |
| Konektivitas Postgres langsung (port 5432/pooler) dari VM | ❌ Belum diuji (egress IPv6 pool; direct connection Supabase sensitif IPv4/IPv6) | Default sesuai ARCHITECTURE §4: **Supabase Python client via HTTPS Data API** — tidak butuh port DB. SQL agregat laporan lewat **RPC PostgreSQL statis** (lihat §5.3) |
| Auto-transkrip voice note bawaan runtime | ⚠️ Ada, tapi kualitas Bahasa Indonesia buruk pada uji 1 Nov (terdeteksi sebagai bahasa Jepang) | ASR of record = faster-whisper lokal yang sudah ada; transkrip runtime hanya fallback |
| Tujuan backup off-platform | ❌ Belum dipilih | Keputusan user di §9 (mis. Google Drive — saat ini juga belum terhubung) |

## 3. Arsitektur target (adaptasi setia ke ARCHITECTURE.md)

```
WhatsApp (teks/VN/foto) ──> Muse agent (adapter per-turn)
   │  envelope: chat_id terdaftar, message ref, sent_at (tag runtime), modalitas
   ├─ VN ──> ASR lokal existing (faster-whisper small, ~/workspace/.asr-venv)
   ├─ foto ──> vision native agent (ekstraksi terstruktur: total, merchant, tanggal)
   └─ teks ─┐
            ▼
   Ekstraksi terstruktur (LLM) ──> kandidat JSON (TOOL_CONTRACT §4)
            ▼
   CLI/service Python (di workspace, dipanggil agent via terminal):
     authorization.py  → cek chat_id allowlist, injeksi FINANCE_OWNER_USER_ID dari config
     schemas.py        → Pydantic: amount int > 0, whitelist kategori/payment, panjang teks
     parser.py         → normalisasi rupiah ("12rb", "12.500"), tanggal relatif berbasis sent_at WIB
     service.py        → idempotency, batch multi-item, koreksi, soft-delete/restore
     reporting.py      → resolusi periode WIB → boundary UTC half-open
     repository.py     → supabase-py (HTTPS) + RPC laporan; TANPA SQL bebas dari model
            ▼
   Supabase PostgreSQL (project khusus finance): expenses, expense_categories, RPC report
            ▼
   Konfirmasi WhatsApp hanya dari hasil commit terverifikasi (ID persisten)
```

Prinsip yang tidak berubah dari spec: LLM tidak melihat secret, tidak memilih `user_id`, tidak menulis SQL bebas; semua angka laporan dari SQL; chat/memory bukan catatan keuangan.

## 4. Struktur repositori (target Phase 1 — sesuai ARCHITECTURE §3)

Mengikuti layout spec, ditempatkan di `~/workspace/expense-tracker/`:

- `docs/` — salinan spec pack (sumber kebenaran desain), `IMPLEMENTATION_PLAN.md` ini, `SETUP.md`, `BACKUP.md`, laporan verifikasi.
- `src/expense_tracker/` — `config.py`, `schemas.py`, `parser.py`, `authorization.py`, `service.py`, `reporting.py`, `repository.py`, `cli.py` (entry point yang dipanggil agent; menggantikan peran `muse_adapter.py` hipotetis — adapter sesungguhnya adalah perilaku agent per-turn, didokumentasikan di `docs/ADAPTER.md`, bukan modul SDK khayalan).
- `supabase/migrations/` — SQL berversi: `0001_schema.sql` (tabel + seed kategori + index + trigger `updated_at`), `0002_rls_grants.sql` (RLS, policies, grants), `0003_report_rpc.sql` (fungsi laporan statis + pembatasan EXECUTE).
- `tests/unit/`, `tests/integration/`, `tests/fixtures/` — pytest; fixtures golden dari TEST_PLAN §2.
- `.env.example` (placeholder saja), `.env` (lokal, gitignored, dibuat hanya saat provisioning), `pyproject.toml`, `.venv/` proyek (pydantic, supabase, pytest, httpx).
- Git diinisialisasi di folder proyek agar migration & kode terversi; secret tidak pernah masuk repo.

## 5. Data model & strategi migration

### 5.1 Skema (persis DATA_MODEL.md §3 — tidak diubah)

- `expense_categories(code PK, label_id, is_active)` + seed 9 kategori kanonis (`food_drink` … `other`).
- `expenses(id uuid PK, user_id FK→auth.users, occurred_at timestamptz, amount_idr bigint CHECK >0, category_code FK, description 1–500, merchant ≤200, payment_method enum, source_type enum, source_platform enum, source_message_id 1–255, source_item_index ≥0, timestamp_basis enum, receipt_reference ≤200, created_at, updated_at, deleted_at)`.
- Unique `(user_id, source_platform, source_message_id, source_item_index)`; dua partial index `(user_id, occurred_at desc)` dan `(user_id, category_code, occurred_at desc)` dengan `deleted_at is null`; trigger `updated_at`.
- Tanpa tabel item struk, tanpa kolom currency (IDR-only) — sesuai keputusan spec.

### 5.2 Migration strategy

1. Tulis migration sebagai file SQL di Git lebih dulu; review diff sebelum apply.
2. Apply pertama ke **staging project** (project Supabase terpisah atau schema staging) → jalankan seluruh test integrasi DB di sana.
3. Apply ke production **hanya dengan persetujuan eksplisit user** per rilis (aturan AGENTS.md spec).
4. Tidak ada DDL dari chat/runtime; rollback = migration kompensasi baru, bukan edit file lama.

### 5.3 Laporan (menjawab catatan DATA_MODEL §7)

supabase-py `.select()` bukan API GROUP BY, jadi laporan diimplementasikan sebagai **RPC PostgreSQL statis** `expense_report(p_start timestamptz, p_end timestamptz, p_category text default null)` yang:
- memakai `auth.uid()`-independent design untuk jalur backend: service memfilter `user_id` dari config server di dalam query RPC lewat parameter internal yang hanya bisa dipanggil role `service_role` (EXECUTE dicabut dari `anon`/`authenticated`/`public`),
- mengembalikan `total_idr`, `transaction_count`, dan baris per-kategori (`SUM`, `COUNT`, `GROUP BY category_code`) dari baris aktif saja,
- menerima boundary UTC half-open yang dihitung `reporting.py` dari tanggal WIB (Senin–Minggu; bulan kalender; custom inklusif→half-open; penolakan range > maksimum aman, default usulan 366 hari — dikonfirmasi Phase 0).

## 6. Identitas, auth, dan keamanan (mencakup seluruh security spec)

| Kontrol | Implementasi di plan |
|---|---|
| Owner identity | Satu Supabase Auth user dibuat saat Phase 0; UUID-nya disimpan sebagai `FINANCE_OWNER_USER_ID` di `.env` server-side. User yang sama dipakai dashboard masa depan |
| Sender authorization | Adapter agent hanya memproses chat WhatsApp terdaftar (chat_id di config); `authorization.py` menolak envelope di luar itu **sebelum** akses DB apa pun (FR-11, T21) |
| Secret handling | `SUPABASE_URL` + secret key hanya di `.env` workspace (gitignored, permission ketat), dimuat `config.py`; tidak masuk prompt, log, repo, atau chat. Provisioning lewat Secure Vault atas persetujuan user |
| RLS & grants | RLS aktif di kedua tabel; `anon` tanpa akses; `authenticated` hanya SELECT baris miliknya (`user_id = auth.uid()`); categories read-only untuk authenticated; RPC report EXECUTE hanya service_role. Secret key bypass RLS → setiap query/mutation repository **wajib** memfilter `user_id` dari config, termasuk `update/delete WHERE id AND user_id AND deleted_at IS NULL` |
| Tool surface | Hanya aksi TOOL_CONTRACT: `extract_expenses` (tanpa tulis), `create_expenses`, `list_expenses` (limit default 10, hard max 50), `update_expense` (whitelist field), `delete_expense`, `restore_expense`, `get_expense_report`. Tidak ada `execute_sql`/admin tool |
| Envelope respons | `{ok, status, data, error}` dengan status persis daftar TOOL_CONTRACT §3 (`created`, `already_recorded`, …, `outcome_unconfirmed`); tidak ada konfirmasi "tersimpan" untuk `outcome_unconfirmed`/timeout sebelum verifikasi ulang by idempotency key |
| Injection & untrusted input | Teks struk/transkrip = data, bukan instruksi (T24); string SQL-injection-like disimpan sebagai teks inert via parameterisasi SDK (T-gate §4 TEST_PLAN) |
| Privasi/log | Log terstruktur hanya ID + status + latensi + correlation ID; tanpa foto/audio/transkrip mentah, tanpa baris keuangan lengkap, tanpa secret. Media mentah tidak disimpan di Supabase secara default |
| Koreksi aman | Target koreksi/hapus dari ID persisten atau daftar terbaru terbatas; >1 kandidat masuk akal → tanya dulu (FR-07/08, T13); otorisasi owner dicek sebelum membaca record target |

## 7. Alur utama

### 7.1 Ingest → validasi → simpan idempoten → konfirmasi (FR-01..04, FR-09..13)

1. Pesan tiba di side-chat WhatsApp terdaftar; agent membentuk envelope (chat_id, referensi pesan, `sent_at` dari tag runtime, modalitas).
2. VN → transkrip via faster-whisper lokal existing; foto → ekstraksi vision native; teks langsung. (Ketiganya menyatu ke jalur validasi yang sama — acceptance PRD §7.1.)
3. LLM menghasilkan kandidat terstruktur (TOOL_CONTRACT §4) termasuk `source_item_index` berurutan untuk multi-pengeluaran.
4. CLI `create_expenses`: cek allowlist → injeksi `user_id` → validasi Pydantic (amount int IDR > 0; "12.500" → 12500; whitelist kategori/payment; `timestamp_basis` receipt > user_explicit > message_time; tanggal-saja → jam netral 12:00 WIB per DATA_MODEL §4).
5. Intent bukan pengeluaran (saldo, tarik tunai, transfer antar-akun sendiri, rencana) → `no_expense`/klarifikasi, tidak ada tulis (T09).
6. Amount/tanggal ambigu → `needs_clarification`, **tidak insert**; jawaban user dipetakan ke perintah beridentitas deterministik yang terdokumentasi (bukan mengandalkan message_id balasan yang sama).
7. Insert batch dengan unique key idempotency; konflik unik → ambil baris lama → `already_recorded` (replay tidak menimpa koreksi yang lebih baru — T28).
8. Timeout tak pasti → query ulang by idempotency key sebelum retry; status `outcome_unconfirmed` tanpa klaim sukses/gagal.
9. Konfirmasi WhatsApp per item dengan ID persisten (format TOOL_CONTRACT §10); sukses parsial dilaporkan per item, tidak digeneralisasi.

### 7.2 Laporan (FR-05, FR-06, FR-16)

Permintaan → `reporting.py` resolusi periode dari timestamp pesan (WIB) → boundary UTC half-open → RPC SQL agregat → format Rp + label periode + timezone + jumlah transaksi + breakdown kategori + opsi transaksi terbaru. Periode kosong → "belum ada transaksi tercatat", bukan "pengeluaran nol".

### 7.3 Koreksi / hapus / pulihkan (FR-07, FR-08, FR-14, FR-15)

`list_expenses` terbatas untuk resolusi target → `update_expense` whitelist field → `delete_expense` soft (set `deleted_at`) → `restore_expense`. Laporan selalu mengecualikan baris terhapus.

## 8. Rencana fase & gerbang (gates)

### Phase 0 — Verifikasi & provisioning (belum coding fitur)
- Konfirmasi keputusan user di §9 (project baru vs existing, email Auth owner, region, tujuan backup, persetujuan buat `.env`).
- Provisioning Supabase: project khusus finance (usulan region Singapore), buat Auth owner, catat UUID.
- Uji konektivitas dari venv proyek: HTTPS Data API read/write ke tabel uji di **staging**, verifikasi secret key tidak bocor ke log.
- Uji keputusan teknis: cara apply migration (CLI binary vs SQL Editor), ketersediaan `message_id` runtime per pesan untuk idempotency, perilaku replay.
- **Gate:** koneksi staging terbukti + migration 0001–0003 apply bersih di staging. Gagal → berhenti, laporkan blocker persis (aturan README: jangan mengklaim integrasi end-to-end).

### Phase 1 — MVP
- Urutan bangun: skema+migration → schemas/parser (unit test) → repository+service (idempotency, CRUD, soft-delete) → reporting RPC → CLI adapter + dokumentasi adapter agent → logging terstruktur → prosedur backup manual + uji restore di staging.
- **Gate:** seluruh TEST_PLAN §3 (T01–T30) lulus di staging dengan label jujur mock vs live (§10), security gates §4 lulus, lalu **smoke test live terbatas atas persetujuan user**: 1 teks, 1 VN, 1 foto struk di chat ini → konfirmasi ID → laporan hari ini cocok.
- Apply migration production hanya setelah gate staging + persetujuan eksplisit.

### Phase 2 (nanti, tidak dibangun sekarang)
Dedupe struk lebih pintar, kategorisasi lebih baik, laporan terjadwal via Hatch cron, export CSV, otomasi backup, antrean retry lokal terenkripsi (bila dibutuhkan).

### Phase 3 (nanti)
Dashboard Next.js sesuai DASHBOARD_ROADMAP (D0–D4) memakai Auth user & skema yang sama. **Tidak ada scaffold Next.js di Phase 1.**

## 9. Setup yang perlu keputusan user (ditanyakan, tidak diasumsikan)

1. **Project Supabase:** buat project baru khusus finance (rekomendasi, region Singapore) atau sudah ada project yang mau dipakai? Jangan pakai project CareerOS (ARCHITECTURE §4: project khusus finance).
2. **Kredensial:** bersedia provisioning URL + secret key lewat Secure Vault (bukan chat)? Siapa yang membuat project — user di dashboard Supabase, lalu kredensial diserahkan aman; agent tidak membuat akun atas nama user.
3. **Auth owner:** email untuk Supabase Auth user (usulan: Gmail utama user) — UUID user ini menjadi `FINANCE_OWNER_USER_ID` dan login dashboard kelak.
4. **Staging:** project kedua gratis untuk test, atau satu project dengan discipline staging-first? (Free tier: jumlah project terbatas — verifikasi kuota saat Phase 0.)
5. **Backup off-platform:** tujuan dump terenkripsi — Google Drive (perlu connect dulu), file lokal workspace + unduh berkala, atau lainnya? Frekuensi & siapa menjalankan restore drill.
6. **Batas range laporan custom** (usulan default maksimum 366 hari) dan konfirmasi format konfirmasi WhatsApp di TOOL_CONTRACT §10.
7. **Persetujuan membuat** folder proyek + `.env` baru di `~/workspace/expense-tracker/` saat Phase 0 dimulai (saat ini belum dibuat apa pun selain file plan ini).

## 10. Pemetaan test (TEST_PLAN: 30 skenario — semua tercakup)

| Kelompok | ID | Dicakup oleh |
|---|---|---|
| Parsing & nominal | T01, T02, T26 | Unit `parser.py`/`schemas.py`: "12rb"→12000, "12.500"→12500, tolak 0/negatif/float |
| Modalitas | T03, T04, T05, T11 | Fixture transkrip VN + fixture struk Nescafe (total saja, abaikan tunai/kembalian, 5 item = 1 baris, merchant null boleh) |
| Multi & idempotency | T06, T07, T08, T25, T28 | Integration: index 0/1, replay message_id sama, forward struk baru = probable-duplicate warning, timeout→lookup by key, replay tidak mengundo koreksi |
| Non-pengeluaran & klarifikasi | T09, T10, T27 | Unit+service: saldo/tarik tunai ditolak, tanpa harga → tanya, tanggal konflik → tanya |
| Mutasi | T12, T13, T14 | Integration: update unik, update ambigu → tanya, delete→report→restore |
| Waktu & periode | T15, T16, T17, T18, T19, T20, T29 | Unit `reporting.py` (Senin 00:00 WIB dst., boundary bulan, backfill by occurred_at) + integration fixture E1–E4 (Okt Rp62.000/2, Nov Rp20.000/2; E4 terhapus → Nov Rp2.000/1) |
| Keamanan | T21, T22, T23, T24 | Integration RLS di staging (sender lain ditolak sebelum DB, user B publishable key = 0 baris, anon ditolak) + unit injection sebagai data |
| Operasional | T30 | Migration dari nol di project uji + restore drill dari backup; dicatat hasilnya |

Label kejujuran (wajib di laporan akhir, per TEST_PLAN §5–6): **Unit** (mock penuh), **DB integration** (staging Supabase nyata), **Adapter contract** (envelope palsu), **Live smoke** (WhatsApp/Muse nyata, opt-in). Mock tidak pernah dilaporkan sebagai live.

Security gates tambahan (TEST_PLAN §4): tidak ada secret di repo/log/prompt; setiap mutation menegaskan `user_id` dari mapping server; grants RPC dibatasi; otorisasi sebelum membaca record target.

## 11. Risiko teknis utama

| Risiko | Level | Mitigasi |
|---|---|---|
| Tidak ada SDK tool-calling Muse formal → integrasi bergantung agent menjalankan CLI per turn | Tinggi (arsitektural) | Terima sebagai desain adapter MVP (terverifikasi jalan hari ini); dokumentasikan di `docs/ADAPTER.md`; evaluasi ulang custom connector bila kontrak resmi muncul. Konsekuensi: tidak ada pemrosesan saat agent tidak dipanggil (tidak ada daemon) — cocok untuk pola percakapan, bukan ingestion pasif |
| `message_id` runtime tidak stabil untuk redelivery yang sama → idempotency melemah | Sedang | Idempotency key utama dari ID pesan bila ada; lapisan kedua: deteksi probable-duplicate (amount+merchant+occurred_at+receipt_reference) → tanya user (sesuai PRD/T08); jangan auto-suppress |
| Allowlist sender berbasis chat terdaftar, bukan provider sender_id | Sedang | Config server-side memegang chat_id; service menolak envelope lain; dicatat sebagai deviasi sadar dari spec §FR-11 dengan alasan bukti runtime; review bila envelope API tersedia |
| Free-tier Supabase: project pause karena inaktivitas + tanpa backup harian otomatis | Sedang | Pemakaian harian membuatnya aktif; backup logis off-platform berkala (Phase 1 manual, Phase 2 otomasi cron) + restore drill T30; verifikasi ulang ketentuan free plan saat Phase 0 |
| Secret key bocor = bypass RLS total | Tinggi bila terjadi | Secret hanya di `.env` workspace berizin ketat, tidak di git/log/prompt/chat; rotasi bila dicurigai; query selalu filter `user_id` |
| Kualitas ekstraksi foto/VN (angka salah baca) | Sedang | Jalur klarifikasi untuk amount tidak pasti; konfirmasi menampilkan amount agar user bisa koreksi (FR-07); ASR lokal model small (terverifikasi) bukan transkrip runtime |
| Migration tanpa Supabase CLI/Docker lokal | Sedang | File SQL berversi + apply via jalur terverifikasi di Phase 0 (CLI binary atau SQL Editor dengan persetujuan); test penuh di staging dulu |
| Koneksi Postgres langsung tidak tersedia dari VM | Rendah | Tidak dipakai di MVP; semua lewat HTTPS Data API + RPC |
| Scope creep (dashboard/Dicoding/budget ditarik ke MVP) | Sedang | Gerbang fase di §8; DASHBOARD_ROADMAP & daftar "not now" README sebagai pagar |

## 12. Addendum — Keputusan user (1 Nov 2026, 16:24 WIB) yang menggantikan §9

| # | Pertanyaan §9 | Keputusan user | Konsekuensi ke plan |
|---|---|---|---|
| 1 | Project Supabase | **Belum ada project apa pun; user bertanya apakah perlu membuat manual** | Ya — user membuat akun + project secara manual (±5 menit, panduan `docs/SETUP.md` Langkah 1–2, region Singapore, plan Free). Agent tidak membuat akun atas nama user |
| 2 | Email Auth owner | **Email pribadi user** (`<owner-email>`) | UUID Auth user tersebut = `FINANCE_OWNER_USER_ID`, dipakai juga untuk dashboard Phase 3 |
| 3 | Staging | **Jangan overengineering** (user kurang memahami opsi staging) | **Satu project saja.** Test memakai Auth user kedua khusus test + fixture yang dibersihkan; drill migration/restore (T30) memakai project free sementara yang dihapus setelahnya. Trade-off dicatat: test dan data asli berbagi project yang sama, dimitigasi oleh user test terpisah, RLS, dan gerbang persetujuan sebelum apply migration |
| 4 | Backup off-platform | **Google Drive; agent diminta membantu setup** | Prosedur di `docs/BACKUP.md`; koneksi Drive dilakukan saat eksekusi (saat ini Drive belum terhubung) |
| 5 | Penyerahan API key | **User ingin memberi kunci tanpa memberikannya ke agent; minta dipandu** | Mekanisme Secure Vault Muse (kartu aman; nilai tidak melewati chat, tidak dibaca agent) — panduan di `docs/SETUP.md` Langkah 3, termasuk satu titik verifikasi Phase 0 tentang penyaluran kredensial vault ke tool Python lokal |
| — | Draft sebelum eksekusi | **User meminta draft final seluruh MD + .sh ditunjukkan dulu, jangan terburu-buru eksekusi** | Paket template disusun di repo proyek: README + AGENTS (dari spec), `docs/` (spec + `SETUP.md`, `BACKUP.md`, `ADAPTER.md` baru), `.env.example`, `scripts/setup.sh`, `scripts/check_env.sh` (draft, hanya dicek sintaks, **tidak dijalankan**) |

## 13. Yang SENGAJA belum dilakukan pada tahap ini

Tidak ada kode, tidak ada `.env`, tidak ada migration yang ditulis/dijalankan, tidak ada project Supabase yang dibuat, tidak ada connector yang diubah, tidak ada file existing yang ditimpa. Satu-satunya artefak tahap ini: file plan ini di `~/workspace/expense-tracker/IMPLEMENTATION_PLAN.md`.

---

## Addendum 3 — Hasil verifikasi Phase 0 (parsial, 1 Nov 2026 ±16:45 WIB)

- Project Supabase `personal-expense-tracker` sudah dibuat user; Project URL `https://<project-ref>.supabase.co`; Auth user owner sudah dibuat; `FINANCE_OWNER_USER_ID=<owner-user-uuid>` (diberikan user di chat — UUID adalah identifier, bukan kredensial).
- Mekanisme kredensial vault **terbukti bekerja**: koneksi terdaftar `custom.supabase`, helper `~/workspace/custom-connectors/custom.supabase/bin/probe_auth_users.py` memanggil API dengan surrogate dari `dynamic_credentials.py`; agent tidak pernah melihat kunci asli. Connector doc selesai ditulis di `~/workspace/custom-connectors/custom.supabase/CONNECTOR.md`.
- Temuan placement: registrasi `bearer_header` ditolak Supabase (HTTP 401, "No API key found in request" — gateway mewajibkan header `apikey`). Reconnect `custom_header:apikey` diterbitkan 16:44 WIB; **status: menunggu user mengisi ulang kunci yang sama** pada kartu aman baru. Setelah itu probe diulang untuk memastikan penerimaan kredensial + kecocokan UUID/email owner.
- Implikasi desain yang perlu dicatat untuk Phase 1: jalur repository yang realistis adalah panggilan HTTPS Data API (PostgREST + RPC) lewat helper surrogate ini — bukan `supabase-py` yang membaca secret dari `.env`. `docs/SETUP.md` Langkah 3 sudah diperbarui; penyesuaian tertulis ke `docs/ADAPTER.md`/rencana repository dilakukan saat Phase 1 dimulai.

## Addendum 4 — Verifikasi Phase 0 SELESAI untuk kredensial & identitas (1 Nov 2026 16:49 WIB)

- Reconnect `custom_header:apikey` diisi user; probe `GET /auth/v1/admin/users` (path admin yang benar — draf probe awal sempat memakai `/auth/v1/users` dan menerima 404, sudah diperbaiki) mengembalikan **HTTP 200**: 1 user di project, UUID cocok dengan `FINANCE_OWNER_USER_ID`, email cocok `<owner-email>`. Endpoint admin ini mensyaratkan hak secret/service key, jadi kelas kuncinya juga terkonfirmasi benar.
- Kesimpulan Phase 0 (bagian kredensial): mekanisme Secure Vault → koneksi `custom.supabase` → helper surrogate **terbukti end-to-end**. Kunci asli tidak pernah dibaca agent, tidak menjadi file, dan tidak masuk log.
- Sisa Phase 0 sebelum Phase 1: (a) jalur apply migration (CLI binary vs SQL Editor) diputuskan saat migration pertama ditulis; (b) koneksi Google Drive untuk backup; (c) bootstrap venv proyek. Menunggu persetujuan user untuk mulai menulis kode + migration Phase 1 (apply migration tetap gerbang persetujuan terpisah).

## Addendum 5 — Phase 1 build SELESAI ditulis, migration BELUM di-apply (2 Nov 2026)

Atas persetujuan user ("lanjut kerjain expense tracker"), Phase 1 dibangun:

- Bootstrap: `scripts/setup.sh` dijalankan (venv proyek + pydantic/supabase/pytest/httpx), `.env` diisi nilai non-rahasia (URL, FINANCE_OWNER_USER_ID, ALLOWED_WHATSAPP_CHAT_ID = side chat ini, TZ, max range 366). Field kunci di `.env` sengaja kosong — akses terautentikasi lewat gateway vault `custom.supabase`. `check_env.sh`: FAIL=0.
- Migration (draft, belum di-apply): `migrations/0001_schema.sql` (2 tabel + seed 9 kategori + index + trigger updated_at), `0002_rls_grants.sql` (RLS aktif; authenticated hanya SELECT miliknya; anon tanpa akses; tanpa grant tulis untuk role browser), `0003_report_rpc.sql` (RPC `expense_report` SQL statis; EXECUTE hanya service_role).
- Kode `src/finance/`: errors, categories, money (parse/format IDR), dates (periode WIB + batas UTC half-open), models (Pydantic strict, tanpa field user_id), config, idempotency (probable-duplicate layer-2), gateway (surrogate vault), repository (PostgREST + RPC, semua query terfilter owner), service (otorisasi chat + envelope TOOL_CONTRACT), confirmation (format §10), cli (`scripts/run_tool.sh`).
- Test: **35 passed, 1 skipped** (`.venv/bin/python -m pytest tests/ -q`). Termasuk golden fixture E1–E4 lewat service layer + FakeRepository: Okt 2026 Rp62.000/2, Nov Rp20.000/2, replay → already_recorded (T07), delete/restore E4 (T14), update (T12), unauthorized chat (T21), parse 12.500 → 12500 (T02), batas bulan E3, range maksimum (T29). Test integrasi live tersedia tapi skipped sampai migration di-apply (FINANCE_INTEGRATION=1).
- Keputusan arsitektur saat build: repository memakai httpx + gateway vault secara langsung (bukan supabase-py dari .env) — konsisten dengan Addendum 3 §12; paket supabase tetap terpasang di venv sesuai draft setup.
- Gerbang berikutnya: review + persetujuan user untuk APPLY migration 0001–0003 ke project (jalur: SQL Editor dashboard atau CLI binary), lalu integration test live + uji ujung-ke-ujung via chat ini. Sisa Phase 0 lain: koneksi Google Drive untuk backup (belum dikerjakan).

## Addendum 6 — Migration TERAPPLY + verifikasi live LULUS (2 Nov 2026 02:36–02:41 WIB)

- User meng-apply 0001–0003 sendiri via SQL Editor dashboard (dipandu per file) — semua sukses.
- Dua perbaikan gateway saat verifikasi: (1) httpx gagal parse NO_PROXY environment ini (IPv6 bracket) → proxy diteruskan eksplisit; (2) broker kredensial salah deteksi tipe Request httpx venv → transport diganti **urllib** (kombinasi yang terbukti di probe) dengan API kelas yang sama. Setelah itu integration test live LULUS (9 kategori terbaca).
- Smoke test ujung-ke-ujung via CLI terhadap project live: report awal Nov 2026 = 0/0 → create transaksi TEST Rp1.000 (id <expense-id>) = created → replay = already_recorded (tanpa dobel) → soft-delete = deleted → report akhir kembali 0/0. Baris TEST tetap ada di DB dalam keadaan soft-deleted (sesuai desain; tidak masuk laporan).
- Status: **MVP fungsional live** untuk pencatatan via chat ini. Suite test penuh: semua hijau termasuk integrasi (FINANCE_INTEGRATION=1).
- Belum dikerjakan: koneksi Google Drive + job backup (BACKUP.md), uji RLS user-B (T22) yang butuh user Auth kedua, uji voice/receipt live lewat percakapan nyata.

## Addendum 7 — Jadwal rekap otomatis dibuat (2 Nov 2026)

Atas permintaan user, tiga cron Hatch dibuat di chat ini (delivery ke side chat WhatsApp ini):
- `expense-report-daily` — daily 23:59 Asia/Jakarta, periode `today`; run pertama Senin 2 Nov 2026 23:59 WIB.
- `expense-report-weekly` — weekly Minggu 23:59, periode `this_week` (Senin–Minggu).
- `expense-report-monthly` — monthly tgl 28–31 23:59; body job memerintahkan diam kecuali hari terakhir bulan (30 Nov untuk November), periode `this_month`.
Ketiganya menjalankan CLI report yang sama, memformat sesuai konvensi laporan, tetap melapor saat 0 transaksi, dan melaporkan kegagalan secara eksplisit. Konvensi perintah chat didokumentasikan di `docs/COMMANDS.md`; transaksi beneran pertama (struk Nescafe Rp12.000, 30 Okt 2026, ID 43d19adc) tercatat lewat foto pada 02:43 WIB.
