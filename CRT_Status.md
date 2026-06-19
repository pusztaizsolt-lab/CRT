# CRT Ajánlatsegéd – Projekt Státusz (White Paper)
> **v1.0 kész · v1.1 folyamatban: WSL2 core architektúra** · Utolsó frissítés: 2026-06-12

> **Claude:** olvasd be ugyanebből a mappából a `CLAUDE.md` fájlt is (rendszer kontextus)!

---

## TL;DR – Hol tartunk most?

A rendszer **funkcionálisan teljes** az ajánlatkészítési alaptörvényig:
bejelentkezés → cikktörzs → ajánlat létrehozás → export (xlsx/docx).
Az **AI azonosítás** Claude API-n át működik, a **helyi LLM** (Ollama) infrastruktúra
fel van készítve (build_wsl.sh letölti), de a fallback logika még nincs bekötve.
Az **installation package** WSL2 Ubuntu alapú, ~13GB bootstrap, 250GB SSD-re tervezett.

---

## BACKEND – API réteg

```
✅ v0.2  FastAPI szerver          main.py · CORS · NTP · SanitizeMiddleware · logging
✅ v0.2  PostgreSQL séma          14 tábla · db_schema.sql
✅ v0.4  Állapotjelző API         /health · /status/widget
✅ v0.3  Cikktörzs API            /cikktorzs/ · /tree · /search · /upload · /identify · /save
✅ v0.4  PIN Auth / JWT + 2FA     auth.py · bcrypt · 6 jegyű PIN · email OTP · JWT 8h
                                  brute force: 4 kísérlet → 30 perc zárolás
✅ v0.4  Admin API                /auth/admin/users · CRUD · unlock · PIN reset
✅ v0.5  Config API               /auth/admin/config GET/PATCH · test-smtp · change-pin
✅ v0.4  Sanitizálási middleware  sanitize.py · SQL inj · XSS · path traversal · 512KB limit
✅ v0.3  Feltöltés pipeline       cikktorzs_parse.py · xlsx/csv/pdf/docx/html/md parser
✅ v0.5  Ajánlat API              quotes_router.py · CRUD · quote_lines · bulk · summary
✅ v0.5  Webes ár scraper API     web_sources.py · CRUD · ping · scripts · web_prices
✅ v0.5  Ár API                   prices_router.py · lista/kisker/nagyker/egyedi · best · stats
✅ v0.5  Export API               export_router.py · xlsx (openpyxl) · docx (python-docx)
✅ v0.5  Audit log API            /audit/logs · szűrhető · lapozható · CSV export
✅ v0.5  Backup API               /admin/backup · JSON snapshot 12 tábla
🟡 v0.3  AI Motor API             Claude identify ✅ · helyi LLM infrastruktúra kész · fallback 🔴
✅ v0.6  Playwright scraper       POST /scripts/{id}/run · navigate/click/fill/extract · web_prices mentés
✅ v0.7  Helyi LLM fallback       ai_motor.py · Claude → Ollama fallback · ollama_status endpoint
✅ v0.7  ChromaDB embedding       chroma_motor.py · crt_raw (DB1) · crt_clean (DB2)
                                  /chroma/search · /chroma/stats · auto-index mentéskor
```

---

## ADATBÁZIS

