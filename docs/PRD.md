# PRD — WhatsApp Personal Expense Tracker

## 1. Problem / outcome

The user wants to casually record real expenses by sending WhatsApp texts, voice notes, or receipt images and ask the same chat for trustworthy daily/weekly/monthly spending reports. Remembering expenses in an LLM is unreliable; manual spreadsheets add friction. Long-term, a Next.js dashboard should reuse the same Supabase PostgreSQL data without a migration.

**North-star:** Low-friction capture + accurate persistent reports with visible save confirmation.

## 2. Primary user and scope

- Single owner, Indonesian casual-language conversation, IDR, timezone `Asia/Jakarta`.
- **MVP:** Expense-only ledger (not a complete accounting/bank system).
- WhatsApp is the only intended UI in Phase 1. Existing Muse agent processes messages.
- Finance database should not be shared with unrelated projects.

## 3. Functional requirements

| ID | Priority | Requirement | Success behavior |
|---|---|---|---|
| FR-01 | Must | Add expense via text | Extract amount, date, category, merchant/description if provided; validate and save |
| FR-02 | Must | Add expense via voice | Reuse available ASR; parse transcript; preserve data semantics, not raw voice by default |
| FR-03 | Must | Add expense via receipt photo | Reuse existing vision/OCR; total amount, merchant, transaction date; avoid tender/change confusion |
| FR-04 | Must | Multi-expense message | "kopi 12rb, parkir 2rb" creates two rows with stable source indices |
| FR-05 | Must | Query report | Today/yesterday, this/last week, this/last month, explicit WIB date interval |
| FR-06 | Must | Breakdown | Total amount, count, category amounts, optionally recent transactions |
| FR-07 | Must | Amend | "kopi tadi 15rb bukan 12rb" resolves a unique row or asks which one |
| FR-08 | Must | Soft-delete & restore | Supports correcting mistakes without losing history; require confirmation for ambiguous targets |
| FR-09 | Must | Idempotent ingestion | Replayed WhatsApp message ID does not add duplicate rows |
| FR-10 | Must | Save confirmation | Return amount/category/date and persistent transaction ID **only after** successful commit |
| FR-11 | Must | Security | Sender allowlist, server-mapped user identity, server-only DB secrets; deny other senders |
| FR-12 | Must | Correct time semantics | Transaction occurred time rather than time of message capture; WIB reporting boundaries |
| FR-13 | Must | Unknown/ambiguous inputs | Ask targeted clarification rather than invent amounts/dates/merchants |
| FR-14 | Should | Category correction | User can change categorized expenses without creating a new row |
| FR-15 | Should | List/search | Last N transactions, date/category/merchant filters; never show other users' records |
| FR-16 | Should | Stable report references | Clearly label covered period, WIB timezone, and data source |

## 4. Conversation examples (illustrative)

### Simple text

**User:** `cuy tadi jajan bakso 18 ribu cash`  
**Agent:** `Tercatat: Bakso · Rp18.000 · Makanan & Minuman · Cash · 1 Nov 2026 (WIB). ID: <short id>.`

Only infer a purchase time from the WhatsApp message time if no more precise timestamp was supplied. Never pretend the user provided merchant or clock time.

### Voice note

ASR returns: `kemarin beli bensin lima puluh ribu`  
Agent parses `Rp50.000`, category `transport`, date **relative to original message timestamp** in WIB. Confirm transcription if amount is uncertain.

### Receipt photo

A receipt shows `Total Rp12.000`, `Tunai Rp100.000`, `Kembali Rp88.000`. Save `amount_idr=12000` **once**. If there are multiple receipt line items, MVP stores receipt total as a single expense.

### Multiple expenses

**User:** `kopi 12 ribu sama parkir 2 ribu`  
Save `12,000` and `2,000` as two expenses (`source_item_index=0,1`); avoid merging them into `14,000` with a single category. Reply total added `Rp14.000` and show each entry.

### Query / report

**User:** `bulan Oktober total pengeluaran berapa?`  
Respond with real PostgreSQL result: period `1–31 Oktober 2026 WIB`, total, number of transactions, top categories. If no records, say "Belum ada transaksi tercatat untuk periode tersebut"—never imply actual spending was zero.

### Correction

