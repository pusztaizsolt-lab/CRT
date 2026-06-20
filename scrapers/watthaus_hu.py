"""
CRT Scraper – Watt-Haus (https://www.watthaus.hu)
Magyar villamos nagykereskedő, jó URL-struktúra (kategóriák szerint)
"""
import asyncio, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from scrapers.base import parse_price, save_price, update_source_status, get_or_create_source

log = logging.getLogger("CRT.scraper.watthaus")

SOURCE_NAME = "Watt-Haus"
SOURCE_URL  = "https://www.watthaus.hu"

CATEGORY_URLS = [
    ("NYM kábel",           f"{SOURCE_URL}/kabelezes/nyomtatott-aramkor-vezetek/nym-j-kabel"),
    ("Kis megszakító",      f"{SOURCE_URL}/vedelem/kismegszakito"),
    ("Fi-relé",             f"{SOURCE_URL}/vedelem/fi-rele"),
    ("Schuko dugalj",       f"{SOURCE_URL}/kapcsolo-dugalj/dugalj"),
    ("Elosztótábla",        f"{SOURCE_URL}/elosztotabla"),
    ("UTP kábel",           f"{SOURCE_URL}/adatkabel/utp-kabel"),
    ("Hálózati switch",     f"{SOURCE_URL}/aktiv-halozat/switch"),
    ("IP kamera",           f"{SOURCE_URL}/biztonsagtechnika/ip-kamera"),
]

SEARCH_TERMS = [
    ("NYY kábel",   f"{SOURCE_URL}/search?q=nyy+kabel"),
    ("WAGO kapocs", f"{SOURCE_URL}/search?q=wago+kapocs"),
    ("Patch panel", f"{SOURCE_URL}/search?q=patch+panel"),
]


async def _scrape_listing(page, url: str, label: str, source_id: int,
                          results: list, errors: list):
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # Cookie elfogadás
        try:
            await page.click(".cookie-accept, #cookie-accept, button[class*='accept']", timeout=2000)
        except Exception:
            pass

        items = await page.query_selector_all(
            ".product-item, .product-card, article.item, li.product"
        )
        if not items:
            items = await page.query_selector_all("[class*='product'][class*='item']")

        log.info("Watt-Haus '%s': %d találat (%s)", label, len(items), url)

        for item in items[:10]:
            try:
                name_el  = await item.query_selector(
                    "h2, h3, .product-name, .item-name, a[class*='name']"
                )
                price_el = await item.query_selector(
                    ".price, .product-price, span[class*='price'], [class*='netto']"
                )
                scode_el = await item.query_selector(".sku, .cikkszam, [class*='code']")

                name  = (await name_el.inner_text()).strip()  if name_el  else label
                raw_p = (await price_el.inner_text()).strip() if price_el else ""
                scode = (await scode_el.inner_text()).strip() if scode_el else None
                price = parse_price(raw_p)

                if name and price and price > 0:
                    save_price(
                        source_id     = source_id,
                        raw_name      = f"[Watt-Haus] {name}",
                        raw_price     = price,
                        supplier_code = scode,
                    )
                    results.append({"name": name[:60], "price": price})
            except Exception as e:
                errors.append(f"item: {e}")

    except Exception as e:
        msg = f"Watt-Haus '{label}': {e}"
        log.warning(msg)
        errors.append(msg)


async def scrape(headless: bool = True) -> dict:
    source_id = get_or_create_source(SOURCE_NAME, SOURCE_URL, "public")
    results, errors = [], []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        ctx     = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        page.set_default_timeout(20_000)

        for label, url in CATEGORY_URLS + SEARCH_TERMS:
            await _scrape_listing(page, url, label, source_id, results, errors)
            await page.wait_for_timeout(800)

        await browser.close()

    ok = len(results) > 0
    update_source_status(source_id, ok, errors[0] if errors and not ok else None)
    log.info("Watt-Haus kész: %d ár, %d hiba", len(results), len(errors))
    return {"source": SOURCE_NAME, "saved": len(results), "errors": errors[:5]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    r = asyncio.run(scrape(headless=False))
    print(r)
