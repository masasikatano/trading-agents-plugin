#!/usr/bin/env python3
"""
US Treasury-bond ETF data fetcher for bond-etf-analysis.

Usage:
  python scripts/fetch_bond_etf_data.py --ticker TLT --type technical --date 2026-10-24
  python scripts/fetch_bond_etf_data.py --ticker EDV --type fundamentals --date 2026-10-24
  python scripts/fetch_bond_etf_data.py --ticker SPTL --type rates --date 2026-10-24
  python scripts/fetch_bond_etf_data.py --ticker TLT --type news --date 2026-10-24

Environment variables (read from .env):
  FRED_API_KEY  - FRED API key (optional; used for the rates fetch.
                  If missing, the rates fetch falls back to yfinance-only output.)
"""
import argparse
import math
import os
import re
import sys
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

from market_data_utils import (
    compute_technicals,
    dump_json,
    fetch_yahoo_news,
    make_indicator_summary,
    make_price_summary,
    normalize_yfinance_news,
    recent_closes,
    safe,
)

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# Effective-duration fallback (years) when yfinance does not provide one.
DURATION_FALLBACK_YEARS = {
    "EDV": 24.4,
    "TLT": 16.6,
    "SPTL": 9.4,
}

NEWS_KEYWORDS = [
    "treasury", "yield", "yields", "bond", "bonds", "fed", "fomc",
    "federal reserve", "rate", "rates", "cpi", "inflation", "auction",
    "tlt", "edv", "sptl",
]


def _yf_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    try:
        hist = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat())
    except Exception:
        return pd.DataFrame()
    if hist.empty:
        return pd.DataFrame()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    return hist


# ---------------------------------------------------------------------------
# Technical
# ---------------------------------------------------------------------------

def _annualized_volatility(close: pd.Series, window: int = 60) -> float | None:
    rets = close.pct_change().dropna()
    if len(rets) < 20:
        return None
    return safe(rets.tail(window).std() * math.sqrt(252) * 100)


def _correlation_with_spx(ticker_hist: pd.DataFrame, as_of: date, window: int = 60) -> float | None:
    try:
        spx = yf.Ticker("^GSPC").history(
            start=(as_of - timedelta(days=520)).isoformat(),
            end=(as_of + timedelta(days=1)).isoformat(),
        )
    except Exception:
        return None
    if spx.empty:
        return None
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    aligned = pd.concat(
        [ticker_hist["Close"].pct_change(), spx["Close"].pct_change()], axis=1, keys=["etf", "spx"]
    ).dropna()
    if len(aligned) < window:
        return None
    return safe(aligned["etf"].tail(window).corr(aligned["spx"].tail(window)))


def fetch_technical(ticker: str, as_of: date) -> dict:
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=520)
    hist = _yf_history(ticker, start, end)
    if hist.empty:
        return {"error": f"No price data for {ticker}"}

    indicators = compute_technicals(hist)
    close = hist["Close"]

    high52 = float(close.rolling(252).max().iloc[-1])
    current = float(close.iloc[-1])
    low52 = float(close.rolling(252).min().iloc[-1])

    price = make_price_summary(close)
    price["52w_high"] = safe(high52)
    price["52w_low"] = safe(low52)
    price["drawdown_from_52w_high_pct"] = safe((current / high52 - 1) * 100) if high52 else None
    price["above_52w_low_pct"] = safe((current / low52 - 1) * 100) if low52 else None
    price["annualized_volatility_60d_pct"] = _annualized_volatility(close)
    price["corr_60d_vs_gspc"] = _correlation_with_spx(hist, as_of)

    result = {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "last_trading_day": close.index[-1].date().isoformat(),
        "price": price,
        "indicators": make_indicator_summary(indicators),
        "recent_closes": recent_closes(close),
    }
    result["signal"] = _technical_signal(result)
    return result