**User:** `eh kopi tadi 15k bukan 12k`  
If exact intended transaction is identified reliably, update it (do **not** add another transaction); otherwise ask which item. Confirmation includes new amount and transaction ID.

### Non-expense

**User:** `saldo e-wallet gua 50rb`  
Do **not** record a Rp50.000 expense. Balances, cash withdrawals, transfers between personal accounts, change, and income are outside MVP; clarify if unclear.

## 5. Product rules

- **Expense = actual money spent for goods/services**, not money tendered, returned change, transfer between own accounts, or unconfirmed planned spending.
- **One record per receipt/purchase**; multiple separate purchases stated in one message can become multiple records.
- All amounts are strictly positive whole integer IDR. Never store floating-point currency values.
- Category labels are editable, backed by canonical codes. Use `other` as fallback if an amount is clear but category unknown.
- Missing amount = block and ask. Missing merchant = allowed. Missing exact time = use message timestamp and mark timestamp provenance `message_time`.
- Receipt timestamp, if unambiguous, wins over message timestamp; otherwise use explicit user time, then message time.
- Relative expressions (`tadi`, `kemarin`, `minggu ini`) must be interpreted based on the **actual timestamp** of the WhatsApp message, not an assumed system date.
- Week = Monday 00:00 through next Monday 00:00 WIB; month = calendar month WIB; date ranges use inclusive start / exclusive end.
- Report historical backfills only include records actually persisted. Do not infer past expenses from messages not ingested.
- Duplicate media forwarded in a **new** message is only a *possible* duplicate; warn/ask using receipt reference or matching details, never blindly suppress two legitimately identical purchases.
- Any tool failure leaves status `not_saved` and user gets an explicit retry-safe message. No "sudah tersimpan" before a confirmed write.

## 6. Non-functional requirements

- **Consistency:** One confirmed expense = one persisted record; duplicate incoming message redelivery must not duplicate the expense.
- **Reliability:** Network timeouts retry with bounded backoff and same idempotency key; distinguish unknown outcome from confirmed failure.
- **Privacy:** Store minimal transaction details; no automatic upload of receipt images/audio/transcripts to Supabase Storage.
- **Observability:** Structured events: `message_received`, `extraction_failed`, `expense_saved`, `expense_duplicated`, `report_generated`, `db_error`. Redact content, keys, and sensitive details.
- **Recovery:** Document reproducible database migrations and off-site backup/restore procedure.
- **Maintainability:** Python core logic independent of Muse; input adapter handles channel specifics; SQL migrations versioned.
- **Security:** Enforce user authorization before any extraction-to-write call; no arbitrary SQL or unchecked user-selected user ID.

## 7. Acceptance criteria / definition of done

1. Each of text, ASR transcript, and OCR output passes the same validated write path.
2. A synthetic text, voice-transcript, and receipt fixture each save correctly to a staging database.
3. A repeated message ID yields the same existing expense, not extra rows.
4. Receipt total is Rp12,000, not Rp100,000 or Rp88,000, in the Nescafe example.
5. `1 Nov 00:15 WIB` is included in November even though UTC timestamp is still October.
6. Real daily, weekly, monthly, and by-category reports match known SQL fixture totals.
7. Corrections modify the intended expense, and soft-deleted rows are excluded from reports.
8. A non-allowlisted WhatsApp sender and an authenticated different Supabase user cannot read the owner's expenses.
9. A connection failure returns a clear unsaved/unknown-outcome status and avoids fake confirmation.
10. Integration is verified in actual Muse/WhatsApp runtime **or** marked blocked with exact missing contract; unit/integration tests can pass independently.

## 8. Phase scope

- **Phase 0:** Inspect Muse environment/WhatsApp envelope; provision Supabase and Auth owner identity; validate connectivity.
- **Phase 1 (MVP):** Text, voice, receipt, CRUD, reports, idempotency, RLS, minimal logging, backup instructions, tests.
- **Phase 2:** Better receipt dedupe, auto categorization refinement, optional scheduled report, CSV export and backup automation.
- **Phase 3:** Authenticated Next.js dashboard, filters/charts/table/editor, same PostgreSQL and owner ID. See `DASHBOARD_ROADMAP.md`.

**Do not pull Phase 2/3 features into MVP merely because they are listed.**
