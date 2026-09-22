"""Local browser check: loads every page, clicks every control, in French and English, at desktop and phone
width, in light and dark colour scheme, and fails on any console error, uncaught exception or failed request.

    pip install -r requirements-dev.txt
    python -m playwright install chromium
    python scripts/check_site.py

Analytics is stubbed (the GoatCounter requests are answered locally, never sent), so a check run is not counted.
"""
import functools, http.server, pathlib, sys, threading
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
STUB_COUNT_JS = "window.goatcounter={count:function(){}};"
VIEWPORTS = {"desktop": (1280, 900), "phone": (390, 844)}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def stub_analytics(page):
    page.route("https://gc.zgo.at/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=STUB_COUNT_JS))
    page.route("https://*.goatcounter.com/**", lambda r: r.fulfill(status=204, body=""))


def new_page(browser, base, size, lang, scheme="light", clock_shift_days=0):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, locale=f"{lang}-{lang.upper()}", accept_downloads=True, color_scheme=scheme)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"exception: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"request failed: {r.url}"))
    page.on("response", lambda r: problems.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    stub_analytics(page)
    if clock_shift_days:
        page.add_init_script(f"(()=>{{const n=Date.now.bind(Date);Date.now=()=>n()+{clock_shift_days}*864e5}})()")
    return ctx, page, problems


def check_no_overflow(page, bad, label):
    w = page.evaluate("document.documentElement.scrollWidth"), page.evaluate("innerWidth")
    if w[0] > w[1] + 2:
        bad.append(f"{label}: horizontal overflow ({w[0]}px content in {w[1]}px viewport)")


def click_index(page, phone, bad):
    def check(cond, msg):
        if not cond: bad.append(msg)
    check(page.locator("#ovBoard .sp-row").count() == 8, "index: overview table does not show the top 8 rows by default")
    for q in ("qual", "win"):
        for u in ("low", "mid", "high"):
            page.click(f'#ovQ [data-q="{q}"]'); page.click(f'#ovU [data-u="{u}"]')
            check(page.locator("#ovBoard .sp-row").count() == 8, f"index: board not capped at 8 rows for {q}/{u}")
    check(not page.is_hidden("#ovMore"), "index: show-all toggle missing")
    page.click("#ovMore")
    check(page.locator("#ovBoard .sp-row").count() >= 15, "index: show-all toggle did not reveal every row")
    page.click("#ovMore")
    check(page.locator("#ovBoard .sp-row").count() == 8, "index: show-fewer toggle did not collapse back to 8")
    check(page.locator('[data-i="subA"] .lm').count() == 1 and page.locator('[data-i="subA"] .lp').count() == 1,
          "index: table intro text lost its mint-mark/black-tick emphasis spans")
    for i in range(min(3, page.locator("#otCands button").count())):
        page.click(f"#otCands button >> nth={i}")
        check(page.locator(".sp-chart-box svg path").count() > 0, f"index: over-time chart empty for candidate {i}")
        labels = page.locator(".sp-chart-box svg text", has_text="%").count()
        check(labels >= 1, f"index: over-time chart has no direct end-of-line label for candidate {i}")
    for tf in ("1M", "3M", "6M", "ALL"):
        page.click(f'#otTf button[data-tf="{tf}"]')
    with page.expect_download(timeout=15000) as dl:
        page.click("#otExportBtn")
    check(dl.value.suggested_filename.endswith(".png"), "index: export is not a PNG")
    check(page.inner_text("#otExportMsg").strip() == "", "index: export reported an error")
    page.click("details summary"); check(page.locator("#polltable tbody tr").count() > 0, "index: poll table empty")
    page.click("#optOut"); page.click("#optOut")
    check(page.locator('#spNav a[href="index.html"]').count() == 1, "index: nav missing Compare link")
    check(page.locator('#spNav a[href="second-tour.html"]').count() == 1, "index: nav missing Runoff link")
    check(page.get_attribute('#spNav a[href="index.html"]', "aria-current") == "page", "index: Compare nav item not marked current")
    check("serif" in (page.eval_on_selector("#h-compare", "el => getComputedStyle(el).fontFamily") or "").lower(), "index: section h2 is not set in the serif face")
    if phone:
        page.click("#spMenuBtn"); check(page.get_attribute("#spMenuBtn", "aria-expanded") == "true", "index: menu did not open")
        page.click('#spNav a[href="second-tour.html"]')
        page.wait_for_selector(".sp-pair-row")   # navigation succeeded; a timeout here fails the run
    check_no_overflow(page, bad, "index")


def click_candidat(page, phone, bad):
    def check(cond, msg):
        if not cond: bad.append(msg)
    page.wait_for_selector("#cdName")
    check(page.inner_text("#cdName").strip() != "", "candidat: no name rendered")
    for q in ("qual", "win"):
        for u in ("low", "mid", "high"):
            page.click(f'#cdQ [data-q="{q}"]'); page.click(f'#cdU [data-u="{u}"]')
            check(page.inner_text("#cdH1").strip() != "", f"candidat: H1 empty for {q}/{u}")
    check(page.locator(".sp-chart-box svg path").count() > 0, "candidat: over-time chart empty")
    if page.locator("#cdTrend .ctm").count() > 0:
        page.hover("#cdTrend .ctm >> nth=0")
        check(page.inner_text("#cdTrendNote").strip() != "", "candidat: trend event note empty on hover")
    check_no_overflow(page, bad, "candidat")


def click_second_tour(page, phone, bad):
    def check(cond, msg):
        if not cond: bad.append(msg)
    page.wait_for_selector(".sp-pair-row")
    check(page.locator(".sp-pair-row").count() >= 1, "second-tour: no pairing rows")
    check(page.inner_text("#rtH1").strip() != "", "second-tour: H1 empty")
    check_no_overflow(page, bad, "second-tour")


def main():
    srv, base = serve()
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp, size in VIEWPORTS.items():
            for lang in ("fr", "en"):
                for scheme in ("light", "dark"):
                    bad = []
                    ctx, page, problems = new_page(browser, base, size, lang, scheme)
                    page.goto(base + "index.html")
                    page.wait_for_selector("#ovBoard .sp-row")
                    page.click(f'[data-lang="{lang}"]')
                    click_index(page, vp == "phone", bad)
                    ctx.close()

                    ctx, page, problems2 = new_page(browser, base, size, lang, scheme)
                    page.goto(base + "candidat.html?c=%C3%89douard%20Philippe")
                    page.click(f'[data-lang="{lang}"]')
                    click_candidat(page, vp == "phone", bad)
                    ctx.close()

                    ctx, page, problems3 = new_page(browser, base, size, lang, scheme)
                    page.goto(base + "second-tour.html")
                    page.click(f'[data-lang="{lang}"]')
                    click_second_tour(page, vp == "phone", bad)
                    ctx.close()

                    problems_all = problems + problems2 + problems3 + bad
                    print(f"{vp:7} {lang} {scheme:5}: {'ok' if not problems_all else str(len(problems_all)) + ' problem(s)'}")
                    failures += [f"[{vp} {lang} {scheme}] {p}" for p in problems_all]
        # freshness notice: absent on fresh data, present once the data is more than 2 days old
        for shift, expect in ((0, False), (3, True)):
            ctx, page, problems = new_page(browser, base, VIEWPORTS["desktop"], "en", "light", clock_shift_days=shift)
            page.goto(base + "index.html")
            page.wait_for_selector("#ovBoard .sp-row")
            shown = page.locator("#stale").count() == 1
            print(f"stale notice with clock +{shift}d: {'shown' if shown else 'hidden'}")
            failures += problems
            if shown != expect: failures.append(f"stale notice {'shown' if shown else 'hidden'} with clock +{shift} days")
            ctx.close()
        # election-silence period (config.json): ?blackout=1/0 forces the state for testing, on every page,
        # at both viewports and in both languages; the real (non-blackout) date is checked once per page above,
        # implicitly, since click_index/click_candidat/click_second_tour only pass with #mainContent visible.
        pages = {"index.html": "#ovBoard .sp-row", "candidat.html?c=%C3%89douard%20Philippe": "#cdName", "second-tour.html": ".sp-pair-row"}
        for vp, size in VIEWPORTS.items():
            for lang in ("fr", "en"):
                for url, ready in pages.items():
                    for qs, expect_blackout in (("blackout=1", True), ("blackout=0", False)):
                        ctx, page, problems = new_page(browser, base, size, lang)
                        page.goto(base + url + ("&" if "?" in url else "?") + qs)
                        page.click(f'[data-lang="{lang}"]')
                        page.wait_for_timeout(400)   # no ready-selector wait: it never appears while blackout hides #mainContent
                        notice_hidden = page.locator("#blackoutNotice").get_attribute("hidden") is not None
                        main_hidden = page.locator("#mainContent").get_attribute("hidden") is not None
                        label = f"{vp} {lang} {url}?{qs}"
                        failures += [f"[blackout {label}] {p}" for p in problems]
                        if main_hidden != expect_blackout: failures.append(f"[blackout {label}] #mainContent {'hidden' if main_hidden else 'shown'}, expected {'hidden' if expect_blackout else 'shown'} (blackout {'active' if expect_blackout else 'inactive'})")
                        if notice_hidden == expect_blackout: failures.append(f"[blackout {label}] #blackoutNotice should be {'shown' if expect_blackout else 'hidden'} when blackout is {'active' if expect_blackout else 'inactive'}")
                        if not expect_blackout: page.wait_for_selector(ready, timeout=5000)   # ?blackout=0: normal render still works
                        else: check_no_overflow(page, failures, f"blackout {label}")
                        ctx.close()
        print("blackout mode: checked on all 3 pages, both viewports, both languages, ?blackout=1 and ?blackout=0")
        browser.close()
    srv.shutdown()
    if failures:
        print("\nFAILED:", *failures, sep="\n  - ")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
