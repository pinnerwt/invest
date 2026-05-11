#!/usr/bin/env python3
"""Aggregate per-ticker verdict dossiers into a single sortable HTML."""
import re
import glob
import html
import json
from pathlib import Path

VERDICTS_DIR = Path("/home/pgi/youtube/verdicts")
DATE = "2026-05-11"
OUT = VERDICTS_DIR / f"index-{DATE}.html"

VERDICT_RANK = {"買": 0, "觀望": 1, "不買": 2, "空": 3, "不適用": 4}
CONF_RANK = {"high": 0, "medium": 1, "low": 2, "—": 3}

def clean_verdict(v):
    v = v.strip()
    # Strip trailing parenthetical notes like "(Stage 2 fail)"
    v = re.sub(r"\s*\([^)]*\)\s*", " ", v).strip()
    # Strip trailing 衍生「X」-style markers, keep only final verdict
    if "→" in v:
        v = v.split("→")[-1].strip()
    # Strip quote markers
    v = v.strip("「」\"' ")
    # Strip leading "衍生" if present
    v = re.sub(r"^衍生", "", v).strip("「」\"' ")
    # If still has compound like "不適用 不買", take the more conservative
    for token in ["空", "不買", "不適用", "觀望", "買"]:
        if token in v:
            return token
    return v or "?"

def parse(path: Path):
    text = path.read_text(encoding="utf-8")
    ticker = path.stem.split("-")[0]
    rec = {"ticker": ticker, "path": path.name}

    m = re.search(r"^#\s+Verdict:\s+\S+\s+(.+?)\s+\(", text, re.M)
    rec["name"] = m.group(1).strip() if m else ""

    m = re.search(r"\*\*Verdict:\s*([^*]+?)\*\*[^\n]*?\(confidence:\s*([^)]+)\)", text)
    if not m:
        # Fallback: some dossiers use `# Verdict: X (confidence: Y)` H1 style
        m = re.search(r"^#\s+Verdict:\s*(.+?)\s*\(confidence:\s*([^)]+)\)", text, re.M)
    if not m:
        # Last resort: `# Verdict: X (...)` without confidence
        m2 = re.search(r"^#\s+Verdict:\s*(.+?)(?:\s*\(|\n|$)", text, re.M)
        if m2:
            rec["verdict"] = clean_verdict(m2.group(1))
            rec["confidence"] = "—"
        else:
            rec["verdict"] = "?"
            rec["confidence"] = "?"
    else:
        rec["verdict"] = clean_verdict(m.group(1))
        rec["confidence"] = m.group(2).strip().split("-")[0].strip()

    # Industry from Stage 0
    m = re.search(r"細分產業[:：]\s*([^\n]+)", text)
    rec["industry"] = m.group(1).strip() if m else ""

    # Current price
    m = re.search(r"當前股價[:：][^\n]*?NT\$\s*([\d,.]+)", text)
    if not m:
        m = re.search(r"股價[^\n]*?NT\$\s*([\d,.]+)", text)
    rec["price"] = m.group(1) if m else ""

    # Checklist score
    m = re.search(r"Score[:：]\s*\*?\*?(\d+)\s*/\s*6", text)
    rec["checklist"] = int(m.group(1)) if m else None

    # Top reasons (2 bullets after "Top reasons:")
    reasons = []
    rsec = re.search(r"\*\*Top reasons:\*\*\s*(.+?)(?:\n\n|\n---)", text, re.S)
    if rsec:
        for line in rsec.group(1).splitlines():
            line = line.strip()
            m = re.match(r"^\d+\.\s*(.+)", line)
            if m:
                reasons.append(m.group(1).strip())
    rec["reasons"] = reasons[:2]
    return rec

def watch_score(r):
    """Lower = more interesting/watchable."""
    v = VERDICT_RANK.get(r["verdict"], 9)
    c = CONF_RANK.get(r["confidence"], 9)
    cl = r["checklist"] if r["checklist"] is not None else -1
    # within verdict tier: higher checklist + higher confidence first
    return (v, -cl, c, r["ticker"])

