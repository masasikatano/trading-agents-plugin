# trading-agents-plugin とは何か

## 一言で言うと

「株式のティッカーシンボル（例：NVDA）を渡すと、複数の AI エージェントが協力しながら『買う・売る・持つ』の投資判断を出してくれる、Claude Code 用のプラグイン」です。

外部の LLM API（OpenAI など）を使わず、Claude Code 自体が備えているマルチエージェント機能だけで動きます。株価データは無料の Yahoo Finance 経由で取得します。

---

## なぜ作られたのか

普通に AI に「NVDA は買い？」と聞くと、1 つの回答者が偏った意見を出しがちです。  
このプロジェクトは、**複数の専門家が同時に分析し、議論し、最後に結論を出す**仕組みを再現しています。

元々は Tauric Research の「TradingAgents」というオープンソースが発想の源です。  
それを、Claude Code のプラグインとして手軽に使える形にアレンジしたものです。

---

## 全体の流れ

分析は 5 つのフェーズに分かれています。

```
Phase 1: 4 人のアナリストが並列でデータ分析
         └─ Technical（テクニカル）
         └─ News（ニュース・センチメント）
         └─ Fundamentals（ファンダメンタルズ）
         └─ Macro（マクロ経済）

Phase 2: 対立する意見を順番に議論
         └─ Bull（強気）
         └─ Bear（弱気）← Bull の主張を直接反論
         └─ Aggressive Risk（積極的リスク）
         └─ Conservative Risk（保守的リスク）
         └─ Neutral Risk（中立的リスク）

Phase 3: Research Manager（研究責任者）が総合評価

Phase 4: Trader（トレーダー）が具体的な入場・損切り・サイズを提案

Phase 5: Portfolio Manager（ポートフォリオマネージャー）が最終決定
```

合計 **9 体の AI エージェント** が動作します。

---

## 各エージェントがやっていること

| エージェント | 役割 |
|---|---|
| **Technical Analyst** | 株価チャートのトレンド、RSI、MACD、ボリンジャーバンド、ATR、サポート・レジスタンスを分析 |
| **News Analyst** | 最新ニュースの感情、セクターの追い風・逆風、決算・アナリストシグナルを評価 |
| **Fundamentals Analyst** | PER、PBR、成長率、利益率、ROE、フリーキャッシュフロー、貸借対照表、アナリスト目標株価などを分析 |
| **Macro Analyst** | S&P 500、10 年国債、金、原油のニュースから地政学・金融政策のリスクを把握 |
| **Bull** | 成長性、競争優位、好材料を強調して「買い」の強いケースを作る |
| **Bear** | Bull の主張に具体的なデータで反論し、リスク・課題を浮き彫りにする |
| **Aggressive Risk** | 高リスク・高リターン側に立ち、慎重すぎる意見に反論する |
| **Conservative Risk** | 資本保護を最優先し、バランスシート、ボラティリティ、マクロリスクを指摘する |
| **Neutral Risk** | 両極端を抑え、持続可能なエントリー・サイズを提案する |
| **Research Manager** | 議論を整理し、Buy / Overweight / Hold / Underweight / Sell の評価を出す |
| **Trader** | Research Manager の評価を元に、ENTRY（買い圏）、STOP（損切り）、SIZE（ポジションサイズ）を提示 |
| **Portfolio Manager** | 最終的な BUY / SELL / HOLD 判定とその根拠をまとめる |

---

## データはどこから来るのか

米国株は `scripts/fetch_market_data.py` が Yahoo Finance（yfinance ライブラリ）から無料でデータを取得します。

取得できるデータは 4 種類：

| タイプ | 取得内容 |
|---|---|
| `technical` | 終値、EMA10、SMA50、SMA200、RSI14、MACD、ボリンジャーバンド、ATR14、直近 10 日分の終値 |
| `news` | その銘柄に関する Yahoo Finance のニュースタイトル・概要・出版社 |
| `fundamentals` | 時価総額、PER、PBR、成長率、利益率、ROE、キャッシュ・債務、アナリスト レーティング・目標株価、四半期決算（損益計算書・貸借対照表・キャッシュフロー） |
| `macro` | S&P 500、10 年国債、金先物、原油先物に関するニュース |

