"""Debug: govill.hu HTML struktura feltarasa"""
import re, ssl, urllib.request, urllib.parse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
}
CTX = ssl.create_default_context()
CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

url = "https://www.govill.hu/hu/?s=" + urllib.parse.quote("NYM")
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=12, context=CTX) as r:
    html = r.read(200_000).decode("utf-8", errors="ignore")

with open("D:/CRT/_test/debug_govill.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML mentve: {len(html):,} bytes")

# Keresunk termek blokkot
idx = html.find("product_name")
if idx >= 0:
    snip = html[max(0,idx-200):idx+600]
    print("\n=== 800 char a 'product_name' korul ===")
    print(snip)
else:
    print("'product_name' NEM talalhato az oldalon!")
    # Keressunk alternativat
    for cls in ["item", "product", "termek", "wcu", "list-item"]:
        positions = [m.start() for m in re.finditer(cls, html, re.I)]
        print(f"'{cls}' elofordulasok: {len(positions)}")
