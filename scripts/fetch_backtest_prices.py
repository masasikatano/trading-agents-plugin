#!/usr/bin/env python3
"""OHLCV window for report-backtest. Numbers only — no thesis scoring.

Usage:
  python scripts/fetch_backtest_prices.py --ticker TYO:6952 --from 2026-07-31 --to 2026-08-24
  python scripts/fetch_backtest_prices.py --ticker NVDA --from 2026-07-29 --to 2026-08-24
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))

from market_data_utils import dump_json, safe


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.sort_index()


def _yf_ohlcv(ticker: str, start: date, end: date) -> pd.DataFrame:
    hist = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat())
    if hist.empty:
        return pd.DataFrame()
    hist = hist.rename(columns={
        "Open": "Open", "High": "High", "Low": "Low",
        "Close": "Close", "Volume": "Volume",
    })
    return _normalize_index(hist)[["Open", "High", "Low", "Close", "Volume"]]


def _jp_ohlcv(ticker: str, start: date, end: date) -> pd.DataFrame:
    import fetch_jp_market_data as jp

    norm = jp.normalize_ticker(ticker)
    try:
        jq = jp.fetch_jquants_bars(norm["jquants"], start, end)
    except Exception:
        jq = pd.DataFrame()
    yf_bars = jp._yf_ticker_history(norm["yfinance"], start, end + timedelta(days=1))
    if jq.empty and yf_bars.empty:
        return pd.DataFrame()
    if jq.empty:
        combined = yf_bars
    elif yf_bars.empty:
        combined = jq
    else:
        combined = jq.combine_first(yf_bars)
    combined = combined.dropna(subset=["Close"])
    return _normalize_index(combined)


def _is_jp(ticker: str) -> bool:
    t = ticker.strip().upper()
    return t.startswith("TYO:") or t.endswith(".T") or t.isdigit()


def _default_benchmark(ticker: str) -> str:
    return "^N225" if _is_jp(ticker) else "^GSPC"


def _bars_to_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for idx, row in df.iterrows():
        rows.append({
            "date": idx.date().isoformat(),
            "open": safe(row.get("Open")),
            "high": safe(row.get("High")),
            "low": safe(row.get("Low")),
            "close": safe(row.get("Close")),
            "volume": safe(row.get("Volume")),
        })
    return rows


def _pct(end: float | None, start: float | None) -> float | None:
    if end is None or start is None or start == 0:
        return None
    return round((end / start - 1) * 100, 4)


def _anchor_on_or_before(df: pd.DataFrame, as_of: date):
    if df.empty:
        return None
    subset = df[df.index.date <= as_of]
    if subset.empty:
        return None
    return subset.iloc[-1]


def fetch_window(ticker: str, from_date: date, to_date: date, benchmark: str | None) -> dict:
    if to_date < from_date:
        return {"error": "--to must be on or after --from"}

    pad_start = from_date - timedelta(days=10)
    yf_end = to_date + timedelta(days=1)
    bench_sym = benchmark or _default_benchmark(ticker)

    if _is_jp(ticker):
        bars = _jp_ohlcv(ticker, pad_start, to_date)
    else:
        bars = _yf_ohlcv(ticker, pad_start, yf_end)

    if bars.empty:
        return {"error": f"No price data for {ticker}"}

    bench = _yf_ohlcv(bench_sym, pad_start, yf_end)

    report_row = _anchor_on_or_before(bars, from_date)
    eval_row = _anchor_on_or_before(bars, to_date)
    if report_row is None or eval_row is None:
        return {"error": f"Insufficient bars for {ticker} in {from_date}..{to_date}"}

    report_day = report_row.name.date()
    eval_day = eval_row.name.date()

    after = bars[bars.index.date > report_day]
    next_row = after.iloc[0] if not after.empty else None
    window = bars[(bars.index.date > report_day) & (bars.index.date <= eval_day)]

    report_close = safe(report_row["Close"])
    eval_close = safe(eval_row["Close"])
    next_open = safe(next_row["Open"]) if next_row is not None else None
    if next_open is None and next_row is not None:
        next_open = safe(next_row["Close"])

    win_high = safe(window["High"].max()) if not window.empty else None
    win_low = safe(window["Low"].min()) if not window.empty else None

    bench_report = _anchor_on_or_before(bench, from_date)
    bench_eval = _anchor_on_or_before(bench, to_date)
    bench_report_close = safe(bench_report["Close"]) if bench_report is not None else None
    bench_eval_close = safe(bench_eval["Close"]) if bench_eval is not None else None

    stock_ret = _pct(eval_close, report_close)
    bench_ret = _pct(bench_eval_close, bench_report_close)
    excess = None
    if stock_ret is not None and bench_ret is not None:
        excess = round(stock_ret - bench_ret, 4)

    from_exec = next_open if next_open is not None else report_close
    exec_to_eval = _pct(eval_close, from_exec)

    return {
        "ticker": ticker,
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "calendar_days": (to_date - from_date).days,
        "report_trading_day": report_day.isoformat(),
        "eval_trading_day": eval_day.isoformat(),
        "report_close": report_close,
        "next_session": {
            "date": next_row.name.date().isoformat() if next_row is not None else None,
            "open": next_open,
            "close": safe(next_row["Close"]) if next_row is not None else None,
        },
        "eval_close": eval_close,
        "window": {
            "trading_days": int(len(window)),
            "high": win_high,
            "low": win_low,
            "bars": _bars_to_rows(window),
        },
        "returns": {
            "stock_pct_report_close_to_eval": stock_ret,
            "stock_pct_next_open_to_eval": exec_to_eval,
            "benchmark": bench_sym,
            "benchmark_pct": bench_ret,
            "excess_pct_vs_benchmark": excess,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", default=None)
    parser.add_argument("--benchmark", default=None)
    args = parser.parse_args()

    from_date = date.fromisoformat(args.from_date)
    to_date = date.fromisoformat(args.to_date) if args.to_date else date.today()
    print(dump_json(fetch_window(args.ticker, from_date, to_date, args.benchmark)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
