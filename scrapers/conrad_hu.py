"""
CRT Scraper – Conrad Electronic Magyarország (Playwright, networkidle)
A Conrad SPA dinamikusan tölt — networkidle + screenshot debug.
"""
import asyncio, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.async_api import async_playwright
from scrapers.base import parse_price, save_price, update_source_status, get_or_create_source

log = logging.getLogger("CRT.scraper.conrad")

SOURCE_NAME = "Conrad Electronic HU"
SOURCE_URL  = "https://www.conrad.hu"

SEARCH_TERMS = [
    ("NYM kábel",      "nym+kabel"),
    ("MCB megszakító", "kismegszakito"),
    ("UTP Cat6",       "utp+cat6"),
    ("PoE switch",     "poe+switch"),
    ("IP kamera",      "ip+kamera"),
    ("WAGO kapocs",    "wago+222"),
]


async def _get_products(page, query: str) -> list[dict]:
    url = f"{SOURCE_URL}/hu/search.html?query={query}"
    await page.goto(url, wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(2000)

    # Cookie elfogadás
    try:
        await page.click("button#onetrust-accept-btn-handler", timeout=3000)
        await page.wait_for_timeout(800)
    except Exception:
        pass

    # Conrad specifikus selectorok (SPA renderelt)
    selectors_to_try = [
        "div[class*='ProductListItem']",
        "div[class*='product-list-item']",
        "article[class*='Product']",
        "li[class*='product']",
        "[data-testid='product-tile']",
        "[data-tracking-name]",
        ".c-pdList__item",
    ]

    items = []
    for sel in selectors_to_try:
        items = await page.query_selector_all(sel)
        if items:
            log.info("Conrad '%s': %d db @ %s", query, len(items), sel)
            break

    if not items:
        # Utolsó kísérlet: DOM tartalom elemzése
        log.warning("Conrad '%s': 0 találat, selector debug...", query)
        try:
            classes = await page.evaluate(
                "() => [...document.querySelectorAll('*')].filter(e => e.children.length"
                " && /product|item|tile|termek/i.test(e.className))"
                ".slice(0,5).map(e => e.tagName + '.' + e.className.split(' ')[0])"
            )
            log.info("  DOM class hint: %s", classes)
        except Exception:
            pass
        return []

    results = []
    for item in items[:8]:
        try:
            name_el  = await item.query_selector(
                "h2, h3, [class*='name'], [class*='title'], [class*='Name'], [class*='Title']"
            )
            price_el = await item.query_selector(
                "[class*='price'], [class*='Price'], [class*='amount'], [class*='Amount']"
            )
            scode_el = await item.query_selector(
                "[class*='article'], [class*='sku'], [class*='Sku'], [class*='id']"
            )
            name  = (await name_el.inner_text()).strip()  if name_el  else ""
            raw_p = (await price_el.inner_text()).strip() if price_el else ""
            scode = (await scode_el.inner_text()).strip() if scode_el else None
            price = parse_price(raw_p)
            if name and price and price > 0:
                results.append({"name": name, "price": price, "scode": scode})
        except Exception as e:
            log.debug("Conrad item parse: %s", e)

    return results


async def scrape(headless: bool = True) -> dict:
    source_id = get_or_create_source(SOURCE_NAME, SOURCE_URL, "public")
    results, errors = [], []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        page.set_default_timeout(30_000)

        for label, query in SEARCH_TERMS:
            try:
                prods = await _get_products(page, query)
                for p in prods:
                    save_price(source_id=source_id,
                               raw_name=f"[Conrad] {p['name'][:200]}",
                               raw_price=p["price"],
                               supplier_code=p.get("scode"))
                    results.append(p)
                await page.wait_for_timeout(1000)
            except Exception as e:
                msg = f"Conrad '{label}': {e}"
                log.warning(msg)
                errors.append(msg)

        await browser.close()

    ok = len(results) > 0
    update_source_status(source_id, ok, errors[0] if errors and not ok else None)
    log.info("Conrad kész: %d ár, %d hiba", len(results), len(errors))
    return {"source": SOURCE_NAME, "saved": len(results), "errors": errors[:5]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    print(asyncio.run(scrape(headless=False)))
