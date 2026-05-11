# verdict-cyclical-tw Skill — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Claude skill at `~/.claude/skills/verdict-cyclical-tw/SKILL.md` that takes any TWSE/TPEx ticker, runs it through robertshih's cyclical-allin-playbook, and writes a deterministic 買/不買/空/觀望 verdict file to `/home/pgi/youtube/verdicts/`.

**Architecture:** Single SKILL.md file containing a 9-stage funnel (regime → payout gate → leading indicator → EPS scenarios → floor target → supply response → checklist → verdict → confidence). Data is fetched live from public Taiwan-finance sources (Goodinfo, 公開資訊觀測站, Yahoo, TDCC) via WebFetch/WebSearch. Output is one markdown file per run plus a short zh-TW chat summary. Methodology is cross-referenced from the existing `cyclical-allin-playbook` skill — never re-derived inline.

**Tech Stack:** Markdown (SKILL.md), WebFetch, WebSearch, Bash (for curl-based fallback fetches). No new code files, no new DB tables, no Python.

**Design doc:** `/home/pgi/youtube/docs/plans/2026-05-11-verdict-cyclical-tw-design.md`

**Note on TDD adaptation:** Skills don't have unit tests in the code sense. The verification loop here is *real-ticker hand-tests* — pick 3 tickers where the right answer is known, run the skill, check that the verdict & file structure match expectations. The "test" tasks (9, 10, 11) are where the skill's correctness is actually verified; treat them as failing-test runs and iterate Stage logic until passing.

**Note on commits:** `/home/pgi/youtube` is not a git repo — skip `git add` / `git commit` lines. The skill file itself lives at `~/.claude/skills/verdict-cyclical-tw/` and is under a separate git tree (if any); treat it as a single working file across tasks and only consider "done" when hand-tests pass.

---

## Task 1: Create skill directory and frontmatter

**Files:**
- Create: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Create directory**

Run: `mkdir -p ~/.claude/skills/verdict-cyclical-tw`
Expected: silent success.

**Step 2: Write SKILL.md with frontmatter + Overview + When to Use sections only**

Write this exact content:

```markdown
---
name: verdict-cyclical-tw
description: Use when the user asks for a buy/不買/空/觀望 verdict on a single Taiwan-listed ticker (TWSE/TPEx) — phrases like "判 2609", "/verdict 2603", "2609 該不該買", "用 robertshih 的方法看 XXXX". Applies the cyclical-allin-playbook deterministically and writes a dated dossier to /home/pgi/youtube/verdicts/. Taiwan-only; non-TW tickers and non-cyclical stocks (secular growers, defensives) get a fail-fast "不適用" response with reason.
---

# verdict-cyclical-tw

## Overview

Applies robertshih's cyclical-allin-playbook framework deterministically to a single Taiwan ticker and emits a verdict.

**REQUIRED BACKGROUND:** Use `cyclical-allin-playbook` for the underlying methodology. This skill does not re-derive the 6x P/E rule, leading-indicator ladder, or supply-response exit logic — it applies them. If methodology questions arise, defer to that skill.

**Bias:** When multiple verdicts qualify, prefer the more conservative (空 > 不買 > 觀望 > 買). The framework is structurally cautious about late-cycle, by robertshih's own 2021-下半年 self-described retreat.

## When to use

- User types `/verdict <ticker>` or asks "判 X / X 該不該買 / 用 robertshih 看 X"
- A Taiwan ticker has been extracted from upstream pipeline (e.g. `/home/pgi/youtube/` YouTube transcript) and needs evaluation
- The question is binary action (buy / don't / short / wait), not deep research dossier

**Do NOT use for:** non-TW listings (ADRs, HK, US), portfolio construction, multi-ticker batch (caller loops), real-time intraday calls (verdict horizon is weeks/quarters), or "explain the playbook" questions (use `cyclical-allin-playbook` directly).
```

**Step 3: Verify file written**

Run: `head -20 ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: frontmatter + Overview visible.

---

## Task 2: Add the 9-stage flow section (skeleton with stage headings only)

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md` (append)

**Step 1: Append the 9-stage flow skeleton**

Use Edit/append to add this section after the "When to use" section:

