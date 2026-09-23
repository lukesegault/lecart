import hashlib, json, pathlib, re, shutil, urllib.error

import pytest

import build_data as b
from fixtures import PAIRS, POLLS, TODAY, csv_rows, kalshi_candlesticks, kalshi_markets_page, market

HERE = pathlib.Path(__file__).parent
REFERENCE = HERE / "reference_simulation.json"
RUNS = 4000


# ---- simulation -------------------------------------------------------------------------

def rounded(sim):
    return {c: {k: round(v, 6) for k, v in r.items()} for c, r in sim.items()}


def test_simulation_is_deterministic():
    assert b.simulate(POLLS, PAIRS, runs=RUNS) == b.simulate(POLLS, PAIRS, runs=RUNS)


def test_simulation_matches_saved_reference():
    """The reference was produced by this code once; a change here means every published probability changes.
    To accept an intended change, delete tests/reference_simulation.json and run pytest again."""
    got = {lvl: rounded(b.simulate(POLLS, PAIRS, b.LEVELS[lvl], runs=RUNS)) for lvl in b.LEVELS}
    if not REFERENCE.exists():
        REFERENCE.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert got == json.loads(REFERENCE.read_text(encoding="utf-8"))


def test_simulation_probabilities_are_sane():
    sim = b.simulate(POLLS, PAIRS, runs=RUNS)
    assert all(0 <= r["win"] <= r["qual"] <= 100 for r in sim.values())
    assert sim["Marine Le Pen"]["win"] > sim["Édouard Philippe"]["win"]


def test_prng_is_seeded():
    r1, r2 = b._rng(2027), b._rng(2027)
    assert [r1() for _ in range(5)] == [r2() for _ in range(5)]
    assert b._rng(2028)() != b._rng(2027)()


# ---- validation -------------------------------------------------------------------------

def prices(names=("Marine Le Pen", "Édouard Philippe"), win=40.0):
    return {n: {"win": win, "qual": 50.0} for n in names}


def prev_markets(names=("Marine Le Pen", "Édouard Philippe"), venue="polymarket"):
    return {"candidates": [{"c": n, "venues": {venue: {"win": 1, "qual": 1}}} for n in names]}


def test_validate_venue_accepts_normal_prices():
    assert b.validate_venue(prices(), win_sum=100, previous_markets=prev_markets(), venue="polymarket", label="Polymarket") == []


@pytest.mark.parametrize("bad", [-0.1, 100.5, 250])
def test_validate_venue_rejects_prices_outside_0_100(bad):
    problems = b.validate_venue(prices(win=bad), win_sum=100, previous_markets=None, venue="polymarket", label="Polymarket")
    assert any("out of range" in p for p in problems)


@pytest.mark.parametrize("total,ok", [(84.9, False), (85, True), (115, True), (115.1, False), (290, False)])
def test_validate_venue_winner_sum(total, ok):
    assert (b.validate_venue(prices(), win_sum=total, previous_markets=None, venue="polymarket", label="Polymarket") == []) is ok


def test_validate_venue_rejects_a_disappeared_candidate():
    problems = b.validate_venue(prices(names=("Marine Le Pen",)), 100, prev_markets(), "polymarket", "Polymarket")
    assert problems == ["candidates missing from Polymarket: Édouard Philippe"]


def test_validate_venue_ignores_candidates_missing_from_a_different_venue():
    # Édouard Philippe was only ever priced by Kalshi in the previous snapshot: Polymarket losing him isn't news
    problems = b.validate_venue(prices(names=("Marine Le Pen",)), 100, prev_markets(names=("Édouard Philippe",), venue="kalshi"), "polymarket", "Polymarket")
    assert problems == []


def test_validate_polls_count_drop():
    poll_data = lambda n: {"polls": [{}] * n}
    assert b.validate_polls(poll_data(40), poll_data(50)) == []            # exactly -20%: allowed
    assert any("poll count" in p for p in b.validate_polls(poll_data(39), poll_data(50)))
    assert b.validate_polls(poll_data(5), {}) == []                         # no previous file: nothing to compare with
    assert any("no poll" in p for p in b.validate_polls(poll_data(0), {}))


