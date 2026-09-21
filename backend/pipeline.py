import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .config import settings

_OUTPUT_JSON_RE = re.compile(r"^\[OUTPUT_JSON\]\s*(.+)$")

SECTOR_PEERS: dict[str, list[str]] = {
    "IT":       ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
    "BANKS":    ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"],
    "ENERGY":   ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL"],
    "FMCG":     ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "DABUR"],
    "TELECOM":  ["BHARTIARTL", "IDEA", "INDUSTOWER"],
    "CAPGOODS": ["LT", "BHEL", "SIEMENS", "ABB", "HAVELLS"],
    "PHARMA":   ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "BIOCON"],
    "AUTO":     ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO"],
    "METALS":   ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "COALINDIA"],
    "REALTY":   ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE"],
}


def _resolve_peers(ticker: str) -> list[str]:
    
    base = ticker.replace(".NS", "").replace(".BO", "")
    for _sector, members in SECTOR_PEERS.items():
        if base in members:
            return [f"{p}.NS" for p in members if p != base][:4]
    return []


class PipelineError(Exception):
    def __init__(self, message: str, stderr_tail: str = ""):
        super().__init__(message)
        self.stderr_tail = stderr_tail


def _ensure_cpp_binary_alias(project_root: Path) -> None:
    expected = project_root / "cpp" / "build" / "Release" / "invest_pipeline.exe"
    if expected.exists():
        return
    linux_binary = project_root / "cpp" / "build" / "invest_pipeline"
    if not linux_binary.exists():
        raise PipelineError(
            f"C++ engine binary not found at '{linux_binary}'. Build it first, e.g.: "
            "cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release && "
            "cmake --build cpp/build --config Release"
        )
    expected.parent.mkdir(parents=True, exist_ok=True)
    try:
        expected.symlink_to(linux_binary)
    except OSError:
        shutil.copy2(linux_binary, expected)


def _parse_generation_id(json_filename: str, fallback_ticker: str) -> tuple[str, str]:
    stem = json_filename[:-5] if json_filename.endswith(".json") else json_filename
    if "_" in stem:
        ticker_part, gen_id = stem.rsplit("_", 1)
        return gen_id, ticker_part
    return str(int(time.time())), fallback_ticker


def run_pipeline(ticker: str, skip_yahoo: bool = False) -> dict:
    
    project_root = settings.JAVA_PROJECT_PATH
    _ensure_cpp_binary_alias(project_root)

    peers = _resolve_peers(ticker)

    cmd = [
        settings.JAVA_PATH,
        "-Xms64m",
        "-Xmx128m",
        "-cp",
        settings.JAVA_CLASSPATH,
        "Main",
        ticker,
        *peers,
    ]
    if skip_yahoo:
        cmd.append("--skip-yahoo")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=settings.PIPELINE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"Pipeline timed out for {ticker}") from exc
    except OSError as exc:
        raise PipelineError(f"Failed to start Java pipeline for {ticker}: {exc}") from exc

    json_path: Optional[str] = None
    for line in proc.stdout.splitlines():
        match = _OUTPUT_JSON_RE.match(line.strip())
        if match:
            json_path = match.group(1).strip()

    if proc.returncode != 0 or not json_path:
        stderr_tail = "\n".join(proc.stderr.splitlines()[-20:])
        raise PipelineError(
            f"Pipeline failed for {ticker} (exit code {proc.returncode})",
            stderr_tail=stderr_tail,
        )

    json_file = Path(json_path)
    if not json_file.is_absolute():
        json_file = (project_root / json_file).resolve()

    generation_id, discovered_ticker = _parse_generation_id(json_file.name, ticker)
    pdf_file = json_file.with_suffix(".pdf")

    return {
        "generation_id": generation_id,
        "ticker": discovered_ticker,
        "json_path": str(json_file),
        "pdf_path": str(pdf_file),
    }


def cleanup_generation(generation_id: str, ticker: str, keep_final_pdf: bool = False) -> None:
    
    if not generation_id:
        return

    project_root = settings.JAVA_PROJECT_PATH
    json_dir = project_root / "json"
    reports_dir = settings.PIPELINE_OUTPUT_DIR

    candidates = [
        json_dir / f"{generation_id}_yf_temp.json",
        json_dir / f"{generation_id}_news_temp.json",
        json_dir / f"{generation_id}_peers_temp.json",
        reports_dir / f"{ticker}_{generation_id}.json",
    ]
    if not keep_final_pdf:
        candidates.append(reports_dir / f"{ticker}_{generation_id}.pdf")

    for path in candidates:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
