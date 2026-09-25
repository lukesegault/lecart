"""Typography audit: loads every page in a real browser and lists each distinct family + size + weight combination
actually rendered (css/type.css is the scale; this is the check that the pages stay on it).

    pip install -r requirements-dev.txt
    python -m playwright install chromium
    python scripts/audit_type.py

Fails (exit 1) if, on any page or across the site, there are more than MAX_COMBOS combinations; if any text renders
smaller than MIN_PX (SVG text is measured after the chart's own scaling, so a shrunken chart fails too); or if a
combination is outside the allowed scale below (the same table as css/type.css) or breaks a role (mono for words).
Pages are loaded in French and English, at desktop and phone width, light scheme; hidden content (the extra table
rows, the Method's details) is opened first, and the other market tab, the chart's hover readout and event note are
opened too, so their type is counted. Analytics is stubbed, as in check_site.py.
"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from check_site import serve, new_page, ROOT  # noqa: F401  (ROOT re-exported for readers)

MAX_COMBOS = 12
MIN_PX = 11
PAGES = ["index.html", "candidat.html?c=Marine%20Le%20Pen", "second-tour.html", "notes.html"]
VIEWPORTS = {"desktop": (1280, 900), "phone": (390, 844)}
LANGS = ("fr", "en")

# family -> allowed (size px, weight); the same scale as css/type.css
ALLOWED = {
    "Bodoni Moda": {(44, 500), (30, 500)},
    "Source Serif 4": {(17, 400), (15, 400)},
    "IBM Plex Sans": {(13, 400), (13, 600), (11, 400), (11, 600)},
    "IBM Plex Mono": {(15, 400), (15, 600), (13, 400), (13, 600), (11, 400), (11, 600)},
}

# One record per rendered text node: family, effective size, weight, a short sample, a selector to find it again.
COLLECT = """
() => {
  const out = [], skip = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TITLE", "HEAD", "META", "LINK"]);
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const sel = el => { const p = []; while (el && el !== document.body && p.length < 4) { p.unshift(el.tagName.toLowerCase() + (el.id ? "#" + el.id : el.classList.length ? "." + [...el.classList].join(".") : "")); el = el.parentElement } return p.join(" > ") };
  for (let n; (n = w.nextNode());) {
    const text = n.nodeValue.replace(/\\s+/g, " ").trim(); if (!text) continue;
    const el = n.parentElement; if (!el || skip.has(el.tagName) || el.closest("[hidden],noscript,script,style")) continue;
    const cs = getComputedStyle(el); if (cs.display === "none" || cs.visibility === "hidden") continue;
    const r = document.createRange(); r.selectNodeContents(n);
    const b = r.getBoundingClientRect(); if (!b.width || !b.height) continue;
    let size = parseFloat(cs.fontSize);
    if (el instanceof SVGElement) { const m = (el.ownerSVGElement || el).getScreenCTM(); if (m) size *= Math.hypot(m.a, m.b) }
    out.push({ family: cs.fontFamily.split(",")[0].replace(/["']/g, "").trim(), size: Math.round(size * 100) / 100, weight: +cs.fontWeight, text: text.slice(0, 40), sel: sel(el) });
  }
  return out;
}
"""


def open_everything(page):
    """Reveal content that is collapsed by default so its type is audited too."""
    page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    more = page.locator("#ovMore")
    if more.count() and more.first.is_visible():
        more.first.click()
    page.wait_for_timeout(150)


def states(page, path):
    """Yield after the page loads and after each interaction that renders different text (the other market tab, the
    chart's hover readout and event note), so type that only appears on interaction is audited too."""
    yield
    if page.locator("#ovQ [data-q=qual]").count() or page.locator("#cdQ [data-q=qual]").count():
        page.locator("#ovQ [data-q=qual], #cdQ [data-q=qual]").first.click()
        page.wait_for_timeout(150)
        yield
    box = page.locator(".sp-chart-box svg")
    if box.count():
        b = box.first.bounding_box()
        page.mouse.move(b["x"] + b["width"] * 0.6, b["y"] + b["height"] * 0.5)
        page.wait_for_timeout(150)
        yield
    marker = page.locator(".sp-chart-box .otm, .sp-trend-wrap .ctm")
    if marker.count():
        marker.first.focus()
        page.wait_for_timeout(150)
        yield


def audit():
    srv, base = serve()
    seen, offenders, per_page, low = {}, {}, {}, {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for lang in LANGS:
                for vname, size in VIEWPORTS.items():
                    for path in PAGES:
                        ctx, page, problems = new_page(browser, base, size, lang)
                        page.add_init_script(f"try{{localStorage.setItem('lecart-lang','{lang}')}}catch(e){{}}")
                        page.goto(base + path)
                        page.wait_for_load_state("networkidle")
                        page.evaluate("document.fonts.ready")
                        page.wait_for_timeout(400)
                        open_everything(page)
                        page.evaluate("document.fonts.ready")
                        name = path.split("?")[0]
                        for _ in states(page, path):
                            for rec in page.evaluate(COLLECT):
                                combo = (rec["family"], round(rec["size"], 1), rec["weight"])
                                seen.setdefault(combo, []).append((name, vname, lang, rec))
                                per_page.setdefault(name, {}).setdefault(combo, 0)
                                per_page[name][combo] += 1
                        ctx.close()
            browser.close()
    finally:
        srv.shutdown()
    return seen, per_page


def fmt(combo):
    fam, size, weight = combo
    return f"{fam:<15} {size:>5g}px  {weight}"


def main():
    seen, per_page = audit()
    fails = []
    print("Type audit: every distinct family / size / weight combination rendered\n")
    print(f"{'combination':<31} {'nodes':>6}  first seen")
    for combo in sorted(seen, key=lambda c: (c[0], -c[1], c[2])):
        uses = seen[combo]
        first = uses[0]
        print(f"{fmt(combo):<31} {len(uses):>6}  {first[0]} ({first[1]}/{first[2]}): {first[3]['sel']}  \"{first[3]['text']}\"")
        fam, size, weight = combo
        if size < MIN_PX:
            fails.append(f"text under {MIN_PX}px: {fmt(combo)} ({len(uses)} nodes, e.g. {first[0]} {first[3]['sel']} \"{first[3]['text']}\")")
        if (round(size), weight) not in ALLOWED.get(fam, set()) or abs(size - round(size)) > 0.05:
            fails.append(f"off the scale: {fmt(combo)} ({len(uses)} nodes, e.g. {first[0]} {first[3]['sel']} \"{first[3]['text']}\")")
        if fam == "IBM Plex Mono":
            for _, v, l, rec in uses:
                if re.search(r"[A-Za-zÀ-ÿ]{2,}", rec["text"]):
                    fails.append(f"mono used for words: \"{rec['text']}\" in {rec['sel']} ({v}/{l})"); break
    print()
    for name, combos in per_page.items():
        print(f"{name:<18} {len(combos):>2} combinations")
        if len(combos) > MAX_COMBOS:
            fails.append(f"{name}: {len(combos)} combinations (max {MAX_COMBOS})")
    print(f"{'whole site':<18} {len(seen):>2} combinations (max {MAX_COMBOS})")
    if len(seen) > MAX_COMBOS:
        fails.append(f"site: {len(seen)} combinations (max {MAX_COMBOS})")
    if fails:
        print("\nFAILED")
        for f in fails: print(" -", f)
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
