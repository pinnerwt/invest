# Design: `verdict-cyclical-tw` skill

Date: 2026-05-11
Status: Approved (brainstorming complete, ready for implementation plan)

## Purpose

Apply robertshih's cyclical-allin-playbook methodology to a single Taiwan-listed ticker and emit a concrete verdict (買 / 不買 / 空 / 觀望). Intended to integrate downstream of the YouTube transcript → strategy extraction pipeline in `/home/pgi/youtube/`: when a YouTuber names a ticker, this skill judges whether the call is worth following on robertshih's framework.

Methodology source: `~/.claude/skills/cyclical-allin-playbook/SKILL.md` (do not re-derive here; cross-reference).

## Scope decisions

| Decision | Value |
|---|---|
| Universe | Taiwan only (TWSE + TPEx). Non-TW → reject |
| Output target | Decision-oriented (verdict required). Non-applicable stocks get "不適用" + reason, not forced verdict |
| Input | Single ticker (`2609` or `2609.TW`). Auto-detect leading indicator |
| Data sources | Public web only — Goodinfo, 公開資訊觀測站, Yahoo TW, WebSearch, TDCC (`norway.twsthr.info`) |
| Storage | `/home/pgi/youtube/verdicts/<ticker>-<YYYY-MM-DD>.md` (one file per run) |
| Approach | B — structured dossier with explicit verdict, ~800-1200 zh-TW words per file |

## Skill identity

- **Name:** `verdict-cyclical-tw`
- **Path:** `~/.claude/skills/verdict-cyclical-tw/SKILL.md`
- **Triggers:**
  - `/verdict <ticker>`
  - User asks "判 2609 / 2609 該不該買 / 用 robertshih 看 XXXX"
  - Programmatic invocation from `/home/pgi/youtube/` pipeline after a ticker is extracted from a transcript

## Evaluation flow (9 stages)

```
Stage 0  Resolve ticker — validate 4-digit TW listing
Stage 1  Regime classification (cyclical / secular grower / defensive / unclassifiable)
         FAIL-FAST: non-cyclical → "不適用" + reason → stop
Stage 2  Payout gate: 大賺年配息率 ≥ 50% 多年成立?
         FAIL-FAST: no → "不適用" → stop
Stage 3  Leading indicator identification + current value + 6-12 month trend
Stage 4  EPS 三情境 (bear / base / bull) based on indicator scenarios
Stage 5  Floor target = bear EPS × 6; compare to current price (gap %)
Stage 6  Supply response check (new-build orders, capex announcements, new entrants)
Stage 7  6-item checklist from cyclical-allin-playbook
Stage 8  Verdict logic
Stage 9  Confidence (high / medium / low)
```

### Verdict logic (deterministic, audit-able)

| Verdict | All-of conditions |
|---|---|
| **買** | gap ≥ +20% AND leading indicator 向上 AND 供給未回應 AND checklist ≥ 5/6 |
| **觀望** | gap ±20% OR leading indicator 持平 OR checklist 3-4/6 |
| **不買** | gap ≤ 0 OR 供給已開始回應 OR checklist ≤ 3/6 |
| **空** | leading indicator 已向下 AND 供給大量湧現 AND sell-side 仍在上修 |

If multiple verdicts qualify by their conditions, priority order: 空 > 不買 > 觀望 > 買 (most conservative wins). This is a deliberate bias — robertshih retired the strategy 2021下半年 rather than rotate into new positions; the framework is structurally cautious about late-cycle.

### Confidence logic

- **high**: checklist ≥ 5/6 AND all 9 stages have public-source data AND leading indicator has ≥ 6 months of values
- **medium**: checklist 4/6 OR 1-2 stages partially missing data
- **low**: checklist ≤ 3/6 OR ≥ 3 stages with significant data gaps

## Output file structure

`/home/pgi/youtube/verdicts/<ticker>-<YYYY-MM-DD>.md`:

```markdown
# Verdict: <ticker> <name> (<YYYY-MM-DD>)

**Verdict: 買/不買/空/觀望** (confidence: high/medium/low)
**Top reasons:** 1. ... 2. ...

---

## Stage 1 — Regime: <class>
[reasoning + data]

## Stage 2 — Payout gate: ✅/❌
[歷史配息率表 — 近 10 年]

## Stage 3 — Leading indicator: <name>
現值 X (vs 6 個月前 Y), trend <up/flat/down>
來源: [urls]

## Stage 4 — EPS 三情境
| 情境 | 假設 | EPS |
| ... |

## Stage 5 — Floor target: $X
Current $Y, gap ±Z%

## Stage 6 — Supply response: 無 / 早期 / 已大規模
[capex / 訂單追蹤 with sources]

## Stage 7 — Checklist (6/6 from cyclical-allin-playbook)
- [x/?] ...

## Stage 8 — Verdict reasoning
[3-5 sentences]

## Stage 9 — Confidence: <level>
[資料完整度註記 + 缺項]

## Sources
[all urls]
```

Short user-facing summary (≤150 zh-TW words, returned to chat after writing file):
- Verdict + confidence
- Top 2 reasons
- Pointer to full file

## Cross-skill references

- **REQUIRED BACKGROUND:** `cyclical-allin-playbook` — methodology source. Do NOT re-derive 6x P/E rule or leading-indicator ladder here; reference it.
- **Optional read:** if ticker has a dossier in `~/supply_demand/data.db`, read `supply_chain.substitution_edges` + `sidestream` to enrich Stage 6 supply-response analysis.
- **Pipeline integration:** `/home/pgi/youtube/extract_strategies.py` may emit a list of tickers per video; downstream wrapper can batch-invoke this skill per ticker.

## Edge cases & failure handling

| Case | Behavior |
|---|---|
| Ticker doesn't exist on TWSE/TPEx | Stop, return "非台股或無此 ticker" |
| Newly listed (< 3 years history) | Stage 2 fail (insufficient payout history) → "不適用" |
| KY / F 股 (foreign-incorporated TW listing) | Note in output; if payout gate passes still proceed |
| Industry has no obvious leading indicator (服務業、生技 pre-revenue) | "不適用" + suggest user manually指定 indicator via future flag |
| Goodinfo / TDCC fetch fails | Confidence drops to low; list which data points are missing |
| Conflicting sources on a number | Use most recent; note discrepancy in Stage source notes |

## Out of scope (explicit non-goals)

- **Multi-ticker** in one invocation (caller orchestrates loop)
- **Position sizing / portfolio fit** (skill is per-stock binary judgement, not portfolio construction)
- **Time-series backtest** of past verdicts (downstream job, not this skill's responsibility)
- **Updating the dossier DB at `~/supply_demand/data.db`** (that's `analyze` skill's job; this one only reads)
- **Real-time prices** beyond same-day; if Yahoo cache is hours old, that's fine — verdict horizon is weeks/quarters
- **Other-investor playbooks** (this skill applies ONLY robertshih's framework)

## Open items (resolve during implementation)

1. **Leading-indicator mapping table** — initial seed list (貨櫃, 散裝, DRAM, NAND, 鋼鐵, 太陽能, 面板, 石化, 銅, 鋁, 水泥, 紡織, 自行車). Implementation will draft this table inside the SKILL.md.
2. **Payout-gate threshold** — "大賺年" definition: EPS > 該股 10 年中位數 × 1.5? Or > 4 元 absolute? Default to relative (1.5× median) — re-evaluate after first 5 runs.
3. **TDCC mandatory vs optional** — design says optional (confidence modifier). May promote to mandatory after observing first runs.

## Implementation order

1. Create skill scaffold at `~/.claude/skills/verdict-cyclical-tw/SKILL.md`
2. Write SKILL.md per spec above — main reference only, no auxiliary files yet
3. Hand-test on 3 cases: a clear-buy (e.g. a current cyclical inflection if found), a clear-不適用 (e.g. 2330 secular grower), a marginal (one needing 觀望)
4. Adjust thresholds based on test outcomes
5. Add seed `verdicts/` README documenting file naming + retention