def _technical_signal(result: dict) -> str:
    ind = result.get("indicators", {})
    price = result.get("price", {})
    current = price.get("current")
    sma50 = ind.get("sma50")
    sma200 = ind.get("sma200")
    rsi = ind.get("rsi14")
    macd_hist = ind.get("macd_hist")
    if current is None or sma50 is None or sma200 is None:
        return "NEUTRAL"
    score = 0
    if current > sma50:
        score += 1
    else:
        score -= 1
    if current > sma200:
        score += 1
    else:
        score -= 1
    if rsi is not None:
        if rsi < 30:
            score += 1  # oversold bond ETF: mean-reversion bounce candidate
        elif rsi > 70:
            score -= 1
    if macd_hist is not None:
        score += 1 if macd_hist > 0 else -1
    if score >= 2:
        return "BULLISH"
    if score <= -2:
        return "BEARISH"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def _dividend_summary(tk) -> dict:
    out = {"recent_dividends": {}, "trailing_12m_total": None, "annualized_yield_pct": None,
           "trend": None}
    try:
        div = tk.dividends
    except Exception:
        return out
    if div is None or div.empty:
        return out
    div.index = pd.to_datetime(div.index).tz_localize(None)
    cutoff = div.index[-1] - pd.DateOffset(months=12)
    ttm = div[div.index >= cutoff]
    out["recent_dividends"] = {
        d.date().isoformat(): safe(v) for d, v in div.tail(12).items()
    }
    ttm_total = float(ttm.sum()) if not ttm.empty else None
    out["trailing_12m_total"] = safe(ttm_total)
    if ttm_total is not None and len(div) >= 2:
        prev_cutoff_low = div.index[-1] - pd.DateOffset(months=24)
        prev_cutoff_high = div.index[-1] - pd.DateOffset(months=12)
        prev = div[(div.index >= prev_cutoff_low) & (div.index < prev_cutoff_high)]
        prev_total = float(prev.sum()) if not prev.empty else None
        if prev_total:
            change_pct = (ttm_total / prev_total - 1) * 100
            out["trend"] = (
                "RISING" if change_pct > 3 else
                "FALLING" if change_pct < -3 else "STABLE"
            )
            out["trailing_12m_change_pct"] = safe(change_pct)
    return out


def _funds_duration(info: dict, funds_data) -> float | None:
    candidates = []
    if isinstance(funds_data, dict):
        candidates.append(funds_data.get("duration"))
    candidates.append(info.get("duration"))
    for c in candidates:
        try:
            if c is None:
                continue
            f = float(c)
            if f > 0:
                return safe(f)
        except (TypeError, ValueError):
            continue
    return None


def fetch_fundamentals(ticker: str, as_of: date) -> dict:
    tk = yf.Ticker(ticker)
    try:
        info = tk.info or {}
    except Exception:
        info = {}
    try:
        funds_data = tk.funds_data
        funds_data = funds_data if isinstance(funds_data, dict) else {}
    except Exception:
        funds_data = {}

    duration = _funds_duration(info, funds_data)
    fallback_used = False
    if duration is None:
        duration = DURATION_FALLBACK_YEARS.get(ticker.upper())
        fallback_used = duration is not None

    # NAV / premium-discount
    nav = None
    for c in (funds_data.get("nav"), info.get("navPrice")):
        try:
            if c is not None:
                nav = safe(float(c))
                break
        except (TypeError, ValueError):
            continue

    keys = ["longName", "category", "fundFamily", "quoteType", "beta3Year",
            "trailingPE"]
    meta = {k: info.get(k) for k in keys}
    # yfinance's raw "yield" field is unreliable for bond ETFs; the computed
    # TTM dividend yield below is the authoritative figure.
    meta["yield_raw_yfinance_unreliable"] = info.get("yield")

    price_current = None
    try:
        hist = tk.history(period="5d")
        if not hist.empty:
            price_current = safe(float(hist["Close"].iloc[-1]))
    except Exception:
        pass

    result = {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "etf_meta": meta,
        "nav": nav,
        "price": price_current,
        "premium_discount_pct": (
            safe((price_current / nav - 1) * 100) if price_current and nav else None
        ),
        "aum": None,
        "expense_ratio": None,
        "effective_duration_years": duration,
        "duration_source": "fallback_table" if fallback_used else "yfinance",
        "duration_fallback_used": fallback_used,
        "dividends": _dividend_summary(tk),
        "note": (
            "Effective duration from fallback table; verify against issuer factsheet."
            if fallback_used else None
        ),
    }

    # AUM: yfinance reports totalAssets on funds; fall back to marketCap.
    for v in (info.get("totalAssets"), info.get("marketCap")):
        try:
            if v is not None:
                result["aum"] = safe(float(v) / 1e9)
                break
        except (TypeError, ValueError):
            continue
    for v in (info.get("annualReportExpenseRatio"), info.get("netExpenseRatio")):
        try:
            if v is not None:
                f = float(v)
                # yfinance reports ETF expense ratios already in percent
                # (e.g. 0.15 for TLT); only rescale if it looks like a fraction.
                result["expense_ratio"] = safe(f / 100 if f > 5 else f)
                break
        except (TypeError, ValueError):
            continue

    ttm = (result["dividends"] or {}).get("trailing_12m_total")
    if ttm is not None and price_current:
        result["dividends"]["annualized_yield_pct"] = safe(ttm / price_current * 100)

    result["signal"] = _fundamentals_signal(result)
    return result


