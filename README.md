# L'Écart

Prediction markets vs polls, French presidential election 2027. Bilingual FR/EN, static site (vanilla HTML/CSS/JS, no build step).
Polls: [MieuxVoter/presidentielle2027](https://github.com/MieuxVoter/presidentielle2027) (MIT). Market prices are shown as data only; no affiliation with any platform.

## What it does

For each candidate the site shows the chance of winning (or reaching the runoff) according to the markets and according to the polls,
and the gap between the two. The poll side is a Monte Carlo simulation: draw a recent poll, add polling error, take the top two,
draw the runoff. Everything computed lives in `scripts/build_data.py`; the pages only display it.

Three pages, sharp/mint design (Archivo + Instrument Serif):

- `index.html` — homepage: headline, the markets-vs-polls-over-time chart, the full candidate comparison table, Method, About.
- `candidat.html?c=<name>` — one candidate: the same over-time chart, qualification/win numbers, first-round trend, the gap isolated.
- `second-tour.html` — every tested runoff pairing, the common candidate always on the same side.

## Files

| Path | Role |
| --- | --- |
| `index.html`, `candidat.html`, `second-tour.html` | The three pages. `index.html`'s markup between `STATIC`/`META` markers is rewritten by the pipeline for crawlers (edit the copy in `i18n/fr.json`, not there); the other two just get their `data-version` meta restamped daily. |
| `css/pages.css` | The site's only stylesheet. Design tokens (colours, fonts, spacing) are at the top. |
| `js/pages-common.js` | Shared `Lecart` helpers: language, data/i18n fetch, figure filling, nav/footer, formatting. No simulation. |
| `js/over-time-chart.js` | The market-vs-poll-implied-win-probability chart shared by index.html and candidat.html (candidate selector, 1M/3M/6M/All, PNG export). |
| `js/index.js`, `js/candidat.js`, `js/second-tour.js` | Per-page rendering and interaction. No simulation. |
| `i18n/fr.json`, `i18n/en.json` | Every user-facing string. `{{name}}` slots are figures filled from data (dates, counts, volumes); `{name}` slots are filled by `Lecart.tf()`. |
| `data.json` | Everything the pages display, minified. Written by the pipeline. |
| `data/market_history.csv`, `data/polls_average.csv` | Downloadable data (linked from the About section). `data/events.json` lists the events marked on the time charts. |
| `config.json` | Election-silence periods (see below). Read by both `js/pages-common.js` and `scripts/build_data.py`. |
| `scripts/build_data.py` | The daily pipeline. `scripts/backfill_history.py` is the one-off that rebuilt the market history. |
| `scripts/check_site.py` | Browser check (see below). `tests/` holds the pytest suite. |
| `fonts/` | Self-hosted Schibsted Grotesk/Spectral (legal pages) and Archivo/Instrument Serif (the three pages). |
| `analytics.js`, `changelog.html`, `confidentialite.html`, `mentions-legales.html`, `legal.css` | Cookie-free analytics with opt-out, legal pages. |

## Run it locally

```bash
python -m http.server 8000     # then open http://localhost:8000/
```

The page fetches its data, so open it through a server, not as a file.

Refresh the data (Python 3.12+):

```bash
pip install -r requirements.txt
python scripts/build_data.py                    # polls + Polymarket + Kalshi + everything below
python scripts/build_data.py --reuse-markets    # where Polymarket is blocked (e.g. France): keeps its last snapshot; Kalshi is still fetched fresh
```

## The daily pipeline

`.github/workflows/update-data.yml` runs every day at 05:00 UTC (and on demand): tests, then `scripts/build_data.py`, then commits what changed.

1. Downloads the poll CSV and fetches two independent prediction-market venues: Polymarket (winner and runoff-qualification events, plus per-candidate volume/liquidity) and Kalshi (winner event and, separately, its candidacy-confirmation "on the ballot" indicator; per-candidate volume/open interest). Retries with backoff on network errors, 429 and 5xx. Each venue's price stands on its own everywhere downstream — the pipeline never computes a mean across venues.
2. Runs the simulation for every view the page has (win/runoff × low/mid/high uncertainty) and the weekly series of the time chart.
3. `validate_venue()` refuses to publish a venue's prices if one is outside 0-100, its winner prices do not add up to 85-115% (skipped for the ballot indicator, which isn't a single-winner market), or a candidate it priced yesterday has vanished; `validate_polls()` separately refuses to publish at all if the poll count dropped by more than 20%. One venue (or the ballot indicator) failing its own check falls back to its last snapshot, marked stale, rather than blocking the run — the run only aborts if neither win/qual venue has usable data. Reasons are printed and a genuine abort exits non-zero.
4. Only when everything passed, `data.json`, all three CSVs (market prices, market liquidity, poll averages), the static text of `index.html`, the `data-version` meta of all three pages
   (the cache key of `data.json`/`i18n/*.json`) and `og-image.png` are replaced. Any earlier failure leaves yesterday's files untouched, and the workflow commits nothing.

If `data.json` is more than two days old, the page shows a discreet notice that the data may be stale.

`config.json` lists the election-silence periods (French Act No. 77-808 of 19 July 1977: no poll publication the
day before or the day of each round). During one of them, all three pages show a legal notice instead of any
poll-derived chance or market price; `Lecart.checkBlackout()` in `js/pages-common.js` checks the current time
against it client-side, and `scripts/build_data.py`'s `in_blackout()` mirrors that server-side for index.html's
crawler-visible layer and `og-image.png`. Append `?blackout=1` (or `?blackout=0` to force it off) to any page's URL
to preview the notice without waiting for a real period.

## Tests and checks

```bash
python -m pytest -q                      # simulation reference values, validation, parsing, retries, all-or-nothing run, blackout periods
pip install -r requirements-dev.txt
python -m playwright install chromium
python scripts/check_site.py             # loads all three pages, clicks every control, FR/EN, 1280/390 px, light/dark, blackout mode, fails on console errors
```

`check_site.py` answers the analytics requests locally, so a check run is not counted. The simulation reference
(`tests/reference_simulation.json`) is deliberate: to accept an intended change of the model, delete it and run pytest once.

## Content rules

- Never link to Polymarket or Kalshi, or encourage betting (Polymarket is not authorised in France): prices are data.
- No blended figure across market venues, anywhere: each of Polymarket's and Kalshi's own prices stands on its own in the data, the page and the CSVs; where both price the same event, show both (or the range they bound), never a mean.
- Every user-facing string exists in FR and EN. No em-dashes in page copy.
- French poll law: polls may not be published the day before and the day of each round; enforced by the blackout
  switch above (`config.json`). Add a new election's periods there (and matching cron entries in
  `.github/workflows/update-data.yml`) well ahead of time.
