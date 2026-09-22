(async () => {
  const { get, loadLang, t, tf, paintNav } = Lecart;
  let DATA;
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("rtBoard").innerHTML = "<p style=\"padding:16px\">Data could not be loaded. / Les données n'ont pas pu être chargées.</p>"; return; }
  const MARKET = DATA.markets.candidates;
  const num = x => Lecart.lang === "fr" ? x.toFixed(1).replace(".", ",") : x.toFixed(1);

  function pairs() {
    return Object.keys(DATA.pairs || {}).map(key => {
      const [a, b] = key.split("|"), [share, n] = DATA.pairs[key];
      // The trailing candidate (share < 50) is the one whose simulated/market win chance the last two columns show,
      // same role the mockup called "the challenger" — generalised here since the leader isn't always the same name.
      const trailing = share >= 50 ? b : a;
      const m = MARKET.find(x => x.c === trailing), s = DATA.sim.mid[trailing];
      return { a, b, shareA: share, shareB: 100 - share, n, trailing, win: m ? m.win : null, sim: s ? s.win : null };
    }).sort((x, y) => Math.max(y.shareA, y.shareB) - Math.max(x.shareA, x.shareB));
  }

  function headline(P) {
    const leaders = new Set(P.map(r => r.shareA >= 50 ? r.a : r.b));
    if (leaders.size === 1) return { n: [...leaders][0] };
    return null;
  }

  function render() {
    document.title = Lecart.lang === "fr" ? "L'Écart · Second tour" : "L'Écart · Runoff";
    document.getElementById("rtKicker").textContent = t("ctx") + " · " + t("spNavRunoff");
    const P = pairs();
    const hl = headline(P);
    document.getElementById("rtH1").textContent = hl ? tf("rtH1AllOne", { n: hl.n }) : t("rtH1Mixed");
    const F = Lecart.figures(DATA);
    document.getElementById("rtSnap").textContent = Lecart.fill(t("spSnap"), F);
    document.getElementById("rtSources").textContent = Lecart.fill(t("spSources"), F);

    if (!P.length) { document.getElementById("rtBoard").innerHTML = ""; return; }
    let h = "";
    P.forEach(r => {
      const aWin = r.shareA >= 50;
      h += `<div class="sp-pair-row" role="listitem"><span>` +
        `<span class="sp-pair-names">` +
        `<a href="candidat.html?c=${encodeURIComponent(r.a)}" style="color:${aWin ? "var(--ink)" : "var(--muted2)"};font-weight:${aWin ? 700 : 500}">${r.a} <span class="num">${num(r.shareA)}</span></a>` +
        `<a href="candidat.html?c=${encodeURIComponent(r.b)}" style="color:${!aWin ? "var(--ink)" : "var(--muted2)"};font-weight:${!aWin ? 700 : 500}"><span class="num">${num(r.shareB)}</span> ${r.b}</a>` +
        `</span>` +
        `<span class="sp-pair-split"><span style="width:${r.shareA}%;background:${aWin ? "var(--ink)" : "var(--faint)"}"></span><span style="width:${r.shareB}%;background:${!aWin ? "var(--ink)" : "var(--faint)"}"></span></span>` +
        `</span>` +
        `<span class="sp-pair-n num">${r.n}</span>` +
        `<span class="sp-pair-sim num">${r.sim != null ? num(r.sim) : "–"}</span>` +
        `<span class="sp-pair-win num">${r.win != null ? num(r.win) : "–"}</span>` +
        `</div>`;
    });
    document.getElementById("rtBoard").innerHTML = h;
  }

  window.addEventListener("lecart-lang-change", () => { render(); paintNav("second-tour"); });
  paintNav("second-tour");
  render();
})();