```markdown

## Evaluation flow

Run stages 0-9 in order. Stages 1 and 2 are fail-fast gates — exit early with "不適用" if they fail.

### Stage 0 — Resolve ticker
[to be filled in Task 3]

### Stage 1 — Regime classification
[to be filled in Task 4]

### Stage 2 — Payout gate
[to be filled in Task 5]

### Stage 3 — Leading indicator
[to be filled in Task 6]

### Stage 4 — EPS 三情境
[to be filled in Task 7]

### Stage 5 — Floor target
[to be filled in Task 7]

### Stage 6 — Supply response
[to be filled in Task 8]

### Stage 7 — Checklist
[to be filled in Task 8]

### Stage 8 — Verdict logic
[to be filled in Task 9]

### Stage 9 — Confidence
[to be filled in Task 9]
```

**Step 2: Verify**

Run: `grep -c "^### Stage" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: `10` (stages 0-9 inclusive).

---

## Task 3: Fill Stage 0 — ticker resolution

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md` (replace Stage 0 placeholder)

**Step 1: Replace `### Stage 0` block**

Replace the placeholder body with:

```markdown
### Stage 0 — Resolve ticker

**Input forms accepted:** 4-digit (`2609`), Yahoo style (`2609.TW`, `8932.TWO`), or company name (resolve via WebSearch).

**Steps:**
1. Strip `.TW` / `.TWO` suffix. Confirm 4-digit numeric.
2. If non-numeric, WebSearch for the company name + "台股代號" and extract the 4-digit code. Confirm with a Goodinfo URL lookup.
3. Confirm the ticker is on TWSE or TPEx via `https://tw.stock.yahoo.com/quote/<ticker>.TW` (if 404 try `.TWO`).
4. Pull: current price, company short name, sub-industry.

**Fail conditions (stop with explicit message):**
- Ticker not found on either exchange → "非台股或無此 ticker"
- Resolves to ADR / 海外掛牌 → "skill 僅支援台灣本土上市"
```

**Step 2: Verify**

Run: `grep -A 3 "Stage 0 — Resolve" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: see the new content (not the placeholder).

---

## Task 4: Fill Stage 1 — regime classification

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Replace `### Stage 1` block**

```markdown
### Stage 1 — Regime classification

Classify the ticker into one of four regimes. **FAIL-FAST: anything other than `cyclical` exits with "不適用" + reason.**

**Data to gather (WebSearch + Goodinfo):**
- 過去 5-10 年 annual EPS (look for amplitude)
- 主營產業 (二級行業)
- 是否依賴單一週期性 commodity / 運價 / 訂單能見度

**Classification rules:**

| Regime | Symptoms | Action |
|---|---|---|
| **cyclical** | EPS 高低點差距 ≥ 5x (在 10 年內), 業績與某個 commodity / 運價 / 產業 capex cycle 直接連動 | Proceed to Stage 2 |
| **secular_grower** | EPS 年年成長 (10 年內最多 1 個 down year), 護城河結構性 (e.g. 2330, 大立光黃金期) | STOP — "secular grower 不適用 robertshih 6x P/E 規則" |
| **defensive** | EPS 平穩 (波動 < 2x), 公用 / 食品 / 通路 / REITs | STOP — "防禦股不在循環 inflection framework 範圍" |
| **unclassifiable** | Pre-revenue 生技 / 新上市 < 3 年 / 服務業無明確 leading indicator | STOP — "無法套用 framework，請手動判斷" |

When borderline, default to the **more restrictive** classification (i.e. not cyclical). False negatives are recoverable (user can manually re-run); false positives waste analysis.
```

**Step 2: Verify**

Run: `grep "FAIL-FAST" ~/.claude/skills/verdict-cyclical-tw/SKILL.md | wc -l`
Expected: `1`.

---

## Task 5: Fill Stage 2 — payout gate

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Replace `### Stage 2` block**

