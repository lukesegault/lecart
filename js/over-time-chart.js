// Shared "markets and polls over time" chart: market vs. poll-implied chance of winning, week by week,
// used on index.html (candidate selector) and candidat.html (locked to the page's candidate, selector navigates).
// Data only (DATA.weekly, data/events.json); no simulation here — see CLAUDE.md.
(function () {
  const { t, tf, track } = Lecart;
  const nb = Lecart.nb;
  const DAYS = { "1M": 30, "3M": 91, "6M": 183, ALL: 1e9 };
  const dvTs = d => Date.parse(d + "T00:00:00Z");
  const xml = v => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const dvDate = (d, lang) => { const [yy, mm, dd] = d.split("-"); return (+dd) + " " + t("months")[+mm - 1] + " " + yy };
  const dvSigned = (d, lang) => { const r = Math.round(d * 10) / 10, a = Math.abs(r).toFixed(1); return (r > 0 ? "+" : r < 0 ? "−" : "") + (lang === "fr" ? a.replace(".", ",") : a) + nb + "pts" };
  const dvLastIdx = a => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null) return i; return -1 };
  const pathOf = (s, x, y, gap) => { let d = "", prev = -1, last = null; s.forEach((v, i) => { if (v == null) return; d += (prev >= 0 && i - prev <= gap ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1) + " "; prev = i; last = i }); return { d, last } };

  const PAGE_COL = { poll: "var(--ink)", market: "var(--mint)", fill: "var(--mint-tint)", rule: "var(--rule2)", muted: "var(--muted)", faint: "var(--faint)", ink: "var(--ink)", surface: "var(--surface)", orange: "var(--orange)" };
  const LIGHT_COL = { poll: "#111418", market: "#0FA37F", fill: "#E6F7F1", rule: "#EDEFEE", muted: "#8C9491", faint: "#C8CFCC", ink: "#111418", surface: "#FFFFFF", orange: "#F26B1D" };

  function chartSvg(o) {
    const { W, H, weeks, poll, market, col, interactive } = o, ml = 42, mr = 14, mt = 30, mb = 26, n = weeks.length;
    const t0 = dvTs(weeks[0]), t1 = dvTs(weeks[n - 1]), span = Math.max(1, t1 - t0), days = span / 864e5;
    const px = tt => ml + (tt - t0) / span * (W - ml - mr), x = i => px(dvTs(weeks[i]));
    const y = v => mt + (1 - v / 100) * (H - mt - mb);   // fixed 0-100: these are probabilities, not first-round scores
    let g = "";
    [0, 25, 50, 75, 100].forEach(v => { g += `<line x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}" stroke="${col.rule}"/><text x="${ml - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="${col.muted}">${v}</text>` });
    const tick = (xx, label) => `<line x1="${xx}" x2="${xx}" y1="${H - mb}" y2="${H - mb + 4}" stroke="${col.faint}"/>` + (label ? `<text x="${xx}" y="${H - 8}" text-anchor="middle" font-size="10.5" fill="${col.muted}">${label}</text>` : "");
    const monthLab = (m, i) => { const [yy, mm] = m.split("-"); return t("months")[+mm - 1] + ((mm === "01" || i === 0) ? " " + yy.slice(2) : "") };
    if (days <= 45) weeks.forEach((w, i) => { const [, mm, dd] = w.split("-"); g += tick(x(i), (+dd) + " " + t("months")[+mm - 1]) });
    else { const d0 = new Date(t0); for (let k = 1; ; k++) { const dt = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth() + k, 1)); if (+dt > t1) break; const mo = dt.getUTCMonth() + 1; g += tick(px(+dt), (days <= 240 || mo % 2 === 1) ? monthLab(dt.getUTCFullYear() + "-" + String(mo).padStart(2, "0"), 1) : ""); } }
    const P = poll.map((v, i) => v == null || market[i] == null ? null : i).filter(i => i != null);
    for (let k = 0; k < P.length;) { let e = k; while (e + 1 < P.length && P[e + 1] - P[e] <= 2) e++;
      if (e > k) { const fwd = [], back = []; for (let j = k; j <= e; j++) fwd.push(x(P[j]).toFixed(1) + " " + y(poll[P[j]]).toFixed(1));
        for (let i = P[e]; i >= P[k]; i--) if (market[i] != null) back.push(x(i).toFixed(1) + " " + y(market[i]).toFixed(1));
        if (back.length) g += `<path d="M${fwd.join(" L")} L${back.join(" L")} Z" fill="${col.fill}" stroke="none"/>`; }
      k = e + 1; }
    const M = pathOf(market, x, y, 2), Pp = pathOf(poll, x, y, 1);
    g += `<path d="${M.d}" fill="none" stroke="${col.market}" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round"/><path d="${Pp.d}" fill="none" stroke="${col.poll}" stroke-width="1.75" stroke-linejoin="round" stroke-linecap="round"/>`;
    if (M.last != null) { const cx = x(M.last), cy = y(market[M.last]); g += `<rect x="${cx - 4}" y="${cy - 4}" width="8" height="8" fill="${col.market}" stroke="${col.surface}" stroke-width="1.5" transform="rotate(45 ${cx} ${cy})"/>`; }
    poll.forEach((v, i) => { if (v != null && (i === Pp.last || (poll[i - 1] == null && poll[i + 1] == null))) g += `<rect x="${(x(i) - 2.5).toFixed(1)}" y="${(y(v) - 2.5).toFixed(1)}" width="5" height="5" fill="${col.poll}" stroke="${col.surface}" stroke-width="1.5"/>`; });
    if (interactive) g += `<line id="otGuide" y1="${mt}" y2="${H - mb}" stroke="${col.ink}" stroke-opacity=".35" visibility="hidden"/><g id="otDots"></g>`;
    (o.events || []).forEach((e, i) => { const tt = dvTs(e.date); if (tt < t0 || tt > t1) return; const xx = px(tt), cy = mt - 14;
      g += `<line x1="${xx}" x2="${xx}" y1="${cy + 8}" y2="${H - mb}" stroke="${col.orange}" stroke-dasharray="2 3" stroke-opacity=".6"/>` +
        `<g class="otm" data-e="${i}"${interactive ? ` role="button" tabindex="0" aria-label="${xml(e[o.lang])}"` : ""}><circle cx="${xx}" cy="${cy}" r="13" fill="transparent"/><circle cx="${xx}" cy="${cy}" r="8" fill="${col.surface}" stroke="${col.orange}" stroke-width="1.5"/><text x="${xx}" y="${cy + 3.5}" text-anchor="middle" font-size="10" font-weight="700" fill="${col.orange}">${i + 1}</text></g>`; });
    return { svg: g, geo: { W, H, ml, mr, mt, mb, x, y, n } };
  }

  function summary(D) {
    const im = dvLastIdx(D.market), ip = dvLastIdx(D.poll);
    let ib = D.weeks.length - 1; while (ib >= 0 && (D.market[ib] == null || D.poll[ib] == null)) ib--;
    return { im, ip, m: im < 0 ? null : D.market[im], p: ip < 0 ? null : D.poll[ip], mw: im < 0 ? "" : D.weeks[im], pw: ip < 0 ? "" : D.weeks[ip], gap: ib < 0 ? null : D.market[ib] - D.poll[ib] };
  }

  /** Mounts the chart into #<elId>. opts: {DATA, EVENTS, candidates:[names], initial, lang, onNav(name)?}.
   * When onNav is given, clicking a candidate tab navigates there (candidat.html) instead of switching in place (index.html). */
  Lecart.mountOverTimeChart = function (elId, opts) {
    const root = document.getElementById(elId);
    const state = { cand: opts.initial, tf: "ALL", hov: null, w: 0 };
    const EVENTS = (opts.EVENTS || []).slice().sort((a, b) => a.date < b.date ? -1 : 1);

    function data() {
      const WK = opts.DATA.weekly; if (!WK || !WK.series[state.cand]) return null;
      const s = WK.series[state.cand], cut = dvTs(WK.weeks[WK.weeks.length - 1]) - DAYS[state.tf] * 864e5;
      const a = Math.max(0, WK.weeks.findIndex(w => dvTs(w) >= cut));
      return { weeks: WK.weeks.slice(a), poll: s.poll.slice(a), market: s.market.slice(a) };
    }

    function readout(idx, D) {
      const guide = root.querySelector("#otGuide"), dots = root.querySelector("#otDots"), out = root.querySelector(".sp-chart-readout");
      if (!guide) return;
      if (idx == null) { guide.setAttribute("visibility", "hidden"); dots.innerHTML = "";
        const S = summary(D); out.innerHTML = S.m == null || S.p == null ? "" : tf("dvLast", { m: Lecart.pct1(S.m), mw: dvDate(S.mw), p: Lecart.pct1(S.p), pw: dvDate(S.pw) }); return; }
      const G = root._otGeo, m = D.market[idx], p = D.poll[idx], xx = G.x(idx);
      guide.setAttribute("x1", xx); guide.setAttribute("x2", xx); guide.setAttribute("visibility", "visible");
      dots.innerHTML = (m != null ? `<circle cx="${xx}" cy="${G.y(m)}" r="4.5" fill="var(--mint)" stroke="var(--surface)" stroke-width="2"/>` : "") + (p != null ? `<circle cx="${xx}" cy="${G.y(p)}" r="4.5" fill="var(--ink)" stroke="var(--surface)" stroke-width="2"/>` : "");
      out.innerHTML = tf("dvAt", { w: dvDate(D.weeks[idx]), m: m == null ? "–" : Lecart.pct1(m), p: p == null ? t("dvNoPoll") : Lecart.pct1(p), g: m != null && p != null ? dvSigned(m - p, Lecart.lang) : "–" });
    }

    function eventNote(D) {
      const box = root.querySelector(".sp-chart-note"); if (!box) return;
      const i = state.hov != null ? state.hov : EVENTS.length - 1, e = i >= 0 ? EVENTS[i] : null;
      root.querySelectorAll(".otm").forEach(gm => gm.classList.toggle("on", +gm.dataset.e === i));
      box.innerHTML = e ? `<strong>${xml(e[Lecart.lang])}</strong><span class="d">${dvDate(e.date)}</span><p>${xml(e[Lecart.lang === "fr" ? "noteFr" : "noteEn"] || "")}</p>` : `<span style="color:var(--muted)">${t("dvHint")}</span>`;
    }

    function drawChart(D) {
      const box = root.querySelector(".sp-chart-box");
      const W = Math.max(280, Math.round(box.clientWidth) || 640), H = W < 520 ? 230 : 300;
      const C = chartSvg({ W, H, weeks: D.weeks, poll: D.poll, market: D.market, events: EVENTS, col: PAGE_COL, interactive: true, lang: Lecart.lang });
      box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${xml(tf("dvAria", { n: state.cand }))}">${C.svg}</svg>`;
      root._otGeo = C.geo; state.w = Math.round(box.clientWidth);
      const svg = box.querySelector("svg");
      const near = e => { const r = svg.getBoundingClientRect(), px = (e.clientX - r.left) / r.width * W; let b = 0; for (let i = 1; i < D.weeks.length; i++) if (Math.abs(C.geo.x(i) - px) < Math.abs(C.geo.x(b) - px)) b = i; return b };
      svg.addEventListener("pointermove", e => readout(near(e), D));
      svg.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") readout(null, D) });
      svg.querySelectorAll(".otm").forEach(gm => { const i = +gm.dataset.e;
        gm.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") { state.hov = i; eventNote(D) } });
        gm.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") { state.hov = null; eventNote(D) } });
        gm.addEventListener("focus", () => { state.hov = i; eventNote(D) }); gm.addEventListener("blur", () => { state.hov = null; eventNote(D) });
        gm.addEventListener("click", () => { state.hov = state.hov === i ? null : i; eventNote(D) }); });
      readout(null, D); eventNote(D);
      if (!root._ro && window.ResizeObserver) { root._ro = new ResizeObserver(() => { const w = Math.round(box.clientWidth); if (w && Math.abs(w - state.w) > 2) drawChart(data()) }); root._ro.observe(box); }
    }

    function render() {
      const D = data();
      root.querySelector(".sp-chart-title").textContent = state.cand;
      const pill = root.querySelector(".sp-chart-pill");
      if (D) { const gap = summary(D).gap; pill.hidden = gap == null; if (gap != null) { pill.textContent = t("gapCol") + " " + dvSigned(gap, Lecart.lang); pill.classList.toggle("neg", gap < 0) } }
      else pill.hidden = true;
      const cTabs = root.querySelector(".sp-chart-cands");
      cTabs.setAttribute("aria-label", t("dvCand"));
      cTabs.innerHTML = (opts.candidates || []).map(n => `<button type="button" data-c="${xml(n)}" aria-pressed="${n === state.cand}">${xml(Lecart.surname(n))}</button>`).join("");
      cTabs.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
        track("ot-c"); if (opts.onNav) { opts.onNav(b.dataset.c); return; } state.cand = b.dataset.c; render();
      }));
      const tfTabs = root.querySelector(".sp-chart-tf");
      tfTabs.setAttribute("aria-label", t("dvPeriod"));
      tfTabs.querySelectorAll("button").forEach(b => { b.setAttribute("aria-pressed", String(b.dataset.tf === state.tf)); b.onclick = () => { track("ot-tf-" + b.dataset.tf); state.tf = b.dataset.tf; render() }; });
      root._exportState = { cand: state.cand, tf: state.tf };
      if (!D) { root.querySelector(".sp-chart-box").innerHTML = `<p style="padding:16px;color:var(--muted)">${t("cdNoTrend")}</p>`; return; }
      drawChart(D);
    }
    root._render = render;
    root._setCand = n => { state.cand = n; render() };
    render();
    return { setCandidate: root._setCand };
  };

  let FONTS = null;
  async function embedFonts() {
    if (FONTS) return FONTS;
    const b64 = async u => { const r = await fetch(u); if (!r.ok) throw new Error(u); const by = new Uint8Array(await r.arrayBuffer()); let s = ""; for (let i = 0; i < by.length; i += 0x8000) s += String.fromCharCode.apply(null, by.subarray(i, i + 0x8000)); return btoa(s) };
    return FONTS = { sans: await b64("fonts/archivo-latin.woff2"), serif: await b64("fonts/instrument-serif-400-latin.woff2") };
  }

  Lecart.exportOverTimeChart = async function (elId, opts, btnId, msgId) {
    const root = document.getElementById(elId), btn = document.getElementById(btnId), msg = document.getElementById(msgId);
    if (btn.disabled) return;
    btn.disabled = true; msg.textContent = "";
    try {
      const WK = opts.DATA.weekly; if (!WK) throw new Error("no data");
      const state = root._exportState || {};
      const cand = state.cand, tfKey = state.tf;
      let F = null; try { F = await embedFonts(); } catch (e) {}
      const W = 1200, H = 675, S = 2, pad = 48, cw = W - 2 * pad, ch = 300, C = LIGHT_COL;
      const face = F ? `<style>@font-face{font-family:"Archivo";font-weight:400 900;src:url(data:font/woff2;base64,${F.sans}) format("woff2")}@font-face{font-family:"Instrument Serif";font-weight:400;src:url(data:font/woff2;base64,${F.serif}) format("woff2")}</style>` : "";
      const EVENTS = (opts.EVENTS || []);
      const s = WK.series[cand], cut = dvTs(WK.weeks[WK.weeks.length - 1]) - DAYS[tfKey] * 864e5, a = Math.max(0, WK.weeks.findIndex(w => dvTs(w) >= cut));
      const Dx = { weeks: WK.weeks.slice(a), poll: s.poll.slice(a), market: s.market.slice(a) };
      const chart = chartSvg({ W: cw - 24, H: ch, weeks: Dx.weeks, poll: Dx.poll, market: Dx.market, events: EVENTS, col: C, interactive: false, lang: Lecart.lang }).svg;
      const Z = summary(Dx), gap = Z.gap, cardY = 150, legY = cardY + ch + 24 + 28;
      let pillSvg = ""; if (gap != null) { const txt = xml(t("gapCol") + " " + dvSigned(gap, Lecart.lang)), w = txt.length * 9.6 + 30, neg = gap < 0;
        pillSvg = `<rect x="${W - pad - w}" y="78" width="${w}" height="34" rx="0" fill="${neg ? "rgba(17,20,24,.08)" : C.fill}"/><text x="${W - pad - w / 2}" y="100" text-anchor="middle" font-size="17" font-weight="700" fill="${neg ? C.ink : "#0B7A5F"}">${txt}</text>`; }
      const legend = `<rect x="${pad}" y="${legY - 12}" width="18" height="8" fill="${C.market}" transform="rotate(45 ${pad + 9} ${legY - 8})"/><text x="${pad + 26}" y="${legY}" font-size="13" fill="${C.muted}">${xml(t("dvLegM"))}</text>` +
        `<rect x="${pad + 260}" y="${legY - 13}" width="10" height="10" fill="${C.poll}"/><text x="${pad + 278}" y="${legY}" font-size="13" fill="${C.muted}">${xml(t("dvLegP"))}</text>` +
        `<rect x="${pad + 560}" y="${legY - 13}" width="22" height="11" fill="${C.fill}" stroke="${C.market}"/><text x="${pad + 590}" y="${legY}" font-size="13" fill="${C.muted}">${xml(t("dvLegG"))}</text>`;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="Archivo,Helvetica,Arial,sans-serif">${face}` +
        `<rect width="${W}" height="${H}" fill="#FFFFFF"/>` +
        `<circle cx="${pad + 6}" cy="${pad + 6}" r="5" fill="${C.poll}"/><rect x="${pad + 20}" y="${pad}" width="10" height="10" fill="${C.market}" transform="rotate(45 ${pad + 25} ${pad + 5})"/><text x="${pad + 40}" y="${pad + 10}" font-size="15" font-weight="800" letter-spacing="1" fill="${C.ink}">L'ÉCART</text>` +
        `<text x="${pad}" y="112" font-family="'Instrument Serif',Georgia,serif" font-size="42" font-weight="400" fill="${C.ink}">${xml(cand)}</text>${pillSvg}` +
        `<text x="${pad}" y="134" font-size="14" fill="${C.muted}">${xml(t("dvCap"))}</text>` +
        `<g transform="translate(${pad + 12} ${cardY + 12})">${chart}</g>` +
        `${legend}` +
        `<line x1="${pad}" x2="${W - pad}" y1="${H - 56}" y2="${H - 56}" stroke="${C.rule}"/>` +
        `<text x="${pad}" y="${H - 32}" font-size="12" fill="${C.muted}">${xml(t("dvSrc"))} ${xml(t("dvAsOf"))} ${dvDate(opts.DATA.updated)}.</text>` +
        `<text x="${W - pad}" y="${H - 32}" text-anchor="end" font-size="12" fill="${C.muted}">lukesegault.github.io/lecart</text></svg>`;
      const img = new Image(); img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg); await img.decode();
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const cv = document.createElement("canvas"); cv.width = W * S; cv.height = H * S; cv.getContext("2d").drawImage(img, 0, 0, W * S, H * S);
      const blob = await new Promise(r => cv.toBlob(r, "image/png")); if (!blob) throw new Error("toBlob");
      const a2 = document.createElement("a"), slug = Lecart.surname(cand).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
      a2.href = URL.createObjectURL(blob); a2.download = `lecart-${slug}-${opts.DATA.updated}.png`; document.body.appendChild(a2); a2.click(); a2.remove(); setTimeout(() => URL.revokeObjectURL(a2.href), 4000);
    } catch (e) { msg.textContent = t("dvExpFail") } finally { btn.disabled = false }
  };
})();
