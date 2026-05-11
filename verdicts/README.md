# verdicts/

Output folder for the `verdict-cyclical-tw` skill (`~/.claude/skills/verdict-cyclical-tw/`).

## File naming

`<ticker>-<YYYY-MM-DD>.md`, one per skill invocation. Same-day re-runs overwrite.

## What's in each file

A 9-stage dossier ending in a 買/不買/空/觀望/不適用 verdict, with sources.

See the methodology in `~/.claude/skills/cyclical-allin-playbook/SKILL.md`.

## Retention

Manual. No automatic cleanup. If verdict files become noisy, archive by quarter to `verdicts/archive/`.
