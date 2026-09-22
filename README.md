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
python scripts/build_data.py                    # polls + Polymarket + everything below
python scripts/build_data.py --reuse-markets    # where Polymarket is blocked (e.g. France): keeps the last market snapshot
```

## The daily pipeline

`.github/workflows/update-data.yml` runs every day at 05:00 UTC (and on demand): tests, then `scripts/build_data.py`, then commits what changed.

1. Downloads the poll CSV and the two Polymarket events (retrying with backoff on network errors, 429 and 5xx).
2. Runs the simulation for every view the page has (win/runoff × low/mid/high uncertainty) and the weekly series of the time chart.
3. `validate()` refuses to publish if a price is outside 0-100, the winner prices do not add up to 85-115%, a candidate present yesterday has vanished,
   or the poll count dropped by more than 20%. The reasons are printed and the run exits non-zero.
4. Only when everything passed, `data.json`, both CSVs, the static text of `index.html`, the `data-version` meta of all three pages
   (the cache key of `data.json`/`i18n/*.json`) and `og-image.png` are replaced. Any earlier failure leaves yesterday's files untouched, and the workflow commits nothing.

If `data.json` is more than two days old, the page shows a discreet notice that the data may be stale.

## Tests and checks

```bash
python -m pytest -q                      # simulation reference values, validation, parsing, retries, all-or-nothing run
pip install -r requirements-dev.txt
python -m playwright install chromium
python scripts/check_site.py             # loads all three pages, clicks every control, FR/EN, 1280/390 px, light/dark, fails on console errors
```

`check_site.py` answers the analytics requests locally, so a check run is not counted. The simulation reference
(`tests/reference_simulation.json`) is deliberate: to accept an intended change of the model, delete it and run pytest once.

## Content rules

- Never link to Polymarket or encourage betting (not authorised in France): prices are data.
- Every user-facing string exists in FR and EN. No em-dashes in page copy.
- French poll law: polls may not be published the day before and the day of each round; a blackout switch is planned before April 2027.
