#!/usr/bin/env python3
"""
Japan-equity data fetcher for trading-analysis-jp.

Usage:
  python scripts/fetch_jp_market_data.py --ticker TYO:6702 --type technical --date 2026-07-29
  python scripts/fetch_jp_market_data.py --ticker TYO:6702 --type fundamentals --date 2026-07-29
  python scripts/fetch_jp_market_data.py --ticker TYO:6702 --type news --date 2026-07-29
  python scripts/fetch_jp_market_data.py --ticker TYO:6702 --type macro --date 2026-07-29

Environment variables (read from .env):
  JQUANTS_API_KEY  - J-Quants API v2 dashboard key (x-api-key)
  FRED_API_KEY     - FRED API key (optional, used for Japanese-rate validation)
"""
import argparse
import io
import math
import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

from market_data_utils import (
    compute_technicals,
    dump_json,
    make_indicator_summary,
    make_price_summary,
    normalize_yfinance_news,
    recent_closes,
    safe,
)

load_dotenv()

JQUANTS_API_KEY = os.getenv("JQUANTS_API_KEY", "").strip()
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()

JQUANTS_BASE = "https://api.jquants.com/v2"
BOJ_BASE = "https://www.stat-search.boj.or.jp/api/v1"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
MOF_JGB_CSV = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"


class JQuantsError(Exception):
    pass


def _jquants_headers():
    if not JQUANTS_API_KEY:
        raise JQuantsError("JQUANTS_API_KEY is not set in .env")
    return {"x-api-key": JQUANTS_API_KEY}


