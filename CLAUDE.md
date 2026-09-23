# L'Écart: brief for Claude Code

## What this is
A public, bilingual (FR/EN) page comparing prediction-market odds with opinion polls for the
2027 French presidential election. Core question: "Do markets see what the polls miss?"
Owner: Vikander. Audience: French journalists, policy people, curious readers.

## Current state
Three pages, vanilla HTML/CSS/JS, no build step, no framework. Sharp/mint visual design (Archivo + Instrument
Serif, self-hosted in `fonts/`; square corners, hairline rules): `css/pages.css` is the only stylesheet.
- `index.html`: the homepage. Headline (biggest gap, win view), the markets-over-time chart, the full
  candidate comparison table, "Écart entre places de marché" (`#venueGap`, hidden when fewer than two
  candidates are priced on both venues), Method, About. Markup between `<!--STATIC-START-->`/`END` and
  `<!--META-START-->`/`END` is rewritten by the pipeline for crawlers. CSP meta tag: scripts from self and
  gc.zgo.at, styles and fonts from self; do not add inline `<script>` or `<style>` blocks.
- `candidat.html?c=<name>`: one candidate. Same over-time chart (candidate selector navigates to a new `?c=`),
  qualification/win meta rail, first-round monthly trend (axis starts at 0, event markers from
  `data/events.json`), the gap isolated on its own 0-100 scale. Defaults to the biggest-gap candidate when
  `c` is missing or unknown.
