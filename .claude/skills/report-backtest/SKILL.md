---
name: report-backtest
description: >
  Backtest a saved trading-analysis report after at least 7 calendar days.
  Checks what would have happened if the SIGNAL/ENTRY/STOP were followed.
  Writes markdown under backtests/. Use when the user runs /report-backtest,
  asks to verify past reports, or mentions report backtest / 事後検証.
---

`$ARGUMENTS` から対象を取る。未指定ならユーザーに聞く。

- ファイルパス（例: `reports/20260731_TYO6952_Grok.md`）
- 日付プレフィックス（例: `20260731`）→ `reports/{date}_*.md` を一括
- `--eval YYYY-MM-DD` があれば評価日。なければ今日

評価日はレポート日の **7 暦日後以降** のみ。満たさないファイルはスキップし理由を出す。trading-analysis パイプラインは再実行しない。価格は推測せずスクリプト JSON のみ使う。

リポジトリルート: `/home/masasikatano/project/trading-agents-plugin`

## 1. レポートを読む

ファイル名 `YYYYMMDD_{TICKER}_{Engine}.md` と Phase 5 ブロックから取る:

- `TICKER`, `DATE`, `SIGNAL` (BUY/SELL/HOLD), `RATING`
- `ENTRY`, `STOP`, `SIZE`
- テクニカル先頭の基準終値（レポート記載）
- BULL / BEAR 各 1 文

ENTRY がレンジなら中央値を数値化する。STOP が取れなければ STOP 判定は省略。

## 2. 価格を取る

JP（`TYO:` / `.T` / 数字）も米株も同じコマンド:

```bash
uv run --project /home/masasikatano/project/trading-agents-plugin python /home/masasikatano/project/trading-agents-plugin/scripts/fetch_backtest_prices.py --ticker $TICKER --from $REPORT_DATE --to $EVAL_DATE
```

JSON の `error` があればその銘柄は失敗として記録し、次へ。

## 3. 仮想執行

執行価格: `next_session.open`。無ければ `report_close`。

| SIGNAL | ポジション |
|--------|------------|
| BUY | ロング 1.0。ENTRY があり、翌始値がレンジ外なら「成行（始値）」と「押し目が期間内に付いた場合」を両方書く。押し目未到達は未約定。 |
| SELL | 新規ロング回避。フルロング機会損益 = `stock_pct_next_open_to_eval`。参考ショート = その符号反転。 |
| HOLD | 新規 0%。RATING が Underweight なら既存 0.5 を売却（回避した 50% ロングの機会）。Overweight ならロング 0.25。それ以外はフラット。 |

STOP: `window.bars` の `low` が STOP 以下の最初の日。決済は STOP 価格と当日終値の両方を書く。BUY または HOLD の仮想ロングに適用。SELL ショートは `high` が STOP 以上。

PnL% = (出口 − 執行) / 執行 × 100。ロング。ショートは符号反転。出口は STOP ヒットなら STOP、否则 `eval_close`。

## 4. 判定

- BUY: 仮想ロング PnL > 0 → `ALIGNED`、&lt; 0 → `MISALIGNED`。未約定のみ → `INCONCLUSIVE`
- SELL: 株の `stock_pct_next_open_to_eval` &lt; 0 → 回避が `ALIGNED`、&gt; 0 → `MISALIGNED`
- HOLD: フルロング PnL の絶対値が 3% 未満 → `INCONCLUSIVE`。Underweight でフルロングが負なら縮小が `ALIGNED`、正なら `MISALIGNED`。Overweight はその逆。フラット HOLD は対ベンチマーク `excess_pct_vs_benchmark` の符号で、|excess| &lt; 3 なら `INCONCLUSIVE`

価格が動いたこと自体を HOLD の失敗にしない。

## 5. 外れ時の予測スキル修正案

`MISALIGNED` のときだけ、分析スキルをこのターンでは編集せず、バックテスト Markdown に修正案を追記する。対象スキル:

- ティッカーが `TYO:` / `.T` / 数字 → `skills/trading-analysis-jp/SKILL.md`
- それ以外 → `skills/trading-analysis/SKILL.md`

レポートのどの Phase のシグナル・論点が価格と食い違ったかを特定し、**その Phase のプロンプトに入れる具体的な変更**を書く。一般論（「もっと慎重に」）は禁止。各項目は:

- 対象: スキル内の見出し（例: Phase 4 Trader の ENTRY/STOP、Phase 3 の Hold の使い方、Technical のギャップ/翌営業日）
- なぜ: 今回の価格事実（ギャップ、STOP 未到達、指数除外後の急騰など）
- 修正: スキル本文に足す／変える文の草案（コピペできる 1〜4 行）

ALIGNED / INCONCLUSIVE ではこの節を省略するか「なし」と書く。一括 summary には MISALIGNED 銘柄の修正案を箇条書きで集約する。

## 6. 保存

個別: `backtests/{YYYYMMDD}_{TICKER}_{evalYYYYMMDD}.md`

一括時は加えて `backtests/{report_date}_summary_{eval_date}.md`（ticker, signal, stock %, vs bench, verdict）。

個別テンプレ（数値は JSON 引用）:

```markdown
# Backtest — $TICKER

**Report:** reports/...  
**Report date / eval date:** ... / ...  
**Calendar days:** ...

## Decision at report time
SIGNAL / RATING / ENTRY / STOP / 基準終値

## Price path
report_close, next open, eval_close, window high/low, stock %, bench %, excess %

## Simulated fill
action, fill, stop hit?, exit, PnL %

## Verdict
ALIGNED | MISALIGNED | INCONCLUSIVE — 2–3 文

## Thesis vs tape
当たった点 / 外れた点（BULL/BEAR を価格事実と照合。再分析しない）

## Skill patch (MISALIGNED only)
対象スキルパス。項目ごとに 対象 Phase / なぜ / スキルへ足す文の草案。
```

ユーザーには保存パスと判定を返す。
