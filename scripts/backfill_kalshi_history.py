"""One-off backfill of Kalshi rows into data/market_history.csv, mirroring backfill_history.py's Polymarket backfill.

Run once, not in the workflow. Daily "win" closes for every FAMILY candidate on Kalshi's KXFRENCHPRES winner
market, from its candlesticks endpoint (quiet days fall back to the bid/ask midpoint, same as build_data.py's
kalshi_candlestick_prices). Kalshi never supplies "qual" (see build_data.py's KALSHI_BASE comment), so the
"qual" column stays empty for these rows, same as it does for Polymarket's own backfilled rows.

Data used per the site owner's explicit direction despite Kalshi's Data Terms of Use restricting redistribution
and automated retrieval (see CLAUDE.md for the record of that decision).

Safe to re-run: a (date, candidate, venue) already in the CSV is never added again, and today is skipped
because build_data.py appends it.
"""
import csv, datetime, sys, time
from build_data import ROOT, FAMILY, KALSHI_WIN_SERIES, KALSHI_ALIASES, kalshi_markets, kalshi_candlestick_prices

HIST = ROOT / "data" / "market_history.csv"
FIELDS = ["date", "candidate", "venue", "win", "qual"]
BACKFILL_START = datetime.date(2025, 9, 1)   # wide enough to predate the market's opening; empty days are just skipped

def main():
    markets = kalshi_markets(KALSHI_WIN_SERIES)
    if not markets:
        raise SystemExit(f"no open markets returned for series {KALSHI_WIN_SERIES}")
    rows = []
    if HIST.exists():
        with HIST.open(newline="", encoding="utf-8") as fh: rows = list(csv.DictReader(fh))
    for r in rows: r.setdefault("venue", "polymarket")
    have = {(r["date"], r["candidate"], r["venue"]) for r in rows}
    today = datetime.datetime.now(datetime.timezone.utc).date()
    failed = []
    for m in markets:
        name = KALSHI_ALIASES.get(m["yes_sub_title"], m["yes_sub_title"])
        if name not in FAMILY: continue
        try:
            prices = kalshi_candlestick_prices(KALSHI_WIN_SERIES, m["ticker"], BACKFILL_START, today)
        except Exception as e:
            print(f"{name}: FAILED {e!r}"); failed.append(name); continue
        prices = {d: p for d, p in prices.items() if d < today.isoformat()}   # today is build_data.py's job
        new = [{"date": d, "candidate": name, "venue": "kalshi", "win": p, "qual": ""}
               for d, p in prices.items() if (d, name, "kalshi") not in have]
        rows += new
        print(f"{name}: {len(prices)} days ({min(prices, default='-')} to {max(prices, default='-')}), {len(new)} new")
        time.sleep(0.3)
    rows.sort(key=lambda r: r["date"])   # stable: existing rows keep their order within a day
    with HIST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} rows written to {HIST.name}")
    if failed: sys.exit("failed: " + ", ".join(failed))

if __name__ == "__main__":
    main()
