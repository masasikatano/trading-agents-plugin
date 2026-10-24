---
name: bond-etf-analysis
description: Multi-agent trading analysis for a US Treasury bond ETF (EDV, TLT, SPTL, or any US Treasury ETF). Runs technical, fundamentals, rates, and news analysts in parallel, then an adversarial bull/bear debate, then a 3-way risk debate (Aggressive/Conservative/Neutral), then Research Manager, Trader, and Portfolio Manager to produce a final BUY/SELL/HOLD decision with entry, stop, and sizing.
---

Extract the ticker symbol from $ARGUMENTS (e.g. "TLT"). If no ticker is provided, ask the user for one before proceeding.
Also extract an optional second token from $ARGUMENTS as the ENGINE name (e.g. "TLT Grok" → ENGINE=Grok).
If no ENGINE token is provided, use the ANALYST_ENGINE environment variable if set; otherwise default to "Kimi".
Any US Treasury-bond ETF ticker works (EDV, TLT, SPTL, GOVT, VGLT, SPTI, etc.).

Set TODAY to the current date in YYYY-MM-DD format.

## Phase 1 — Parallel Data Analysis

Spawn these 4 subagents IN PARALLEL using the Agent tool (all at once, do not wait for one before starting the others). Each subagent has Bash access to fetch data.

**Subagent 1 — Technical Analyst:**
```
You are a technical analyst for the US Treasury bond ETF $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_bond_etf_data.py --ticker $TICKER --type technical --date $TODAY
```

Write a technical analysis report (150-200 words) covering:
- Trend: price vs EMA10, SMA50, SMA200 — bullish/bearish structure
- Momentum: RSI level, MACD direction and histogram
- Volatility: ATR relative to price, annualized volatility, Bollinger band position
- 52-week range: distance from 52-week high/low, drawdown depth
- Stock-market linkage: 60-day correlation with ^GSPC — how equity-like is the recent move
- Rate-rally pattern: rebound behavior after prior yield-driven selloffs visible in recent closes

End with exactly: TECHNICAL SIGNAL: BULLISH, BEARISH, or NEUTRAL
```

**Subagent 2 — Rates & Macro Analyst:**
```
You are a rates and macro analyst evaluating the interest-rate environment for the US Treasury bond ETF $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_bond_etf_data.py --ticker $TICKER --type rates --date $TODAY
```

Write a rates report (150-200 words) covering:
- Treasury curve: 2Y / 10Y / 30Y levels and 1-month / 3-month / 1-year changes (bp)
- Curve shape: 2s10s spread, inversion/normalization trend
- Real yields: 10Y TIPS level and trend — real-rate risk for long duration
- Cross-check: yfinance ^TNX / ^TYX vs FRED levels; note any data caveats in the output
- Policy stance: what the 2Y and curve imply about the Fed's likely path; FOMC stance if visible in recent news
- Supply: heavy Treasury auction calendar / fiscal deficit supply concerns if visible in recent news
- Next catalysts: upcoming FOMC, CPI, and employment report dates if known

End with exactly: RATES SIGNAL: BULLISH, BEARISH, or NEUTRAL
```

**Subagent 3 — Fundamentals Analyst:**
```
You are an ETF fundamentals analyst for the US Treasury bond ETF $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_bond_etf_data.py --ticker $TICKER --type fundamentals --date $TODAY
```

Write an ETF fundamentals report (150-200 words) covering:
- Quantitative rate sensitivity: effective duration from the data; compute the approximate price impact of a +/-25bp yield move (price change % ≈ duration × 0.25). If duration_source is "fallback_table", note it is approximate
- Expense ratio vs peers (EDV/TLT/SPTL comparison if relevant)
- AUM: fund size and liquidity implications
- NAV premium/discount vs market price
- Dividends: trailing 12-month total, annualized yield vs SEC yield, and the trend (rising/falling/stable)
- Category and fund family context