def _fundamentals_signal(result: dict) -> str:
    er = result.get("expense_ratio")
    dur = result.get("effective_duration_years")
    trend = (result.get("dividends") or {}).get("trend")
    score = 0
    if er is not None:
        score += 1 if er < 0.2 else (-1 if er > 0.3 else 0)
    if dur is not None:
        score += 1  # any well-defined duration allows rate-sensitivity sizing
    if trend == "RISING":
        score += 1
    elif trend == "FALLING":
        score -= 1
    if score >= 2:
        return "ATTRACTIVE"
    if score <= -1:
        return "UNATTRACTIVE"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------

FRED_SERIES = {
    "DGS2": "2Y Treasury",
    "DGS10": "10Y Treasury",
    "DGS30": "30Y Treasury",
    "T10Y2Y": "2s10s Curve",
    "DFII10": "10Y TIPS (real yield)",
}


def _fred_series(series_id: str, limit: int = 400) -> list[tuple[str, float]]:
    if not FRED_API_KEY:
        return []
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        resp = requests.get(FRED_BASE, params=params, timeout=30)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
    except Exception:
        return []
    out = []
    for o in obs:
        v = o.get("value")
        if v in (".", "", None):
            continue
        try:
            out.append((o.get("date"), float(v)))
        except (TypeError, ValueError):
            continue
    return out


def _changes(pairs: list[tuple[str, float]]) -> dict:
    if not pairs:
        return {}
    latest_date, latest = pairs[0]

    def _lookback(days: int) -> float | None:
        from datetime import datetime as _dt
        try:
            ref = _dt.fromisoformat(latest_date).date() - timedelta(days=days)
        except Exception:
            return None
        for d, v in pairs:  # newest first
            try:
                if _dt.fromisoformat(d).date() <= ref:
                    return safe((latest - v) * 100)  # pp -> bp
            except Exception:
                continue
        return None

    return {
        "latest": safe(latest),
        "date": latest_date,
        "change_1m_bp": _lookback(30),
        "change_3m_bp": _lookback(91),
        "change_1y_bp": _lookback(365),
    }


def _yf_yield_latest(ticker: str, scale: float = 1.0) -> dict:
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
    except Exception:
        return {}
    if hist.empty:
        return {}
    close = hist["Close"].dropna()
    if close.empty:
        return {}
    latest = float(close.iloc[-1]) * scale
    out = {"latest": safe(latest), "date": close.index[-1].date().isoformat(),
           "source": f"yfinance:{ticker}"}
    if len(close) >= 2:
        prev = float(close.iloc[-2]) * scale
        if prev:
            out["change_pct"] = safe((latest / prev - 1) * 100)
    return out


def fetch_rates(ticker: str, as_of: date) -> dict:
    fred = {}
    fred_ok = bool(FRED_API_KEY)
    if FRED_API_KEY:
        for sid, label in FRED_SERIES.items():
            series = _fred_series(sid)
            if not series:
                fred_ok = False
                continue
            fred[sid] = {"label": label, **_changes(series)}
    if not fred:
        fred_ok = False

    curve_shape = None
    if fred.get("DGS2") and fred.get("DGS10"):
        diff = (fred["DGS10"].get("latest") or 0) - (fred["DGS2"].get("latest") or 0)
        if fred["DGS2"].get("latest") is not None and fred["DGS10"].get("latest") is not None:
            curve_shape = "INVERTED" if diff < 0 else ("FLAT" if diff < 0.25 else "STEEP")

    result = {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "fred": fred if fred_ok else {},
        "fred_available": fred_ok,
        "fred_warning": (
            None if fred_ok else
            "FRED_API_KEY missing or FRED request failed; FRED data skipped. "
            "Set FRED_API_KEY in .env for Treasury curve data."
        ),
        "curve_shape": curve_shape if fred_ok else None,
        "yahoo_crosscheck": {
            "us10y_tnx": _yf_yield_latest("^TNX"),
            "us30y_tyx": _yf_yield_latest("^TYX"),
        },
    }
    result["signal"] = _rates_signal(result)
    return result


