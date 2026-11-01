-- 0002_rls_grants.sql — Row Level Security + least-privilege grants.
-- Source of truth: docs/DATA_MODEL.md §6.
-- Notes: the backend secret key bypasses RLS; the tool layer independently
-- validates the WhatsApp sender and filters by server-derived user_id.
-- Browser roles get read-only access to their own rows (future dashboard);
-- no browser writes in MVP.

begin;

alter table public.expense_categories enable row level security;
alter table public.expenses enable row level security;

-- Categories: readable by signed-in users, never writable from the browser.
drop policy if exists expense_categories_read on public.expense_categories;
create policy expense_categories_read on public.expense_categories
  for select to authenticated
  using (true);

-- Expenses: owner can read only their own rows.
drop policy if exists expenses_owner_read on public.expenses;
create policy expenses_owner_read on public.expenses
  for select to authenticated
  using (user_id = (select auth.uid()));

-- Least-privilege grants: clear defaults, then grant exactly what is needed.
revoke all on table public.expense_categories from anon, authenticated, public;
revoke all on table public.expenses from anon, authenticated, public;
grant select on table public.expense_categories to authenticated;
grant select on table public.expenses to authenticated;
-- The backend uses the secret key (service_role), which bypasses RLS and
-- holds its own grants; no INSERT/UPDATE/DELETE is granted to browser roles.

commit;
