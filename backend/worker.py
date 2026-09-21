"""
Celery task + task metadata store.

Per the "do not build a second database" constraint, task state
(status, ownership, generationId, result path) lives entirely in
Redis - the same broker already required for Celery. This also lets
GET /api/status/{task_id} answer instantly even for a task that is
still PENDING and hasn't been picked up by the worker yet.
"""
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import redis as redis_lib

from . import pipeline
from .celery_app import celery_app
from .config import settings

redis_client = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)

IST = timezone(timedelta(hours=5, minutes=30))


def _cache_key(ticker: str) -> str:
    return f"ticker_cache:{ticker}"


def _seconds_until_next_9am_ist() -> int:
    """Return the number of seconds from now until the next 9:00 AM IST."""
    now = datetime.now(IST)
    next_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now >= next_9am:
        next_9am += timedelta(days=1)
    return int((next_9am - now).total_seconds())


def mark_ticker_cached(ticker: str) -> None:
    """Mark a ticker as cached in Redis, expiring at the next 9:00 AM IST."""
    ttl = _seconds_until_next_9am_ist()
    redis_client.set(_cache_key(ticker), "1", ex=ttl)


def is_ticker_cached(ticker: str) -> bool:
    """Check if a ticker has valid cached data (generated after the last 9 AM)."""
    return redis_client.exists(_cache_key(ticker)) == 1


def _meta_key(task_id: str) -> str:
    return f"task_meta:{task_id}"


def create_task_record(task_id: str, user_id: str, ticker: str) -> None:
    record = {
        "task_id": task_id,
        "user_id": user_id,
        "ticker": ticker,
        "status": "PENDING",
        "generation_id": None,
        "pdf_path": None,
        "error": None,
        "created_at": time.time(),
    }
    redis_client.set(_meta_key(task_id), json.dumps(record), ex=settings.TASK_TTL_SECONDS)


def get_task_record(task_id: str) -> Optional[dict]:
    raw = redis_client.get(_meta_key(task_id))
    return json.loads(raw) if raw else None


def delete_task_record(task_id: str) -> None:
    redis_client.delete(_meta_key(task_id))


def _update_task_record(task_id: str, **fields) -> None:
    record = get_task_record(task_id)
    if record is None:
        return
    record.update(fields)
    redis_client.set(_meta_key(task_id), json.dumps(record), ex=settings.TASK_TTL_SECONDS)


def _run_task(task_id: str, user_id: str, ticker: str, skip_yahoo: bool) -> dict:
    _update_task_record(task_id, status="PROCESSING")

    try:
        result = pipeline.run_pipeline(ticker, skip_yahoo=skip_yahoo)
    except pipeline.PipelineError as exc:
        _update_task_record(task_id, status="FAILED", error=str(exc))
        return {"status": "FAILED", "error": str(exc)}
    except Exception:
        _update_task_record(task_id, status="FAILED", error="Internal pipeline error")
        raise

    generation_id = result["generation_id"]
    try:
        pipeline.cleanup_generation(generation_id, result["ticker"], keep_final_pdf=True)
    except Exception:
        pass  # cleanup failures must never mask a successful pipeline run

    mark_ticker_cached(ticker)

    _update_task_record(
        task_id,
        status="COMPLETED",
        generation_id=generation_id,
        pdf_path=result["pdf_path"],
    )
    return {"status": "COMPLETED", "generation_id": generation_id}


@celery_app.task(name="backend.worker.run_research_task_fast", bind=True)
def run_research_task_fast(self, task_id: str, user_id: str, ticker: str) -> dict:
    return _run_task(task_id, user_id, ticker, skip_yahoo=True)


@celery_app.task(name="backend.worker.run_research_task_slow", bind=True)
def run_research_task_slow(self, task_id: str, user_id: str, ticker: str) -> dict:
    return _run_task(task_id, user_id, ticker, skip_yahoo=False)

