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
SIM_MID = {"base": 1.5, "k": 0.2, "run": 6}   # "mid" level of LEVELS in index.html
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
WEEKLY_CANDIDATES = ["Marine Le Pen","Édouard Philippe","Jean-Luc Mélenchon"]   # polls vs markets small multiples
HISTORY = ROOT / "data" / "market_history.csv"

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
    obs = [(rs[0]["fin_enquete"], {r["candidat"]: float(r["intentions"]) for r in rs if r["candidat"] in WEEKLY_CANDIDATES})
           for rs in first.values() if rs[0]["fin_enquete"] >= TREND_START]
    return polls, pairs, trend, obs

def monday(iso):
    d = datetime.date.fromisoformat(iso)
    return d - datetime.timedelta(days=d.weekday())

def weekly_series(obs):
    """Weekly (Monday-start) series per WEEKLY_CANDIDATES, from the first market day to the last.
    market: mean of the daily prices of the week (market_history.csv). poll: mean first-round score over every
    poll scenario ending that week, None when no poll ended that week (polls are sparse: the page decides what to bridge)."""
    market, poll = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    with HISTORY.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["candidate"] in WEEKLY_CANDIDATES and r["win"]:
                market[r["candidate"]][monday(r["date"])].append(float(r["win"]))
    for end, v in obs:
        for c, x in v.items(): poll[c][monday(end)].append(x)
    first, last = (f([w for c in market.values() for w in c]) for f in (min, max))
    weeks = [first + datetime.timedelta(weeks=i) for i in range((last - first).days // 7 + 1)]
    avg = lambda xs: round(mean(xs), 1) if xs else None
    return {"weeks": [w.isoformat() for w in weeks],
            "series": {c: {"poll": [avg(poll[c].get(w)) for w in weeks], "market": [avg(market[c].get(w)) for w in weeks]}
                       for c in WEEKLY_CANDIDATES}}

def market_prices(slug):
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
    print(f"{slug}: {len(out)} markets:", ", ".join(f"{k}={v}" for k, v in out.items()))
    return out

# ---- Static layer (crawlers, link previews) --------------------------------------------------
# simulate() below is a line-by-line port of simulate() in index.html (same PRNG, same draw order),
# so the headline figures match what the page shows. Keep the two in sync.

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

def surname(n):
    return {"Marine Le Pen": "Le Pen", "Jean-Luc Mélenchon": "Mélenchon", "Dominique de Villepin": "de Villepin",
            "Nicolas Dupont-Aignan": "Dupont-Aignan"}.get(n) or n.split(" ")[-1]

def headline(data):
    """Largest win gap between the poll simulation and the markets (same rule as renderSpot())."""
    sim = simulate(data["polls"], data["pairs"])
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

def french_strings(page):
    """FR entries of the T object in index.html: plain strings, plus spotCap (a template literal)."""
    body = re.search(r"const T=\{\s*fr:\{(.*?)\},\s*en:\{", page, re.S).group(1)
    fr = {k: json.loads('"' + v + '"') for k, v in re.findall(r'(?<![\w"])(\w+):"((?:[^"\\]|\\.)*)"', body)}
    cap = re.search(r"spotCap:\(n,p,m\)=>`((?:[^`\\]|\\.)*)`", body)
    fr["spotCap"] = cap.group(1)
    return fr

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
    cap = fr["spotCap"].replace("${n}", surname(hl["name"]))
    if "${" in cap: raise ValueError("spotCap uses placeholders other than ${n}")
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
    fr = french_strings(page)
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
    polls, pairs, trend, obs = load_polls()
    data_path = ROOT / "data.json"
    previous = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}
    try:
        win, qual = market_prices(WIN_SLUG), market_prices(QUAL_SLUG)
        names = [n for n in win if n in FAMILY]
        print("Unmatched market names (not in FAMILY):", [n for n in win if n not in FAMILY])
        print("FAMILY names with no market:", [n for n in FAMILY if n not in win])
        if not names:
            raise ValueError("no market name matched FAMILY")
        candidates = [{"c": n, "f": FAMILY[n], "win": win.get(n, 0), "qual": qual.get(n, 0)} for n in names]
        markets = {"snapshot": datetime.date.today().isoformat(), "source": "Polymarket", "candidates": candidates}
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
        weekly = weekly_series(obs)
    except Exception as e:   # same rule as the markets: keep the previous series rather than breaking the page
        print("Weekly series failed, keeping previous:", e)
        weekly = previous.get("weekly")
    data = {"updated": datetime.date.today().isoformat(), "polls": polls, "pairs": pairs, "trend": trend, "weekly": weekly, "markets": markets}
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(polls)} polls, {len(markets['candidates'])} market candidates")
    write_static(data)

if __name__ == "__main__":
    main()
