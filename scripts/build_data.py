"""Daily data refresh for L'Écart.

1. Downloads the open poll compilation (MieuxVoter/presidentielle2027, MIT licence).
2. Fetches current prices from two independent prediction-market venues: Polymarket (winner and runoff-qualification
   markets) and Kalshi (winner market only; see the KALSHI_BASE comment for why it stops there). Public APIs, no key.
3. Runs the poll-to-probability simulation for every view of the page and writes data.json, plus the CSV downloads
   (data/market_history.csv gets today's prices per venue, data/polls_average.csv).
4. Writes the static French text, meta/Open Graph tags and og-image.png so crawlers and link
   previews see content without running JS (index.html, between the STATIC and META markers). During an
   election-silence period (config.json, see in_blackout()) this static layer shows the legal notice instead.

All-or-nothing: everything is built in memory and in a temporary folder, checked by validate_venue()/validate_polls(),
and only then moved over the real files. Any failure (network, parsing, validation) ends the run with a non-zero exit
code and leaves yesterday's files untouched, EXCEPT that the two market venues are independent: one venue's fetch or
sanity check failing does not abort the run, it falls back to that venue's last snapshot and marks it stale (see
run()); the run only aborts if NEITHER venue has usable data. Polymarket is blocked from some countries: use
--reuse-markets there (keeps its last market snapshot; Kalshi is still fetched fresh).

Run `python scripts/build_data.py`; the tests are in tests/.
"""
import argparse, csv, io, json, datetime, math, os, pathlib, re, shutil, sys, tempfile, textwrap, time, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from statistics import mean
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLLS_URL = "https://raw.githubusercontent.com/MieuxVoter/presidentielle2027/main/presidentielle2027.csv"
GAMMA = "https://gamma-api.polymarket.com/events?slug={slug}"
WIN_SLUG = "next-french-presidential-election"
QUAL_SLUG = "next-french-presidential-election-who-will-advance-to-the-2nd-round"
# Kalshi: a second, independent venue for the winner price only. Its KXFRPRESBALLOT series is NOT a runoff/qualifying
# market (it resolves on official candidacy confirmation, a different question), so unlike Polymarket, Kalshi never
# contributes a "qual" price here. Public GET endpoints, no API key. docs.kalshi.com; data used per user direction
# despite Kalshi's Data Terms of Use restricting redistribution (see CLAUDE.md for the record of that decision).
KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"
KALSHI_WIN_SERIES = "KXFRENCHPRES"
# KXFRPRESBALLOT resolves on official candidacy confirmation for the first round, a third question distinct from
# both "wins the election" and "qualifies for the runoff": it is shown as its own small "on the ballot" indicator
# (see build_ballot()), never merged into win or qual.
KALSHI_BALLOT_SERIES = "KXFRPRESBALLOT"
KALSHI_ALIASES = {}   # {Kalshi yes_sub_title: our canonical FAMILY name}, for when the two spellings drift apart
# A market's lifetime volume below this ($) gets the "thin market" flag (see thin_flags()): $20,000 is a round,
# conservative figure at which a single order of ordinary size can move the price several points, so a thinly
# traded market's price is less informative than the same price on a deep one. Documented in the Method's
# "Liquidité" section; keep the two in step.
THIN_MARKET_VOLUME = 20000
FIRST_ROUND_WINDOW_DAYS = 60   # polls used for the simulation
TREND_START = "2025-09-01"
SITE_URL = "https://lukesegault.github.io/lecart/"
INDEX = ROOT / "index.html"
CANDIDAT = ROOT / "candidat.html"
SECOND_TOUR = ROOT / "second-tour.html"
OG_IMAGE = ROOT / "og-image.png"
CONFIG = ROOT / "config.json"
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
WEEKLY_CANDIDATES = TREND_CANDIDATES   # polls vs markets chart: same roster as the monthly trend, now selectable on the homepage and candidate page
WEEKLY_WINDOW_DAYS = 30        # polls feeding each weekly poll-implied win probability
HISTORY = ROOT / "data" / "market_history.csv"
POLLS_AVERAGE = ROOT / "data" / "polls_average.csv"
LIQUIDITY = ROOT / "data" / "market_liquidity.csv"

def get(url, tries=4, pause=2.0):
    """GET with retries and exponential backoff (2 s, 4 s, 8 s) on network errors, timeouts, 429 and 5xx."""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lecart-data-bot"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500: raise
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        if attempt == tries: raise err
        wait = pause * 2 ** (attempt - 1)
        print(f"GET {url} failed ({err!r}), retry {attempt}/{tries - 1} in {wait:.0f}s", file=sys.stderr)
        time.sleep(wait)

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
    return parse_polls(list(csv.DictReader(io.StringIO(get(POLLS_URL)))))

def parse_polls(rows, today=None):
    """Poll rows of the MieuxVoter CSV -> (polls of the last FIRST_ROUND_WINDOW_DAYS, runoff pairs, monthly trend, history for the weekly series)."""
    today = today or datetime.date.today()
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

