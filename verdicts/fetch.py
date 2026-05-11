#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["yfinance>=0.2.40", "requests", "beautifulsoup4", "lxml"]
# ///
"""Price + EPS + dividend fetcher for Taiwan-listed tickers.

Serves the verdict-cyclical-tw skill: pulls the per-ticker inputs needed for
Stages 0, 1, 2, and parts of 4 (price, multi-year EPS, dividend history,
quarterly EPS). Stage 3 (industry leading indicator) and Stage 6 (supply
response news) are NOT covered — those are not per-ticker.

Primary source: yfinance (clean, fast). statementdog HTML scrape is used as
fallback when yfinance is missing the latest annual EPS (common: yfinance
lags the most recent filing by a quarter or two).

Usage:
    fetch.py 6789
    fetch.py 6789.TW --years 10 --quarters 8 --dividends
    fetch.py 6789 --all --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import date

import requests
import yfinance as yf
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


# Tickers that have been delisted/merged. Mirrors SKILL.md `delisted` row.
# Format: ticker -> (date, successor_ticker, note)
DELISTED: dict[str, tuple[str, str, str]] = {
    "2456": ("2022-01-05", "2327", "奇力新 併入 國巨"),
    "2448": ("2021-01-06", "3714", "晶電 + 隆達 換股下市，併入 富采"),
    "2311": ("2018-04-30", "3711", "日月光 併入 日月光投控"),
}


# Industry → free indicator that the CLI can fetch.
# Only includes indicators with public, scrape-friendly sources (no paywall, no JS rendering).
# Paywalled / JS-only indicators (SCFI, DRAM spot, panel ASP, MLCC ASP, ABF, 鐵礦石 specific
# index, etc.) stay in WebSearch territory — the skill prompts the user / model to fetch
# them manually for now.
INDUSTRY_TO_INDICATOR: dict[str, str] = {
    # yfinance "Marine Shipping" does NOT distinguish container (SCFI, paywalled) vs
    # dry bulk (BDI, free) — skip auto-map. User picks via --indicator-only bdi when
    # ticker is known dry-bulk (2606/2637/5608).
    "Aluminum": "lme-aluminum",
    "Copper": "lme-copper",
    "Other Industrial Metals & Mining": "lme-copper",
    # Steel could use iron-ore but tradingeconomics 鐵礦石 page is JS-heavy; leave manual.
}

INDICATOR_SOURCES: dict[str, dict] = {
    "bdi": {
        "name": "Baltic Dry Index (BDI)",
        "url": "https://tradingeconomics.com/commodity/baltic",
    },
    "lme-copper": {
        "name": "LME Copper",
        "url": "https://tradingeconomics.com/commodity/copper",
    },
    "lme-aluminum": {
        "name": "LME Aluminum",
        "url": "https://tradingeconomics.com/commodity/aluminum",
    },
}


@dataclass
class AnnualEPS:
    year: int
    diluted: float | None = None
    basic: float | None = None


@dataclass
class QuarterEPS:
    year: int
    quarter: int  # 1-4 (calendar quarter)
    diluted: float | None = None


@dataclass
class Dividend:
    """Taiwan convention: cash dividend paid in year X is for EPS year X-1."""
    paid_year: int
    eps_year: int
    cash: float


@dataclass
class MonthlyRevenue:
    year: int
    month: int
    revenue_kntd: float  # value in NT$ thousand
    yoy_pct: float | None = None


@dataclass
class IndicatorReading:
    key: str
    name: str
    current: float | None
    change_1m_pct: float | None
    change_12m_pct: float | None
    url: str
    asof: str


@dataclass
class TickerData:
    ticker: str
    suffix: str  # "TW" or "TWO"
    name: str | None = None
    industry: str | None = None
    price: float | None = None
    asof: str = ""
    annual_eps: list[AnnualEPS] = field(default_factory=list)
    quarterly_eps: list[QuarterEPS] = field(default_factory=list)
    dividends: list[Dividend] = field(default_factory=list)
    monthly_revenue: list[MonthlyRevenue] = field(default_factory=list)
    indicator: IndicatorReading | None = None
    warnings: list[str] = field(default_factory=list)


# ---------- ticker resolution ----------


def resolve(raw: str) -> tuple[str, str] | None:
    """Return (ticker, suffix) where suffix is 'TW' or 'TWO'. None if not found."""
    t = raw.strip().upper()
    t = re.sub(r"\.(TW|TWO)$", "", t)
    if not re.fullmatch(r"\d{4,6}", t):
        return None
    for suffix in ("TW", "TWO"):
        try:
            info = yf.Ticker(f"{t}.{suffix}").info
        except Exception:
            continue
        if info.get("shortName") or info.get("longName"):
            return t, suffix
    return None


def check_delisted(t: str) -> str | None:
    """Return a human-readable explanation if the ticker is known to be delisted/merged.
    Stage 0 fail-fast: caller should exit with this message before any data fetch."""
    if t in DELISTED:
        d, succ, note = DELISTED[t]
        return f"{t} 已於 {d} 下市 — {note}；改用後續 ticker {succ}"
    return None


# ---------- yfinance pulls ----------


def pull_yfinance(data: TickerData, years: int, quarters: int, want_div: bool) -> None:
    tk = yf.Ticker(f"{data.ticker}.{data.suffix}")
    info = tk.info
    data.name = info.get("shortName") or info.get("longName")
    data.industry = info.get("industry")

    try:
        data.price = float(tk.fast_info["lastPrice"])
    except Exception as e:
        data.warnings.append(f"price fetch failed: {e}")

    fin = tk.financials
    if fin is not None and not fin.empty:
        for col in fin.columns[:years]:
            y = col.year
            d = fin[col].get("Diluted EPS") if "Diluted EPS" in fin.index else None
            b = fin[col].get("Basic EPS") if "Basic EPS" in fin.index else None
            data.annual_eps.append(
                AnnualEPS(
                    year=y,
                    diluted=_nan_to_none(d),
                    basic=_nan_to_none(b),
                )
            )

    qf = tk.quarterly_financials
    if qf is not None and not qf.empty:
        for col in qf.columns[:quarters]:
            d = qf[col].get("Diluted EPS") if "Diluted EPS" in qf.index else None
            data.quarterly_eps.append(
                QuarterEPS(
                    year=col.year,
                    quarter=(col.month - 1) // 3 + 1,
                    diluted=_nan_to_none(d),
                )
            )

    if want_div:
        div = tk.dividends
        if div is not None and len(div):
            agg: dict[int, float] = {}
            for ts, val in div.items():
                agg[ts.year] = agg.get(ts.year, 0.0) + float(val)
            for py, total in sorted(agg.items(), reverse=True):
                data.dividends.append(
                    Dividend(paid_year=py, eps_year=py - 1, cash=round(total, 4))
                )


def fetch_monthly_revenue(data: TickerData, months: int = 1) -> None:
    """Pull the latest monthly revenue from TWSE / TPEx open data.

    Endpoints (no auth, no rate limit):
      - https://openapi.twse.com.tw/v1/opendata/t187ap05_L  (上市 SII)
      - https://openapi.twse.com.tw/v1/opendata/t187ap05_O  (上櫃 OTC)

    Each call returns one row per listed company for the *latest published* month.
    For multi-month history you'd need to scrape mops/Goodinfo with a session —
    those are blocked from naive requests. So this CLI returns just the latest
    month + YoY%, which is what Stage 4 run-rate confirmation needs.
    """
    endpoints = (
        ("t187ap05_L", "TWSE"),
        ("t187ap05_O", "TPEx"),
    )
    found = False
    for ep, label in endpoints:
        try:
            r = requests.get(
                f"https://openapi.twse.com.tw/v1/opendata/{ep}",
                headers={"Accept": "application/json"},
                timeout=15,
            )
            r.raise_for_status()
            rows = r.json()
        except Exception as e:
            data.warnings.append(f"monthly revenue {label} fetch failed: {e}")
            continue

        match = next((x for x in rows if x.get("公司代號") == data.ticker), None)
        if not match:
            continue

        ym = match.get("資料年月", "")
        if not re.fullmatch(r"\d{5}", ym):
            continue
        roc_year = int(ym[:3])
        month = int(ym[3:])
        year = roc_year + 1911
        try:
            rev = float(match["營業收入-當月營收"])
            yoy = float(match.get("營業收入-去年同月增減(%)", "nan"))
        except (KeyError, ValueError):
            continue
        if yoy != yoy:  # nan
            yoy = None
        data.monthly_revenue.append(
            MonthlyRevenue(year=year, month=month, revenue_kntd=rev, yoy_pct=yoy)
        )
        found = True
        if months > 1:
            data.warnings.append(
                f"monthly revenue: only latest month available via TWSE open API; "
                f"for {months}-month history use WebSearch on Goodinfo / statementdog"
            )
        break

    if not found:
        data.warnings.append(
            f"monthly revenue: ticker {data.ticker} not found in latest TWSE/TPEx open data "
            "(may be too new, suspended, or pending publication)"
        )


def fetch_indicator(key: str) -> IndicatorReading | None:
    """Scrape tradingeconomics commodity page for current value + simple changes.
    Returns None if the source layout has drifted."""
    cfg = INDICATOR_SOURCES.get(key)
    if not cfg:
        return None
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    # Source of truth on tradingeconomics is the meta description, which reads e.g.:
    #   "Aluminum rose to 3,551.40 USD/T on May 11, 2026, up 1.38% from the previous
    #    day. Over the past month, Aluminum's price has fallen 2.08%, but it is still
    #    43.73% higher than a year ago, ..."
    # The visible `id="p">` spans on the page belong to the sidebar list of other
    # commodities, NOT the page's headline price — so we parse the meta description.
    desc_meta = soup.find("meta", attrs={"name": "description"})
    desc = desc_meta["content"] if desc_meta and desc_meta.get("content") else ""

    current = None
    m = re.search(
        r"(?:rose|fell|jumped|dropped|increased|decreased|traded(?:\s+flat)?|climbed|slipped)\s+(?:to|at)\s+([\d,]+\.?\d*)",
        desc,
        re.IGNORECASE,
    )
    if m:
        try:
            current = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    ch_1m = ch_12m = None
    m = re.search(
        r"past month[^.]*?price has\s+(risen|fallen|gained|lost)\s+([\-\d.]+)\s*%",
        desc,
        re.IGNORECASE,
    )
    if m:
        try:
            ch_1m = float(m.group(2))
            if m.group(1).lower() in {"fallen", "lost"}:
                ch_1m = -abs(ch_1m)
        except ValueError:
            pass

    # 12m: matches both "is up X% compared to ... last year" and "is X% higher/lower than a year ago"
    m = re.search(
        r"is\s+(up|down)\s+([\-\d.]+)\s*%\s+compared to (?:the same time last year|last year)",
        desc,
        re.IGNORECASE,
    )
    if m:
        try:
            ch_12m = float(m.group(2))
            if m.group(1).lower() == "down":
                ch_12m = -abs(ch_12m)
        except ValueError:
            pass
    else:
        m = re.search(
            r"(?:is\s+(?:still\s+)?|is\s+)([\-\d.]+)\s*%\s+(higher|lower)\s+than\s+a year ago",
            desc,
            re.IGNORECASE,
        )
        if m:
            try:
                ch_12m = float(m.group(1))
                if m.group(2).lower() == "lower":
                    ch_12m = -abs(ch_12m)
            except ValueError:
                pass

    return IndicatorReading(
        key=key,
        name=cfg["name"],
        current=current,
        change_1m_pct=ch_1m,
        change_12m_pct=ch_12m,
        url=cfg["url"],
        asof=date.today().isoformat(),
    )


def _nan_to_none(v):
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None


# ---------- statementdog fallback for missing latest annual EPS ----------


def patch_latest_eps(data: TickerData) -> None:
    """If yfinance is missing the most recent year, try to scrape statementdog."""
    if not data.annual_eps:
        return
    latest_year = max(a.year for a in data.annual_eps)
    has_latest = any(
        a.year == latest_year and a.diluted is not None for a in data.annual_eps
    )
    current_year = date.today().year
    target = current_year - 1
    if has_latest and latest_year >= target:
        return

    try:
        r = requests.get(
            f"https://statementdog.com/analysis/{data.ticker}/eps",
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        data.warnings.append(f"statementdog fallback failed: {e}")
        return

    # statementdog page embeds a chart JSON with full-year EPS history.
    # The page also exposes per-quarter EPS in nearby tables; we prefer to
    # sum 4 quarters for the target fiscal year.
    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text(" ", strip=True)
    # Pattern: "2025年第4季EPS為1.21元，季增11.0%，近四季EPS為4.0元"
    # Better: pick up "{year}年第{q}季EPS為{x}元" entries and sum.
    qmatches = re.findall(
        r"(\d{4})年第([1-4])季\s*EPS\s*為\s*([\-\d.]+)\s*元", text
    )
    quarter_eps: dict[tuple[int, int], float] = {}
    for y, q, v in qmatches:
        try:
            quarter_eps[(int(y), int(q))] = float(v)
        except ValueError:
            continue
    full_year = None
    quarters_present = [q for (y, q) in quarter_eps if y == target]
    if set(quarters_present) >= {1, 2, 3, 4}:
        full_year = round(sum(quarter_eps[(target, q)] for q in (1, 2, 3, 4)), 2)
        source = "statementdog (sum of 4 quarters)"
    else:
        m = re.search(r"近四季\s*EPS\s*為\s*([\d.\-]+)\s*元", text)
        if m:
            full_year = float(m.group(1))
            source = "statementdog TTM (approximate)"

    if full_year is not None:
        data.warnings.append(
            f"EPS {target} missing from yfinance; using {full_year} from {source}"
        )
        already = next((a for a in data.annual_eps if a.year == target), None)
        if already:
            already.diluted = full_year
        else:
            data.annual_eps.append(AnnualEPS(year=target, diluted=full_year, basic=full_year))
            data.annual_eps.sort(key=lambda a: a.year, reverse=True)


# ---------- derived metrics ----------


def derived(data: TickerData) -> dict:
    out = {}
    eps_vals = [a.diluted for a in data.annual_eps if a.diluted is not None]
    if eps_vals:
        out["eps_max"] = max(eps_vals)
        out["eps_min"] = min(eps_vals)
        if out["eps_min"] and out["eps_min"] > 0:
            out["eps_amplitude"] = round(out["eps_max"] / out["eps_min"], 2)
        out["eps_avg_5y"] = round(sum(eps_vals[:5]) / min(5, len(eps_vals)), 2)
        if data.price:
            latest = next(
                (a.diluted for a in data.annual_eps if a.diluted is not None), None
            )
            if latest and latest > 0:
                out["pe_trailing"] = round(data.price / latest, 1)
            out["floor_6x"] = round(out["eps_min"] * 6, 2)
            out["floor_gap_pct"] = round(
                (out["floor_6x"] - data.price) / data.price * 100, 1
            )

    if data.dividends and eps_vals:
        # payout per matched eps_year
        eps_by_year = {a.year: a.diluted for a in data.annual_eps if a.diluted}
        rows = []
        for d in data.dividends:
            eps = eps_by_year.get(d.eps_year)
            payout = round(d.cash / eps * 100, 1) if eps and eps > 0 else None
            rows.append(
                {
                    "eps_year": d.eps_year,
                    "eps": eps,
                    "cash_div": d.cash,
                    "payout_pct": payout,
                }
            )
        out["payout_history"] = rows

    return out


# ---------- output formatting ----------


def render_text(data: TickerData, deriv: dict) -> str:
    lines = []
    lines.append(f"{data.ticker}.{data.suffix}  {data.name or '?'}  ({data.industry or '?'})")
    lines.append(f"  price: {data.price}  asof: {data.asof}")
    if data.annual_eps:
        lines.append("  annual EPS (diluted):")
        for a in data.annual_eps:
            lines.append(f"    {a.year}: {a.diluted}")
    if data.quarterly_eps:
        lines.append("  quarterly EPS (diluted):")
        for q in data.quarterly_eps:
            lines.append(f"    {q.year}Q{q.quarter}: {q.diluted}")
    if data.dividends:
        lines.append("  cash dividends (paid_year → for EPS year):")
        for d in data.dividends:
            lines.append(f"    {d.paid_year} → EPS {d.eps_year}: {d.cash:.3f}")
    if data.monthly_revenue:
        lines.append("  monthly revenue (latest first, kNTD + YoY%):")
        for mr in data.monthly_revenue[:12]:
            yoy = f"{mr.yoy_pct:+.1f}%" if mr.yoy_pct is not None else "?"
            lines.append(f"    {mr.year}/{mr.month:02d}: {mr.revenue_kntd:,.0f}  YoY {yoy}")
    if data.indicator:
        ind = data.indicator
        lines.append(
            f"  indicator [{ind.key}] {ind.name}: current={ind.current} "
            f"Δ1m={ind.change_1m_pct}% Δ12m={ind.change_12m_pct}%"
        )
        lines.append(f"    source: {ind.url}")
    if deriv:
        lines.append("  derived:")
        for k, v in deriv.items():
            if k == "payout_history":
                lines.append("    payout_history:")
                for r in v:
                    lines.append(
                        f"      EPS{r['eps_year']}={r['eps']}  cash={r['cash_div']:.3f}  payout={r['payout_pct']}%"
                    )
            else:
                lines.append(f"    {k}: {v}")
    if data.warnings:
        lines.append("  warnings:")
        for w in data.warnings:
            lines.append(f"    - {w}")
    return "\n".join(lines)


def render_json(data: TickerData, deriv: dict) -> str:
    payload = asdict(data)
    payload["derived"] = deriv
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------- entrypoint ----------


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "ticker", nargs="?",
        help="4-6 digit ticker, with or without .TW/.TWO suffix (omit when using --indicator-only)",
    )
    p.add_argument("-y", "--years", type=int, default=10, help="annual EPS years (default 10)")
    p.add_argument("-q", "--quarters", type=int, default=8, help="quarterly EPS count (default 8)")
    p.add_argument("-d", "--dividends", action="store_true", help="include dividend history")
    p.add_argument("-r", "--revenue", action="store_true", help="include monthly revenue (last 24 months)")
    p.add_argument(
        "-i", "--indicator", action="store_true",
        help="include leading indicator if industry has a free source mapping",
    )
    p.add_argument("-a", "--all", action="store_true", help="include everything")
    p.add_argument("-j", "--json", action="store_true", help="JSON output")
    p.add_argument(
        "--indicator-only", metavar="KEY",
        help="fetch only a named indicator (bdi, lme-copper, lme-aluminum) without ticker context",
    )
    args = p.parse_args()

    if args.indicator_only:
        ind = fetch_indicator(args.indicator_only)
        if not ind:
            print(f"error: indicator {args.indicator_only!r} not found or fetch failed", file=sys.stderr)
            sys.exit(2)
        if args.json:
            print(json.dumps(asdict(ind), ensure_ascii=False, indent=2))
        else:
            print(f"{ind.name} ({ind.key})")
            print(f"  current: {ind.current}  Δ1m: {ind.change_1m_pct}%  Δ12m: {ind.change_12m_pct}%")
            print(f"  source: {ind.url}  asof: {ind.asof}")
        return

    if not args.ticker:
        print("error: ticker required (or use --indicator-only KEY)", file=sys.stderr)
        sys.exit(2)

    if args.all:
        args.dividends = True
        args.revenue = True
        args.indicator = True
        args.years = max(args.years, 10)
        args.quarters = max(args.quarters, 12)

    # Stage 0 fail-fast: known delisted tickers
    raw_t = re.sub(r"\.(TW|TWO)$", "", args.ticker.strip().upper())
    delisted_msg = check_delisted(raw_t)
    if delisted_msg:
        print(f"error: {delisted_msg}", file=sys.stderr)
        sys.exit(3)

    resolved = resolve(args.ticker)
    if not resolved:
        print(f"error: ticker {args.ticker!r} not found on TWSE or TPEx", file=sys.stderr)
        sys.exit(2)

    t, suffix = resolved
    data = TickerData(ticker=t, suffix=suffix, asof=date.today().isoformat())
    pull_yfinance(data, years=args.years, quarters=args.quarters, want_div=args.dividends)
    patch_latest_eps(data)
    if args.revenue:
        fetch_monthly_revenue(data, months=24)
    if args.indicator and data.industry:
        key = INDUSTRY_TO_INDICATOR.get(data.industry)
        if key:
            data.indicator = fetch_indicator(key)
            if not data.indicator:
                data.warnings.append(f"indicator {key} fetch failed (layout drift?)")
        else:
            data.warnings.append(
                f"no free indicator mapping for industry {data.industry!r}; "
                "use WebSearch for SCFI / DRAM / panel ASP / 鐵礦石 / MLCC etc."
            )
    deriv = derived(data)

    print(render_json(data, deriv) if args.json else render_text(data, deriv))


if __name__ == "__main__":
    main()
