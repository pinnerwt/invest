#!/usr/bin/env bash
# Process every channel listed in channels.txt and build a combined index.
# Usage:  ./run_all.sh           # 5 newest videos per channel (default)
#         ./run_all.sh --n 10    # any flags are forwarded to extract_strategies.py
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

CHANNELS_FILE="${CHANNELS_FILE:-channels.txt}"
REPORT_DIR="${REPORT_DIR:-reports}"
mkdir -p "$REPORT_DIR"

# Collect channels (strip comments + blank lines).
mapfile -t CHANNELS < <(sed -E 's/#.*//' "$CHANNELS_FILE" | awk 'NF')

if [[ ${#CHANNELS[@]} -eq 0 ]]; then
    echo "No channels found in $CHANNELS_FILE" >&2
    exit 1
fi

INDEX="$REPORT_DIR/index.html"
{
    cat <<HTML
<!doctype html><html lang="zh-TW"><meta charset="utf-8">
<title>交易策略總覽</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.5 system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }
  ul { padding-left: 1.2rem; }
  li { margin: .4rem 0; }
  .meta { color: #888; font-size: 12px; }
  .err { color: #c66; font-style: italic; }
</style>
<h1>交易策略總覽</h1>
<div class="meta">產生於 $(date '+%Y-%m-%d %H:%M')</div>
<ul>
HTML
} > "$INDEX"

failed=0
for ch in "${CHANNELS[@]}"; do
    # Strip leading @ / URL prefix to derive a slug for the filename.
    slug="${ch#@}"
    slug="${slug##*/}"
    slug="${slug#@}"
    slug="${slug// /_}"
    out="$REPORT_DIR/${slug}.html"

    echo
    echo "=========================================="
    echo "  $ch  →  $out"
    echo "=========================================="

    if uv run extract_strategies.py "$ch" -o "$out" "$@"; then
        printf '  <li><a href="%s">%s</a></li>\n' "${slug}.html" "$ch" >> "$INDEX"
    else
        rc=$?
        echo "  ! $ch failed (exit $rc)" >&2
        printf '  <li class="err">%s — failed (exit %d)</li>\n' "$ch" "$rc" >> "$INDEX"
        failed=$((failed + 1))
    fi
done

echo "</ul></html>" >> "$INDEX"

echo
echo "Index: $(readlink -f "$INDEX")"
[[ $failed -eq 0 ]] || echo "($failed channel(s) failed)"
exit $failed
