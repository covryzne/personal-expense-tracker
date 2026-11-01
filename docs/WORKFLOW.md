# Workflow — Personal Expense Tracker (end-to-end)

How the live system behaves, step by step. Written so the same workflow
can be re-implemented behind another bot/transport: sections 1–10 are
transport-independent except where the **adapter** is explicitly named.
Contracts (field-level) live in `TOOL_CONTRACT.md`; schema in
`DATA_MODEL.md`; this document is the behavior narrative.

## 0. Actors and components

- **User** — one owner, chatting from one allowlisted chat.
- **Transport** (WhatsApp here) — delivers text / image / audio and the
  replies. Its redelivery semantics are *not* trusted (see §5).
- **Adapter** — builds the *trusted envelope* `{chat_id, message_id,
  sent_at, modality, source_type}` from transport facts the LLM cannot
  forge, runs ASR/OCR-side observation, and invokes the CLI once per
  user turn.
- **Agent/LLM** — extraction and phrasing only: turns a message into
  typed expense *candidates*, maps chat commands to tool calls, and
  renders confirmations from tool results. It holds no credentials.
- **Service layer** (`src/finance/service.py`) — authorization,
  ownership injection, validation, envelope-shaped results.
- **Repository** (`src/finance/repository.py`) — the only DB client;
  every query filtered by the server-derived owner UUID.
- **Supabase PostgreSQL** — canonical storage, RLS, static report RPC.
- **Scheduler** — three cron jobs (§9) calling the same report path.

## 1. Recording from text

1. User sends `bensin 50rb, parkir 2rb`.
2. Adapter builds the envelope from the *actual* inbound message
   (chat id, provider message id, send timestamp in WIB).
