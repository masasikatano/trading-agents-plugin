# trading-agents-plugin

Multi-agent trading analysis skills for AI coding agents — runs on [Kimi Code](https://www.kimi.com/) and [Grok Build](https://grok.com/) with no external LLM API cost (uses the agent's built-in subagent capability).

## Setup

Clone the repo and install the Python data dependency (fetches market data via yfinance):

```bash
git clone https://github.com/lucemia/trading-agents-plugin
cd trading-agents-plugin
uv sync   # or: pip install yfinance pandas
```

The `skills/` directory is read automatically when you open this project in Kimi Code (project-scope skills). For other agents (e.g. Grok Build), point the agent at `skills/trading-analysis/SKILL.md` (and the `-jp` variant) as its instruction set — the skill files are agent-agnostic plain Markdown.

## Usage

```
/trading-analysis NVDA
/trading-analysis GOOG
/trading-analysis SOXL
```

The full analysis report is saved automatically to `reports/{date}_{ticker}_{engine}.md`
(e.g. `reports/20261024_NVDA_Kimi.md`). To override the engine suffix, pass it as a
second argument (`/trading-analysis NVDA Grok`) or set the `ANALYST_ENGINE` environment
variable; it defaults to `Kimi`.

### Japan equities (`trading-analysis-jp`)

For Tokyo Stock Exchange tickers, prefix with `TYO:`:

```
/trading-analysis-jp TYO:6702
```

This uses `scripts/fetch_jp_market_data.py`, which combines J-Quants API (prices/financials), yfinance (news, indices, recent price fill), BOJ API + MOF CSV + FRED API (Japanese rates).

Required environment variables:

```bash
JQUANTS_API_KEY=   # issued from the J-Quants API v2 dashboard
FRED_API_KEY=      # optional, used for Japanese-rate cross-check
```

### US Treasury bond ETFs (`bond-etf-analysis`)

For US Treasury-bond ETFs (EDV, TLT, SPTL, GOVT, VGLT, ...):

```
/bond-etf-analysis TLT
/bond-etf-analysis EDV Grok
```

This uses `scripts/fetch_bond_etf_data.py`, which combines yfinance (prices, fund data, dividends, news) and the FRED API (Treasury curve: DGS2/DGS10/DGS30/T10Y2Y/DFII10). The FRED key is optional — without it the rates fetch falls back to yfinance (^TNX/^TYX) with a warning.

```bash
FRED_API_KEY=      # optional, used for Treasury curve data (DGS2/DGS10/DGS30/T10Y2Y/DFII10)
```

### Report backtest (`report-backtest`)

After at least 7 calendar days, check what would have happened if you followed a saved analysis report (`SIGNAL` / `ENTRY` / `STOP`). Does not re-run the analysis pipeline.

```
/report-backtest reports/20260731_TYO6952_Grok.md
/report-backtest reports/20260731_TYO6952_Grok.md --eval 2026-08-24
/report-backtest 20260731
```

Writes `backtests/{report_date}_{ticker}_{eval_date}.md`. Batch runs also write `backtests/{report_date}_summary_{eval_date}.md`. Prices come from `scripts/fetch_backtest_prices.py` (J-Quants + yfinance for `TYO:`, yfinance otherwise). Verdicts are `ALIGNED` / `MISALIGNED` / `INCONCLUSIVE`. On `MISALIGNED`, the file includes suggested patches for `trading-analysis-jp` or `trading-analysis` (skills are not edited automatically).

## Pipeline

```
Phase 1 (parallel):    Technical + News + Fundamentals + Macro analyst
Phase 2 (sequential):  Bull → Bear rebuts Bull directly → Aggressive / Conservative / Neutral risk debate
Phase 3:               Research Manager synthesizes all three voices
Phase 4:               Trader sets entry / stop / size anchored to technicals
Phase 5:               Portfolio Manager → final BUY / SELL / HOLD
Phase 6:               Full report saved to reports/{date}_{ticker}_{engine}.md
```

9 subagents total. Each phase spawns subagents via the host agent's built-in subagent/task tool.

Data sources:
- US tickers: [yfinance](https://github.com/ranaroussi/yfinance) only — no API key required.
- Bond ETFs: yfinance (prices, fund data, dividends, news) + FRED API for the Treasury curve (optional key).
- Japan tickers: J-Quants API v2 (prices/financials), yfinance (news, indices, recent-price gap fill), BOJ time-series API, Japanese MOF JGB CSV, and optional FRED API for cross-checking Japanese rates.

## What each analyst covers

| Analyst | Coverage |
|---------|---------|
| **Technical** | EMA10/SMA50/SMA200 trend, RSI14, MACD, Bollinger Bands, ATR, key support/resistance |
| **News** | Top headlines, sentiment, sector tailwinds/headwinds, earnings signals |
| **Fundamentals** | P/E, forward P/E, PEG, P/B, revenue/earnings growth, margins, ROE, FCF, D/E ratio, current ratio, beta, short ratio, quarterly income/balance sheet statements, analyst consensus |
| **Macro** | S&P 500, 10Y Treasury, gold, oil news — geopolitical/monetary policy signals (US); Nikkei 225, USD/JPY, BOJ policy rate, JGB 10Y, US 10Y, oil (JP) |
| **Bull** | Strongest buy case using all Phase 1 data |
| **Bear** | Directly rebuts Bull's specific claims with data |
| **Aggressive Risk** | Champions the high-reward side — pushes back against overcaution and highlights upside optionality |
| **Conservative Risk** | Protects capital — surfaces balance-sheet, volatility, and macro tail risks that Bull/Aggressive gloss over |
| **Neutral Risk** | Balances both extremes — argues for a moderate, sustainable sizing/entry approach given the evidence |

## Sample output

```
TICKER: NVDA
DATE:   2026-05-02
SIGNAL: BUY
RATING: Overweight
ENTRY:  $197–$199 (tranche 1); $188–$190 (tranche 2 if macro deteriorates)
STOP:   $183 (below SMA200)
SIZE:   2–3% of portfolio initial; reserve 2% for second tranche

BULL: PEG 0.18, FCF $58.1B, net cash $51B, and 57 analysts pricing in 35% upside —
      NVDA's AI dominance is structurally mispriced.
BEAR: Beta 2.33 in RISK-OFF macro with crowded longs means a guidance miss could
      trigger a 20%+ unwind against a 30.7x P/B backdrop.
RISK: The three risk views converge on "respect the volatility" — Aggressive sees the
      risk/reward as favorable, Conservative flags beta/crowding, and Neutral lands on
      staged entry rather than full-sized commitment.
VERDICT: Bull wins on fundamentals — no operational weakness identified. The 3-way
         risk debate kept sizing disciplined: Conservative and Neutral views overrode
         Aggressive sizing, setting a 2–3% initial position with a second tranche near
         SMA50.
```

## Requirements

- An agent that supports subagents (e.g. [Kimi Code](https://www.kimi.com/) or [Grok Build](https://grok.com/))
- Python 3.10+, [uv](https://github.com/astral-sh/uv) (or pip)

## Inspiration

Inspired by [TradingAgents](https://github.com/TauricResearch/TradingAgents) — a multi-agent LLM trading framework by Tauric Research. This project adapts their analyst pipeline design as agent-agnostic Markdown skills, replacing the LangGraph/OpenAI stack with the host agent's built-in subagent capability and yfinance for free market data.

## License

MIT