```
✅ v0.2  Cikktörzs táblák         products · activities · categories
                                  + crt_code · supplier_code · model
✅ v0.2  Árnapló tábla            prices · lista/kisker/nagyker/egyedi
✅ v0.5  Ajánlat táblák           quotes (bővített) · quote_lines · cellajelzők
                                  source_mode / source_file / base_quote_id / client_ref
                                  confidence / price_source / item_id (quote_lines-ban)
✅ v0.1  Audit / Napló            audit_log (description, ip_address, entity_id) · recycle_bin
✅ v0.4  Auth táblák              users (email/locked_until/attempt_count) · auth_tokens
✅ v0.5  Scraper táblák           web_sources · web_scripts · web_prices
                                  prices.source_id / supplier_code / currency
✅ v0.5  System config            system_config · claude_api_key · smtp · ai_conf_* stb.
✅ v0.6  Migráció scriptek        db_migrate_v02 · v04 · v05 · v06 (kötelező sorrend!)
                                  v06: IF NOT EXISTS bővítések + indexek (audit, prices, q-lines)
✅ v0.7  ChromaDB – DB1           crt_raw · nyers sorok (identify előtt auto-indexelve)
✅ v0.7  ChromaDB – DB2           crt_clean · cikktörzs mentéskor auto-indexelve
✅ v0.8  Arany Példatár           golden_router.py · JSONL/JSON/CSV export · auto-mentés acceptAll()-ból
```

---

## FRONTEND – Felhasználói felületek

```
✅ v0.4  Bejelentkezés            login.html · PIN + OTP 2 lépés · 4 CSS téma · visszaszámláló
✅ v0.5  Főmenü                   fomenu.html · 9 aktív kártya · státusz chip-ek · v0.5 badge
✅ v0.4  Admin konzol             admin.html · felhasználók · unlock · PIN reset · konfig
✅ v0.4  Diagnosztikai kezelőpult kezelőpult_v2.html · 4 téma · Paletta szerkesztő (11 picker)
✅ v0.3  Cikktörzs kezelő         cikktorzs.html · fa struktúra · keresés · feltöltés · AI
                                  + natív fájlmegnyitás (Excel/Word gomb)
✅ v0.5  Ajánlatkészítő           ajanlatkezelo.html · 3 indítási mód:
                                    Üres ajánlat / Feltöltött ajánlatkérő / Korábbi másolat
                                  Cell status jelzők: raw/identified/uncertain/manual/skip/done
                                  AI azonosítás popup jóváhagyással (acceptAll/rejectAll)
                                  Export: xlsx + docx · Árak: GET /prices/best/{item_id}
✅ v0.5  Webes árak               webes_arak.html · forrás lista · Tanít gomb · script rögzítés
✅ v0.5  Beállítások              beallitasok.html · SMTP · AI/Claude · Webes árak
                                  PIN csere (3×6 PIN doboz) · Megjelenés · Verzió · Backup
✅ v0.5  Naplók / Audit           naplok.html · szűrők (q/akció/entitás/dátum/user_id)
                                  CSV export BOM · részlet panel · auto-refresh 60 mp
                                  kor jelzők (age-dot) · akció badge-ek (ab-login/ab-create stb.)
✅ v0.5  Árak UI                  arak.html · stat sáv (total/egyedi/forrás/friss/utolsó frissítés)
                                  szűrők · kor jelzők (fresh/warn/old) · típus chipek
                                  kézi ár modal (min 3 kar keresés) · CSV export
```

### CSS témák (4 db – CSS custom properties)
```
  ejszaka  – sötét, fekete-szürke
  ocean    – kék-cián árnyalatok
  forest   – zöld-meleg tónusok
  steel    – acélszürke, ipari
  localStorage kulcs: crt-theme
```

### localStorage kulcsok
```
  crt-token      JWT token
  crt-user       felhasználónév
  crt-role       role (admin/user)
  crt-login-ts   belépés időbélyege
  crt-theme      aktív téma
```

---

## AI & OCR réteg

```
✅ v0.3  Claude API               /cikktorzs/identify · termék azonosítás · token tracking
                                  konfig: beallitasok.html → PATCH /auth/admin/config
✅ v0.7  Helyi LLM motor          Ollama llama3:8b / mistral:7b · ai_motor.py fallback
                                  infrastruktúra: build_wsl.sh · service · beallitasok.html UI
✅ v0.7  Embedding motor          sentence-transformers · chroma_motor.py
                                  crt_raw (DB1) · crt_clean (DB2) · cosine similarity
✅ v0.8  OCR                      pdfplumber ✅ · pytesseract + Pillow fallback ✅
✅ v0.9  Rajz komparátor          vision_motor.py · LLaVA Vision · rajz_elemzo.html UI
✅ v1.0  LoRA finomhangolás        lora_train.py · lora_router.py · ui/lora.html
                                  Claude → LoRA fine-tuned → Ollama fallback lánc
                                  Alapmodellek: Phi-3-mini (GPU) / TinyLlama (CPU)
                                  db_migrate_v08 · GET/POST /lora/* · aktiválás UI
```

