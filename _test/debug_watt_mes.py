"""Debug: Conrad.hu - hálózati kérések elfogása (API alapú SPA)"""
import asyncio, json
from playwright.async_api import async_playwright

APIKEY = "vC9FZafAfIyvmYWXEGGAWNCLnabH1kcEXmnSDkaY2RxNhcr3"

async def debug_conrad_api():
    results = []

    async with async_playwright() as pw:
        br  = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        pg = await ctx.new_page()

        # Hálózati válaszok elfogása - MINDEN kérés
        captured = []
        async def on_response(resp):
            url = resp.url
            ct  = resp.headers.get("content-type", "")
            if "api.conrad.hu" in url or "json" in ct:
                print(f"  [{resp.status}] {url[:100]}")
            if "api.conrad.hu/search" in url:
                try:
                    body = await resp.json()
                    captured.append({"url": url, "data": body})
                except Exception:
                    pass
        pg.on("response", on_response)

        # Consent előre beállítása localStorage-ban a Conrad doménján
        print("Conrad domain megnyitasa...")
        await pg.goto("https://www.conrad.hu/hu/", wait_until="domcontentloaded", timeout=20_000)

        # LocalStorage: cookiesGloballyAccepted + Usercentrics bypass
        await pg.evaluate("""() => {
            localStorage.setItem('cookiesGloballyAccepted', 'yes');
            sessionStorage.setItem('cookiesGloballyAccepted', 'yes');
            document.cookie = 'cookiesGloballyAccepted=yes; path=/; domain=.conrad.hu';
        }""")

        # Usercentrics "Elfogad" gomb megnyomása ha megjelenik
        try:
            btn = await pg.wait_for_selector(
                "button[data-testid='uc-accept-all-button'], "
                "button[aria-label*='elfogad'], "
                "[class*='AcceptAll'], "
                "#uc-btn-accept-banner",
                timeout=5000
            )
            if btn:
                await btn.click()
                print("  Usercentrics elfogadva")
                await pg.wait_for_timeout(1000)
        except Exception:
            print("  Nincs consent popup / mar elfogadva")

        print("Keresés: nym+kabel")
        await pg.goto(
            "https://www.conrad.hu/hu/search.html?query=nym+kabel",
            wait_until="networkidle", timeout=30_000
        )
        await pg.wait_for_timeout(3000)

        print(f"\nElkapott API valaszok: {len(captured)}")
        for c in captured:
            d = c["data"]
            products = d.get("products") or d.get("results") or d.get("items") or []
            if isinstance(products, dict):
                products = list(products.values())
            print(f"  URL: {c['url'][:90]}")
            print(f"  Top-level keys: {list(d.keys())[:8]}")
            if products:
                print(f"  Termekek: {len(products)} db")
                for p in products[:3]:
                    name = p.get("title") or p.get("name") or p.get("description") or ""
                    price = p.get("price") or p.get("priceGross") or p.get("priceBrutto") or ""
                    sku   = p.get("articleNumber") or p.get("sku") or p.get("id") or ""
                    print(f"    [{sku}] {name[:60]} | {price}")
                # Elso termek teljes strukturaja
                if products:
                    with open("D:/CRT/_test/debug_conrad_prod.json", "w", encoding="utf-8") as f:
                        json.dump(products[0], f, ensure_ascii=False, indent=2)
                    print("  -> Elso termek mentve: _test/debug_conrad_prod.json")

        # Ha semmi sem jonn, probaljuk kozvetlenul
        if not captured:
            print("\nKozetlen API kiserlet...")
            import urllib.request
            search_url = (
                f"https://api.conrad.hu/search/1/v3/search/hu/hu/B2C"
                f"?apikey={APIKEY}&query=nym+kabel&limit=5"
            )
            req = urllib.request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://www.conrad.hu/",
                "Origin":  "https://www.conrad.hu",
            })
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    body = json.loads(r.read())
                    print(f"  HTTP {r.status}, keys: {list(body.keys())[:8]}")
                    prods = body.get("products") or body.get("results") or []
                    print(f"  Termekek: {len(prods)}")
                    with open("D:/CRT/_test/debug_conrad_api.json","w",encoding="utf-8") as f:
                        json.dump(body, f, ensure_ascii=False, indent=2)
                    print("  -> Mentve: _test/debug_conrad_api.json")
            except Exception as e:
                print(f"  HIBA: {e}")

        await br.close()

asyncio.run(debug_conrad_api())