def _jquants_get(path: str, params: dict | None = None) -> dict:
    url = f"{JQUANTS_BASE}{path}"
    resp = requests.get(url, headers=_jquants_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _yf_ticker_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Fetch yfinance history and standardise columns."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(start=start.isoformat(), end=end.isoformat())
    except Exception as exc:
        return pd.DataFrame()
    if hist.empty:
        return pd.DataFrame()
    hist = hist.rename(columns={
        "Open": "Open", "High": "High", "Low": "Low",
        "Close": "Close", "Volume": "Volume",
    })
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    return hist[["Open", "High", "Low", "Close", "Volume"]]


def normalize_ticker(ticker: str) -> dict:
    """Return {input, jquants, yfinance} forms."""
    t = ticker.strip().upper()
    if t.startswith("TYO:"):
        code = t.split(":", 1)[1].strip()
        return {"input": ticker, "jquants": code.lstrip("0") or code, "yfinance": f"{code}.T"}
    if t.endswith(".T"):
        code = t[:-2]
        return {"input": ticker, "jquants": code.lstrip("0") or code, "yfinance": t}
    if t.isdigit():
        # J-Quants accepts 4-digit issue codes; internal 5-digit codes end in 0.
        code = t[:4] if len(t) == 5 else t
        return {"input": ticker, "jquants": code.lstrip("0") or code, "yfinance": f"{code}.T"}
    raise ValueError(f"Unsupported Japan ticker format: {ticker}")


# ---------------------------------------------------------------------------
# J-Quants data helpers
# ---------------------------------------------------------------------------

def _parse_coverage_window(message: str) -> tuple[date | None, date | None]:
    """Extract 'YYYY-MM-DD ~ YYYY-MM-DD' coverage window from a J-Quants error."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", message)
    if not m:
        return None, None
    return date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))


def _jquants_bars_raw(code: str, start: date, end: date) -> list[dict]:
    """Call /equities/bars/daily, retrying if the requested range exceeds subscription."""
    params = {"code": code, "from": start.isoformat(), "to": end.isoformat()}
    try:
        payload = _jquants_get("/equities/bars/daily", params)
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 400:
            raise
        msg = exc.response.text or ""
        cov_start, cov_end = _parse_coverage_window(msg)
        if cov_end is None:
            raise
        if end > cov_end:
            params["to"] = cov_end.isoformat()
        if start < cov_start:
            params["from"] = cov_start.isoformat()
        payload = _jquants_get("/equities/bars/daily", params)

    data = payload.get("data", [])
    next_key = payload.get("pagination_key")
    while next_key:
        page = _jquants_get("/equities/bars/daily", {**params, "pagination_key": next_key})
        data.extend(page.get("data", []))
        next_key = page.get("pagination_key")
    return data


def fetch_jquants_bars(code: str, start: date, end: date) -> pd.DataFrame:
    """Daily adjusted OHLCV from J-Quants v2 /equities/bars/daily."""
    data = _jquants_bars_raw(code, start, end)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()

    open_col = df.get("AdjO") if "AdjO" in df.columns else df.get("O", df.get("Open"))
    high_col = df.get("AdjH") if "AdjH" in df.columns else df.get("H", df.get("High"))
    low_col = df.get("AdjL") if "AdjL" in df.columns else df.get("L", df.get("Low"))
    close_col = df.get("AdjC") if "AdjC" in df.columns else df.get("C", df.get("Close"))
    vol_col = df.get("AdjVo") if "AdjVo" in df.columns else df.get("Vo", df.get("Volume"))

    out = pd.DataFrame({
        "Open": open_col,
        "High": high_col,
        "Low": low_col,
        "Close": close_col,
        "Volume": vol_col,
    })
    return out


def fetch_jquants_fins_summary(code: str) -> list[dict]:
    return _jquants_get("/fins/summary", {"code": code}).get("data", [])


def fetch_jquants_master(code: str) -> dict | None:
    """Issue master metadata (optional, currently unused)."""
    rows = _jquants_get("/equities/master", {"code": code}).get("data", [])
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Technicals
# ---------------------------------------------------------------------------

def fetch_technical(ticker: str, as_of: date) -> dict:
    norm = normalize_ticker(ticker)
    code = norm["jquants"]
    yf_ticker = norm["yfinance"]

    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=520)

    jq_bars = fetch_jquants_bars(code, start, end)
    yf_bars = _yf_ticker_history(yf_ticker, start, end)

    if jq_bars.empty and yf_bars.empty:
        return {"error": f"No price data for {ticker}"}

    # Prefer J-Quants adjusted data; fill any gaps with yfinance.
    if jq_bars.empty:
        combined = yf_bars
    elif yf_bars.empty:
        combined = jq_bars
    else:
        combined = jq_bars.combine_first(yf_bars)

    combined = combined.dropna(subset=["Close"])
    if combined.empty:
        return {"error": f"No price data for {ticker}"}

    indicators = compute_technicals(combined)
    close = combined["Close"]

    return {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "last_trading_day": close.index[-1].date().isoformat(),
        "price": make_price_summary(close),
        "indicators": make_indicator_summary(indicators),
        "recent_closes": recent_closes(close),
        "data_sources": {
            "jquants_dates": len(jq_bars),
            "yfinance_dates": len(yf_bars),
            "combined_dates": len(combined),
        },
    }


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def fetch_news(ticker: str, as_of: date) -> dict:
    norm = normalize_ticker(ticker)
    tk = yf.Ticker(norm["yfinance"])
    items = normalize_yfinance_news(tk.news)
    return {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "news_count": len(items),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

GROWTH_METRICS = {
    "Sales": "sales_growth",
    "OP": "operating_profit_growth",
    "NP": "net_income_growth",
    "EPS": "eps_growth",
}


def _to_float(val):
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _sort_key(entry: dict):
    """Best-effort sort key for J-Quants summary entries (newest last)."""
    disclosed = entry.get("DisclosedDate") or entry.get("DiscloseDate") or entry.get("DiscDate")
    if disclosed:
        try:
            return (0, datetime.fromisoformat(str(disclosed)[:10]).date())
        except Exception:
            pass
    year = entry.get("FiscalYear") or entry.get("Year") or entry.get("CurFYSt", "")[:4] or 0
    period = entry.get("FiscalPeriod") or entry.get("Period") or entry.get("CurPerType", "")
    order = {"1Q": 1, "2Q": 2, "3Q": 3, "4Q": 4, "FY": 5, "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    return (1, int(year), order.get(str(period).upper(), 0))


def _compute_growth_rates(summary: list[dict]) -> list[dict]:
    if not summary:
        return summary
    sorted_rows = sorted(summary, key=_sort_key)
    for i in range(1, len(sorted_rows)):
        prev = sorted_rows[i - 1]
        cur = sorted_rows[i]
        for metric, growth_key in GROWTH_METRICS.items():
            prev_val = _to_float(prev.get(metric))
            cur_val = _to_float(cur.get(metric))
            if prev_val is not None and cur_val is not None and prev_val != 0:
                cur[growth_key] = round((cur_val / prev_val - 1) * 100, 2)
    # Return newest-first for the caller.
    return list(reversed(sorted_rows))


def fetch_fundamentals(ticker: str, as_of: date) -> dict:
    norm = normalize_ticker(ticker)
    code = norm["jquants"]
    yf_ticker = norm["yfinance"]

    jq_summary = fetch_jquants_fins_summary(code)
    jq_summary = _compute_growth_rates(jq_summary)

    # Supplement with yfinance info for items J-Quants does not provide.
    try:
        tk = yf.Ticker(yf_ticker)
        info = tk.info or {}
    except Exception:
        info = {}

    yf_keys = [
        "marketCap", "trailingPE", "forwardPE", "priceToBook",
        "grossMargins", "operatingMargins", "profitMargins",
        "returnOnEquity", "returnOnAssets",
        "totalRevenue", "totalCash", "totalDebt", "freeCashflow",
        "dividendYield", "beta",
        "recommendationMean", "numberOfAnalystOpinions",
        "targetMeanPrice", "targetHighPrice", "targetLowPrice",
        "sector", "industry", "longBusinessSummary",
    ]
    yf_data = {k: info.get(k) for k in yf_keys}
    for k, v in list(yf_data.items()):
        if isinstance(v, float):
            yf_data[k] = safe(v)

    return {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "jquants_summary": jq_summary[:4],  # latest 2 periods incl. growth calcs
        "yfinance": yf_data,
    }


# ---------------------------------------------------------------------------
# Macro (Japan)
# ---------------------------------------------------------------------------

def _yf_latest(ticker: str) -> dict:
    """Latest close and 1-day change for a yfinance proxy."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="10d")
    except Exception:
        return {}
    if hist.empty:
        return {}
    close = hist["Close"].dropna()
    if close.empty:
        return {}
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) >= 2 else None
    out = {
        "latest": safe(last),
        "date": close.index[-1].date().isoformat(),
    }
    if prev is not None and prev != 0:
        out["change_pct"] = safe((last / prev - 1) * 100)
    return out


