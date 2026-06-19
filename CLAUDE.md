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
- Migrációk sorban: `v02 → v04 → v05 → v06 → v07 → v08` (mind kötelező!)
- v07 új táblák: `golden_examples`, `chroma_index`, Ollama config
- v08 új táblák: `lora_jobs`, lora system_config kulcsok

## Backend fájlok
| Fájl | Mi ez |
|------|-------|
| `main.py` | FastAPI app v1.0 – routerek, audit, chroma, vision, ollama endpointok |
| `auth.py` | PIN auth + 2FA OTP + JWT + admin + config PATCH + change-pin |
| `sanitize.py` | SQL injection / XSS / path traversal middleware |
| `ai_motor.py` | AI azonosítás: Claude → LoRA fine-tuned → Ollama fallback pipeline (v1.0) |
| `lora_router.py` | LoRA tréning kezelő API – indítás/status/aktiválás (v1.0) |
| `lora_train.py` | LoRA standalone tréning szkript – Phi-3-mini/TinyLlama (v1.0) |
| `chroma_motor.py` | ChromaDB vektoros keresés – crt_raw (DB1) + crt_clean (DB2) |
| `vision_motor.py` | LLaVA Vision – kép/PDF elemzés tervrajzokhoz |
| `golden_router.py` | Tanítóadat gyűjtés – golden_examples · batch · JSONL export |
| `web_sources.py` | Webes árforrások CRUD + scripts + Playwright ping |
| `quotes_router.py` | Ajánlat CRUD + sorok + bulk + summary |
| `export_router.py` | Excel + Word + PDF (reportlab) export |
| `prices_router.py` | Árlisták CRUD + best-price + stats |
| `cikktorzs_parse.py` | Fájl beolvasó (xlsx/csv/pdf/docx/html/md) + OCR fallback |

## Frontend oldalak
| Fájl | Státusz |
|------|---------|
| `ui/login.html` | ✅ 2 lépéses PIN + OTP · 4 téma |
| `ui/fomenu.html` | ✅ Főmenü v0.8 · widget link |
| `ui/admin.html` | ✅ Felhasználókezelés · konfig |
| `ui/cikktorzs.html` | ✅ Fa struktúra · AI azonosítás |
| `ui/webes_arak.html` | ✅ Árforrások · Tanít gomb · scriptek |
| `ui/ajanlatkezelo.html` | ✅ 3 mód · cellajelzők · AI · xlsx/docx/PDF export · golden auto-mentés |
| `ui/beallitasok.html` | ✅ SMTP · Claude + Ollama · PIN csere · backup |
| `ui/naplok.html` | ✅ Audit napló · szűrők · CSV |
| `ui/arak.html` | ✅ Árlista · kézi ár · stats |
| `ui/widget.html` | ✅ Státusz widget – API/DB/Ollama/ChromaDB élő jelző |
| `ui/rajz_elemzo.html` | ✅ LLaVA Vision UI – drag&drop kép/PDF, eredmény kártyák, CSV export |
| `ui/lora.html` | ✅ LoRA finomhangolás UI – tréning indítás, live status, aktiválás (v1.0) |

## Séma – fontos mezők
- `products`: item_id (UUID) · crt_code · manufacturer · unit · status
- `activities`: activity_id (UUID) · crt_code · name · unit_type
- `prices`: id · item_id · price_type (lista/kisker/nagyker/egyedi) · price · currency · source_id · db_inserted
- `quotes`: id · quote_number (CRT-YYYY-NNNN) · client_name · client_ref · title · status · source_mode
- `quote_lines`: id · quote_id · line_no · name · raw_name · unit_price · total_price · cell_status · confidence
- `web_sources`: id · name · base_url · source_type · status
- `web_scripts`: id · source_id · script_type · steps (JSONB) · version · active
- `audit_log`: id · user_id · action · entity_type · entity_id · description · ip_address · created_at
- `system_config`: key · value – fontos kulcsok: claude_api_key, smtp_host/port/user/pass, company_name

## Auth
- PIN: bcrypt, 6 számjegy
- 2FA: email OTP, 10 perc érvényes; ha smtp_host üres → OTP csak naplóba kerül (dev mód)
- JWT: HS256, 8 óra, `CRT_JWT_SECRET` env var (dev default: crt_dev_secret_CHANGE_IN_PRODUCTION)
- Brute force: 4 kísérlet → 30 perces zárolás

