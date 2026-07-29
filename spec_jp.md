# trading-analysis-jp 作成計画書（Option A）

## 1. 目的

既存の `trading-analysis` スキル（米国株向け多エージェント分析）をベースに、**東証（Tokyo Stock Exchange）上場銘柄** を対象とした新スキル `trading-analysis-jp` を作成する。初回の検証対象銘柄は **富士通（TYO: 6702 / yfinance: 6702.T）** とする。

本計画書は `spec_jp.md` としてプロジェクトルートに保存する。

## 2. 現状把握

### 2.1 既存スキルの構成

- スキルファイル: `skills/trading-analysis/SKILL.md`
- データ取得スクリプト: `scripts/fetch_market_data.py`
- パイプライン:
  1. Phase 1: 4 つの分析エージェントを並列実行（テクニカル、ニュース、ファンダメンタル、マクロ）
  2. Phase 2: Bull/Bear 討論 + Aggressive/Conservative/Neutral リスク討論
  3. Phase 3: Research Manager による統合判断
  4. Phase 4: Trader によるエントリー/ストップ/サイズ提案
  5. Phase 5: Portfolio Manager による最終判定

### 2.2 既存データ取得スクリプトの動作確認

富士通（6702.T）に対して実際に取得テストを実施した結果:

- **technical（yfinance）**: 取得成功（終値、RSI、MACD、ボリンジャー、ATR など）
- **fundamentals（yfinance）**: 一部取得成功（P/E、P/B、ROE、総資産、負債、純資産、目標株価など）
- **fundamentals（J-Quants）**: 取得成功。売上高・営業利益・純利益・EPS・BPS・配当・業績予想など、yfinance では null になりやすい成長率系指標も自前計算可能
- **news（yfinance）**: 取得成功（英語ニュースが主体）
- **macro（yfinance）**: 既存は S&P 500、米国10年債、金、原油が対象 → 日本市場には不十分

**結論**: 日本株の財務・価格データは **J-Quants API（JPX 公式）** の方が完全。ニュース・マクロ・直近価格は yfinance で補完するハイブリッド構成が最適。

### 2.3 日本市場への適用時の差分

| 項目 | 既存（米国） | 日本版（東証） |
|------|-------------|---------------|
| ティッカー形式 | `NVDA` | `TYO:6702` または `6702.T` |
| 通貨 | USD | JPY |
| マクロ指標 | S&P 500, 米10年債, 金, 原油 | 日経平均、USD/JPY、日本国債/BOJ動向、グローバル指標 |
| 会計年度 | 12月 | 多くは3月（富士通も3月決算） |
| 市場特性 | 株式分割・買い戻し文化 | 持ち合い解消、ガバナンス改革、配当・自社株買い増加 |
| ニュース言語 | 英語主体 | 英語 + 日本語情報の可能性（今回は yfinance 英語主体のまま） |
| データソース | yfinance のみ | **J-Quants（財務・価格メイン）+ yfinance（ニュース・マクロ・直近価格補完）** |
| データ欠損 | 少ない | yfinance 単体では成長率系が null になりやすいが、**J-Quants で補完可能** |

## 3. 採用アプローチ：Option A

**新規スキル `trading-analysis-jp` を独立して作成する。**

- 既存 `trading-analysis` のエージェントフローはそのまま再利用
- 日本市場に合わせてティッカー正規化、マクロ指標、プロンプト、通貨表記を変更
- データ取得スクリプトは既存 `fetch_market_data.py` を拡張し、`--market jp` オプションを追加
- **日本株データ源は J-Quants API をメインとし、yfinance はニュース・マクロ・直近価格の補完に回す**
- `.claude/skills/trading-analysis-jp/SKILL.md` にシンボリックリンクを配置し、プラグインとして利用可能にする

### 採用理由

- 日本株と米国株で明確に異なる市場コンテキストがあるため、独立スキルの方が保守性が高い
- 既存スキルの動作を壊さない
- 将来、他の日本株（トヨタ、ソフトバンクG など）への展開が容易

## 4. 作成・変更ファイル

### 4.1 新規作成

