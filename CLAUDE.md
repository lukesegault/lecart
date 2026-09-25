# L'Écart: brief for Claude Code

## What this is
A public, bilingual (FR/EN) page comparing prediction-market odds with opinion polls for the
2027 French presidential election. Core question: "Do markets see what the polls miss?"
Owner: Vikander. Audience: French journalists, policy people, curious readers.

## Current state
Three pages, vanilla HTML/CSS/JS, no build step, no framework. Sharp/mint visual design (Archivo + Instrument
Serif, self-hosted in `fonts/`; square corners, hairline rules): `css/type.css` (the type scale) and `css/pages.css` are the only stylesheets.
- `index.html`: the homepage. Headline (biggest gap, win view), the markets-over-time chart, the full
  candidate comparison table, "Écart entre places de marché" (`#venueGap`, hidden when fewer than two
  candidates are priced on both venues), Method, About. Markup between `<!--STATIC-START-->`/`END` and
  `<!--META-START-->`/`END` is rewritten by the pipeline for crawlers. CSP meta tag: scripts from self and
  gc.zgo.at, styles and fonts from self; do not add inline `<script>` or `<style>` blocks.
- `candidat.html?c=<name>`: one candidate. Same over-time chart (candidate selector navigates to a new `?c=`),
  a meta rail with each venue's own qualification/win number (`cdMktQual` = Polymarket only, `cdMktWinPoly`/
  `cdMktWinKal`) plus the poll numbers, first-round monthly trend (axis starts at 0, event markers from
  `data/events.json`), the gap isolated on its own 0-100 scale with up to three ticks (Polymarket, Kalshi,
  polls). Defaults to the biggest-gap candidate when `c` is missing or unknown.
- `second-tour.html`: every tested runoff pairing. The candidate common to every pairing (found by
  `referenceCandidate()` in `js/second-tour.js`, currently always Marine Le Pen) is anchored on the right in
  every row so the table doesn't flip sides; the last two columns are always the *other* candidate's
  (the challenger's) simulated win chance and each venue's own market win chance, stacked (`.sp-pair-win .pv`).
- `notes.html`/`js/notes.js`: the full archive of `data/notes.json`, newest first. index.html shows only the
  latest entry (`#latestNote`); this page shows all of them, same card style (`.sp-note`).
- **No blended market figure exists anywhere in this codebase** (owner instruction, 24 Sept 2026): not in
  `data.json`, not in a chart line, not in a table cell, not in the generated headline. Every number a venue
  quotes stands on its own; where two venues both quote the same event the page shows both (or the range they
  bound), never a mean. `scripts/build_data.py`'s `merge_candidates()` docstring and this file are the record of
  that decision — do not reintroduce an average when touching this code.
- Comparison table (`#ovBoard` in index.html): one column per venue (`ovColPoly`, `ovColKalshi`) plus polls.
  Each venue's own price comes straight from `data.json`'s `candidates[].venues.<venue>`; the "Écart" column
  shows each venue's own gap against the poll figure, stacked (`.val.ec .g.poly`/`.g.kal`), never averaged.
  A venue that doesn't quote a candidate/market shows an em space and a footnote marker (`venueFootnote`),
  never a substituted value — see `venueCell()` in `js/index.js`. "Gagner" (`win`) is the default tab on every
  page (`state.q` in `js/index.js`/`js/candidat.js`): it is the only event both venues price. Under "Accéder au
  second tour" the Kalshi column and its half of the gap are hidden outright (CSS `.q-qual .g.kal`, plus the
  Kalshi cell rendered empty in JS) and a one-line note (`ovQualKalshiNote`) explains why: Kalshi has no
  qualification market. Under each venue's header, a `.sp-volrow` line gives that venue's own volume, liquidity
  and snapshot date as one sentence (`volSentencePoly`/`volSentenceKal`, from `markets.venues.<venue>.volume.win`/
  `.liquidity.win`), with a discreet `.thinbadge` when that venue's win (or, in the qual tab, Polymarket's qual)
  market is flagged thin (see `THIN_MARKET_VOLUME` below). Shows the top 8 rows by default, with an `#ovMore`
  "show all" toggle (`ovMore`/`ovLess` i18n keys); `js/index.js`'s `SHOWN` constant. "Écarts marché-sondages les
  plus marqués" (`#divergences`, `renderDivergences()`): the three candidates with the largest gap between one
  venue and the polls, one generated sentence each (`data.json`'s `notes.divergences`, computed once by
  `scripts/build_data.py`'s `largest_divergences()`/`generated_notes()` — see "Generated, not hand-written prose"
  below). "Écart entre places de marché" (`#venueGap`, `renderVenueGap()`): the FAMILY candidates priced on both
  venues, ranked by `|polymarket − kalshi|`, top 5, with a generated lead sentence naming the single largest
  disagreement (`notes.venueGapLead`); hidden when fewer than two candidates qualify. "Figurer sur le bulletin"
  (`#ballot`, `renderBallot()`): Kalshi's `KXFRPRESBALLOT` candidacy-confirmation price, its own small section,
  never merged with win or qual (see "Kalshi decisions" under Constraints); hidden when `data.json` has no
  `markets.ballot`. A dated note (`#latestNote`, `renderLatestNote()`) shows the most recent entry of
  `data/notes.json`, hand-written by the owner; older ones live on `notes.html` (`js/notes.js`).
