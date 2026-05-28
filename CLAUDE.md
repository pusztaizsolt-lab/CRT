# CRT Ajánlatsegéd – Claude kontextus

## Mi ez?
AI alapú ajánlatkészítő szoftver – Civil Rendszertechnika Kft.
Automatikus árkeresés, összehasonlítás, ajánlat-dokumentum generálás.

## Projekt helye
- **Elsődleges:** `H:\Saját meghajtó\CRT\` (Google Drive, szinkronizált)
- **DB adatok:** `H:\Saját meghajtó\CRT\db_data\` – NEM szinkronizálni futás közben!

## Technológia
- Backend: Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL (bundled, `db\pgsql\`)
- Frontend: Vanilla HTML/CSS/JS (böngészőben fut, nincs Node/npm)
- AI: Claude API (`claude-sonnet-4-6`) – termék azonosítás
- Indítás: `start.bat` vagy `CRT.hta`

## Adatbázis
- Host: `localhost:5432` · DB: `crt` · User: `crt_user` · Pass: `crt2026`
- 14 tábla, v0.2 séma
- Migráció: `py -3.11 db_migrate_v02.py`

## Fő fájlok
| Fájl | Mi ez |
|------|-------|
| `main.py` | FastAPI backend – minden API endpoint |
| `cikktorzs_parse.py` | Fájl beolvasó (xlsx/csv/pdf/docx/html/md) |
| `db_schema.py` | SQLAlchemy modellek (products, activities, prices...) |
| `db_migrate_v02.py` | DB migráció – crt_code, supplier_code, model, price_type |
| `ui/kezelőpult.html` | Fejlesztői dashboard (kártyák, státusz) |
| `ui/cikktorzs.html` | Cikktörzs kezelő – fa struktúra · keresés · AI review |
| `CRT_Status.md` | Részletes projekt státusz |

## Séma – fontos mezők
- `products`: item_id · **crt_code** (CRT-P-000001) · **supplier_code** · manufacturer · **model** · name
- `activities`: activity_id · **crt_code** (CRT-A-000001) · name · unit_type
- `prices`: price_id · item_id · **price_type** (lista/kisker/nagyker/egyedi) · db_level (db1_raw/db2_refined/db_master)

## API kulcs
- Táblában: `system_config` WHERE key = `claude_api_key`
- Vagy: `ANTHROPIC_API_KEY` environment változó

## Szükséges csomagok
```
py -3.11 -m pip install fastapi uvicorn sqlalchemy psycopg2-binary ntplib
py -3.11 -m pip install openpyxl pdfplumber python-docx beautifulsoup4 anthropic
```

## Aktuális státusz
Lásd: `CRT_Status.md` (v0.3, ~25% kész)

## Következő lépés
v0.4 – PIN Auth + JWT bejelentkezés (bcrypt, 6 jegyű PIN, token)
