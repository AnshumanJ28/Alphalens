import sys
import os
import json
from curl_cffi import requests
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
def fetch_single_ticker(ticker, session):
    modules = "financialData,defaultKeyStatistics,summaryDetail,incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,price,summaryProfile"
    crumb_resp = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10)
    crumb = crumb_resp.text.strip()
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}&crumb={crumb}"
    data = {}
    
    # 1. Fetch Alpha Vantage if key is available (Bypasses Yahoo Finance Cloudflare Blocks)
    av_key = os.getenv("ALPHAVANTAGE_KEY")
    if av_key:
        print(f"  [Tricker] Using Alpha Vantage for {ticker} financials...")
        data["alpha_vantage"] = {}
        for func in ["INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"]:
            try:
                av_url = f"https://www.alphavantage.co/query?function={func}&symbol={ticker}&apikey={av_key}"
                r = requests.get(av_url, timeout=10)
                if r.status_code == 200:
                    data["alpha_vantage"][func] = r.json()
            except Exception as e:
                print(f"  [Tricker] AV {func} error: {e}")

    # 2. Fetch Yahoo quoteSummary
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            yf_data = resp.json()
            data.update(yf_data)
    except: pass
    try:
        yf_ticker = yf.Ticker(ticker, session=session)
        bs = yf_ticker.balance_sheet
        print(f"  [Tricker] balance_sheet empty: {bs.empty}")
        if not bs.empty:
            data["modern_balance_sheet"] = {"latest": bs.iloc[:, 0].dropna().to_dict()}
        inc = yf_ticker.income_stmt
        print(f"  [Tricker] income_stmt empty: {inc.empty}")
        if not inc.empty:
            data["modern_income_stmt"] = {"latest": inc.iloc[:, 0].dropna().to_dict()}
        cf = yf_ticker.cashflow
        if not cf.empty:
            data["modern_cashflow"] = {"latest": cf.iloc[:, 0].dropna().to_dict()}
            
    except Exception as e:
        print(f"  [Tricker] Error getting yfinance data for {ticker}: {e}")
        
    # Validation: If we have no AV data and no YF data, it's totally empty
    has_av = "alpha_vantage" in data and "INCOME_STATEMENT" in data["alpha_vantage"]
    has_yf = "modern_income_stmt" in data
    
    if not has_av and not has_yf:
        print(f"  [Tricker] WARNING: Could not fetch financial statements for {ticker} from any source.")
    return ticker, data
def fetch_yahoo_data(generation_id, tickers):
    session = requests.Session(impersonate="chrome120")
    try: session.get("https://fc.yahoo.com", timeout=10)
    except: pass
    os.makedirs("json", exist_ok=True)
    peers_data = {}
    print(f"  [Tricker] Stealth session established. Fetching {len(tickers)} tickers concurrently...")
    with ThreadPoolExecutor(max_workers=len(tickers)) as executor:
        futures = {executor.submit(fetch_single_ticker, t, session): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                t, data = future.result()
                if ticker == tickers[0]:
                    has_av = "alpha_vantage" in data and "INCOME_STATEMENT" in data["alpha_vantage"]
                    has_yf = "modern_income_stmt" in data
                    
                    if not has_av and not has_yf:
                        print(f"  [Tricker] FATAL: Failed to download financial statements for {ticker} (Yahoo Finance may be blocking the IP).")
                        sys.exit(1)
                    with open(f"json/{generation_id}_yf_temp.json", "w", encoding="utf-8") as f:
                        json.dump(data, f)
                    os.makedirs(f"cache/{ticker}", exist_ok=True)
                    with open(f"cache/{ticker}/yf_cache.json", "w", encoding="utf-8") as f:
                        json.dump(data, f)
                    print(f"  [Tricker] Downloaded complete main data for {ticker}")
                else:
                    peers_data[ticker] = data
                    print(f"  [Tricker] Downloaded complete peer data for {ticker}")
            except Exception as e:
                print(f"  [Tricker] Failed to process {ticker}: {e}")
    if peers_data:
        with open(f"json/{generation_id}_peers_temp.json", "w", encoding="utf-8") as f:
            json.dump(peers_data, f)
        main_ticker = tickers[0]
        os.makedirs(f"cache/{main_ticker}", exist_ok=True)
        with open(f"cache/{main_ticker}/peers_cache.json", "w", encoding="utf-8") as f:
            json.dump(peers_data, f)
        print(f"  [Tricker] Saved all peers to peers_temp.json and peers_cache.json")
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tricker.py <generation_id> <main_ticker> [peer1] [peer2] ...")
        sys.exit(1)
    gen_id = sys.argv[1]
    tickers = sys.argv[2:]
    fetch_yahoo_data(gen_id, tickers)
