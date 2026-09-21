"""Daily data refresh for L'Écart.

1. Downloads the open poll compilation (MieuxVoter/presidentielle2027, MIT licence).
2. Fetches current Polymarket prices for the French 2027 markets (public API, no key).
3. Writes data.json for the page and appends today's prices to data/market_history.csv.
4. Writes the static French text, meta/Open Graph tags and og-image.png so crawlers and link
   previews see content without running JS (index.html, between the STATIC and META markers).

NOTE: the Polymarket part was written without live access to the API and must be
verified against https://docs.polymarket.com before relying on it.
"""
import csv, io, json, datetime, math, pathlib, re, urllib.request
from collections import defaultdict
from statistics import mean

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLLS_URL = "https://raw.githubusercontent.com/MieuxVoter/presidentielle2027/main/presidentielle2027.csv"
GAMMA = "https://gamma-api.polymarket.com/events?slug={slug}"
WIN_SLUG = "next-french-presidential-election"
QUAL_SLUG = "next-french-presidential-election-who-will-advance-to-the-2nd-round"
FIRST_ROUND_WINDOW_DAYS = 60   # polls used for the simulation
TREND_START = "2025-09-01"
SITE_URL = "https://lukesegault.github.io/lecart/"
INDEX = ROOT / "index.html"
OG_IMAGE = ROOT / "og-image.png"
SIM_RUNS = 20000
# polling-error levels of the page's "Poll uncertainty" control: sd of a first-round score = base + k * score, sd of the runoff share = run
LEVELS = {"low": {"base": 1, "k": 0.12, "run": 3.5}, "mid": {"base": 1.5, "k": 0.2, "run": 6}, "high": {"base": 2, "k": 0.3, "run": 9}}
SIM_MID = LEVELS["mid"]
TABLE_CANDIDATES = ["Marine Le Pen", "Édouard Philippe", "Jean-Luc Mélenchon"]   # columns of the poll table on the page
NB = "\u00a0"
FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

FAMILY = {  # political family per candidate, used for colours on the page
 "Marine Le Pen":"far-right","Jordan Bardella":"far-right","Éric Zemmour":"far-right","Nicolas Dupont-Aignan":"far-right","Sarah Knafo":"far-right",
 "Bruno Retailleau":"right","David Lisnard":"right","Dominique de Villepin":"right","Laurent Wauquiez":"right",
 "Édouard Philippe":"centre","Gabriel Attal":"centre","Sébastien Lecornu":"centre",
 "Raphaël Glucksmann":"left","François Hollande":"left","Olivier Faure":"left",
 "Marine Tondelier":"green","Jean-Luc Mélenchon":"far-left","Fabien Roussel":"far-left",
}
TREND_CANDIDATES = ["Marine Le Pen","Jordan Bardella","Édouard Philippe","Jean-Luc Mélenchon","Raphaël Glucksmann","Gabriel Attal","Bruno Retailleau"]
WEEKLY_CANDIDATES = ["Marine Le Pen","Édouard Philippe","Jean-Luc Mélenchon"]   # polls vs markets chart
WEEKLY_WINDOW_DAYS = 30        # polls feeding each weekly poll-implied win probability
HISTORY = ROOT / "data" / "market_history.csv"
POLLS_AVERAGE = ROOT / "data" / "polls_average.csv"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lecart-data-bot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")

def pair_records(second):
    """(end, "A|B", share of A in the A-vs-B runoff, %) for every complete two-candidate runoff poll."""
    out = []
    for pid, rs in second.items():
        if len(rs) != 2: continue
        a, b = sorted(rs, key=lambda r: r["candidat"])
        va, vb = float(a["intentions"]), float(b["intentions"])
        out.append({"id": pid, "end": a["fin_enquete"], "key": a["candidat"] + "|" + b["candidat"], "share": 100 * va / (va + vb)})
    return out

