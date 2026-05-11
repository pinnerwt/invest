#!/usr/bin/env python3
"""Build TWSE + TPEx universe with P/E, P/B, yield, close price.

Sources (no auth):
  - TWSE BWIBBU_d:  上市個股本益比/殖利率/股價淨值比 (~1,073 檔)
  - TPEx PE ratio:  上櫃個股本益比 (~886 檔)
  - TPEx daily close: 上櫃日收盤 (for OTC close price)

Output: /home/pgi/youtube/verdicts/universe-pe-<YYYY-MM-DD>.csv
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

TWSE_PE = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
TPEX_PE = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
TPEX_CLOSE = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"

OUT_DIR = Path("/home/pgi/youtube/verdicts")


def fetch_json(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def to_float(x: str | None) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def main() -> int:
    print("Fetching TWSE BWIBBU_d ...", file=sys.stderr)
    twse = fetch_json(TWSE_PE)
    print(f"  {len(twse)} rows", file=sys.stderr)

    print("Fetching TPEx PE analysis ...", file=sys.stderr)
    tpex_pe = fetch_json(TPEX_PE)
    print(f"  {len(tpex_pe)} rows", file=sys.stderr)

    print("Fetching TPEx daily close ...", file=sys.stderr)
    tpex_close = fetch_json(TPEX_CLOSE)
    print(f"  {len(tpex_close)} rows", file=sys.stderr)
    close_map = {r["SecuritiesCompanyCode"]: r["Close"] for r in tpex_close}

    rows: list[dict] = []

    for r in twse:
        rows.append(
            {
                "ticker": r["Code"],
                "name": r["Name"],
                "exchange": "TWSE",
                "close": to_float(r.get("ClosePrice")),
                "pe": to_float(r.get("PEratio")),
                "pb": to_float(r.get("PBratio")),
                "yield_pct": to_float(r.get("DividendYield")),
                "as_of": r.get("Date", ""),
            }
        )

    for r in tpex_pe:
        code = r["SecuritiesCompanyCode"]
        rows.append(
            {
                "ticker": code,
                "name": r["CompanyName"],
                "exchange": "TPEx",
                "close": to_float(close_map.get(code)),
                "pe": to_float(r.get("PriceEarningRatio")),
                "pb": to_float(r.get("PriceBookRatio")),
                "yield_pct": to_float(r.get("YieldRatio")),
                "as_of": r.get("Date", ""),
            }
        )

    rows.sort(key=lambda x: (x["pe"] is None, x["pe"] if x["pe"] is not None else 0, x["ticker"]))

    today = date.today().isoformat()
    out_path = OUT_DIR / f"universe-pe-{today}.csv"
    fieldnames = ["ticker", "name", "exchange", "close", "pe", "pb", "yield_pct", "as_of"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with_pe = sum(1 for r in rows if r["pe"] is not None)
    print(
        f"\nWrote {out_path}\n"
        f"  total rows: {len(rows)} (TWSE {len(twse)} + TPEx {len(tpex_pe)})\n"
        f"  rows with P/E: {with_pe} ({with_pe / len(rows):.1%})\n"
        f"  rows missing P/E: {len(rows) - with_pe} (loss-making or NA)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