3. Agent extracts two candidates with stable `source_item_index` 0/1,
   amounts parsed to integer IDR (deterministic parser for `rb/ribu/k/
   jt/juta`, thousand dots), category from the controlled code list,
   `payment_method` only when stated, `occurred_at` = message time
   unless the user stated another time (`kemarin` resolves against the
   message's WIB date; date-only gets local noon + `user_explicit`).
4. Agent calls: `run_tool.sh --chat-id … --message-id … create
   --payload <CreateExpensesRequest>` (source_message_id must equal the
   envelope message id — the service rejects mismatches).
5. Service: chat allowlist check → owner injection → per-item insert.
6. Repository insert returns the persisted row incl. DB-generated `id`.
7. Only now does the agent confirm, one line per item, format:
   `Tercatat: <desc> · Rp<amount> · <category label> · <WIB date>. ID
   <short-id>.`

If any field is ambiguous (unclear amount, contradictory date), the
flow stops *before* step 4 and the agent asks a clarification question
(§6). Non-expenses (`saldo 50rb`, `tarik tunai 100rb`) are never
recorded; the agent clarifies instead.

## 2. Recording from a receipt photo

1. User sends the photo. Adapter marks `source_type=receipt`,
   `modality=image`; the media file itself is **not** stored in the DB.
2. Vision extraction reads merchant, printed timestamp, line items,
   subtotal/fees, **grand total**, tendered cash, change, order id.
3. Candidate: one expense at the **grand total** (never tendered, never
   change), `occurred_at` = printed timestamp with
   `timestamp_basis=receipt`, `receipt_reference` = printed order id,
   `payment_method=cash` when the receipt shows cash.
4. Steps 4–7 of §1. A receipt with 5 line items still creates exactly
   **one** expense (line-item storage is a future migration, and never
   in addition to the total row).

## 3. Recording from a voice note

1. Adapter transcribes locally (faster-whisper, Indonesian; model
   `small` verified accurate) — audio never leaves the machine and is
   not stored in the DB.
2. The transcript is processed exactly like §1 text, with
   `source_type=voice`. Relative dates anchor to the *original*
   message timestamp, not to when transcription finished.
3. Transcript text is data, not instructions: embedded commands in a
   receipt photo or transcript are ignored (prompt-injection rule).

## 4. Validation and authorization (every operation)

- Envelope `chat_id` must equal the server-configured allowlist value,
  else the operation returns `unauthorized` and touches nothing.
- The owner UUID comes **only** from server configuration
  (`FINANCE_OWNER_USER_ID`, a Supabase Auth user). Models forbid extra
  fields, so a candidate carrying `user_id` fails validation.
- Candidate rules: positive integer `amount_idr`; whitelisted
  `category_code` / `payment_method`; aware timestamps; length caps;
  unique ordered `source_item_index` values.
- Update patches are allowlisted (`amount_idr`, `category_code`,
  `description`, `merchant`, `payment_method`, `occurred_at`,
  `timestamp_basis`); writes to identity/provenance/timestamps are
  rejected by construction.

## 5. Persistence and idempotency (two layers)

- **Layer 1 — exact key.** Unique constraint
  `(user_id, source_platform, source_message_id, source_item_index)`.
  A re-delivered message hits the constraint; the repository fetches
  and returns the previously stored row, and the result status is
  `already_recorded` — never a silent upsert, never an overwrite of a
  later user correction.
- **Layer 2 — probable duplicate.** When a write cannot reuse the
  original key (a receipt re-forwarded as a *new* message; a
  post-clarification write under a derived command key), the service
  first checks the last 24h for same amount + category + similar
  description (≥0.85). A hit returns `needs_clarification` with the
  existing expense id — the user decides; same-amount purchases are
  never blanket-suppressed.
- **Unknown outcomes.** A transport failure during a write yields
  `outcome_unconfirmed`: the agent must re-check by idempotency key
  before retrying and must never send a "saved" confirmation.

## 6. Clarification flow

1. Extraction flags uncertainty (two plausible totals, missing price,
   receipt date contradicting the user's stated date).
2. Nothing is inserted. The agent asks a targeted question with the
   options it actually saw.
3. The user's answer is persisted under a **deterministic derived
   command key** (documented mapping from the pending message), and
   Layer-2 duplicate assessment (§5) runs first, because the answer
   arrives as a new message with a different provider id.

## 7. Update / delete / restore

- Conversational references ("kopi tadi") are resolved to candidate
  rows **after** the authorization check; exactly one match → proceed,
  multiple → ask which (the user can answer with the 8-char short id,
  which the agent resolves to the full UUID first).
- Update: PATCH filtered by `id + user_id + deleted_at IS NULL`; zero
  rows → `not_found`.
- Delete sets `deleted_at=now()` (soft); restore clears it. Replays
  report `already_in_state` distinctly from a fresh change. Hard delete
  does not exist in the tool surface.
- Reports and lists exclude soft-deleted rows by default, always.

## 8. Reports (manual)

1. User: `/bulan_ini`, `/laporan 2026-10-01 2026-10-31`, or "pengeluaran
   minggu ini". Period enum: `today`, `yesterday`, `this_week`,
   `last_week`, `this_month`, `last_month`, `custom`.
2. Service resolves the period against the **trusted message
   timestamp** in WIB: local calendar dates first, then UTC half-open
   bounds `[start_utc, end_utc)`. Weeks start Monday. Custom ranges are
   validated (end ≥ start, ≤ configured max, default 366 days).
3. Repository calls the static RPC `expense_report(owner, start, end,
   category?)` → `{total_idr, transaction_count, by_category[]}`.
   Aggregation happens in SQL; row data is never dumped to the LLM for
   arithmetic.
4. Agent formats: `Laporan 1–31 Okt 2026 (WIB): N transaksi, total
   RpX. Terbesar: <category> RpY.` Zero rows → wording that says *no
   records exist* for the period.

## 9. Scheduled recaps

Three cron jobs deliver to the same chat, all at 23:59 Asia/Jakarta,
all through the §8 path:

- **Daily** — every day, period `today`.
- **Weekly** — Sundays, period `this_week` (the Mon–Sun week just
  ending).
- **Monthly** — scheduled on days 28–31; the job body instructs it to
  stay silent unless today is the month's last day, then period
  `this_month`.

Recaps are sent even for zero-record periods ("belum ada catatan"),
and a tool failure produces a short explicit failure message — never
silence — so a missing recap is itself a signal.

## 10. Errors and statuses

Shared envelope: `{ok, status, data, error{code, message, retryable}}`.
Statuses: `created`, `already_recorded`, `updated`, `deleted`,
`restored`, `found`, `not_found`, `needs_clarification`,
`unauthorized`, `validation_error`, `temporarily_unavailable`,
`outcome_unconfirmed`. The agent phrases results from this envelope
only; it never invents a status or a number.

## 11. Adapting to another bot (adapter checklist)

Keep: schema + migrations, service, repository, gateway pattern,
report RPC, tests, command conventions. Rebuild only the adapter,
which must provide:

1. A **stable sender/chat identifier** for the allowlist check.
2. A **stable per-message id** for the Layer-1 idempotency key (or a
   documented deterministic derivation when the transport lacks one).
3. **Trusted send timestamps** (timezone-aware) for period resolution
   and relative dates.
4. Media handling: image → vision extraction input; audio → local ASR;
   raw media stays out of the database and out of logs.
5. One CLI invocation per user turn + rendering of the result envelope
   (confirmation only on persisted success).

If the new platform has a real credential vault, keep the surrogate
gateway pattern (`gateway.py`): code never holds the DB secret. If it
does not, inject the secret via environment at runtime — never commit
it, never print it.

## 12. Security checklist (summary)

- DB secret only in the vault; `.env` carries non-secret config only.
- RLS on both tables; `anon` has no expense access; `authenticated`
  can only SELECT its own rows; the report RPC executes only for the
  backend role (PUBLIC execute revoked).
- Backend filters by owner on **every** query/mutation anyway (the
  secret key bypasses RLS — RLS is not the backend's guard).
- Logs carry ids and statuses, never full expense rows or media.
- Full rationale: `ARCHITECTURE.md` §4–5, `DATA_MODEL.md` §6,
  `docs/BACKUP.md` for the (not-yet-automated) backup design.
