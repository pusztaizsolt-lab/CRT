"""
CRT Scraper – Govill.hu (villamos anyagok)
Egyszerű HTML oldal, urllib-bel scrapelható, nincs SPA / GDPR blokk.
prefix: /scraper/govill
"""
import asyncio, logging, re, sys, os, ssl, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.base import save_price, update_source_status, get_or_create_source

log = logging.getLogger("CRT.scraper.govill")

SOURCE_NAME = "Govill.hu"
SOURCE_URL  = "https://www.govill.hu"

SEARCH_TERMS = [
    ("NYM kábel",        "NYM"),
    ("NYY kábel",        "NYY"),
    ("MCB megszakító",   "kismegszakito"),
    ("RCCB",             "FI+relé"),
    ("WAGO kapocs",      "WAGO"),
    ("UTP kábel",        "UTP+cat6"),
    ("IP kamera",        "IP+kamera"),
    ("hálózati switch",  "PoE+switch"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode    = ssl.CERT_NONE


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=CTX) as r:
        return r.read(120_000).decode("utf-8", errors="ignore")


def _parse_products(html: str) -> list[dict]:
    """
    govill.hu struktúra:
      <a href="/hu/termek-slug/" class="product_name wcu">Termék neve</a>
      ...majd közel a szülő div-ben: 21 500 Ft
    """
    results = []

    # Regex: href ELŐBB van, mint class — govill.hu sajátosság
    prod_re  = re.compile(
        r'href="(/hu/[^"]+)"\s+class="product_name\s+wcu"[^>]*>\s*(.*?)\s*</a>',
        re.S | re.I
    )
    price_re = re.compile(r'(\d[\d\s]+)\s*Ft', re.I)

    for m in prod_re.finditer(html):
        product_url  = m.group(1)
        product_name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if not product_name or len(product_name) < 3:
            continue

        # Ár a következő 1000 karakterben (a product div-ben van)
        after = html[m.end(): m.end() + 1000]
        price_m = price_re.search(after)
        if not price_m:
            continue

        raw = price_m.group(1).replace('\xa0', '').replace(' ', '').replace('.', '')
        try:
            price = float(raw)
        except ValueError:
            continue
        if price <= 0:
            continue

        sku_m = re.search(r'Cikkszám[:\s]*([A-Z0-9\-/]+)', after[:500], re.I)
        sku   = sku_m.group(1).strip() if sku_m else None

        results.append({
            "name":  product_name[:200],
            "price": price,
            "url":   SOURCE_URL + product_url,
            "sku":   sku,
        })

    return results


async def scrape(headless: bool = True) -> dict:
    source_id = get_or_create_source(SOURCE_NAME, SOURCE_URL, "public")
    saved, errors = 0, []

    for label, query in SEARCH_TERMS:
        url = f"{SOURCE_URL}/hu/?s={urllib.parse.quote(query, safe='+')}"
        try:
            html     = _fetch_html(url)
            products = _parse_products(html)
            log.info("govill '%s': %d találat", label, len(products))

            for p in products:
                save_price(
                    source_id = source_id,
                    raw_name  = f"[Govill] {p['name']}",
                    raw_price = p["price"],
                    unit      = "db",
                    url       = p.get("url"),
                )
                saved += 1

        except Exception as e:
            msg = f"govill '{label}': {e}"
            log.warning(msg)
            errors.append(msg)

    ok = saved > 0
    update_source_status(source_id, ok, errors[0] if errors and not ok else None)
    log.info("Govill kész: %d ár, %d hiba", saved, len(errors))
    return {"source": SOURCE_NAME, "saved": saved, "errors": errors[:5]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    import json
    print(json.dumps(asyncio.run(scrape()), ensure_ascii=False, indent=2))
