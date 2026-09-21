"""
Ticker validation with Name-to-Ticker resolution.

The CSV is loaded exactly once (at FastAPI startup) into two in-memory
data structures:
  1. A set of valid ticker symbols (e.g. "INFY.NS") for O(1) membership checks.
  2. A dict mapping lowercased company names to symbols for fuzzy resolution
     (e.g. "infosys limited" -> "INFY").

This allows users to search by either the official ticker symbol OR by
the company name.
"""
import csv
from pathlib import Path
from typing import Optional

from .config import settings

_VALID_TICKERS: set[str] = set()
_NAME_TO_SYMBOL: dict[str, str] = {}


class TickerCsvError(RuntimeError):
    pass


def _find_field(fieldnames: Optional[list[str]], target: str) -> Optional[str]:
    """Find a CSV header field by case-insensitive match."""
    if not fieldnames:
        return None
    for name in fieldnames:
        if name.strip().upper() == target.upper():
            return name
    return None


def load_valid_tickers(csv_path: Optional[str] = None) -> set[str]:
    """
    Loads the NSE/BSE equity CSV (e.g. EQUITY_L.csv) once and builds:
      - An in-memory set of valid, normalized tickers (SYMBOL + ".NS").
      - A name-to-symbol mapping for fuzzy resolution.
    """
    global _VALID_TICKERS, _NAME_TO_SYMBOL
    csv_path_str = csv_path or settings.TICKER_CSV_PATH
    if not csv_path_str:
        csv_path_str = "backend/fixtures/EQUITY_L.csv"
    
    path = Path(csv_path_str).resolve()
    if not path.is_file():
        raise TickerCsvError(
            f"Ticker CSV not found at '{path}'. Set TICKER_CSV_PATH to the "
            "NSE EQUITY_L.csv file (or BSE equivalent) before starting the backend."
        )

    tickers: set[str] = set()
    name_map: dict[str, str] = {}

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        symbol_field = _find_field(reader.fieldnames, "SYMBOL")
        name_field = _find_field(reader.fieldnames, "NAME OF COMPANY")

        if not symbol_field:
            symbol_field = reader.fieldnames[0] if reader.fieldnames else None

        for row in reader:
            symbol = (row.get(symbol_field) or "").strip().upper() if symbol_field else ""
            if symbol:
                tickers.add(f"{symbol}.NS")
                if name_field:
                    name = (row.get(name_field) or "").strip()
                    if name:
                        name_map[name.lower()] = symbol

    _VALID_TICKERS = tickers
    _NAME_TO_SYMBOL = name_map
    return _VALID_TICKERS


def _resolve_name_to_ticker(raw: str) -> Optional[str]:
    """
    Try to resolve a company name to an official ticker symbol.
    Prioritizes:
    1. Exact Match ("infosys limited")
    2. Prefix Match ("infosys" -> "infosys limited")
    3. Partial Match ("infosys" -> "hcl infosystems")
    """
    query = raw.strip().lower()
    if not query:
        return None

    if query in _NAME_TO_SYMBOL:
        return f"{_NAME_TO_SYMBOL[query]}.NS"

    for name, symbol in _NAME_TO_SYMBOL.items():
        if name.startswith(query):
            return f"{symbol}.NS"

    for name, symbol in _NAME_TO_SYMBOL.items():
        if query in name:
            return f"{symbol}.NS"

    return None


def normalize_ticker(raw: str) -> str:
    """
    Normalize user input into an official ticker.
    1. Try as a direct ticker symbol (e.g. "INFY" -> "INFY.NS").
    2. If not found, try resolving as a company name (e.g. "Infosys" -> "INFY.NS").
    """
    if raw is None:
        return ""

    cleaned = raw.strip().upper()

    if cleaned in _VALID_TICKERS:
        return cleaned
    if f"{cleaned}.NS" in _VALID_TICKERS:
        return f"{cleaned}.NS"

    resolved = _resolve_name_to_ticker(raw)
    if resolved:
        return resolved

    return cleaned


def is_valid_ticker(ticker: str) -> bool:
    return ticker in _VALID_TICKERS


def ticker_count() -> int:
    return len(_VALID_TICKERS)

