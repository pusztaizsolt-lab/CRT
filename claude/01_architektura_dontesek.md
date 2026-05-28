# CRT – Architektúra döntések
> 2026-05-27 | Forrás: Claude beszélgetés | v2

---

## 1. Kezelőpult (dashboard)

- Fájl: `C:\CRT\ui\kezelőpult.html` (mindig legfrissebb)
- Verzióz ott: `kezelőpult_v1.html` stb. – nagyobb változásnál másolat
- Zöld keret = kész · Piros = inaktív · Sárga = részleges · **Lila = védett/admin**
- Haladásjelző sáv + élő server-state (`/health`)
- Projekt státusz fa: `C:\CRT\CRT_Status.md`

---

## 2. Első modul – Ajánlat összerakó

### Munkamenet
```
EREDETI FELTÖLTÖTT DOKUMENTUM
  └──→ SOHA NEM MÓDOSUL (formázás védve – decipher tönkreteszi!)
  └──→ MÁSOLAT készül → ezen dolgozunk
            │
            ▼
      TANÍTÓ / KALKULÁCIÓS RÉSZ
      • Kalkulációs táblák hozzáadva (nem az eredetihez!)
      • Beszállítói számok oszlopa
      • Alvállalkozói számok oszlopa
      • Sablon választás (1..N – gusztus dolga)
            │
            ▼
      ÖSSZESZERELÉS → LETÖLTÉS
```

### v1 – Szerkesztő ablak (jövő)
- Office-szerű ablak nyílik a másolaton
- Ismeretlen adatok kézi bevitele
- Formázás elvégezhető
- Elfogad gomb → adatbázisba kerül

---

## 3. Centrális AI mag – kulcsdöntés

**Egyszer építjük meg, minden modul ezt használja.**

```
┌─────────────────────────────────────────────┐
│           CENTRÁLIS AI MAG                  │
│                                             │
│  OCR / parser        pytesseract, pdfplumber│
│  Struktúra felismerő táblák, oszlopok       │
│  Adat kinyerő        árak, mennyiségek      │
│  Fuzzy komparátor    nem pont egyezők!      │
│  ChromaDB            formai minták          │
│  LLaMA               értelmező réteg        │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┬──────────────┐
        ▼          ▼          ▼              ▼
   Ajánlat    Cikktörzs  Sanitizálás    [jövő...]
   összerakó  azonosítás  réteg
```

### Fuzzy komparátor – réteges logika
```
1. Pontos egyezés        → automatikus
2. Helyi LLaMA fuzzy     → automatikus  (ha confidence > 0.70)
3. Claude / Gemini API   → ⚠️ KÉZI JÓVÁHAGYÁS  (popup!)
4. Megoldatlan           → kézi bevitel
```

**Miért?**
- Adatvédelem: üzleti árak, partneri adatok ne menjenek ki automatikusan
- Költségkontroll: API hívás = pénz, ne menjen vakon

---

## 4. Külső API jóváhagyó popup

Minden külső AI API hívás előtt felugrik – komponens: `kezelőpult.html` → újrahasználható minden oldalon.

### Mit mutat:
```
• Feladat leírása  (mit kér a motor)
• Model neve       (claude-sonnet-4-6 / gemini stb.)
• Becsült token    (~1 200 token)
• Becsült költség  (~42 Ft)
• Keret felhasználás % + progress bar (zöld/sárga/piros)
• Maradék token
• ⚠️ Figyelmeztetés ha keret > 80%
• [Jóváhagyom]  [Elutasítom]
```

### Fejlesztői teszt: F2 billentyű → popup előugrik

### Backend API szükséges (még TODO):
- `GET /admin/api-status` → aktuális token használat, keret
- `POST /admin/api-approve` → naplózza a jóváhagyást

---

## 5. Védett beállítások szekció (lila kártyák)

PIN újra bekér módosításkor (whitepaper mérnöki 4.4).

| Elem | Tartalom |
|------|----------|
| API beállítások | Claude · Gemini · partner API kulcsok |
| Kapcsolatok | preferált nagyker URL-ek · belépési adatok |
| AI keret / Token limit | havi limit · felhasználónkénti keret · riasztás % |
| Felhasználók | PIN kezelés · jogosultságok · zárolás |

---

## 6. Build sorrend

```
✅ v0.1  DB séma (14 tábla)
✅ v0.2  FastAPI gerinc + állapotjelző
🔴 v0.3  PIN Auth + JWT (bcrypt · 6 jegyű PIN · token)
🔴 v0.4  Centrális AI mag
           ├── OCR / parser
           ├── Struktúra felismerő
           ├── Fuzzy komparátor
           ├── ChromaDB integráció
           └── LLaMA alap
🔴 v0.5  Ajánlat összerakó (AI magra épül)
🔴 v0.6  Cikktörzs azonosítás (AI magra épül)
🔴 v0.7  Sanitizálási réteg (AI magra épül)
🔴 v0.8  Feltöltő + export
🔴 v0.9  Frontend (bejelentkezés · főmenü · ajánlatkészítő)
🔴 v1.0  Admin konzol · védett beállítások · widget · szerkesztő ablak
```

---

## 7. Whitepaper referenciák

| Doki | Elérési út |
|------|-----------|
| Felhasználói v1.3 | `h:\Saját meghajtó\MUNKA MEGOSZTÁS\Segéd\1,2\files\CRT_WhitePaper_Felhasználói_v1.3.md` |
| Mérnöki v1.3 | `h:\Saját meghajtó\MUNKA MEGOSZTÁS\Segéd\1,2\files\CRT_WhitePaper_Mérnöki_v1.3.md` |

---

`[CTX: crt-arch-v2 | 2026-05-27 | ai-mag | fuzzy-reteg | api-popup | vedett-beallitasok | build-order]`