def _rates_signal(result: dict) -> str:
    score = 0
    dgs10 = result.get("fred", {}).get("DGS10") or {}
    dgs2 = result.get("fred", {}).get("DGS2") or {}
    chg = dgs10.get("change_3m_bp")
    if chg is not None:
        score += 1 if chg <= 0 else -1  # falling yields are tailwind for bond ETFs
    curve = result.get("curve_shape")
    if curve in ("STEEP", "FLAT"):
        score += 0
    elif curve == "INVERTED":
        score += 1  # inverted curve often precedes cuts
    tnx = (result.get("yahoo_crosscheck") or {}).get("us10y_tnx") or {}
    if not result.get("fred_available"):
        # Fall back to yfinance direction only.
        change_pct = tnx.get("change_pct")
        if change_pct is None:
            return "NEUTRAL"
        return "BULLISH" if change_pct <= 0 else "BEARISH"
    if dgs2.get("latest") is not None and dgs10.get("latest") is not None:
        score += 1 if dgs10["latest"] <= dgs2["latest"] else 0
    if score >= 2:
        return "BULLISH"
    if score <= -1:
        return "BEARISH"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def _is_relevant(item: dict) -> bool:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(k in text for k in NEWS_KEYWORDS)


def fetch_news(ticker: str, as_of: date) -> dict:
    raw = normalize_yfinance_news(fetch_yahoo_news(ticker))
    relevant = [i for i in raw if _is_relevant(i)]
    # Add rate-topic news via search on a Treasury-yield query.
    try:
        extra = normalize_yfinance_news(
            fetch_yahoo_news("Treasury yields", count=10) or []
        )
    except Exception:
        extra = []
    seen = {i.get("title") for i in relevant}
    for i in extra:
        if i.get("title") and i["title"] not in seen and _is_relevant(i):
            seen.add(i["title"])
            relevant.append(i)
    relevant = relevant[:15]

    result = {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "news_count": len(relevant),
        "raw_ticker_news_count": len(raw),
        "items": relevant,
    }
    result["signal"] = _news_signal(relevant)
    return result


_POSITIVE = re.compile(r"cut|easing|dovish|rally|rallies|rallied|gain|gains|bid|"
                       r"demand|falling yields|yields fall|yields drop|inflows")
_NEGATIVE = re.compile(r"hike|hawkish|selloff|sell-off|falls?|drops?|plunge|"
                       r"outflows|falling prices|supply|auction tails|inflation "
                       r"reaccelerat|deficit")


def _news_signal(items: list[dict]) -> str:
    if not items:
        return "NEUTRAL"
    score = 0
    for i in items:
        text = f"{i.get('title', '')} {i.get('summary', '')}".lower()
        score += len(_POSITIVE.findall(text))
        score -= len(_NEGATIVE.findall(text))
    if score >= 3:
        return "POSITIVE"
    if score <= -3:
        return "NEGATIVE"
    return "MIXED"


# ---------------------------------------------------------------------------
# Signal line printer
# ---------------------------------------------------------------------------

SIGNAL_PREFIX = {
    "technical": "TECHNICAL SIGNAL",
    "fundamentals": "FUNDAMENTALS SIGNAL",
    "rates": "RATES SIGNAL",
    "news": "NEWS SIGNAL",
}


def _print_signal(fetch_type: str, result: dict):
    signal = result.get("signal")
    if signal:
        print(f"{SIGNAL_PREFIX[fetch_type]}: {signal}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--type", required=True,
                        choices=["technical", "fundamentals", "rates", "news"])
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    as_of = date.fromisoformat(args.date)
    fetchers = {
        "technical": fetch_technical,
        "news": fetch_news,
        "fundamentals": fetch_fundamentals,
        "rates": fetch_rates,
    }

    try:
        result = fetchers[args.type](args.ticker, as_of)
    except Exception as e:
        result = {"error": str(e), "ticker": args.ticker, "type": args.type}

    print(dump_json(result))
    if "error" not in result:
        _print_signal(args.type, result)


if __name__ == "__main__":
    main()