# ---- parsing ----------------------------------------------------------------------------

def test_parse_polls_handles_a_candidate_missing_from_a_poll():
    rows = csv_rows("p1", "2026-09-10", "1er Tour", {"Marine Le Pen": 30.0, "Jean-Luc Mélenchon": 17.0, "Édouard Philippe": 18.0})
    rows += csv_rows("p2", "2026-09-12", "1er Tour", {"Marine Le Pen": 32.0, "Édouard Philippe": 17.0})   # no Mélenchon
    rows += csv_rows("r1", "2026-09-11", "2eme Tour", {"Marine Le Pen": 53.0, "Édouard Philippe": 47.0})
    polls, pairs, trend, history = b.parse_polls(rows, today=TODAY)
    assert [p["id"] for p in polls] == ["p1", "p2"]
    assert "Jean-Luc Mélenchon" not in polls[1]["v"]
    slim = b.slim_polls(polls)                      # the page table has a Mélenchon column: the missing value is simply absent
    assert "Jean-Luc Mélenchon" not in slim[1]["v"] and slim[0]["v"]["Jean-Luc Mélenchon"] == 17.0
    sim, avg = b.page_views(polls, pairs)
    assert avg["Jean-Luc Mélenchon"][1] == 1 and avg["Marine Le Pen"][1] == 2
    assert set(sim) == {"low", "mid", "high"} and "Jean-Luc Mélenchon" in sim["mid"]
    assert pairs["Marine Le Pen|Édouard Philippe"] == [53.0, 1] and len(history["first"]) == 2


def test_parse_polls_drops_polls_older_than_the_window():
    rows = csv_rows("old", "2026-06-01", "1er Tour", {"Marine Le Pen": 30.0}) + csv_rows("new", "2026-09-10", "1er Tour", {"Marine Le Pen": 31.0})
    assert [p["id"] for p in b.parse_polls(rows, today=TODAY)[0]] == ["new"]


def test_parse_event_and_missing_runoff_price():
    win, stats = b.parse_event(market({"Marine Le Pen": 37.5, "Édouard Philippe": 23.5, "Someone Else": 5.0}))
    assert win == {"Marine Le Pen": 37.5, "Édouard Philippe": 23.5, "Someone Else": 5.0} and stats["volume"] == 1000000
    qual, _ = b.parse_event(market({"Marine Le Pen": 89.0}))                       # Philippe has no runoff market
    cands = b.build_candidates_polymarket(win, qual)
    assert cands["Marine Le Pen"]["qual"] == 89.0 and cands["Édouard Philippe"]["qual"] == 0   # missing price 0
    assert "Someone Else" not in cands   # unknown name skipped (not in FAMILY)


def test_parse_event_rejects_an_empty_response():
    with pytest.raises(ValueError):
        b.parse_event([])
    with pytest.raises(ValueError):
        b.parse_event([{"markets": [{"groupItemTitle": "X", "outcomePrices": "[]"}]}])


# ---- Kalshi -------------------------------------------------------------------------------

def test_kalshi_markets_pages_through_the_cursor(monkeypatch):
    pages = [kalshi_markets_page({"Marine Le Pen": 37.0}, cursor="p2"), kalshi_markets_page({"Édouard Philippe": 19.0}, cursor="")]
    calls = []
    def fake_get(path, **params):
        calls.append(params.get("cursor")); return pages.pop(0)
    monkeypatch.setattr(b, "kalshi_get", fake_get)
    markets = b.kalshi_markets("KXFRENCHPRES")
    assert [m["yes_sub_title"] for m in markets] == ["Marine Le Pen", "Édouard Philippe"]
    assert calls == [None, "p2"]   # first request has no cursor, second carries the one the first page returned


def test_kalshi_win_prices_parses_dollars_to_percent(monkeypatch):
    # volume_fp is per-market (like real Kalshi markets), so two markets at 250 contracts each sum to 500
    monkeypatch.setattr(b, "kalshi_markets", lambda series: kalshi_markets_page({"Marine Le Pen": 37.5, "Someone Else": 5.0}, volume_fp=250)["markets"])
    win, stats = b.kalshi_win_prices()
    assert win == {"Marine Le Pen": 37.5, "Someone Else": 5.0} and stats["volume"] == 500 and stats["sum"] == 42.5


