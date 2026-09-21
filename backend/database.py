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
