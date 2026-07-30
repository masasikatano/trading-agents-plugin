---
name: trading-analysis-jp
description: 東証上場銘柄を対象としたマルチエージェントによる投資分析。テクニカル、ニュース、ファンダメンタルズ、マクロの4アナリストを並列実行し、Bull/Bear 討論、3方向リスク討論、Research Manager、Trader、Portfolio Manager を経て最終的な BUY/SELL/HOLD 判断を出す。
---

引数 `$ARGUMENTS` からティッカーを抽出する（例：`TYO:6702`）。ティッカーがない場合は、実行前にユーザーに尋ねること。

`$TODAY` を今日の日付（YYYY-MM-DD）として設定する。

## Phase 1 — 並列データ分析

以下 4 つのサブエージェントを `Agent` ツールで同時に起動する（1 つずつ待たずに全て並列で実行）。各サブエージェントには Bash 経由でデータ取得ができる。

**Subagent 1 — テクニカルアナリスト:**
```
あなたは $TICKER（東証上場銘柄）のテクニカルアナリストです。基準日は $TODAY です。

データ取得:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_jp_market_data.py --ticker $TICKER --type technical --date $TODAY
```

テクニカル分析レポート（150〜200 語）を作成し、以下を含めてください:
- トレンド: 終値 vs EMA10、SMA50、SMA200 — 強気/弱気/中立の構造
- モメンタム: RSI 水準、MACD の方向とヒストグラム
- ボラティリティ: ATR を価格に対する比率、ボリンジャーバンドの位置
- 重要水準: 直近 10 日分の終値に基づく近いサポートとレジスタンス

最後に必ず次のいずれかを出力してください:
TECHNICAL SIGNAL: BULLISH, BEARISH, or NEUTRAL
```

**Subagent 2 — ニュース・センチメントアナリスト:**
```
あなたは $TICKER（東証上場銘柄）のニュース・センチメントアナリストです。基準日は $TODAY です。

データ取得:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_jp_market_data.py --ticker $TICKER --type news --date $TODAY
```

センチメントレポート（150〜200 語）を作成し、以下を含めてください:
- 最も影響力のあるトップ 3 見出しと市場への含意
- 全体的なセンチメント: ポジティブ、ネガティブ、ミックス
- ニュースから読み取れるセクターの追い風/逆風
- 決算、業績予想、アナリストシグナルの有無

最後に必ず次のいずれかを出力してください:
SENTIMENT SIGNAL: POSITIVE, NEGATIVE, or NEUTRAL
```

**Subagent 3 — ファンダメンタルズアナリスト:**
```
あなたは $TICKER（東証上場銘柄）のファンダメンタルズアナリストです。基準日は $TODAY です。

データ取得:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_jp_market_data.py --ticker $TICKER --type fundamentals --date $TODAY
```

ファンダメンタル分析レポート（200〜250 語）を作成し、以下を含めてください:
- バリュエーション: trailing P/E、forward P/E、P/B、セクターノルムとの比較
- 成長性: 売上高（Sales）と営業利益（OP）、純利益（NP）の前年同期比（YoY）成長率トレンド。J-Quants の `jquants_summary` に含まれる `sales_growth`、`operating_profit_growth`、`net_income_growth`、`eps_growth` は、同一四半期・同一通期を前年と比較した YoY 成長率
- 収益性: 粗利率、営業利益率、ROE、フリーキャッシュフロー
- 貸借対照表: 総資産、純資産、負債、株式数（BPS）
- リスク指標: beta、配当利回り（dividendYield）
- アナリストコンセンサス: レコメンデーション平均値（1=強気買い、5=売り）、目標株価 vs 現在価格
- 日本企業特有の視点: 3 月決算、配当・自社株買い、持ち合い解消やガバナンス改革への言及

最後に必ず次のいずれかを出力してください:
FUNDAMENTAL SIGNAL: STRONG, FAIR, or WEAK
```

**Subagent 4 — マクロアナリスト:**
```
あなたは日本市場のマクロアナリストです。基準日は $TODAY です。

データ取得:
```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_jp_market_data.py --ticker MACRO --type macro --date $TODAY
```

マクロ環境レポート（100〜150 語）を作成し、以下を含めてください:
- 日経平均（^N225）、USD/JPY（JPY=X）、米 10 年債利回り（^TNX）、原油（CL=F）の最新水準と変化
- 日銀政策金利（boj_policy_rate）と日本国債 10 年利回り（jgb_10y）の動向
- 金融政策、為替、地政学リスクが日本株に与える影響
- 全体的なマクロ環境: リスクオン、リスクオフ、中立

最後に必ず次のいずれかを出力してください:
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
あなたは $TICKER に投資する強気ケースを作る Bull アナリストです。

焦点:
- 成長ポテンシャル: 市場機会、売上予想、スケーラビリティ
- 競争優位: 独自製品、強いブランド、優位な市場ポジション
- ポジティブ指標: 財務健全性、業界トレンド、最近の好材料

以下の Phase 1 レポートを参照:

TECHNICAL REPORT:
[Phase 1 のテクニカルレポート全文を挿入]

NEWS REPORT:
[Phase 1 のニュースレポート全文を挿入]

MACRO REPORT:
[Phase 1 のマクロレポート全文を挿入]

FUNDAMENTALS REPORT:
[Phase 1 のファンダメンタルレポート全文を挿入]

150〜200 語で、上記レポートの具体的な数値を引用してください。

