# Personal Expense Tracker — WhatsApp + AI Agent + Supabase (PoC)

A working proof of concept: record personal expenses by chatting with an
AI agent on WhatsApp (plain text, receipt photo, or voice note) and get
deterministic reports back. PostgreSQL (Supabase) is the only source of
truth — the LLM never writes SQL, never sees the database secret, and
never decides who the data owner is.

**Status: LIVE and verified end-to-end** (Nov 2026). Migrations applied,
integration tests green, real expenses recorded from real chat messages,
scheduled daily/weekly/monthly recaps running.

> This repo is a reference implementation. To rebuild the same system
> behind a different bot/transport, read `docs/WORKFLOW.md` (the full
> workflow) and implement only a new transport adapter — the service,
> repository, schema, and contracts stay as they are.

## Features

- **Record from text** — `kopi 12rb cash`, multi-item in one message
  (`bensin 50rb, parkir 2rb` → two rows with stable item indexes).
- **Record from a receipt photo** — vision extraction; stores the
  *receipt total*, never the tendered cash or the change.
- **Record from a voice note** — local Whisper ASR (faster-whisper),
  Indonesian-tuned; the transcript is then treated like text.
- **Idempotent writes** — a re-delivered message returns
  `already_recorded` instead of a duplicate (unique key on
  owner + platform + message id + item index). A re-forwarded receipt
  with a *new* message id is flagged as a probable duplicate and the
  user decides (24h window, same amount+category, similar description).
- **Corrections** — update amount/category/date/etc. through an
  allowlisted patch; soft-delete and restore; reports always exclude
  soft-deleted rows.
- **Deterministic reports** — daily / weekly (Mon–Sun) / monthly /
  custom ranges computed by a static SQL RPC over WIB calendar
  boundaries (stored as UTC `timestamptz`, half-open intervals).
  Zero-row periods are reported as "no records", never as "you spent 0".
- **Chat commands** — `/catat`, `/hari_ini`, `/minggu_ini`,
  `/bulan_ini`, `/laporan <from> <to>`, `/terbaru`, `/cari`, `/ubah`,
  `/hapus`, `/pulihkan`, `/help` (see `docs/COMMANDS.md`). Natural
  language works too; commands are just shortcuts.
- **Scheduled recaps** — daily 23:59, weekly Sunday 23:59, monthly on
  the last day of the month 23:59 (Asia/Jakarta), delivered to chat.
- **Guardrails** — sender allowlist mapped server-side to one Supabase
  Auth owner UUID; RLS enabled; the LLM cannot inject `user_id`, run
  free-form SQL, or confirm a save before the database returns a
  persisted row ID. Unknown write outcomes surface as
  `outcome_unconfirmed` and are re-checked by idempotency key.

Explicitly **not** in this PoC: web dashboard (roadmap only), income /
balances, budgets, recurring transactions, bank sync, multi-user.

## Architecture

```
WhatsApp chat
    │  text / photo / voice
    ▼
AI agent (extraction only: message → typed candidates)
    │  trusted envelope (chat_id, message_id, sent_at) built by adapter
    ▼
CLI adapter ──► Service layer ──► Repository ──► Supabase PostgREST + RPC
 (per turn)     auth + ownership    owner-filtered   PostgreSQL (RLS)
                     │
                     └─ secret key stays in a credential vault;
                        requests carry a surrogate the platform proxy
                        swaps for the real key on the registered host
    │
    ▼
Confirmation message (only after a persisted row/ID comes back)
```

Key design decisions (details in `docs/ARCHITECTURE.md` and
`docs/ADAPTER.md`):

- The agent's tool mechanism is a **JSON CLI** (`scripts/run_tool.sh`),
  not an SDK: any bot framework that can run a command per message and
  read JSON can host this system.
- Authenticated database calls go through a **credential-vault
  gateway**: code holds only a surrogate; the real secret never lands
  in `.env`, files, or logs.
- Reports are a **restricted static RPC** (`expense_report`), because a
  REST `.select()` is not a GROUP BY API.

## Repository layout

```
src/finance/     tool layer: models, service, repository, gateway,
                 money/date/category utils, confirmations, CLI
migrations/      0001 schema · 0002 RLS+grants · 0003 report RPC
tests/           unit suite + golden fixtures (TEST_PLAN E1–E4)
                 + live integration test (FINANCE_INTEGRATION=1)
docs/            PRD · ARCHITECTURE · DATA_MODEL · TOOL_CONTRACT
                 TEST_PLAN · WORKFLOW · COMMANDS · ADAPTER
                 SETUP · BACKUP · DASHBOARD_ROADMAP
scripts/         setup.sh (idempotent bootstrap) · check_env.sh
                 run_tool.sh (CLI wrapper)
IMPLEMENTATION_PLAN.md   build journal: phases, verified findings,
                         deviations, evidence
.env.example     placeholders only — never commit a real .env
```

Specification reading order (in `docs/`): PRD → ARCHITECTURE →
DATA_MODEL → TOOL_CONTRACT → TEST_PLAN → WORKFLOW → ADAPTER.

## Quickstart (reimplementation)

1. Create a Supabase project; create one Auth user (the owner).
2. Apply `migrations/0001` → `0002` → `0003` in order (SQL Editor or
   CLI) — see `docs/SETUP.md` for the guided, approval-gated flow.
3. Store the project's **secret key** in your platform's credential
   vault (never in chat, never in `.env`); code reaches it through the
   gateway surrogate pattern (`src/finance/gateway.py`).
4. `bash scripts/setup.sh` — creates the venv and a placeholder `.env`;
   fill only non-secret values (`SUPABASE_URL`,
   `FINANCE_OWNER_USER_ID`, `ALLOWED_WHATSAPP_CHAT_ID`).
5. Verify: `.venv/bin/python -m pytest tests/ -q` (unit) and
   `FINANCE_INTEGRATION=1 .venv/bin/python -m pytest
   tests/test_integration_supabase.py -q` (live).
6. Wire your bot: per inbound message, build the trusted envelope,
   extract candidates, call the CLI, send the confirmation only on
   `ok=true`. The exact contract is `docs/TOOL_CONTRACT.md`; the
   step-by-step behavior is `docs/WORKFLOW.md`.

## Testing evidence

- Unit: 35 tests (money parsing `12.500 → 12500`, WIB period math
  incl. month boundary, model guardrails incl. `user_id` injection
  rejection, probable-duplicate detection, golden fixtures E1–E4:
  Oct 2026 = Rp62.000/2 tx, Nov = Rp20.000/2 tx, delete/restore cycle,
  replay = `already_recorded`, unauthorized sender rejected).
- Live: integration test reads the 9 seeded categories; an end-to-end
  smoke run (create → replay → soft-delete → report returns to 0) was
  executed against the real project before the first real expense.

## Known limitations / next steps

- Backup to Google Drive is designed (`docs/BACKUP.md`) but not yet
  automated.
- RLS cross-user test (user B reads nothing) is specified (T22) and
  still pending a second Auth user.
- WhatsApp bridge redelivery semantics are undocumented upstream; the
  two-layer idempotency design assumes probable duplicates are possible
  (see `docs/ADAPTER.md`).
- Next.js dashboard is a later phase reusing the same schema and Auth
  user (`docs/DASHBOARD_ROADMAP.md`).
