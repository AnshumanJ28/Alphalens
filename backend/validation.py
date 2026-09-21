import csv
from pathlib import Path
from typing import Optional

from .config import settings

_VALID_TICKERS: set[str] = set()
_NAME_TO_SYMBOL: dict[str, str] = {}


class TickerCsvError(RuntimeError):
    pass


def _find_field(fieldnames: Optional[list[str]], target: str) -> Optional[str]:
    
    if not fieldnames:
        return None
    for name in fieldnames:
        if name.strip().upper() == target.upper():
            return name
    return None


def load_valid_tickers(csv_path: Optional[str] = None) -> set[str]:
    
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

