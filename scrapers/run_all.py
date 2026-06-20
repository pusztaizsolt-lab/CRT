"""
CRT – Összes scraper futtatása
py -3.11 scrapers/run_all.py
py -3.11 scrapers/run_all.py --source conrad
py -3.11 scrapers/run_all.py --source watthaus
py -3.11 scrapers/run_all.py --source evill
py -3.11 scrapers/run_all.py --headed
"""
import asyncio, argparse, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("CRT.scraper.run")

SCRAPERS = {
    "conrad":   "scrapers.conrad_hu",
    "watthaus": "scrapers.watthaus_hu",
    "evill":    "scrapers.evill_hu",
}


async def run_one(module_path: str, headed: bool) -> dict:
    import importlib
    mod = importlib.import_module(module_path)
    return await mod.scrape(headless=not headed)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="all",
                        help="Forrás: all | conrad | watthaus | evill")
    parser.add_argument("--headed", action="store_true",
                        help="Látható böngésző (debug)")
    args = parser.parse_args()

    targets = (
        list(SCRAPERS.items()) if args.source == "all"
        else [(args.source, SCRAPERS[args.source])]
    )

    print(f"\n  CRT Scraper — {len(targets)} forrás, {'headed' if args.headed else 'headless'}\n")
    total_saved = 0
    for name, module in targets:
        print(f"  → {name}...")
        try:
            result = await run_one(module, args.headed)
            saved = result.get("saved", 0)
            total_saved += saved
            print(f"    OK: {saved} ár mentve"
                  + (f", hibák: {result['errors']}" if result.get("errors") else ""))
        except Exception as e:
            print(f"    HIBA: {e}")

    print(f"\n  Összesen: {total_saved} ár mentve\n")


if __name__ == "__main__":
    asyncio.run(main())
