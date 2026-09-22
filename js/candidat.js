(async () => {
  const { get, loadLang, t, tf, paintNav } = Lecart;
  let DATA;
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("cdName").textContent = "Data could not be loaded. / Les données n'ont pas pu être chargées."; return; }
  const MARKET = DATA.markets.candidates;
  const state = { q: "qual", u: "mid" };
  const num = x => Lecart.lang === "fr" ? x.toFixed(1).replace(".", ",") : x.toFixed(1);

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
    // Bridges a single missing month; breaks the line over longer gaps (same rule as js/app.js's pathOf()).
    let d = "", prev = -1, last = null;
    s.forEach((v, i) => { if (v == null) return; d += (prev >= 0 && i - prev <= 1 ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1) + " "; prev = i; last = i });
    return { d, last };
  }

  function drawTrend() {
    const tr = (DATA.trend.series[NAME] || []).slice(), months = DATA.trend.months;
    const svg = document.getElementById("cdTrend"), wrap = document.getElementById("cdTrendWrap");
    const vals = tr.filter(v => v != null);
    if (!vals.length) { wrap.innerHTML = `<p style="font:400 13px var(--sans);color:var(--muted)">${t("cdNoTrend")}</p>`; return; }
    const lo = Math.floor(Math.min(...vals) - 1), hi = Math.ceil(Math.max(...vals) + 1);
    const X = i => 34 + i / (tr.length - 1) * 496, Y = s => 172 - (s - lo) / (hi - lo) * 160;
    const { d: path, last: li } = pathOf(tr, X, Y);
    let g = "";
    [1, 2, 3].forEach(k => { const tv = Math.round(lo + (hi - lo) * k / 4), y = Y(tv);
      g += `<line x1="34" y1="${y.toFixed(1)}" x2="530" y2="${y.toFixed(1)}" stroke="var(--rule2)"/><text x="26" y="${(y + 3.5).toFixed(1)}" text-anchor="end" style="font:400 10px var(--sans);fill:var(--muted)">${tv}%</text>`; });
    g += `<path d="${path}" stroke="var(--ink)" stroke-width="1.6" fill="none" stroke-linejoin="round"/>`;
    const peak = tr.indexOf(Math.max(...vals));
    if (peak !== li) {   // no separate marker when the peak is also the latest point (would sit on top of it)
      const px = X(peak), py = Y(tr[peak]);
      const mo = t("months")[+months[peak].split("-")[1] - 1];
      g += `<line x1="${px.toFixed(1)}" y1="${py.toFixed(1)}" x2="${px.toFixed(1)}" y2="22" stroke="var(--orange)" stroke-width="1" stroke-dasharray="2 3"/>` +
        `<rect x="${(px - 3).toFixed(1)}" y="16" width="6" height="6" fill="var(--orange)"/>` +
        `<text x="${(px + 10).toFixed(1)}" y="22" style="font:500 10.5px var(--sans);fill:var(--orange)">${mo} ${months[peak].slice(0, 4)}, ${tf("cdPeak", { v: num(tr[peak]) })}</text>`;
    }
    if (li != null) { const ex = X(li), ey = Y(tr[li]);
      g += `<rect x="${(ex - 3).toFixed(1)}" y="${(ey - 3).toFixed(1)}" width="6" height="6" fill="var(--ink)"/>` +
        `<text x="556" y="${(ey + 4).toFixed(1)}" text-anchor="end" style="font:600 11px var(--sans);fill:var(--ink)" class="num">${num(tr[li])}</text>`; }
    g += `<line x1="34" y1="172" x2="530" y2="172" stroke="var(--ink)"/>`;
    // Month labels live inside the SVG (like the rest of the chart) so they scale with the viewBox instead of drifting out of alignment at other widths.
    const ml = i => t("months")[+months[i].split("-")[1] - 1] + " " + months[i].slice(2, 4);
    [0, Math.round((tr.length - 1) / 3), Math.round((tr.length - 1) * 2 / 3), tr.length - 1].forEach((i, k) => {
      const anchor = k === 0 ? "start" : k === 3 ? "end" : "middle";
      g += `<text x="${X(i).toFixed(1)}" y="190" text-anchor="${anchor}" style="font:400 10px var(--sans);fill:var(--muted)">${ml(i)}</text>`;
    });
    svg.innerHTML = g;
  }

  function render() {
    document.title = Lecart.lang === "fr" ? `L'Écart · ${NAME}` : `L'Écart · ${NAME}`;
    const S = DATA.sim[state.u][NAME], avg = DATA.avg[NAME];
    document.getElementById("cdName").textContent = NAME;
    document.getElementById("cdFamily").textContent = t("fam")[cand.f] || cand.f;
    document.getElementById("cdMktQual").textContent = num(cand.qual);
    document.getElementById("cdPolQual").textContent = S ? num(S.qual) : "–";
    document.getElementById("cdMktWin").textContent = num(cand.win);
    document.getElementById("cdPolWin").textContent = S ? num(S.win) : "–";
    document.getElementById("cdAvg").textContent = avg ? num(avg[0]) + (Lecart.lang === "fr" ? " %" : "%") : t("notPolled");
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
      document.getElementById("cdH1").textContent = tf(ec >= 0 ? "cdH1Up" : "cdH1Down", { n: NAME, v: verb });
      document.getElementById("cdNote").textContent = tf(ec >= 0 ? "gapUp" : "gapDown", { s: Lecart.surname(NAME), v: verb, d: Math.abs(Math.round(ec)) });
    }
    document.getElementById("cdGapLabel").textContent = t(state.q === "qual" ? "qual" : "win");
    document.getElementById("cdGapVal").textContent = poll == null ? t("marketsOnly") : (market - poll >= 0 ? "+" : "−") + num(Math.abs(market - poll));
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
  window.addEventListener("lecart-lang-change", () => { render(); paintNav("apercu"); });

  paintNav("apercu");
  render();
})();