```markdown
### Stage 2 — Payout gate

robertshih's 6x P/E floor rule is **conditional** on payout ratio ≥ 50% in 高 EPS 年. Without this, the floor doesn't hold and the framework can't price the stock.

**Data to gather:**
- 過去 10 年配息歷史 (Goodinfo `StockDividendPolicy.asp?STOCK_ID=<ticker>` or 公開資訊觀測站)
- 對應年度 EPS

**Gate logic:**
1. Identify 大賺年: EPS > 該股 10 年 EPS 中位數 × 1.5
2. 大賺年中，配息率 (現金 + 股票) ≥ 50%?
3. Pattern check: 至少 2 個大賺年都 ≥ 50%, AND 無大賺年 < 30%

**Pass:** Proceed to Stage 3.

**Fail:** STOP — "近 10 年大賺年配息率不足，6x P/E 規則不適用". Show the payout table in the output before exiting.

**Edge cases:**
- 新上市 < 3 年無大賺年 → fail (insufficient history)
- 公司歷年都未大賺 (EPS 一直平淡) → 應該已在 Stage 1 被分到 defensive 或 unclassifiable
- KY / F 股 → 仍適用 if payout history 符合
```

**Step 2: Verify**

Run: `grep -c "Stage 2" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: ≥ 2 (header + body references).

---

## Task 6: Fill Stage 3 — leading indicator + add mapping table

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Replace `### Stage 3` block**

```markdown
### Stage 3 — Leading indicator

Every cyclical needs a leading indicator that prints ≥1 quarter ahead of EPS. Without one, the framework can't tell you what direction you're in.

**Mapping table (seed list, extend over time):**

| 產業 / 細分 | Leading indicator | 來源 |
|---|---|---|
| 貨櫃航運 (2603 長榮, 2609 陽明, 2615 萬海) | SCFI (上海集運指數) | shippingexchange / 中時 / cnYES 週發布 |
| 散裝航運 (2606 裕民, 2615 萬海散裝) | BDI (波羅的海乾散貨指數) | TradingEconomics / 鉅亨 |
| DRAM (2408 南亞科, 3260 威剛) | DRAM spot / contract price | TrendForce / DRAMeXchange |
| NAND Flash (2451 創見, 3260 威剛) | NAND spot | TrendForce |
| 面板 (2409 友達, 3481 群創) | 大尺寸 panel ASP | DSCC / WitsView |
| 鋼鐵 (2002 中鋼) | 鐵礦石 + 廢鋼 + 中國熱軋鋼價 | TradingEconomics / Mysteel |
| 太陽能 (3576 聯合再生, 6443 元晶) | 多晶矽 spot / 模組 ASP | PVInsights / Bernreuter |
| 石化 (1301 台塑, 1303 南亞, 1326 台化) | 乙烯 / PVC / EVA spread | ICIS / 鉅亨 |
| 銅 (2009 第一銅, 2014 中鴻) | LME copper | LME |
| 鋁 (1503 士電 …) | LME aluminum | LME |
| 水泥 (1101 台泥, 1102 亞泥) | 中國水泥價 + 煤價 | 中國水泥網 |
| 紡織原料 (1409 新纖, 1414 東和) | PTA / MEG / PX spread | ICIS |
| 自行車 (9914 美利達, 9921 巨大) | 庫存月數 + 歐美零售 sell-through | TaiwanBike / 公司月營收 |
| ABF 載板 (3037 欣興, 6213 聯茂) | ABF 載板報價 + 缺貨指數 | DigiTimes / Prismark |
| 矽晶圓 (5347 世界先進, 6488 環球晶) | 半導體 wafer ASP + 訂單能見度月數 | DigiTimes |

**If 產業 not in table:** WebSearch `"<sub-industry> leading indicator" OR "<sub-industry> 領先指標"`. If no clear single indicator exists → STOP — "找不到明確 leading indicator, framework 不適用".

**Data to gather for chosen indicator:**
- 現值 (latest week / month)
- 6 個月前數值
- 12 個月前數值
- Trend: 向上 (現值 > 6mo 前 ≥ 10%) / 持平 (±10%) / 向下 (現值 < 6mo 前 ≥ 10%)

**Output for this stage:** indicator name, three time-point values, trend label, 來源 URLs.
```

**Step 2: Verify mapping table is intact**

Run: `grep -c "領先指標\|Leading indicator" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: ≥ 2.

---

## Task 7: Fill Stage 4 + Stage 5 — EPS scenarios and floor target

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Replace `### Stage 4` block**