def weekly_series(history, market_rows, today=None):
    """Weekly (Monday-start) series per WEEKLY_CANDIDATES, from the first poll (or market day, if earlier) to the last market day.
    venues: each venue's own weekly average (each venue counts once, not once per day it happened to be quoted);
    no blended figure across venues is computed anywhere in this file, so there is no single "market" line here,
    only each venue's own.
    poll: poll-implied win probability, the same Monte Carlo as the rest of the page (simulate(), medium uncertainty, seed 2027) run on the
    first-round polls that ended in the WEEKLY_WINDOW_DAYS days up to the end of the week, with the runoff polls of that same window;
    None when no poll ended in that window (or the candidate is in none of them)."""
    today = today or datetime.date.today()
    market = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))   # candidate -> venue -> monday -> [prices]
    for r in market_rows:
        if r["candidate"] in WEEKLY_CANDIDATES and r["win"]:
            market[r["candidate"]][r["venue"]][monday(r["date"])].append(float(r["win"]))
    mondays = [w for venues in market.values() for days in venues.values() for w in days]
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
    series = {}
    for c in WEEKLY_CANDIDATES:
        venues = {v: [avg(market[c][v].get(w)) for w in weeks] for v in market[c]}
        series[c] = {"poll": poll[c], "venues": venues}
    return {"weeks": [w.isoformat() for w in weeks], "windowDays": WEEKLY_WINDOW_DAYS, "uncertainty": "mid", "runs": SIM_RUNS,
            "series": series}

def polls_average_rows(history):
    """data/polls_average.csv rows: weekly (Monday) mean first-round score per candidate over every scenario of the polls that ended that week."""
    by = defaultdict(list)
    for p in history["first"]:
        for c, v in p["v"].items(): by[(monday(p["end"]), c)].append(v)
    return [[wk.isoformat(), c, round(mean(v), 1), len(v)] for (wk, c), v in sorted(by.items())]

def read_history_rows():
    """Rows of data/market_history.csv as dicts of strings (date, candidate, venue, win, qual). Rows written before
    the venue column existed (every row up to 22 Sept 2026) are all Polymarket; defaulted here so callers never
    need to special-case them, and rewritten with the column the next time build_outputs() runs."""
    if not HISTORY.exists(): return []
    with HISTORY.open(newline="", encoding="utf-8") as fh: rows = list(csv.DictReader(fh))
    for r in rows: r.setdefault("venue", "polymarket")
    return rows

def csv_text(header, rows, lineterminator="\n"):
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator=lineterminator)
    w.writerow(header); w.writerows(rows)
    return buf.getvalue()

def history_with_today(rows, snapshot, venue_candidates):
    """The history rows with today's prices in place of any earlier rows of the same (date, venue) (a second run
    the same day does not duplicate). venue_candidates: {venue: {name: {win[, qual]}}}, only venues that actually
    produced prices this run (a stale/failed venue's rows for today are left exactly as they were, if any)."""
    kept = [r for r in rows if not (r["date"] == snapshot and r["venue"] in venue_candidates)]
    new = [{"date": snapshot, "candidate": name, "venue": venue, "win": str(p["win"]), "qual": str(p.get("qual", ""))}
           for venue, prices in venue_candidates.items() for name, p in prices.items()]
    return kept + new

def read_liquidity_rows():
    """Rows of data/market_liquidity.csv as dicts of strings (date, venue, candidate, market, volume, liquidity)."""
    if not LIQUIDITY.exists(): return []
    with LIQUIDITY.open(newline="", encoding="utf-8") as fh: return list(csv.DictReader(fh))

def liquidity_with_today(rows, snapshot, venue_candidates, ballot_candidates=None):
    """The liquidity rows with today's figures in place of any earlier rows of the same (date, venue, market) (a
    second run the same day does not duplicate). venue_candidates: {venue: {name: {..., volume: {market: $},
    liquidity: {market: $}}}}, only venues that actually produced fresh figures this run. One row per (venue,
    candidate, market): `market` is "win", "qual" or (from ballot_candidates, Kalshi's KXFRPRESBALLOT) "ballot",
    each replaced independently of the others so one failing today doesn't discard another's fresh row."""
    def stale(r):
        if r["date"] != snapshot: return False
        if r["market"] == "ballot": return r["venue"] == "kalshi" and bool(ballot_candidates)
        return r["venue"] in venue_candidates
    kept = [r for r in rows if not stale(r)]
    new = [{"date": snapshot, "venue": venue, "candidate": name, "market": mkt, "volume": str(v), "liquidity": str(p.get("liquidity", {}).get(mkt, ""))}
           for venue, prices in venue_candidates.items() for name, p in prices.items() for mkt, v in (p.get("volume") or {}).items()]
    if ballot_candidates:
        new += [{"date": snapshot, "venue": "kalshi", "candidate": name, "market": "ballot",
                  "volume": str(p["volume"]), "liquidity": str(p["liquidity"])} for name, p in ballot_candidates.items()]
    return kept + new

