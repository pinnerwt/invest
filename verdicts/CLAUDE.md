# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

Output sink for the `verdict-cyclical-tw` skill (`~/.claude/skills/verdict-cyclical-tw/SKILL.md`). It is **not** an application — it stores per-ticker dossier markdown files plus a small aggregator that produces a sortable HTML index.

The authoritative methodology and the cyclical-ticker universe live in the skill, not here. If a classification or framework question arises, defer to `~/.claude/skills/verdict-cyclical-tw/SKILL.md`; treat this directory as the artifact store.

## File layout

- `<ticker>-<YYYY-MM-DD>.md` — one dossier per skill run. Same-day re-runs overwrite.
- `cache-sweep-<YYYY-MM-DD>.md` — batch-sweep summary written by hand when running the skill over the whole cyclical universe.
- `build_html.py` — aggregator (see below).
- `index-<YYYY-MM-DD>.html` — generated; do not edit by hand.
- `README.md` — short pointer for humans.

## Common commands

```bash
# Rebuild the HTML aggregation for DATE (currently hardcoded in build_html.py)
python3 build_html.py
```

To aggregate a different date, edit the `DATE` constant at the top of `build_html.py`. There are no tests, lint, or build steps.

## Dossier format the aggregator depends on

`build_html.py` parses each `<ticker>-<DATE>.md` with regexes. Keep these contracts when authoring or editing dossiers, or the row will land in the HTML with blanks / wrong sort tier:

- H1 line: `# Verdict: <ticker> <name> (<DATE>)`
- Verdict line: `**Verdict: <X>** (... optional parenthetical ...) (confidence: <level>)`
  - `<X>` may be compound (e.g. `不適用 → 衍生「不買」`); `clean_verdict()` strips arrows / quote markers / parenthetical notes and falls back to the most-conservative token.
  - Fallback formats accepted: H1-only `# Verdict: X (confidence: Y)` or `# Verdict: X (...)` without confidence.
- `**Top reasons:**` block with numbered bullets (first 2 are surfaced in HTML).
- Stage 0 fields the parser scrapes: `細分產業:`, `當前股價: ... NT$ <price>`.
- Stage 7 score: `Score: <n>/6`.

Sort order in HTML (lower = more interesting):
`(verdict tier, -checklist, confidence, ticker)` with verdict tiers `買 < 觀望 < 不買 < 空 < 不適用`.

## When adding or editing dossiers

- Don't edit `index-*.html` directly — it is regenerated from the markdown files.
- If a dossier uses a non-standard verdict header, prefer fixing the dossier to match the formats above rather than loosening regex in `build_html.py` (the parser already tolerates the documented variants).
- New cyclical / non-cyclical classifications belong in the skill cache (`~/.claude/skills/verdict-cyclical-tw/SKILL.md`), not in dossiers here. Per-ticker dossiers are evidence, not the source of truth for regime classification.
