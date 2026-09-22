(async () => {
  const { get, loadLang, t, tf, paintNav } = Lecart;
  let DATA, EVENTS = [];
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("cdName").textContent = "Data could not be loaded. / Les données n'ont pas pu être chargées."; return; }
  try { EVENTS = await get("data/events.json"); EVENTS.sort((a, b) => a.date < b.date ? -1 : 1); } catch (e) {}

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

  const MARKET = DATA.markets.candidates;
  const state = { q: "qual", u: "mid" };
  const num = x => Lecart.lang === "fr" ? x.toFixed(1).replace(".", ",") : x.toFixed(1);
  const WK_NAMES = Object.keys(DATA.weekly ? DATA.weekly.series : {});

  function headline() {
    const S = DATA.sim.mid;
    const rows = MARKET.map(m => ({ c: m.c, market: m.win, poll: S[m.c] ? S[m.c].win : null })).filter(r => r.poll != null);
    rows.sort((a, b) => Math.abs(b.market - b.poll) - Math.abs(a.market - a.poll));
    return rows[0].c;
  }

  const params = new URLSearchParams(location.search);
  const wanted = params.get("c");
  const NAME = (wanted && MARKET.some(m => m.c === wanted)) ? wanted : headline();
  const cand = MARKET.find(m => m.c === NAME);

  function pathOf(s, x, y) {
    let d = "", prev = -1, last = null;
    s.forEach((v, i) => { if (v == null) return; d += (prev >= 0 && i - prev <= 1 ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1) + " "; prev = i; last = i });
    return { d, last };
  }

  // Nearest trend month to an event date, only kept if within half a month-step of an actual point.
  function nearestMonth(months, dateIso) {
    const t0 = Date.parse(dateIso + "T00:00:00Z");
    let best = -1, bestDiff = Infinity;
    months.forEach((m, i) => { const diff = Math.abs(Date.parse(m + "-15T00:00:00Z") - t0); if (diff < bestDiff) { bestDiff = diff; best = i } });
    return bestDiff < 24 * 864e5 * 30 ? best : -1;   // within ~30 days of that month's midpoint
  }

  const trendState = { hov: null };
  function drawTrend() {
    const tr = (DATA.trend.series[NAME] || []).slice(), months = DATA.trend.months;
    const svg = document.getElementById("cdTrend"), wrap = document.getElementById("cdTrendWrap");
    let note = document.getElementById("cdTrendNote");
    const vals = tr.filter(v => v != null);
    if (!vals.length) { wrap.innerHTML = `<p style="font:400 13px var(--sans);color:var(--muted)">${t("cdNoTrend")}</p>`; if (note) note.hidden = true; return; }
    const lo = 0, hi = Math.max(10, Math.ceil((Math.max(...vals) + 2) / 5) * 5);
    const X = i => 34 + i / (tr.length - 1) * 496, Y = s => 172 - (s - lo) / (hi - lo) * 160;
    const { d: path, last: li } = pathOf(tr, X, Y);
    let g = "";
    const step = hi <= 20 ? 5 : 10;
    for (let v = 0; v <= hi; v += step) { const y = Y(v); g += `<line x1="34" y1="${y.toFixed(1)}" x2="530" y2="${y.toFixed(1)}" stroke="var(--rule2)"/><text x="26" y="${(y + 3.5).toFixed(1)}" text-anchor="end" style="font:400 10px var(--sans);fill:var(--muted)">${v}%</text>`; }
    g += `<path d="${path}" stroke="var(--ink)" stroke-width="1.6" fill="none" stroke-linejoin="round"/>`;
    if (li != null) { const ex = X(li), ey = Y(tr[li]);
      g += `<rect x="${(ex - 3).toFixed(1)}" y="${(ey - 3).toFixed(1)}" width="6" height="6" fill="var(--ink)"/>` +
        `<text x="556" y="${(ey + 4).toFixed(1)}" text-anchor="end" style="font:600 11px var(--sans);fill:var(--ink)" class="num">${num(tr[li])}</text>`; }
    g += `<line x1="34" y1="172" x2="530" y2="172" stroke="var(--ink)"/>`;
    const ml = i => t("months")[+months[i].split("-")[1] - 1] + " " + months[i].slice(2, 4);
    [0, Math.round((tr.length - 1) / 3), Math.round((tr.length - 1) * 2 / 3), tr.length - 1].forEach((i, k) => {
      const anchor = k === 0 ? "start" : k === 3 ? "end" : "middle";
      g += `<text x="${X(i).toFixed(1)}" y="190" text-anchor="${anchor}" style="font:400 10px var(--sans);fill:var(--muted)">${ml(i)}</text>`;
    });
    // Real events (data/events.json) replace the old single "peak" annotation, same numbered-marker language as the chart above.
    const evPos = EVENTS.map(e => ({ e, i: nearestMonth(months, e.date) })).filter(p => p.i >= 0);
    evPos.forEach(({ e, i }, k) => { const ex = X(i), ey = Y(tr[i]) ;
      g += `<line x1="${ex.toFixed(1)}" y1="${(ey - 14).toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}" stroke="var(--orange)" stroke-width="1" stroke-dasharray="2 3" stroke-opacity=".6"/>` +
        `<g class="ctm" data-e="${k}" role="button" tabindex="0" aria-label="${e[Lecart.lang]}"><circle cx="${ex.toFixed(1)}" cy="${(ey - 20).toFixed(1)}" r="11" fill="transparent"/><circle cx="${ex.toFixed(1)}" cy="${(ey - 20).toFixed(1)}" r="7" fill="var(--surface)" stroke="var(--orange)" stroke-width="1.3"/><text x="${ex.toFixed(1)}" y="${(ey - 17).toFixed(1)}" text-anchor="middle" font-size="9" font-weight="700" fill="var(--orange)">${k + 1}</text></g>`;
    });
    svg.innerHTML = g;
    if (!note) { note = document.createElement("div"); note.className = "sp-chart-note"; note.id = "cdTrendNote"; wrap.after(note); }
    note.hidden = !evPos.length;
    const paintNote = () => {
      const idx = trendState.hov != null ? trendState.hov : evPos.length - 1, pick = idx >= 0 ? evPos[idx].e : null;
      svg.querySelectorAll(".ctm").forEach(gm => gm.classList.toggle("on", +gm.dataset.e === idx));
      note.innerHTML = pick ? `<strong>${pick[Lecart.lang]}</strong><span class="d">${Lecart.longDate(pick.date)}</span><p>${pick[Lecart.lang === "fr" ? "noteFr" : "noteEn"] || ""}</p>` : "";
    };
    svg.querySelectorAll(".ctm").forEach(gm => { const i = +gm.dataset.e;
      gm.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") { trendState.hov = i; paintNote() } });
      gm.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") { trendState.hov = null; paintNote() } });
      gm.addEventListener("focus", () => { trendState.hov = i; paintNote() }); gm.addEventListener("blur", () => { trendState.hov = null; paintNote() });
      gm.addEventListener("click", () => { trendState.hov = trendState.hov === i ? null : i; paintNote() }); });
    paintNote();
  }

  function render() {
    document.title = `L'Écart · ${NAME}`;
    const S = DATA.sim[state.u][NAME], avg = DATA.avg[NAME];
    document.getElementById("cdName").textContent = NAME;
    document.getElementById("cdFamily").textContent = t("fam")[cand.f] || cand.f;
    document.getElementById("cdMktQual").textContent = num(cand.qual);
    document.getElementById("cdPolQual").textContent = S ? num(S.qual) : "–";
    document.getElementById("cdMktWin").textContent = num(cand.win);
    document.getElementById("cdPolWin").textContent = S ? num(S.win) : "–";
    document.getElementById("cdAvg").textContent = avg ? num(avg[0]) + (Lecart.lang === "fr" ? Lecart.nb + "%" : "%") : t("notPolled");
    const F = Lecart.figures(DATA);
    document.getElementById("cdSnap").textContent = Lecart.fill(t("spSnap"), F);
    document.getElementById("cdSources").textContent = Lecart.fill(t("spSources"), F);

    const market = cand[state.q], poll = S ? S[state.q] : null;
    const verb = state.q === "qual" ? t("verbQ") : t("verbW");
    if (poll == null) {
      document.getElementById("cdH1").textContent = `${NAME}. ${t("notPolled")}.`;
      document.getElementById("cdNote").textContent = t("marketsOnly");
    } else {
      const ec = market - poll;
      document.getElementById("cdH1").textContent = tf("headline", { n: NAME, m: Lecart.pct(market), p: Lecart.pct(poll), v: verb });
      document.getElementById("cdNote").textContent = tf("gapNote", { v: verb, d: Math.abs(Math.round(ec)) });
    }
    document.getElementById("cdGapLabel").textContent = t(state.q === "qual" ? "qual" : "win");
    // whole points, matching the headline sentence and the over-time chart's gap badge
    document.getElementById("cdGapVal").textContent = poll == null ? t("marketsOnly") : (market - poll >= 0 ? "+" : "−") + Math.round(Math.abs(market - poll));
    const bar = document.getElementById("cdGapbar");
    if (poll == null) {
      bar.querySelectorAll(".fill,.tick-p,.lbl.p").forEach(el => el.style.display = "none");
      document.getElementById("cdM").style.left = market + "%";
      document.getElementById("cdMLbl").style.left = market + "%";
      document.getElementById("cdMLbl").textContent = num(market);
    } else {
      const lo = Math.min(poll, market), hi = Math.max(poll, market);
      bar.querySelectorAll(".fill,.tick-p,.lbl.p").forEach(el => el.style.display = "");
      document.getElementById("cdFill").style.left = lo + "%"; document.getElementById("cdFill").style.width = (hi - lo) + "%";
      document.getElementById("cdP").style.left = poll + "%"; document.getElementById("cdM").style.left = market + "%";
      document.getElementById("cdPLbl").style.left = poll + "%"; document.getElementById("cdPLbl").textContent = num(poll);
      document.getElementById("cdMLbl").style.left = market + "%"; document.getElementById("cdMLbl").textContent = num(market);
    }
    document.getElementById("cdTrendLabel").textContent = t("cdTrendTitle");
    drawTrend();
  }

  let chart = null;
  function mountChart() {
    if (WK_NAMES.length && !chart) {
      chart = Lecart.mountOverTimeChart("otChart", {
        DATA, EVENTS, candidates: WK_NAMES, initial: WK_NAMES.includes(NAME) ? NAME : WK_NAMES[0],
        onNav: n => { location.href = "candidat.html?c=" + encodeURIComponent(n) }
      });
      document.getElementById("otExportBtn").addEventListener("click", () => Lecart.exportOverTimeChart("otChart", { DATA, EVENTS }, "otExportBtn", "otExportMsg"));
    }
  }

  document.querySelectorAll("#cdQ [data-q]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("cd-q-" + b.dataset.q);
    state.q = b.dataset.q;
    document.querySelectorAll("#cdQ [data-q]").forEach(x => x.setAttribute("aria-pressed", x === b));
    render();
  }));
  document.querySelectorAll("#cdU [data-u]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("cd-u-" + b.dataset.u);
    state.u = b.dataset.u;
    document.querySelectorAll("#cdU [data-u]").forEach(x => x.setAttribute("aria-pressed", x === b));
    render();
  }));
  window.addEventListener("lecart-lang-change", () => {
    render(); paintNav("home");
    const root = document.getElementById("otChart"); if (root._render) root._render();
  });

  paintNav("home");
  render();
  mountChart();
})();