def market_prices(slug):
    """Yes prices (%) per candidate, the event's traded volume ($) and the sum of all its Yes prices (%), and each
    candidate's own volume/liquidity ($, from the Gamma API's per-market volumeNum/liquidityNum)."""
    return parse_event(json.loads(get(GAMMA.format(slug=slug))), slug)

def parse_event(events, slug=""):
    if not events:
        raise ValueError(f"no event returned for slug {slug}")
    out, liq = {}, {}
    for m in events[0]["markets"]:
        name = m.get("groupItemTitle") or m.get("question")
        prices = json.loads(m.get("outcomePrices") or "[]")
        outcomes = json.loads(m.get("outcomes") or '["Yes","No"]')
        if name and prices and outcomes[0] == "Yes":
            out[name] = round(100 * float(prices[0]), 1)   # price of "Yes"
            liq[name] = {"volume": round(float(m.get("volumeNum") or 0)), "liquidity": round(float(m.get("liquidityNum") or 0))}
    if not out:
        raise ValueError(f"no usable markets for slug {slug}")
    volume = float(events[0].get("volume") or 0) or sum(float(m.get("volumeNum") or 0) for m in events[0]["markets"])
    liquidity = sum(v["liquidity"] for v in liq.values())
    print(f"{slug}: {len(out)} markets, volume ${volume:,.0f}, prices add up to {sum(out.values()):.0f}%:", ", ".join(f"{k}={v}" for k, v in out.items()))
    return out, {"volume": round(volume), "liquidity": round(liquidity), "sum": round(sum(out.values()), 1)}, liq

def kalshi_get(path, **params):
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return json.loads(get(f"{KALSHI_BASE}{path}" + (f"?{qs}" if qs else "")))

def kalshi_markets(series_ticker):
    """Every open market in a Kalshi series, paginating via `cursor` until exhausted."""
    out, cursor = [], None
    while True:
        page = kalshi_get("/markets", series_ticker=series_ticker, status="open", limit=200, cursor=cursor)
        out += page["markets"]
        cursor = page.get("cursor") or None
        if not cursor: return out

def kalshi_win_prices():
    """Yes prices (%) per candidate from Kalshi's KXFRENCHPRES winner markets, plus traded volume ($, approximate:
    Kalshi's volume_fp is a contract count, and these contracts have $1 notional, so count and dollars coincide),
    the sum of all Yes prices (%, same sanity check as Polymarket's), and each candidate's own volume/open interest."""
    return _kalshi_series_prices(KALSHI_WIN_SERIES)

def kalshi_ballot_prices():
    """Yes prices (%) per candidate from Kalshi's KXFRPRESBALLOT markets: not a qualifying/runoff indicator (see the
    KALSHI_BALLOT_SERIES comment), just "is this person an official candidate", shown in its own small section."""
    return _kalshi_series_prices(KALSHI_BALLOT_SERIES)

def _kalshi_series_prices(series_ticker):
    markets = kalshi_markets(series_ticker)
    out, liq, volume = {}, {}, 0.0
    for m in markets:
        price = m.get("last_price_dollars")
        if price is None: continue
        name = KALSHI_ALIASES.get(m["yes_sub_title"], m["yes_sub_title"])
        out[name] = round(100 * float(price), 1)
        v = float(m.get("volume_fp") or 0)
        liq[name] = {"volume": round(v), "openInterest": round(float(m.get("open_interest_fp") or 0))}
        volume += v
    if not out: raise ValueError(f"no usable Kalshi markets for series {series_ticker}")
    open_interest = sum(v["openInterest"] for v in liq.values())
    print(f"Kalshi {series_ticker}: {len(out)} markets, volume ${volume:,.0f}, prices add up to {sum(out.values()):.0f}%:",
          ", ".join(f"{k}={v}" for k, v in out.items()))
    return out, {"volume": round(volume), "liquidity": round(open_interest), "sum": round(sum(out.values()), 1)}, liq

def kalshi_candlestick_prices(series_ticker, ticker, start, end):
    """{ISO date: win %} daily closes for one Kalshi market, from its candlesticks. A day with no trade has no
    `price` block; the bid/ask midpoint is used instead so a quiet day doesn't leave a hole in the history."""
    start_ts, end_ts = int(datetime.datetime.combine(start, datetime.time.min, datetime.timezone.utc).timestamp()), \
                        int(datetime.datetime.combine(end, datetime.time.max, datetime.timezone.utc).timestamp())
    data = kalshi_get(f"/series/{series_ticker}/markets/{ticker}/candlesticks", start_ts=start_ts, end_ts=end_ts, period_interval=1440)
    out = {}
    for c in data["candlesticks"]:
        d = datetime.datetime.fromtimestamp(c["end_period_ts"], datetime.timezone.utc).date().isoformat()
        price = c.get("price", {}).get("close_dollars")
        if price is None:
            bid, ask = c.get("yes_bid", {}).get("close_dollars"), c.get("yes_ask", {}).get("close_dollars")
            if bid is None or ask is None: continue
            price = (float(bid) + float(ask)) / 2
        out[d] = round(100 * float(price), 1)
    return out

