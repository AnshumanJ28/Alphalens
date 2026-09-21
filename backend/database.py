"""
Supabase search-history logging.

Runs as a FastAPI BackgroundTask, scheduled AFTER the response to
POST /api/search has already been prepared, so it never adds latency
to the pipeline-queueing path.

The user's own access token (forwarded from the Authorization header)
is attached to the PostgREST client so that Row Level Security
(auth.uid() = user_id) is enforced exactly as it would be for a
request made directly by the frontend - no service-role key is used
or exposed anywhere in this backend.
"""
from supabase import Client, create_client

from .config import settings


def _client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def log_search(user_id: str, ticker: str, user_jwt: str) -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return
    try:
        client = _client()
        client.postgrest.auth(user_jwt)
        client.table("search_history").insert(
            {"user_id": user_id, "ticker": ticker}
        ).execute()
    except Exception:
        pass