## API kulcs
- Táblában: `system_config` WHERE key = `claude_api_key`
- Vagy: `ANTHROPIC_API_KEY` environment változó

## Szükséges csomagok
```
py -3.11 -m pip install -r requirements.txt
# vagy manuálisan:
py -3.11 -m pip install fastapi uvicorn sqlalchemy psycopg2-binary bcrypt
py -3.11 -m pip install python-jose[cryptography] openpyxl pdfplumber python-docx
py -3.11 -m pip install beautifulsoup4 anthropic httpx reportlab
py -3.11 -m pip install chromadb sentence-transformers playwright
# OCR (opcionális): pip install pytesseract Pillow  + Tesseract OCR engine
```

## Dokumentációs rendszer
- `CRT_Status.md` – formális státusz (✅🟡🔴, verziók, %)
- `CRT_Chat.md` – projekt chat napló (ötletek, döntések, narratíva)
- `claude/00_session_log.md` – session összefoglalók
- `claude/01_architektura_dontesek.md` – döntések indoklással

**Minden session elején olvasd be a `CRT_Status.md`-t és a `CRT_Chat.md`-t!**

## Claude Code hook – új gépen kötelező beállítani

Ha ezt a projektet új gépen nyitod meg, futtasd le az alábbi parancsot egyszer,
hogy a session-végi autosave hook beálljon a helyi `settings.json`-ba:

```powershell
& "H:\Saját meghajtó\CRT\scripts\setup_claude_hook.ps1"
```

A script tartalma (kézzel is elvégezhető):
- `C:\Users\<felhasználó>\.claude\settings.json`-ba beleírja a Stop hookot
- A hook minden Claude session végén timestampet ír a `CRT_Chat.md`-be

## Teszt környezet (C:\CRT\Segéd)
- `C:\CRT\Segéd\` — H:-ről másolt Windows-natív teszt, NEM törölni H:-t!
- `C:\CRT\db\pgsql\` — PostgreSQL 16 binaries
- Indítási sorrend: `db_init.bat` → `migrate.bat` → `start_backend.bat`
- Ez egy ideiglenes teszt setup — NEM a végleges architektúra

## Architektúrális döntés — WSL2 core (v1.1 irány)
**A CRT elsődleges futtatási környezete: WSL2 Ubuntu 22.04.**
- Windows = host OS + böngésző (UI), semmi más
- WSL2 = backend, PostgreSQL, Ollama, ChromaDB, LoRA — mind Linux alatt
- Hordozható csomag: `ext4.vhdx` (exportálható/importálható)
- Egyetlen belépő: `CRT_install.ps1` → WSL2 + Ubuntu import → szolgáltatás indítás
- Port-forward: WSL2 `localhost:8000` → Windows `localhost:8000` (átlátszó)

## Aktuális státusz
Lásd: `CRT_Status.md` (v1.0, ~100% kész – LoRA pipeline elkészült)

## Következő lépések
### v1.0 véglegesítés (azonnali)
1. `C:\CRT\Segéd\` teszt: `db_init.bat` → `migrate.bat` → `start_backend.bat` → UI teszt
2. Bugfix kör valós ajánlat-munkafolyamaton

### v1.1 — WSL2 core (következő fejlesztési fázis)
1. `CRT_install.ps1` véglegesítése — egyetlen belépőpont, WSL2 + Ubuntu import
2. `build_wsl.sh` frissítése — systemd/loop alatt minden szolgáltatás
3. `start.bat` / `stop.bat` — WSL2 vezérlés Windows oldalról
4. `ext4.vhdx` csomag előállítása (hordozható telepítési egység)
5. Éles teszt WSL2 módban

## Migrációs sorrend (KÖTELEZŐ, friss gépen)
1. `py -3.11 db_migrate_v02.py`
2. `py -3.11 db_migrate_v04.py`
3. `py -3.11 db_migrate_v05.py`
4. `py -3.11 db_migrate_v06.py`
5. `py -3.11 db_migrate_v07.py`  ← golden_examples + chroma_index + Ollama config
6. `py -3.11 db_migrate_v08.py`  ← lora_jobs tábla (v1.0 LoRA pipeline)
