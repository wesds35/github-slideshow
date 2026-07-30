-- Grants matching Supabase's defaults: the authenticated role can attempt any DML on public
-- tables — row-level security is what actually constrains it.
grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant execute on all functions in schema public to authenticated;
