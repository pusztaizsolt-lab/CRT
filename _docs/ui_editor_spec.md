# CRT Szerkesztő Felület — UI/UX Spec v0.1

## Alapelv

**A mező soha nem üres.** Az AI mindig kitölti a legjobb tippjével.
A szín mondja meg mennyire bízz benne, a tooltip mondja el miért.
A felhasználó dönt: jóváhagyja, javítja, vagy figyelmen kívül hagyja.

---

## Szín logika

| Szín | Confidence | Kor | Jelentés |
|---|---|---|---|
| Zöld | 90%+ | friss | Biztos egyezés — bátran fogadd el |
| Sárga | 50–90% | bármi | Bizonytalan — nézd át |
| Narancssárga | bármi | > 6 hónap | Jó egyezés de elavult ár |
| Piros | < 50% | bármi | Gyenge egyezés vagy mindkét baj egyszerre |

A két hibaforrás egymástól független:
- **"túl kaki"** = gyenge AI egyezés (confidence alacsony)
- **"túl öreg"** = az ár régi (Chroma időindex alapján)

Mindkettő lehet egyszerre — akkor piros.

---

## Tooltip (hover) — a program magyaráz

Minden jelölt mezőn hover-re plain text magyarázat jelenik meg:

```
⚠️ Bosch DS151i PIR
   Egyezés: 67% (bizonytalan)
   Ár: 4 850 Ft — 2025. január óta nem frissült
   Árugrás: +18% az előző scrapinghez képest
   → Javaslat: ellenőrizd a szállítónál
```

Zöld mezőn is megjelenik (de rövid):
```
✅ NYM-J 3x1,5mm² erősáramú kábel
   Egyezés: 94% — Chroma szemantikus egyezés
   Ár: 285 Ft/m — frissítve: 2 hete
```

---

## Adatforrások a szín/tooltip számításához

| Adat | Honnan |
|---|---|
| `confidence` | `web_prices.confidence` (AI suggest motor) |
| `kor` | `web_prices.created_at` vs `NOW()` |
| `árugrás %` | Chroma időindexelt előző bejegyzés vs jelenlegi |
| `item_id egyezés` | `web_prices.item_id` → `products` tábla |

---

## AI suggest 2 kanyar (backend logika)

**1. kanyar — Ki ez a termék?**
- Chroma cosine similarity: `raw_name` → `item_id`
- Kezeli a néveltéréseket, rövidítéseket, elírásokat
- Eredmény: `item_id` + `confidence`

**2. kanyar — Változott-e az ára?**
- Chroma időfilter: ugyanaz a termék korábbi bejegyzései
- Delta számítás: `(jelenlegi - előző) / előző * 100`
- Ha > 15%: `change_tag = "spike"` → sárga/piros + tooltip figyelmeztetés
- Ha stabil: `change_tag = "stable"` → zöld

---

## Commit szabályok

- **Soha nem auto-commit** — minden rögzítés emberi klikk
- Zöld mező: egy klikk OK
- Sárga/narancs/piros: user látja a tooltip-et, majd dönt
- Javítás esetén: user felülírja → a javított érték `golden_example`-ként mentődik (AI tanul belőle)

---

## Golden example visszacsatolás

Ha a user javít egy AI javaslatot:
```
AI javasolta: Bosch DS151i PIR  (confidence: 67%)
User javította: Bosch DS151i PIR mozgásérzékelő beltéri
→ golden_examples-be kerül: raw_name → helyes item_id
→ legközelebb 95%+ lesz ugyanerre
```

Ez az AI önfejlesztési mechanizmusa — nem kell külön "tanítás", a napi munka során tanul.

---

## Státusz: tervezési fázis
- Backend: `ai-suggest` 2. kanyar (Chroma) → v1.2
- Frontend: szín logika + tooltip → v1.2
- `auto_ok` flag átnevezése `ui_prefill`-re → következő commit
