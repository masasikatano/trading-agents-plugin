#!/usr/bin/env python3
"""
Japan index-inverse ETF data fetcher for inverse-index-etf-jp.

Covers TSE-listed inverse / double-inverse index ETFs:
  1360  日経平均ベア２倍上場投信 (N225 -2x)
  1356  ＴＯＰＩＸベア２倍上場投信 (TOPIX -2x)
  1366  iFreeETF 日経平均ダブルインバース・インデックス (N225 -2x)
  1456  iFreeETF 日経平均インバース・インデックス (N225 -1x)

Usage:
  python scripts/fetch_inverse_index_etf_data.py --ticker 1360 --type technical --date 2026-11-22
  python scripts/fetch_inverse_index_etf_data.py --ticker 1360 --type underlying --date 2026-11-22
  python scripts/fetch_inverse_index_etf_data.py --ticker 1360 --type cost --date 2026-11-22
  python scripts/fetch_inverse_index_etf_data.py --ticker 1360 --type news --date 2026-11-22
  python scripts/fetch_inverse_index_etf_data.py --ticker 1360 --type macro --date 2026-11-22

No API key required (yfinance only).
"""
import argparse
import math
import sys
from datetime import date, timedelta

import pandas as pd
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
)

# Static facts — verify against the issuer factsheet before sizing.
ETF_STATIC_FACTS = {
    "1360": {"name": "日経平均ベア２倍上場投信", "underlying": "N225",
             "leverage": -2, "expense_ratio": 0.80,
             "factsheet": "Simplex / 日経平均ベア２倍上場投信 factsheet"},
    "1356": {"name": "ＴＯＰＩＸベア２倍上場投信", "underlying": "TOPIX",
             "leverage": -2, "expense_ratio": 0.80,
             "factsheet": "Simplex / ＴＯＰＩＸベア２倍上場投信 factsheet"},
    "1366": {"name": "iFreeETF 日経平均ダブルインバース・インデックス",
             "underlying": "N225", "leverage": -2, "expense_ratio": 0.64,
             "factsheet": "大和アセット 1366 factsheet"},
    "1456": {"name": "iFreeETF 日経平均インバース・インデックス",
             "underlying": "N225", "leverage": -1, "expense_ratio": 0.64,
             "factsheet": "大和アセット 1456 factsheet"},
}

# TOPIX has no reliable Yahoo index symbol (^TOPX is often empty);
# fall back to TOPIX-linked ETFs as a price proxy (flagged in output).
UNDERLYING_YF = {"N225": ["^N225"], "TOPIX": ["^TOPX", "1306.T", "1305.T"]}


def _yf_history_first(symbols: list[str], start: date, end: date) -> tuple[str, pd.DataFrame]:
    for sym in symbols:
        hist = _yf_history(sym, start, end)
        if not hist.empty and "Close" in hist.columns and not hist["Close"].dropna().empty:
            return sym, hist
    return symbols[0], pd.DataFrame()

NEWS_KEYWORDS = [
    "日経平均", "TOPIX", "トピックス", "ベア", "インバース",
    "nikkei", "topix", "bear market", "selloff", "日銀", "利上げ",
]


def resolve_ticker(ticker: str) -> str:
    """Map a user-supplied ticker to the yfinance symbol."""
    t = (ticker or "").strip().upper()
    if t.endswith(".T"):
        return t
    if t.startswith("TYO:"):
        t = t[4:]
    if t.isdigit():
        return f"{t}.T"
    return t


def display_ticker(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    if t.endswith(".T"):
        t = t[:-2]
    if t.startswith("TYO:"):
        t = t[4:]
    return t


def _yf_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    try:
        hist = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat())
    except Exception:
        return pd.DataFrame()
    if hist.empty:
        return pd.DataFrame()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    return hist


def _annualized_volatility(close: pd.Series, window: int = 60) -> float | None:
    rets = close.pct_change().dropna()
    if len(rets) < 20:
        return None
    return safe(rets.tail(window).std() * math.sqrt(252) * 100)


