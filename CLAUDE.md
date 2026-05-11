# Repo layout

Two independent workstreams in one repo:

## `youtube/` — YouTube transcript → trading-strategy pipeline

- `extract_strategies.py` — main script. Downloads YouTube transcripts (or transcribes via faster-whisper), asks DeepSeek to extract "WHEN ... THEN ..." rules, renders per-channel HTML.
- `run_all.sh` — iterates `channels.txt` and builds `reports/index.html`.
- `channels.txt` — channel handles to process.
- `cache/transcripts/`, `cache/strategies/` — JSON cache keyed by video id; prompt-fingerprinted so prompt edits invalidate.
- `reports/` — generated per-channel HTML + combined index.
- `rta.html`, `strategies.html` — standalone outputs.
- `.env` — `DEEPSEEK_API_KEY`. Loaded from CWD and next-to-script.

Run from anywhere — paths in `extract_strategies.py` and `run_all.sh` are script-relative.

## `verdicts/` — per-ticker buy/觀望/不買/空 dossiers

Output of the `verdict-cyclical-tw` skill (applies the `cyclical-allin-playbook`).

- `<ticker>-<YYYY-MM-DD>.md` — one dossier per ticker, overwritten on same-day rerun. **Path is referenced verbatim by the skill — do not move.**
- `build_html.py` — aggregates all dossiers into a sortable `index-<DATE>.html`. `VERDICTS_DIR` hardcoded to `/home/pgi/youtube/verdicts`.
- `cache-sweep-<DATE>.md` — batch-run summary across the full cache universe.
- `plans/` — design docs for the verdict skill itself.

## Cross-cutting

- Companion repo: `~/supply_demand/data.db` (SQLite) holds supply-chain dossiers; the verdict skill reads it for Stage 6 enrichment when present.
- Taiwan-listed cyclicals only for verdicts; non-TW or non-cyclical tickers fail fast with 不適用.
