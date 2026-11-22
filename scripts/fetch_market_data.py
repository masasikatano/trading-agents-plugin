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
    fetch_yahoo_news,
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
    items = normalize_yfinance_news(fetch_yahoo_news(ticker))

    # Earnings calendar: next earnings date if available.
    earnings_next = None
    try:
        ed = tk.earnings_dates
        if ed is not None and not ed.empty:
            future = ed[ed.index.date >= as_of] if hasattr(ed.index, "date") else ed
            row = future.iloc[0] if len(future) else ed.iloc[-1]
            earnings_next = {
                "date": str(future.index[0].date()) if len(future) else str(ed.index[-1].date()),
                "reported_eps": safe(row.get("Reported EPS")) if hasattr(row, "get") else None,
                "estimated_eps": safe(row.get("Estimated EPS")) if hasattr(row, "get") else None,
                "surprise_pct": safe(row.get("Surprise(%)")) if hasattr(row, "get") else None,
            }
    except Exception:
        pass

    # Recent analyst actions (upgrades/downgrades).
    analyst_actions = []
    try:
        ud = tk.upgrades_downgrades
        if ud is not None and not ud.empty:
            for idx, row in ud.tail(5).iloc[::-1].iterrows():
                d = idx.date().isoformat() if hasattr(idx, "date") else str(idx)
                analyst_actions.append({
                    "date": d,
                    "firm": str(row.get("Firm", "")),
                    "to_grade": str(row.get("ToGrade", "")),
                    "from_grade": str(row.get("FromGrade", "")),
                    "action": str(row.get("Action", "")),
                })
    except Exception:
        pass

    return {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "news_count": len(items),
        "items": items,
        "earnings_next": earnings_next,
        "analyst_actions": analyst_actions,
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
            for n in fetch_yahoo_news(sym, count=5):
                title = n.get("content", {}).get("title", n.get("title", ""))
                if title and title not in seen:
                    seen.add(title)
                    items.append({
                        "source": label,
                        "title": title,
                        "summary": n.get("content", {}).get("summary") or n.get("summary", ""),
                        "publisher": n.get("content", {}).get("provider", {}).get("displayName", ""),
                    })
        except Exception:
            continue

    # Numeric snapshots for the same proxies (FRED key not required).
    macro_prices = {}
    for sym, label in macro_tickers.items():
        try:
            hist = yf.Ticker(sym).history(
                start=(as_of - timedelta(days=10)).isoformat(),
                end=(as_of + timedelta(days=1)).isoformat(),
            )
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                last = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
                macro_prices[sym] = {
                    "label": label,
                    "last_date": closes.index[-1].date().isoformat(),
                    "last": safe(last),
                    "prev": safe(prev) if prev is not None else None,
                    "change_pct": safe((last / prev - 1) * 100)
                    if prev else None,
                }
        except Exception:
            continue

    return {
        "as_of": as_of.isoformat(),
        "macro_news_count": len(items),
        "items": items[:20],
        "macro_prices": macro_prices,
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

    # Current price from recent history (tk.info has no reliable spot).
    current_price = None
    last_trading_day = None
    try:
        hist = tk.history(
            start=(as_of - timedelta(days=10)).isoformat(),
            end=(as_of + timedelta(days=1)).isoformat(),
        )
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            current_price = safe(float(closes.iloc[-1]))
            last_trading_day = closes.index[-1].date().isoformat()
    except Exception:
        pass
    data["current_price"] = current_price
    data["last_trading_day"] = last_trading_day
    try:
        tgt = data.get("targetMeanPrice")
        if current_price and isinstance(tgt, (int, float)) and current_price != 0:
            data["target_vs_current_pct"] = safe(float(tgt) / float(current_price) * 100 - 100)
        else:
            data["target_vs_current_pct"] = None
    except Exception:
        data["target_vs_current_pct"] = None

    # Sector P/B norm: median priceToBook of peers (yfinance has no sector avg).
    peer_map = {
        "Semiconductors": ["AMD", "AVGO", "TXN", "QCOM", "INTC"],
    }
    sector_pb_median = None
    sector_pb_peers = {}
    try:
        peers = peer_map.get(info.get("industry") and "" or "") or peer_map.get(info.get("sector") and "" or "")
        if not peers:
            peers = peer_map["Semiconductors"] if info.get("sector") == "Technology" else []
        for p in peers:
            try:
                v = yf.Ticker(p).info.get("priceToBook")
                if isinstance(v, (int, float)):
                    sector_pb_peers[p] = safe(v)
            except Exception:
                continue
        if sector_pb_peers:
            import statistics
            sector_pb_median = safe(statistics.median(sector_pb_peers.values()))
    except Exception:
        pass
    data["sector_pb_median"] = sector_pb_median
    data["sector_pb_peers"] = sector_pb_peers

    data["quarterly_income_stmt"] = statement_to_dict(tk.quarterly_income_stmt)
    data["quarterly_balance_sheet"] = statement_to_dict(tk.quarterly_balance_sheet)
    data["quarterly_cashflow"] = statement_to_dict(tk.quarterly_cashflow)

    # Compact highlights so analysts don't miss key rows in raw statements.
    def _pick(stmt, names):
        for col, rows in stmt.items():
            for n in names:
                for k, v in rows.items():
                    if n.lower() in str(k).lower():
                        return {"date": col, "line": str(k), "value": v}
        return None
    data["quarterly_highlights"] = {
        "revenue": _pick(data["quarterly_income_stmt"], ["total revenue", "totalrevenues"]),
        "net_income": _pick(data["quarterly_income_stmt"], ["net income"]),
        "diluted_eps": _pick(data["quarterly_income_stmt"], ["diluted eps", "dilutedeps"]),
        "total_assets": _pick(data["quarterly_balance_sheet"], ["total assets"]),
    }

    # Short-interest block derived from the already-fetched tk.info (no new network).
    def _epoch_to_date(v):
        try:
            if v is None:
                return None
            from datetime import datetime, timezone
            return datetime.fromtimestamp(float(v), tz=timezone.utc).date().isoformat()
        except Exception:
            return None

    spf = info.get("shortPercentOfFloat")
    spso = info.get("sharesPercentSharesOut")
    sspm = info.get("sharesShortPriorMonth")
    sss = info.get("sharesShort")
    data["short_interest"] = {
        "shares_short": sss,
        "shares_short_prior_month": sspm,
        "shares_short_change_pct": (
            safe(float(sss) / float(sspm) * 100 - 100)
            if isinstance(sss, (int, float))
            and isinstance(sspm, (int, float))
            and float(sspm) != 0 else None),
        "short_percent_of_float_pct": (
            safe(float(spf) * 100)
            if isinstance(spf, (int, float)) else None),
        "shares_percent_shares_out_pct": (
            safe(float(spso) * 100)
            if isinstance(spso, (int, float)) else None),
        "short_ratio_days_to_cover": safe(info.get("shortRatio")),
        "float_shares": info.get("floatShares"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "date_short_interest": _epoch_to_date(info.get("dateShortInterest")),
        "shares_short_previous_month_date": _epoch_to_date(
            info.get("sharesShortPreviousMonthDate")),
        "available": sss is not None,
        "source": "yfinance_info",
        "staleness_days": (
            (as_of - date.fromisoformat(_epoch_to_date(info.get("dateShortInterest")))).days
            if _epoch_to_date(info.get("dateShortInterest")) else None),
        "stale": (
            (as_of - date.fromisoformat(_epoch_to_date(info.get("dateShortInterest")))).days > 14
            if _epoch_to_date(info.get("dateShortInterest")) else None),
    }

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