# ---- Static layer (crawlers, link previews) --------------------------------------------------
# simulate() is the only implementation of the poll-to-probability Monte Carlo: build_data.py runs it for every view
# (see page_views()) and stores the results in data.json; the page just displays them.

def build_candidates_polymarket(win, qual, liq_win, liq_qual):
    """{name: {win, qual, volume, liquidity}} for every Polymarket-priced name we have a political family for.
    A missing runoff price counts as 0; volume/liquidity are each {win, qual} ($, 0 for a market that didn't price
    this candidate)."""
    return {n: {"win": win[n], "qual": qual.get(n, 0),
                "volume": {"win": liq_win[n]["volume"], "qual": liq_qual.get(n, {}).get("volume", 0)},
                "liquidity": {"win": liq_win[n]["liquidity"], "qual": liq_qual.get(n, {}).get("liquidity", 0)}}
            for n in win if n in FAMILY}

def build_candidates_kalshi(win, liq_win):
    """{name: {win, volume, liquidity}} for every Kalshi-priced name we have a political family for. Winner price
    only: KXFRPRESBALLOT is not a qualifying/runoff market (see the KALSHI_BASE comment), so Kalshi never supplies
    `qual` here (its own price lives in `markets.ballot`, built separately by build_ballot())."""
    return {n: {"win": win[n], "volume": {"win": liq_win[n]["volume"]}, "liquidity": {"win": liq_win[n]["openInterest"]}}
            for n in win if n in FAMILY}

def build_ballot(price, liq):
    """{name: {price, volume, liquidity}} for every Kalshi KXFRPRESBALLOT-priced name we have a political family
    for: "is this person an official candidate", never merged with win or qual (see KALSHI_BALLOT_SERIES)."""
    return {n: {"price": price[n], "volume": liq[n]["volume"], "liquidity": liq[n]["openInterest"]} for n in price if n in FAMILY}

def merge_candidates(venue_prices):
    """venue_prices: {venue: {name: {win[, qual], volume, liquidity}}}, one entry per venue that produced usable
    prices this run. One output row per candidate priced by at least one venue. No blended figure is computed here
    or anywhere else in this file: `venues` carries each venue's own, unmixed numbers, and every consumer (the
    page, the CSVs, the headline) reads a specific venue's own price, never a mean across venues."""
    names = sorted({n for prices in venue_prices.values() for n in prices})
    return [{"c": n, "f": FAMILY[n], "venues": {v: prices[n] for v, prices in venue_prices.items() if n in prices}} for n in names]

def thin_flags(win_volume, qual_volume=None):
    """{"win": bool[, "qual": bool]}: whether this venue's lifetime volume for that market as a whole is below
    THIN_MARKET_VOLUME, i.e. every price it quotes should carry the discreet "thin market" flag."""
    flags = {"win": win_volume < THIN_MARKET_VOLUME}
    if qual_volume is not None: flags["qual"] = qual_volume < THIN_MARKET_VOLUME
    return flags

PRICE_KEYS = ("win", "qual", "price")   # keys of `prices[name]` that are 0-100 prices, as opposed to volume/liquidity

def validate_venue(prices, win_sum, previous_markets, venue, label, check_sum=True):
    """Reasons not to trust `prices` (one venue, {name: {win[, qual], volume, liquidity}}) this run (empty: fine).
    previous_markets is yesterday's data["markets"] (or None); a candidate that venue priced yesterday and doesn't
    today is suspect. check_sum is False for the "on the ballot" indicator (see fetch_ballot()): unlike win/qual,
    it isn't a single-winner market, so its prices are independent and have no reason to sum near 100%."""
    bad = []
    for name, p in prices.items():
        for k in PRICE_KEYS:
            if k not in p: continue
            v = p[k]
            if not 0 <= v <= 100: bad.append(f"{label}: price out of range: {name} {k} = {v}")
    if check_sum and not 85 <= win_sum <= 115: bad.append(f"{label}: winner prices add up to {win_sum:.1f}%, outside 85-115%")
    if previous_markets:
        prev_names = {c["c"] for c in previous_markets.get("candidates", []) if venue in c.get("venues", {})}
        gone = sorted(prev_names - set(prices))
        if gone: bad.append(f"candidates missing from {label}: " + ", ".join(gone))
    return bad

def validate_polls(data, previous):
    """Reasons not to publish `data` at all (empty: fine): the poll side, independent of any market venue."""
    bad = []
    before, now = len(previous.get("polls", [])), len(data["polls"])
    if before and now < 0.8 * before: bad.append(f"poll count fell from {before} to {now} (more than 20%)")
    if not data["polls"]: bad.append("no poll in the window")
    return bad

# ---- Election-silence period (French Act No. 77-808 of 19 July 1977: no poll publication the day before or the day
# of a round) ------------------------------------------------------------------------------------------------------
# config.json is the single source of truth, read here and by js/pages-common.js's checkBlackout(): keep both in step.

