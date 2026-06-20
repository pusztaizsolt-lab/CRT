"""
CRT Böngészős Frontend Teszt — Playwright alapú
Futtatás: py -3.11 _test/browser_test.py
         py -3.11 _test/browser_test.py --headed   (látható böngészővel)
         py -3.11 _test/browser_test.py --page arak (csak egy oldal)
"""
import sys, os, re, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, expect

BASE      = "http://localhost:8000"
ADMIN_PIN = os.environ.get("CRT_ADMIN_PIN", "123456")
ADMIN_USR = os.environ.get("CRT_ADMIN_USER", "admin")
ADMIN_EML = os.environ.get("CRT_ADMIN_EMAIL", "pusztaizsolt@gmail.com")
LOG_PATHS = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend.err"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend.log"),
]

# ── Színek ────────────────────────────────────────────────────────
G  = "[OK]"
R  = "[--]"
W  = "[!]"
SEP = "-" * 56

results = []

def tick(name, label, ok, ms=0, note=""):
    sym = G if ok else R
    ms_str = f"{ms:.0f}ms" if ms else ""
    line = f"  [{name:>4}] {sym}  {label:<32} {ms_str:>7}  {note}"
    print(line)
    results.append((name, ok, note))

def p(s=""): print(s)

# ── OTP kiolvasás logból ──────────────────────────────────────────
OTP_PAT = re.compile(r"OTP k.?d a loggban: (\d{6})")

def _log_offset() -> dict:
    """Visszaadja az összes logfájl aktuális méretét (byte-ban)."""
    sizes = {}
    for path in LOG_PATHS:
        try:
            sizes[path] = os.path.getsize(path)
        except OSError:
            sizes[path] = 0
    return sizes