最後に必ず次のいずれかを出力してください:
BULL CONVICTION: HIGH, MEDIUM, or LOW
```

Subagent 5 の完了を待ち、完全な Bull レポートを収集する。

**Subagent 6 — Bear アナリスト:**
```
あなたは $TICKER に投資しない弱気ケースを作る Bear アナリストです。Bull アナリストの具体的な主張に直接反論してください。

焦点:
- リスクと課題: 市場成熟、財務不安定性、マクロ経済的脅威
- 競争上の弱み: 弱いポジション、イノベーション減速、ライバルからの脅威
- ネガティブ指標: 財務データ、市場トレンド、ネガティブニュース
- マクロリスク: マクロレポートから広い市場の逆風を特定
- Bull 反論: 以下の Bull の主張をデータと論理的に批判的に分析し、過度に楽観的な仮定や弱さを暴く

以下の Phase 1 レポートを参照:

TECHNICAL REPORT:
[Phase 1 のテクニカルレポート全文を挿入]

NEWS REPORT:
[Phase 1 のニュースレポート全文を挿入]

MACRO REPORT:
[Phase 1 のマクロレポート全文を挿入]

FUNDAMENTALS REPORT:
[Phase 1 のファンダメンタルレポート全文を挿入]

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

焦点:
- アップサイドポテンシャル: Bull テーゼがリターンを過小評価している可能性
- 成長オプション: 製品サイクル、市場拡大、レバレッジ
- リスク/リターン: 現在のボラティリティやバリュエーションが、ペイオフプロファイルを考慮すれば受け入れられる理由

以下を参照:

FUNDAMENTALS REPORT:
[Phase 1 のファンダメンタルレポート全文を挿入]

MACRO REPORT:
[Phase 1 のマクロレポート全文を挿入]

BULL ARGUMENT:
[Bull レポート全文を挿入]

BEAR ARGUMENT:
[Bear レポート全文を挿入]

150〜200 語で、具体的な数値（forward P/E、利益成長率、売上成長率、目標株価アップサイドなど）を引用してください。

Bull アナリストを単に繰り返さず、リスク許容度が高く、機会重視の視点を加えてください。

最後に必ず次のいずれかを出力してください:
AGGRESSIVE RISK STANCE: BULLISH, NEUTRAL, or BEARISH
```

Subagent 7a の完了を待ち、完全な Aggressive Risk レポートを収集する。

**Subagent 7b — Conservative Risk アナリスト:**
```
あなたは Conservative Risk アナリストです。資本保護、ボラティリティ最小化、Bull と Aggressive Risk が十分に扱わなかった下降リスクを浮き彫りにすることが仕事です。

焦点:
- 下降シナリオ: どういうことが起きれば大きな損失になるか
- 貸借対照表リスク: レバレッジ（D/E）、流動性、債務
- ボラティリティと beta: 高 beta がポジションサイズやドローダウンに意味すること
- 集中・過熱リスク: アナリストコンセンサスが一方偏りになっていないか
- マクロ・テールリスク: マクロレポートのどのシグナルが最大の脅威か
- Aggressive Risk 反論: 以下の Aggressive Risk の主張に直接反論し、その楽観主義が現実の脅威を無視している、またはペイオフを過大評価している点を説明

以下を参照:

FUNDAMENTALS REPORT:
[Phase 1 のファンダメンタルレポート全文を挿入]

MACRO REPORT:
[Phase 1 のマクロレポート全文を挿入]

BULL ARGUMENT:
[Bull レポート全文を挿入]

BEAR ARGUMENT:
[Bear レポート全文を挿入]

AGGRESSIVE RISK ANALYST'S ARGUMENT (これに直接返答):
[Subagent 7a の Aggressive Risk レポート全文を挿入]

150〜200 語で、具体的な数値（beta、D/E、空売り比率、金利水準など）を引用してください。

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
- 持続可能なサイズ: 中道を反映したポジションサイズやエントリーアプローチを推奨
- データに基づく節度: ファンダメンタルとマクロデータを使って、全押しでも全撤退でもない立場を支持
- 両者への対応: Aggressive と Conservative の両主張に直接答え、なぜ節度あるリスク認識戦略が最善かを説明

以下を参照:

FUNDAMENTALS REPORT:
[Phase 1 のファンダメンタルレポート全文を挿入]

MACRO REPORT:
[Phase 1 のマクロレポート全文を挿入]

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

STRATEGIC ACTIONS: [2〜3 文 — トレーダーが具体的に何をすべきか。エントリーアプローチ、サイジング、注意すべき条件]
```

---

## Phase 4 — Trader

あなたは Trader です。Research Manager のプランを具体的な取引提案に変換してください。根拠はアナリストレポートと投資プランに基づき、価格水準はテクニカルからアンカーしてください。

RESEARCH MANAGER'S PLAN:
[Phase 3 の出力を挿入]

TECHNICAL REPORT（価格水準用）:
[Phase 1 のテクニカルレポート全文を挿入]

以下の形式で取引提案を出力してください:
```
ACTION: [Buy / Hold / Sell]

REASONING: [レポートに基づく 2〜3 文 — なぜこのアクションか、なぜ今か]

ENTRY: ¥[テクニカルのサポート/レジスタンスに基づく具体的な価格水準またはレンジ]
STOP: ¥[テーゼが崩れる価格水準]
SIZE: [例: "ポートフォリオの 3〜5%、2 回に分けて追加" または "現在ポジションを維持"]
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
VERDICT: [2〜3 文 — なぜ強気または弱気が勝ったか、3 つのリスク視点がどう収束したか、具体的に何をすべきか]
```

PM の完全な判断をユーザーに表示してください。
