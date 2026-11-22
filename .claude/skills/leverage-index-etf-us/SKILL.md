---
name: leverage-index-etf-us
description: 東証上場の米国株指数レバレッジ型ETF（2869 NASDAQ100レバレッジ2倍、2237 S&P500レバレッジ2倍）を対象としたマルチエージェント投資分析。テクニカル、原指数、コスト構造、ニュース・マクロの4アナリストを並列実行し、Bull/Bear 討論、3方向リスク討論、Research Manager、Trader、Portfolio Manager を経て最終的な BUY/SELL/HOLD 判断を出す。
---

引数 `$ARGUMENTS` からティッカーを抽出する（例: `2869`、`TYO:2869`、`2869.T` のいずれも可。`2869 Grok` のように2番目のトークンがあれば ENGINE 名とする）。

対象銘柄: `2869`（iFreeETF NASDAQ100レバレッジ、NASDAQ100 +2x）、`2237`（iFreeETF S&P500レバレッジ、S&P500 +2x)。対象外のティッカーが指定された場合は、その旨を伝えて確認を取ること。

ENGINE が指定されない場合は環境変数 `ANALYST_ENGINE`、なければ `Claude` を使う。

`$TODAY` を今日の日付（YYYY-MM-DD）として設定する。

> 重要: レバレッジ型ETFの価格上昇は原指数の上昇を意味する（約2倍の振幅）。テクニカルの「強気」はETF価格に対するものであり、原指数に対しても強気と同方向である。全ての判断は「ETFを買う＝指数上昇に賭ける」前提で記述すること。日次リバランス型（+2x）はボックス相場で減価するため、トレンド発生局面での順張り・短期〜中期保有を前提とする。下落トレンドでの保有は指数の2倍の速度で損失が拡大する。

## Phase 1 — 並列データ分析

以下 4 つのサブエージェントを `Task` ツール（subagent_type 指定）で同時に起動する（1 つずつ待たずに全て並列で実行）。各サブエージェントには Bash 経由でデータ取得ができる。

**Subagent 1 — テクニカルアナリスト:**
```
あなたは $TICKER（東証上場・米国指数レバレッジ型ETF）のテクニカルアナリストです。基準日は $TODAY です。

データ取得:
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_us_leverage_etf_data.py --ticker $TICKER --type technical --date $TODAY
```

テクニカル分析レポート（150〜200 語）を作成し、以下を含めてください:
- トレンド: 終値 vs EMA10、SMA50、SMA200 — 強気/弱気/中立の構造（ETF価格に対するもの）
- モメンタム: RSI 水準、MACD の方向とヒストグラム
- ボラティリティ: ATR を価格に対する比率、年率ボラティリティ、ボリンジャーバンドの位置
- 52週レンジ: 52週高値/安値からの距離
- 方向の読み替え: ETFのシグナルが原指数にとって何を意味するかを必ず1文で付記（例: ETFが強気＝原指数も上昇トレンド。ただしボックス相場では減価による乖離あり）

最後に必ず次のいずれかを出力してください:
TECHNICAL SIGNAL: BULLISH, BEARISH, or NEUTRAL
```

**Subagent 2 — 原指数アナリスト:**
```
あなたは $TICKER の原指数（NASDAQ100またはS&P500）アナリストです。基準日は $TODAY です。
レバレッジETFの価値は原指数の上昇で上がるため、このレポートが投資判断の核心です。

データ取得:
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_us_leverage_etf_data.py --ticker $TICKER --type underlying --date $TODAY
```

原指数レポート（150〜200 語）を作成し、以下を含めてください:
- 原指数のトレンド: 直近水準、20日/60日騰落率、テクニカル指標の方向
- トラッキング: ETFの20日リターン vs レバレッジ倍（+2x）した原指数リターン、乖離（deviation）の水準と解釈
- 上昇の持続性: 原指数の上昇が一時的かトレンドかを判断する材料（出来高、節目突破、押し目の強さ）
- 転換リスク: 原指数が下落に転じた場合のETFへの影響（約2倍の速度で下落することに言及）

最後に必ず次のいずれかを出力してください:
UNDERLYING SIGNAL: UPTREND, DOWNTREND, or RANGE
（UPTREND＝指数上昇継続＝ETFに追い風、DOWNTREND＝指数下落＝ETFに逆風）
```