日本株は `scripts/fetch_jp_market_data.py` が、以下のデータ源を組み合わせて取得します。

| データ種別 | 優先数据源 | 補完/フォールバック |
|---|---|---|
| 日本株 OHLC | J-Quants `/v2/equities/bars/daily` | yfinance（直近 12 週間など J-Quants 未提供分） |
| 日本株財務 | J-Quants `/v2/fins/summary` | yfinance（P/E、beta、アナリスト目標など） |
| 日本株ニュース | yfinance | — |
| 日銀政策金利 | BOJ API（FM01 / STRDCLUCON） | FRED API |
| 日本国債10年利回り | 財務省 CSV | FRED API（検証用） |
| 日経平均/円相場/米10年債/原油 | yfinance | — |
| 売上成長率/利益成長率 | J-Quants から自前計算 | — |

---

## 使い方

### Claude Code プラグインとして使う場合

```
/plugin marketplace add lucemia/trading-agents-plugin
/plugin install trading-agents-plugin
```

インストール後、

```
/trading-analysis NVDA
```

と打つだけで分析が始まります。

### 日本株版 `trading-analysis-jp`

東証上場銘柄を分析する場合は、以下のようにティッカーに `TYO:` プレフィックスを付けてください。

```
/trading-analysis-jp TYO:6702
```

以下はレポート保存込みのプロンプトです。
```
/trading-analysis-jp TYO:3132
を実行して、分析レポートを、
reports/20260731_TYO3132_Grok.md
に保存して。
```

内部的には `scripts/fetch_jp_market_data.py` が動作し、J-Quants API（財務・株価）+ yfinance（ニュース・指数・直近価格）+ BOJ API・財務省 CSV・FRED API（日本の金利マクロ）を組み合わせてデータを取得します。

必要な環境変数:

```bash
JQUANTS_API_KEY=   # J-Quants API v2 のダッシュボードで発行
FRED_API_KEY=      # 任意（日本金利データの補完・検証用）
```

#### データ取得を目視確認する

`scripts/fetch_jp_market_data.py` には `--verbose` フラグがあり、JSON 出力の前に人間が読みやすいサマリーを stderr に表示します。マクロ指標のドル円や日経平均、テクニカルの終値・RSI などが一目で確認できます。

```bash
# マクロ指標の確認（ドル円、日経平均、金利など）
uv run python scripts/fetch_jp_market_data.py --ticker TYO:6702 --type macro --date 2026-07-29 --verbose
```

出力例:

```text
[macro] 基準日: 2026-07-29
  日経平均: 61,867.43
  ドル円  : 159.61 円
  米10年債: 4.66 %
  原油    : 83.99 USD
  BOJ 政策金利: 0.98 %
  国債10年: 2.69 %
```

```bash
# テクニカル指標の確認
uv run python scripts/fetch_jp_market_data.py --ticker TYO:6702 --type technical --date 2026-07-29 --verbose
```

出力例:

```text
[technical] ティッカー: TYO:6702  基準日: 2026-07-29
  終値    : 3,844.00 円
  前日比  : 3.89 %
  52週高  : 4,636.00 円
  52週安  : 3,075.00 円
  RSI(14) : 72.03
  MACD    : 66.87
  データ源: J-Quants 291 日 / yfinance 349 日
```

`--verbose` を付けない場合は従来通り JSON のみが stdout に出力されます。

### 手動で使う場合

```bash
git clone https://github.com/lucemia/trading-agents-plugin
cd trading-agents-plugin
uv sync   # pip install yfinance pandas python-dotenv requests でも可
```

その後、Claude Code の skill ディレクトリにコマンド定義をコピーします。

```bash
mkdir -p ~/.claude/skills/trading-analysis
cp .claude/skills/trading-analysis/SKILL.md ~/.claude/skills/trading-analysis/
```

**注意：** skill ファイル内の Python スクリプトパスが、自分の環境と一致していることを確認してください。

---

## 実際の出力例