def test_kalshi_win_prices_applies_the_alias_table(monkeypatch):
    monkeypatch.setattr(b, "KALSHI_ALIASES", {"J.-L. Mélenchon": "Jean-Luc Mélenchon"})
    monkeypatch.setattr(b, "kalshi_markets", lambda series: kalshi_markets_page({"J.-L. Mélenchon": 12.0})["markets"])
    win, _ = b.kalshi_win_prices()
    assert win == {"Jean-Luc Mélenchon": 12.0}


def test_kalshi_win_prices_rejects_a_response_with_no_priced_market(monkeypatch):
    monkeypatch.setattr(b, "kalshi_markets", lambda series: [{"yes_sub_title": "X", "last_price_dollars": None}])
    with pytest.raises(ValueError):
        b.kalshi_win_prices()


def test_build_candidates_kalshi_has_no_qual_field():
    # Kalshi's KXFRPRESBALLOT is candidacy confirmation, not runoff qualification (see the KALSHI_BASE comment):
    # Kalshi candidates never carry a "qual" key, unlike Polymarket's.
    cands = b.build_candidates_kalshi({"Marine Le Pen": 38.0, "Someone Else": 1.0})
    assert cands == {"Marine Le Pen": {"win": 38.0}}   # unknown name skipped, no "qual" key present


def test_kalshi_candlestick_prices_falls_back_to_bid_ask_midpoint_on_a_quiet_day(monkeypatch):
    monkeypatch.setattr(b, "kalshi_get", lambda path, **params: kalshi_candlesticks([(1700000000, 37.0), (1700086400, None)]))
    prices = b.kalshi_candlestick_prices("KXFRENCHPRES", "KXFRENCHPRES-27-MLEP", TODAY, TODAY)
    days = sorted(prices)
    assert prices[days[0]] == 37.0 and prices[days[1]] == 20.0   # (10 + 30) / 2 from the bid/ask fixture


# ---- merging venues -------------------------------------------------------------------------

def test_merge_candidates_means_the_venues_a_candidate_is_priced_on():
    # merge_candidates trusts its input to already be FAMILY-filtered (build_candidates_kalshi/_polymarket do that);
    # both names here must be real FAMILY entries
    merged = b.merge_candidates({"polymarket": {"Marine Le Pen": {"win": 36.0, "qual": 89.0}},
                                  "kalshi": {"Marine Le Pen": {"win": 38.0}, "Jordan Bardella": {"win": 5.0}}})
    by_name = {c["c"]: c for c in merged}
    assert by_name["Marine Le Pen"]["win"] == 37.0 and by_name["Marine Le Pen"]["qual"] == 89.0   # mean of 36 and 38
    assert set(by_name["Marine Le Pen"]["venues"]) == {"polymarket", "kalshi"}


def test_merge_candidates_handles_a_candidate_on_one_venue_only():
    merged = b.merge_candidates({"polymarket": {}, "kalshi": {"Marine Le Pen": {"win": 38.0}}})
    assert merged == [{"c": "Marine Le Pen", "f": b.FAMILY["Marine Le Pen"], "win": 38.0, "qual": 0, "venues": {"kalshi": {"win": 38.0}}}]


# ---- election-silence period --------------------------------------------------------------

CONFIG = {"blackout": {"timezone": "Europe/Paris", "periods": [
    {"start": "2027-04-17T00:00", "end": "2027-04-18T20:00"}, {"start": "2027-05-01T00:00", "end": "2027-05-02T20:00"}]}}


@pytest.mark.parametrize("iso,expect", [
    ("2027-04-16T21:59:00+00:00", False),   # just before period 1 (Paris 00:00 = UTC 22:00, CEST)
    ("2027-04-16T22:00:00+00:00", True),    # start, inclusive
    ("2027-04-17T12:00:00+00:00", True),    # well inside
    ("2027-04-18T17:59:00+00:00", True),    # just before period 1 end
    ("2027-04-18T18:00:00+00:00", False),   # end, exclusive
    ("2027-04-30T22:00:00+00:00", True),    # period 2 start
    ("2027-05-02T18:00:00+00:00", False),   # period 2 end, exclusive
    ("2026-09-22T12:00:00+00:00", False),   # today: nowhere near either period
])
def test_in_blackout_boundaries(iso, expect):
    assert b.in_blackout(CONFIG, b.datetime.datetime.fromisoformat(iso)) is expect