```markdown
### Stage 4 — EPS 三情境

Build 3 forward-looking EPS scenarios anchored to Stage 3's leading indicator.

**Data to gather:**
- 近 4 季 EPS (Goodinfo `EPS_Q.asp?STOCK_ID=<ticker>`)
- 最新月營收 + YoY (Goodinfo `ShowMonthlyReport.asp?STOCK_ID=<ticker>`)
- Consensus sell-side EPS (Yahoo, 鉅亨, MoneyDJ) if available
- 該股歷史「leading indicator → EPS」對應關係 (rough elasticity)

**Scenario construction:**

| 情境 | Indicator 假設 | EPS 推估 |
|---|---|---|
| Bear | Indicator 自現值 -50% (回到循環下緣) | EPS_bear |
| Base | Indicator 持平於現值 | EPS_base |
| Bull | Indicator 自現值 +30% (續創高或 supply 持續緊) | EPS_bull |

如果近期月營收已能驗證 indicator → revenue 的傳導 (運價 vs 月營收 lag rule)，可以直接用月營收 trailing run-rate 推 base 情境。

**Output:** 三個 EPS 數字 + 各自的關鍵假設 (1 句話/情境)。
```

**Step 2: Replace `### Stage 5` block**

```markdown
### Stage 5 — Floor target

**Floor target = EPS_bear × 6** (來自 cyclical-allin-playbook 的 6x P/E 規則，僅在 Stage 2 payout gate 通過時適用)。

**Compute the gap:**
```
gap = (floor_target - current_price) / current_price
```

**Gap 分類:**
- `gap ≥ +50%`: 嚴重低估
- `gap ≥ +20%`: 顯著低估
- `gap ≥ -20%`: 合理區間
- `gap < -20%`: 高估

如果 indicator trend 向上且 gap 接近 0，計算「乾貨 base target = EPS_base × 6」作為延伸參考 (但不取代 floor)。
```

**Step 3: Verify**

Run: `grep "EPS_bear × 6" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: match found.

---

## Task 8: Fill Stage 6 + Stage 7 — supply response and checklist

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Replace `### Stage 6` block**

```markdown
### Stage 6 — Supply response

Check if the supply side is starting to respond (the cycle's exit signal).

**Data to gather (WebSearch + 公開資訊觀測站重大訊息):**
- 該產業近 6 個月 capex 公告金額 (vs 過去 5 年平均)
- 新建產能 / 新船訂單 / 新廠破土公告
- 新進入者 / 整合 / 併購消息
- 中國 / 韓國 / 越南 同業同期擴產

**Status:**

| Status | Symptoms |
|---|---|
| **無** | 業界 capex 仍低於歷史平均, 無新進入者 |
| **早期** | 龍頭開始談擴產但尚未動工, 個別公司公告但業界整體仍保守 |
| **大規模** | 多家業者同時公告 + 新訂單 / 新廠已動工, capex 顯著高於歷史平均 |

**Optional enrichment:** If `~/supply_demand/data.db` 已有該 ticker 的 dossier, 讀取 `payload_json -> supply_chain.sidestream[]` 看是否有 capacity_slack_pct 高的同業, 補強 supply response 判讀.

**Output:** status label + 3-5 條主要證據 + 來源 URLs.
```

**Step 2: Replace `### Stage 7` block**

```markdown
### Stage 7 — Checklist (6 項)

This is the cyclical-allin-playbook entry checklist. Score `x/6`.

- [ ] 1. 領先指標明確且現在向上 (Stage 3 確認)
- [ ] 2. EPS 三情境寫出 (Stage 4 完成)
- [ ] 3. 大賺年配息率 ≥ 50% (Stage 2 通過)
- [ ] 4. 供給未大規模回應 (Stage 6 = 無 或 早期)
- [ ] 5. Floor target gap ≥ +20% (Stage 5 顯著低估或更佳)
- [ ] 6. **使用者已有預先寫好的出場觸發條件**

第 6 項 skill 沒辦法替使用者打勾 — 在輸出中標明這項要求使用者自行確認。如果使用者沒有 pre-written exit, verdict 不應為「買」(改觀望).
```

**Step 3: Verify**

Run: `grep -c "^- \[ \]" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: `6`.

---

## Task 9: Fill Stage 8 + Stage 9 — verdict logic and confidence

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Replace `### Stage 8` block**

