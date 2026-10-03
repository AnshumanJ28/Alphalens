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
    
    # 0. Fetch FMP if key is available
    fmp_key = os.getenv("FMP_API_KEY")
    if fmp_key:
        print(f"  [Tricker] Using FMP for {ticker} financials...")
        data["alpha_vantage"] = {
            "INCOME_STATEMENT": {"annualReports": []},
            "BALANCE_SHEET": {"annualReports": []},
            "CASH_FLOW": {"annualReports": []}
        }
        try:
            # Income Statement
            r_inc = requests.get(f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}?limit=1&apikey={fmp_key}", timeout=10)
            if r_inc.status_code == 200 and r_inc.json():
                inc_data = r_inc.json()[0]
                data["alpha_vantage"]["INCOME_STATEMENT"]["annualReports"].append({
                    "totalRevenue": str(inc_data.get("revenue", "None")),
                    "grossProfit": str(inc_data.get("grossProfit", "None")),
                    "operatingIncome": str(inc_data.get("operatingIncome", "None")),
                    "netIncome": str(inc_data.get("netIncome", "None")),
                    "ebitda": str(inc_data.get("ebitda", "None")),
                    "interestAndDebtExpense": str(inc_data.get("interestExpense", "None")),
                    "incomeBeforeTax": str(inc_data.get("incomeBeforeTax", "None"))
                })
            # Balance Sheet
            r_bs = requests.get(f"https://financialmodelingprep.com/api/v3/balance-sheet-statement/{ticker}?limit=1&apikey={fmp_key}", timeout=10)
            if r_bs.status_code == 200 and r_bs.json():
                bs_data = r_bs.json()[0]
                data["alpha_vantage"]["BALANCE_SHEET"]["annualReports"].append({
                    "totalAssets": str(bs_data.get("totalAssets", "None")),
                    "totalLiabilities": str(bs_data.get("totalLiabilities", "None")),
                    "totalCurrentAssets": str(bs_data.get("totalCurrentAssets", "None")),
                    "totalCurrentLiabilities": str(bs_data.get("totalCurrentLiabilities", "None")),
                    "inventory": str(bs_data.get("inventory", "None")),
                    "shortLongTermDebtTotal": str(bs_data.get("totalDebt", "None")),
                    "totalShareholderEquity": str(bs_data.get("totalStockholdersEquity", "None")),
                    "retainedEarnings": str(bs_data.get("retainedEarnings", "None")),
                    "cashAndCashEquivalentsAtCarryingValue": str(bs_data.get("cashAndCashEquivalents", "None"))
                })
            # Cash Flow
            r_cf = requests.get(f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}?limit=1&apikey={fmp_key}", timeout=10)
            if r_cf.status_code == 200 and r_cf.json():
                cf_data = r_cf.json()[0]
                data["alpha_vantage"]["CASH_FLOW"]["annualReports"].append({
                    "operatingCashflow": str(cf_data.get("operatingCashFlow", "None")),
                    "capitalExpenditures": str(cf_data.get("capitalExpenditure", "None"))
                })
        except Exception as e:
            print(f"  [Tricker] FMP error: {e}")
            
        # Clean up if FMP failed to populate data
        if not data["alpha_vantage"]["INCOME_STATEMENT"]["annualReports"]:
            del data["alpha_vantage"]

    # 1. Fetch via ScraperAPI REST (Bulletproof Yahoo Timeseries Bypass)
    scraper_key = os.getenv("SCRAPER_API_KEY")
    if scraper_key and "modern_income_stmt" not in data:
        print(f"  [Tricker] Using ScraperAPI REST for {ticker} financials...")
        try:
            import urllib.parse
            ts_url = f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{ticker}?symbol={ticker}&type=annualTotalRevenue,annualGrossProfit,annualOperatingIncome,annualNetIncome,annualEBITDA,annualTotalAssets,annualTotalLiabilities,annualTotalCurrentAssets,annualTotalCurrentLiabilities,annualInventory,annualTotalDebt,annualTotalStockholderEquity,annualRetainedEarnings,annualCashAndCashEquivalents,annualOperatingCashFlow,annualCapitalExpenditure,annualFreeCashFlow&period1=0&period2=9999999999"
            api_url = f"http://api.scraperapi.com?api_key={scraper_key}&url={urllib.parse.quote(ts_url)}"
            r = requests.get(api_url, timeout=60)
            if r.status_code == 200:
                ts = r.json().get("timeseries", {}).get("result", [])
                inc, bs, cf = {}, {}, {}
                
                # Mapping definitions
                inc_map = {"annualTotalRevenue": "Total Revenue", "annualGrossProfit": "Gross Profit", "annualOperatingIncome": "Operating Income", "annualNetIncome": "Net Income", "annualEBITDA": "EBITDA"}
                bs_map = {"annualTotalAssets": "Total Assets", "annualTotalLiabilities": "Total Liabilities Net Minority Interest", "annualTotalCurrentAssets": "Current Assets", "annualTotalCurrentLiabilities": "Current Liabilities", "annualInventory": "Inventory", "annualTotalDebt": "Total Debt", "annualTotalStockholderEquity": "Stockholders Equity", "annualRetainedEarnings": "Retained Earnings", "annualCashAndCashEquivalents": "Cash And Cash Equivalents"}
                cf_map = {"annualOperatingCashFlow": "Operating Cash Flow", "annualCapitalExpenditure": "Capital Expenditure", "annualFreeCashFlow": "Free Cash Flow"}
                
                for item in ts:
                    meta_type = item.get("meta", {}).get("type", [""])[0]
                    if meta_type in item and len(item[meta_type]) > 0:
                        val = item[meta_type][-1].get("reportedValue", {}).get("raw")
                        if val is not None:
                            if meta_type in inc_map: inc[inc_map[meta_type]] = val
                            elif meta_type in bs_map: bs[bs_map[meta_type]] = val
                            elif meta_type in cf_map: cf[cf_map[meta_type]] = val
                
                if inc: data["modern_income_stmt"] = {"latest": inc}
                if bs: data["modern_balance_sheet"] = {"latest": bs}
                if cf: data["modern_cashflow"] = {"latest": cf}
                print(f"  [Tricker] Successfully parsed ScraperAPI REST timeseries for {ticker}")
        except Exception as e:
            print(f"  [Tricker] ScraperAPI REST error: {e}")

    # 2. Fetch Alpha Vantage if key is available (Bypasses Yahoo Finance Cloudflare Blocks)
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
    scraper_key = os.getenv("SCRAPER_API_KEY")
    proxies = None
    if scraper_key:
        print("  [Tricker] Using ScraperAPI proxy to bypass Cloudflare...")
        proxy_url = f"http://scraperapi:{scraper_key}@proxy-server.scraperapi.com:8001"
        proxies = {"http": proxy_url, "https": proxy_url}
        
    session = requests.Session(impersonate="chrome120", proxies=proxies)
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