| ファイル | 内容 |
|---------|------|
| `skills/trading-analysis-jp/SKILL.md` | 日本株版マルチエージェント分析スキル |
| `spec_jp.md` | 本計画書をプロジェクトルートに保存 |

### 4.2 修正

| ファイル | 修正内容 |
|---------|---------|
| `scripts/fetch_market_data.py` | `--market jp` オプション追加、J-Quants API クライアント統合、日本マクロ指標取得関数追加、ティッカー正規化対応 |
| `README.md` または `README_human.md` | `trading-analysis-jp` の使い方を追記 |
| `.env.example` | `JQUANTS_API_KEY` 追加 |

### 4.3 シンボリックリンク

| リンク | 実体 |
|-------|------|
| `.claude/skills/trading-analysis-jp/SKILL.md` | `skills/trading-analysis-jp/SKILL.md` |

## 5. 実装ステップ

### Step 1: データ取得スクリプトの拡張（J-Quants 統合）

`scripts/fetch_market_data.py` に以下を追加:

- **J-Quants API クライアントの統合**
  - `requests` で直接 `https://api.jquants.com/v2` を呼び出す（公式クライアント `jquants-api-client` も検討可）
  - `.env` から `JQUANTS_API_KEY` を読み込み
  - 無料プランのレート制限（5 req/min）を考慮し、API 呼び出しは 1 実行あたり 2〜3 回に抑える

- **ティッカー正規化関数**:
  - `TYO:6702` → J-Quants 用 `6702`、yfinance 用 `6702.T`
  - `6702` → `6702.T`（`--market jp` 指定時）
  - J-Quants 内部では 5桁コード `67020` で返ってくるが、4桁 `6702` でも受け付ける

- **`--market {us,jp}` オプション**（デフォルトは `us`）

- **日本株 technical データの取得ロジック**:
  - J-Quants `/v2/equities/bars/daily` から調整済み OHLCV を取得
  - 無料プランでは直近 12 週間が取得できないため、**足りない直近期間は yfinance `6702.T` で補完**
  - 取得した DataFrame で EMA/SMA/RSI/MACD/ボリンジャー/ATR を計算

- **日本株 fundamentals データの取得ロジック**:
  - J-Quants `/v2/fins/summary` から財務サマリーを取得
  - 売上高・営業利益・純利益・EPS の時系列から **売上成長率・利益成長率を自前計算**
  - yfinance から補完する項目: `trailingPE`, `forwardPE`, `beta`, `numberOfAnalystOpinions`, `targetMeanPrice`, `dividendYield`, 英語 `longBusinessSummary`

- **`fetch_macro_jp(as_of)` 関数**:
  - `^N225`（日経平均）
  - `JPY=X` または `USDJPY=X`（円相場）
  - `^TNX`（米10年債、グローバル影響）
  - `CL=F`（原油）
  - 必要に応じて日本国債 ETF や東証 REIT 指数など追加検討
  - ※J-Quants 無料プランでは指数 OHLC は取得できないため、マクロは yfinance で賄う

- **データソース対応表**:

| データ種別 | 優先数据源 | 補完/フォールバック | 理由 |
|---|---|---|---|
| 日本株 OHLC | J-Quants | yfinance（直近 12 週間） | J-Quants は調整済みで正確。無料プランは 12 週遅延 |
| 日本株財務 | J-Quants | yfinance（P/E, beta, アナリスト目標など） | J-Quants の財務サマリーが完全 |
| 日本株ニュース | yfinance | - | J-Quants にニュースエンドポイントはない |
| マクロ指標 | yfinance | - | J-Quants 無料プランでは指数データ不可 |
| 売上成長率/利益成長率 | J-Quants から自前計算 | - | yfinance では null になりやすい |

### Step 2: `skills/trading-analysis-jp/SKILL.md` の作成

既存 `SKILL.md` をコピーし、以下を日本市場向けに改変:

- ティッカー入力例を `TYO:6702` に変更
- 全エージェントのデータ取得コマンドに `--market jp` を追加
- Phase 1 マクロアナリストのプロンプトを日本市場コンテキストに変更
- Phase 4/5 の価格表記を `¥3,844` 形式に変更
- Phase 5 の `TICKER` フィールドに `TYO:6702` を使用
- ファンダメンタル分析で、日本企業特有の項目（3月決算、配当利回り、持合解消、自社株買い）に言及

