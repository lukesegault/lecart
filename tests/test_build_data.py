import hashlib, json, pathlib, re, shutil, urllib.error

import pytest

import build_data as b
from fixtures import PAIRS, POLLS, TODAY, csv_rows, market

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

def data(names=("Marine Le Pen", "Édouard Philippe"), n_polls=50, win=40.0):
    return {"markets": {"candidates": [{"c": n, "f": "x", "win": win, "qual": 50.0} for n in names]}, "polls": [{}] * n_polls}


def test_validate_accepts_normal_data():
    assert b.validate(data(), data(), win_sum=100) == []


@pytest.mark.parametrize("bad", [-0.1, 100.5, 250])
def test_validate_rejects_prices_outside_0_100(bad):
    assert any("out of range" in p for p in b.validate(data(win=bad), data(), win_sum=100))


@pytest.mark.parametrize("total,ok", [(84.9, False), (85, True), (115, True), (115.1, False), (290, False)])
def test_validate_winner_sum(total, ok):
    assert (b.validate(data(), data(), win_sum=total) == []) is ok


def test_validate_rejects_a_disappeared_candidate():
    problems = b.validate(data(names=("Marine Le Pen",)), data(), win_sum=100)
    assert problems == ["candidates missing from the markets: Édouard Philippe"]


def test_validate_poll_count_drop():
    assert b.validate(data(n_polls=40), data(n_polls=50), 100) == []            # exactly -20%: allowed
    assert any("poll count" in p for p in b.validate(data(n_polls=39), data(n_polls=50), 100))
    assert b.validate(data(n_polls=5), {}, 100) == []                            # no previous file: nothing to compare with


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
    cands = b.build_candidates(win, qual)
    assert [(c["c"], c["qual"]) for c in cands] == [("Marine Le Pen", 89.0), ("Édouard Philippe", 0)]   # unknown name skipped, missing price 0


def test_parse_event_rejects_an_empty_response():
    with pytest.raises(ValueError):
        b.parse_event([])
    with pytest.raises(ValueError):
        b.parse_event([{"markets": [{"groupItemTitle": "X", "outcomePrices": "[]"}]}])


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


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the published files, and the pipeline pointed at it with fake network data."""
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
    monkeypatch.setattr(b, "load_polls", lambda: (fake * 14, PAIRS, prev["trend"], history))   # 42 polls: within 20% of yesterday's 50
    prev["names"] = [c["c"] for c in prev["markets"]["candidates"]]
    return tmp_path, prev["names"]


def test_failed_validation_leaves_every_file_untouched(sandbox, monkeypatch):
    root, names = sandbox
    before = {f: sha(root / f) for f in FILES}
    monkeypatch.setattr(b, "market_prices", lambda slug: ({n: 150 / len(names) for n in names}, {"volume": 1, "sum": 150.0}))
    with pytest.raises(SystemExit) as e:
        b.run()
    assert e.value.code == 1
    assert {f: sha(root / f) for f in FILES} == before
    assert [p.name for p in root.iterdir() if p.is_dir() and p.name not in ("data", "i18n")] == []   # temp folder cleaned up


def test_successful_run_writes_everything_and_is_idempotent(sandbox, monkeypatch):
    root, names = sandbox
    monkeypatch.setattr(b, "market_prices", lambda slug: ({n: 100 / len(names) for n in names}, {"volume": 123456, "sum": 100.0}))
    b.run()
    d = json.loads((root / "data.json").read_text(encoding="utf-8"))
    assert d["updated"] == b.datetime.date.today().isoformat() and d["markets"]["volume"]["win"] == 123456
    assert d["pairs"] == PAIRS   # written verbatim by run(), same as pairs_of() computes
    assert f'name="data-version" content="{d["updated"]}"' in (root / "index.html").read_text(encoding="utf-8")
    assert f'name="data-version" content="{d["updated"]}"' in (root / "candidat.html").read_text(encoding="utf-8")
    assert f'name="data-version" content="{d["updated"]}"' in (root / "second-tour.html").read_text(encoding="utf-8")
    rows = (root / "data/market_history.csv").read_text(encoding="utf-8").splitlines()
    b.run()   # a second run the same day does not duplicate that day's history rows
    assert (root / "data/market_history.csv").read_text(encoding="utf-8").splitlines() == rows


def test_run_during_blackout_publishes_the_legal_notice_not_the_candidate(sandbox, monkeypatch):
    root, names = sandbox
    monkeypatch.setattr(b, "market_prices", lambda slug: ({n: 100 / len(names) for n in names}, {"volume": 123456, "sum": 100.0}))
    monkeypatch.setattr(b, "in_blackout", lambda config: True)
    b.run()
    page = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="blackoutNotice" class="sp-blackout">' in page and 'id="mainContent" hidden>' in page
    h1 = re.search(r'<h1 class="sp-h1" id="siteH1">(.*?)</h1>', page, re.S).group(1)
    desc = re.search(r'<meta name="description" content="(.*?)">', page, re.S).group(1)
    hl_name = b.headline(json.loads((root / "data.json").read_text(encoding="utf-8")))["name"]
    assert hl_name not in h1 and hl_name not in desc
    assert (root / "og-image.png").stat().st_size > 0   # the neutral card, not the candidate chart
