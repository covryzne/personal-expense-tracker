-- 0003_report_rpc.sql — Restricted, static report aggregation.
-- Source of truth: docs/DATA_MODEL.md §7 + docs/TOOL_CONTRACT.md §9.
-- The function is static SQL with parameters only (no dynamic SQL).
-- EXECUTE is revoked from PUBLIC/anon/authenticated; only service_role
-- (the backend secret key path) may call it.

begin;

create or replace function public.expense_report(
    p_user_id uuid,
    p_start_utc timestamptz,
    p_end_utc timestamptz,
    p_category_code text default null
)
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'total_idr', coalesce(sum(e.amount_idr), 0)::bigint,
    'transaction_count', count(e.id)::bigint,
    'by_category', coalesce(
      (select jsonb_agg(
                jsonb_build_object(
                  'category_code', g.category_code,
                  'amount_idr', g.amount_idr,
                  'count', g.cnt
                )
                order by g.amount_idr desc, g.category_code
              )
       from (
         select e2.category_code,
                sum(e2.amount_idr)::bigint as amount_idr,
                count(*)::bigint as cnt
         from public.expenses e2
         where e2.user_id = p_user_id
           and e2.deleted_at is null
           and e2.occurred_at >= p_start_utc
           and e2.occurred_at < p_end_utc
           and (p_category_code is null or e2.category_code = p_category_code)
         group by e2.category_code
       ) g),
      '[]'::jsonb
    )
  )
  from public.expenses e
  where e.user_id = p_user_id
    and e.deleted_at is null
    and e.occurred_at >= p_start_utc
    and e.occurred_at < p_end_utc
    and (p_category_code is null or e.category_code = p_category_code);
$$;

revoke all on function public.expense_report(uuid, timestamptz, timestamptz, text)
  from public, anon, authenticated;
grant execute on function public.expense_report(uuid, timestamptz, timestamptz, text)
  to service_role;

commit;