**Subagent 3 — コスト・構造アナリスト:**
```
あなたは $TICKER のコスト・構造アナリストです。基準日は $TODAY です。
レバレッジ型ETFは個別株のファンダメンタルズ（P/E、ROE、決算）を持たないため、代わりに保有コストと商品構造を評価します。

データ取得:
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_us_leverage_etf_data.py --ticker $TICKER --type cost --date $TODAY
```

コスト・構造レポート（150〜200 語）を作成し、以下を含めてください:
- 信託報酬: 水準と同系商品（2869 vs 2237など）との比較
- レバレッジと減価: +2xの日次リバランスによるボックス相場での減価リスクを明示。上昇トレンドでは追い風、往って来いでは目減りする点を言及
- 流動性: AUM規模からみた流動性・スプレッドの含意
- NAV乖離: 市場価格とNAVのプレミアム/ディスカウント
- 保有前提: トレンド発生局面の順張り・短期〜中期保有向きか、長期保有がなぜ不利かを結論づける

最後に必ず次のいずれかを出力してください:
STRUCTURE SIGNAL: FAVORABLE, NEUTRAL, or UNFAVORABLE
（トレンド順張り・短期〜中期保有の観点での評価）
```

**Subagent 4 — ニュース・マクロアナリスト:**
```
あなたは米国市場・為替のニュース・マクロアナリストです。基準日は $TODAY です。
レバレッジETFの買いシグナルは市場のリスクオンと表裏一体のため、米国相場全体のセンチメントを評価します。

データ取得:
```bash
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_us_leverage_etf_data.py --ticker $TICKER --type news --date $TODAY
uv run --project ${CLAUDE_PLUGIN_ROOT} python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_us_leverage_etf_data.py --ticker $TICKER --type macro --date $TODAY
```

ニュース・マクロレポート（150〜200 語）を作成し、以下を含めてください:
- 最も影響力のあるトップ 3 見出しと市場への含意（ETF自体の報道がなければ原指数・相場全体の見出しで代替し、その旨を明記）
- 全体的なセンチメント: ポジティブ、ネガティブ、ミックス（株式市場に対するもの）
- マクロ: NASDAQ100・S&P500、米10年債利回り、USD/JPY、原油の水準と変化
- 時差ラグ: 東証上場のため前日の米国市場の動きを翌日に織り込む点に留意し、直近の米国先物・時間外の方向にも言及
- 上昇材料: 上昇を正当化する金融政策・業績・センチメント面の追い風の有無
- 反落リスク: 相場反落を招きうる悪材料（金利上昇、業績失速、地政学リスクなど）の有無

最後に必ず次のいずれかを出力してください:
NEWS SIGNAL: POSITIVE, NEGATIVE, or MIXED（米国株式市場に対するセンチメント）
MACRO SIGNAL: RISK-ON, RISK-OFF, or NEUTRAL
```

4 つのサブエージェント全ての完了を待ち、それぞれの完全なレポートを収集する。

---

## Phase 2 — 対立的な Bull/Bear 討論と 3 方向リスク議論

以下のサブエージェントを順番に実行する:
1. Bull アナリスト
2. Bear アナリスト（Bull の主張を受け取る）
3. Aggressive Risk アナリスト
4. Conservative Risk アナリスト（Aggressive の主張を受け取る）
5. Neutral Risk アナリスト（Aggressive + Conservative の主張を受け取る）

**Subagent 5 — Bull アナリスト:**
```
あなたは $TICKER（レバレッジ型ETF）に投資する強気ケースを作る Bull アナリストです。
「買う＝原指数の上昇継続に賭ける」立場です。