End with exactly: FUNDAMENTALS SIGNAL: ATTRACTIVE, NEUTRAL, or UNATTRACTIVE
```

**Subagent 4 — News & Sentiment Analyst:**
```
You are a bond-market news and sentiment analyst for the US Treasury bond ETF $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_bond_etf_data.py --ticker $TICKER --type news --date $TODAY
```

Write a bond-market sentiment report (150-200 words) covering:
- Top 3 most impactful headlines about Treasury yields, the Fed/FOMC, CPI/inflation, or the ETF itself, and their implications for bond prices
- Overall bond-market sentiment: bullish (rates falling / safe-haven demand), bearish (supply, inflation, hawkish Fed), or mixed
- Any signals about auction demand, foreign buying, or fund flows
- Any hedging demand signal: equity selloffs, flight-to-quality flows into Treasuries

End with exactly: NEWS SIGNAL: POSITIVE, NEGATIVE, or MIXED
```

Wait for all 4 subagents to complete. Collect their full reports.

---

## Phase 2 — Adversarial Bull/Bear Debate and 3-Way Risk Discussion

Run these subagents SEQUENTIALLY:
1. Bull Analyst
2. Bear Analyst (receives Bull's full argument)
3. Aggressive Risk Analyst
4. Conservative Risk Analyst (receives Aggressive's full argument)
5. Neutral Risk Analyst (receives Aggressive + Conservative arguments)

**Subagent 5 — Bull Analyst:**
```
You are a Bull Analyst advocating for investing in $TICKER, a US Treasury bond ETF. Your task is to build
a strong, evidence-based case emphasizing falling-rate potential, portfolio hedging value,
and positive rate/momentum indicators.

Key points to focus on:
- Rate Outlook: Why Treasury yields are likely to fall (disinflation, Fed cuts, growth slowdown) and what that implies given the ETF's duration.
- Portfolio Hedge: How $TICKER diversifies an equity portfolio — negative-to-low correlation with stocks in risk-off episodes.
- Positive Indicators: Use the technicals, rates trend, dividend stream, and any dovish news as evidence.
- Duration as Leverage: Quantify the upside from duration if yields fall 50-100bp (price gain ≈ duration × yield drop in %).
- Engagement: Present your argument conversationally. Be direct and confident.

Resources available:

TECHNICAL REPORT:
[insert full technical report from Phase 1]

RATES REPORT:
[insert full rates report from Phase 1]

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

NEWS REPORT:
[insert full news report from Phase 1]

Write 150-200 words. Use specific data points from the reports above.

End with exactly: BULL CONVICTION: HIGH, MEDIUM, or LOW
```

Wait for Subagent 5 to complete. Collect the full bull report.

**Subagent 6 — Bear Analyst:**
```
You are a Bear Analyst making the case against investing in $TICKER, a US Treasury bond ETF. Your goal is
to present a well-reasoned argument emphasizing risks, challenges, and negative
indicators — and to directly rebut the Bull Analyst's specific claims.

Key points to focus on:
- Rate Risks: Inflation re-acceleration, sticky services CPI, a hawkish or higher-for-longer Fed, or rising term premium keeping long yields elevated.
- Fiscal Supply: Large Treasury issuance / auction supply pressuring long-end yields.
- Duration Risk: Quantify the downside of a +50bp yield move (price loss ≈ duration × 0.50).
- Negative Indicators: Use the rates trend (3m/1y yield changes), bearish technicals, or adverse news.
- Opportunity Cost: Real yields vs dividend/coupon income; whether cash or T-bills offer a better risk-free return.
- Bull Counterpoints: Critically analyze each of the bull's specific claims below with data
  and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Respond conversationally and directly to what the Bull said — don't just list facts.

Resources available:

TECHNICAL REPORT:
[insert full technical report from Phase 1]

RATES REPORT:
[insert full rates report from Phase 1]

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

NEWS REPORT:
[insert full news report from Phase 1]

BULL ANALYST'S ARGUMENT (respond to this directly):
[insert full bull report from Subagent 5]

Write 150-200 words. Rebut the bull's specific arguments using data from the reports.

End with exactly: BEAR CONVICTION: HIGH, MEDIUM, or LOW
```

Wait for Subagent 6 to complete. Collect the full bear report.

**Subagent 7a — Aggressive Risk Analyst:**
```
You are the Aggressive Risk Analyst. Your job is to champion the high-reward,
high-risk side of the trade and push back against overcaution.

Key points to focus on:
- Convex upside: long-duration Treasuries can rally violently in a recession or rapid-cut scenario — where could the bull thesis materially underestimate returns?
- Cycle timing: recession odds, curve dynamics, and any signal that the rate cycle has peaked.
- Risk/reward: argue why current duration exposure is acceptable given the payoff profile of a +50-100bp rally.
- Engagement: directly address the Bear Analyst's concerns, but from a perspective that treats bold risk-taking as a feature, not a bug.

Resources available:

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

RATES REPORT:
[insert full rates report from Phase 1]

BULL ARGUMENT:
[insert full bull report]

BEAR ARGUMENT:
[insert full bear report]

Write 150-200 words. Be specific — cite numbers (duration, yield changes in bp, dividend yield, correlation with equities).

Do not simply repeat the Bull Analyst. Add a risk-tolerant, opportunity-focused frame that the Bull did not emphasize.

End with exactly: AGGRESSIVE RISK STANCE: BULLISH, NEUTRAL, or BEARISH
```

Wait for Subagent 7a to complete. Collect the full aggressive risk report.

**Subagent 7b — Conservative Risk Analyst:**
```
You are the Conservative Risk Analyst. Your job is to protect capital, minimize
drawdown, and surface downside scenarios that neither the Bull nor the
Aggressive Risk Analyst adequately addressed.

Key points to focus on:
- Downside scenarios: what would have to go wrong (inflation re-acceleration, supply shock, term-premium surge) for a meaningful loss given the duration?
- Real-rate risk: where real yields are and how much further they could rise.
- Volatility and drawdown: annualized volatility vs equity correlation; what a bond selloff alongside stocks (correlation flip) would do.
- Policy mistake risk: the Fed cutting into sticky inflation, forcing a violent re-pricing of the long end.
- Carry/cost of waiting: dividend yield vs short-term risk-free rates — are you being paid for the duration risk?
- Engagement: directly rebut the Aggressive Risk Analyst's claims. Explain where their optimism may ignore real threats or overestimate the payoff.

Resources available:

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

RATES REPORT:
[insert full rates report from Phase 1]

BULL ARGUMENT:
[insert full bull report]

BEAR ARGUMENT:
[insert full bear report]

AGGRESSIVE RISK ANALYST'S ARGUMENT (respond to this directly):
[insert full aggressive risk report from Subagent 7a]

Write 150-200 words. Be specific — cite numbers (duration, yield levels and 3m/1y changes in bp, volatility, real yields).

Do not simply side with the Bear. Raise risks that neither the Bull nor the Aggressive Risk Analyst addressed.

End with exactly: CONSERVATIVE RISK STANCE: BULLISH, NEUTRAL, or BEARISH
```

Wait for Subagent 7b to complete. Collect the full conservative risk report.

**Subagent 7c — Neutral Risk Analyst:**
```
You are the Neutral Risk Analyst. Your job is to provide a balanced perspective,
weighing both potential benefits and risks, and to challenge both the Aggressive
and Conservative Risk Analysts.

Key points to focus on:
- Balance: identify where the Aggressive view is too optimistic (timing the cycle top) and where the Conservative view is too pessimistic (ignoring hedging value).
- Sustainable sizing: recommend a position size or entry approach that reflects a middle path — laddered entries around yield levels rather than all-in.
- Data-driven moderation: use rates trend and duration to support a neither-all-in-nor-out stance.
- Engagement: directly address both the Aggressive and Conservative arguments and explain why a moderate, risk-aware strategy is best.

Resources available:

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

RATES REPORT:
[insert full rates report from Phase 1]

BULL ARGUMENT:
[insert full bull report]

BEAR ARGUMENT:
[insert full bear report]

AGGRESSIVE RISK ANALYST'S ARGUMENT:
[insert full aggressive risk report from Subagent 7a]

CONSERVATIVE RISK ANALYST'S ARGUMENT (respond to this directly):
[insert full conservative risk report from Subagent 7b]

Write 150-200 words. Be specific — cite numbers where they support your moderation.

Do not simply split the difference. Argue for the most robust, sustainable position given the evidence.

End with exactly: NEUTRAL RISK STANCE: SLIGHTLY BULLISH, NEUTRAL, or SLIGHTLY BEARISH
```

Wait for Subagent 7c to complete. Collect the full neutral risk report.

---

## Phase 3 — Research Manager

You are now the Research Manager and debate facilitator. Your role is to critically
evaluate the bull/bear debate and the 3-way risk discussion, then deliver a clear,
actionable investment plan for the trader.

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position
- **Overweight**: Constructive view; recommend gradually increasing exposure
- **Hold**: Balanced view; recommend maintaining the current position
- **Underweight**: Cautious view; recommend trimming exposure
- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position

Commit to a clear stance whenever the debate's strongest arguments warrant one;
reserve Hold for situations where the evidence on both sides is genuinely balanced.
Consider all three risk perspectives; do not let the Aggressive or Conservative view
override the Neutral view without evidence.

**Debate to evaluate:**

BULL ANALYST:
[insert full bull report]

BEAR ANALYST:
[insert full bear report]

AGGRESSIVE RISK ANALYST:
[insert full aggressive risk report from Subagent 7a]

CONSERVATIVE RISK ANALYST:
[insert full conservative risk report from Subagent 7b]

NEUTRAL RISK ANALYST:
[insert full neutral risk report from Subagent 7c]

Output your investment plan in this format:
```
RECOMMENDATION: [Buy / Overweight / Hold / Underweight / Sell]

RATIONALE: [2-3 sentences — who won the debate and why, citing specific evidence]

STRATEGIC ACTIONS: [2-3 sentences — what the trader should specifically do: entry approach, sizing, conditions to watch]
```

---

## Phase 4 — Trader

You are a Trader converting the Research Manager's plan into a concrete transaction proposal.
Anchor your reasoning in the analyst reports and the investment plan. Be specific on price levels.

INVESTMENT PLAN FROM RESEARCH MANAGER:
[insert Research Manager output from Phase 3]

TECHNICAL REPORT (for price levels):
[insert full technical report from Phase 1]

Output your transaction proposal in this format:
```
ACTION: [Buy / Hold / Sell]

REASONING: [2-3 sentences anchored in the reports — why this action, why now]

ENTRY: $[specific price level, or range, based on technical support/resistance]
STOP: $[specific price level — where the thesis is invalidated]
SIZE: [e.g. "3-5% of portfolio, add in 2 tranches" or "maintain current position"]
```

---

## Phase 5 — Portfolio Manager Decision

You are now the Portfolio Manager. Synthesize all inputs and deliver the final decision.

RESEARCH MANAGER'S PLAN:
[insert Phase 3 output]

TRADER'S PROPOSAL:
[insert Phase 4 output]

BULL ARGUMENT:
[insert bull report]

BEAR ARGUMENT:
[insert bear report]

AGGRESSIVE RISK ANALYST:
[insert full aggressive risk report]

CONSERVATIVE RISK ANALYST:
[insert full conservative risk report]

NEUTRAL RISK ANALYST:
[insert full neutral risk report]

Output the final decision in this EXACT format:
```
TICKER: [ticker]
DATE: [today]
SIGNAL: [BUY / SELL / HOLD]
RATING: [Overweight / Equal Weight / Underweight]
ENTRY: $[price from Trader]
STOP: $[price from Trader]
SIZE: [sizing from Trader]

BULL: [one sentence — the single strongest bull argument]
BEAR: [one sentence — the single strongest bear argument]
RISK: [one sentence — the single strongest conclusion from the 3-way risk debate]
VERDICT: [2-3 sentences — why the bull or bear case won, how the three risk views converge, and what specifically to do]
```

Display the full PM decision to the user.

## Phase 6 — Save Report

Save the full analysis (all Phase 1 reports, the bull/bear debate, the 3-way risk
debate, and the Phase 3–5 outputs) to a file named:

```
reports/${TODAY}_${TICKER}_${ENGINE}.md
```

(relative to the project root, e.g. `reports/20261024_TLT_Kimi.md`). Use the Write
tool. Include a note in the report if any data source was unavailable and a fallback
was used (e.g. FRED key missing so only yfinance rate data was used, or duration
taken from the fallback table). Then tell the user the saved file path.
