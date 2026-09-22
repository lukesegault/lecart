import hashlib, json, pathlib, shutil, urllib.error

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


FILES = ("data.json", "index.html", "og-image.png", "data/market_history.csv", "data/polls_average.csv")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of the published files, and the pipeline pointed at it with fake network data."""
    root = pathlib.Path(b.ROOT)
    for rel in FILES + ("i18n/fr.json",):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy(root / rel, tmp_path / rel)
    for name, rel in (("ROOT", ""), ("INDEX", "index.html"), ("OG_IMAGE", "og-image.png"), ("HISTORY", "data/market_history.csv"),
                      ("POLLS_AVERAGE", "data/polls_average.csv")):
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
    rows = (root / "data/market_history.csv").read_text(encoding="utf-8").splitlines()
    b.run()   # a second run the same day does not duplicate that day's history rows
    assert (root / "data/market_history.csv").read_text(encoding="utf-8").splitlines() == rows