def fetch_technical(ticker: str, as_of: date) -> dict:
    yf_ticker = resolve_ticker(ticker)
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=520)
    hist = _yf_history(yf_ticker, start, end)
    if hist.empty or "Close" not in hist.columns:
        return {"error": f"No price data for {ticker}"}
    hist = hist.dropna(subset=["Close"])
    indicators = compute_technicals(hist)
    close = hist["Close"]
    hi_52 = safe(close.tail(252).max())
    lo_52 = safe(close.tail(252).min())
    last = safe(close.iloc[-1])
    return {
        "ticker": display_ticker(ticker),
        "as_of": as_of.isoformat(),
        "last_trading_day": close.index[-1].date().isoformat(),
        "price": make_price_summary(close),
        "indicators": make_indicator_summary(indicators),
        "recent_closes": recent_closes(close),
        "range_52w": {"high": hi_52, "low": lo_52,
                      "off_high_pct": safe((last / hi_52 - 1) * 100) if last and hi_52 else None,
                      "off_low_pct": safe((last / lo_52 - 1) * 100) if last and lo_52 else None},
        "annualized_volatility_pct": _annualized_volatility(close),
        "note": "インバース型のため価格上昇=原指数下落。テクニカルの強気/弱気はETF価格に対するものであり、原指数とは逆方向である点に注意。",
    }


def fetch_underlying(ticker: str, as_of: date) -> dict:
    """Fetch the underlying index (N225 / TOPIX) trend + tracking vs the ETF."""
    bare = display_ticker(ticker)
    facts = ETF_STATIC_FACTS.get(bare, {})
    underlying = facts.get("underlying", "N225")
    leverage = facts.get("leverage")
    u_symbols = UNDERLYING_YF.get(underlying, ["^N225"])
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=120)
    u_ticker, u_hist = _yf_history_first(u_symbols, start, end)
    e_hist = _yf_history(resolve_ticker(ticker), start, end)
    out: dict = {
        "ticker": bare,
        "as_of": as_of.isoformat(),
        "underlying": underlying,
        "underlying_yf": u_ticker,
        "leverage": leverage,
    }
    if u_ticker != u_symbols[0]:
        out["underlying_proxy_note"] = (
            f"指数シンボル {u_symbols[0]} が取得できないため {u_ticker} をプロキシに使用（ETF分配・コスト分の誤差あり）")
    if u_hist.empty:
        out["error"] = f"No underlying data for {u_ticker}"
        return out
    u_close = u_hist["Close"].dropna()
    out["underlying_price"] = make_price_summary(u_close)
    out["underlying_indicators"] = make_indicator_summary(compute_technicals(u_hist))
    out["underlying_recent_closes"] = recent_closes(u_close)
    out["underlying_trend"] = {
        "vs_20d_pct": safe((u_close.iloc[-1] / u_close.iloc[-21] - 1) * 100) if len(u_close) > 21 else None,
        "vs_60d_pct": safe((u_close.iloc[-1] / u_close.iloc[-61] - 1) * 100) if len(u_close) > 61 else None,
    }
    # Tracking check: compare ETF 20-day return vs leverage * underlying 20-day return.
    if not e_hist.empty and leverage:
        e_close = e_hist["Close"].dropna()
        common = u_close.index.intersection(e_close.index)
        if len(common) > 21:
            u_ret = u_close.loc[common].iloc[-1] / u_close.loc[common].iloc[-21] - 1
            e_ret = e_close.loc[common].iloc[-1] / e_close.loc[common].iloc[-21] - 1
            out["tracking_20d"] = {
                "underlying_ret_pct": safe(u_ret * 100),
                "etf_ret_pct": safe(e_ret * 100),
                "expected_etf_ret_pct": safe(u_ret * leverage * 100),
                "deviation_pp": safe((e_ret - u_ret * leverage) * 100),
                "note": "乖離が大きい場合は減価・コスト・分配の影響。マイナス方向への乖離蓄積は長期保有の不利を示す。",
            }
    return out


