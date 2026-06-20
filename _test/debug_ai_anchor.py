"""
Proof of concept: AI horgonypont
Teszt: govill.hu HTML-ból AI kinyeri a termékeket CSS selector NÉLKÜL.
Összehasonlítás: regex-alapú parser vs AI extrakció.
"""
import urllib.request, json, re, sys
sys.path.insert(0, "D:/CRT")

OLLAMA_URL = "http://localhost:11434/api/generate"

# ── 1. REGEX PARSER (jelenlegi megoldás) ──────────────────────
with open("D:/CRT/_test/debug_govill.html", encoding="utf-8", errors="ignore") as f:
    html = f.read()

prod_re  = re.compile(r'href="(/hu/[^"]+)"\s+class="product_name\s+wcu"[^>]*>\s*(.*?)\s*</a>', re.S|re.I)
price_re = re.compile(r'(\d[\d\s]+)\s*Ft', re.I)
regex_results = []
for m in prod_re.finditer(html):
    name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
    after = html[m.end(): m.end() + 800]
    pm = price_re.search(after)
    if pm and name:
        raw = pm.group(1).replace('\xa0','').replace(' ','')
        try:
            regex_results.append((name, float(raw)))
        except ValueError:
            pass

print(f"REGEX találat: {len(regex_results)} termék")
for n, p in regex_results[:5]:
    print(f"  {n[:55]:55s} | {p:>10,.0f} Ft")

# ── 2. AI EXTRAKCIÓ (selector nélkül) ─────────────────────────
# Tiszta szöveg: csak termékblokkok területe
blocks = []
for m in prod_re.finditer(html):
    name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
    after_txt = re.sub(r'<[^>]+>', ' ', html[m.end(): m.end()+600])
    after_txt = re.sub(r'\s+', ' ', after_txt).strip()[:300]
    blocks.append(f"- {name}\n  Környezet: {after_txt}")

ai_input = "\n".join(blocks[:8])

prompt = f"""Villamos anyag webshop termékadatok. Minden termékblokknál add meg:
- Termék neve
- Nettó ár Ft-ban (a szövegben "Ft" előtt álló szám)

Csak a tényleges termékeket és árakat listázd.
Formátum: TERMÉKNÉV | ÁR

Adatok:
{ai_input}"""

print(f"\nAI EXTRAKCIÓ (llama3:8b, CSS selector nelkul)")
print("="*60)

payload = json.dumps({
    "model": "llama3:8b",
    "prompt": prompt,
    "stream": False,
    "options": {"temperature": 0.0, "num_predict": 600}
}).encode()

req = urllib.request.Request(OLLAMA_URL,
    data=payload, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
        ai_text = resp["response"]
        print(ai_text)

    # ── 3. PONTOSSÁG MÉRÉSE ────────────────────────────────────
    ai_lines = [l.strip() for l in ai_text.splitlines() if "|" in l and "Ft" in l]
    matched = 0
    for line in ai_lines:
        parts = line.split("|")
        if len(parts) >= 2:
            ai_name  = parts[0].strip().lower()
            ai_price = re.search(r'[\d\s]+', parts[1].replace('.','').replace(',',''))
            if ai_price:
                try:
                    ap = float(ai_price.group().replace(' ',''))
                    for rn, rp in regex_results:
                        if abs(ap - rp) < 1 or any(w in ai_name for w in rn.lower().split()[:2]):
                            matched += 1
                            break
                except ValueError:
                    pass

    total = max(len(ai_lines), 1)
    pct = matched / total * 100
    print(f"\n{'='*60}")
    print(f"Egyezés: {matched}/{total} = {pct:.0f}%")
    print(f"Ertek: {'MEGFELEL (>=90%)' if pct >= 90 else 'NEM ERI EL (90% alatt)'}")

except Exception as e:
    print(f"Hiba: {e}")
