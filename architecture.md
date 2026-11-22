# Architecture — trading-agents-plugin

Agent-agnostic multi-agent trading analysis pipeline. The host agent
(Muse Code / Kimi Code / Grok Build) provides subagents; this repo provides
the instruction set (skills), entry points (commands), and data fetchers (scripts).

## Layout

- `skills/<name>/SKILL.md` — single source of truth for each analysis pipeline
  (trading-analysis-us, trading-analysis-jp, bond-etf-analysis, inverse-index-etf-jp, report-backtest).
- `.claude/skills/<name>` — symlinks to `skills/<name>` (Muse Code project skills).
- `.agents/skills`, `.kimi/skills` — symlinks to `.claude/skills` (shared content).
- `commands/*.md` — slash-command definitions (plugin install path).
- `.claude/commands/*.md` — copies for Muse Code project-scope commands.
- `scripts/fetch_*.py` — market-data fetchers (yfinance / J-Quants / FRED / BOJ / MOF).
- `scripts/market_data_utils.py` — shared indicator and formatting helpers.
- `reports/` — generated analysis reports `{date}_{ticker}_{engine}.md`.
- `backtests/` — generated backtest reports.

## Pipeline (skills/trading-analysis-us)

```
Phase 1 (parallel subagents): Technical + News + Fundamentals + Macro
Phase 2 (sequential):         Bull → Bear (rebuts Bull) → Aggressive / Conservative / Neutral risk
Phase 3:                      Research Manager synthesizes
Phase 4:                      Trader sets entry / stop / size
Phase 5:                      Portfolio Manager → BUY / SELL / HOLD
Phase 6:                      Report saved to reports/{date}_{ticker}_{engine}.md
```

9 subagents total, spawned via the host agent's built-in subagent/task tool.

## Data sources

- US tickers: yfinance only (no API key).
- Bond ETFs: yfinance + FRED API for the Treasury curve (optional key,
  falls back to yfinance `^TNX`/`^TYX` with a warning).
- Japan tickers: J-Quants API v2 (prices/financials; short-sale and margin
  data need Standard plan or higher), yfinance (news/indices/recent-price fill),
  BOJ time-series API, MOF JGB CSV, optional FRED cross-check.

## Conventions

- Engine suffix on reports defaults to `Claude`; override with a second
  command argument or the `ANALYST_ENGINE` env var.
- `.mcp.json` declares no MCP servers (no external services needed).
- Agent-facing docs (`AGENTS.md`, `CLAUDE.md`, `ANTIGRAVITY.md`) are symlinks
  to `README.md`; ignore files (`.antigravityignore`, `.kimiignore`) are
  symlinks to `.claudeignore`.
