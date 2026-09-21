-- Run this once in the Supabase SQL editor for your project.

create table if not exists public.search_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    ticker text not null,
    timestamp timestamptz not null default now()
);

create index if not exists search_history_user_id_idx
    on public.search_history (user_id);

alter table public.search_history enable row level security;

-- Users may insert only rows where they are the owner. The backend
-- authenticates each insert with the user's own JWT (see
-- backend/database.py), so this is enforced for backend-originated
-- inserts exactly the same as for any direct client insert.
create policy "search_history_insert_own"
    on public.search_history
    for insert
    with check (auth.uid() = user_id);

-- Users may read only their own history. The React frontend queries
-- this table directly via @supabase/supabase-js; FastAPI never exposes
-- a GET /api/history endpoint.
create policy "search_history_select_own"
    on public.search_history
    for select
    using (auth.uid() = user_id);
