"""Daily data refresh for L'Écart.

1. Downloads the open poll compilation (MieuxVoter/presidentielle2027, MIT licence).
2. Fetches current Polymarket prices for the French 2027 markets (public API, no key).
3. Writes data.json for the page and appends today's prices to data/market_history.csv.

NOTE: the Polymarket part was written without live access to the API and must be
verified against https://docs.polymarket.com before relying on it.
"""
import csv, io, json, datetime, pathlib, urllib.request
from collections import defaultdict
from statistics import mean

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLLS_URL = "https://raw.githubusercontent.com/MieuxVoter/presidentielle2027/main/presidentielle2027.csv"
GAMMA = "https://gamma-api.polymarket.com/events?slug={slug}"
WIN_SLUG = "next-french-presidential-election"
QUAL_SLUG = "next-french-presidential-election-who-will-advance-to-the-2nd-round"
FIRST_ROUND_WINDOW_DAYS = 60   # polls used for the simulation
TREND_START = "2025-09-01"

FAMILY = {  # political family per candidate, used for colours on the page
 "Marine Le Pen":"far-right","Jordan Bardella":"far-right","Éric Zemmour":"far-right","Nicolas Dupont-Aignan":"far-right","Sarah Knafo":"far-right",
 "Bruno Retailleau":"right","David Lisnard":"right","Dominique de Villepin":"right","Laurent Wauquiez":"right",
 "Édouard Philippe":"centre","Gabriel Attal":"centre","Sébastien Lecornu":"centre",
 "Raphaël Glucksmann":"left","François Hollande":"left","Olivier Faure":"left",
 "Marine Tondelier":"green","Jean-Luc Mélenchon":"far-left","Fabien Roussel":"far-left",
}
TREND_CANDIDATES = ["Marine Le Pen","Jordan Bardella","Édouard Philippe","Jean-Luc Mélenchon","Raphaël Glucksmann","Gabriel Attal","Bruno Retailleau"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lecart-data-bot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")

def load_polls():
    rows = list(csv.DictReader(io.StringIO(get(POLLS_URL))))
    today = datetime.date.today()
    cutoff = (today - datetime.timedelta(days=FIRST_ROUND_WINDOW_DAYS)).isoformat()
    first, second = defaultdict(list), defaultdict(list)
    for r in rows:
        (first if r["tour"] == "1er Tour" else second)[r["poll_id"]].append(r)
    polls = []
    for pid, rs in first.items():
        f = rs[0]
        if f["fin_enquete"] < cutoff: continue
        polls.append({"id": pid, "inst": f["nom_institut"], "for": f["commanditaire"], "start": f["debut_enquete"],
                      "end": f["fin_enquete"], "n": int(float(f["echantillon"] or 0)),
                      "v": {r["candidat"]: float(r["intentions"]) for r in rs}})
    polls.sort(key=lambda p: p["end"])
    pairs = defaultdict(list)
    for pid, rs in second.items():
        if len(rs) != 2 or rs[0]["fin_enquete"] < cutoff: continue
        a, b = sorted(rs, key=lambda r: r["candidat"])
        va, vb = float(a["intentions"]), float(b["intentions"])
        pairs[a["candidat"] + "|" + b["candidat"]].append(100 * va / (va + vb))
    pairs = {k: [round(mean(v), 1), len(v)] for k, v in pairs.items()}
    monthly = defaultdict(lambda: defaultdict(list))
    for pid, rs in first.items():
        for r in rs:
            if r["fin_enquete"] >= TREND_START and r["candidat"] in TREND_CANDIDATES:
                monthly[r["fin_enquete"][:7]][r["candidat"]].append(float(r["intentions"]))
    months = sorted(monthly)
    trend = {"months": months, "series": {c: [round(mean(monthly[m][c]), 1) if monthly[m][c] else None for m in months] for c in TREND_CANDIDATES}}
    return polls, pairs, trend

def market_prices(slug):
    events = json.loads(get(GAMMA.format(slug=slug)))
    out = {}
    for m in events[0]["markets"]:
        name = m.get("groupItemTitle") or m.get("question")
        prices = json.loads(m.get("outcomePrices") or "[]")
        if name and prices:
            out[name] = round(100 * float(prices[0]), 1)   # price of "Yes"
    return out

def main():
    polls, pairs, trend = load_polls()
    data_path = ROOT / "data.json"
    previous = json.loads(data_path.read_text()) if data_path.exists() else {}
    try:
        win, qual = market_prices(WIN_SLUG), market_prices(QUAL_SLUG)
        names = [n for n in win if n in FAMILY]
        candidates = [{"c": n, "f": FAMILY[n], "win": win.get(n, 0), "qual": qual.get(n, 0)} for n in names]
        markets = {"snapshot": datetime.date.today().isoformat(), "source": "Polymarket", "candidates": candidates}
        hist = ROOT / "data" / "market_history.csv"
        new = not hist.exists()
        with hist.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new: w.writerow(["date", "candidate", "win", "qual"])
            for c in candidates: w.writerow([markets["snapshot"], c["c"], c["win"], c["qual"]])
    except Exception as e:   # keep yesterday's market data rather than breaking the page
        print("Market fetch failed, keeping previous snapshot:", e)
        markets = previous.get("markets")
    data = {"updated": datetime.date.today().isoformat(), "polls": polls, "pairs": pairs, "trend": trend, "markets": markets}
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"{len(polls)} polls, {len(markets['candidates'])} market candidates")

if __name__ == "__main__":
    main()
