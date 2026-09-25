(async () => {
  const { get, loadLang, t, tf, paintNav } = Lecart;
  let DATA;
  try { [DATA] = await Promise.all([get("data.json"), loadLang(Lecart.lang)]); }
  catch (e) { document.getElementById("rtBoard").innerHTML = "<p style=\"padding:16px\">Data could not be loaded. / Les données n'ont pas pu être chargées.</p>"; return; }

  // Election-silence period (see config.json): no poll-derived chances or market prices are rendered at all, only
  // the legal notice. Checked once at load; ?blackout=1/0 in the URL overrides the real date for testing.
  const blackout = await Lecart.checkBlackout();
  Lecart.paintBlackout(blackout);
  if (blackout) {
    document.title = Lecart.lang === "fr" ? "L'Écart · Publication suspendue" : "L'Écart · Publication suspended";
    paintNav("second-tour");
    window.addEventListener("lecart-lang-change", () => {
      document.title = Lecart.lang === "fr" ? "L'Écart · Publication suspendue" : "L'Écart · Publication suspended";
      paintNav("second-tour");
    });
    return;
  }

  const MARKET = DATA.markets.candidates;
  const num = x => Lecart.lang === "fr" ? x.toFixed(1).replace(".", ",") : x.toFixed(1);

  // The candidate common to every tested pairing (currently always Marine Le Pen) anchors the right side of
  // every row, so the table reads consistently top to bottom instead of the left/right side flipping per pair.
  function referenceCandidate(keys) {
    const counts = {};
    keys.forEach(key => key.split("|").forEach(n => counts[n] = (counts[n] || 0) + 1));
    const common = Object.keys(counts).filter(n => counts[n] === keys.length);
    if (common.length === 1) return common[0];
    return Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] || null;
  }

  function pairs() {
    const keys = Object.keys(DATA.pairs || {});
    const ref = referenceCandidate(keys);
    return keys.map(key => {
      const [a, b] = key.split("|"), [shareA, n] = DATA.pairs[key];
      const flip = ref != null && a !== ref;   // put the reference candidate second (right) in every row
      const left = flip ? a : b, right = flip ? b : a, shareLeft = flip ? shareA : 100 - shareA, shareRight = 100 - shareLeft;
      const m = MARKET.find(x => x.c === left), s = DATA.sim.mid[left], v = m ? m.venues : {};
      return { left, right, shareLeft, shareRight, n, winPoly: v.polymarket ? v.polymarket.win : null, winKal: v.kalshi ? v.kalshi.win : null, sim: s ? s.win : null };
    }).sort((x, y) => Math.max(y.shareLeft, y.shareRight) - Math.max(x.shareLeft, x.shareRight));
  }

  function headline(P) {
    if (!P.length) return null;
    const rights = new Set(P.map(r => r.right));
    if (rights.size === 1 && P.every(r => r.shareRight >= 50)) return { n: [...rights][0] };
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
      const rightWins = r.shareRight >= 50;
      h += `<div class="sp-pair-row" role="listitem"><span>` +
        `<span class="sp-pair-names">` +
        `<a${!rightWins ? ' class="win"' : ""} href="candidat.html?c=${encodeURIComponent(r.left)}">${r.left} <span class="num">${num(r.shareLeft)}</span></a>` +
        `<a${rightWins ? ' class="win"' : ""} href="candidat.html?c=${encodeURIComponent(r.right)}"><span class="num">${num(r.shareRight)}</span> ${r.right}</a>` +
        `</span>` +
        `<span class="sp-pair-split"><span${!rightWins ? ' class="win"' : ""} style="width:${r.shareLeft}%"></span><span${rightWins ? ' class="win"' : ""} style="width:${r.shareRight}%"></span></span>` +
        `</span>` +
        `<span class="sp-pair-n num">${r.n}</span>` +
        `<span class="sp-pair-sim num">${r.sim != null ? num(r.sim) : "–"}</span>` +
        `<span class="sp-pair-win">` +
        `<span class="pv poly">${t("ovColPoly")} ${r.winPoly != null ? `<span class="num">${num(r.winPoly)}</span>` : " " + t("venueFootnoteMark")}</span>` +
        `<span class="pv kal">${t("ovColKalshi")} ${r.winKal != null ? `<span class="num">${num(r.winKal)}</span>` : " " + t("venueFootnoteMark")}</span>` +
        `</span>` +
        `</div>`;
    });
    document.getElementById("rtBoard").innerHTML = h;
  }

  window.addEventListener("lecart-lang-change", () => { render(); paintNav("second-tour"); });
  paintNav("second-tour");
  render();
})();