```markdown
### Stage 8 — Verdict logic

Run conditions in priority order. **First match wins** (priority bias toward conservative).

1. **空 (short)** — ALL of:
   - Stage 3 indicator trend = 向下
   - Stage 6 supply response = 大規模
   - Sell-side EPS estimates 仍在上修 (lagging 買盤未消化)

2. **不買** — ANY of:
   - Stage 5 gap ≤ 0 (高估)
   - Stage 6 supply response = 大規模
   - Stage 7 checklist ≤ 3/6

3. **觀望** — ANY of:
   - Stage 5 gap 在 -20% ~ +20% (合理區間)
   - Stage 3 indicator trend = 持平
   - Stage 7 checklist = 4/6
   - Stage 7 item 6 (預先寫好出場條件) 未確認 (block "買")

4. **買** — ALL of:
   - Stage 5 gap ≥ +20%
   - Stage 3 indicator trend = 向上
   - Stage 6 supply response = 無 或 早期
   - Stage 7 checklist ≥ 5/6
```

**Step 2: Replace `### Stage 9` block**

```markdown
### Stage 9 — Confidence

- **high**: checklist ≥ 5/6 AND 全部 9 stages 都有公開來源資料 AND indicator 有 ≥ 6 月歷史
- **medium**: checklist 4/6 OR 1-2 stages 有部分缺值
- **low**: checklist ≤ 3/6 OR ≥ 3 stages 有顯著缺值

低 confidence 時，verdict 仍要給，但在 chat 摘要中明講「資料不全，建議補充 XX 後再評估」。
```

**Step 3: Verify**

Run: `grep -c "^[0-9]\. \*\*" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: ≥ 4 (the four verdicts).

---

## Task 10: Add output file template + chat summary spec

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Append the output section**

After Stage 9, append:

```markdown

## Output

### File

Write to `/home/pgi/youtube/verdicts/<ticker>-<YYYY-MM-DD>.md`. Overwrite if same-day rerun.

Template:

\`\`\`markdown
# Verdict: <ticker> <name> (<YYYY-MM-DD>)

**Verdict: 買/不買/空/觀望** (confidence: high/medium/low)
**Top reasons:** 1. <one-liner>  2. <one-liner>

---

## Stage 1 — Regime: <class>
<reasoning + 2-3 lines of data>

## Stage 2 — Payout gate: ✅/❌
| 年 | EPS | 配息率 | 大賺年? |
| ... |

## Stage 3 — Leading indicator: <name>
- 現值: <X>
- 6 個月前: <Y>
- 12 個月前: <Z>
- Trend: <up/flat/down>
- 來源: <urls>

## Stage 4 — EPS 三情境
| 情境 | 假設 | EPS |
| Bear | ... | ... |
| Base | ... | ... |
| Bull | ... | ... |

## Stage 5 — Floor target: $<X>
Current $<Y>, gap <±Z>%
分類: <嚴重低估/顯著低估/合理/高估>

## Stage 6 — Supply response: <無/早期/大規模>
- 主要證據 (3-5 條)
- 來源: <urls>

## Stage 7 — Checklist
- [x/ ] 1. 領先指標明確且向上
- [x/ ] 2. EPS 三情境寫出
- [x/ ] 3. 大賺年配息率 ≥ 50%
- [x/ ] 4. 供給未大規模回應
- [x/ ] 5. Floor target gap ≥ +20%
- [ ] 6. (使用者自填) 預先寫好出場觸發條件
Score: x/6

## Stage 8 — Verdict reasoning
<3-5 sentences walking through which conditions matched in the priority list>

## Stage 9 — Confidence: <level>
資料完整度: ...
缺項: ...

## Sources
<all URLs used, grouped by stage>
\`\`\`

### Chat summary

After writing the file, return to chat (zh-TW, ≤150 words):

\`\`\`
判 <ticker> <name>: **<verdict>** (confidence: <level>)

理由:
1. <top reason>
2. <second reason>

完整 dossier: /home/pgi/youtube/verdicts/<ticker>-<YYYY-MM-DD>.md
\`\`\`
```

**Step 2: Verify**

Run: `grep "Chat summary\|完整 dossier" ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: both matches found.

---

## Task 11: Add edge cases, cross-skill notes, and red flags sections

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Step 1: Append**

```markdown

## Edge cases