---

## DEPLOYMENT ARCHITEKTÚRA (v0.5 döntés)

```
Cél platform:   Windows szerver (Win10/11, x64)
Tárhely:        250GB SSD dedikált lemez
Telepítési mód: 2 fázis:
  1. Bootstrap ZIP   – kis csomag (~50MB scripts + ui + python kód)
  2. Intelligent installer – felméri rendszert, telepít mindent helyben (~13GB)

Futtatókörnyezet (WSL2 mód – ajánlott):
  ┌─── Windows host ─────────────────────────────────────┐
  │  start.bat → wsl -d CRT → wsl_start.sh              │
  │  Böngésző: http://localhost (Nginx kiszolgál)        │
  │                                                       │
  │  ┌── WSL2 Ubuntu 22.04 (CRT disztribúció) ────────┐  │
  │  │  PostgreSQL 16    → localhost:5432             │  │
  │  │  FastAPI/uvicorn  → localhost:8000 (2 worker)  │  │
  │  │  ChromaDB         → localhost:8001             │  │
  │  │  Ollama LLM       → localhost:11434            │  │
  │  │  Nginx            → localhost:80               │  │
  │  └─────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────┘

Fallback (natív mód – ha WSL2 nincs):
  PostgreSQL portable + uvicorn + ui/login.html direkt

Helyigény (becsült):
  WSL2 Ubuntu base:    ~1.2 GB
  Python + csomagok:   ~800 MB
  Playwright Chromium: ~350 MB
  llama3:8b modell:    ~5.0 GB
  mistral:7b modell:   ~4.5 GB
  ChromaDB + vektorok: ~500 MB
  CRT kód + UI:        ~50  MB
  PostgreSQL adatok:   ~100 MB (üzemi induláskor)
  ─────────────────────────────
  ÖSSZESEN:            ~12.5 GB  (szabad: 250GB − 13GB ≈ 237GB)
```

---

## MAPPASTRUKTÚRA (SSD-n)