def read_otp_from_log(offsets: dict, timeout=12) -> str:
    """Csak az `offsets` után keletkezett logsorokban keresi az OTP-t."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for path in LOG_PATHS:
            if not os.path.exists(path):
                continue
            start = offsets.get(path, 0)
            with open(path, "rb") as f:
                f.seek(start)
                new_bytes = f.read()
            new_text = new_bytes.decode("utf-8", errors="ignore")
            m = list(OTP_PAT.finditer(new_text))
            if m:
                return m[-1].group(1)
        time.sleep(0.4)
    return ""

# ── Bejelentkezés ─────────────────────────────────────────────────
def do_login(page) -> bool:
    log_pos = _log_offset()   # logfájlok mérete a PIN elküldése ELŐTT

    t = time.time()
    try:
        page.goto(f"{BASE}/ui/login.html", wait_until="networkidle", timeout=10000)
        # Felhasználónév + PIN
        page.wait_for_selector("#username", timeout=5000)
        page.fill("#username", ADMIN_USR)
        # PIN: pinRow gyerekei, dinamikusan generált inputok
        for i, digit in enumerate(ADMIN_PIN):
            page.locator(f"#pinRow input:nth-child({i+1})").fill(digit)
        page.click("#btnLogin")
        # OTP képernyő megjelenése (step2 panel lesz visible)
        page.wait_for_selector("#step2.visible", timeout=8000)
        tick("B1", "Login oldal + PIN", True, (time.time()-t)*1000)
    except Exception as e:
        tick("B1", "Login oldal + PIN", False, note=str(e)[:50])
        return False

    # OTP kiolvasás logból — csak a PIN elküldése UTÁN keletkezett sorokból
    t2 = time.time()
    otp = read_otp_from_log(offsets=log_pos)
    if not otp:
        tick("B2", "OTP kiolvasás", False, note="nem található a logban")
        return False
    tick("B2", "OTP kiolvasás", True, (time.time()-t2)*1000, f"kód: {otp}")

    # OTP mezők kitöltése — click first input, then type digits (keydown handler moves focus)
    t3 = time.time()
    try:
        # Interceptor ELŐBB, mielőtt typing triggereli doVerify()-t
        verify_resp = {}
        def capture_verify(resp):
            if "/auth/verify" in resp.url:
                try:
                    verify_resp["status"] = resp.status
                    verify_resp["body"]   = resp.json()
                except Exception:
                    verify_resp["status"] = resp.status
        page.on("response", capture_verify)

        # OTP értékek beállítása JS-sel, majd doVerify() közvetlen hívása
        page.evaluate(f"""() => {{
            const row = document.getElementById('otpRow');
            const code = '{otp}';
            [...row.children].forEach((inp, i) => {{ inp.value = code[i] || ''; }});
        }}""")
        page.wait_for_timeout(100)
        page.evaluate("() => doVerify()")

        # A JS 800ms delay után redirect-el admin.html vagy fomenu.html-re
        page.wait_for_url(lambda url: "login.html" not in url, timeout=10000)
        landed = page.url.split("/")[-1]
        ok = landed in ("fomenu.html", "admin.html")
        tick("B3", f"OTP verify -> {landed}", ok, (time.time()-t3)*1000)
        return ok
    except Exception as e:
        tick("B3", "OTP verify -> ?", False, note=str(e)[:50])
        return False

# ── Oldalak tesztje ───────────────────────────────────────────────
PAGES = [
    ("fomenu",        "fomenu.html",        "fomenu",      None),
    ("cikktorzs",     "cikktorzs.html",     "cikktorzs",   None),
    ("arak",          "arak.html",          "arak",        ".stats-bar"),
    ("ajanlat",       "ajanlatkezelo.html", "ajanlat",     None),
    ("beallitasok",   "beallitasok.html",   "beallitasok", None),
    ("naplok",        "naplok.html",        "naplok",      ".stat-bar"),
    ("admin",         "admin.html",         "admin",       None),
    ("lora",          "lora.html",          "lora",        None),
    ("webes_arak",    "webes_arak.html",    "webes",       None),
    ("widget",        "widget.html",        "widget",      None),
]

def test_page(page, code, html, label, wait_sel=None):
    t = time.time()
    try:
        page.goto(f"{BASE}/ui/{html}", wait_until="domcontentloaded", timeout=10000)
        # Átirányítás ellenőrzés (nem login oldalra ment?)
        if "login.html" in page.url:
            tick(code, f"{label} oldal betölt", False, note="→ login (auth hiba)")
            return
        # Várt elem megjelenése
        if wait_sel:
            page.wait_for_selector(wait_sel, timeout=5000)
        # Nincs JS hiba?
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.wait_for_timeout(800)
        note = f"JS hiba: {errors[0][:40]}" if errors else ""
        tick(code, f"{label} oldal betölt", not errors, (time.time()-t)*1000, note)
    except Exception as e:
        tick(code, f"{label} oldal betölt", False, (time.time()-t)*1000, str(e)[:50])

def test_cikktorzs_search(page):
    t = time.time()
    try:
        page.goto(f"{BASE}/ui/cikktorzs.html", wait_until="domcontentloaded")
        page.wait_for_selector("#searchInput", timeout=5000)
        page.fill("#searchInput", "a")   # 1 karakter → "legalább 2 karakter" hint
        page.wait_for_timeout(400)
        page.fill("#searchInput", "al")  # 2 karakter → API hívás indul
        page.wait_for_timeout(1000)
        # Siker: vagy találat (sr-item) vagy "Nincs találat" hint — mindkettő OK, csak hiba ne legyen
        hint = page.query_selector("#searchResults .search-hint")
        item = page.query_selector("#searchResults .sr-item")
        ok = hint is not None or item is not None
        note = f"{page.query_selector('#searchResults').inner_text()[:30]}" if ok else "searchResults ures"
        tick("BS1", "Cikktörzs keresés API", ok, (time.time()-t)*1000, note)
    except Exception as e:
        tick("BS1", "Cikktörzs keresés API", False, note=str(e)[:50])

def test_arak_load(page):
    t = time.time()
    try:
        page.goto(f"{BASE}/ui/arak.html", wait_until="domcontentloaded")
        page.wait_for_selector(".stats-bar", timeout=6000)
        # Stats endpoint válaszolt-e? A DOM elem létezik = endpoint hívódott
        total_el = page.query_selector("#st-total")
        src_el   = page.query_selector("#st-src")
        ok = total_el is not None and src_el is not None
        total = total_el.inner_text() if total_el else "?"
        tick("BA1", "Arak stats endpoint", ok, (time.time()-t)*1000, f"total={total}")
    except Exception as e:
        tick("BA1", "Arak stats endpoint", False, note=str(e)[:50])

def test_naplok_load(page):
    t = time.time()
    try:
        page.goto(f"{BASE}/ui/naplok.html", wait_until="domcontentloaded")
        page.wait_for_selector(".log-table", timeout=8000)
        rows = page.query_selector_all(".log-table tbody tr")
        ok = len(rows) > 0
        tick("BN1", "Napló tábla betölt", ok, (time.time()-t)*1000, f"{len(rows)} sor")
    except Exception as e:
        tick("BN1", "Napló tábla betölt", False, note=str(e)[:50])

def test_ajanlat_create(page):
    t = time.time()
    try:
        page.goto(f"{BASE}/ui/ajanlatkezelo.html", wait_until="domcontentloaded")
        # Mode-card grid megjelenése (startEmpty / upload / copy kártyák)
        page.wait_for_selector(".mode-card", timeout=6000)
        cards = page.query_selector_all(".mode-card")
        ok = len(cards) >= 1
        tick("BQ1", "Ajánlat mode-grid betölt", ok, (time.time()-t)*1000, f"{len(cards)} kártya")
    except Exception as e:
        tick("BQ1", "Ajánlat oldal betölt", False, note=str(e)[:50])

# ── FŐ FUTÁS ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Látható böngészővel fut")
    parser.add_argument("--page",   default="",          help="Csak egy oldalt tesztel")
    parser.add_argument("--slow",   type=int, default=0, help="Lassítás ms (headed módhoz)")
    args = parser.parse_args()

    p(f"\n{'='*56}")
    p(f"  CRT Bongeszes Teszt -- Playwright")
    p(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}  |  {'headed' if args.headed else 'headless'}")
    p(f"{'='*56}\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not args.headed,
            slow_mo=args.slow,
        )
        ctx  = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(10000)

        # ── Bejelentkezés
        p("  — Bejelentkezés —")
        logged_in = do_login(page)
        if not logged_in:
            p("\n  FATÁLIS: bejelentkezés sikertelen, teszt leáll.")
            browser.close()
            return

        # ── Oldalak betöltése
        p(f"\n  — Oldalak ({len(PAGES)}) —")
        filter_page = args.page.lower()
        for code, html, label, sel in PAGES:
            if filter_page and filter_page not in label:
                continue
            test_page(page, code, html, label, sel)

        # ── Funkcionális tesztek
        p("\n  — Funkcionális tesztek —")
        test_cikktorzs_search(page)
        test_arak_load(page)
        test_naplok_load(page)
        test_ajanlat_create(page)

        browser.close()

    # ── Eredmény
    ok_n  = sum(1 for _, ok, _ in results if ok)
    err_n = sum(1 for _, ok, _ in results if not ok)
    total = len(results)

    p(f"\n{'='*56}")
    p(f"  Eredmeny: {ok_n}/{total} OK | {err_n} hiba")
    p(f"{'='*56}")
    if err_n == 0:
        p("  Minden böngészős teszt sikeres.\n")
    else:
        p("  Hibás lépések:")
        for name, ok, note in results:
            if not ok:
                p(f"  [--]  {name}: {note}")
        p()

    sys.exit(0 if err_n == 0 else 1)

if __name__ == "__main__":
    main()