### Step 3: `.claude/skills/trading-analysis-jp/SKILL.md` へのリンク作成

```bash
mkdir -p .claude/skills/trading-analysis-jp
ln -s ../../../skills/trading-analysis-jp/SKILL.md .claude/skills/trading-analysis-jp/SKILL.md
```

### Step 4: 富士通（6702.T）で動作検証

```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python \
  /home/masasikatano/project/trading-agents-plugin/scripts/fetch_market_data.py \
  --ticker 6702.T --type technical --market jp --date 2026-07-29
```

### Step 5: ドキュメント更新

- README に `/trading-analysis-jp TYO:6702` の実行例を追加
- J-Quants API key の取得手順と `.env` 設定を追記
- 日本市場対応の制限事項を明記:
  - ニュースは英語主体
  - J-Quants 無料プランでは株価データに 12 週間の遅延あり
  - 指数・マクロデータは J-Quants 無料プランでは未取得のため yfinance を使用
  - `shortRatio` などの空売り指標は J-Quants 有料プラン限定のため未取得

## 6. テスト計画

| テスト | 内容 | 成功基準 |
|-------|------|---------|
| データ取得 | `6702.T` の technical/news/fundamentals/macro(jp) を取得 | JSON が返り、主要フィールドが存在 |
| J-Quants 接続 | `.env` の `JQUANTS_API_KEY` で認証成功 | `/equities/master` が 200 を返す |
| ティッカー正規化 | `TYO:6702` → J-Quants `6702` / yfinance `6702.T` | スクリプトが正しく解釈 |
| 成長率計算 | J-Quants の `Sales`/`OP`/`NP` 時系列から成長率を導出 | `revenue_growth`, `earnings_growth` フィールドが存在 |
| 直近価格補完 | J-Quants 遅延期間中のデータが yfinance で補完されている | 最新 10 営業日の終値が欠損していない |
| マクロ日本版 | `^N225`, `JPY=X` のニュース取得 | macro_news_count > 0 |
| スキル実行 | `/trading-analysis-jp TYO:6702` | Phase 1〜5 が完了し、最終 SIGNAL が出力される |

## 7. リスクと対応

| リスク | 対応 |
|-------|------|
| J-Quants API key が未設定 | `--market jp` 実行時に `.env` から `JQUANTS_API_KEY` を読み込み、未設定の場合はエラーメッセージを表示 |
| J-Quants 無料プランのレート制限（5 req/min） | 1 回のスクリプト実行で J-Quants API 呼び出しを 2〜3 回に抑え、必要に応じてリトライ待機を実装 |
| J-Quants 無料プランの 12 週間遅延 | 直近 12 週間の株価は yfinance `6702.T` で補完。テクニカル指標は両データ源を結合して計算 |
| yfinance の日本株データが不完全 | J-Quants で取得可能な財務データはそちらを優先。yfinance 固有の null 項目（`shortRatio` など）はアナリストに「利用可能な指標のみで分析」と指示 |
| 日本語ニュースが取得できない | 英語ニュース主体で運用。必要に応じて日本語ニュース源の追加は将来拡張 |
| マクロ指標の不足（日銀政策金利など） | `^N225` + 円相場 + 米指標でカバー。追加が必要な場合は WebSearch 等を検討 |
| 既存スキルとの重複コード | データ取得関数の共通化を検討。今回はコピー改変で最小限の変更を優先 |

## 8. オープン問題

1. `jquants-api-client` 公式ライブラリを使うか、`requests` で直接呼び出すか？
   - `requests` 直接呼び出しであれば依存追加が不要
   - 公式クライアントを使うと DataFrame 返却・認証周りが楽だが `pyproject.toml` に依存追加が必要
2. J-Quants から取得した財務データをどの程度正規化して LLM プロンプトに渡すか？
   - 例: 成長率を計算して追加する、日本語の決算期（1Q/2Q/3Q/FY）をそのまま渡すなど
3. マクロ指標に日銀政策金利や日本10年国債を含めるか？
4. 出力は日本語にするか、英語のままにするか？