def main():
    rows = []
    for p in sorted(VERDICTS_DIR.glob(f"*-{DATE}.md")):
        if "cache-sweep" in p.name:
            continue
        try:
            rows.append(parse(p))
        except Exception as e:
            print(f"skip {p.name}: {e}")
    rows.sort(key=watch_score)

    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    html_rows = []
    for r in rows:
        verdict = r["verdict"]
        klass = {
            "買": "buy", "觀望": "watch", "不買": "no",
            "空": "short", "不適用": "na"
        }.get(verdict, "na")
        reasons_html = "<br>".join(
            f"<span class='r'>{i+1}.</span> {html.escape(x)}"
            for i, x in enumerate(r["reasons"])
        )
        cl = r["checklist"]
        cl_display = f"{cl}/6" if cl is not None else "—"
        html_rows.append(
            f"<tr class='v-{klass}' data-verdict='{verdict}' data-conf='{r['confidence']}' "
            f"data-checklist='{cl if cl is not None else -1}'>"
            f"<td class='t'>{html.escape(r['ticker'])}</td>"
            f"<td>{html.escape(r['name'])}</td>"
            f"<td>{html.escape(r['industry'])}</td>"
            f"<td class='v'><span class='badge b-{klass}'>{verdict}</span></td>"
            f"<td class='c'>{html.escape(r['confidence'])}</td>"
            f"<td class='cl'>{cl_display}</td>"
            f"<td class='p'>{html.escape(r['price'])}</td>"
            f"<td class='reasons'>{reasons_html}</td>"
            f"<td class='link'><a href='{r['path']}' target='_blank'>md</a></td>"
            f"</tr>"
        )

    summary_cells = "".join(
        f"<span class='pill b-{ {'買':'buy','觀望':'watch','不買':'no','空':'short','不適用':'na'}.get(k,'na') }'>"
        f"{k}: {v}</span>"
        for k, v in sorted(counts.items(), key=lambda kv: VERDICT_RANK.get(kv[0], 9))
    )

    page = f"""<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<title>Verdict Cache Sweep — {DATE}</title>
<style>
  body {{ font: 14px/1.5 -apple-system, "Noto Sans TC", system-ui, sans-serif; margin: 24px; color: #222; }}
  h1 {{ margin: 0 0 4px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 16px; }}
  .summary {{ margin: 16px 0; }}
  .pill {{ display: inline-block; padding: 4px 10px; margin-right: 6px; border-radius: 12px; font-size: 13px; color: #fff; }}
  .controls {{ margin: 12px 0; }}
  .controls label {{ margin-right: 12px; font-size: 13px; }}
  input[type=text] {{ padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; width: 220px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }}
  th {{ background: #fafafa; cursor: pointer; user-select: none; position: sticky; top: 0; }}
  th:hover {{ background: #f0f0f0; }}
  td.t {{ font-weight: 600; font-family: SFMono-Regular, Consolas, monospace; }}
  td.reasons {{ font-size: 12px; color: #555; max-width: 560px; }}
  td.reasons .r {{ color: #999; font-size: 11px; margin-right: 2px; }}
  td.cl, td.p, td.c {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 10px; font-size: 12px; color: #fff; }}
  .b-buy {{ background: #1f8a3a; }}
  .b-watch {{ background: #c98a00; }}
  .b-no {{ background: #888; }}
  .b-short {{ background: #b32525; }}
  .b-na {{ background: #ccc; color: #555; }}
  tr.v-watch {{ background: #fffbe6; }}
  tr.v-buy {{ background: #e6f7eb; }}
  tr.hide {{ display: none; }}
</style>
</head>
<body>
<h1>Verdict Cache Sweep — {DATE}</h1>
<div class="meta">
  共 {len(rows)} ticker，依「觀望程度」排序（買 → 觀望 [checklist 高→低] → 不買 → 不適用）。
  完整方法見 <code>~/.claude/skills/verdict-cyclical-tw/SKILL.md</code>。
</div>
<div class="summary">{summary_cells}</div>
<div class="controls">
  <label>篩選 verdict：
    <select id="fv">
      <option value="">全部</option>
      <option value="買">買</option>
      <option value="觀望">觀望</option>
      <option value="不買">不買</option>
      <option value="空">空</option>
      <option value="不適用">不適用</option>
    </select>
  </label>
  <label>搜尋： <input type="text" id="fq" placeholder="ticker / 名稱 / 產業 / 理由"></label>
  <span style="color:#888;font-size:12px">(點欄位標題可重新排序)</span>
</div>
<table id="t">
  <thead>
    <tr>
      <th data-k="ticker">Ticker</th>
      <th data-k="name">Name</th>
      <th data-k="industry">產業</th>
      <th data-k="verdict">Verdict</th>
      <th data-k="conf">Conf.</th>
      <th data-k="checklist">Checklist</th>
      <th data-k="price">股價</th>
      <th data-k="reasons">Top reasons</th>
      <th>md</th>
    </tr>
  </thead>
  <tbody>
{chr(10).join(html_rows)}
  </tbody>
</table>
<script>
const tbody = document.querySelector('#t tbody');
const rows = Array.from(tbody.querySelectorAll('tr'));
const fv = document.querySelector('#fv');
const fq = document.querySelector('#fq');
function apply() {{
  const v = fv.value;
  const q = fq.value.trim().toLowerCase();
  for (const r of rows) {{
    let show = true;
    if (v && r.dataset.verdict !== v) show = false;
    if (show && q) {{
      show = r.textContent.toLowerCase().includes(q);
    }}
    r.classList.toggle('hide', !show);
  }}
}}
fv.addEventListener('change', apply);
fq.addEventListener('input', apply);

const verdictRank = {{"買":0,"觀望":1,"不買":2,"空":3,"不適用":4}};
const confRank = {{"high":0,"medium":1,"low":2}};
let sortKey = null, sortDir = 1;
document.querySelectorAll('th[data-k]').forEach(th => {{
  th.addEventListener('click', () => {{
    const k = th.dataset.k;
    if (sortKey === k) sortDir = -sortDir; else {{ sortKey = k; sortDir = 1; }}
    const sorted = [...rows].sort((a, b) => {{
      let va, vb;
      if (k === 'verdict') {{ va = verdictRank[a.dataset.verdict] ?? 9; vb = verdictRank[b.dataset.verdict] ?? 9; }}
      else if (k === 'conf') {{ va = confRank[a.dataset.conf] ?? 9; vb = confRank[b.dataset.conf] ?? 9; }}
      else if (k === 'checklist') {{ va = +a.dataset.checklist; vb = +b.dataset.checklist; }}
      else if (k === 'price') {{
        const pa = a.querySelector('td.p').textContent.replace(/,/g,'');
        const pb = b.querySelector('td.p').textContent.replace(/,/g,'');
        va = parseFloat(pa) || 0; vb = parseFloat(pb) || 0;
      }}
      else {{
        const idx = {{ticker:0,name:1,industry:2,reasons:7}}[k];
        va = a.cells[idx].textContent; vb = b.cells[idx].textContent;
        return sortDir * va.localeCompare(vb, 'zh-Hant');
      }}
      return sortDir * (va - vb);
    }});
    sorted.forEach(r => tbody.appendChild(r));
  }});
}});
</script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows)")
    print(f"counts: {counts}")

if __name__ == "__main__":
    main()
