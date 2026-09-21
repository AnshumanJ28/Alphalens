"""
FastAPI web wrapper around the existing research engine.

Flow for POST /api/search:
    JWT verification -> ticker normalization -> ticker set membership
    check -> Celery task queued -> task_id returned immediately.

The HTTP request path never runs Java/C++ directly; only the Celery
worker (backend.worker.run_research_task) does that.
"""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import database, pipeline, validation
from .auth import AuthenticatedUser, get_current_user
from .config import settings
from .worker import (
    create_task_record,
    delete_task_record,
    get_task_record,
    is_ticker_cached,
    run_research_task_fast,
    run_research_task_slow,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validation.load_valid_tickers()
    yield


app = FastAPI(title="Investment Research Agent - Web Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


class SearchRequest(BaseModel):
    ticker: str


class SearchResponse(BaseModel):
    task_id: str


class StatusResponse(BaseModel):
    task_id: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    error: Optional[str] = None


def _get_owned_record(task_id: str, user: AuthenticatedUser) -> dict:
    record = get_task_record(task_id)
    if record is None or record["user_id"] != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return record


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse, status_code=status.HTTP_202_ACCEPTED)
def search(
    payload: SearchRequest,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
) -> SearchResponse:
    ticker = validation.normalize_ticker(payload.ticker)
    if not validation.is_valid_ticker(ticker):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown ticker")

    task_id = str(uuid.uuid4())

    task_func = run_research_task_fast if is_ticker_cached(ticker) else run_research_task_slow

    try:
        create_task_record(task_id, user.user_id, ticker)
        task_func.apply_async(args=[task_id, user.user_id, ticker], task_id=task_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not queue the search right now",
        )

    background_tasks.add_task(database.log_search, user.user_id, ticker, user.raw_token)

    return SearchResponse(task_id=task_id)


@app.get("/api/status/{task_id}", response_model=StatusResponse)
def get_status(task_id: str, user: AuthenticatedUser = Depends(get_current_user)) -> StatusResponse:
    record = _get_owned_record(task_id, user)
    return StatusResponse(task_id=task_id, status=record["status"], error=record.get("error"))


@app.get("/api/result/{task_id}")
def get_result(task_id: str, user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    record = _get_owned_record(task_id, user)

    if record["status"] == "FAILED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search failed")
    if record["status"] != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not ready yet")

    pdf_path = Path(record["pdf_path"]) if record.get("pdf_path") else None
    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result no longer available")

    data = pdf_path.read_bytes()

    pipeline.cleanup_generation(record["generation_id"], record["ticker"], keep_final_pdf=False)
    delete_task_record(task_id)

    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{record["ticker"]}.pdf"'},
    )
