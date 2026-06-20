"""
CRT Scraper – eVill.hu (https://www.evill.hu)
Magyar villamossági webshop, jó keresési API-val
Profil: erősáram + gyengeáram, beléptető, tűzjelző
"""
import asyncio, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from scrapers.base import parse_price, save_price, update_source_status, get_or_create_source

log = logging.getLogger("CRT.scraper.evill")

SOURCE_NAME = "eVill.hu"
SOURCE_URL  = "https://www.evill.hu"

SEARCH_TERMS = [
    ("NYM kábel 3x1.5",   "nym-j 3x1.5"),
    ("NYM kábel 3x2.5",   "nym-j 3x2.5"),
    ("NYY kábel 4x10",    "nyy 4x10"),
    ("MCB 1P 16A",        "kismegszakito 1p 16a"),
    ("MCB 3P 32A",        "kismegszakito 3p 32a"),
    ("Fi-relé 4P 40A",    "fi-rele 4p 40a"),
    ("RCBO kombináció",   "rcbo 1p 16a"),
    ("Schuko dugalj",     "schuko dugalj"),
    ("UTP Cat6 fm",       "utp cat6"),
    ("IP dóm kamera",     "ip dom kamera 4mp"),
    ("NVR 8 csatornás",   "nvr 8 csatornás"),
    ("PIR érzékelő",      "pir mozgaserzekelo"),
    ("Tűzjelző érzékelő","optikai fusterzekelo"),
    ("RFID olvasó",       "rfid kartyaolvaso"),
    ("Patch panel 24p",   "patch panel 24"),
    ("PoE switch 8p",     "poe switch 8"),
]


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

        first_page = True
        for label, query in SEARCH_TERMS:
            try:
                url = f"{SOURCE_URL}/kereses?q={query.replace(' ','+')}"
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(1800)

                # Cookie elfogadás (csak egyszer)
                if first_page:
                    try:
                        await page.click(
                            "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll,"
                            " .cc-btn.cc-allow, [class*='cookie'][class*='accept']",
                            timeout=3000
                        )
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass
                    first_page = False

                # Terméklista
                items = await page.query_selector_all(
                    ".product-item, .termek-item, .product-card, "
                    "li.product, .shop-item, article[class*='product']"
                )

                log.info("eVill '%s': %d találat", query, len(items))

                for item in items[:8]:
                    try:
                        name_el  = await item.query_selector(
                            ".product-name, .termek-nev, h2, h3, a[class*='name']"
                        )
                        price_el = await item.query_selector(
                            ".netto-ar, .net-price, .price-netto, "
                            "[class*='netto'], [class*='price'], .ar"
                        )
                        scode_el = await item.query_selector(".cikkszam, .sku, .product-code")

                        name  = (await name_el.inner_text()).strip()  if name_el  else label
                        raw_p = (await price_el.inner_text()).strip() if price_el else ""
                        scode = (await scode_el.inner_text()).strip() if scode_el else None
                        price = parse_price(raw_p)

                        if name and price and price > 0:
                            save_price(
                                source_id     = source_id,
                                raw_name      = f"[eVill] {name}",
                                raw_price     = price,
                                supplier_code = scode,
                            )
                            results.append({"name": name[:60], "price": price})
                    except Exception as e:
                        errors.append(f"item '{label}': {e}")

                await page.wait_for_timeout(1000)

            except Exception as e:
                msg = f"eVill '{query}': {e}"
                log.warning(msg)
                errors.append(msg)

        await browser.close()

    ok = len(results) > 0
    update_source_status(source_id, ok, errors[0] if errors and not ok else None)
    log.info("eVill kész: %d ár, %d hiba", len(results), len(errors))
    return {"source": SOURCE_NAME, "saved": len(results), "errors": errors[:5]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    r = asyncio.run(scrape(headless=False))
    print(r)