def pairs_of(records):
    by = defaultdict(list)
    for r in records: by[r["key"]].append(r["share"])
    return {k: [round(mean(v), 1), len(v)] for k, v in by.items()}

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
    runoffs = pair_records(second)
    pairs = pairs_of([r for r in runoffs if r["end"] >= cutoff])
    monthly = defaultdict(lambda: defaultdict(list))
    for pid, rs in first.items():
        for r in rs:
            if r["fin_enquete"] >= TREND_START and r["candidat"] in TREND_CANDIDATES:
                monthly[r["fin_enquete"][:7]][r["candidat"]].append(float(r["intentions"]))
    months = sorted(monthly)
    trend = {"months": months, "series": {c: [round(mean(monthly[m][c]), 1) if monthly[m][c] else None for m in months] for c in TREND_CANDIDATES}}
    # every poll since TREND_START, with all its candidates: the input of the weekly poll-implied win probability
    history = {"first": sorted(({"id": pid, "end": rs[0]["fin_enquete"], "v": {r["candidat"]: float(r["intentions"]) for r in rs}}
                                for pid, rs in first.items() if rs[0]["fin_enquete"] >= TREND_START), key=lambda p: p["end"]),
               "runoff": [r for r in runoffs if r["end"] >= TREND_START]}
    return polls, pairs, trend, history

def monday(iso):
    d = datetime.date.fromisoformat(iso)
    return d - datetime.timedelta(days=d.weekday())