```
D:\CRT\  (vagy H:\Saját meghajtó\CRT\)
├── ui\                    HTML oldalak (fomenu, login, admin, ...)
├── db_data\
│   ├── pg\                PostgreSQL adatkönyvtár  ← NE szinkronizáld!
│   └── backups\           JSON backup snapshot-ok
├── models\
│   └── ollama\            Helyi LLM modellek (llama3:8b, mistral:7b)
├── vectors\
│   └── chroma\            ChromaDB vektoros adatbázis
├── logs\
│   ├── backend\           FastAPI naplók
│   ├── nginx\             Nginx access/error
│   └── install\           Telepítési napló
├── uploads\               Feltöltött fájlok (pdf, xlsx, docx)
├── wsl\                   WSL2 Ubuntu 22.04 ext4.vhdx
├── _setup\
│   ├── CRT_install.ps1    Intelligens Windows telepítő (helyigény, GPU, WSL2 detekció)
│   ├── build_wsl.sh       Ubuntu belső telepítő (PG16, Py3.11, Ollama, ChromaDB, Nginx)
│   └── wsl_start.sh       Univerzális Linux indítószkript (wsl2 + bare metal)
├── env_detect.py          Platform detekció + runtime dir kezelés (v1.0+)
├── main.py                FastAPI belépőpont (v1.0)
├── auth.py                Auth + Config + 2FA router
├── quotes_router.py       Ajánlat API
├── export_router.py       xlsx / docx export
├── prices_router.py       Ár API
├── web_sources.py         Webes scraper API
├── sanitize.py            Biztonsági middleware
├── db_schema.sql          Alap séma (v0.1)
├── db_migrate_v02.py      Migráció
├── db_migrate_v04.py      Migráció
├── db_migrate_v05.py      Migráció (web_sources, quotes)
├── db_migrate_v06.py      Migráció (bővítések + indexek)
├── requirements.txt       Python függőségek (pin-elt verziók)
├── docker-compose.yml     Docker alternatíva (opcionális)
├── start.bat              Napi indítás (WSL2 + natív fallback)
├── stop.bat               Leállítás
├── status.bat             Futó szolgáltatások ellenőrzése
├── install.bat            Telepítő belépőpont (admin jogosultság kell)
├── .env.example           Környezeti változók sablon
├── .env                   Éles konfig (NEM szinkronizálni!)
├── CLAUDE.md              Claude kontextus (gépen átadáshoz)
├── CRT_Status.md          ← EZT OLVASOD
├── CRT_Whitebook_v1.0.md  Fehér könyv (teljes rendszer leírás)
├── CRT_Whitebook_v1.0.html Whitebook – navigálható HTML
├── CRT_Security_Audit_v1.0.md  Biztonsági audit (2 kritikus!)
├── CRT_Kezikonyv_v1.0.md  Kezelői kézikönyv (admin + user)
└── CRT_Kezikonyv_v1.0.html Kézikönyv – navigálható HTML
```

---

## MÉRFÖLDKÖVEK

