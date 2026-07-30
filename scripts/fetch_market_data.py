#!/usr/bin/env python3
"""
Usage:
  python scripts/fetch_market_data.py --ticker NVDA --type technical --date 2026-05-02
  python scripts/fetch_market_data.py --ticker NVDA --type news --date 2026-05-02
  python scripts/fetch_market_data.py --ticker NVDA --type fundamentals --date 2026-05-02
"""
import argparse
import sys
from datetime import date, timedelta

import yfinance as yf

from market_data_utils import (
    compute_technicals,
    dump_json,
    make_indicator_summary,
    make_price_summary,
    normalize_yfinance_news,
    recent_closes,
    safe,
    statement_to_dict,
)


def fetch_technical(ticker: str, as_of: date) -> dict:
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=520)
    tk = yf.Ticker(ticker)
    hist = tk.history(start=start.isoformat(), end=end.isoformat())
    if hist.empty:
        return {"error": f"No price data for {ticker}"}

    indicators = compute_technicals(hist)
    close = hist["Close"]

    return {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "last_trading_day": close.index[-1].date().isoformat(),
        "price": make_price_summary(close),
        "indicators": make_indicator_summary(indicators),
        "recent_closes": recent_closes(close),
    }


def fetch_news(ticker: str, as_of: date) -> dict:
    # yfinance always returns latest news regardless of as_of date
    tk = yf.Ticker(ticker)
    items = normalize_yfinance_news(tk.news)

    return {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "news_count": len(items),
        "items": items,
    }


def fetch_macro(as_of: date) -> dict:
    # Pull news from broad market proxies to get global macro context
    macro_tickers = {
        "^GSPC": "S&P 500",
        "^TNX": "10Y Treasury Yield",
        "GC=F": "Gold Futures",
        "CL=F": "Crude Oil Futures",
    }
    items = []
    seen = set()
    for sym, label in macro_tickers.items():
        try:
            for n in (yf.Ticker(sym).news or [])[:5]:
                title = n.get("content", {}).get("title", n.get("title", ""))
                if title and title not in seen:
                    seen.add(title)
                    items.append({
                        "source": label,
                        "title": title,
                        "summary": n.get("content", {}).get("summary", ""),
                        "publisher": n.get("content", {}).get("provider", {}).get("displayName", ""),
                    })
        except Exception:
            continue

    return {
        "as_of": as_of.isoformat(),
        "macro_news_count": len(items),
        "items": items[:20],
    }


def fetch_fundamentals(ticker: str, as_of: date) -> dict:
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    keys = [
        "marketCap", "trailingPE", "forwardPE", "priceToBook",
        "revenueGrowth", "earningsGrowth", "grossMargins", "operatingMargins",
        "profitMargins", "returnOnEquity", "returnOnAssets",
        "totalRevenue", "totalCash", "totalDebt", "freeCashflow",
        "dividendYield", "beta", "shortRatio",
        "recommendationMean", "numberOfAnalystOpinions",
        "targetMeanPrice", "targetHighPrice", "targetLowPrice",
        "sector", "industry", "longBusinessSummary",
    ]
    data = {k: info.get(k) for k in keys}
    data["ticker"] = ticker
    data["as_of"] = as_of.isoformat()
    for k in list(data.keys()):
        if isinstance(data[k], float):
            data[k] = safe(data[k])

    data["quarterly_income_stmt"] = statement_to_dict(tk.quarterly_income_stmt)
    data["quarterly_balance_sheet"] = statement_to_dict(tk.quarterly_balance_sheet)
    data["quarterly_cashflow"] = statement_to_dict(tk.quarterly_cashflow)

    return data


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
