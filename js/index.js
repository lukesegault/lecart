(async () => {
  const { get, loadLang, t, tf, paintNav } = Lecart;
  let DATA, EVENTS = [];
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("ovBoard").innerHTML = "<p style=\"padding:16px\">Data could not be loaded. / Les données n'ont pas pu être chargées.</p>"; return; }
  try { EVENTS = await get("data/events.json"); } catch (e) {}
  const MARKET = DATA.markets.candidates;
  const VENUES = DATA.markets.venues || {};
  // "Gagner" is the default view everywhere: it is the only event both venues price (Kalshi has no qualification
  // market), so it is the one view where the two venues can always be compared side by side.
  const state = { q: "win", u: "mid", all: false };
  const WK_NAMES = Object.keys(DATA.weekly ? DATA.weekly.series : {});
  const SHOWN = 8;
  const EM = " ", MARK = t("venueFootnoteMark");

  // Election-silence period (see config.json): no poll-derived chances or market prices are rendered at all, only
  // the legal notice. Checked once at load; ?blackout=1/0 in the URL overrides the real date for testing.
  const blackout = await Lecart.checkBlackout();
  Lecart.paintBlackout(blackout);
  if (blackout) {
    document.title = Lecart.lang === "fr" ? "L'Écart · Publication suspendue" : "L'Écart · Publication suspended";
    paintNav("home");
    window.addEventListener("lecart-lang-change", () => {
      document.title = Lecart.lang === "fr" ? "L'Écart · Publication suspendue" : "L'Écart · Publication suspended";
      paintNav("home");
    });
    return;
  }

  // The candidate with the single largest gap between one venue's own win price and the poll simulation: never a
  // figure blended across venues (see scripts/build_data.py's headline(), which this mirrors).
  function headline() {
    let best = null;
    MARKET.forEach(m => {
      const s = DATA.sim.mid[m.c]; if (!s) return;
      Object.entries(m.venues).forEach(([venue, p]) => {
        const gap = Math.abs(p.win - s.win);
        if (!best || gap > best.gap) best = { c: m.c, poll: s.win, gap, venues: m.venues };
      });
    });
    return best;
  }

  function headlineText(hl) {
    const names = Object.keys(hl.venues);
    if (names.length > 1) {
      const vals = names.map(v => hl.venues[v].win);
      return tf("headlineRange", { n: hl.c, lo: Lecart.pct(Math.min(...vals)), hi: Lecart.pct(Math.max(...vals)), p: Lecart.pct(hl.poll), v: t("verbW") });
    }
    return tf("headlineSingle", { venue: t("venue" + names[0][0].toUpperCase() + names[0].slice(1)), n: hl.c, m: Lecart.pct(hl.venues[names[0]].win), p: Lecart.pct(hl.poll), v: t("verbW") });
  }

  function renderStatic() {
    document.title = Lecart.lang === "fr" ? "L'Écart · Marchés vs sondages, présidentielle 2027" : "L'Écart · Markets vs polls, French election 2027";
    const hl = headline();
    document.getElementById("siteH1").textContent = headlineText(hl);
    const F = Lecart.figures(DATA);
    document.getElementById("siteSnap").textContent = Lecart.fill(t("spSnap"), F);
    document.getElementById("siteSources").textContent = Lecart.fill(t("spSources"), F);
    document.getElementById("ovBarLabel").textContent = t(state.q === "qual" ? "ovBarQual" : "ovBarWin");
    document.getElementById("ovQualNote").hidden = state.q !== "qual";
    renderStale(F);
    return { c: hl.c };
  }

  function renderStale() {
    let el = document.getElementById("stale");
    const old = (Date.now() - Date.parse(DATA.updated + "T00:00:00Z")) / 864e5 > 2;
    if (!old) { if (el) el.remove(); return }
    if (!el) { el = document.createElement("p"); el.id = "stale"; el.className = "sp-footnote"; el.style.color = "var(--orange)"; el.style.marginTop = "6px"; document.querySelector(".sp-meta").after(el) }
    el.textContent = t("stale");
  }

  // Volume line under each venue's column header ("Volume cumulé : 137 M$ · dernier relevé 23 sept."), and the
  // thin-market badge on the header itself when that venue's win market falls under THIN_MARKET_VOLUME.
  function fmtMoney(n) {
    if (n == null) return "–";
    const abbr = n >= 1e6 ? (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(Math.round(n));
    return abbr + "$";
  }
  function renderVolRow() {
    ["Poly", "Kal"].forEach((suffix, i) => {
      const venue = i === 0 ? "polymarket" : "kalshi", el = document.getElementById("ovVol" + suffix), v = VENUES[venue];
      if (!v) { el.textContent = ""; return; }
      const d = new Date(v.snapshot + "T00:00:00Z");
      const short = Lecart.lang === "fr" ? `${d.getUTCDate()} ${t("months")[d.getUTCMonth()].slice(0, 3)}` : `${t("months")[d.getUTCMonth()].slice(0, 3)} ${d.getUTCDate()}`;
      const thinT = (DATA.markets.thinThreshold || 0).toLocaleString(Lecart.lang === "fr" ? "fr-FR" : "en-US");
      el.innerHTML = tf("volCumul", { v: fmtMoney(v.volume.win), d: short }) + (v.thin && v.thin.win ? ` <span class="thinbadge" title="${tf("thinNote", { t: thinT }).replace(/"/g, "&quot;")}">${t("thinBadge")}</span>` : "");
    });
  }

  function rows() {
    const S = DATA.sim[state.u];
    return MARKET.map(m => {
      const s = S[m.c], a = DATA.avg[m.c];
      return { c: m.c, f: m.f, poll: s ? s[state.q] : null, avg: a ? a[0] : null, n: a ? a[1] : 0, venues: m.venues || {} };
    }).sort((x, y) => {
      const mx = Math.max(...Object.values(x.venues).map(v => v[state.q] || 0), 0), my = Math.max(...Object.values(y.venues).map(v => v[state.q] || 0), 0);
      return Math.max(my, y.poll || 0) - Math.max(mx, x.poll || 0);
    });
  }

  // A venue that doesn't quote this candidate/market shows an em space and a footnote marker, never a
  // substituted value (0, a dash standing in for a real reading, etc.).
  function venueCell(cls, val, thin) {
    if (val == null) return `<span class="val ${cls} num none">${EM}${MARK}</span>`;
    const badge = thin ? `<sup class="thinmark" title="${t("thinBadge")}">†</sup>` : "";
    return `<span class="val ${cls} num">${Lecart.pct(val)}${badge}</span>`;
  }

  function gapText(val, poll) {
    if (val == null || poll == null) return `${EM}${MARK}`;
    const d = val - poll;
    return (d >= 0 ? "+" : "−") + Math.round(Math.abs(d)) + (Lecart.lang === "fr" ? Lecart.nb + "%" : "%");
  }

  function renderBoard() {
    const R = rows(), shown = state.all ? R : R.slice(0, SHOWN);
    const qualMode = state.q === "qual";
    let anyMissing = false, h = "";
    shown.forEach(r => {
      const sub = r.avg != null ? tf("inPolls", { a: Lecart.pct1(r.avg), n: r.n }) : t("notPolled");
      const poly = r.venues.polymarket ? r.venues.polymarket[state.q] : null;
      const kal = !qualMode && r.venues.kalshi ? r.venues.kalshi.win : null;   // Kalshi never prices "qual"
      const thinPoly = VENUES.polymarket && VENUES.polymarket.thin && VENUES.polymarket.thin[state.q];
      if (poly == null || (!qualMode && kal == null)) anyMissing = true;
      const ticks = [];
      if (poly != null) ticks.push(`<span class="tick-m" style="left:${poly}%"></span>`);
      if (kal != null) ticks.push(`<span class="tick-mk" style="left:${kal}%"></span>`);
      if (r.poll != null) ticks.push(`<span class="tick-p" style="left:${r.poll}%"></span>`);
      h += `<a class="sp-row${qualMode ? " q-qual" : ""}" role="listitem" href="candidat.html?c=${encodeURIComponent(r.c)}">` +
        `<span class="name"><b>${r.c}</b><small>${sub}</small></span>` +
        venueCell("poly", poly, thinPoly) +
        (qualMode ? `<span class="val kal num none"></span>` : venueCell("kal", kal, false)) +
        `<span class="val pol num${r.poll == null ? " none" : ""}">${r.poll == null ? "–" : Lecart.pct(r.poll)}</span>` +
        `<span class="val ec">` +
        `<span class="g poly">${gapText(poly, r.poll)}</span>` +
        (qualMode ? "" : `<span class="g kal">${gapText(kal, r.poll)}</span>`) +
        `</span>` +
        `<span class="sp-bartrack"><span class="base"></span>${ticks.join("")}</span></a>`;
    });
    document.getElementById("ovBoard").innerHTML = h;
    document.getElementById("ovVenueFootnote").hidden = !anyMissing;
    const more = document.getElementById("ovMore");
    more.hidden = R.length <= SHOWN;
    if (!more.hidden) more.textContent = state.all ? t("ovLess") : tf("ovMore", { n: R.length });
  }

  // "Écart entre places de marché": the FAMILY candidates priced by both venues, ranked by how far Polymarket
  // and Kalshi disagree on the winner price. Hidden entirely when fewer than two candidates have both prices.
  function renderVenueGap() {
    const sec = document.getElementById("venueGap");
    const diffs = MARKET.map(m => {
      const v = m.venues || {};
      if (!v.polymarket || !v.kalshi) return null;
      return { c: m.c, p: v.polymarket.win, k: v.kalshi.win, d: Math.abs(v.polymarket.win - v.kalshi.win) };
    }).filter(Boolean).sort((a, b) => b.d - a.d);
    sec.hidden = diffs.length < 2;
    if (sec.hidden) return;
    document.getElementById("venueGapList").innerHTML = diffs.slice(0, 5).map(r =>
      `<li><b>${r.c}</b><span class="d">${tf("venueGapItem", { p: Lecart.pct(r.p), k: Lecart.pct(r.k), d: (r.p >= r.k ? "+" : "−") + Math.round(r.d) + (Lecart.lang === "fr" ? Lecart.nb + "%" : "%") })}</span></li>`
    ).join("");
  }

  // "Figurer sur le bulletin" (Kalshi KXFRPRESBALLOT): a separate indicator, never merged with win or qual.
  function renderBallot() {
    const sec = document.getElementById("ballot"), ballot = DATA.markets.ballot;
    if (!ballot || !ballot.candidates || !ballot.candidates.length) { sec.hidden = true; return; }
    sec.hidden = false;
    const rows = ballot.candidates.slice().sort((a, b) => b.price - a.price);
    document.getElementById("ballotList").innerHTML = rows.map(r =>
      `<li><b>${r.c}</b><span class="d">${Lecart.pct(r.price)}</span></li>`).join("");
  }

  function table() {
    const d = s => { const [y, m, dd] = s.split("-"); return dd + "/" + m };
    document.querySelector("#polltable tbody").innerHTML = DATA.polls.slice().reverse().map(p => {
      const f = v => v == null ? "–" : (Lecart.lang === "fr" ? String(v).replace(".", ",") : v);
      return `<tr><td>${p.inst}</td><td>${p.for}</td><td>${d(p.start)} ${t("to")} ${d(p.end)}/${p.end.slice(0, 4)}</td><td>${p.n.toLocaleString(Lecart.lang === "fr" ? "fr-FR" : "en-GB")}</td><td>${f(p.v["Marine Le Pen"])}</td><td>${f(p.v["Édouard Philippe"])}</td><td>${f(p.v["Jean-Luc Mélenchon"])}</td></tr>`;
    }).join("");
  }

  let chart = null;
  function mountChart(hl) {
    const initial = WK_NAMES.includes(hl.c) ? hl.c : WK_NAMES[0];
    if (!chart) {
      chart = Lecart.mountOverTimeChart("otChart", { DATA, EVENTS, candidates: WK_NAMES, initial });
      document.getElementById("otExportBtn").addEventListener("click", () => Lecart.exportOverTimeChart("otChart", { DATA, EVENTS }, "otExportBtn", "otExportMsg"));
    } else chart.setCandidate(initial);
  }

  document.querySelectorAll("#ovQ [data-q]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("ov-q-" + b.dataset.q);
    state.q = b.dataset.q;
    document.querySelectorAll("#ovQ [data-q]").forEach(x => x.setAttribute("aria-pressed", x === b));
    document.getElementById("ovBarLabel").textContent = t(state.q === "qual" ? "ovBarQual" : "ovBarWin");
    document.getElementById("ovQualNote").hidden = state.q !== "qual";
    renderBoard();
  }));
  document.querySelectorAll("#ovU [data-u]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("ov-u-" + b.dataset.u);
    state.u = b.dataset.u;
    document.querySelectorAll("#ovU [data-u]").forEach(x => x.setAttribute("aria-pressed", x === b));
    renderBoard();
  }));
  document.getElementById("ovMore").addEventListener("click", () => {
    Lecart.track("ov-more"); state.all = !state.all; renderBoard();
  });
  window.addEventListener("lecart-lang-change", () => {
    renderStatic(); renderVolRow(); renderBoard(); renderVenueGap(); renderBallot(); table(); paintNav("home", Lecart.figures(DATA));
    const root = document.getElementById("otChart"); if (root._render) root._render();
  });

  paintNav("home", Lecart.figures(DATA));
  const hl = renderStatic();
  renderVolRow();
  renderBoard();
  renderVenueGap();
  renderBallot();
  table();
  mountChart(hl);
})();