def test_in_blackout_with_no_configured_periods():
    assert b.in_blackout({"blackout": {"periods": []}}) is False
    assert b.in_blackout({}) is False


def test_config_json_is_the_live_config():
    """load_config() reads the real config.json (not a fixture): keep this in step with js/pages-common.js's copy."""
    cfg = b.load_config()
    assert cfg["blackout"]["timezone"] == "Europe/Paris"
    assert len(cfg["blackout"]["periods"]) == 2
    for p in cfg["blackout"]["periods"]: assert p["start"] < p["end"]


def blackout_fr():
    hl = {"name": "Marine Le Pen", "poll": 85.0, "market": 38.0, "updated": "2027-04-17", "figs": {"upd": "17 avril 2027", "year": "2027", "snap": "x", "n": "1", "from": "x", "to": "x"}}
    fr = {k: b.fill_figures(v, hl["figs"]) for k, v in b.french_strings().items() if isinstance(v, str)}
    return fr, hl


def test_static_html_swaps_the_headline_for_the_legal_notice():
    fr, hl = blackout_fr()
    region = '<h1 class="sp-h1" id="siteH1">placeholder</h1><p data-i="dek">x</p>'
    normal = b.static_html(region, fr, hl, blackout=False)
    silent = b.static_html(region, fr, hl, blackout=True)
    assert "Marine Le Pen" in normal or "Le Pen" in normal   # the real headline sentence names the candidate
    assert fr["blackoutTitle"] in silent
    assert "Le Pen" not in silent and "Marine" not in silent


def test_meta_html_drops_the_figures_during_blackout():
    fr, hl = blackout_fr()
    page = "<title>L'Écart</title>"
    normal = b.meta_html(page, fr, hl, blackout=False)
    silent = b.meta_html(page, fr, hl, blackout=True)
    assert "38" in normal or "85" in normal   # the real description carries the poll/market figures
    assert "38" not in silent and "85" not in silent and "Le Pen" not in silent
    assert fr["blackoutMeta"] in silent


def test_toggle_blackout_markup_swaps_the_hidden_attribute():
    region = '<div id="blackoutNotice" class="sp-blackout" hidden>x</div><div id="mainContent">y</div>'
    assert b.toggle_blackout_markup(region, False) == region
    silent = b.toggle_blackout_markup(region, True)
    assert '<div id="blackoutNotice" class="sp-blackout">' in silent
    assert '<div id="mainContent" hidden>' in silent


def test_render_index_full_page_hides_the_candidate_during_blackout(sandbox):
    # the headline and meta description are where a figure would otherwise leak; the poll table's fixed column
    # headers ("Le Pen", "Philippe"...) are plain labels with no data next to them and are excluded from this check
    fr, hl = blackout_fr()
    page = b.render_index(hl, fr, blackout=True)
    h1 = re.search(r'<h1 class="sp-h1" id="siteH1">(.*?)</h1>', page, re.S).group(1)
    desc = re.search(r'<meta name="description" content="(.*?)">', page, re.S).group(1)
    assert fr["blackoutTitle"] in h1 and "Le Pen" not in h1
    assert fr["blackoutMeta"] in desc and "Le Pen" not in desc and "38" not in desc and "85" not in desc
    assert 'id="blackoutNotice" class="sp-blackout">' in page   # visible (no `hidden`) even before JS runs
    assert 'id="mainContent" hidden>' in page


# ---- network ----------------------------------------------------------------------------

class Resp:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return self.body.encode()