```
✅  v0.1  (2026-05-18)  DB séma – 14 tábla alapok

✅  v0.2  (2026-05-18)  FastAPI gerinc + állapotjelző + alapszolgáltatások

✅  v0.3  (2026-05-28)  Cikktörzs API + UI + fájl parser + AI azonosítás
                         GitHub repo + VS Code konfig + Google Drive sync

✅  v0.4  (2026-06-08)  Auth rendszer teljes:
                           PIN + OTP + JWT 8h + brute force + sanitize middleware
                           login.html · admin.html · fomenu.html

✅  v0.5  (2026-06-08)  Ajánlatkészítés + export + árak + naplók + beállítások:
                           Backend: quotes_router · export_router · prices_router
                                    config PATCH/GET/test-smtp · audit logs · backup
                           Frontend: ajanlatkezelo · arak · naplok · beallitasok · webes_arak
                                     fomenu (9 aktív kártya) frissítve
                           DB: db_migrate_v06 (bővítések + indexek)
                           Infra: requirements.txt · docker-compose.yml
                                  start/stop/status/install.bat
                                  _setup/CRT_install.ps1 (intelligens telepítő)
                                  _setup/build_wsl.sh (Ubuntu belső telepítő)
                                  .env.example · 250GB SSD terv rögzítve

✅  v0.6  (2026-06-09)  Playwright scraper + nginx.conf + admin init + backend fixes:
                           web_sources.py: POST /scripts/{id}/run (Playwright, extract→web_prices)
                           _setup/nginx/nginx.conf: standalone sablon, build_wsl.sh frissítve
                           _setup/create_admin.py: interaktív admin init script
                           main.py: v0.6 verzió string, backup abszolút path, backups/ almappa
✅  v0.7  (2026-06-10)  Helyi LLM fallback + ChromaDB embedding motor:
                           ai_motor.py: Claude → Ollama fallback pipeline
                           chroma_motor.py: crt_raw (DB1) + crt_clean (DB2)
                           db_migrate_v07.py: golden_examples + chroma_index + Ollama config
                           /chroma/search · /chroma/stats · /ollama/status

✅  v0.8  (2026-06-10)  OCR + PDF export + Golden examples + SSD csomag + Widget:
                           export_router.py: reportlab PDF (A4, dark theme, összesítő sor)
                           cikktorzs_parse.py: pytesseract OCR 3. fallback
                           golden_router.py: JSONL/JSON/CSV export · batch · auto-mentés
                           vision_motor.py: LLaVA Vision alap infrastruktúra
                           _setup/build_package.ps1: Bootstrap ZIP csomagoló
                           ui/widget.html: Élő státusz widget (API/DB/Ollama/ChromaDB)
                           ui/beallitasok.html + ajanlatkezelo.html: Ollama UI + golden

✅  v0.9  (2026-06-10)  Rajz komparátor (LLaVA Vision):
                           ui/rajz_elemzo.html: teljes Vision UI (drag&drop, PDF oldal, eredmény kártyák)
                           build_wsl.sh: llava:7b letöltés hozzáadva
                           fomenu.html: Rajz/Képelemző kártya

🟡  v1.1  (2026-06-12)  WSL2 core architektúra – install lánc kész:
                           _setup/CRT_install.ps1: teljes átírás, 0 szintaxis hiba
                                          helyigény felmérés · GPU detekció · admin hitelesítők
                                          WSL2 CRT disztribúció import · build_wsl.sh hívás
                                          start.bat generálás helyes WSL path-dal · v02–v08 migráció
                           _setup/build_wsl.sh: nem írja felül wsl_start.sh, csak chmod + dos2unix
                           _setup/create_admin.py: csendes mód (CRT_ADMIN_USER/PIN env-var, nincs TTY)
                           Még hátra: ext4.vhdx csomag · éles WSL2 teszt

✅  v1.0  (2026-06-10)  LoRA finomhangolás pipeline:
                           lora_train.py: golden_examples DB → Phi-3-mini/TinyLlama QLoRA tréning
                                          4-bit GPU / fp32 CPU mód · adapter mentés
                           lora_router.py: POST /lora/train · GET /lora/jobs · activate/deactivate
                           db_migrate_v08.py: lora_jobs tábla + system_config kulcsok
                           ai_motor.py: Claude → LoRA fine-tuned → Ollama fallback lánc
                                        modul-szintű pipeline cache (nem tölt újra minden kérésnél)
                           ui/lora.html: tréning indítás · live státusz · aktiválás · előzmények
                           fomenu.html: LoRA kártya (v1.0 badge)
                           build_wsl.sh: transformers/peft/trl/datasets/accelerate/bitsandbytes
                           main.py: v1.0 · lora_router bekötve

✅  v1.0+ (2026-06-10)  Linux platform támogatás + dokumentációs csomag:

         Platform detekció:
                           env_detect.py: detect_platform() → windows/wsl2/linux
                                          get_service_commands() → systemd/sysv
                                          ensure_runtime_dirs() · write_runtime_status() · write_pid()
                                          standalone futtatható: py env_detect.py (diagnosztika)
                           _setup/wsl_start.sh: univerzális Linux indítószkript
                                          PG → Nginx → ChromaDB → Ollama → FastAPI
                                          metrics/runtime.json · run/*.pid · logs/system/startup.log
                           build_wsl.sh: platform detekció az elején (wsl2 vs linux)
                                         ASCII log szimbólumok (✓→OK, ⚠→WARN encoding fix)
                           main.py: env_detect integráció · startup/shutdown events
                                    /health: platform mező hozzáadva

         Runtime könyvtárak (létrehozva, .gitkeep):
                           logs/backend/ · logs/nginx/ · logs/system/ · run/ · metrics/

         UI fejlesztés:
                           ui/beallitasok.html: hover tooltip rendszer [data-tip] CSS
                                          minden gombhoz multi-line leírás · .tip-left overflow védelem

         Teszt környezet:
                           C:\CRT\Segéd\ – Windows-natív tesztkörnyezet (IDEIGLENES)
                                          db_init.bat · db_start.bat · migrate.bat · start_backend.bat
                                          saját .env (crt_dev_secret / localhost / 8000)

         Dokumentáció:
                           CRT_Whitebook_v1.0.html: standalone HTML whitebook (dark CRT téma)
                           CRT_Security_Audit_v1.0.md: v1.0 biztonsági audit
                                          2 kritikus (K-1 DB jelszó, K-2 JWT secret)
                                          5 közepes · 4 alacsony · 16 rendben lévő pont
                           CRT_Kezikonyv_v1.0.md: 15 fejezetes kombinált admin+kezelő kézikönyv
                           CRT_Kezikonyv_v1.0.html: navigálható HTML kézikönyv (sticky nav, scroll-spy)
```

