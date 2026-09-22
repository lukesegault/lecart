(async () => {
  const { get, loadLang, T, t, tf, paintNav } = Lecart;
  let DATA;
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("ovBoard").innerHTML = "<p style=\"padding:16px\">Data could not be loaded. / Les données n'ont pas pu être chargées.</p>"; return; }
  const MARKET = DATA.markets.candidates;
  const state = { q: "qual", u: "mid" };

  // Same rule as index.html's spotlight: the candidate with the largest gap on the Win view, medium uncertainty, sets the headline regardless of the tabs below.
  function headline() {
    const S = DATA.sim.mid;
    const rows = MARKET.map(m => ({ c: m.c, market: m.win, poll: S[m.c] ? S[m.c].win : null })).filter(r => r.poll != null);
    rows.sort((a, b) => Math.abs(b.market - b.poll) - Math.abs(a.market - a.poll));
    return rows[0];
  }

  function renderStatic() {
    document.title = Lecart.lang === "fr" ? "L'Écart · Comparer" : "L'Écart · Compare";
    const hl = headline(), d = hl.market - hl.poll;
    document.getElementById("ovH1").textContent = tf(d >= 0 ? "gapUp" : "gapDown", { s: Lecart.surname(hl.c), v: t("verbW"), d: Math.abs(Math.round(d)) });
    document.getElementById("ovDek").innerHTML = t("subA");
    const F = Lecart.figures(DATA);
    document.getElementById("ovSnap").textContent = Lecart.fill(t("spSnap"), F);
    document.getElementById("ovSources").textContent = Lecart.fill(t("spSources"), F);
    document.getElementById("ovBarLabel").textContent = t(state.q === "qual" ? "ovBarQual" : "ovBarWin");
  }

  function rows() {
    const S = DATA.sim[state.u];
    return MARKET.map(m => { const s = S[m.c], a = DATA.avg[m.c]; return { c: m.c, f: m.f, market: m[state.q], poll: s ? s[state.q] : null, avg: a ? a[0] : null, n: a ? a[1] : 0 } })
      .sort((x, y) => Math.max(y.market, y.poll || 0) - Math.max(x.market, x.poll || 0));
  }

  function renderBoard() {
    const R = rows();
    let h = "";
    R.forEach(r => {
      const sub = r.avg != null ? tf("inPolls", { a: Lecart.pct1(r.avg), n: r.n }) : t("notPolled");
      const none = r.poll == null;
      const lo = none ? 0 : Math.min(r.poll, r.market), hi = none ? 0 : Math.max(r.poll, r.market);
      const ec = none ? null : r.market - r.poll;
      h += `<a class="sp-row" role="listitem" href="candidat.html?c=${encodeURIComponent(r.c)}">` +
        `<span class="name"><b>${r.c}</b><small>${sub}</small></span>` +
        `<span class="val mkt num">${r.market.toFixed(1)}</span>` +
        `<span class="val pol num${none ? " none" : ""}">${none ? "–" : r.poll.toFixed(1)}</span>` +
        `<span class="val ec num${none ? " none" : ""}">${none ? t("marketsOnly") : (ec >= 0 ? "+" : "−") + Math.abs(ec).toFixed(1)}</span>` +
        `<span class="sp-bartrack"><span class="base"></span>` +
        (none ? "" : `<span class="fill" style="left:${lo}%;width:${hi - lo}%"></span><span class="p" style="left:${r.poll}%"></span>`) +
        `<span class="m" style="left:${r.market}%"></span></span></a>`;
    });
    document.getElementById("ovBoard").innerHTML = h;
  }

  document.querySelectorAll("#ovQ [data-q]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("ov-q-" + b.dataset.q);
    state.q = b.dataset.q;
    document.querySelectorAll("#ovQ [data-q]").forEach(x => x.setAttribute("aria-pressed", x === b));
    document.getElementById("ovBarLabel").textContent = t(state.q === "qual" ? "ovBarQual" : "ovBarWin");
    renderBoard();
  }));
  document.querySelectorAll("#ovU [data-u]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("ov-u-" + b.dataset.u);
    state.u = b.dataset.u;
    document.querySelectorAll("#ovU [data-u]").forEach(x => x.setAttribute("aria-pressed", x === b));
    renderBoard();
  }));
  window.addEventListener("lecart-lang-change", () => { renderStatic(); renderBoard(); paintNav("apercu"); });

  paintNav("apercu");
  renderStatic();
  renderBoard();
})();