```
TICKER: NVDA
DATE:   2026-07-29
SIGNAL: BUY
RATING: Overweight
ENTRY:  $192–$197
STOP:   $188
SIZE:   2–4% of portfolio in 2 tranches

BULL: 成長率 +85%、営業利益率 66%、フォワード PER ~15.3、目標株価 ~$303 と、
      今の押し目は割安ではないが成長調整後では魅力的。
BEAR: EMA10/SMA50 割れ、AI 半導体セクターのローテーション、beta 2.21、
      1.3 の強気アナリスト consensus は崩壊リスクを孕んでいる。
RISK: Neutral Risk の中道案が優位。ファンダは強いが、ベータと集中投資リスクを
      考慮して 2 回に分けたエントリーと硬い損切りが必要。
VERDICT: 強気のフランチャイズ論は弱気のタイミング警戒を上回るが、
         ポジションサイズは慎重に。$192–$197 で段階的に買い、$188 で損切り。
```

---

## 注意点・既知の問題

### 1. ハードコードされたパス

skill ファイル（`.claude/skills/trading-analysis/SKILL.md` や `skills/trading-analysis/SKILL.md` など）には、作者の PC の絶対パスが埋め込まれていることがあります。

```bash
# 例（これは作者の環境向け）
uv run --project /Users/davidchen/repo/TradingAgents python /Users/davidchen/repo/TradingAgents/scripts/fetch_market_data.py ...
```

そのまま実行すると、`No such file or directory` で失敗します。  
**自分の環境のパスに置き換える必要があります。**

現在のリポジトリでは、すでにローカルパス（`/home/masasikatano/project/trading-agents-plugin/...`）に修正されています。

### 2. 外部 API キーは不要

分析自体に OpenAI API キーなどは不要です。  
`.env` にある `OPENAI_API_KEY` は、別の日次 Slack 投稿機能で使う想定で、メインの `/trading-analysis` には関係ありません。

### 3. これは投資助言ではありません

あくまでデモ・研究用の自動分析パイプラインです。  
実際の投資判断は自分の責任で行ってください。

### 4. 日本株版の制限事項

- ニュースは英語主体（yfinance のデータ）
- J-Quants 無料プランでは、株価データに最大 12 週間の遅延があります。不足分は yfinance で補完
- 指数データ（日経平均、円相場、米10年債、原油）は J-Quants 無料プランでは未取得のため yfinance を使用
- 日本の金利データ（BOJ政策金利・日本国債10年利回り）は BOJ API・財務省 CSV・FRED API から取得
- `shortRatio` などの空売り指標は J-Quants 有料プラン限定のため未取得

---

## ファイル構成の概要

```
trading-agents-plugin/
├── README.md                          # 英語版の公式 README
├── README_human.md                    # このファイル（人間向け日本語解説）
├── pyproject.toml                     # Python パッケージ設定
├── uv.lock                            # 依存関係ロックファイル
├── scripts/
│   ├── fetch_market_data.py           # 米国株データ取得（Yahoo Finance）
│   ├── fetch_jp_market_data.py        # 日本株データ取得（J-Quants + BOJ + MOF + FRED + yfinance）
│   └── market_data_utils.py           # 共有ユーティリティ
├── .claude/skills/
│   ├── trading-analysis/SKILL.md      # 米国株用 skill（シンボリックリンク）
│   └── trading-analysis-jp/SKILL.md   # 日本株用 skill（シンボリックリンク）
├── skills/
│   ├── trading-analysis/SKILL.md      # プラグイン配布用 skill 定義
│   └── trading-analysis-jp/SKILL.md   # 日本株版 skill 定義
└── reports/                           # 実行レポート・調査用レポートのサンプル
    └── 20260729_NVDA_Grok.md
```

---

## まとめ

このプロジェクトは、**1 人の AI ではなく「9 人の専門家チーム」が議論して投資判断を出す仕組み**を、Claude Code プラグインとして実現したものです。

- 入力：ティッカーシンボル（例：NVDA）
- データ：Yahoo Finance（無料）
- 処理：テクニカル・ニュース・ファンダ・マクロを並列分析 → Bull/Bear 議論 → 3 方向リスク議論 → 最終判断
- 出力：BUY / SELL / HOLD、エントリー圏、損切りライン、ポジションサイズ、根拠

「AI に投資判断を任せたい」というよりは、「AI を使って構造化された投資検討プロセスを再現する」ツール、と捉えるのが近いです。
