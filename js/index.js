(async () => {
  const { get, loadLang, t, tf, paintNav } = Lecart;
  let DATA, EVENTS = [];
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("ovBoard").innerHTML = "<p style=\"padding:16px\">Data could not be loaded. / Les données n'ont pas pu être chargées.</p>"; return; }
  try { EVENTS = await get("data/events.json"); } catch (e) {}
  const MARKET = DATA.markets.candidates;
  const state = { q: "qual", u: "mid" };
  const WK_NAMES = Object.keys(DATA.weekly ? DATA.weekly.series : {});

  function headline() {
    const S = DATA.sim.mid;
    const rows = MARKET.map(m => ({ c: m.c, market: m.win, poll: S[m.c] ? S[m.c].win : null })).filter(r => r.poll != null);
    rows.sort((a, b) => Math.abs(b.market - b.poll) - Math.abs(a.market - a.poll));
    return rows[0];
  }

  function renderStatic() {
    document.title = Lecart.lang === "fr" ? "L'Écart · Marchés vs sondages, présidentielle 2027" : "L'Écart · Markets vs polls, French election 2027";
    const hl = headline(), d = hl.market - hl.poll;
    document.getElementById("siteH1").textContent = tf(d >= 0 ? "gapUp" : "gapDown", { s: Lecart.surname(hl.c), v: t("verbW"), d: Math.abs(Math.round(d)) });
    const F = Lecart.figures(DATA);
    document.getElementById("siteSnap").textContent = Lecart.fill(t("spSnap"), F);
    document.getElementById("siteSources").textContent = Lecart.fill(t("spSources"), F);
    document.getElementById("ovBarLabel").textContent = t(state.q === "qual" ? "ovBarQual" : "ovBarWin");
    renderStale(F);
    return hl;
  }

  function renderStale() {
    let el = document.getElementById("stale");
    const old = (Date.now() - Date.parse(DATA.updated + "T00:00:00Z")) / 864e5 > 2;
    if (!old) { if (el) el.remove(); return }
    if (!el) { el = document.createElement("p"); el.id = "stale"; el.className = "sp-footnote"; el.style.color = "var(--orange)"; el.style.marginTop = "6px"; document.querySelector(".sp-meta").after(el) }
    el.textContent = t("stale");
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
        `<span class="val mkt num">${Lecart.pct(r.market)}</span>` +
        `<span class="val pol num${none ? " none" : ""}">${none ? "–" : Lecart.pct(r.poll)}</span>` +
        `<span class="val ec num${none ? " none" : ""}">${none ? t("marketsOnly") : (ec >= 0 ? "+" : "−") + Math.round(Math.abs(ec)) + (Lecart.lang === "fr" ? Lecart.nb + "%" : "%")}</span>` +
        `<span class="sp-bartrack"><span class="base"></span>` +
        (none ? "" : `<span class="fill" style="left:${lo}%;width:${hi - lo}%"></span><span class="tick-p" style="left:${r.poll}%"></span>`) +
        `<span class="tick-m" style="left:${r.market}%"></span></span></a>`;
    });
    document.getElementById("ovBoard").innerHTML = h;
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
    renderBoard();
  }));
  document.querySelectorAll("#ovU [data-u]").forEach(b => b.addEventListener("click", () => {
    Lecart.track("ov-u-" + b.dataset.u);
    state.u = b.dataset.u;
    document.querySelectorAll("#ovU [data-u]").forEach(x => x.setAttribute("aria-pressed", x === b));
    renderBoard();
  }));
  window.addEventListener("lecart-lang-change", () => {
    renderStatic(); renderBoard(); table(); paintNav("home", Lecart.figures(DATA));
    const root = document.getElementById("otChart"); if (root._render) root._render();
  });

  paintNav("home", Lecart.figures(DATA));
  const hl = renderStatic();
  renderBoard();
  table();
  mountChart(hl);
})();