| Case | Behavior |
|---|---|
| Ticker 不存在 | Stop at Stage 0, message "非台股或無此 ticker" |
| 新上市 < 3 年 | Stage 2 fail (history insufficient) |
| KY / F 股 | Proceed if payout gate passes; note "海外控股" in Stage 1 |
| 找不到 leading indicator | Stage 3 fail, "不適用 framework, 請手動判斷" |
| Goodinfo / TDCC fetch 失敗 | Confidence drops to low; list missing data |
| 數字衝突 | 取最新; 在 Stage source notes 標記分歧 |
| 同日多次 invoke | Overwrite file (same-day re-run is intentional) |

## Red flags (skill 自我紀律)

| 紅旗 | 對應 |
|---|---|
| 我想跳過 Stage 1 直接給 verdict | 不可。Stage 1 是 framework 適用門檻。 |
| 我想把 secular grower 也套 6x 規則 | 不可。媒體常這樣寫，但 robertshih 原文沒這個延伸。 |
| 我想把「空」condition 放寬 | 不可。priority 偏保守是 framework 內建設計。 |
| 我想跳過 Stage 6 supply response 因為資料難找 | 不可。沒有 supply response 判讀，verdict 必為 confidence low. |
| 我想推測 EPS 而不引 source | 不可。每個數字都要可追溯。 |

## Cross-skill

- **Required background:** `cyclical-allin-playbook` — methodology source.
- **Optional read:** if `~/supply_demand/data.db` has a dossier for this ticker, read `payload_json -> supply_chain.sidestream[]` and `substitution_edges[]` for Stage 6 enrichment.
- **Caller integration:** `/home/pgi/youtube/extract_strategies.py` emits per-video ticker lists; downstream batch invoker can call this skill per ticker.

## Out of scope

