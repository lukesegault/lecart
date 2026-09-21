# L'Écart: brief for Claude Code

## What this is
A public, bilingual (FR/EN) page comparing prediction-market odds with opinion polls for the
2027 French presidential election. Core question: "Do markets see what the polls miss?"
Owner: Vikander. Audience: French journalists, policy people, curious readers.

## Current state
- `index.html`: finished single-page front end (vanilla HTML/CSS/JS, no build step). Loads `data.json`.
  Contains the poll-to-probability Monte Carlo simulation (runs in the browser) and the FR/EN toggle.
- `data.json`: snapshot data (polls since mid-July 2026, runoff pairs, monthly trend, manual market snapshot of 20 Sept 2026).
- `scripts/build_data.py`: daily refresh script. Poll part is tested logic. **The Polymarket part is untested**:
  verify the Gamma API endpoint, response shape and candidate naming against https://docs.polymarket.com first.
- `scripts/backfill_history.py`: one-off (already run, 21 Sept 2026) daily "win" history of FAMILY candidates since the market opened (14 Nov 2025) into `data/market_history.csv`; `qual` is empty before 21 Sept 2026. Polymarket is blocked from France, so run it on a GitHub runner.
- Section "Marchés et sondages dans le temps" (`renderDv()` in index.html): one chart per candidate (pills, 1M/3M/6M/Tout, shaded écart, hover readout, PNG export built as one SVG with embedded fonts) from `data.json` `weekly`, numbered event markers from `data/events.json` (date, fr, en, noteFr, noteEn). Both lines are win probabilities: market = weekly mean of daily prices; poll = `simulate()` (medium uncertainty, seed 2027) run by `weekly_series()` on the polls of the 30 days up to each week's end, first-round and runoff. The chart ignores the Win/Runoff and uncertainty toggles; the gap badge is market minus poll in the latest week with both. Its poll figures must also go under the future blackout switch.
- Analytics (CNIL consent exemption, no banner): GoatCounter (vikander.goatcounter.com, EU) loaded by `analytics.js`, skipped when `localStorage["lecart-optout"]` is set (footer link and confidentialite.html); events `lang-*`, `q-*`, `u-*` via `track()`; no other third party (fonts self-hosted in `fonts/`); legal pages `confidentialite.html`/`mentions-legales.html` state 25-month retention, so keep GoatCounter's data retention setting at 760 days or less.
- `.github/workflows/update-data.yml`: runs the script daily and commits changes.
- Dates and figures in the page text (`updated`, `meta`, `note`, `pollsIncl`) are `{{placeholders}}` in `T`, filled from data.json by `figures()` in index.html and `fr_figures()` in build_data.py: keep both in step. `markets.volume`/`qualSum` come from the Polymarket fetch (seeded by hand on 21 Sept 2026 until the first successful run).
- Credibility layer: "À propos" section (author, academic-research-only statement, GitHub issues as contact, CSV downloads of `data/market_history.csv` and `data/polls_average.csv` written by `write_polls_average()`, citation line with `{{year}}`/`{{upd}}`), and `changelog.html` (bilingual, linked from every footer): add an entry there for each notable change.
- SEO layer: `build_data.py` rewrites the FR text, headline figures and meta/OG tags in `index.html` (between the STATIC and META markers) plus `og-image.png`, so edit FR copy only in `T.fr`, and keep its Python `simulate()` in sync with the JS one.

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
- Every user-facing string must exist in both FR and EN (see the `T` object in index.html).
- Writing style for page copy: no em-dashes.
- Keep it dependency-free and fast; no frameworks unless there is a clear need.