---

## TODO-LISTA (következő lépések)

### v0.6 – KÉSZ ✅
| # | Feladat | Státusz |
|---|---------|---------|
| 1 | `_setup/nginx/nginx.conf` standalone konfig | ✅ |
| 2 | `_setup/create_admin.py` admin init script | ✅ |
| 3 | Playwright scraper – `POST /scripts/{id}/run` | ✅ |
| 4 | Backend kód review (`main.py` verzió + backup path) | ✅ |

### v0.7–v0.9 – KÉSZ ✅
| # | Feladat | Státusz |
|---|---------|---------|
| 6 | Ollama fallback az AI azonosításhoz | ✅ ai_motor.py |
| 7 | ChromaDB vektoros keresés (DB1/DB2) | ✅ chroma_motor.py |
| 8 | Tanítóadat gyűjtő pipeline | ✅ golden_router.py |
| 9 | PDF export (ajánlat) | ✅ reportlab |
| 10 | OCR képes PDF-hez | ✅ pytesseract |
| 11 | Bootstrap ZIP csomagoló | ✅ build_package.ps1 |
| 12 | Rajz komparátor UI (LLaVA) | ✅ rajz_elemzo.html |
| 13 | Státusz widget | ✅ widget.html |

### v1.0 – LoRA pipeline KÉSZ ✅
| # | Feladat | Státusz |
|---|---------|---------|
| 14 | LoRA finomhangolás pipeline | ✅ lora_train.py + lora_router.py + ui/lora.html |

### v1.0 – dokumentáció és platform KÉSZ ✅
| # | Feladat | Státusz |
|---|---------|---------|
| 15 | env_detect.py – Linux platform detekció | ✅ |
| 16 | wsl_start.sh – univerzális Linux indítószkript | ✅ |
| 17 | beallitasok.html – hover tooltip rendszer | ✅ |
| 18 | CRT_Whitebook_v1.0.html | ✅ |
| 19 | CRT_Security_Audit_v1.0.md | ✅ |
| 20 | CRT_Kezikonyv_v1.0.md + .html | ✅ |

### v1.0 – még hátra van
| # | Feladat | Megjegyzés |
|---|---------|------------|
| 21 | C:\CRT\Segéd teszt | db_init.bat → migrate.bat → start_backend.bat → UI teszt |
| 22 | Éles tesztelés + bugfix kör | valós ajánlat-munkafolyamat |
| 23 | K-1 fix: DB URL → .env (CRT_DB_URL) | éles telepítés előtt kötelező |
| 24 | K-2 fix: JWT secret erős kulcs | éles telepítés előtt kötelező |

### v1.1 – WSL2 core architektúra (folyamatban 🟡)
**Döntés (2026-06-10): A CRT backend elsődleges futtatási környezete WSL2 Ubuntu 22.04.**
- Windows = host OS + böngésző, semmi más
- WSL2 = FastAPI, PostgreSQL, Ollama, ChromaDB, LoRA — mind Linux alatt
- `ext4.vhdx` = hordozható csomag (exportálható/importálható új gépre)