def weekly_series(history, today=None):
    """Weekly (Monday-start) series per WEEKLY_CANDIDATES, from the first poll (or market day, if earlier) to the last market day.
    market: mean of the daily win prices of the week (market_history.csv).
    poll: poll-implied win probability, the same Monte Carlo as the rest of the page (simulate(), medium uncertainty, seed 2027) run on the
    first-round polls that ended in the WEEKLY_WINDOW_DAYS days up to the end of the week, with the runoff polls of that same window;
    None when no poll ended in that window (or the candidate is in none of them)."""
    today = today or datetime.date.today()
    market = defaultdict(lambda: defaultdict(list))
    with HISTORY.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["candidate"] in WEEKLY_CANDIDATES and r["win"]:
                market[r["candidate"]][monday(r["date"])].append(float(r["win"]))
    mondays = [w for c in market.values() for w in c]
    first = min(mondays + [monday(history["first"][0]["end"])])
    last = max(mondays)
    weeks = [first + datetime.timedelta(weeks=i) for i in range((last - first).days // 7 + 1)]
    cache, poll = {}, {c: [] for c in WEEKLY_CANDIDATES}
    for w in weeks:
        ref = min(w + datetime.timedelta(days=6), today)
        lo, hi = (ref - datetime.timedelta(days=WEEKLY_WINDOW_DAYS)).isoformat(), ref.isoformat()
        fp = [p for p in history["first"] if lo < p["end"] <= hi]
        rp = [r for r in history["runoff"] if lo < r["end"] <= hi]
        key = (tuple(p["id"] for p in fp), tuple(r["id"] for r in rp))
        if fp and key not in cache: cache[key] = simulate(fp, pairs_of(rp))
        sim = cache.get(key, {}) if fp else {}
        for c in WEEKLY_CANDIDATES:
            poll[c].append(round(sim[c]["win"], 1) if c in sim else None)
    avg = lambda xs: round(mean(xs), 1) if xs else None
    return {"weeks": [w.isoformat() for w in weeks], "windowDays": WEEKLY_WINDOW_DAYS, "uncertainty": "mid", "runs": SIM_RUNS,
            "series": {c: {"poll": poll[c], "market": [avg(market[c].get(w)) for w in weeks]} for c in WEEKLY_CANDIDATES}}

def write_polls_average(history):
    """data/polls_average.csv: weekly (Monday) mean first-round score per candidate over every scenario of the polls that ended that week."""
    by = defaultdict(list)
    for p in history["first"]:
        for c, v in p["v"].items(): by[(monday(p["end"]), c)].append(v)
    with POLLS_AVERAGE.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["week", "candidate", "average", "scenarios"])
        for (wk, c), v in sorted(by.items()): w.writerow([wk.isoformat(), c, round(mean(v), 1), len(v)])
    return len(by)

def market_prices(slug):
    """Yes prices (%) per candidate, plus the event's traded volume ($) and the sum of all its Yes prices (%)."""
    events = json.loads(get(GAMMA.format(slug=slug)))
    if not events:
        raise ValueError(f"no event returned for slug {slug}")
    out = {}
    for m in events[0]["markets"]:
        name = m.get("groupItemTitle") or m.get("question")
        prices = json.loads(m.get("outcomePrices") or "[]")
        outcomes = json.loads(m.get("outcomes") or '["Yes","No"]')
        if name and prices and outcomes[0] == "Yes":
            out[name] = round(100 * float(prices[0]), 1)   # price of "Yes"
    if not out:
        raise ValueError(f"no usable markets for slug {slug}")
    volume = float(events[0].get("volume") or 0) or sum(float(m.get("volumeNum") or 0) for m in events[0]["markets"])
    print(f"{slug}: {len(out)} markets, volume ${volume:,.0f}, prices add up to {sum(out.values()):.0f}%:", ", ".join(f"{k}={v}" for k, v in out.items()))
    return out, {"volume": round(volume), "sum": round(sum(out.values()), 1)}

# ---- Static layer (crawlers, link previews) --------------------------------------------------
# simulate() is the only implementation of the poll-to-probability Monte Carlo: build_data.py runs it for every view
# (see page_views()) and stores the results in data.json; the page just displays them.

def _i32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x

def _imul(a, b):
    return _i32((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF))

def _rng(seed):
    state = [_i32(seed)]
    def rand():
        s = state[0] = _i32(state[0] + 0x6D2B79F5)
        x = _imul(s ^ ((s & 0xFFFFFFFF) >> 15), 1 | s)
        x = _i32(x + _imul(x ^ ((x & 0xFFFFFFFF) >> 7), 61 | x)) ^ x
        return ((x ^ ((x & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF) / 4294967296
    return rand

def simulate(polls, pairs, level=SIM_MID, runs=SIM_RUNS):
    r, spare = _rng(2027), [None]
    def gauss():
        if spare[0] is not None:
            s, spare[0] = spare[0], None
            return s
        u = 0
        while not u: u = r()
        v = r(); m = math.sqrt(-2 * math.log(u))
        spare[0] = m * math.sin(2 * math.pi * v)
        return m * math.cos(2 * math.pi * v)
    seen, qual, win = defaultdict(int), defaultdict(int), defaultdict(int)
    for _ in range(runs):
        p = polls[int(r() * len(polls))]["v"]
        names = list(p)
        s = [max(0, p[n] + gauss() * (level["base"] + level["k"] * p[n])) for n in names]
        a = b = -1
        for j, x in enumerate(s):
            if a < 0 or x > s[a]: b, a = a, j
            elif b < 0 or x > s[b]: b = j
        for n in names: seen[n] += 1
        A, B = names[a], names[b]
        qual[A] += 1; qual[B] += 1
        k = sorted([A, B]); key = k[0] + "|" + k[1]
        tot = s[a] + s[b]
        share = pairs[key][0] if key in pairs else (100 * s[names.index(k[0])] / tot if tot else float("nan"))
        win[k[0] if share + gauss() * level["run"] > 50 else k[1]] += 1
    return {n: {"qual": 100 * qual[n] / seen[n], "win": 100 * win[n] / seen[n]} for n in seen}

def page_views(polls, pairs):
    """Everything the page needs from the poll simulation, so the page runs no Monte Carlo of its own:
    sim[uncertainty][candidate] = {qual, win} (%), and avg[candidate] = [mean first-round score, number of polls]."""
    sim = {lvl: {c: {k: round(v, 3) for k, v in r.items()} for c, r in simulate(polls, pairs, LEVELS[lvl]).items()} for lvl in LEVELS}
    tot, cnt = defaultdict(float), defaultdict(int)
    for p in polls:
        for c, v in p["v"].items(): tot[c] += v; cnt[c] += 1
    return sim, {c: [tot[c] / cnt[c], cnt[c]] for c in tot}

def slim_polls(polls):
    """The fields the page's poll table shows."""
    return [{"inst": p["inst"], "for": p["for"], "start": p["start"], "end": p["end"], "n": p["n"],
             "v": {c: p["v"][c] for c in TABLE_CANDIDATES if c in p["v"]}} for p in polls]

def surname(n):
    return {"Marine Le Pen": "Le Pen", "Jean-Luc Mélenchon": "Mélenchon", "Dominique de Villepin": "de Villepin",
            "Nicolas Dupont-Aignan": "Dupont-Aignan"}.get(n) or n.split(" ")[-1]

def headline(data):
    """Largest win gap between the poll simulation and the markets (same rule as renderSpot())."""
    sim = data["sim"]["mid"]
    rows = [{"c": m["c"], "market": m["win"], "poll": sim[m["c"]]["win"] if m["c"] in sim else None}
            for m in data["markets"]["candidates"]]
    rows.sort(key=lambda r: max(r["market"], r["poll"] or 0), reverse=True)
    rows = [r for r in rows if r["poll"] is not None]
    rows.sort(key=lambda r: abs(r["market"] - r["poll"]), reverse=True)
    top = rows[0]
    return {"name": top["c"], "poll": top["poll"], "market": top["market"], "updated": data["updated"]}

def fr_pct(x):
    return "<1" + NB + "%" if 0 < x < 1 else f"{math.floor(x + 0.5)}{NB}%"

def fr_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {FR_MONTHS[d.month - 1]} {d.year}"

def fr_money(v):
    if v >= 1e6:
        m = round(v / 1e6, 1 if v < 1e7 else 0)
        return (f"{m:g}".replace(".", ",") + NB + ("million" if m < 2 else "millions") + NB + "de" + NB + "$")
    return f"{round(v / 1000) * 1000:,}".replace(",", NB) + NB + "$"

def fr_figures(data):
    """Values of the {{placeholders}} in the French strings of index.html; figures() in index.html does the same in both languages."""
    ends = [p["end"] for p in data["polls"]]
    lo, hi = datetime.date.fromisoformat(min(ends)), datetime.date.fromisoformat(max(ends))
    mk = data["markets"]
    return {"upd": fr_date(data["updated"]), "snap": fr_date(mk["snapshot"]), "n": str(len(data["polls"])),
            "from": f"{'1er' if lo.day == 1 else lo.day} {FR_MONTHS[lo.month - 1]}" + (f" {lo.year}" if lo.year != hi.year else ""),
            "to": fr_date(hi.isoformat()),
            "vq": fr_money(mk["volume"]["qual"]), "vw": fr_money(mk["volume"]["win"]),
            "sum": f"{round(mk['qualSum'] / 10) * 10}{NB}%", "year": data["updated"][:4]}

def fill_figures(text, figs):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: figs[m.group(1)], text)

def french_strings():
    """The French strings of the page (i18n/fr.json): plain strings, plus lists and objects the static layer ignores."""
    return json.loads((ROOT / "i18n" / "fr.json").read_text(encoding="utf-8"))

def fill(page, pattern, text):
    page, n = re.subn(pattern, lambda m: m.group(1) + text + m.group(3), page, flags=re.S)
    if n != 1: raise ValueError(f"expected 1 match for {pattern!r}, got {n}")
    return page

def attr(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")

def static_html(region, fr, hl):
    """Fill every data-i element and the spotlight with the French text, in place."""
    keys = set(re.findall(r'\bdata-i="(\w+)"', region))
    if keys - set(fr): raise KeyError(f"no FR string for data-i keys: {sorted(keys - set(fr))}")
    region = re.sub(r'(<(\w+)\b[^>]*\bdata-i="(\w+)"[^>]*>)(.*?)(</\2>)',
                    lambda m: m.group(1) + fr[m.group(3)] + m.group(5), region, flags=re.S)
    cap = fr["spotCap"].replace("{n}", surname(hl["name"]))
    if re.search(r"\{\w+\}", cap): raise ValueError("spotCap uses placeholders other than {n}")
    region = fill(region, r'(<p class="who" id="spotWho">)(.*?)(</p>)', hl["name"])
    region = fill(region, r'(<div class="pin p" id="spotP"[^>]*><b>)(.*?)(</b>)', fr_pct(hl["poll"]))
    region = fill(region, r'(<div class="pin m" id="spotM"[^>]*><b>)(.*?)(</b>)', fr_pct(hl["market"]))
    return fill(region, r'(<p class="cap" id="spotCap">)(.*?)(</p>)', cap)

def meta_html(page, fr, hl):
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
    figs = f"{hl['name']}, {fr_pct(hl['poll'])} dans les sondages contre {fr_pct(hl['market'])} sur les marchés"
    desc = f"{fr['spotK']} : {figs}. {fr['h1']}"
    alt = f"{figs} ({fr_date(hl['updated'])})"
    img = SITE_URL + OG_IMAGE.name
    tags = [
        ("name", "description", desc),
        ("property", "og:type", "website"), ("property", "og:site_name", "L'Écart"), ("property", "og:locale", "fr_FR"),
        ("property", "og:url", SITE_URL), ("property", "og:title", title), ("property", "og:description", desc),
        ("property", "og:image", img), ("property", "og:image:width", "1200"), ("property", "og:image:height", "630"),
        ("property", "og:image:alt", alt),
        ("name", "twitter:card", "summary_large_image"), ("name", "twitter:title", title),
        ("name", "twitter:description", desc), ("name", "twitter:image", img), ("name", "twitter:image:alt", alt),
        ("name", "data-version", hl["updated"]),   # cache key of data.json and the event list (see js/app.js)
    ]
    return "\n".join(f'<meta {k}="{n}" content="{attr(c)}">' for k, n, c in tags)

def between(page, start, end, transform):
    """Rewrite what sits between two markers; the pair must already exist exactly once in index.html."""
    pat = re.compile("(" + re.escape(start) + ")(.*?)(" + re.escape(end) + ")", re.S)
    if len(pat.findall(page)) != 1: raise ValueError(f"need exactly one {start} ... {end} pair in index.html")
    return pat.sub(lambda m: m.group(1) + transform(m.group(2)) + m.group(3), page)

def write_index(hl):
    raw = INDEX.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"   # keep the file's own line endings (CRLF checkout on Windows)
    page = raw.replace("\r\n", "\n")
    fr = {k: fill_figures(v, hl["figs"]) for k, v in french_strings().items() if isinstance(v, str)}
    page = between(page, "<!--STATIC-START-->", "<!--STATIC-END-->", lambda region: static_html(region, fr, hl))
    page = between(page, "<!--META-START-->", "<!--META-END-->", lambda _: "\n" + meta_html(page, fr, hl) + "\n")
    INDEX.write_bytes(page.replace("\n", eol).encode("utf-8"))

def write_og_image(hl):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    BG, INK, MUTED, FAINT, RULE, POLL, MARKET = "#EEF0F4", "#161922", "#5A6071", "#9EA4B2", "#DDE0E7", "#3446A6", "#0B8474"
    fig = plt.figure(figsize=(12, 6.3), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1200); ax.set_ylim(630, 0); ax.axis("off")
    # brand: the site's dot + diamond mark, then the name
    ax.plot(80, 72, "o", ms=14, color=POLL); ax.plot(106, 72, "D", ms=11, color=MARKET)
    ax.text(132, 72, "L'Écart", fontsize=30, fontweight="bold", color=INK, va="center")
    ax.text(1120, 72, "Présidentielle 2027", fontsize=20, color=MUTED, va="center", ha="right")
    ax.text(80, 168, "Le plus grand écart, chances de victoire", fontsize=21, color=MUTED, va="center")
    ax.text(80, 236, hl["name"], fontsize=52, fontweight="bold", color=INK, va="center")
    # 0-100 scale with both pins, as in the page's spotlight
    x0, x1, y = 110, 1090, 470
    px = lambda v: x0 + v / 100 * (x1 - x0)
    xp, xm = px(hl["poll"]), px(hl["market"])
    ax.plot([x0, x1], [y, y], color=RULE, lw=3, solid_capstyle="round")
    ax.plot([xp, xm], [y, y], color=FAINT, lw=9, solid_capstyle="round", alpha=.55)
    ax.plot(xp, y, "o", ms=24, color=POLL, mec=BG, mew=3)
    ax.plot(xm, y, "D", ms=19, color=MARKET, mec=BG, mew=3)
    lo_c, hi_c = 150, 1050   # keep the label centres inside the canvas
    cp, cm = min(max(xp, lo_c), hi_c), min(max(xm, lo_c), hi_c)
    if abs(cp - cm) < 300:   # small gap: spread the two labels apart, around the midpoint, instead of overlapping them
        mid = min(max((cp + cm) / 2, lo_c + 150), hi_c - 150)
        cp, cm = (mid - 150, mid + 150) if xp <= xm else (mid + 150, mid - 150)
    for lx, val, label, col in ((cp, hl["poll"], "sondages", POLL), (cm, hl["market"], "marchés", MARKET)):
        ax.text(lx, 352, fr_pct(val), fontsize=52, fontweight="bold", color=col, ha="center", va="center")
        ax.text(lx, 405, label, fontsize=21, color=MUTED, ha="center", va="center")
    for v in (0, 50, 100):
        ax.text(px(v), 522, str(v), fontsize=17, color=FAINT, ha="center", va="center")
    ax.plot([80, 1120], [566, 566], color=RULE, lw=2)
    ax.text(80, 596, "Données du " + fr_date(hl["updated"]), fontsize=20, color=MUTED, va="center")
    fig.savefig(OG_IMAGE, dpi=100, facecolor=BG, metadata={"Software": None})
    plt.close(fig)

def write_static(data):
    """Runs after data.json is written. A failure is reported at the end so the data refresh still ships."""
    hl = headline(data)
    hl["figs"] = fr_figures(data)
    print(f"Headline: {hl['name']}, polls {hl['poll']:.1f}%, markets {hl['market']:.1f}%")
    failed = []
    for step in (write_og_image, write_index):
        try:
            step(hl)
        except Exception as e:
            print(f"{step.__name__} failed: {e!r}")
            failed.append(step.__name__)
    if failed: raise SystemExit("static step failed: " + ", ".join(failed))

def main():
    polls, pairs, trend, history = load_polls()
    data_path = ROOT / "data.json"
    previous = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}
    try:
        (win, win_stats), (qual, qual_stats) = market_prices(WIN_SLUG), market_prices(QUAL_SLUG)
        names = [n for n in win if n in FAMILY]
        print("Unmatched market names (not in FAMILY):", [n for n in win if n not in FAMILY])
        print("FAMILY names with no market:", [n for n in FAMILY if n not in win])
        if not names:
            raise ValueError("no market name matched FAMILY")
        candidates = [{"c": n, "f": FAMILY[n], "win": win.get(n, 0), "qual": qual.get(n, 0)} for n in names]
        # traded volume ($) of both markets and the total of the "reach the runoff" prices (%), for the liquidity note
        markets = {"snapshot": datetime.date.today().isoformat(), "source": "Polymarket", "candidates": candidates,
                   "volume": {"win": win_stats["volume"], "qual": qual_stats["volume"]}, "qualSum": qual_stats["sum"]}
        hist = HISTORY
        hist.parent.mkdir(exist_ok=True)
        new = not hist.exists()
        with hist.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new: w.writerow(["date", "candidate", "win", "qual"])
            for c in candidates: w.writerow([markets["snapshot"], c["c"], c["win"], c["qual"]])
    except Exception as e:   # keep yesterday's market data rather than breaking the page
        print("Market fetch failed, keeping previous snapshot:", e)
        markets = previous.get("markets")
    try:
        weekly = weekly_series(history)
    except Exception as e:   # same rule as the markets: keep the previous series rather than breaking the page
        print("Weekly series failed, keeping previous:", e)
        weekly = previous.get("weekly")
    sim, avg = page_views(polls, pairs)
    data = {"updated": datetime.date.today().isoformat(), "polls": slim_polls(polls), "avg": avg, "sim": sim, "trend": trend, "weekly": weekly, "markets": markets}
    data_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(polls)} polls, {len(markets['candidates'])} market candidates, {write_polls_average(history)} weekly poll averages")
    write_static(data)

if __name__ == "__main__":
    main()
