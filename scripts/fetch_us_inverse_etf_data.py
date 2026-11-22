#!/usr/bin/env python3
"""
US index-inverse ETF data fetcher for inverse-index-etf-us (TSE-listed).

Covers TSE-listed US-index inverse / double-inverse ETFs:
  2870  iFreeETF NASDAQ100ダブルインバース (NASDAQ100 -2x)
  2842  iFreeETF NASDAQ100インバース (NASDAQ100 -1x)
  2249  iFreeETF S&P500ダブルインバース (SP500 -2x)
  2238  iFreeETF S&P500インバース (SP500 -1x)

Usage:
  python scripts/fetch_us_inverse_etf_data.py --ticker 2870 --type technical --date 2026-11-22
  python scripts/fetch_us_inverse_etf_data.py --ticker 2870 --type underlying --date 2026-11-22
  python scripts/fetch_us_inverse_etf_data.py --ticker 2870 --type cost --date 2026-11-22
  python scripts/fetch_us_inverse_etf_data.py --ticker 2870 --type news --date 2026-11-22
  python scripts/fetch_us_inverse_etf_data.py --ticker 2870 --type macro --date 2026-11-22

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

# Static facts — expense_ratio is tax-inclusive, verified 2026-11-22 against
# JPX official docs (leveraged-inverse files). Re-verify if the issuer revises fees.
ETF_STATIC_FACTS = {
    "2870": {"name": "iFreeETF NASDAQ100ダブルインバース",
             "underlying": "NASDAQ100", "leverage": -2, "expense_ratio": 0.825,
             "expense_ratio_tax": "incl", "expense_verified": "2026-11-22",
             "factsheet": "https://www.jpx.co.jp/equities/products/etfs/leveraged-inverse/files/2870-j.pdf"},
    "2842": {"name": "iFreeETF NASDAQ100インバース",
             "underlying": "NASDAQ100", "leverage": -1, "expense_ratio": 0.825,
             "expense_ratio_tax": "incl", "expense_verified": "2026-11-22",
             "factsheet": "https://www.jpx.co.jp/equities/products/etfs/leveraged-inverse/files/2842-j.pdf"},
    "2249": {"name": "iFreeETF S&P500ダブルインバース",
             "underlying": "SP500", "leverage": -2, "expense_ratio": 0.803,
             "expense_ratio_tax": "incl", "expense_verified": "2026-11-22",
             "factsheet": "https://www.jpx.co.jp/equities/products/etfs/leveraged-inverse/files/2249-j.pdf"},
    "2238": {"name": "iFreeETF S&P500インバース",
             "underlying": "SP500", "leverage": -1, "expense_ratio": 0.803,
             "expense_ratio_tax": "incl", "expense_verified": "2026-11-22",
             "factsheet": "https://www.jpx.co.jp/equities/products/etfs/leveraged-inverse/files/2238-j.pdf"},
}

# Index symbols with liquid-ETF fallbacks (flagged in output when a proxy is used).
UNDERLYING_YF = {"NASDAQ100": ["^NDX", "QQQ"], "SP500": ["^GSPC", "SPY"]}


def _yf_history_first(symbols: list[str], start: date, end: date) -> tuple[str, pd.DataFrame]:
    for sym in symbols:
        hist = _yf_history(sym, start, end)
        if not hist.empty and "Close" in hist.columns and not hist["Close"].dropna().empty:
            return sym, hist
    return symbols[0], pd.DataFrame()

NEWS_KEYWORDS = [
    "NASDAQ100", "ナスダック100", "S&P500", "ベア", "インバース",
    "nasdaq", "s&p 500", "bear market", "selloff", "FOMC", "利下げ",
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
    """Fetch the underlying index (NASDAQ100 / SP500) trend + tracking vs the ETF."""
    bare = display_ticker(ticker)
    facts = ETF_STATIC_FACTS.get(bare, {})
    underlying = facts.get("underlying", "NASDAQ100")
    leverage = facts.get("leverage")
    u_symbols = UNDERLYING_YF.get(underlying, ["^NDX"])
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=520)
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
    if "Volume" in u_hist.columns:
        vol = u_hist["Volume"].dropna()
        if not vol.empty:
            out["underlying_price"]["volume_last"] = safe(vol.iloc[-1])
            out["underlying_price"]["volume_avg_20"] = safe(vol.tail(20).mean())
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
        out["static_facts"] = {**facts, "note": "信託報酬は税込・JPX公表資料で確認済み（expense_verified参照）"}
    try:
        info = yf.Ticker(resolve_ticker(ticker)).info or {}
    except Exception:
        info = {}
    fallback_expense = (facts or {}).get("expense_ratio")
    if info.get("annualReportExpenseRatio") is not None:
        out["expense_ratio_pct"] = info.get("annualReportExpenseRatio")
        out["expense_ratio_source"] = "yfinance"
    else:
        out["expense_ratio_pct"] = fallback_expense
        out["expense_ratio_source"] = "fallback_static"
    out["aum"] = info.get("totalAssets")
    # 気配は取得時点のスナップショット。過去基準日との比較ではなく目安として扱うこと。
    bid, ask = safe(info.get("bid")), safe(info.get("ask"))
    if bid and ask and ask > 0:
        out["quote"] = {"bid": bid, "ask": ask,
                        "spread_bps": safe((ask - bid) / ask * 10000),
                        "bid_size": info.get("bidSize"), "ask_size": info.get("askSize"),
                        "quote_status": "OK",
                        "note": "取得時点のスナップショットであり、基準日時点の気配ではない"}
    else:
        out["quote"] = {"quote_status": "QUOTE_STALE",
                        "note": "板情報なし — 指値運用前提。寄り付きの気配で確認すること。"}
    e_hist = _yf_history(resolve_ticker(ticker), as_of - timedelta(days=10), as_of + timedelta(days=1))
    price_last = safe(e_hist["Close"].dropna().iloc[-1]) if not e_hist.empty and "Close" in e_hist.columns and not e_hist["Close"].dropna().empty else None
    out["price_last"] = price_last
    # yfinance `info` は取得時点のスナップショットであり、過去基準日の比較には使えない。
    # 基準日が直近(今日から3日以内)の場合のみ同日値として参照し、それ以外は評価外とする。
    if (date.today() - as_of).days <= 3:
        prev_close = safe(info.get("previousClose"))
        nav = safe(info.get("navPrice"))
        stale = prev_close is not None and price_last is not None and abs(prev_close - price_last) / price_last > 0.02
        out["nav_vs_price"] = {"previousClose": prev_close,
                               "nav": nav,
                               "price_last_history": price_last,
                               "stale": stale,
                               "nav_status": "STALE_OR_MISSING" if (nav is None or stale) else "OK"}
    else:
        out["nav_vs_price"] = {"nav_status": "NOT_APPLICABLE",
                               "note": ("プレミアム/ディスカウントは日次NAV時系列が無料ソースにないため評価外。"
                                        "寄り付きの気配で確認すること。")}
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
    if facts.get("underlying", "NASDAQ100") == "NASDAQ100":
        queries = ["^NDX", "QQQ", f"{bare}.T"]
        fallback_queries = ["NASDAQ 100", "QQQ"]
    else:
        queries = ["^GSPC", "SPY", f"{bare}.T"]
        fallback_queries = ["S&P 500", "SPY"]
    seen: dict = {}
    for q in queries:
        for item in normalize_yfinance_news(fetch_yahoo_news(q, count=10)):
            seen[item.get("link") or item.get("title")] = item
    if not seen:
        for q in fallback_queries:
            for item in normalize_yfinance_news(fetch_yahoo_news(q, count=10)):
                seen[item.get("link") or item.get("title")] = item

    def _relevance(item) -> tuple:
        text = ((item.get("title") or "") + " " + (item.get("summary") or "")).lower()
        hits = sum(1 for k in NEWS_KEYWORDS if k.lower() in text)
        direct = 1 if bare in (item.get("title") or "") else 0
        return (direct, hits)

    items = sorted(seen.values(), key=_relevance, reverse=True)[:15]
    kw = [k for k in NEWS_KEYWORDS if any(
        k.lower() in ((i.get("title") or "") + (i.get("summary") or "")).lower() for i in items)]
    return {
        "ticker": bare,
        "as_of": as_of.isoformat(),
        "status": "OK" if items else "NO_COVERAGE",
        "news": items,
        "direct_coverage_count": sum(1 for i in items if bare in (i.get("title") or "")),
        "matched_keywords": kw,
        "coverage_note": ("インバースETF自体の個別報道は少ないため、原指数（NASDAQ100/S&P500）と"
                          "相場全体のヘッドラインを重視すること。"),
    }


def fetch_macro(as_of: date) -> dict:
    end = as_of + timedelta(days=1)
    start = as_of - timedelta(days=120)
    out: dict = {"as_of": as_of.isoformat()}
    for name, syms in [("nasdaq100", ["^NDX", "QQQ"]), ("sp500", ["^GSPC", "SPY"]),
                         ("nasdaq100_fut", ["NQ=F"]), ("sp500_fut", ["ES=F"]),
                         ("vix", ["^VIX"]),
                         ("us10y", ["^TNX"]), ("usd_jpy", ["JPY=X"]), ("oil", ["CL=F"])]:
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
                   "原指数のトレンド転換（上昇再開）はETFの売りシグナルになる。米国立会時間と東証の時差による織り込みラグに注意。")
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