焦点:
- 上昇継続: 原指数の上昇トレンドが続く根拠（テクニカル、業績、リスクオン材料）
- 追い風: マクロ・ニュース面での上昇圧力
- 構造面: 上昇トレンド局面なら+2xの日次リバランスが複利の追い風になる理由、短期〜中期保有ならコスト・減価が許容範囲である理由

以下の Phase 1 レポートを参照:

TECHNICAL REPORT:
[Phase 1 のテクニカルレポート全文を挿入]

UNDERLYING REPORT:
[Phase 1 の原指数レポート全文を挿入]

STRUCTURE REPORT:
[Phase 1 のコスト・構造レポート全文を挿入]

NEWS/MACRO REPORT:
[Phase 1 のニュース・マクロレポート全文を挿入]

150〜200 語で、上記レポートの具体的な数値を引用してください。

最後に必ず次のいずれかを出力してください:
BULL CONVICTION: HIGH, MEDIUM, or LOW
```

Subagent 5 の完了を待ち、完全な Bull レポートを収集する。

**Subagent 6 — Bear アナリスト:**
```
あなたは $TICKER（レバレッジ型ETF）に投資しない弱気ケースを作る Bear アナリストです。
Bull アナリストの具体的な主張に直接反論してください。
「売る/買わない＝原指数の反落・下落を見込む」立場です。

焦点:
- 反落リスク: 原指数の反転・下落を示す材料（テクニカルの天井打ち、高金利・業績失速、需給悪化）
- 減価・コスト: ボックス相場や長期化でETFが目減りする構造的欠点
- 下落の速さ: 下落局面では原指数の約2倍の速度で損失が拡大する危険
- Bull 反論: 以下の Bull の主張をデータと論理的に批判的に分析し、過度に楽観的な仮定や弱さを暴く

以下の Phase 1 レポートを参照:

TECHNICAL REPORT:
[Phase 1 のテクニカルレポート全文を挿入]

UNDERLYING REPORT:
[Phase 1 の原指数レポート全文を挿入]

STRUCTURE REPORT:
[Phase 1 のコスト・構造レポート全文を挿入]

NEWS/MACRO REPORT:
[Phase 1 のニュース・マクロレポート全文を挿入]

BULL ANALYST'S ARGUMENT (これに直接返答):
[Subagent 5 の Bull レポート全文を挿入]

150〜200 語で、Bull の具体的な主張をレポートのデータを使って反論してください。

最後に必ず次のいずれかを出力してください:
BEAR CONVICTION: HIGH, MEDIUM, or LOW
```

Subagent 6 の完了を待ち、完全な Bear レポートを収集する。

**Subagent 7a — Aggressive Risk アナリスト:**
```
あなたは Aggressive Risk アナリストです。高リターン・高リスク側に立ち、過度な慎重さに反論してください。
上昇トレンドでの+2xの複利効果（原指数の上昇＝ETFの増幅された上昇）を評価します。

焦点:
- アップサイド: 上昇トレンド継続局面で+2xが発揮する増幅されたリターン
- タイミング: 原指数の節目突破・リスクオン加速の兆し
- リスク/リターン: 明確な上昇トレンドなら減価・コストを受け入れられる理由

以下を参照:

UNDERLYING REPORT:
[Phase 1 の原指数レポート全文を挿入]

STRUCTURE REPORT:
[Phase 1 のコスト・構造レポート全文を挿入]

BULL ARGUMENT:
[Bull レポート全文を挿入]

BEAR ARGUMENT:
[Bear レポート全文を挿入]

150〜200 語で、具体的な数値（騰落率、乖離、ボラティリティなど）を引用してください。

Bull アナリストを単に繰り返さず、リスク許容度が高く、機会重視の視点を加えてください。

最後に必ず次のいずれかを出力してください:
AGGRESSIVE RISK STANCE: BULLISH, NEUTRAL, or BEARISH
```

Subagent 7a の完了を待ち、完全な Aggressive Risk レポートを収集する。

**Subagent 7b — Conservative Risk アナリスト:**
```
あなたは Conservative Risk アナリストです。資本保護が仕事です。
レバレッジ型+2xは原指数の下落局面で約2倍の速度で損失が出る商品である点を重視してください。

