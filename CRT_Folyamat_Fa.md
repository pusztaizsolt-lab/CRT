# CRT Ajánlatsegéd – Folyamat és Funkció Fa
> Rendszer áttekintés cégvezetési referencia célra
> v1.4 · 2026-05-30

---

## A rendszerről egy mondatban
Ajánlatkészítést segítő rendszer: automatikusan keres árakat, azonosítja a termékeket, és elkészíti a kitöltött ajánlati dokumentumot – emberi jóváhagyással minden kritikus lépésnél.

---

## RENDSZER INDÍTÁS
```
[RENDSZER INDÍTÁS]
│
├── [1] Mappa elérés (OS szintű védelem)
│
├── [2] Rendszeradmin felület megnyitása (csak helyi)
│   └── Admin bejelentkezés
│       ├── PIN kód
│       └── Email 2FA kód
│
├── [3] Szerver indítás (admin explicit indítja)
│   ├── PostgreSQL adatbázis ellenőrzés / indítás
│   ├── FastAPI backend indítás
│   └── Állapotjelző widget aktiválás
│
└── [4] Felületek elérhetővé válnak
    ├── Felhasználói felület (1-es)
    ├── Rendszeradmin felület (2-es) ← már aktív
    └── Diagnosztikai felület (3-as)
```

---

## 1-ES FELÜLET – FELHASZNÁLÓI
```
[FELHASZNÁLÓI FELÜLET]
│
├── [BEJELENTKEZÉS]
│   ├── Felhasználónév + PIN kód
│   ├── Email 2FA kód (automatikusan kiküldve)
│   └── Állapotjelző: zöld pont = rendben · piros = hiba
│
├── [FŐMENÜ]
│
├── [AJÁNLATKÉSZÍTŐ]
│   ├── Indítási módok
│   │   ├── Üres ajánlat (nulláról)
│   │   ├── Sablon alapján
│   │   └── Feltöltött dokumentumból
│   │
│   ├── Cellajelzők
│   │   ├── Forrás jelzés (honnan jött az adat)
│   │   ├── Frissesség jelzés (milyen régi)
│   │   └── Megbízhatóság % 
│   │
│   ├── Adat mentés
│   │   ├── Igen – automatikusan adatbázisba
│   │   ├── Igen – de előbb ellenőrzöm
│   │   └── Nem – csak az ajánlathoz kell
│   │
│   └── Exportálás
│       ├── Excel
│       ├── Word
│       └── PDF
│
├── [CIKKTÖRZS]
│   ├── Termékek (materiális)
│   │   └── Hierarchikus kategória fa
│   ├── Tevékenységek (immateriális)
│   │   └── Hierarchikus kategória fa
│   ├── Keresés
│   ├── Feltöltés (xlsx/csv/pdf/docx/html)
│   │   └── AI azonosítás → jóváhagyó popup → DB
│   └── AI Review tábla
│
└── [API KULCSOK ÉS ADATFORRÁSOK]
    │
    ├── [Forrás weboldalak]
    │   ├── URL lista kezelés
    │   ├── Státusz: Elérve · Megtanulva
    │   └── Tanít gomb
    │       └── Felhasználó megmutatja az aloldalakat
    │           └── Rendszer rögzíti → önállóan navigál
    │
    ├── [Forrás kereskedői oldalak]
    │   ├── URL + felhasználónév + jelszó tárolás (titkosítva)
    │   ├── Státusz: Elérve · Megtanulva
    │   └── Tanít gomb (speciális)
    │       ├── Rögzítő mód indul
    │       ├── Felhasználó elvégzi a belépést
    │       ├── Rendszer rögzíti a műveletsort
    │       ├── AI általánosítja a szekvenciát
    │       └── Önálló belépés legközelebb
    │
    ├── [Kereskedői API kulcsok]
    │   └── Közvetlen API hozzáférés kulcsai
    │
    └── [AI API kulcsok]
        ├── Claude API (Anthropic)
        └── Egyéb AI szolgáltatások
```

---

