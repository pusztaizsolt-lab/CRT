# CRT Ajánlatsegéd – Projekt Státusz
> v0.3 aktuális állapot · Utolsó frissítés: 2026-05-28

---

## BACKEND – API réteg
```
✅ v0.2  FastAPI szerver          alap · CORS · NTP · logging
✅ v0.1  PostgreSQL séma          14 tábla · v0.2 migráció kész
🟡 ---   Állapotjelző API         /health ✅ · /status/widget ✅ (részleges)
✅ v0.3  Cikktörzs API            /tree · /search · /upload · /identify · /save
🔴 TODO  PIN Auth / JWT           bcrypt · 6 jegyű PIN · token kezelés
🔴 TODO  Ajánlat API              /quotes · CRUD · NTP időbélyeg
🔴 TODO  Ár API                   /prices · lista/kisker/nagyker/egyedi szint
🟡 v0.3  Feltöltés pipeline       xlsx · csv · pdf · docx · html · md parser ✅
🟡 v0.3  AI Motor API             Claude identify ✅ · helyi LLM 🔴 · fallback 🟡
🔴 TODO  Export API               Excel · Word · PDF
🔴 TODO  Webes ár scraper         preferált nagyker URL lista
🔴 TODO  Sanitizálási middleware  MINDEN adat kötelező átjárója
🔴 TODO  Admin API                /admin · rendszergazda végpontok
```

## ADATBÁZIS
```
✅ v0.2  Cikktörzs táblák         products · activities · categories
           + crt_code · supplier_code · model (v0.2 migráció)
✅ v0.2  Árnapló tábla            prices · lista/kisker/nagyker/egyedi · db1/db2/master
✅ v0.1  Ajánlat táblák           quotes · quote_cells · tenders
✅ v0.1  Audit / Napló táblák     audit_log · recycle_bin · system_config
✅ v0.2  Migráció script          db_migrate_v02.py · ALTER TABLE · next_crt_code()
🔴 TODO  ChromaDB – DB1           nyers vektorok (azonosítás előtt)
🔴 TODO  ChromaDB – DB2           tisztított vektorok (sanitizált)
🔴 TODO  Arany Példatár           golden_examples · LoRA tanítóadat
```

## FRONTEND – Felhasználói felületek
```
🔴 TODO  Bejelentkezés            felhasználónév + 6 jegyű PIN
🔴 TODO  Főmenü                   navigáció · összesítő nézet
🔴 TODO  Ajánlatkészítő           3 indítási mód · cellajelzők
🟡 v0.3  Cikktörzs kezelő         fa struktúra · keresés · feltöltés · review tábla · AI
🔴 TODO  Webes árak               nagyker URL lista kezelő
🔴 TODO  Naplók / Audit           napló néző · szűrők
🔴 TODO  Beállítások              kapcsolatok · preferált URL-ek · PIN csere
🔴 TODO  Admin konzol             felhasználók · jogosultságok
🔴 TODO  Állapotjelző widget      tálca · zöld / piros pont
🔴 TODO  META fejlesztői platform fejlesztői eszközök · tesztelő
```

## AI & OCR réteg
```
🟡 v0.3  Claude API fallback      /cikktorzs/identify · termék azonosítás · token tracking
🔴 TODO  Helyi LLM motor          llama-cpp · llamafile portable
🔴 TODO  Azonosító motor          cikk / tevékenység AI osztályozó
🔴 TODO  OCR feldolgozó           pytesseract · pdfplumber · docx ✅ (parse kész)
🔴 TODO  Embedding motor          sentence-transformers · ChromaDB
🔴 TODO  Rajz komparátor          LLaVA Vision · tervrajz felismerés
```

---

## Összesített haladás

| Réteg      | Kész | Részleges | Összes | % |
|------------|------|-----------|--------|---|
| Backend    | 4    | 3         | 13     | 31% |
| Adatbázis  | 5    | 0         | 8      | 63% |
| Frontend   | 0    | 1         | 10     | 5%  |
| AI / OCR   | 0    | 1         | 6      | 8%  |
| **TOTAL**  | **9**| **5**     | **37** | **~25%** |

---

## Mérföldkövek

```
v0.1  ✅  DB séma (2026-05-18)
v0.2  ✅  FastAPI gerinc + állapotjelző (2026-05-18)
v0.3  ✅  Cikktörzs API + UI + fájl parser + AI azonosítás (2026-05-28)
           · products: +crt_code · +supplier_code · +model
           · prices:   +price_type (lista/kisker/nagyker/egyedi)
           · Frontend: cikktorzs.html – fa struktúra · review tábla · Claude AI
v0.4  🔴  PIN Auth + JWT
v0.5  🔴  Ár API + sanitizálási réteg
v0.6  🔴  Ajánlat API + export
v0.7  🔴  Feltöltés teljes OCR + helyi LLM
v0.8  🔴  Frontend (bejelentkezés + főmenü + ajánlatkészítő)
v0.9  🔴  Frontend (webes árak + beállítások + admin)
v1.0  🔴  Widget + teljes integráció + LoRA tanítóadat
```

---

## Fejlesztési környezet
```
Elsődleges hely:   H:\Saját meghajtó\CRT\   (Google Drive – szinkronizált)
Korábbi hely:      C:\CRT\                   (lokális – archiválható)
Drive szinkron:    IGEN – kód, UI, schema fájlok
KIVÉTEL:           H:\Saját meghajtó\CRT\db_data\  ← NEM szinkronizálni!
                   (PostgreSQL bináris adatok – szinkron közben sérülhet)
Másik gépen:       Google Drive → H:\Saját meghajtó\CRT\ + CLAUDE.md alapján
```

## v0.3 – Új / módosított fájlok

| Fájl | Leírás |
|------|--------|
| `ui/cikktorzs.html` | Cikktörzs kezelő ablak – fa · keresés · feltöltés · AI review |
| `cikktorzs_parse.py` | Fájl beolvasó modul – xlsx/csv/pdf/docx/html/md |
| `db_migrate_v02.py` | Adatbázis migráció – új oszlopok + CRT kód generátor |
| `CLAUDE.md` | Claude kontextus összefoglaló – gépen átadáshoz |
| `migrate_to_drive.ps1` | Migrációs script – C:\CRT → H:\Saját meghajtó\CRT |

## Szükséges Python csomagok (v0.3)
```
py -3.11 -m pip install fastapi uvicorn sqlalchemy psycopg2-binary ntplib
py -3.11 -m pip install openpyxl pdfplumber python-docx beautifulsoup4 anthropic
```