def test_get_retries_with_backoff(monkeypatch):
    calls, sleeps = [], []
    def flaky(req, timeout):
        calls.append(1)
        if len(calls) < 3: raise urllib.error.URLError("boom")
        return Resp("ok")
    monkeypatch.setattr(b.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(b.time, "sleep", sleeps.append)
    assert b.get("http://x") == "ok" and len(calls) == 3 and sleeps == [2.0, 4.0]


def test_get_gives_up_and_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    calls = []
    def down(req, timeout): calls.append(1); raise urllib.error.URLError("down")
    monkeypatch.setattr(b.urllib.request, "urlopen", down)
    with pytest.raises(urllib.error.URLError): b.get("http://x", tries=3)
    assert len(calls) == 3
    calls.clear()
    def notfound(req, timeout): calls.append(1); raise urllib.error.HTTPError("http://x", 404, "nf", {}, None)
    monkeypatch.setattr(b.urllib.request, "urlopen", notfound)
    with pytest.raises(urllib.error.HTTPError): b.get("http://x")
    assert len(calls) == 1


# ---- all-or-nothing run -----------------------------------------------------------------

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


FILES = ("data.json", "index.html", "candidat.html", "second-tour.html", "og-image.png", "data/market_history.csv", "data/polls_average.csv")


def default_polymarket(names):
    return lambda slug: ({n: 100 / len(names) for n in names}, {"volume": 123456, "sum": 100.0})


def default_kalshi(names):
    return lambda: ({n: 100 / len(names) for n in names}, {"volume": 65432, "sum": 100.0})


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the published files, and the pipeline pointed at it with fake network data for both venues
    (override b.market_prices / b.kalshi_win_prices in a test for non-default behaviour, e.g. a failing venue)."""
    root = pathlib.Path(b.ROOT)
    for rel in FILES + ("i18n/fr.json",):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy(root / rel, tmp_path / rel)
    for name, rel in (("ROOT", ""), ("INDEX", "index.html"), ("CANDIDAT", "candidat.html"), ("SECOND_TOUR", "second-tour.html"),
                      ("OG_IMAGE", "og-image.png"), ("HISTORY", "data/market_history.csv"), ("POLLS_AVERAGE", "data/polls_average.csv")):
        monkeypatch.setattr(b, name, tmp_path / rel if rel else tmp_path)
    today = b.datetime.date.today()
    fake = [dict(p, end=(today - b.datetime.timedelta(days=i)).isoformat()) for i, p in enumerate(POLLS)]
    history = {"first": [{"id": p["id"], "end": p["end"], "v": p["v"]} for p in fake], "runoff": []}
    prev = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    # tests must not depend on whether the real repo's data.json happens to have a previous venue snapshot at the
    # time they run (e.g. once Kalshi has been fetched for real, its "venues" entry sticks around): strip every
    # candidate's per-venue history so each test starts from "neither venue has a previous snapshot" and opts in
    # to a previous snapshot explicitly (an initial b.run() call) when that's the scenario it wants to cover.
    prev["markets"]["venues"] = {}
    for c in prev["markets"]["candidates"]: c["venues"] = {}
    (tmp_path / "data.json").write_text(json.dumps(prev), encoding="utf-8")
    monkeypatch.setattr(b, "load_polls", lambda: (fake * 14, PAIRS, prev["trend"], history))   # 42 polls: within 20% of yesterday's 50
    names = [c["c"] for c in prev["markets"]["candidates"]]
    monkeypatch.setattr(b, "market_prices", default_polymarket(names))
    monkeypatch.setattr(b, "kalshi_win_prices", default_kalshi(names))
    return tmp_path, names


def test_failed_validation_leaves_every_file_untouched(sandbox, monkeypatch):
    root, names = sandbox
    before = {f: sha(root / f) for f in FILES}
    # both venues fail their own sanity check this run, and the sandbox's data.json has no previous snapshot to
    # fall back to (it predates the venues schema): nothing for either venue to reuse, so the whole run aborts
    monkeypatch.setattr(b, "market_prices", lambda slug: ({n: 150 / len(names) for n in names}, {"volume": 1, "sum": 150.0}))
    monkeypatch.setattr(b, "kalshi_win_prices", lambda: ({n: 150 / len(names) for n in names}, {"volume": 1, "sum": 150.0}))
    with pytest.raises(SystemExit) as e:
        b.run()
    assert e.value.code == 1
    assert {f: sha(root / f) for f in FILES} == before
    assert [p.name for p in root.iterdir() if p.is_dir() and p.name not in ("data", "i18n")] == []   # temp folder cleaned up


def test_one_venue_failing_keeps_the_other_and_marks_it_stale(sandbox, monkeypatch):
    root, names = sandbox
    monkeypatch.setattr(b, "kalshi_win_prices", lambda: (_ for _ in ()).throw(ValueError("Kalshi is down")))
    b.run()   # does not raise: Polymarket alone is enough to publish
    d = json.loads((root / "data.json").read_text(encoding="utf-8"))
    assert d["markets"]["venues"]["polymarket"]["stale"] is False
    assert "kalshi" not in d["markets"]["venues"]   # never fetched successfully before either: simply absent, not stale
    assert all("kalshi" not in c["venues"] for c in d["markets"]["candidates"])


def test_a_previously_fetched_venue_that_now_fails_is_reused_and_marked_stale(sandbox, monkeypatch):
    root, names = sandbox
    b.run()   # first run: both venues fresh
    monkeypatch.setattr(b, "kalshi_win_prices", lambda: (_ for _ in ()).throw(ValueError("Kalshi is down")))
    b.run()   # second run: Kalshi fails, but it has yesterday's (today's, in test time) snapshot to fall back to
    d = json.loads((root / "data.json").read_text(encoding="utf-8"))
    assert d["markets"]["venues"]["kalshi"]["stale"] is True
    assert d["markets"]["venues"]["polymarket"]["stale"] is False
    assert all("kalshi" in c["venues"] for c in d["markets"]["candidates"] if c["c"] in names)


def test_successful_run_writes_everything_and_is_idempotent(sandbox, monkeypatch):
    root, names = sandbox
    b.run()
    d = json.loads((root / "data.json").read_text(encoding="utf-8"))
    assert d["updated"] == b.datetime.date.today().isoformat()
    assert d["markets"]["venues"]["polymarket"]["volume"]["win"] == 123456
    assert d["markets"]["venues"]["kalshi"]["volume"]["win"] == 65432
    by_name = {c["c"]: c for c in d["markets"]["candidates"]}
    # both venue mocks split 100% evenly across all `names`, so each candidate's mean win is 100 / len(names)
    assert by_name[names[0]]["win"] == round(100 / len(names), 1) and set(by_name[names[0]]["venues"]) == {"polymarket", "kalshi"}
    assert d["pairs"] == PAIRS   # written verbatim by run(), same as pairs_of() computes
    assert f'name="data-version" content="{d["updated"]}"' in (root / "index.html").read_text(encoding="utf-8")
    assert f'name="data-version" content="{d["updated"]}"' in (root / "candidat.html").read_text(encoding="utf-8")
    assert f'name="data-version" content="{d["updated"]}"' in (root / "second-tour.html").read_text(encoding="utf-8")
    hist = (root / "data/market_history.csv").read_text(encoding="utf-8").splitlines()
    assert hist[0] == "date,candidate,venue,win,qual"
    assert sum(1 for r in hist if r.startswith(f"{d['updated']},") and ",kalshi," in r) == len(names)
    b.run()   # a second run the same day does not duplicate that day's history rows
    assert (root / "data/market_history.csv").read_text(encoding="utf-8").splitlines() == hist


def test_run_during_blackout_publishes_the_legal_notice_not_the_candidate(sandbox, monkeypatch):
    root, names = sandbox
    monkeypatch.setattr(b, "in_blackout", lambda config: True)
    b.run()
    page = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="blackoutNotice" class="sp-blackout">' in page and 'id="mainContent" hidden>' in page
    h1 = re.search(r'<h1 class="sp-h1" id="siteH1">(.*?)</h1>', page, re.S).group(1)
    desc = re.search(r'<meta name="description" content="(.*?)">', page, re.S).group(1)
    hl_name = b.headline(json.loads((root / "data.json").read_text(encoding="utf-8")))["name"]
    assert hl_name not in h1 and hl_name not in desc
    assert (root / "og-image.png").stat().st_size > 0   # the neutral card, not the candidate chart