## 2-ES FELÜLET – RENDSZERADMIN
```
[RENDSZERADMIN FELÜLET]
│
├── [SZERVER VEZÉRLÉS]
│   ├── Szerver indítás / leállítás
│   ├── Adatbázis állapot
│   └── Rendszer napló
│
├── [FELHASZNÁLÓ KEZELÉS]
│   ├── Új felhasználó létrehozása
│   │   ├── Felhasználónév
│   │   ├── PIN beállítás
│   │   ├── Email cím (2FA-hoz)
│   │   └── Jogosultsági szint (user / admin)
│   ├── Felhasználó módosítás
│   ├── Felhasználó letiltás / törlés
│   │   └── 3 lépéses megerősítés kötelező
│   └── Zárolás feloldás (brute force után)
│
├── [RENDSZERBEÁLLÍTÁSOK]
│   ├── Email szerver konfiguráció (2FA küldéshez)
│   ├── API keret / token limit beállítás
│   └── Biztonsági paraméterek
│
└── [AUDIT NAPLÓ]
    ├── Belépési előzmények
    ├── Módosítások naplója
    └── AI hívások naplója
```

---

## 3-AS FELÜLET – DIAGNOSZTIKAI
```
[DIAGNOSZTIKAI FELÜLET]
│
├── [FOLYAMAT MONITOR]
│   ├── Párhuzamos folyamatok élő státusza
│   ├── Scraper futások állapota
│   ├── AI motor terhelés
│   └── DB kapcsolat állapot
│
├── [ADATBÁZIS NÉZET]
│   ├── Táblák tartalma (olvasható)
│   ├── Szűrési paraméterek tesztelése
│   └── Napló viewer
│
└── [RENDSZERPARAMÉTEREK]
    ├── Token használat / keret
    ├── Scraper szekvenciák listája
    └── ChromaDB vektorok állapota
```

---

## HÁTTÉR FOLYAMATOK
```
[HÁTTÉR FOLYAMATOK]
│
├── [WEBES ADATGYŰJTÉS]
│   ├── Ütemezett scraper futások
│   │   ├── Nyilvános webshopok (Playwright)
│   │   └── Kereskedői portálok (rögzített szekvencia)
│   ├── Hiba esetén: AI javítja a szekvenciát
│   └── Eredmény → Sanitizálás → Adatbázis
│
├── [AI MOTOR]
│   ├── Termék azonosítás (feltöltéskor)
│   │   ├── Helyi LLM (elsőként)
│   │   └── Claude API (jóváhagyás után)
│   ├── Weboldal struktúra felismerés (tanításkor)
│   ├── Szekvencia javítás (hiba esetén)
│   └── Fuzzy komparátor (hasonló tételek)
│
└── [SANITIZÁLÁSI RÉTEG]
    └── MINDEN adat kötelező átjárója DB felé
        ├── Kód injekció szűrés
        ├── Forrás és megbízhatóság jelölés
        └── NTP időbélyeg rögzítés
```

---

## ADATTÁROLÁS
```
[ADATTÁROLÁS]
│
├── [PostgreSQL] – strukturált adatok
│   ├── products (cikktörzs)
│   ├── activities (tevékenységi törzs)
│   ├── prices (árnapló)
│   ├── quotes / quote_cells (ajánlatok)
│   ├── users (felhasználók)
│   ├── auth_tokens (2FA kódok)
│   ├── web_scripts (scraper szekvenciák)
│   ├── audit_log (napló)
│   └── system_config (beállítások)
│
├── [ChromaDB] – vektorok
│   ├── DB1: nyers vektorok (azonosítás előtt)
│   ├── DB2: tisztított vektorok (sanitizált)
│   └── Weboldal sablon minták (scraper)
│
└── [Fájlrendszer] – dokumentumok
    ├── Feltöltött eredeti fájlok (csak olvasható)
    └── Exportált ajánlatok
```

---

## BIZTONSÁGI MODELL
```
[BIZTONSÁGI RÉTEGEK]
│
├── Fizikai: mappa OS-szintű védelme
├── Hálózati: szerver csak admin indítása után fut
├── Hitelesítés: PIN + email 2FA minden felhasználónak
├── Jogosultság: user / admin szintek
├── Brute force: 4 hibás kísérlet → 30 perc zárolás
├── Törlés: 3 lépéses megerősítés kötelező
├── Audit: minden művelet naplózva névvel + időponttal
└── Adat: eredeti dokumentum soha nem módosul
```

---

`[CTX: crt-folyamat-fa-v1.4 | 2026-05-30]`
