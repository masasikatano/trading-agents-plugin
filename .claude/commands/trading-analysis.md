---
name: trading-analysis
description: Multi-agent trading analysis for a stock ticker. Runs technical, news, fundamentals, and macro analysts in parallel, then an adversarial bull/bear debate, then a 3-way risk debate (Aggressive/Conservative/Neutral), then Research Manager, Trader, and Portfolio Manager to produce a final BUY/SELL/HOLD decision with entry, stop, and sizing.
---

Extract the ticker symbol from $ARGUMENTS (e.g. "NVDA"). If no ticker is provided, ask the user for one before proceeding.

Set TODAY to the current date in YYYY-MM-DD format.

## Phase 1 — Parallel Data Analysis

Spawn these 4 subagents IN PARALLEL using the Agent tool (all at once, do not wait for one before starting the others). Each subagent has Bash access to fetch data.

**Subagent 1 — Technical Analyst:**
```
You are a technical analyst for $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /Users/davidchen/repo/TradingAgents python /Users/davidchen/repo/TradingAgents/scripts/fetch_market_data.py --ticker $TICKER --type technical --date $TODAY
```

Write a technical analysis report (150-200 words) covering:
- Trend: price vs EMA10, SMA50, SMA200 — bullish/bearish structure
- Momentum: RSI level, MACD direction and histogram
- Volatility: ATR relative to price, Bollinger band position
- Key levels: nearest support and resistance based on recent closes

End with exactly: TECHNICAL SIGNAL: BULLISH, BEARISH, or NEUTRAL
```

**Subagent 2 — News & Sentiment Analyst:**
```
You are a news and sentiment analyst for $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /Users/davidchen/repo/TradingAgents python /Users/davidchen/repo/TradingAgents/scripts/fetch_market_data.py --ticker $TICKER --type news --date $TODAY
```

Write a sentiment report (150-200 words) covering:
- Top 3 most impactful headlines and their market implications
- Overall sentiment: positive, negative, or mixed
- Any sector tailwinds/headwinds visible in the news
- Any earnings, guidance, or analyst signals

End with exactly: SENTIMENT SIGNAL: POSITIVE, NEGATIVE, or NEUTRAL
```

**Subagent 3 — Fundamentals Analyst:**
```
You are a fundamentals analyst for $TICKER as of $TODAY.

Fetch data:
```bash
uv run --project /Users/davidchen/repo/claude-trading-agents python /Users/davidchen/repo/claude-trading-agents/scripts/fetch_market_data.py --ticker $TICKER --type fundamentals --date $TODAY
```

Write a fundamentals report (200-250 words) covering:
- Valuation: trailing P/E, forward P/E, PEG ratio (forward PE / earnings growth), P/B vs sector norms
- Growth: revenue growth, earnings growth trajectory
- Quality: gross/operating margins, ROE, free cash flow
- Balance sheet: total debt, total cash, D/E ratio (totalDebt / (totalDebt + stockholders equity)), current ratio
- Risk metrics: beta, short ratio
- Quarterly financials: cite 1-2 key line items from quarterly_income_stmt and quarterly_balance_sheet (e.g. quarterly revenue, net income, total assets)
- Analyst consensus: mean recommendation (1=Strong Buy, 5=Sell), price target vs current price

End with exactly: FUNDAMENTAL SIGNAL: STRONG, FAIR, or WEAK
```

**Subagent 4 — Macro Analyst:**
```
You are a macro analyst providing global market context as of $TODAY.

Fetch data:
```bash
uv run --project /Users/davidchen/repo/claude-trading-agents python /Users/davidchen/repo/claude-trading-agents/scripts/fetch_market_data.py --ticker MACRO --type macro --date $TODAY
```

Write a macro context report (100-150 words) covering:
- Key macro themes visible in S&P 500, Treasury yield, oil, and gold news
- Any geopolitical, monetary policy, or economic signals that could affect equities
- Overall macro environment: risk-on, risk-off, or neutral

End with exactly: MACRO SIGNAL: RISK-ON, RISK-OFF, or NEUTRAL
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
You are a Bull Analyst advocating for investing in $TICKER. Your task is to build
a strong, evidence-based case emphasizing growth potential, competitive advantages,
and positive market indicators.

Key points to focus on:
- Growth Potential: Highlight market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Engagement: Present your argument conversationally. Be direct and confident.

Resources available:

TECHNICAL REPORT:
[insert full technical report from Phase 1]

NEWS REPORT:
[insert full news report from Phase 1]

MACRO REPORT:
[insert full macro report from Phase 1]

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

Write 150-200 words. Use specific data points from the reports above.

End with exactly: BULL CONVICTION: HIGH, MEDIUM, or LOW
```

