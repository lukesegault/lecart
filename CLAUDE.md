# L'Écart: brief for Claude Code

## What this is
A public, bilingual (FR/EN) page comparing prediction-market odds with opinion polls for the
2027 French presidential election. Core question: "Do markets see what the polls miss?"
Owner: Vikander. Audience: French journalists, policy people, curious readers.

## Current state
File structure (vanilla HTML/CSS/JS, no build step, no framework):
- `index.html`: markup and the static French block for crawlers (between `<!--STATIC-START-->`/`END` and `<!--META-START-->`/`END`; both are rewritten by the pipeline). Has the CSP meta tag: scripts from self and gc.zgo.at, styles and fonts from self; do not add inline `<script>` or `<style>` blocks.
- `css/styles.css`: all styles; design tokens (colours, fonts, spacing, radii) at the top of the file. `js/app.js`: rendering and interaction only. `i18n/fr.json`, `i18n/en.json`: every user-facing string.
- `data.json` (minified, written by the pipeline only): `updated`, `polls` (fields the table shows), `avg`, `sim` (win/qual per candidate for low/mid/high uncertainty), `trend`, `weekly`, `markets`. Loaded with `?v=<updated>` taken from `<meta name="data-version">`.
- `scripts/build_data.py`: the daily pipeline and **the only place the Monte Carlo lives** (`simulate()`, `LEVELS`, `page_views()`, `weekly_series()`). The page never simulates: to change a model parameter change it there, and the page follows. All-or-nothing: outputs are built in memory and a temp folder, `validate()` checks them (prices 0-100, winner sum 85-115%, no vanished candidate, poll count not down more than 20%), then they replace the real files; any failure exits non-zero and changes nothing. `--reuse-markets` for machines where Polymarket is blocked (France).
- `tests/` (pytest, `python -m pytest -q`, run by the workflow before the build) and `scripts/check_site.py` (Playwright, clicks every control in FR and EN, fails on console errors; run it after any front-end change).
- `scripts/backfill_history.py`: one-off (already run, 21 Sept 2026) daily "win" history of FAMILY candidates since the market opened (14 Nov 2025) into `data/market_history.csv`; `qual` is empty before 21 Sept 2026. Polymarket is blocked from France, so run it on a GitHub runner.
- `.github/workflows/update-data.yml`: daily at 05:00 UTC, 10 minute timeout, concurrency group, pip cache, pinned `requirements.txt`; tests, build, commit; nothing is committed after a failure.
- Section "Marchés et sondages dans le temps" (`renderDv()`): one chart per candidate (pills, 1M/3M/6M/Tout, shaded écart, hover readout, PNG export built as one SVG with embedded fonts) from `data.json` `weekly`, numbered event markers from `data/events.json` (date, fr, en, noteFr, noteEn; the latest note shows by default). Both lines are win probabilities: market = weekly mean of daily prices; poll = `simulate()` (medium uncertainty, seed 2027) run by `weekly_series()` on the polls of the 30 days up to each week's end, first-round and runoff. The chart ignores the Win/Runoff and uncertainty toggles; the gap badge is market minus poll in the latest week with both. Its poll figures must also go under the future blackout switch.
- Dates and figures in page text (`updated`, `stale`, `meta`, `note`, `pollsIncl`, `cite`) are `{{placeholders}}` in the i18n files, filled from data.json by `figures()` in `js/app.js` and `fr_figures()` in build_data.py: keep both in step. Strings with `{name}` slots are filled by `tf()` in `js/app.js`. `markets.volume`/`qualSum`/`winSum` come from the Polymarket fetch.
- SEO layer: `build_data.py` rewrites the FR text, headline figures and meta/OG tags in `index.html` plus `og-image.png`, from `i18n/fr.json`: edit FR copy there only.
- Analytics (CNIL consent exemption, no banner): GoatCounter (vikander.goatcounter.com, EU) loaded by `analytics.js`, skipped when `localStorage["lecart-optout"]` is set (footer link and confidentialite.html); events `lang-*`, `q-*`, `u-*` via `track()`; no other third party (fonts self-hosted in `fonts/`); legal pages `confidentialite.html`/`mentions-legales.html` state 25-month retention, so keep GoatCounter's data retention setting at 760 days or less.
- Credibility layer: "À propos" section (author, academic-research-only statement, GitHub issues as contact, CSV downloads of `data/market_history.csv` and `data/polls_average.csv`, citation line with `{{year}}`/`{{upd}}`), and `changelog.html` (bilingual, linked from every footer): add an entry there for each notable change.
- If `data.json` is more than 2 days old the page shows a discreet stale-data notice (`renderStale()`).

## First tasks
1. Create a GitHub repository `lecart`, push these files, enable GitHub Pages (deploy from main branch, root).
2. Run `scripts/build_data.py` locally, fix the Polymarket fetch until it produces sensible prices, then check the page renders with the new data.
3. Enable the workflow and trigger it once manually (workflow_dispatch) to confirm it commits.

## Next features (ask the owner before starting each)
- Custom domain.

## Constraints (important)
- Never link to Polymarket or encourage betting: it is not authorised in France. Show prices as data only.
- Poll disclosure: keep the table of polls with institute, sponsor, fieldwork dates and sample size.
- French poll law: publication of polls is prohibited the day before and the day of each round.
  Before April 2027, add a blackout switch that hides poll-derived figures during those windows.
- Every user-facing string must exist in both FR and EN (`i18n/fr.json` and `i18n/en.json`).
- Writing style for page copy: no em-dashes.
- Keep it dependency-free and fast; no frameworks unless there is a clear need. The page has no runtime dependency; Python dependencies are pinned in `requirements.txt`.
- No Monte Carlo or model logic in the page JS: it belongs in `scripts/build_data.py`, with a test.