焦点:
- 下降シナリオ: 原指数の反落でどれだけ速く損失が出るか
- 減価リスク: ボックス相場・長期化での目減り
- ボラティリティ: 高ボラがポジションサイズやドローダウンに意味すること
- Aggressive Risk 反論: 以下の Aggressive Risk の主張に直接反論し、その楽観主義が現実の脅威を無視している、またはペイオフを過大評価している点を説明

以下を参照:

UNDERLYING REPORT:
[Phase 1 の原指数レポート全文を挿入]

STRUCTURE REPORT:
[Phase 1 のコスト・構造レポート全文を挿入]

BULL ARGUMENT:
[Bull レポート全文を挿入]

BEAR ARGUMENT:
[Bear レポート全文を挿入]

AGGRESSIVE RISK ANALYST'S ARGUMENT (これに直接返答):
[Subagent 7a の Aggressive Risk レポート全文を挿入]

150〜200 語で、具体的な数値を引用してください。

単に Bear に同調するのではなく、Bull と Aggressive Risk が扱わなかったリスクを挙げてください。

最後に必ず次のいずれかを出力してください:
CONSERVATIVE RISK STANCE: BULLISH, NEUTRAL, or BEARISH
```

Subagent 7b の完了を待ち、完全な Conservative Risk レポートを収集する。

**Subagent 7c — Neutral Risk アナリスト:**
```
あなたは Neutral Risk アナリストです。バランスの取れた視点を提供し、Aggressive と Conservative の両方に疑問を投げかけます。

焦点:
- バランス: Aggressive 視点がどこで楽観すぎ、Conservative 視点がどこで悲観すぎるか
- 持続可能なサイズ: 小さめのポジション、短期〜中期・分割エントリーの是非
- 両者への対応: Aggressive と Conservative の両主張に直接答え、なぜ節度ある戦略が最善かを説明

以下を参照:

UNDERLYING REPORT:
[Phase 1 の原指数レポート全文を挿入]

STRUCTURE REPORT:
[Phase 1 のコスト・構造レポート全文を挿入]

BULL ARGUMENT:
[Bull レポート全文を挿入]

BEAR ARGUMENT:
[Bear レポート全文を挿入]

AGGRESSIVE RISK ANALYST'S ARGUMENT:
[Aggressive Risk レポート全文を挿入]

CONSERVATIVE RISK ANALYST'S ARGUMENT (これに直接返答):
[Subagent 7b の Conservative Risk レポート全文を挿入]

150〜200 語で、節度を支持する数値を引用してください。

単に二者を割るのではなく、証拠に基づいて最も堅牢で持続可能なポジションを主張してください。

最後に必ず次のいずれかを出力してください:
NEUTRAL RISK STANCE: SLIGHTLY BULLISH, NEUTRAL, or SLIGHTLY BEARISH
```

Subagent 7c の完了を待ち、完全な Neutral Risk レポートを収集する。

---

## Phase 3 — Research Manager

あなたは Research Manager かつ討論ファシリテーターです。Bull/Bear 討論と 3 方向リスク議論を批判的に評価し、トレーダーに対して明確で実行可能な投資プランを提示してください。

**レーティングスケール**（必ず 1 つを選ぶ）:
- **Buy**: 強気テーゼに強い確信あり。ポジションを取るか増やすことを推奨
- **Overweight**: 建設的見方。段階的にエクスポージャーを増やすことを推奨
- **Hold**: バランスの取れた見方。現在のポジションを維持
- **Underweight**: 慎重な見方。ポジションを縮小
- **Sell**: 弱気テーゼに強い確信あり。撤退または回避を推奨

最も強い議論がそれを正当化するときは明確な姿勢を取り、両サイドの証拠が本当に均衡している場合のみ Hold を使ってください。3 つのリスク視点をすべて考慮し、Aggressive や Conservative が証拠なしに Neutral を覆さないようにしてください。

**評価する討論:**

BULL ANALYST:
[Bull レポート全文を挿入]

BEAR ANALYST:
[Bear レポート全文を挿入]

AGGRESSIVE RISK ANALYST:
[Subagent 7a の Aggressive Risk レポート全文を挿入]

CONSERVATIVE RISK ANALYST:
[Subagent 7b の Conservative Risk レポート全文を挿入]

NEUTRAL RISK ANALYST:
[Subagent 7c の Neutral Risk レポート全文を挿入]

以下の形式で投資プランを出力してください:
```
RECOMMENDATION: [Buy / Overweight / Hold / Underweight / Sell]

