// Shared helpers for apercu.html, candidat.html and second-tour.html: language, data loading, formatting.
// No Monte Carlo or model logic here (see CLAUDE.md): everything comes from data.json, written by scripts/build_data.py.
const Lecart = (() => {
  let lang = (() => { try { const s = localStorage.getItem("lecart-lang"); if (s === "fr" || s === "en") return s } catch (e) {} return (navigator.language || "fr").toLowerCase().startsWith("fr") ? "fr" : "en" })();
  const T = {};
  const nb = " ";
  // data.json and i18n/*.json change once a day: the version in <meta name="data-version"> (rewritten by build_data.py) lets browsers cache them, same as js/app.js.
  const VER = (document.querySelector('meta[name="data-version"]') || {}).content;
  const get = u => fetch(VER ? u + "?v=" + VER : u, { cache: VER ? "default" : "no-store" }).then(r => { if (!r.ok) throw new Error(u); return r.json() });
  const loadLang = async l => { if (!T[l]) T[l] = await get("i18n/" + l + ".json") };
  const t = k => T[lang][k];
  const tf = (k, o) => t(k).replace(/\{(\w+)\}/g, (m, x) => x in o ? o[x] : m);
  const setLang = l => { lang = l; try { localStorage.setItem("lecart-lang", l) } catch (e) {} };
  const pct = x => x > 0 && x < 1 ? (lang === "fr" ? "<1" + nb + "%" : "<1%") : Math.round(x) + (lang === "fr" ? nb + "%" : "%");
  const pct1 = x => lang === "fr" ? x.toFixed(1).replace(".", ",") + nb + "%" : x.toFixed(1) + "%";
  const surname = n => ({ "Marine Le Pen": "Le Pen", "Jean-Luc Mélenchon": "Mélenchon", "Dominique de Villepin": "de Villepin", "Nicolas Dupont-Aignan": "Dupont-Aignan" }[n] || n.split(" ").slice(-1)[0]);
  const longDate = iso => { const [y, m, d] = iso.split("-"); return (lang === "fr" && +d === 1 ? "1er" : +d) + " " + t("monthsL")[+m - 1] + " " + y };
  // Same figures as index.html's figures()/fr_figures() in build_data.py: kept in step so the "updated"/"meta" sentences read the same everywhere.
  const figures = DATA => {
    const ends = DATA.polls.map(p => p.end).sort(), lo = ends[0], hi = ends[ends.length - 1], mk = DATA.markets;
    const from = lo.slice(0, 4) === hi.slice(0, 4) ? longDate(lo).replace(/ \d{4}$/, "") : longDate(lo);
    const thin = (mk.thinThreshold || 0).toLocaleString(lang === "fr" ? "fr-FR" : "en-US");
    return { upd: longDate(DATA.updated), year: DATA.updated.slice(0, 4), snap: longDate(mk.snapshot), n: DATA.polls.length, from, to: longDate(hi), thin };
  };
  const fill = (s, figs) => s.replace(/\{\{(\w+)\}\}/g, (_, k) => figs[k]);
  // Aggregated GoatCounter event (cookie-free), same convention as js/app.js.
  const track = name => { try { if (window.lecartOptOut.get()) return; window.goatcounter.count({ path: name, title: name, event: true }) } catch (e) {} };

  function paintNav(active, figs) {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i]").forEach(el => { const v = t(el.dataset.i); if (typeof v === "string") el.innerHTML = figs ? fill(v, figs) : v });
    document.querySelectorAll("[data-lang]").forEach(b => b.setAttribute("aria-pressed", b.dataset.lang === lang));
    document.querySelectorAll("[data-nav]").forEach(a => { if (a.dataset.nav === active) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current") });
    const bar = document.querySelector(".sp-bar"), menuBtn = document.getElementById("spMenuBtn");
    if (menuBtn && !menuBtn.dataset.wired) {
      menuBtn.dataset.wired = "1";
      menuBtn.addEventListener("click", e => { e.stopPropagation(); bar.classList.toggle("open"); menuBtn.setAttribute("aria-expanded", String(bar.classList.contains("open"))) });
      document.addEventListener("click", e => { if (!bar.contains(e.target)) { bar.classList.remove("open"); menuBtn.setAttribute("aria-expanded", "false") } });
    }
    const optEl = document.getElementById("optOut"), optMsg = document.getElementById("optMsg");
    if (optEl) {
      optEl.textContent = t(window.lecartOptOut && window.lecartOptOut.get() ? "optIn" : "optOut");
      if (!optEl.dataset.wired) {
        optEl.dataset.wired = "1";
        optEl.addEventListener("click", e => {
          e.preventDefault();
          const O = window.lecartOptOut; if (!O) return;
          const ok = O.set(!O.get());
          optMsg.textContent = ok ? "" : " " + t("optFail");
          optEl.textContent = t(O.get() ? "optIn" : "optOut");
        });
      }
    }
  }
  document.querySelectorAll("[data-lang]").forEach(b => b.addEventListener("click", () => {
    track("lang-" + b.dataset.lang);
    loadLang(b.dataset.lang).then(() => { setLang(b.dataset.lang); window.dispatchEvent(new Event("lecart-lang-change")) });
  }));

  // Election-silence switch (French Act No. 77-808 of 19 July 1977): config.json lists the periods, in local wall-clock
  // time for its timezone, when poll-derived chances and market prices must not be published. checkBlackout() compares
  // "now" (converted to that timezone) against them; ?blackout=1/0 in the URL forces the state, for testing.
  // scripts/build_data.py reads the same file to also swap index.html's server-rendered headline/meta during a blackout.
  let blackoutConfig = null;
  async function loadBlackoutConfig() {
    if (!blackoutConfig) { try { blackoutConfig = await fetch("config.json").then(r => r.json()) } catch (e) { blackoutConfig = { blackout: { periods: [] } } } }
    return blackoutConfig;
  }
  function parisStamp(ms, timezone) {
    // "YYYY-MM-DDTHH:MM" in the given timezone: sortable, and directly comparable with config.json's period strings
    const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    const p = Object.fromEntries(fmt.formatToParts(new Date(ms)).map(x => [x.type, x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  }
  async function checkBlackout() {
    const qs = new URLSearchParams(location.search);
    if (qs.has("blackout")) return qs.get("blackout") !== "0";
    const cfg = (await loadBlackoutConfig()).blackout || {};
    const now = parisStamp(Date.now(), cfg.timezone || "Europe/Paris");
    return (cfg.periods || []).some(p => now >= p.start && now < p.end);
  }
  function paintBlackout(active) {
    const notice = document.getElementById("blackoutNotice"), main = document.getElementById("mainContent");
    if (!notice || !main) return;
    notice.hidden = !active;
    main.hidden = active;
  }

  return { get lang() { return lang }, T, t, tf, nb, get, loadLang, setLang, pct, pct1, surname, longDate, figures, fill, track, paintNav, checkBlackout, paintBlackout };
})();