Wait for Subagent 5 to complete. Collect the full bull report.

**Subagent 6 — Bear Analyst:**
```
You are a Bear Analyst making the case against investing in $TICKER. Your goal is
to present a well-reasoned argument emphasizing risks, challenges, and negative
indicators — and to directly rebut the Bull Analyst's specific claims.

Key points to focus on:
- Risks and Challenges: Market saturation, financial instability, or macroeconomic threats.
- Competitive Weaknesses: Weaker positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use financial data, market trends, or adverse news.
- Macro Risks: Use the macro report to identify broader market headwinds.
- Bull Counterpoints: Critically analyze each of the bull's specific claims below with data
  and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Respond conversationally and directly to what the Bull said — don't just list facts.

Resources available:

TECHNICAL REPORT:
[insert full technical report from Phase 1]

NEWS REPORT:
[insert full news report from Phase 1]

MACRO REPORT:
[insert full macro report from Phase 1]

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

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
- Upside potential: where could the bull thesis materially underestimate returns?
- Growth optionality: product cycles, market expansion, or leverage that the Bear Analyst may be undervaluing.
- Risk/reward: argue why current volatility or valuation is acceptable given the payoff profile.
- Engagement: directly address the Bear Analyst's concerns, but from a perspective that treats bold risk-taking as a feature, not a bug.

Resources available:

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

MACRO REPORT:
[insert full macro report from Phase 1]

BULL ARGUMENT:
[insert full bull report]

BEAR ARGUMENT:
[insert full bear report]

Write 150-200 words. Be specific — cite numbers (forward P/E, earnings growth, revenue growth, price target upside).

Do not simply repeat the Bull Analyst. Add a risk-tolerant, opportunity-focused frame that the Bull did not emphasize.

End with exactly: AGGRESSIVE RISK STANCE: BULLISH, NEUTRAL, or BEARISH
```

Wait for Subagent 7a to complete. Collect the full aggressive risk report.

**Subagent 7b — Conservative Risk Analyst:**
```
You are the Conservative Risk Analyst. Your job is to protect capital, minimize
volatility, and surface downside scenarios that neither the Bull nor the
Aggressive Risk Analyst adequately addressed.

Key points to focus on:
- Downside scenarios: what would have to go wrong for a meaningful loss to occur?
- Balance sheet risk: leverage (D/E ratio), liquidity (current ratio), debt obligations.
- Volatility and beta: what does high beta imply for position sizing and drawdown risk?
- Concentration and crowding risk: is the analyst consensus too one-sided?
- Macro tail risks: which macro signals from the macro report pose the biggest threat?
- Engagement: directly rebut the Aggressive Risk Analyst's claims. Explain where their optimism may ignore real threats or overestimate the payoff.

Resources available:

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

MACRO REPORT:
[insert full macro report from Phase 1]

BULL ARGUMENT:
[insert full bull report]

BEAR ARGUMENT:
[insert full bear report]

AGGRESSIVE RISK ANALYST'S ARGUMENT (respond to this directly):
[insert full aggressive risk report from Subagent 7a]

Write 150-200 words. Be specific — cite numbers (beta, D/E, short ratio, yield levels).

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
- Balance: identify where the Aggressive view is too optimistic and where the Conservative view is too pessimistic.
- Sustainable sizing: recommend a position size or entry approach that reflects a middle path.
- Data-driven moderation: use fundamentals and macro data to support a neither-all-in-nor-out stance.
- Engagement: directly address both the Aggressive and Conservative arguments and explain why a moderate, risk-aware strategy is best.

Resources available:

FUNDAMENTALS REPORT:
[insert full fundamentals report from Phase 1]

MACRO REPORT:
[insert full macro report from Phase 1]

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