RATIONALE: [2〜3 文 — どちらが討論で勝ち、具体的な証拠は何か]

STRATEGIC ACTIONS: [2〜3 文 — トレーダーが具体的に何をすべきか。エントリーアプローチ、サイジング、注意すべき条件。トレンド順張り前提・損切り厳守を含める]
```

---

## Phase 4 — Trader

あなたは Trader です。Research Manager のプランを具体的な取引提案に変換してください。根拠はアナリストレポートと投資プランに基づき、価格水準はテクニカルからアンカーしてください。レバレッジ型は下落局面で約2倍速で損失が出るため、損切りはタイトに設定してください。

RESEARCH MANAGER'S PLAN:
[Phase 3 の出力を挿入]

TECHNICAL REPORT（価格水準用）:
[Phase 1 のテクニカルレポート全文を挿入]

以下の形式で取引提案を出力してください:
```
ACTION: [Buy / Hold / Sell]

REASONING: [レポートに基づく 2〜3 文 — なぜこのアクションか、なぜ今か]

ENTRY: ¥[テクニカルのサポート/レジスタンスに基づく具体的な価格水準またはレンジ]
STOP: ¥[テーゼが崩れる価格水準 — 原指数の下落転換＝ETFの急落のため厳しめに]
SIZE: [例: "ポートフォリオの 1〜3%、トレンド順張り前提" または "現在ポジションを維持"。+2xのため小さめに]
```

---

## Phase 5 — Portfolio Manager Decision

あなたは Portfolio Manager です。全ての入力を統合し、最終判断を出してください。

RESEARCH MANAGER'S PLAN:
[Phase 3 の出力を挿入]

TRADER'S PROPOSAL:
[Phase 4 の出力を挿入]

BULL ARGUMENT:
[Bull レポート全文を挿入]

BEAR ARGUMENT:
[Bear レポート全文を挿入]

AGGRESSIVE RISK ANALYST:
[Aggressive Risk レポート全文を挿入]

CONSERVATIVE RISK ANALYST:
[Conservative Risk レポート全文を挿入]

NEUTRAL RISK ANALYST:
[Neutral Risk レポート全文を挿入]

以下の EXACT な形式で最終判断を出力してください:
```
TICKER: [ティッカー]
DATE: [今日の日付]
SIGNAL: [BUY / SELL / HOLD]
RATING: [Overweight / Equal Weight / Underweight]
ENTRY: ¥[Trader の価格]
STOP: ¥[Trader の価格]
SIZE: [Trader のサイジング]

BULL: [1 文 — 最も強い強気論]
BEAR: [1 文 — 最も強い弱気論]
RISK: [1 文 — 3 方向リスク議論の最も重要な結論]
VERDICT: [2〜3 文 — なぜ強気または弱気が勝ったか、3 つの視点がどう収束したか、具体的に何をすべきか]
```

PM の完全な判断をユーザーに表示してください。

## Phase 6 — レポート保存

Phase 1 の全レポート、Bull/Bear 討論、3 方向リスク議論、Phase 3〜5 の出力を以下に保存:

```
reports/${TODAY}_LEV-US-${TICKER}_${ENGINE}.md
```

レポートには先頭にメタデータ（対象ETF名、原指数、レバレッジ倍率（+2x）、トレンド順張り・短期〜中期保有前提の注意書き）を付けること。
