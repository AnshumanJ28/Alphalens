"""
Centralized backend configuration.

Nothing in this file touches or modifies the existing engine. It only
reads environment variables (from the repo-root .env, which already
exists, is gitignored, and is never committed - so loading it here is
not a change to the repository) and exposes typed settings for the
rest of the backend package.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/ lives directly under the repository root.
_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_PROJECT_ROOT = _BACKEND_DIR.parent

# Load the existing repo-root .env (already used by the C++/Java engine
# for NEWSAPI_KEY, etc). This file is gitignored - reading/extending it
# locally is not a modification of tracked repository content.
load_dotenv(_DEFAULT_PROJECT_ROOT / ".env")
# Optionally allow a backend-only .env to layer additional vars on top
# without ever touching the root one.
load_dotenv(_BACKEND_DIR / ".env", override=False)


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings:
    # --- Supabase / Auth ---
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    SUPABASE_JWT_AUDIENCE: str | None = os.getenv("SUPABASE_JWT_AUDIENCE") or None

    # --- Redis / Celery ---
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = _split_csv(os.getenv("ALLOWED_ORIGINS", ""))

    # --- Existing engine integration ---
    JAVA_PATH: str = os.getenv("JAVA_PATH", "java")
    JAVA_PROJECT_PATH: Path = Path(
        os.getenv("JAVA_PROJECT_PATH", str(_DEFAULT_PROJECT_ROOT))
    ).resolve()
    # Matches the existing README's documented run command:
    #   java -cp "java/bin;java/lib/*" Main <TICKER> (or : on Unix)
    JAVA_CLASSPATH: str = os.getenv("JAVA_CLASSPATH", f"java/bin{os.pathsep}java/lib/*")
    PIPELINE_OUTPUT_DIR: Path = Path(
        os.getenv("PIPELINE_OUTPUT_DIR", str(_DEFAULT_PROJECT_ROOT / "reports"))
    ).resolve()
    PIPELINE_TIMEOUT_SECONDS: int = int(os.getenv("PIPELINE_TIMEOUT_SECONDS", "60"))

    # --- Ticker validation ---
    TICKER_CSV_PATH: str = os.getenv(
        "TICKER_CSV_PATH", str(_BACKEND_DIR / "fixtures" / "EQUITY_L.csv")
    )

    # --- Task metadata TTL (Redis key expiry, seconds) ---
    TASK_TTL_SECONDS: int = int(os.getenv("TASK_TTL_SECONDS", "3600"))


settings = Settings()