def load_config():
    if not CONFIG.exists(): return {"blackout": {"timezone": "Europe/Paris", "periods": []}}
    return json.loads(CONFIG.read_text(encoding="utf-8"))

def blackout_periods_utc(config):
    cfg = config.get("blackout", {})
    tz = ZoneInfo(cfg.get("timezone", "Europe/Paris"))
    periods = []
    for p in cfg.get("periods", []):
        start = datetime.datetime.fromisoformat(p["start"]).replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        end = datetime.datetime.fromisoformat(p["end"]).replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        periods.append((start, end))
    return periods

def in_blackout(config, now=None):
    """Whether `now` (UTC, defaults to the current instant) falls inside one of config.json's blackout periods."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return any(start <= now < end for start, end in blackout_periods_utc(config))

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

def headline(data):
    """The candidate with the single largest win-probability gap between one venue's own price and the poll
    simulation (never a blended figure: each venue's gap against the polls is judged on its own, and the largest
    of those, across every venue and candidate, wins). `venues` carries every venue that prices that candidate's
    win event, for a range headline ("between X% and Y%") when more than one does, or a named single venue when
    only one does (see fr_headline_sentence() / js/index.js's mirror of this)."""
    sim = data["sim"]["mid"]
    best = None
    for m in data["markets"]["candidates"]:
        poll = sim[m["c"]]["win"] if m["c"] in sim else None
        if poll is None: continue
        for venue, p in m["venues"].items():
            gap = abs(p["win"] - poll)
            if best is None or gap > best[0]:
                best = (gap, m["c"], poll, {v: pv["win"] for v, pv in m["venues"].items()})
    _, name, poll, venues = best
    return {"name": name, "poll": poll, "venues": venues, "updated": data["updated"]}

def fr_pct(x):
    return "<1" + NB + "%" if 0 < x < 1 else f"{math.floor(x + 0.5)}{NB}%"

def fr_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {FR_MONTHS[d.month - 1]} {d.year}"

def fr_figures(data):
    """Values of the {{placeholders}} in the French strings of index.html; figures() in index.html does the same in both languages."""
    ends = [p["end"] for p in data["polls"]]
    lo, hi = datetime.date.fromisoformat(min(ends)), datetime.date.fromisoformat(max(ends))
    mk = data["markets"]
    return {"upd": fr_date(data["updated"]), "snap": fr_date(mk["snapshot"]), "n": str(len(data["polls"])),
            "from": f"{'1er' if lo.day == 1 else lo.day} {FR_MONTHS[lo.month - 1]}" + (f" {lo.year}" if lo.year != hi.year else ""),
            "to": fr_date(hi.isoformat()), "year": data["updated"][:4], "thin": f"{mk.get('thinThreshold', THIN_MARKET_VOLUME):,}".replace(",", NB)}

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

def fr_headline_sentence(fr, hl):
    """The same sentence js/index.js builds client-side, for the static layer and the meta description. A range
    ("entre X% et Y%") when more than one venue prices the headline candidate's win event, a single venue named
    explicitly when only one does: never a figure blended across venues."""
    venues = hl["venues"]
    if len(venues) > 1:
        lo, hi = min(venues.values()), max(venues.values())
        sentence = (fr["headlineRange"].replace("{n}", hl["name"]).replace("{lo}", fr_pct(lo)).replace("{hi}", fr_pct(hi))
                    .replace("{p}", fr_pct(hl["poll"])).replace("{v}", fr["verbW"]))
    else:
        venue, m = next(iter(venues.items()))
        sentence = (fr["headlineSingle"].replace("{venue}", fr[f"venue{venue.capitalize()}"]).replace("{n}", hl["name"])
                    .replace("{m}", fr_pct(m)).replace("{p}", fr_pct(hl["poll"])).replace("{v}", fr["verbW"]))
    if re.search(r"\{\w+\}", sentence): raise ValueError("headline uses an unfilled placeholder")
    return sentence

def toggle_blackout_markup(region, blackout):
    """Swap which of #blackoutNotice/#mainContent carries the `hidden` attribute, so a crawler that never runs JS
    still sees the legal notice (not the figures) during an election-silence period. A no-op outside one."""
    if not blackout: return region
    subs = [('<div id="blackoutNotice" class="sp-blackout" hidden>', '<div id="blackoutNotice" class="sp-blackout">'),
            ('<div id="mainContent">', '<div id="mainContent" hidden>')]
    for old, new in subs:
        if region.count(old) != 1: raise ValueError(f"expected exactly one {old!r} in index.html")
        region = region.replace(old, new, 1)
    return region

def static_html(region, fr, hl, blackout=False):
    """Fill every data-i element and the crawler-visible headline (js/index.js computes the same sentence at runtime).
    During an election-silence period (see in_blackout()), the headline becomes the legal notice instead, and
    toggle_blackout_markup() (called by render_index()) swaps which block is visible."""
    keys = set(re.findall(r'\bdata-i="(\w+)"', region))
    if keys - set(fr): raise KeyError(f"no FR string for data-i keys: {sorted(keys - set(fr))}")
    region = re.sub(r'(<(\w+)\b[^>]*\bdata-i="(\w+)"[^>]*>)(.*?)(</\2>)',
                    lambda m: m.group(1) + fr[m.group(3)] + m.group(5), region, flags=re.S)
    headline_text = fr["blackoutTitle"] if blackout else fr_headline_sentence(fr, hl)
    return fill(region, r'(<h1 class="sp-h1" id="siteH1">)(.*?)(</h1>)', headline_text)

def meta_html(page, fr, hl, blackout=False):
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
    if blackout:
        desc = alt = fr["blackoutMeta"]
    else:
        mkt_txt = " / ".join(f"{fr[f'venue{v.capitalize()}']} {fr_pct(p)}" for v, p in hl["venues"].items())
        figs = f"{hl['name']}, {fr_pct(hl['poll'])} dans les sondages contre {mkt_txt} sur les marchés"
        desc = f"{fr_headline_sentence(fr, hl)} {fr['dek']}"
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

def render_index(hl, fr, blackout=False):
    """index.html with the static French layer and the meta tags refreshed."""
    raw = INDEX.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"   # keep the file's own line endings (CRLF checkout on Windows)
    page = raw.replace("\r\n", "\n")
    page = between(page, "<!--STATIC-START-->", "<!--STATIC-END-->",
                   lambda region: toggle_blackout_markup(static_html(region, fr, hl, blackout), blackout))
    page = between(page, "<!--META-START-->", "<!--META-END-->", lambda _: "\n" + meta_html(page, fr, hl, blackout) + "\n")
    return page.replace("\n", eol)

def write_og_image(hl, path):
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
    # 0-100 scale: the poll pin, and one diamond per venue that prices this candidate (never a single blended
    # market pin) -- a dumbbell between them when there are two, a lone diamond named after its venue when one.
    x0, x1, y = 110, 1090, 470
    px = lambda v: x0 + v / 100 * (x1 - x0)
    xp = px(hl["poll"])
    venue_x = {v: px(p) for v, p in hl["venues"].items()}
    ax.plot([x0, x1], [y, y], color=RULE, lw=3, solid_capstyle="round")
    if len(venue_x) > 1:
        vx = sorted(venue_x.values())
        ax.plot([vx[0], vx[-1]], [y, y], color=FAINT, lw=9, solid_capstyle="round", alpha=.55)
    ax.plot(xp, y, "o", ms=24, color=POLL, mec=BG, mew=3)
    for vx in venue_x.values(): ax.plot(vx, y, "D", ms=19, color=MARKET, mec=BG, mew=3)
    lo_c, hi_c = 150, 1050   # keep the label centres inside the canvas
    clamp = lambda x: min(max(x, lo_c), hi_c)
    labels = [(clamp(xp), hl["poll"], "sondages", POLL)]
    labels += [(clamp(vx), hl["venues"][v], v.capitalize(), MARKET) for v, vx in venue_x.items()]
    labels.sort(key=lambda t: t[0])
    for i in range(1, len(labels)):   # spread overlapping label centres apart along the axis
        if labels[i][0] - labels[i - 1][0] < 220:
            labels[i] = (labels[i - 1][0] + 220,) + labels[i][1:]
    for lx, val, label, col in labels:
        ax.text(lx, 352, fr_pct(val), fontsize=44 if len(labels) > 2 else 52, fontweight="bold", color=col, ha="center", va="center")
        ax.text(lx, 405, label, fontsize=19, color=MUTED, ha="center", va="center")
    for v in (0, 50, 100):
        ax.text(px(v), 522, str(v), fontsize=17, color=FAINT, ha="center", va="center")
    ax.plot([80, 1120], [566, 566], color=RULE, lw=2)
    ax.text(80, 596, "Données du " + fr_date(hl["updated"]), fontsize=20, color=MUTED, va="center")
    fig.savefig(path, format="png", dpi=100, facecolor=BG, metadata={"Software": None})
    plt.close(fig)

def write_blackout_image(fr, path):
    """og-image.png during an election-silence period: the legal notice, no candidate figures. Same palette as
    write_og_image() (kept separate: this card has no chart, so it doesn't share layout with it)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    BG, INK, MUTED, ORANGE = "#EEF0F4", "#161922", "#5A6071", "#A15F00"
    fig = plt.figure(figsize=(12, 6.3), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1200); ax.set_ylim(630, 0); ax.axis("off")
    ax.plot(80, 72, "o", ms=14, color="#3446A6"); ax.plot(106, 72, "D", ms=11, color="#0B8474")
    ax.text(132, 72, "L'Écart", fontsize=30, fontweight="bold", color=INK, va="center")
    ax.plot([80, 1120], [140, 140], color=ORANGE, lw=5, solid_capstyle="round")
    ax.text(80, 236, fr["blackoutTitle"], fontsize=44, fontweight="bold", color=INK, va="center")
    body = re.sub(r"<[^>]+>", "", fr["blackoutMeta"])   # plain text: this card has no link to follow
    ax.text(80, 340, "\n".join(textwrap.wrap(body, 58)), fontsize=21, color=MUTED, va="center", linespacing=1.7)
    fig.savefig(path, format="png", dpi=100, facecolor=BG, metadata={"Software": None})
    plt.close(fig)

def restamp_version(path, updated):
    """candidat.html and second-tour.html carry no STATIC/META markers (generic, parameterised pages): only their
    <meta name="data-version"> needs a daily refresh, so js/pages-common.js can cache-bust data.json and i18n/*.json."""
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    page = raw.replace("\r\n", "\n")
    page = fill(page, r'(<meta name="data-version" content=")([^"]*)(")', updated)
    return page.replace("\n", eol)

def build_outputs(data, history_rows, history, liquidity_rows, tmp):
    """Everything main() publishes, written into the temporary folder `tmp`: {final path: temporary path}."""
    hl = headline(data)
    hl["figs"] = fr_figures(data)
    fr = {k: fill_figures(v, hl["figs"]) for k, v in french_strings().items() if isinstance(v, str)}
    blackout = in_blackout(load_config())
    mkt_txt = ", ".join(f"{v} {p:.1f}%" for v, p in hl["venues"].items())
    print(f"Headline: {hl['name']}, polls {hl['poll']:.1f}%, markets {mkt_txt}"
          + (" -- election-silence period active: the homepage shows the legal notice instead" if blackout else ""))
    out = {}
    def stage(final, text=None, writer=None):
        t = pathlib.Path(tmp) / str(len(out))
        if writer: writer(t)
        else: t.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        out[final] = t
    stage(ROOT / "data.json", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    stage(HISTORY, csv_text(["date", "candidate", "venue", "win", "qual"],
                             [[r["date"], r["candidate"], r["venue"], r["win"], r["qual"]] for r in history_rows], "\r\n"))
    stage(LIQUIDITY, csv_text(["date", "venue", "candidate", "market", "volume", "liquidity"],
                               [[r["date"], r["venue"], r["candidate"], r["market"], r["volume"], r["liquidity"]] for r in liquidity_rows], "\r\n"))
    stage(POLLS_AVERAGE, csv_text(["week", "candidate", "average", "scenarios"], polls_average_rows(history)))
    stage(INDEX, render_index(hl, fr, blackout))
    stage(CANDIDAT, restamp_version(CANDIDAT, hl["updated"]))
    stage(SECOND_TOUR, restamp_version(SECOND_TOUR, hl["updated"]))
    stage(OG_IMAGE, writer=lambda t: write_blackout_image(fr, t) if blackout else write_og_image(hl, t))
    return out

def fetch_venue_polymarket(previous_markets):
    """(candidates, venue info) for Polymarket this run, or None if the fetch or its sanity checks failed."""
    label = "Polymarket"
    try:
        (win, win_stats, liq_win), (qual, qual_stats, liq_qual) = market_prices(WIN_SLUG), market_prices(QUAL_SLUG)
        print("Unmatched market names (not in FAMILY):", [n for n in win if n not in FAMILY])
        print("FAMILY names with no market:", [n for n in FAMILY if n not in win])
        candidates = build_candidates_polymarket(win, qual, liq_win, liq_qual)
        if not candidates: raise ValueError("no market name matched FAMILY")
        problems = validate_venue(candidates, win_stats["sum"], previous_markets, "polymarket", label)
        if problems: raise ValueError("; ".join(problems))
        info = {"snapshot": datetime.date.today().isoformat(), "stale": False,
                "volume": {"win": win_stats["volume"], "qual": qual_stats["volume"]},
                "liquidity": {"win": win_stats["liquidity"], "qual": qual_stats["liquidity"]},
                "winSum": win_stats["sum"], "qualSum": qual_stats["sum"],
                "thin": thin_flags(win_stats["volume"], qual_stats["volume"])}
        return candidates, info
    except Exception as e:
        print(f"{label} fetch failed, marking stale:", e)
        return None

def fetch_venue_kalshi(previous_markets):
    """(candidates, venue info) for Kalshi this run, or None if the fetch or its sanity checks failed."""
    label = "Kalshi"
    try:
        win, stats, liq_win = kalshi_win_prices()
        candidates = build_candidates_kalshi(win, liq_win)
        if not candidates: raise ValueError("no Kalshi market matched FAMILY")
        problems = validate_venue(candidates, stats["sum"], previous_markets, "kalshi", label)
        if problems: raise ValueError("; ".join(problems))
        info = {"snapshot": datetime.date.today().isoformat(), "stale": False, "volume": {"win": stats["volume"]},
                "liquidity": {"win": stats["liquidity"]}, "winSum": stats["sum"], "thin": thin_flags(stats["volume"])}
        return candidates, info
    except Exception as e:
        print(f"{label} fetch failed, marking stale:", e)
        return None

def fetch_ballot(previous_ballot):
    """(candidates, ballot info) for Kalshi's KXFRPRESBALLOT this run, or None if the fetch or its sanity check
    failed. Independent of the win/qual venues: a failure here never affects them or aborts the run, it just
    leaves the "on the ballot" section stale or (if there is no previous snapshot either) absent."""
    label = "Kalshi (on-the-ballot)"
    try:
        price, stats, liq = kalshi_ballot_prices()
        candidates = build_ballot(price, liq)
        if not candidates: raise ValueError("no Kalshi ballot market matched FAMILY")
        problems = validate_venue(candidates, stats["sum"], None, "ballot", label, check_sum=False)
        if problems: raise ValueError("; ".join(problems))
        info = {"snapshot": datetime.date.today().isoformat(), "stale": False, "volume": stats["volume"],
                "liquidity": stats["liquidity"], "sum": stats["sum"], "thin": thin_flags(stats["volume"])["win"]}
        return candidates, info
    except Exception as e:
        print(f"{label} fetch failed, marking stale:", e)
        return None

def stale_venue_prices(previous_markets, venue):
    """This venue's last-known {name: {win[, qual]}}, read back out of yesterday's merged candidate list, for when
    today's fetch failed or didn't pass validate_venue()."""
    return {c["c"]: c["venues"][venue] for c in previous_markets.get("candidates", []) if venue in c.get("venues", {})}

def run(reuse_markets=False):
    today = datetime.date.today().isoformat()
    data_path = ROOT / "data.json"
    previous = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}
    previous_markets = previous.get("markets") or {}
    polls, pairs, trend, history = load_polls()
    history_rows = read_history_rows()
    liquidity_rows = read_liquidity_rows()

    # Each venue is fetched and validated independently; one failing keeps the other and falls back to that venue's
    # own previous snapshot, marked stale, rather than aborting the whole run. --reuse-markets only forces this
    # fallback for Polymarket (blocked in some countries, e.g. France); Kalshi is always fetched fresh.
    fetched = {"polymarket": None if reuse_markets else fetch_venue_polymarket(previous_markets),
               "kalshi": fetch_venue_kalshi(previous_markets)}
    venues, venue_candidates, effective_prices = {}, {}, {}
    for name, result in fetched.items():
        if result:
            candidates, info = result
            venues[name], venue_candidates[name], effective_prices[name] = info, candidates, candidates
        elif previous_markets.get("venues", {}).get(name):
            venues[name] = dict(previous_markets["venues"][name], stale=True)
            effective_prices[name] = stale_venue_prices(previous_markets, name)
            print(f"{name.capitalize()}: no fresh data, reusing the snapshot of {venues[name]['snapshot']} (marked stale)")
    if not venues:
        print("VALIDATION FAILED, nothing was written:\n  - no venue (Polymarket or Kalshi) produced usable prices, "
              "and no previous snapshot to fall back to", file=sys.stderr)
        raise SystemExit(1)
    markets = {"snapshot": today, "source": ", ".join(v.capitalize() for v in venues), "candidates": merge_candidates(effective_prices),
               "venues": venues, "thinThreshold": THIN_MARKET_VOLUME}

    # "On the ballot" (Kalshi KXFRPRESBALLOT): independent of win/qual, a separate small indicator (see fetch_ballot()).
    ballot_result = fetch_ballot(previous_markets.get("ballot"))
    ballot_candidates = None
    if ballot_result:
        ballot_candidates, ballot_info = ballot_result
        markets["ballot"] = {**ballot_info, "candidates": [{"c": n, **p} for n, p in sorted(ballot_candidates.items())]}
    elif previous_markets.get("ballot"):
        markets["ballot"] = dict(previous_markets["ballot"], stale=True)
        print(f"Kalshi (on-the-ballot): no fresh data, reusing the snapshot of {markets['ballot']['snapshot']} (marked stale)")

    if venue_candidates: history_rows = history_with_today(history_rows, today, venue_candidates)
    if venue_candidates or ballot_candidates:
        liquidity_rows = liquidity_with_today(liquidity_rows, today, venue_candidates, ballot_candidates)

    weekly = weekly_series(history, history_rows)
    sim, avg = page_views(polls, pairs)
    data = {"updated": today, "polls": slim_polls(polls), "avg": avg, "sim": sim, "trend": trend, "weekly": weekly, "markets": markets, "pairs": pairs}
    problems = validate_polls(data, previous)
    if problems:
        print("VALIDATION FAILED, nothing was written:", *problems, sep="\n  - ", file=sys.stderr)
        raise SystemExit(1)
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        staged = build_outputs(data, history_rows, history, liquidity_rows, tmp)
        for final, t in staged.items(): os.replace(t, final)
    print(f"OK: {len(polls)} polls, {len(markets['candidates'])} market candidates across {', '.join(venues)}, {len(staged)} files written")

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reuse-markets", action="store_true", help="skip Polymarket (blocked in some countries, e.g. France) and keep its last snapshot; Kalshi is still fetched fresh")
    run(ap.parse_args(argv).reuse_markets)

if __name__ == "__main__":
    main()