- `second-tour.html`: every tested runoff pairing. The candidate common to every pairing (found by
  `referenceCandidate()` in `js/second-tour.js`, currently always Marine Le Pen) is anchored on the right in
  every row so the table doesn't flip sides; the last two columns are always the *other* candidate's
  (the challenger's) simulated/market win chance.
- Comparison table (`#ovBoard` in index.html): two market columns (Polymarket, Kalshi; a candidate priced on
  only one venue shows `venueNone` ("–") in the other) plus polls. The mint mark on the bar and the "Écart"
  column use the *mean* of the venues that priced the candidate (`m.win`/`m.qual` in `data.json`, already
  blended by `merge_candidates()`; the two venue columns show each venue's own number from `m.venues`). The
  black tick is the poll value (`subA` describes exactly this; keep it in step if the visual encoding changes).
  Kalshi never has a `qual` value (see the `data.json` bullet below), so its column is blank under the
  "Accéder au second tour" tab. Shows the top 8 rows by default, with an `#ovMore` "show all" toggle
  (`ovMore`/`ovLess` i18n keys); `js/index.js`'s `SHOWN` constant. "Écart entre places de marché" (`#venueGap`,
  `renderVenueGap()` in `js/index.js`): the FAMILY candidates priced on both venues, ranked by
  `|polymarket − kalshi|`, top 5; hidden when fewer than two candidates qualify.
- `js/pages-common.js` (`Lecart` global): language, `data.json`/i18n fetch (`?v=<meta data-version>` cache-busting), figure filling, nav/footer/opt-out wiring, shared formatting (`pct` whole numbers, `pct1` one decimal, both with French comma/nbsp-% rules), `checkBlackout()`/`paintBlackout()` (see Constraints). `js/over-time-chart.js` (`Lecart.mountOverTimeChart`/`exportOverTimeChart`): the market-vs-poll-implied-win-probability chart shared by index.html and candidat.html (0-100 fixed axis, 1M/3M/6M/All, direct end-of-line labels with a white halo, gap shading only across genuinely consecutive weeks, a thin band between the two venues' own weekly series behind the mean line wherever both priced the same run of consecutive weeks, hover readout appends both venues' values when both are present that week (`dvAtVenues`), PNG export as a self-contained SVG with embedded fonts). `js/index.js`, `js/candidat.js`, `js/second-tour.js`: one per page, no simulation.
- Top bar (`.sp-bar`, all three pages): under 760px the nav collapses into `#spMenuBtn`'s menu; under 400px the
  brand's tagline (`.sp-brand span`) also hides, keeping the brand and FR/EN buttons visible without crowding.
- `data.json` (minified, written by the pipeline only): `updated`, `polls` (fields the table shows), `avg`,
  `sim` (win/qual per candidate for low/mid/high uncertainty), `trend`, `weekly` (poll-vs-market win
  probability by week, `WEEKLY_CANDIDATES` = the same 7 as `TREND_CANDIDATES`), `pairs` (head-to-head poll
  share and poll count per tested runoff pairing), `markets`.
  `markets`: `snapshot` (today's date), `source` (comma-joined venue names that priced this run), `venues`
  (`{polymarket: {snapshot, stale, volume: {win, qual}, winSum, qualSum}, kalshi: {snapshot, stale, volume: {win}, winSum}}`;
  a venue absent from `venues` was never fetched successfully; `stale: true` means today's fetch or sanity
  check failed and this is a reused earlier snapshot), `candidates` (`merge_candidates()`'s output: one row per
  candidate priced by at least one venue, `{c, f, win, qual, venues}`; `win` is the **mean** of the venues that
  priced the candidate, `qual` is **Polymarket's own number, or 0** — Kalshi never supplies `qual`, see the
  `build_data.py` bullet below; `venues` is `{venue: {win[, qual]}}`, each venue's own unmixed number, for the
  table's two market columns and the "Écart entre places de marché" section).
  `weekly.series[c]`: `poll`, `market` (mean of each priced venue's own weekly average, one vote per venue —
  not a raw average of every daily price, so a venue quoted on more days that week isn't over-weighted),
  `venues` (`{polymarket: [...], kalshi: [...]}`, each venue's own weekly average, for the chart's band).
- `scripts/build_data.py`: the daily pipeline and **the only place the Monte Carlo lives** (`simulate()`, `LEVELS`, `page_views()`, `weekly_series()`). The page never simulates: to change a model parameter change it there, and the page follows. Two independent prediction-market venues: Polymarket (`market_prices()`, winner + runoff-qualification) and Kalshi (`kalshi_win_prices()`, winner only — its `KXFRPRESBALLOT` series was investigated and rejected as a `qual` source, see "Kalshi decisions" under Constraints). `build_candidates_polymarket()`/`build_candidates_kalshi()` filter each venue's prices to FAMILY names; `merge_candidates()` blends them (see the `data.json` bullet). All-or-nothing per run, but **per-venue graceful degradation**: `fetch_venue_polymarket()`/`fetch_venue_kalshi()` each fetch, build candidates and run `validate_venue()` (prices 0-100, winner sum 85-115%, no vanished candidate) independently; a venue that fails falls back to its previous snapshot marked `stale` instead of aborting the run (`stale_venue_prices()`); the run only aborts (`SystemExit(1)`, changes nothing) if **neither** venue has usable data, fresh or previous. `validate_polls()` is the separate, unconditional check (poll count not down more than 20%) that still aborts the whole run on its own. `--reuse-markets` skips only Polymarket (for machines where it's blocked, e.g. France) and keeps its last snapshot marked stale; Kalshi is always fetched fresh regardless of this flag.
- `tests/` (pytest, `python -m pytest -q`, run by the workflow before the build) and `scripts/check_site.py` (Playwright, clicks every control on all three pages in FR/EN, desktop/phone, light/dark; fails on console errors; run it after any front-end change).
- `scripts/backfill_history.py`: one-off (already run, 21 Sept 2026) daily "win" history of FAMILY candidates since the market opened (14 Nov 2025) into `data/market_history.csv`; `qual` is empty before 21 Sept 2026. Polymarket is blocked from France, so run it on a GitHub runner.
- `scripts/backfill_kalshi_history.py`: one-off (not yet run against production data as of 23 Sept 2026), the same
  pattern for Kalshi: daily "win" closes from `kalshi_candlestick_prices()` (quiet-day bid/ask-midpoint fallback)
  for every FAMILY candidate on `KXFRENCHPRES`, appended into `data/market_history.csv` with `venue=kalshi` and
  `qual` left empty (Kalshi never supplies it). Safe to re-run: an existing `(date, candidate, venue)` triple is
  never duplicated. Run it on a GitHub runner too, for the same reason as `backfill_history.py`.
- `data/market_history.csv`: `date, candidate, venue, win, qual` (the `venue` column was added 22 Sept 2026; rows
  written before that default to `polymarket` on read, see `read_history_rows()`). The CSV download UI
  (index.html "Télécharger les données") and its FR/EN blurb (`dlMarket`/`dlNote` in the i18n files) mention
  both venues; update them if a third venue is ever added.
- `.github/workflows/update-data.yml`: daily at 05:00 UTC, 10 minute timeout, concurrency group, pip cache, pinned `requirements.txt`; tests, build, commit `index.html candidat.html second-tour.html` (statics/`data-version`) plus `data.json data/ og-image.png`; nothing is committed after a failure.
- Dates and figures in page text (`updated`, `pollsIncl`, `cite`, `spSnap`, `spSources`) are `{{placeholders}}` in the i18n files, filled from data.json by `Lecart.figures()`/`Lecart.fill()` in `js/pages-common.js` and `fr_figures()` in build_data.py: keep both in step. Strings with `{name}` slots are filled by `Lecart.tf()`. `markets.venues.<venue>.volume`/`winSum`/`qualSum` come from that venue's own fetch (`markets.snapshot`/`source` stay top-level, used by `fr_figures()`'s `snap` placeholder).
- SEO layer: `build_data.py` rewrites the FR text, headline (`<h1 id="siteH1">`, same `gapUp`/`gapDown` sentence js/index.js builds client-side) and meta/OG tags in `index.html` plus `og-image.png` from `i18n/fr.json` (edit FR copy there only); `candidat.html`/`second-tour.html` have static generic OG tags and just get their `data-version` meta restamped daily (no per-candidate OG image: `?c=` has too many values).
- Analytics (CNIL consent exemption, no banner): GoatCounter (vikander.goatcounter.com, EU) loaded by `analytics.js`, skipped when `localStorage["lecart-optout"]` is set (footer link and confidentialite.html); events `lang-*`, `q-*`, `u-*`, `ot-*` via `track()`; no other third party (fonts self-hosted in `fonts/`); legal pages `confidentialite.html`/`mentions-legales.html` state 25-month retention, so keep GoatCounter's data retention setting at 760 days or less.
- Credibility layer (index.html "À propos" section): author, academic-research-only statement, GitHub issues as contact, CSV downloads of `data/market_history.csv` and `data/polls_average.csv`, citation line with `{{year}}`/`{{upd}}`; `changelog.html` (bilingual, linked from every footer): add an entry there for each notable change.
- If `data.json` is more than 2 days old index.html shows a discreet stale-data notice (`renderStale()` in `js/index.js`).

## First tasks
1. Create a GitHub repository `lecart`, push these files, enable GitHub Pages (deploy from main branch, root).
2. Run `scripts/build_data.py` locally, fix the Polymarket fetch until it produces sensible prices, then check the page renders with the new data.
3. Enable the workflow and trigger it once manually (workflow_dispatch) to confirm it commits.

## Next features (ask the owner before starting each)
- Custom domain.
- The old design's "where they disagree most" gap cards and "reading the gaps" prose, and the standalone multi-candidate first-round poll-history chart, were dropped in the redesign (superseded by the over-time chart and the per-candidate first-round chart). Bring any of them back if wanted.

## Constraints (important)
- Never link to Polymarket or encourage betting: it is not authorised in France. Show prices as data only.
- Poll disclosure: keep the table of polls with institute, sponsor, fieldwork dates and sample size.
- French poll law (Act No. 77-808 of 19 July 1977): publication of polls is prohibited the day before and the day
  of each round. **Implemented**: `config.json` (`blackout.periods`, local time in `blackout.timezone`) lists the
  windows; `Lecart.checkBlackout()`/`paintBlackout()` in `js/pages-common.js` hide `#mainContent` and show
  `#blackoutNotice` on all three pages (checked once per load; `?blackout=1`/`0` in the URL forces it for testing).
  `scripts/build_data.py`'s `in_blackout()`/`render_index()` mirror this server-side for index.html's static
  layer and meta tags (`write_blackout_image()` for `og-image.png`), so a crawler that never runs JS also gets the
  notice, not the figures. Extra `schedule.cron` entries in `.github/workflows/update-data.yml` fire right at each
  boundary. Update `config.json` for any future election; keep its periods in step with the client and server copy
  (there is only one file, both read it) and add matching cron entries for the new dates.
- Every user-facing string must exist in both FR and EN (`i18n/fr.json` and `i18n/en.json`).
- Writing style for page copy: no em-dashes.
- Keep it dependency-free and fast; no frameworks unless there is a clear need. The page has no runtime dependency; Python dependencies are pinned in `requirements.txt`.
- No Monte Carlo or model logic in the page JS: it belongs in `scripts/build_data.py`, with a test.
- **Kalshi decisions (22 Sept 2026), kept here as the record of two calls made while adding Kalshi as a second
  venue:**
  - **Winner price only, never `qual`.** Kalshi's `KXFRPRESBALLOT` series was investigated as a possible source
    for the runoff-qualification price and rejected: its `rules_primary` text resolves it on official candidacy
    *confirmation* for the first round, not on reaching the second round, a different question from Polymarket's
    `qual` market. No Kalshi series for runoff qualification was found (checked the events list under
    `KXFRENCHPRES`, and several plausible series tickers, all 404). Using `KXFRPRESBALLOT` as `qual` would have
    misrepresented candidacy-confirmation odds as runoff odds, so `build_candidates_kalshi()` only ever emits
    `win`; Polymarket remains the sole `qual` source (`merge_candidates()` falls back to `0` for a candidate
    Polymarket hasn't priced). If Kalshi ever lists a genuine runoff-qualification series, this is the place to
    reconsider it.
  - **Data Terms of Use.** Kalshi's published Data Terms of Use prohibit public display, distribution, database
    compilation and automated/scripted retrieval of its data without Kalshi's written permission, and separately
    bar AI-usage of the data; this is a real conflict with this site's public, automated, non-commercial-research
    nature. This was surfaced to the owner before any Kalshi code was written; the owner's explicit, informed
    decision (after this conflict was restated a second time, since "personal, non-commercial use" does not on
    its own cover those specific prohibitions) was to proceed anyway. Kalshi integration therefore exists here on
    that basis, not on a legal reading that the site is in the clear. Revisit only on new owner instruction.
