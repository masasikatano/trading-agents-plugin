# TODO: usdjpy / fred_policy_rate データ品質改善

調査日: 2026-07-30  
関連: `scripts/fetch_jp_market_data.py`, `spec_jp.md`

## 背景

`fetch_jp_market_data.py --type macro` の出力で、以下が市場コンセンサスと乖離・陳腐化している。

| フィールド | スクリプト値（例） | 市場コンセンサス |
|---|---|---|
| `usdjpy` | ~159.5（yfinance live） | ~163 台 |
| `fred_policy_rate` | 0.3%（2023-12-01） | BOJ 政策金利 ~1.0% / コール実績 ~0.98% |

---

## 問題の本質

### 1. `usdjpy`（`JPY=X` via yfinance）

- `_yf_latest` が `regularMarketPrice`（live）を最優先している。
- live フィールドが ~159 と歪む一方、`history` の日次 Close は ~163.8 で他ソースと整合。
- `change_pct ≈ -2.3%` は誤った live ÷ 妥当な previousClose から出た見かけ上の急落。

### 2. `fred_policy_rate`（`IRSTCB01JPM156N`）

- OECD 経由の FRED 系列が **2023-12 で更新停止**（Next Release: Not Available）。
- FRED 上に 2026 年時点の BOJ **政策金利ターゲット**を追う代替系列は見つからない。
- 一次ソースは既に実装済みの **BOJ API**（`STRDCLUCON`、無担保コール O/N ≈ 0.98%）が妥当。

---

## 推奨 API / データ源（調査結果）

### USD/JPY

| 優先 | ソース | キー | 最新性 | 備考 |
|---|---|---|---|---|
| 1 | yfinance **daily Close**（`history`） | 不要 | 日次 | コード変更のみで改善 |
| 2 | FRED **`DEXJPUS`** | 既存 `FRED_API_KEY` | 日次・数営業日遅延 | Fed H.10。検証用に最適 |
| 3 | open.er-api.com `/v6/latest/USD` | 不要 | 約日次 | 実測 ~163.53 |
| 4 | Frankfurter `api.frankfurter.app` | 不要 | 日次（ECB） | 参照レート寄り ~162.94 |
| 5 | currency-api (jsDelivr / fawazahmed0) | 不要 | 日次 | 実測 ~163.47。CDN 依存 |
| 参考 | Twelve Data / Finnhub / Alpha Vantage | 要（無料枠） | リアルタイム寄り | 新規キー運用コスト |

### 日銀政策金利

| 優先 | ソース | キー | 備考 |
|---|---|---|---|
| 1（既存） | BOJ API `FM01` / `STRDCLUCON` | 不要 | 無担保コール実績。現状の `boj_policy_rate` |
| 弱い補完 | FRED **`IRSTCI01JPM156N`** | 既存 | Call Money/Interbank（2026-06: 0.841）。**policy と混同しない** |
| 非推奨 | FRED `IRSTCB01JPM156N`（現行） | 既存 | 2023-12 停止。分析に出すべきでない |
| 不可 | FRED に「最新政策金利ターゲット」系列 | — | 調査時点で代替なし |

---

## 実装タスク

### [ ] A. `usdjpy` の取得ロジック修正

- [ ] `_yf_latest` で FX（少なくとも `JPY=X`）は **history の最新 Close を優先**する  
  または live と history の乖離が閾値（例: 1%）超なら history を採用
- [ ] `source` を `live` / `daily_close` で正しく区別し、誤った `change_pct` を出さない
- [ ] （任意）フォールバック: FRED `DEXJPUS` または open.er-api.com
- [ ] マクロ verbose 出力と JSON の回帰確認（`--type macro --date 今日`）

### [ ] B. `fred_policy_rate` の扱い

- [ ] 現行 `IRSTCB01JPM156N` を **出力から削除**、または観測日が古い場合は omit / 警告
- [ ] 政策金利の一次表示は **`boj_policy_rate` のみ**と明記（SKILL.md / アナリストプロンプト）
- [ ] （任意）検証用に `IRSTCI01JPM156N` を載せる場合はフィールド名を `fred_call_rate` 等にし、policy と分離
- [ ] `spec_jp.md` のデータソース表を更新（FRED 補完の記述を実態に合わせる）

### [ ] C. ドキュメント

- [ ] `spec_jp.md`: 日銀政策金利のフォールバックから停止系列を外す
- [ ] `skills/trading-analysis-jp/SKILL.md`: マクロが参照する指標の優先順位を明記
- [ ] 本ファイルの完了タスクにチェックを入れる

### [ ] D. 検証

- [ ] 修正後の `usdjpy` が ~163 台（市場コンセンサス）と一致することを確認
- [ ] `boj_policy_rate` が ~1% 近傍で、古い `fred_policy_rate` が意思決定に混入しないことを確認
- [ ] `n225` / `us10y` / `crude_oil` に副作用がないことを確認

---

## 実装方針メモ（最短パス）

```text
usdjpy:
  優先: yfinance history Close (JPY=X)
  フォールバック: FRED DEXJPUS / open.er-api.com

policy rate:
  primary: boj_policy_rate（現状維持）
  fred_policy_rate: 削除 or 古い系列は非表示
  （任意）fred_call_rate = IRSTCI01JPM156N（ラベル厳守）
```

---

## 参考実測（2026-07-30 付近）

| ソース | USD/JPY |
|---|---|
| yfinance `regularMarketPrice` | ~159.45（問題値） |
| yfinance history Close（7/29） | ~163.86 |
| FRED DEXJPUS（7/24） | 163.71 |
| open.er-api.com | 163.53 |
| Frankfurter | 162.94 |
| currency-api | 163.47 |

| ソース | 政策関連金利 |
|---|---|
| BOJ `STRDCLUCON`（7/28） | 0.98% |
| 市場コンセンサス（ターゲット） | ~1.0% |
| FRED IRSTCB01JPM156N | 0.3%（2023-12）停止 |
| FRED IRSTCI01JPM156N | 0.841%（2026-06）コール |