- Multi-ticker per invocation (caller loops)
- Position sizing / portfolio fit
- Backtest of past verdicts
- Updating `~/supply_demand/data.db` (that's `analyze` skill)
- Real-time intraday calls
- Applying other practitioners' frameworks
```

**Step 2: Verify**

Run: `wc -l ~/.claude/skills/verdict-cyclical-tw/SKILL.md`
Expected: ≥ 300 lines.

---

## Task 12: Hand-test 1 — clear-不適用 case (2330 TSMC)

**Goal:** Verify Stage 1 fail-fast works for a secular grower. This is the simplest test — the skill should stop early without doing the full analysis.

**Files:**
- Will create: `/home/pgi/youtube/verdicts/2330-2026-05-11.md` (if skill outputs file even on fail-fast — design says output file before stopping)

**Step 1: Invoke the skill on 2330**

In a fresh Claude Code session or sub-agent:
> 用 verdict-cyclical-tw skill 判 2330 該不該買

Expected behavior:
- Stage 0 resolves "台積電"
- Stage 1 classifies as `secular_grower` (10 年 EPS 連年成長, 護城河結構性)
- Skill stops, writes file with Stage 1 result + "不適用" verdict
- Chat summary: "2330: 不適用 (secular grower, 不在 robertshih cyclical inflection framework 範圍)"

**Step 2: Inspect the output file**

Run: `cat /home/pgi/youtube/verdicts/2330-2026-05-11.md`

Expected:
- Verdict line says 不適用 / N/A
- Has Stage 1 section explaining secular grower classification
- Does NOT have Stages 3-9 fully populated (early exit)

**Step 3: If skill fully analyzed instead of stopping**

→ Fix: tighten Stage 1 wording to make fail-fast explicit. Re-test.

---

## Task 13: Hand-test 2 — clear-適用 case (pick a current cyclical inflection)

**Goal:** Verify the full 9-stage flow works on a stock the framework should pass.

**Step 1: Pick test ticker**

Choose based on current (2026-05) Taiwan cyclical state. Candidates:
- 散裝航運 (2606 裕民) if BDI is in an upturn
- 鋼鐵 (2002 中鋼) if 廢鋼 / 鐵礦石 is up
- 面板 (2409 友達, 3481 群創) if panel ASP up

Quick WebSearch the relevant leading indicator before picking. Pick the one with clearest current trend signal.

**Step 2: Invoke**

> 用 verdict-cyclical-tw skill 判 <picked ticker>

**Step 3: Inspect output file** at `/home/pgi/youtube/verdicts/<ticker>-2026-05-11.md`

Verify:
- All 9 stages have content (no placeholders)
- Verdict matches the priority logic (not arbitrary)
- Each datum has a source URL
- Checklist score makes sense vs. verdict
- Chat summary is ≤150 words and zh-TW

**Step 4: Note any issues**

Common issues to watch for:
- Stage 4 EPS scenarios with no source → fix prompt
- Stage 6 skipped because data was hard → tighten skill rule
- Verdict logic conflict (e.g. matched 觀望 conditions but skill emitted 買) → debug priority bias

---

## Task 14: Hand-test 3 — payout-gate edge case (low-payout cyclical)

**Goal:** Verify Stage 2 fail-fast for a cyclical that fails the payout gate.

**Step 1: Pick test ticker**

A cyclical that historically pays < 50% in big-EPS years. Candidates:
- 某些 IC 設計 / 太陽能虧損抵稅後的非配息年
- 重資本擴張期的鋼鐵或半導體周邊

**Step 2: Invoke**

> 用 verdict-cyclical-tw skill 判 <picked ticker>

**Step 3: Inspect output**

Expected: file shows Stage 1 = cyclical, Stage 2 = fail with payout table, verdict = 不適用, no Stages 3-9.

**Step 4: If skill bulldozed past Stage 2**

→ Fix: ensure Stage 2 description has explicit "STOP" + "no fallback".

---

## Task 15: Tune thresholds based on test outcomes

**Files:**
- Modify: `~/.claude/skills/verdict-cyclical-tw/SKILL.md`

**Inputs:** observations from Tasks 12-14.

**Common tuning items:**
- 大賺年定義: 中位數 × 1.5 might be too loose for stable-EPS stocks; consider absolute floor (e.g. EPS ≥ 4 元)
- Gap thresholds: ±20% may be too wide; observe what gap the test cases produced and adjust
- Indicator trend threshold: ±10% over 6 months; may need finer granularity for slow-moving indicators (e.g. 水泥)
- Verdict 4 (買) checklist requirement: 5/6 may be too strict if Stage 7 item 6 is structurally unchecked

**Step 1: Edit Stage 2 / Stage 5 / Stage 8 thresholds as needed**

**Step 2: Re-run any failing test from Tasks 12-14**

Iterate until all 3 test cases produce sensible verdicts.

---

## Task 16: Add a README to /home/pgi/youtube/verdicts/

**Files:**
- Create: `/home/pgi/youtube/verdicts/README.md`

**Step 1: Write README**

```markdown
# verdicts/

Output folder for the `verdict-cyclical-tw` skill (`~/.claude/skills/verdict-cyclical-tw/`).

## File naming

`<ticker>-<YYYY-MM-DD>.md`, one per skill invocation. Same-day re-runs overwrite.

## What's in each file

A 9-stage dossier ending in a 買/不買/空/觀望/不適用 verdict, with sources.

See the methodology in `~/.claude/skills/cyclical-allin-playbook/SKILL.md`.

## Retention

Manual. No automatic cleanup. If verdict files become noisy, archive by quarter to `verdicts/archive/`.
```

**Step 2: Verify**

Run: `ls /home/pgi/youtube/verdicts/`
Expected: `README.md` present, plus the 3 test-case verdict files from Tasks 12-14.

---

## Task 17: Final structural review

**Files:**
- Read: `~/.claude/skills/verdict-cyclical-tw/SKILL.md` end-to-end

**Step 1: Re-read the full SKILL.md**

Check:
- Frontmatter `name` and `description` are accurate
- All 10 stage headings present (0-9)
- No leftover `[to be filled]` placeholders
- Cross-skill links use plain skill names (no `@` syntax)
- Word count ≤ 1500 (skills should be tight)

**Step 2: If any issue, edit and re-verify**

**Step 3: Confirm skill works end-to-end**

Re-invoke on one of the 3 test tickers in a fresh session. Output file should generate correctly.

---

## Done criteria

- [x] SKILL.md exists at `~/.claude/skills/verdict-cyclical-tw/SKILL.md`
- [x] All 9 stages have concrete logic, not placeholders
- [x] Leading-indicator mapping table has ≥ 15 industries
- [x] Verdict logic is deterministic and priority-ordered
- [x] 3 hand-tests produce sensible verdicts (1 secular-grower fail-fast, 1 cyclical pass-through, 1 payout-gate fail-fast)
- [x] `/home/pgi/youtube/verdicts/README.md` exists
- [x] Skill triggers correctly when user types `/verdict <ticker>` or natural-language equivalent
