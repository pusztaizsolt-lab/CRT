"""Scraper selector debugger — megnézi az oldal struktúráját"""
import asyncio, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__file__)))
from playwright.async_api import async_playwright

URLS = {
    "conrad":   "https://www.conrad.hu/search?query=kabel+nym",
    "watthaus": "https://www.watthaus.hu/search?q=nym+kabel",
    "evill":    "https://www.evill.hu/kereses?q=nym+kabel",
}

async def debug_url(name: str, url: str):
    print(f"\n{'='*60}")
    print(f"  {name}: {url}")
    print(f"{'='*60}")
    async with async_playwright() as pw:
        br  = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        pg  = await ctx.new_page()
        await pg.goto(url, wait_until="domcontentloaded")
        await pg.wait_for_timeout(3000)

        # HTML mentése
        html = await pg.content()
        out  = f"D:/CRT/_test/debug_{name}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html[:120000])
        print(f"  HTML mentve: {out} ({len(html):,} byte)")

        # Osztályok keresése amelyek termékekre utalnak
        classes = await pg.evaluate("""() => {
            const sel = '[class*="product"],[class*="item"],[class*="card"],[class*="termek"],[class*="tile"]';
            const els = [...document.querySelectorAll(sel)].slice(0,12);
            return els.map(e => {
                const cl = e.className.toString().trim().split(/\\s+/).slice(0,4).join('.');
                return e.tagName.toLowerCase() + '.' + cl;
            });
        }""")
        print("  Releváns elemek:")
        for c in classes:
            print(f"    {c}")

        # Ár elemek keresése
        prices = await pg.evaluate("""() => {
            const sel = '[class*="price"],[class*="ar"],[class*="price__"],[class*="netto"]';
            const els = [...document.querySelectorAll(sel)].slice(0,8);
            return els.map(e => e.tagName.toLowerCase() + '.' + e.className.toString().trim().split(/\\s+/).slice(0,3).join('.') + ' → ' + e.innerText.trim().slice(0,40));
        }""")
        print("  Ár elemek:")
        for p in prices:
            print(f"    {p}")

        # Title
        title = await pg.title()
        print(f"  Cím: {title}")
        await br.close()


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = {target: URLS[target]} if target in URLS else URLS
    for name, url in targets.items():
        await debug_url(name, url)

asyncio.run(main())