| # | Feladat | Státusz |
|---|---------|---------|
| 17 | `CRT_install.ps1` véglegesítése | ✅ újraírva (2026-06-12) — 0 szintaxis hiba, admin env-var mód, helyigény check, GPU detect |
| 18 | `build_wsl.sh` javítása | ✅ nem írja felül wsl_start.sh, dos2unix + chmod |
| 18b | `create_admin.py` csendes mód | ✅ CRT_ADMIN_USER / CRT_ADMIN_PIN env-var → nem kell TTY |
| 19 | `start.bat` WSL2 módra | ✅ CRT_install.ps1 generálja a helyes WSL path-dal |
| 19b | `wsl_stop.sh` tiszta leállítás | ✅ PID-alapú leállítás (FastAPI/ChromaDB/Ollama/Nginx/PG) |
| 19c | `wsl_export.ps1` export szkript | ✅ wsl --export CRT → wsl/crt_export_YYYYMMDD.tar |
| 19d | `stop.bat` WSL2 módra | ✅ wsl_stop.sh-t hív, pgsql16 + db\data natív fallback |
| 20 | `ext4.vhdx` csomag előállítása | ⬜ install.bat után: wsl_export.ps1 futtatása |
| 21 | Éles teszt WSL2 módban | ⬜ install.bat futtatás + teljes UI teszt |

---

## ÖSSZESÍTETT HALADÁS

| Réteg           | Kész | Részleges | Összes | % |
|-----------------|------|-----------|--------|---|
| Backend API     | 14   | 0         | 14     | 100% |
| Adatbázis       | 11   | 0         | 11     | 100% |
| Frontend        | 12   | 0         | 12     | 100% |
| AI / OCR        | 6    | 0         | 6      | 100% |
| Infrastruktúra  | 10   | 0         | 10     | 100% |
| **TOTAL**       | **53** | **0**  | **53** | **~100%** |

---

## FEJLESZTÉSI KÖRNYEZET

```
Elsődleges hely:   H:\Saját meghajtó\CRT\   (Google Drive – szinkronizált)
GitHub:            https://github.com/pusztaizsolt-lab/CRT
Drive szinkron:    IGEN – kód, UI, schema, setup fájlok
KIVÉTEL:           db_data\     ← SOHA ne szinkronizálni!  (PostgreSQL binárisok)
                   .env         ← titkos kulcsok
                   models\      ← ~10GB LLM modellek (felesleges)
                   wsl\         ← ~1.2GB ext4.vhdx (felesleges)

DB kapcsolat:      postgresql://crt_user:crt2026@localhost:5432/crt

Migráció sorrend (kötelező, friss gépen):
  python db_migrate_v02.py
  python db_migrate_v04.py
  python db_migrate_v05.py
  python db_migrate_v06.py

Másik gépen:
  git clone https://github.com/pusztaizsolt-lab/CRT.git "H:\Saját meghajtó\CRT"
  → _setup\setup_new_machine.ps1
  → _setup\setup_vscode.ps1
  → install.bat   (WSL2 + teljes stack)
```

---

## BIZTONSÁGI MEGJEGYZÉSEK

```
JWT:        HS256 · 8h TTL · CRT_JWT_SECRET env változó (megváltoztatandó!)
PIN:        6 jegy · bcrypt hash · 4 kísérlet → 30 perc zárolás
2FA:        email OTP · 10 perc érvényesség
CORS:       csak localhost (élesben szerver IP-re szűkítendő)
Sanitize:   SanitizeMiddleware → SQL inj · XSS · path traversal · 512KB limit
Middleware: CORSMiddleware → SanitizeMiddleware (fordított exec sorrend!)
Config:     _CONFIG_ALLOWED set – csak engedélyezett kulcsok módosíthatók
Backup:     POST /admin/backup → db_data/backups/backup_YYYYMMDD_HHMMSS.json
```

---

*Civil Rendszertechnika Kft. · Fejlesztő: Zsolt · Asszisztens: Claude (claude-sonnet-4-6)*
*Következő session: v1.0 teszt (C:\CRT\Segéd) + K-1/K-2 security fix + v1.1 WSL2 core*
