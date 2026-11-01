# AGENTS.md — Instructions for Coding Agents

This repository is for a **Muse/WhatsApp personal expense tracker** using **Supabase PostgreSQL**. The docs in `README.md` and the linked specification pack are normative.

## Mandatory workflow

1. **Read all specifications** in README order; note disagreements or feasibility blockers before writing production code.
2. **Inspect the actual workspace** (files, Muse integration contracts, Python environment, WhatsApp metadata, ASR/OCR existing tools) first. Do not fabricate APIs, methods, credentials, folders, installed packages, provider events, or a finished integration.
3. Provide an **implementation plan** with phases, file layout, schema/migration strategy, auth approach, report method, and test method.
4. Implement the smallest **Phase 1** solution after user approval/existing instruction to implement; do not silently build a dashboard or unrelated modules.
5. Use Pydantic, restricted actions, Supabase client or verified equivalent, versioned migrations, safe secrets, tests, and reproducible commands.
6. Verify with unit + isolated DB integration tests and clearly distinguish mocks from real WhatsApp/Muse testing.
7. Report actual pass/fail evidence, blockers, security checks, and unimplemented work.

## Hard invariants

- Only source of truth for amounts is Supabase PostgreSQL; no LLM memory, WhatsApp chat history, spreadsheet, or SQLite mirror as canonical storage.
- LLM cannot choose `user_id`, make free-form SQL queries, change database schema, or read credentials.
- Only authorized WhatsApp sender can access data, mapped to server-owned Auth user ID.
- Always enable RLS and test grants; service secret bypasses RLS, so keep server-side checks.
- All amounts positive integer IDR, timestamps `timestamptz`, reports using WIB boundaries.
- One receipt = one expense at grand total. A multi-purchase message can create several records.
- Must support idempotency by `(user_id, source_platform, source_message_id, source_item_index)` and safe replay.
- Persisted ID must be returned and verified before telling WhatsApp that an expense is saved.
- Ambiguous amount/date or transaction target => clarification, not hallucination.
- Soft-delete instead of irreversible deletion; active reports exclude deleted rows.
- Never install Whisper again without verifying whether existing Muse ASR already works.
- No raw photos/audio stored in Supabase by default; keep sensitive content out of logs.
- Do not create a Next.js app, FastAPI app, n8n workflow, or multi-user features in Phase 1.

## Prioritization under constraints

- If Muse SDK/tool calling is undocumented/inaccessible: implement portable service/repository and tests, write the adapter interface, and label live integration as `BLOCKED`. Do not invent the connector.
- If secrets/project are not available: implement migration + simulated integration tests; show exact secure setup needs, never request secrets in normal chat.
- If migration cannot be run safely: generate and test in isolated DB, ask for explicit production deployment approval. Do not mutate a live project without authorization.
- Prefer small focused files and deterministic business logic. Avoid unnecessary abstractions, queues, distributed services, or whole new dashboards.

## Deliverables when implementation is requested

- Source code + `.env.example` (placeholders, not secrets).
- Versioned Supabase SQL migrations and seed categories.
- Automated unit/integration tests + golden fixtures from `TEST_PLAN.md`.
- Short setup guide for actual Muse tool registration once integration contract is verified.
- Security/privacy/backup checklist and report of what was actually tested.
- No fabricated demo data labeled as the user's real transactions.