- `js/pages-common.js` (`Lecart` global): language, `data.json`/i18n fetch (`?v=<meta data-version>` cache-busting), figure filling, nav/footer/opt-out wiring, shared formatting (`pct` whole numbers, `pct1` one decimal, both with French comma/nbsp-% rules), `checkBlackout()`/`paintBlackout()` (see Constraints). `js/over-time-chart.js` (`Lecart.mountOverTimeChart`/`exportOverTimeChart`): the market-vs-poll-implied-win-probability chart shared by index.html and candidat.html (0-100 fixed axis, 1M/3M/6M/All). Two market lines, one per venue — Polymarket solid mint, Kalshi dashed mint (`stroke-dasharray`) — plus the poll line, each with its own direct end-of-line label; no poll-vs-market gap shading (dropped when the chart went from one blended line to two: two overlapping semi-transparent fills read as a muddy overlap, not a legible gap — see the code comment in `chartSvg()`). The one shaded region left is the thin band between the two venues' own weekly series, wherever both priced the same run of 3+ consecutive weeks (`MIN_RUN`). The gap pill and hover readout show each venue's own gap against the polls, joined by "/" when they differ (`gapsText()`), never a mean. `js/index.js`, `js/candidat.js`, `js/second-tour.js`: one per page, no simulation.
- Top bar (`.sp-bar`, all three pages): under 760px the nav collapses into `#spMenuBtn`'s menu; under 400px the
  brand's tagline (`.sp-brand span`) also hides, keeping the brand and FR/EN buttons visible without crowding.
