# ADAPTER.md — Kontrak Adapter Muse/WhatsApp (Draft Final)

**Status: DRAFT untuk review user.** Dokumen ini mencatat bagaimana spec (yang mengasumsikan "server-side Python tools" dan envelope WhatsApp terprogram) dipetakan ke **realitas runtime Muse yang terverifikasi pada 1 Nov 2026** — termasuk deviasi sadarnya. Tidak ada SDK khayalan di dokumen ini.

## 1. Model eksekusi yang nyata

- Tidak ada daemon/webhook: VM Muse tidak memiliki port inbound, IP publik, atau proses server yang dijamin hidup.
- Pemrosesan terjadi **per turn percakapan**: pesan user masuk ke side-chat WhatsApp → agent Muse berjalan → agent memanggil CLI proyek (`expense-tracker` di `~/workspace/expense-tracker`) lewat terminal → hasil terverifikasi → agent membalas di chat yang sama.
- Pekerjaan terjadwal (bila kelak disetujui) berjalan sebagai **Hatch cron** (agent terjadwal), bukan systemd/crontab.
- Konsekuensi yang diterima untuk MVP: tidak ada ingestion pasif di luar turn chat; pola pakai memang percakapan, jadi ini selaras dengan PRD.

## 2. Envelope masuk (dibangun agent dari konteks runtime)

```json
{
  "chat_id": "<whatsapp-chat-id>",
  "source_platform": "whatsapp",
  "source_message_id": "<id pesan runtime bila tersedia>",
  "sent_at": "<tag waktu runtime pesan, Asia/Jakarta>",
  "modality": "text | voice | receipt",
  "text": "<isi teks / transkrip ASR / hasil ekstraksi vision>"
}
```

| Field | Sumber terverifikasi | Catatan |
|---|---|---|
| `chat_id` | Metadata sesi side-chat WhatsApp | Dipakai sebagai pengganti allowlist `sender_id` (lihat §3) |
| `sent_at` | Tag waktu yang disematkan runtime pada setiap pesan user | Dasar interpretasi "tadi/kemarin/minggu ini" (FR-12) |
| `source_message_id` | ID pesan runtime bila terekspos pada turn berjalan | **Belum terverifikasi stabil untuk redelivery.** Bila kosong/tidak stabil → lapisan probable-duplicate (§4) |
| Media | File lampiran tersimpan runtime ke workspace dan dapat dibuka agent | Jalur file tidak dicatat permanen di DB; media mentah tidak disimpan (kebijakan spec) |

## 3. Deviasi kontrol: allowlist sender

- Spec FR-11/ARCHITECTURE §5 mengasumsikan `sender_id` dari provider untuk allowlist.
- Realitas: side-chat WhatsApp Muse **terikat pada akun WhatsApp owner yang ter-pairing**; tidak ada pihak ketiga yang dapat mengirim pesan ke chat 1:1 ini, dan tidak ada `sender_id` provider yang dapat dicek oleh kode.
- Adaptasi: `authorization.py` memvalidasi `chat_id` terhadap **satu chat terdaftar** yang disimpan di config server-side (`ALLOWED_WHATSAPP_CHAT_ID`), dan menolak envelope lain sebelum akses DB. Agent hanya membentuk envelope untuk pesan dari chat tersebut.
- Risiko sisa (diterima sadar): siapa pun yang memegang ponsel/WhatsApp owner yang sudah ter-pairing dapat memakai chat ini. Mitigasi tambahan di luar scope MVP.
- Kewajiban review: bila Muse kelak mengekspos envelope provider resmi (sender/message ID stabil), adapter wajib dimigrasikan ke kontrak tersebut dan deviasi ini ditutup.

## 4. Idempotency dua lapis

1. **Lapis utama:** unique key DB `(user_id, source_platform, source_message_id, source_item_index)` persis seperti DATA_MODEL — dipakai setiap kali `source_message_id` tersedia.
2. **Lapis cadangan (probable duplicate):** bila ID pesan tidak tersedia untuk sebuah replay/forward, service memeriksa kecocokan (amount, merchant, occurred_at ± toleransi, receipt_reference) dan **memperingatkan user untuk memutuskan** (perilaku T08) — tidak pernah men-suppress diam-diam dan tidak pernah mendobelkan diam-diam.

## 5. ASR & vision (reuse, bukan instalasi baru)

- **ASR of record:** faster-whisper lokal existing di `~/workspace/.asr-venv` (model `small`, PyAV 12.3.0) — terverifikasi menghasilkan transkrip Bahasa Indonesia akurat pada 1 Nov 2026. Transkrip bawaan runtime WhatsApp (teramati salah deteksi bahasa) hanya fallback dan tidak dipakai untuk amount tanpa konfirmasi.
- **Vision/OCR:** kemampuan vision native agent — terverifikasi mengekstrak struk Nescafe dengan benar (total Rp12.000 vs tunai Rp100.000 vs kembalian Rp88.000). Ekstraksi selalu keluar sebagai kandidat terstruktur TOOL_CONTRACT §4 dan melewati validasi yang sama dengan teks.
- Transkrip/ekstraksi tidak disimpan mentah di Supabase; hanya field ternormalisasi + provenance (`source_type`, `timestamp_basis`, `receipt_reference`).

## 6. Batasan adapter yang harus diakui di laporan verifikasi

- Test "live smoke" (TEST_PLAN §1) hanya dapat mengklaim PASS bila benar-benar dijalankan pada chat ini dengan data uji; test adapter berbasis envelope palsu berlabel **mock**.
- Bila suatu saat runtime berubah (VM diganti, chat terputus), pemulihan = reconnect WhatsApp + pastikan folder proyek persisten utuh; tidak ada state adapter di luar workspace.
