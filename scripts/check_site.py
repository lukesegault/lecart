"""Local browser check: loads the page, clicks every control in French and English, at desktop and phone width,
and fails on any console error, uncaught exception, failed request or broken control.

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


def new_page(browser, base, size, lang, clock_shift_days=0):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, locale=f"{lang}-{lang.upper()}", accept_downloads=True)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"exception: {e}"))
    page.on("requestfailed", lambda r: problems.append(f"request failed: {r.url}"))
    page.on("response", lambda r: problems.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    stub_analytics(page)
    if clock_shift_days:
        page.add_init_script(f"(()=>{{const n=Date.now.bind(Date);Date.now=()=>n()+{clock_shift_days}*864e5}})()")
    page.goto(base + "index.html")
    page.wait_for_selector("#board .row")
    return page, problems


def click_all(page, phone):
    """Click every control of the page once; returns what went wrong."""
    bad = []
    def check(cond, msg):
        if not cond: bad.append(msg)
    page.click("#more"); check(page.get_attribute("#more", "aria-expanded") == "true", "#more did not expand the board")
    page.click("#more")
    for q in ("qual", "win"):
        for u in ("low", "mid", "high"):
            page.click(f'[data-q="{q}"]'); page.click(f'[data-u="{u}"]')
            check(page.locator("#board .row").count() >= 8, f"board empty for {q}/{u}")
            check(page.locator("#gaps .gap-item").count() == 3, f"largest gaps missing for {q}/{u}")
    for i in range(page.locator("#dvPills button").count()):
        page.click(f"#dvPills button >> nth={i}")
        check(page.locator("#dvChart svg path").count() > 0, f"over-time chart empty for pill {i}")
        check(page.inner_text("#dvPill").strip() != "", f"gap badge empty for pill {i}")
    for tf in ("1M", "3M", "6M", "ALL"):
        page.click(f'#dvTf button[data-tf="{tf}"]')
    for i in range(page.locator("#dvEvents button").count()):
        page.click(f"#dvEvents button >> nth={i}"); check(page.inner_text("#dvNote").strip() != "", "event note empty")
    page.hover("#dvChart svg")
    with page.expect_download(timeout=15000) as dl:
        page.click("#dvExport")
    check(dl.value.suggested_filename.endswith(".png"), "export is not a PNG")
    check(page.inner_text("#dvExpMsg").strip() == "", "export reported an error")
    page.click("details summary"); check(page.locator("#polltable tbody tr").count() > 0, "poll table empty")
    page.hover("#trend .lbl >> nth=0")
    page.click("#optOut"); page.click("#optOut")   # opt out, then back in: leaves storage as found
    for href in ("#multiSection", "#compare", "#method"):
        if phone: page.click("#menuBtn"); check(page.get_attribute("#menuBtn", "aria-expanded") == "true", "menu did not open")
        page.click(f'#nav a[href="{href}"]')
        if phone: check(page.get_attribute("#menuBtn", "aria-expanded") == "false", "menu stayed open after a link")
    return bad


def main():
    srv, base = serve()
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp, size in VIEWPORTS.items():
            for lang in ("fr", "en"):
                page, problems = new_page(browser, base, size, lang)
                page.click(f'[data-lang="{lang}"]')
                problems += click_all(page, phone=vp == "phone")
                other = "en" if lang == "fr" else "fr"
                page.click(f'[data-lang="{other}"]'); page.click(f'[data-lang="{lang}"]')
                print(f"{vp:7} {lang}: {'ok' if not problems else str(len(problems)) + ' problem(s)'}")
                failures += [f"[{vp} {lang}] {p}" for p in problems]
                page.context.close()
        # freshness notice: absent on fresh data, present once the data is more than 2 days old
        for shift, expect in ((0, False), (3, True)):
            page, problems = new_page(browser, base, VIEWPORTS["desktop"], "en", clock_shift_days=shift)
            shown = page.locator("#stale").count() == 1
            print(f"stale notice with clock +{shift}d: {'shown' if shown else 'hidden'}")
            failures += problems
            if shown != expect: failures.append(f"stale notice {'shown' if shown else 'hidden'} with clock +{shift} days")
            page.context.close()
        browser.close()
    srv.shutdown()
    if failures:
        print("\nFAILED:", *failures, sep="\n  - ")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
