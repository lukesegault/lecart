"""One-off backfill of data/market_history.csv from the market's opening (13 Nov 2025).

Run once, not in the workflow. Daily "win" prices for every FAMILY candidate of the winner market,
from the Polymarket CLOB prices-history endpoint. The "qual" column stays empty for backfilled rows.
Safe to re-run: a (date, candidate) already in the CSV is never added again, and today is skipped
because build_data.py appends it.
"""
import csv, datetime, json, sys, time
from build_data import ROOT, FAMILY, WIN_SLUG, GAMMA, get

CLOB = "https://clob.polymarket.com/prices-history?market={token}&interval=max&fidelity=1440"
HIST = ROOT / "data" / "market_history.csv"
FIELDS = ["date", "candidate", "win", "qual"]

def daily_prices(token):
    """{UTC date: win %} from the daily series; points come in time order, so the last one of a day wins."""
    points = json.loads(get(CLOB.format(token=token)))["history"]
    today = datetime.datetime.now(datetime.timezone.utc).date()
    out = {}
    for p in points:
        d = datetime.datetime.fromtimestamp(p["t"], datetime.timezone.utc).date()
        if d < today: out[d.isoformat()] = round(100 * float(p["p"]), 1)
    return out

def main():
    events = json.loads(get(GAMMA.format(slug=WIN_SLUG)))
    if not events:
        raise SystemExit(f"no event returned for slug {WIN_SLUG}")
    rows = []
    if HIST.exists():
        with HIST.open(newline="", encoding="utf-8") as fh: rows = list(csv.DictReader(fh))
    have = {(r["date"], r["candidate"]) for r in rows}
    failed = []
    for m in events[0]["markets"]:
        name = m.get("groupItemTitle")
        if name not in FAMILY or json.loads(m.get("outcomes") or "[]")[:1] != ["Yes"]: continue
        try:
            prices = daily_prices(json.loads(m["clobTokenIds"])[0])
        except Exception as e:
            print(f"{name}: FAILED {e!r}"); failed.append(name); continue
        new = [{"date": d, "candidate": name, "win": p, "qual": ""} for d, p in prices.items() if (d, name) not in have]
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