def fetch_cost(ticker: str, as_of: date) -> dict:
    """Structural cost view: expense, leverage decay warning, distributions."""
    bare = display_ticker(ticker)
    facts = ETF_STATIC_FACTS.get(bare)
    out: dict = {"ticker": bare, "as_of": as_of.isoformat()}
    if facts:
        out["static_facts"] = {**facts, "note": "概算値 — サイジング前に発行体ファクトシートで確認すること"}
    try:
        info = yf.Ticker(resolve_ticker(ticker)).info or {}
    except Exception:
        info = {}
    out["expense_ratio_pct"] = info.get("annualReportExpenseRatio",
                                        (facts or {}).get("expense_ratio"))
    out["aum"] = info.get("totalAssets")
    out["nav_vs_price"] = {"previousClose": safe(info.get("previousClose")),
                           "nav": safe(info.get("navPrice"))}
    out["yield_ttm_pct"] = safe((info.get("trailingAnnualDividendYield") or 0) * 100)
    if (facts or {}).get("leverage") == -2:
        out["decay_warning"] = ("日次2倍リバランス型はボックス相場で減価する。"
                                "原指数が往って来いでもETF価格は目減りするため、長期保有には向かず短期トレード・ヘッジ用途が前提。")
    elif (facts or {}).get("leverage") == -1:
        out["decay_warning"] = ("日次-1倍連動型。-2倍より減価は小さいが、分配・コスト分の乖離は蓄積する。")
    return out


def fetch_news(ticker: str, as_of: date) -> dict:
    bare = display_ticker(ticker)
    facts = ETF_STATIC_FACTS.get(bare, {})
    queries = [f"{bare} ETF", "日経平均 急落 反発" if facts.get("underlying", "N225") == "N225" else "TOPIX 急落 反発"]
    seen: dict = {}
    for q in queries:
        for item in normalize_yfinance_news(fetch_yahoo_news(q, count=10)):
            seen[item.get("link") or item.get("title")] = item
    items = list(seen.values())[:15]
    kw = [k for k in NEWS_KEYWORDS if any(
        k.lower() in ((i.get("title") or "") + (i.get("summary") or "")).lower() for i in items)]
    return {
        "ticker": bare,
        "as_of": as_of.isoformat(),
        "news": items,
        "direct_coverage_count": sum(1 for i in items if bare in (i.get("title") or "")),
        "matched_keywords": kw,
        "coverage_note": ("インバースETF自体の個別報道は少ないため、原指数（日経平均/TOPIX）と"
                          "相場全体のヘッドラインを重視すること。"),
    }


def fetch_macro(as_of: date) -> dict:
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=120)
    out: dict = {"as_of": as_of.isoformat()}
    for name, syms in [("nikkei225", ["^N225"]), ("topix", ["^TOPX", "1306.T"]),
                         ("usd_jpy", ["JPY=X"]), ("us10y", ["^TNX"]), ("oil", ["CL=F"])]:
        sym, h = _yf_history_first(syms, start, end)
        if h.empty:
            out[name] = {"error": f"No data for {sym}"}
            continue
        c = h["Close"].dropna()
        out[name] = {
            "last": safe(c.iloc[-1]),
            "last_day": c.index[-1].date().isoformat(),
            "vs_20d_pct": safe((c.iloc[-1] / c.iloc[-21] - 1) * 100) if len(c) > 21 else None,
            "vs_60d_pct": safe((c.iloc[-1] / c.iloc[-61] - 1) * 100) if len(c) > 61 else None,
        }
    out["note"] = ("インバースETFの買いシグナルは、原指数の下落・リスクオフ局面と表裏一体。"
                   "日経平均のトレンド転換（上昇再開）はETFの売りシグナルになる。")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--type", required=True,
                    choices=["technical", "underlying", "cost", "news", "macro"])
    ap.add_argument("--date", required=True)
    args = ap.parse_args(argv)
    as_of = date.fromisoformat(args.date)
    if args.type == "technical":
        print(dump_json(fetch_technical(args.ticker, as_of)))
    elif args.type == "underlying":
        print(dump_json(fetch_underlying(args.ticker, as_of)))
    elif args.type == "cost":
        print(dump_json(fetch_cost(args.ticker, as_of)))
    elif args.type == "news":
        print(dump_json(fetch_news(args.ticker, as_of)))
    elif args.type == "macro":
        print(dump_json(fetch_macro(as_of)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