def _fred_latest(series_id: str) -> dict:
    if not FRED_API_KEY:
        return {}
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    try:
        resp = requests.get(FRED_BASE, params=params, timeout=30)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        if not obs:
            return {}
        o = obs[0]
        val = safe(o.get("value")) if o.get("value") not in (".", "", None) else None
        return {"date": o.get("date"), "value": val}
    except Exception:
        return {}


def _mof_era_to_gregorian(era_text: str) -> date | None:
    """Convert 'S49.9.24' / 'H01.4.1' / 'R7.7.30' to a Gregorian date."""
    m = re.match(r"^([SHR])(\d+)\.(\d{1,2})\.(\d{1,2})$", era_text.strip())
    if not m:
        return None
    era, year, month, day = m.groups()
    year = int(year)
    month = int(month)
    day = int(day)
    if era == "S":  # Showa
        g_year = 1925 + year
    elif era == "H":  # Heisei
        g_year = 1988 + year
    elif era == "R":  # Reiwa
        g_year = 2018 + year
    else:
        return None
    try:
        return date(g_year, month, day)
    except ValueError:
        return None


def fetch_mof_jgb_10y() -> dict:
    """Fetch the latest 10-year JGB yield from MOF CSV."""
    try:
        resp = requests.get(MOF_JGB_CSV, timeout=60)
        resp.raise_for_status()
        # CSV is Shift-JIS encoded.
        df = pd.read_csv(io.StringIO(resp.content.decode("cp932", errors="replace")), header=1)
    except Exception:
        return {}
    # Header row 2: columns are 基準年月日, 1年, 2年, ... 10年, ...
    if df.shape[1] < 11:
        return {}
    date_col = df.columns[0]
    ten_year_col = df.columns[10]  # 10th maturity after reference date
    # Find the last row with a valid 10-year value.
    for _, row in reversed(list(df.iterrows())):
        raw_date = row[date_col]
        value = row[ten_year_col]
        if pd.isna(value) or value in ("-", ""):
            continue
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        g_date = _mof_era_to_gregorian(str(raw_date))
        if g_date is None:
            continue
        return {"date": g_date.isoformat(), "value": safe(val)}
    return {}


def fetch_boj_policy_rate() -> dict:
    """Fetch the latest uncollateralized overnight call rate from BOJ API."""
    # Use a 6-month lookback window formatted as YYYYMM.
    start = (date.today().replace(day=1) - timedelta(days=180)).strftime("%Y%m")
    params = {"db": "FM01", "code": "STRDCLUCON", "format": "json", "startDate": start}
    try:
        resp = requests.get(f"{BOJ_BASE}/getDataCode", params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        result = payload.get("RESULTSET", [{}])[0]
        values = result.get("VALUES", {})
        dates = values.get("SURVEY_DATES", [])
        vals = values.get("VALUES", [])
        if not dates or not vals:
            return {}
        # Keep only valid numeric observations.
        pairs = []
        for d, v in zip(dates, vals):
            try:
                pairs.append((int(d), float(v)))
            except (TypeError, ValueError):
                continue
        if not pairs:
            return {}
        latest_date_int, latest_val = pairs[-1]
        latest_date = datetime.strptime(str(latest_date_int), "%Y%m%d").date()
        return {"date": latest_date.isoformat(), "value": safe(latest_val)}
    except Exception:
        return {}


def fetch_macro(as_of: date) -> dict:
    result = {
        "as_of": as_of.isoformat(),
        "indices": {
            "n225": _yf_latest("^N225"),
            "usdjpy": _yf_latest("JPY=X"),
            "us10y": _yf_latest("^TNX"),
            "crude_oil": _yf_latest("CL=F"),
        },
        "boj_policy_rate": fetch_boj_policy_rate(),
        "jgb_10y": fetch_mof_jgb_10y(),
        "fred_jgb_10y": _fred_latest("IRLTLT01JPM156N"),
        "fred_policy_rate": _fred_latest("IRSTCB01JPM156N"),
    }
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--type", required=True, choices=["technical", "news", "fundamentals", "macro"])
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    as_of = date.fromisoformat(args.date)
    fetchers = {
        "technical": fetch_technical,
        "news": fetch_news,
        "fundamentals": fetch_fundamentals,
        "macro": lambda ticker, as_of: fetch_macro(as_of),
    }

    try:
        result = fetchers[args.type](args.ticker, as_of)
    except Exception as e:
        result = {"error": str(e), "ticker": args.ticker, "type": args.type}

    print(dump_json(result))


if __name__ == "__main__":
    main()
