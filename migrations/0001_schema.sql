-- 0001_schema.sql — Personal Expense Tracker core schema.
-- Source of truth: docs/DATA_MODEL.md §3. Apply order: 0001 -> 0002 -> 0003.
-- Idempotent where practical (IF NOT EXISTS on tables/indexes).

begin;

create table if not exists public.expense_categories (
    code text primary key,
    label_id text not null,
    is_active boolean not null default true
);

insert into public.expense_categories (code, label_id) values
 ('food_drink', 'Makanan & Minuman'),
 ('transport', 'Transportasi'),
 ('groceries', 'Belanja Kebutuhan'),
 ('bills', 'Tagihan'),
 ('shopping', 'Belanja Lainnya'),
 ('health', 'Kesehatan'),
 ('entertainment', 'Hiburan'),
 ('education', 'Pendidikan'),
 ('other', 'Lainnya')
on conflict (code) do nothing;

create table if not exists public.expenses (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id),
    occurred_at timestamptz not null,
    amount_idr bigint not null check (amount_idr > 0),
    category_code text not null references public.expense_categories(code),
    description text not null check (length(btrim(description)) between 1 and 500),
    merchant text check (merchant is null or length(merchant) <= 200),
    payment_method text not null default 'unknown'
      check (payment_method in
        ('cash','qris','bank_transfer','debit_card','credit_card','e_wallet','unknown')),
    source_type text not null
      check (source_type in ('text','voice','receipt','dashboard')),
    source_platform text not null
      check (source_platform in ('whatsapp','dashboard')),
    source_message_id text not null check (length(source_message_id) between 1 and 255),
    source_item_index integer not null default 0 check (source_item_index >= 0),
    timestamp_basis text not null
      check (timestamp_basis in ('receipt','user_explicit','message_time')),
    receipt_reference text check (receipt_reference is null or length(receipt_reference) <= 200),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deleted_at timestamptz,
    constraint expenses_source_unique unique
      (user_id, source_platform, source_message_id, source_item_index)
);

create index if not exists expenses_user_occurred_idx
    on public.expenses (user_id, occurred_at desc)
    where deleted_at is null;
create index if not exists expenses_user_category_occurred_idx
    on public.expenses (user_id, category_code, occurred_at desc)
    where deleted_at is null;

-- updated_at maintained by the database, never by client clocks.
create or replace function public.expenses_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists expenses_set_updated_at_trg on public.expenses;
create trigger expenses_set_updated_at_trg
  before update on public.expenses
  for each row execute function public.expenses_set_updated_at();

commit;