- `data.json` (minified, written by the pipeline only): `updated`, `polls` (fields the table shows), `avg`,
  `sim` (win/qual per candidate for low/mid/high uncertainty), `trend`, `weekly` (poll-vs-market win
  probability by week, `WEEKLY_CANDIDATES` = the same 7 as `TREND_CANDIDATES`), `pairs` (head-to-head poll
  share and poll count per tested runoff pairing), `markets`, `notes` (`{divergences: [{fr, en}, ...], venueGapLead: {fr, en} | null}`,
  built once per run by `generated_notes()` — see "Generated, not hand-written, prose" under Constraints).
  `markets`: `snapshot` (today's date), `source` (comma-joined venue names that priced this run), `thinThreshold`
  (= `THIN_MARKET_VOLUME`, so the page and the Method text always quote the same figure), `venues`
  (`{polymarket: {snapshot, stale, volume: {win, qual}, liquidity: {win, qual}, winSum, qualSum, thin: {win, qual}},
  kalshi: {snapshot, stale, volume: {win}, liquidity: {win}, winSum, thin: {win}}}`; a venue absent from `venues`
  was never fetched successfully; `stale: true` means today's fetch or sanity check failed and this is a reused
  earlier snapshot; `thin.<market>` is `volume.<market> < THIN_MARKET_VOLUME`, that venue's own cumulative
  volume against the documented threshold), `candidates` (`merge_candidates()`'s output: one row per candidate
  priced by at least one venue, `{c, f, venues}` — **no top-level `win`/`qual`, by design**: `venues` is
  `{venue: {win[, qual], volume: {...}, liquidity: {...}}}`, each venue's own unmixed price and its own
  volume/liquidity for that market), `ballot` (Kalshi `KXFRPRESBALLOT` only, built by `fetch_ballot()`:
  `{snapshot, stale, volume, liquidity, sum, thin, candidates: [{c, price, volume, liquidity}]}`; absent when
  never fetched successfully, same stale/fallback pattern as a venue but tracked separately since it isn't a
  win/qual venue).
  `weekly.series[c]`: `poll`, `venues` (`{polymarket: [...], kalshi: [...]}`, each venue's own weekly average —
  no blended line here either; the chart draws both).
- `scripts/build_data.py`: the daily pipeline and **the only place the Monte Carlo lives** (`simulate()`, `LEVELS`, `page_views()`, `weekly_series()`). The page never simulates: to change a model parameter change it there, and the page follows. Two independent prediction-market venues: Polymarket (`market_prices()`, winner + runoff-qualification, each call also returns per-candidate volume/liquidity from the Gamma API's `volumeNum`/`liquidityNum`) and Kalshi (`kalshi_win_prices()`, winner only, per-candidate volume/open-interest from `volume_fp`/`open_interest_fp`; its `KXFRPRESBALLOT` series was investigated and rejected as a `qual` source, see "Kalshi decisions" under Constraints, and is instead fetched separately by `kalshi_ballot_prices()`/`fetch_ballot()`). `build_candidates_polymarket()`/`build_candidates_kalshi()`/`build_ballot()` filter each venue's prices to FAMILY names and attach volume/liquidity; `merge_candidates()` keeps every venue's own price, unmixed — see "no blended market figure" above. `THIN_MARKET_VOLUME` (currently $20,000) is the documented cutoff below which a venue's cumulative volume for a market gets the thin-market flag (`thin_flags()`); change the constant and the Method's `m5`/`{{thin}}` figure follow automatically (`fr_figures()`'s `thin`, `js/pages-common.js`'s `figures()`). All-or-nothing per run, but **per-venue graceful degradation**: `fetch_venue_polymarket()`/`fetch_venue_kalshi()`/`fetch_ballot()` each fetch, build candidates and run `validate_venue()` (prices 0-100, winner sum 85-115% — **except** `check_sum=False` for the ballot indicator, whose independent per-candidate confirmations routinely sum well past 100%, unlike a single-winner market — no vanished candidate) independently; a venue or the ballot indicator that fails falls back to its own previous snapshot marked `stale` instead of aborting the run (`stale_venue_prices()`); the run only aborts (`SystemExit(1)`, changes nothing) if **neither win/qual venue** has usable data, fresh or previous (the ballot indicator failing never blocks the run: it just goes stale or absent). `validate_polls()` is the separate, unconditional check (poll count not down more than 20%) that still aborts the whole run on its own. `--reuse-markets` skips only Polymarket (for machines where it's blocked, e.g. France) and keeps its last snapshot marked stale; Kalshi (win and ballot) is always fetched fresh regardless of this flag.
- Headline (`headline()` in build_data.py, mirrored by `headline()`/`headlineText()` in `js/index.js` and
  `js/candidat.js`): the candidate with the single largest gap between **one venue's own** win price and the
  poll simulation — never a mean (computed by comparing every venue's gap against the polls independently and
  keeping the largest, across every candidate). The generated sentence states a range ("entre X % et Y %",
  `headlineRange` i18n key) when more than one venue prices that candidate's win event, or names the one venue
  explicitly (`headlineSingle`, `venuePolymarket`/`venueKalshi`) when only one does. `write_og_image()` plots one
  diamond marker per venue on the OG card (a dumbbell when there are two) instead of a single blended pin.
- **Type system (25 Sept 2026).** `css/type.css` is the only place a font family, size or weight is decided; `css/pages.css` and the pages' JS use its `--t-*` tokens (`font: var(--t-prose)`) and never a raw size, weight or family. Roles: Bodoni Moda (500) for h1 and h2 only (`--t-display` 44, `--t-h2` 30; h1 drops to 30 under 760px); Source Serif 4 (400) for all prose (`--t-prose` 17/1.65, `--t-prose-s` 15, nothing smaller); IBM Plex Sans for labels, navigation, table headers, controls and candidate names (`--t-ui` 13, `--t-ui-b` 13/600, `--t-label` 11/600, which is always uppercase with 0.08em tracking, set by the one label rule at the top of `pages.css`); IBM Plex Mono for numerals only, never words (`--t-num-l` 15/600, `--t-num` 13/600, `--t-num-r` 13/400, `--t-num-s` 11/400). Weights are 400 and 600, plus Bodoni 500; only those font files ship (`fonts/fonts.css`). Where a line mixes words and numbers (a pill, a venue-gap item, "Polymarket 38 %") it is sans, or the number gets its own `.num` span. SVG charts (`js/over-time-chart.js`, `js/candidat.js`) are drawn at the box's real pixel width so 1 unit = 1px and their text keeps its size on a phone; the over-time chart's text carries presentation attributes (not classes) because the PNG export reuses `chartSvg()` as a standalone SVG, so keep those attribute values on the scale. `scripts/audit_type.py` (Playwright, both languages, desktop and phone, other tab/hover/event states included) lists every rendered family+size+weight combination and fails on more than 12 (per page or site-wide, currently 11), text under 11px, anything off the allowed table, or mono used for words; the daily workflow runs it after the build (needs `requirements-dev.txt` and chromium, so the job timeout is 15 min).
- `tests/` (pytest, `python -m pytest -q`, run by the workflow before the build) and `scripts/check_site.py` (Playwright, clicks every control on all three pages in FR/EN, desktop/phone, light/dark; fails on console errors; run it after any front-end change).
- `scripts/backfill_history.py`: one-off (already run, 21 Sept 2026) daily "win" history of FAMILY candidates since the market opened (14 Nov 2025) into `data/market_history.csv`; `qual` is empty before 21 Sept 2026. Polymarket is blocked from France, so run it on a GitHub runner.
- `scripts/backfill_kalshi_history.py`: one-off (not yet run against production data as of 23 Sept 2026), the same
  pattern for Kalshi: daily "win" closes from `kalshi_candlestick_prices()` (quiet-day bid/ask-midpoint fallback)
  for every FAMILY candidate on `KXFRENCHPRES`, appended into `data/market_history.csv` with `venue=kalshi` and
  `qual` left empty (Kalshi never supplies it). Safe to re-run: an existing `(date, candidate, venue)` triple is
  never duplicated. Run it on a GitHub runner too, for the same reason as `backfill_history.py`.
- `data/market_history.csv`: `date, candidate, venue, win, qual` (the `venue` column was added 22 Sept 2026; rows
  written before that default to `polymarket` on read, see `read_history_rows()`). `data/market_liquidity.csv`
  (added 24 Sept 2026): `date, venue, candidate, market, volume, liquidity`, one row per (venue, candidate,
  market) each day, `market` being `win`, `qual` or (Kalshi only) `ballot`; `liquidity` holds a different real
  metric per venue (Polymarket's own liquidity figure, Kalshi's open interest) — see the Method's `m5` for the
  definitions, and read `venue` before comparing the column across rows. Written by `liquidity_with_today()`,
  each (venue, market) replaced independently so one failing today doesn't discard another's fresh row (see
  `stale()` inside it). The CSV download UI (index.html "Télécharger les données") and its FR/EN blurbs
  (`dlMarket`/`dlLiquidity`/`dlNote` in the i18n files) mention both venues and both CSVs; update them if a
  third venue is ever added.
- `.github/workflows/update-data.yml`: daily at 05:00 UTC, 15 minute timeout, concurrency group, pip cache, pinned `requirements.txt`; tests, build, type audit, commit `index.html candidat.html second-tour.html notes.html` (statics/`data-version`) plus `data.json data/ og-image.png`; nothing is committed after a failure.
- Dates and figures in page text (`updated`, `pollsIncl`, `cite`, `spSnap`, `spSources`) are `{{placeholders}}` in the i18n files, filled from data.json by `Lecart.figures()`/`Lecart.fill()` in `js/pages-common.js` and `fr_figures()` in build_data.py: keep both in step. Strings with `{name}` slots are filled by `Lecart.tf()`. `markets.venues.<venue>.volume`/`winSum`/`qualSum` come from that venue's own fetch (`markets.snapshot`/`source` stay top-level, used by `fr_figures()`'s `snap` placeholder).
- SEO layer: `build_data.py` rewrites the FR text, headline (`<h1 id="siteH1">`, same sentence `js/index.js` builds client-side, see the headline bullet above) and meta/OG tags in `index.html` plus `og-image.png` from `i18n/fr.json` (edit FR copy there only); `candidat.html`/`second-tour.html` have static generic OG tags and just get their `data-version` meta restamped daily (no per-candidate OG image: `?c=` has too many values).
- Analytics (CNIL consent exemption, no banner): GoatCounter (vikander.goatcounter.com, EU) loaded by `analytics.js`, skipped when `localStorage["lecart-optout"]` is set (footer link and confidentialite.html); events `lang-*`, `q-*`, `u-*`, `ot-*` via `track()`; no other third party (fonts self-hosted in `fonts/`); legal pages `confidentialite.html`/`mentions-legales.html` state 25-month retention, so keep GoatCounter's data retention setting at 760 days or less.
- Credibility layer (index.html "À propos" section): author, academic-research-only statement, GitHub issues as contact, CSV downloads of `data/market_history.csv`, `data/market_liquidity.csv` and `data/polls_average.csv`, citation line with `{{year}}`/`{{upd}}`; `changelog.html` (bilingual, linked from every footer): add an entry there for each notable change.
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
    `win`; Polymarket remains the sole `qual` source (`merge_candidates()` leaves `qual` off a candidate's row
    entirely when Polymarket hasn't priced it). If Kalshi ever lists a genuine runoff-qualification series, this
    is the place to reconsider it. `KXFRPRESBALLOT` itself is not wasted, though: per owner instruction (24 Sept
    2026) it is shown as its own small "Figurer sur le bulletin" section (`fetch_ballot()`, `markets.ballot`,
    `#ballot` on index.html) — a distinct, Kalshi-only, candidacy-confirmation indicator, never merged into win
    or qual.
  - **Data Terms of Use.** Kalshi's published Data Terms of Use prohibit public display, distribution, database
    compilation and automated/scripted retrieval of its data without Kalshi's written permission, and separately
    bar AI-usage of the data; this is a real conflict with this site's public, automated, non-commercial-research
    nature. This was surfaced to the owner before any Kalshi code was written; the owner's explicit, informed
    decision (after this conflict was restated a second time, since "personal, non-commercial use" does not on
    its own cover those specific prohibitions) was to proceed anyway. Kalshi integration therefore exists here on
    that basis, not on a legal reading that the site is in the clear. Revisit only on new owner instruction.
- **Liquidity threshold (24 Sept 2026).** `THIN_MARKET_VOLUME` in `scripts/build_data.py` ($20,000) is a chosen,
  documented round figure: a market whose cumulative traded volume stays under it is flagged thin (`thin_flags()`,
  the `.thinbadge` on the page, `m5` in the Method). It is deliberately an *absolute* cutoff on that venue's own
  volume, not a ratio against the other venue or the other market — Polymarket's qualification market is
  described as thinly traded in the owner's brief, but on any given day its real volume may or may not clear
  $20,000; the flag is meant to move with the data, not to hard-code that market as permanently thin. Change the
  constant (and only the constant) if $20,000 stops being the right line; the page and the Method text pick it up
  automatically via `markets.thinThreshold` in data.json.
- **Generated, not hand-written, prose (24 Sept 2026).** Every sentence that names a specific candidate or figure
  is either a template filled from `data.json` at render time, or generated once server-side and stored as final
  text in `data.json`'s `notes` object — never typed by hand into an i18n string. This followed an audit of every
  string in `i18n/fr.json`/`en.json`: the one hand-written sentence that assumed something about *today's* numbers
  (`m5`'s old claim that the qualification market "is thinly traded") was reworded into a pure definition; 20 dead
  keys left over from earlier redesigns (never referenced by any page or script) were deleted. `m2`'s reference to
  the 2022 election understating Jean-Luc Mélenchon is kept on purpose: it is a fixed historical fact used to
  justify the uncertainty model, not analysis of the current race, so it can never go stale.
  `scripts/build_data.py`'s `generated_notes()` builds, once per run, in both languages: `largest_divergences()`
  (the 3 candidates with the biggest single-venue gap against the polls, `data.json`'s `notes.divergences`,
  rendered via the `divergenceItem` i18n template) and `largest_venue_gap()` (the single biggest Polymarket-vs-
  Kalshi disagreement, `notes.venueGapLead`, via the `venueGapLead` template). Both read from `data.json`'s
  `candidates[].venues`, never a mean. `elide_de()` handles French elision ("d'Édouard" vs "de Marine") for the
  venue-gap-lead sentence; `signed_pts()` rounds *before* signing a gap, so a value that rounds to zero reads "0",
  never "−0" (the same fix is mirrored in `js/index.js`'s `gapText()` and `js/candidat.js`'s `gapOf()` — round
  first, sign the rounded value, in every place a gap is displayed). Templates avoid adjectives that would need
  gender agreement, by design, rather than tracking each candidate's gender. Covered by
  `tests/test_build_data.py`'s "generated notes" section (elision, signed zero, one-venue-only, negative and
  positive gaps). `data/notes.json` (`date`, `titleFr`/`bodyFr`, `titleEn`/`bodyEn`) is the one genuinely
  hand-written, dated exception: the owner's own notes, latest one on the homepage (`#latestNote`), the rest on
  `notes.html`. Keep this pattern when adding new page text: if a sentence would need updating as the numbers
  change, generate it from data.json instead of writing it by hand.
