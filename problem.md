# Problem: `/trading-analysis NVDA` 実行可否

調査日: 2026-07-29  
対象: `trading-agents-plugin`（ワークスペース: `/home/masasikatano/project/trading-agents-plugin`）

## 総合判定

| 観点 | 判定 | 説明 |
|------|------|------|
| スキル/コマンドの存在 | 可 | 本リポジトリの `trading-analysis` が認識済み |
| 市場データ取得（yfinance） | 可（ローカルパス時） | `uv sync` 後、4タイプとも NVDA で成功 |
| コマンド記載どおりのパスでの取得 | **不可** | 作者マシンの絶対パスがハードコードされている |
| フル分析パイプライン（9エージェント） | 条件付きで可 | パス修正（または実行時にローカルパスへ読み替え）すれば実行可能 |
| 外部 LLM API キー | 不要 | 分析はエージェント自身が行う。データは yfinance のみ |

**結論:** 現状のスキル文言をそのまま機械的に実行すると **Phase 1 のデータ取得で失敗する**。  
ローカルプロジェクトパスに読み替えれば **今すぐ実行可能**。恒久対応はスキル内パス修正。

---

## 何が `/trading-analysis` か

定義ファイル（同一内容が3箇所）:

- `.claude/commands/trading-analysis.md`（Grok が参照しているパス）
- `commands/trading-analysis.md`
- `skills/trading-analysis/SKILL.md`

パイプライン:

1. **Phase 1（並列）**: Technical / News / Fundamentals / Macro
2. **Phase 2（直列）**: Bull → Bear → Aggressive / Conservative / Neutral Risk
3. **Phase 3**: Research Manager
4. **Phase 4**: Trader（ENTRY / STOP / SIZE）
5. **Phase 5**: Portfolio Manager（最終 BUY/SELL/HOLD）

設計意図: Claude Code の `Agent` ツール相当を使い、LLM API 課金なしで分析。データは yfinance。

README の想定利用先は **Claude Code プラグイン**。Grok Build では `spawn_subagent` で同等の再現が可能。

---

## ブロッカー: ハードコードされた絶対パス

スキル内の fetch コマンドがすべて作者環境向け:

```bash
# technical / news
uv run --project /Users/davidchen/repo/TradingAgents \
  python /Users/davidchen/repo/TradingAgents/scripts/fetch_market_data.py ...

# fundamentals / macro
uv run --project /Users/davidchen/repo/claude-trading-agents \
  python /Users/davidchen/repo/claude-trading-agents/scripts/fetch_market_data.py ...
```

### 実測

```
warning: Project directory `/Users/davidchen/repo/TradingAgents` does not exist...
can't open file '.../fetch_market_data.py': [Errno 2] No such file or directory
```

→ スキルを一字一句どおりに走らせると **Phase 1 全滅**。

### 正しいローカル相当

```bash
cd /home/masasikatano/project/trading-agents-plugin
uv run python scripts/fetch_market_data.py --ticker NVDA --type technical --date 2026-07-29
# type: technical | news | fundamentals | macro
# macro 時: --ticker MACRO --type macro
```

README も「clone 後にパスを自分の環境に合わせて更新せよ」と明記している。

このリポジトリの `scripts/fetch_market_data.py` は `technical` / `news` / `fundamentals` / `macro` の4タイプすべてに対応済み。  
スキル側だけが、別リポジトリ名（`TradingAgents` / `claude-trading-agents`）を指している不整合がある。

---

## データ層の実測結果（ローカルパス）

`uv sync` 成功（yfinance / pandas 等 29 packages）。  
`.env` は本コマンドには不要（`.env.example` の OPENAI/SLACK は daily Slack 用）。

| type | 結果 | サンプル |
|------|------|----------|
| technical | OK | price ≈ 197.01, RSI14 ≈ 44.16, SMA200 ≈ 192.82 |
| news | OK | news_count=10（半導体セルオフ等） |
| fundamentals | OK | trailingPE≈30.12, forwardPE≈15.31, beta≈2.21, targetMean≈302.83 |
| macro | OK | macro_news_count=18 |

---

## 実行環境の差分（Claude Code vs Grok）

| 項目 | Claude Code 想定 | 本 Grok 環境 |
|------|------------------|--------------|
| サブエージェント | `Agent` tool | `spawn_subagent`（general-purpose + Bash） |
| コマンド登録 | Claude plugin / `~/.claude/commands` | プロジェクト skill として認識 |
| スクリプトパス | 要ローカル置換 | 同上・要置換 |
| Python | `uv` 必須 | `uv 0.11.6` あり、`uv sync` 済み |

Grok でもフルパイプラインは技術的に実行可能。subagent 9 本前後＋親の合成で時間がかかる。

---

## 実行可能性の整理

### そのまま `/trading-analysis NVDA` をスキル記述どおりに実行

- **不可**（データ fetch が存在しないパスを叩く）

### パスをローカルに読み替えて実行

- **可**
- 前提: リポジトリで `uv sync` 済み、yfinance へのネットワークアクセス可

### 恒久的にコマンド一発で成功させるには

1. 3ファイルの fetch パスをリポジトリ相対（またはワークスペースルート検出）に統一する  
2. technical/news と fundamentals/macro で別リポジトリを指している不整合を解消する  
3. （任意）README の Manual install 手順と整合させる

---

## 次の一手（候補）

1. **今すぐ分析を回す** — パスをローカルに読み替えた上で `/trading-analysis NVDA` 相当を実行  
2. **先にスキルを直す** — ハードコードパスをこのリポジトリ向けに修正してから実行  
3. **調査のみで終了** — 本ファイルが成果物
