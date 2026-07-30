#!/usr/bin/env python3
"""Shared utilities for market-data fetch scripts."""
import json
import math

import pandas as pd


def safe(val):
    """Convert a scalar to a rounded float, treating NaN/Inf as None."""
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


def compute_technicals(df):
    """Compute technical indicator series from an OHLCV DataFrame.

    `df` must have columns: Close, High, Low, Volume.
    Returns a dict of pandas Series.
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    ema10 = close.ewm(span=10).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100)

    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    boll_upper = sma20 + 2 * std20
    boll_lower = sma20 - 2 * std20

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    return {
        "ema10": ema10,
        "sma50": sma50,
        "sma200": sma200,
        "rsi14": rsi,
        "macd": macd,
        "macd_signal": signal,
        "sma20": sma20,
        "std20": std20,
        "boll_upper": boll_upper,
        "boll_lower": boll_lower,
        "atr14": atr,
        "52w_high": close.rolling(252).max(),
        "52w_low": close.rolling(252).min(),
    }


def make_price_summary(close):
    """Return the price block used by both US and JP technical fetchers."""
    prev_close = float(close.iloc[-2]) if len(close) >= 2 else None
    return {
        "current": safe(close.iloc[-1]),
        "prev_close": safe(prev_close) if prev_close is not None else None,
        "change_pct": safe((float(close.iloc[-1]) / prev_close - 1) * 100)
        if prev_close is not None and prev_close != 0
        else None,
        "52w_high": safe(close.rolling(252).max().iloc[-1]),
        "52w_low": safe(close.rolling(252).min().iloc[-1]),
    }


def make_indicator_summary(indicators):
    """Return the indicators block from a compute_technicals() result."""
    return {
        "ema10": safe(indicators["ema10"].iloc[-1]),
        "sma50": safe(indicators["sma50"].iloc[-1]),
        "sma200": safe(indicators["sma200"].iloc[-1]),
        "rsi14": safe(indicators["rsi14"].iloc[-1]),
        "macd": safe(indicators["macd"].iloc[-1]),
        "macd_signal": safe(indicators["macd_signal"].iloc[-1]),
        "macd_hist": safe(indicators["macd"].iloc[-1] - indicators["macd_signal"].iloc[-1]),
        "boll_upper": safe(indicators["boll_upper"].iloc[-1]),
        "boll_mid": safe(indicators["sma20"].iloc[-1]),
        "boll_lower": safe(indicators["boll_lower"].iloc[-1]),
        "atr14": safe(indicators["atr14"].iloc[-1]),
    }


def recent_closes(close, n=10):
    """Return the last n closes as {YYYY-MM-DD: price}."""
    return {
        row.date().isoformat(): safe(val)
        for row, val in close.tail(n).items()
    }


def normalize_yfinance_news(news):
    """Normalize yfinance news items to a common schema."""
    items = []
    for n in (news or [])[:15]:
        items.append({
            "title": n.get("content", {}).get("title", n.get("title", "")),
            "summary": n.get("content", {}).get("summary", ""),
            "publisher": n.get("content", {}).get("provider", {}).get("displayName", ""),
        })
    return items


def statement_to_dict(df):
    """Convert a yfinance quarterly statement DataFrame to a compact dict."""
    if df is None or df.empty:
        return {}
    out = {}
    for col in df.columns[:2]:
        label = col.date().isoformat() if hasattr(col, "date") else str(col)
        out[label] = {
            str(idx): (safe(v) if isinstance(v, float) else v)
            for idx, v in df[col].items()
            if v is not None and not (isinstance(v, float) and math.isnan(v))
        }
    return out


def dump_json(obj, indent=2):
    return json.dumps(obj, indent=indent, default=str)
