# Future Dashboard Roadmap — Design Now, Build Later

**Status: FUTURE / NOT PART OF CURRENT MVP.** This file captures forward compatibility. A coding agent working on WhatsApp MVP **must not** scaffold Next.js, install React packages, or create dashboard routes unless explicitly asked in a separate phase.

## 1. Goal

The future dashboard is a browser UI for the exact same finance data collected through WhatsApp. It should **not** be a second database or a new source of truth. WhatsApp remains a fully supported capture/report interface.

## 2. Recommended future stack

- **Frontend:** Next.js App Router + TypeScript + Tailwind CSS + accessible component library (e.g. shadcn/ui, optional choice).
- **Backend/data:** Supabase Auth + PostgreSQL + RLS. Next.js Server Components/Server Actions or route handlers for validated mutations as needed; no separate FastAPI service by default.
- **Charts:** Lightweight chart library picked at dashboard implementation time.
- **Hosting:** Decide during Phase 3 based on cost and operational requirements, not now.

## 3. Initial information architecture

```text
/dashboard
  Overview
  Transactions
  Reports
  Settings
```

### Overview

- KPI cards: **today**, **this week**, **this month** (IDR, count).
- Line/bar trend by day for selected period.
- Category breakdown with total and share.
- Recent transactions; clear filter period and WIB timezone.
- Source label: recorded expenses only, not estimated account balance.

### Transactions

- Table/list: timestamp WIB, description, merchant, category, amount, payment method, source (`WhatsApp` / `Dashboard`).
- Date range, category, text search, sort, pagination.
- Edit, soft-delete, restore (server-validated; same rules as WhatsApp).
- Create transaction manually through UI as a second input channel.
- CSV export (optional phase 3.1; avoid including raw message IDs or secret metadata by default).

### Reports

- Calendar period selector: today, this week, this month, previous period, custom range.
- Total, count, category totals, trend, optional merchant breakdown after enough data.
- Comparisons (e.g. this month vs last month) must disclose time windows and partial-month comparison caveats.
- Export and scheduled digest can come later; not in MVP.

### Settings

- Display timezone `Asia/Jakarta` (fixed in MVP, future configurable only with proper migration/handling).
- Category names, not codes (optional custom categories in later migration).
- Data export/backup status, account/session settings, privacy/retention controls.
- No WhatsApp sender management UI in the first dashboard; can be future admin functionality.

## 4. Future design principles

- **Mobile-first responsive:** easy to glance on phone, since daily usage is WhatsApp-first.
- **Transparent totals:** period start/end visible, only persisted and non-deleted records included.
- **Single source of truth:** dashboard reads same `expenses` table; updates visible in subsequent WhatsApp reports.
- **No double entry:** dashboard `source_platform='dashboard'` with server-generated stable idempotency key.
- **Secure ownership:** Supabase Auth user ID matches the single user already stored on expenses; RLS keeps each user's rows private; never ship secret key to client.
- **No fake analytics:** empty state is “Belum ada transaksi tercatat,” not synthetic charts.
- **Performance:** index by `user_id` and `occurred_at`; server-side paginated transaction list and aggregated SQL responses; avoid fetching every row to client.
- **Accessibility:** labels, readable contrast, keyboard/assistive tech support; hover must not be sole channel for detail.

## 5. Dashboard wireframe, conceptual only

```text
+-------------------------------------------------------------+
| Expense Tracker                     [Oct 2026 v] [Profile]   |
+----------------+----------------+---------------------------+
| Today          | This Week      | This Month                |
| Rp ...         | Rp ...         | Rp ...                    |
+----------------+----------------+---------------------------+
| Daily Spending Trend         | Spending by Category        |
| (chart; server-calculated)   | (category totals)           |
+------------------------------+-----------------------------+
| Recent Transactions                      [View all]          |
| Date       Merchant          Category       Amount          |
+-------------------------------------------------------------+
```

This is an IA/wireframe **reference**, not a requirement to create a frontend in Phase 1.

## 6. Future API / app boundaries

- `GET /dashboard/summary?start=...&end=...` (server route only if necessary; otherwise use safe query/RPC via Supabase Auth).
- `GET /dashboard/expenses?cursor=...&limit=...` (pagination; query constrained to session owner).
- `POST /dashboard/expenses` (server-validated; idempotency token).
- `PATCH /dashboard/expenses/:id` (owner check + allowed fields).
- `DELETE /dashboard/expenses/:id` (soft-delete).

**These are proposed contracts, not implemented routes.** A browser session must never send caller-controlled `user_id` used for authorization.

## 7. Future milestones

| Milestone | Deliverable | Entry criteria |
|---|---|---|
| D0 | Verify schema supports dashboard Auth and categories | MVP integration tests pass |
| D1 | Next.js Auth, protected route, read-only dashboard | Owner can log in with matching Supabase Auth ID; RLS tests pass |
| D2 | Transactions CRUD, categories, robust pagination | Validated server mutations, end-to-end tests |
| D3 | Comparison reports, charts, exports | Sufficient real records; query performance tested |
| D4 | Optional accounts, budgets, recurring reports | Separate approved PRD, migration plan |

## 8. Things not to assume

Do not infer bank balance from expenses; don't invent income or savings. The MVP has no personal account ledger. Financial summaries are **expense summaries**, not accounting-grade statements or financial advice.
