# Perintah Chat — Personal Expense Tracker

Konvensi perintah untuk chat WhatsApp ini (disepakati 2 Nov 2026).
Perintah hanyalah jalan pintas: bahasa alami tetap cara utama. Agent
memetakan perintah ke tool layer (`scripts/run_tool.sh`) dan hanya
mengirim konfirmasi setelah data benar-benar tersimpan di Supabase.

## Mencatat (tanpa perintah pun bisa)

- Kirim teks: `kopi 12rb cash`, `bensin 50rb, parkir 2rb` (multi-item OK)
- Kirim foto struk → dicatat dari total struk (bukan tunai/kembalian)
- Kirim voice note → ditranskrip lokal lalu dicatat
- `/catat <teks>` — bentuk eksplisit dari hal yang sama

Aturan pencatatan:
- Nominal/tanggal ambigu → agent bertanya dulu, tidak menebak.
- Pesan yang sama terkirim ulang → tidak didobel (`already_recorded`).
- Struk yang sama diforward ulang → ditandai sebagai kemungkinan
  duplikat dan diminta keputusan user.

## Rekap / laporan

| Perintah | Periode |
|---|---|
| `/hari_ini` | hari ini (WIB) |
| `/kemarin` | kemarin |
| `/minggu_ini` | Senin–Minggu berjalan |
| `/minggu_lalu` | Senin–Minggu lalu |
| `/bulan_ini` | bulan berjalan |
| `/bulan_lalu` | bulan lalu |
| `/pengeluaran_hari_ini` | alias `/hari_ini` |
| `/laporan <YYYY-MM-DD> <YYYY-MM-DD>` | rentang khusus, maks 366 hari |

Bahasa alami juga berlaku: "laporan bulan ini", "pengeluaran minggu
ini", "total Oktober kemarin".

## Melihat & mengubah data

| Perintah | Fungsi |
|---|---|
| `/terbaru [n]` | n transaksi terakhir (default 10, maks 50) |
| `/cari <kata>` | cari berdasarkan nama merchant |
| `/ubah <ID> <field> <nilai>` | koreksi amount/kategori/tanggal/dll |
| `/hapus <ID>` | soft-delete (hilang dari laporan, bisa dipulihkan) |
| `/pulihkan <ID>` | batalkan soft-delete |

`<ID>` boleh ID pendek 8 karakter (awalan UUID) selama unik; agent
menyelesaikannya ke UUID penuh sebelum memanggil tool.

## Lainnya

- `/help` — tampilkan ringkasan perintah ini.

## Jadwal rekap otomatis (cron, dibuat 2 Nov 2026)

| Jadwal | Cron ID | Waktu (WIB) | Isi |
|---|---|---|---|
| Harian | `expense-report-daily` | setiap hari 23:59 | rekap hari berjalan |
| Mingguan | `expense-report-weekly` | Minggu 23:59 | rekap Senin–Minggu berjalan |
| Bulanan | `expense-report-monthly` | tgl 28–31 23:59, hanya terkirim di hari terakhir bulan | rekap bulan berjalan |

Ketiganya mengirim ke chat WhatsApp ini dan mengambil angka dari RPC
laporan yang sama dengan perintah manual. Rekap tetap terkirim walau
0 transaksi ("belum ada catatan"), dan kegagalan tool dilaporkan
sebagai pesan error singkat, bukan diam.
