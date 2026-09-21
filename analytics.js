/* Cookie-free audience measurement (GoatCounter, EU-hosted). Loaded on every page, before its own script.
   Nothing is loaded or sent once the visitor has opted out. The choice lives in localStorage only. */
(function () {
  var KEY = "lecart-optout";
  function get() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  function set(off) {   // returns false when the browser blocks storage, so the page can say the choice was not saved
    try { if (off) localStorage.setItem(KEY, "1"); else localStorage.removeItem(KEY); return true; } catch (e) { return false; }
  }
  window.lecartOptOut = { get: get, set: set };
  if (get()) return;
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://gc.zgo.at/count.js";
  s.setAttribute("data-goatcounter", "https://vikander.goatcounter.com/count");
  document.head.appendChild(s);
})();
