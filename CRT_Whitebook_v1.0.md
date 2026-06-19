# CRT Ajánlatsegéd – Whitebook v1.0
> Civil Rendszertechnika Kft. · Helyi AI alapú ajánlatkezelő rendszer
> Utolsó frissítés: 2026-06-10 · Verzió: 1.0 (teljes)

---

## 1. RENDSZER ÁTTEKINTÉS

### Mi ez?
A CRT Ajánlatsegéd egy **helyi, offline-képes** AI alapú ajánlatkészítő szoftver,
amelyet a Civil Rendszertechnika Kft. villamossági és épületautomatizálási
ajánlatkészítési folyamatának automatizálására fejlesztettünk.

### Fő értékek
| Funkció | Leírás |
|---------|--------|
| **AI azonosítás** | Ajánlatkérő dokumentumból automatikusan azonosítja a tételeket |
| **Árfigyelés** | Webes scraping + kézi ár bevitel, forrás tracking |
| **Ajánlatkészítés** | 3 indítási mód, cell-szintű státuszkövetés, xlsx/docx/PDF export |
| **Helyi LLM** | Ollama (llama3:8b / mistral:7b) – internet nélkül is működik |
| **LoRA finomhangolás** | Saját jóváhagyott példákból fine-tuned AI modell |
| **Rajz elemzés** | LLaVA Vision alapú tervrajz/kép elemzés |
| **Adatbiztonság** | Minden adat helyi gépen, titkosított auth, audit log |

---

## 2. ARCHITEKTÚRA

### Telepítési modell (ajánlott: WSL2)

```
Windows szerver (Win10/11, x64, 250GB SSD)
│
├─ start.bat ──→ wsl -d CRT ──→ wsl_start.sh
│
└─── WSL2 Ubuntu 22.04 "CRT" disztribúció ──────────────────────┐
     │                                                            │
     │  PostgreSQL 16      localhost:5432                        │
     │  FastAPI/uvicorn    localhost:8000  (2 worker)            │
     │  ChromaDB           localhost:8001  (vektoros DB)         │
     │  Ollama LLM         localhost:11434 (helyi LLM)           │
     │  Nginx              localhost:80    (UI kiszolgáló)        │
     │                                                            │
     └────────────────────────────────────────────────────────────┘
          ↑ böngésző: http://localhost
```

### Fallback mód (WSL2 nélkül)
```
PostgreSQL portable (db\pgsql\) + Python 3.11 + ui/login.html böngészőből
```

### Helyigény (250GB SSD-re tervezett)
```
WSL2 Ubuntu base:         ~1.2 GB
Python + csomagok:        ~1.2 GB  (LoRA csomagokkal együtt)
Playwright Chromium:      ~350 MB
llama3:8b + mistral:7b:   ~9.5 GB
llava:7b (Vision):        ~4.1 GB
ChromaDB + vektorok:      ~500 MB
LoRA adapter (tréning):   ~500 MB  (GPU) / ~3 GB (merged)
CRT kód + UI:              ~50 MB
PostgreSQL adatok:        ~100 MB
──────────────────────────────────
ÖSSZESEN:                ~17.5 GB  (szabad: ~232 GB)
```

---

## 3. TECHNOLÓGIAI STACK

| Réteg | Technológia |
|-------|-------------|
| Backend | Python 3.11 · FastAPI 0.115 · SQLAlchemy 2.0 |
| Adatbázis | PostgreSQL 16 |
| Auth | bcrypt PIN + email OTP + JWT HS256 (8h) |
| Biztonság | SanitizeMiddleware (SQL inj / XSS / path traversal) |
| AI – fő | Claude API (`claude-sonnet-4-6`) |
| AI – LoRA | HuggingFace transformers + PEFT + TRL (Phi-3-mini / TinyLlama) |
| AI – helyi | Ollama (llama3:8b, mistral:7b, llava:7b) |
| Vektoros keresés | ChromaDB + sentence-transformers |
| Web scraping | Playwright (Chromium) |
| Frontend | Vanilla HTML/CSS/JS (nincs Node/npm, 4 CSS téma) |
| Export | openpyxl (xlsx) · python-docx (docx) · reportlab (PDF) |
| OCR | pdfplumber → pytesseract + Pillow (fallback) |
| Kiszolgáló | Nginx (WSL2) / direkt fájl (fallback) |

---

## 4. ADATBÁZIS SÉMA

### Táblák (15 db)
```
CIKKTÖRZS
  products       – Termékek (item_id UUID, crt_code, manufacturer, unit, status)
  activities     – Tevékenységek (activity_id UUID, unit_type)
  categories     – Kategória fa (parent_id, item_class, sort_order)

ÁRAK
  prices         – Ármozgások (price_type: lista/kisker/nagyker/egyedi,
                               source_id, supplier_code, currency)

AJÁNLATOK
  quotes         – Ajánlat fejlécek (quote_number: CRT-YYYY-NNNN,
                                     source_mode, client_ref, base_quote_id)
  quote_lines    – Tételsorok (line_no, raw_name, cell_status,
                               confidence, price_source, item_id)

WEB SCRAPING
  web_sources    – Forrás URL-ek (base_url, source_type, status)
  web_scripts    – Playwright scriptek (steps JSONB, version, active)
  web_prices     – Scrapelt árak (source_id, item_id, price, currency)

AI / VEKTOROS
  golden_examples – Jóváhagyott azonosítások (raw_text, clean_name, source)
  chroma_index    – ChromaDB vektor indexek (collection, vector_id)
  lora_jobs       – LoRA tréning futtatások (status, train_loss, adapter_path)

RENDSZER
  users           – Felhasználók (pin_hash, email, role, locked_until)
  auth_tokens     – JWT refresh tokenek
  system_config   – Kulcs-érték konfiguráció
  audit_log       – Minden esemény naplója (action, entity_type, ip_address)
```

### Migrációs sorrend (kötelező, friss gépen)
```bash
py -3.11 db_migrate_v02.py   # cikktörzs + árak + audit + config táblák
py -3.11 db_migrate_v04.py   # auth: users bővítés + auth_tokens
py -3.11 db_migrate_v05.py   # web_sources, web_scripts, web_prices, quotes bővítés
py -3.11 db_migrate_v06.py   # IF NOT EXISTS bővítések + indexek
py -3.11 db_migrate_v07.py   # golden_examples + chroma_index + Ollama config
py -3.11 db_migrate_v08.py   # lora_jobs + LoRA system_config kulcsok
```

---

## 5. AI PIPELINE

### Azonosítási prioritási lánc
```
POST /cikktorzs/identify
        │
        ▼
   1. Claude API ────────── ha claude_api_key van a system_config-ban
        │ hiba / nincs kulcs
        ▼
   2. LoRA fine-tuned ───── ha lora_active_job_id + lora_adapter_path be van állítva
        │ hiba / nincs aktiválva
        ▼
   3. Ollama helyi LLM ──── http://localhost:11434 (llama3:8b alapértelmezett)
        │ hiba
        ▼
   RuntimeError → 503 válasz
```

### Visszaadott formátum (mindhárom forrástól azonos)
```json
{
  "results": [
    {
      "index": 1,
      "name": "Kábelcsatorna 60×40mm",
      "manufacturer": "OBO Bettermann",
      "unit": "m",
      "category": "Kábelcsatornák",
      "confidence": 0.95
    }
  ],
  "tokens_used": 312,
  "source": "claude"   // vagy "lora" / "ollama"
}
```

### LoRA finomhangolás folyamata
```
1. Jóváhagyás az ajánlatkészítőben (acceptAll) → golden_examples tábla
2. ui/lora.html → Tréning indítása (min. 10 példa)
3. lora_train.py háttérben fut (WSL2):
   - GPU: Phi-3-mini-4k-instruct + 4-bit QLoRA (~30 perc)
   - CPU: TinyLlama-1.1B + fp32 (~2-4 óra)
4. Adapter mentve: models/lora/{job_id}/adapter/
5. Aktiválás a UI-ból → ai_motor.py ezt tölti be (cachelve)
```

### Embedding / vektoros keresés (ChromaDB)
```
crt_raw  (DB1) – Feltöltött nyers sorok, azonosítás előtt indexelve
crt_clean (DB2) – Jóváhagyott, mentett cikktörzs tételek

GET /chroma/search?q=kábelcsatorna&collection=crt_clean&n=5
```

---

## 6. API VÉGPONTOK

### Rendszer
| Endpoint | Leírás |
|----------|--------|
| `GET /` | Ping – verzió, NTP idő, DB státusz |
| `GET /health` | Gyors health check |
| `GET /status/widget` | Zöld/piros – widgethez |
| `GET /db/test` | PostgreSQL kapcsolat teszt |
| `GET /ollama/status` | Ollama + elérhető modellek |
| `GET /vision/status` | LLaVA elérhetőség |

### Auth (`/auth/`)
| Endpoint | Leírás |
|----------|--------|
| `POST /auth/login/pin` | PIN beküldés → OTP trigger |
| `POST /auth/login/otp` | OTP ellenőrzés → JWT token |
| `POST /auth/logout` | Token érvénytelenítés |
| `GET /auth/me` | Saját profil |
| `GET /auth/admin/users` | Felhasználók listája (admin) |
| `POST /auth/admin/users` | Új felhasználó (admin) |
| `POST /auth/admin/users/{id}/unlock` | Zárolás feloldása (admin) |
| `GET /auth/admin/config` | System config lekérdezés |
| `PATCH /auth/admin/config` | System config módosítás |
| `POST /auth/admin/config/test-smtp` | SMTP teszt |
| `POST /auth/change-pin` | PIN csere |

### Cikktörzs
| Endpoint | Leírás |
|----------|--------|
| `GET /cikktorzs/tree` | Kategória fa + termékek + tevékenységek |
| `GET /cikktorzs/search` | Szöveges keresés |
| `POST /cikktorzs/upload` | Fájl feltöltés és sorok kiolvasása |
| `POST /cikktorzs/identify` | AI azonosítás (Claude→LoRA→Ollama) |
| `POST /cikktorzs/save` | Jóváhagyott tételek mentése |

### Ajánlatok (`/quotes/`)
| Endpoint | Leírás |
|----------|--------|
| `GET /quotes/` | Lista (szűrők: status, client, dátum) |
| `POST /quotes/` | Új ajánlat |
| `GET /quotes/{id}` | Ajánlat fejléc |
| `PATCH /quotes/{id}` | Módosítás |
| `DELETE /quotes/{id}` | Törlés (recycle bin) |
| `GET /quotes/{id}/lines` | Tételsorok |
| `POST /quotes/{id}/lines/bulk` | Tömeges sor feltöltés |
| `GET /quotes/{id}/summary` | Összesítő (összeg, státusz stat) |

### Export (`/export/`)
| Endpoint | Leírás |
|----------|--------|
| `GET /export/{quote_id}/xlsx` | Excel export |
| `GET /export/{quote_id}/docx` | Word export |
| `GET /export/{quote_id}/pdf` | PDF export (A4, dark theme) |

### Árak (`/prices/`)
| Endpoint | Leírás |
|----------|--------|
| `GET /prices/` | Ár lista (szűrők) |
| `POST /prices/` | Kézi ár bevitel |
| `GET /prices/best/{item_id}` | Legjobb ár lekérdezés |
| `GET /prices/stats` | Statisztika (total/egyedi/forrás) |

### Webes árak (`/web/`)
| Endpoint | Leírás |
|----------|--------|
| `GET /web/sources` | Forrás lista |
| `POST /web/sources` | Új forrás |
| `POST /web/sources/{id}/ping` | Elérhetőség teszt |
| `GET /web/scripts` | Script lista |
| `POST /web/scripts` | Új script |
| `POST /scripts/{id}/run` | Playwright futtatás → web_prices mentés |

### Golden / Tanítóadat (`/golden/`)
| Endpoint | Leírás |
|----------|--------|
| `GET /golden/` | Lista (szűrők: q, source) |
| `POST /golden/` | Egy példa mentése |
| `POST /golden/batch` | Batch mentés (acceptAll-ból) |
| `GET /golden/stats` | Statisztika |
| `GET /golden/export?format=jsonl` | JSONL/JSON/CSV export |
| `DELETE /golden/{id}` | Törlés |

### LoRA (`/lora/`)
| Endpoint | Leírás |
|----------|--------|
| `GET /lora/stats` | Golden count + aktív job info |
| `POST /lora/train` | Tréning indítása (háttér subprocess) |
| `GET /lora/jobs` | Job előzmények |
| `GET /lora/jobs/{job_id}` | Job részlet + live status.json |
| `POST /lora/jobs/{job_id}/activate` | Modell aktiválása az AI pipeline-ban |
| `POST /lora/deactivate` | LoRA kikapcsolása |
| `DELETE /lora/jobs/{job_id}` | Job + adapter fájlok törlése |

### ChromaDB / Audit
| Endpoint | Leírás |
|----------|--------|
| `GET /chroma/stats` | Gyűjtemény statisztika |
| `GET /chroma/search` | Vektoros keresés |
| `GET /audit/logs` | Audit napló (szűrők) |
| `POST /admin/backup` | DB JSON snapshot |
| `POST /vision/analyze` | Kép/PDF elemzés LLaVA-val |

---

## 7. FRONTEND OLDALAK

| Oldal | URL | Leírás |
|-------|-----|--------|
| Bejelentkezés | `ui/login.html` | PIN → OTP 2 lépés, 4 téma, brute force visszaszámláló |
| Főmenü | `ui/fomenu.html` | 10 funkciókártya, státusz chip-ek |
| Admin konzol | `ui/admin.html` | Felhasználókezelés, lock/unlock, PIN reset, konfig |
| Cikktörzs | `ui/cikktorzs.html` | Fa struktúra, keresés, fájl feltöltés, AI azonosítás |
| Ajánlatkészítő | `ui/ajanlatkezelo.html` | 3 indítási mód, cell-státusz jelzők, AI, xlsx/docx/PDF |
| Webes árak | `ui/webes_arak.html` | Árforrások, script rögzítés, Tanít gomb |
| Beállítások | `ui/beallitasok.html` | SMTP, Claude/Ollama kulcsok, PIN csere, backup |
| Naplók | `ui/naplok.html` | Audit log, szűrők, CSV export |
| Árak | `ui/arak.html` | Ár lista, kézi bevitel, stat sáv |
| Widget | `ui/widget.html` | Élő rendszerállapot (API/DB/Ollama/ChromaDB) |
| Rajzelemző | `ui/rajz_elemzo.html` | LLaVA Vision, drag&drop kép/PDF, eredmény kártyák |
| LoRA | `ui/lora.html` | Tréning indítás, live progress, job lista, aktiválás |
| Diagnosztika | `ui/kezelőpult_v2.html` | Rendszer diagnosztika, 4 téma palettaszerkesztő |

### CSS témák (mind a 13 oldalon egységes)
```
ejszaka  – sötét, fekete-szürke (alapértelmezett)
ocean    – kék-cián
forest   – zöld, meleg tónusok
steel    – acélszürke, ipari
```
localStorage kulcs: `crt-theme` · JWT: `crt-token` · Felhasználó: `crt-user`

---

## 8. BIZTONSÁG

### Auth réteg
- **PIN**: bcrypt, 6 számjegy
- **2FA**: email OTP, 10 perc érvényes (ha smtp_host üres → OTP naplóba, dev mód)
- **JWT**: HS256, 8 óra, `CRT_JWT_SECRET` env var
- **Brute force**: 4 kísérlet → 30 perces zárolás (automatikus unlock)

### Input szanitizálás (SanitizeMiddleware – minden kérésre)
- SQL injection minták (UNION, DROP, SELECT * stb.)
- XSS vektoros (`<script>`, `javascript:`, event handlerek)
- Path traversal (`../`, `..\\`)
- Kérés méret limit: 512 KB

### Audit log
Minden bejelentkezés, módosítás, törlés, backup rögzítve az `audit_log` táblában
IP cím, felhasználó, entitás típus és ID, leírás.

---

## 9. TELEPÍTÉSI ÚTMUTATÓ

### Gyors indítás (fejlesztési mód, Windows natív)
```powershell
# 1. Csomagok telepítése
py -3.11 -m pip install -r requirements.txt

# 2. DB inicializálás (sorban!)
py -3.11 db_migrate_v02.py
py -3.11 db_migrate_v04.py
py -3.11 db_migrate_v05.py
py -3.11 db_migrate_v06.py
py -3.11 db_migrate_v07.py
py -3.11 db_migrate_v08.py

# 3. Admin felhasználó létrehozása
py -3.11 _setup/create_admin.py

# 4. Backend indítása
py -3.11 -m uvicorn main:app --reload

# 5. Böngészőben: ui/login.html
```

### Éles telepítés (WSL2, intelligens telepítő)
```powershell
# Adminként futtatva:
.\install.bat
# Vagy:
powershell -ExecutionPolicy Bypass -File "_setup\CRT_install.ps1"
```

A telepítő automatikusan:
1. WSL2 + Ubuntu 22.04 "CRT" disztribúció létrehozása
2. PostgreSQL 16 + Python 3.11 + Nginx telepítése
3. LLM modellek letöltése (llama3:8b, mistral:7b, llava:7b)
4. ChromaDB, Playwright, LoRA csomagok telepítése
5. Systemd service-ek regisztrálása
6. Admin felhasználó konfigurálása

### Napi indítás / leállítás
```
start.bat   – WSL2 CRT + összes szolgáltatás
stop.bat    – graceful shutdown
status.bat  – futó szolgáltatások listája
```

---

## 10. KONFIGURÁCIÓ (system_config kulcsok)

| Kulcs | Leírás | Hol állítható |
|-------|--------|--------------|
| `claude_api_key` | Anthropic API kulcs | beallitasok.html / .env |
| `claude_model` | Alapértelmezett Claude modell | beallitasok.html |
| `smtp_host/port/user/pass` | Email SMTP (OTP küldéshez) | beallitasok.html |
| `company_name` | Cég neve (dokumentumokba) | beallitasok.html |
| `ollama_url` | Ollama szerver URL | beallitasok.html |
| `ollama_model` | Alapértelmezett Ollama modell | beallitasok.html |
| `lora_active_job_id` | Aktív LoRA job azonosítója | lora.html |
| `lora_adapter_path` | LoRA adapter könyvtár elérési útja | lora.html |
| `ai_conf_high` | AI azonosítás magas bizonyossági küszöb | beallitasok.html |
| `ai_conf_low` | AI azonosítás alacsony bizonyossági küszöb | beallitasok.html |

### .env fájl (titkos értékek, NEM szinkronizálni!)
```env
CRT_DB_URL=postgresql://crt_user:crt2026@localhost:5432/crt
CRT_JWT_SECRET=valtoztasd-meg-eles-rendszeren
ANTHROPIC_API_KEY=sk-ant-...
CRT_OLLAMA_URL=http://localhost:11434
CRT_LORA_DIR=models/lora
```

---

## 11. MAPPA STRUKTÚRA

```
H:\Saját meghajtó\CRT\  (Google Drive szinkronizált)
│
├── ui\                    HTML felületek (13 oldal)
├── _setup\
│   ├── CRT_install.ps1    Intelligens Windows telepítő
│   ├── build_wsl.sh       Ubuntu belső telepítő
│   ├── wsl_start.sh       WSL2 runtime indító
│   ├── create_admin.py    Admin felhasználó init
│   ├── build_package.ps1  Bootstrap ZIP csomagoló
│   └── nginx\nginx.conf   Nginx sablon konfig
├── models\
│   ├── ollama\            LLM modellek (~10 GB, NEM szinkronizálni)
│   └── lora\              LoRA adapterek ({job_id}/adapter/)
├── vectors\chroma\        ChromaDB adatok
├── uploads\               Feltöltött fájlok
├── exports\               Generált dokumentumok
├── logs\                  Backend + Nginx naplók
├── db_data\               PostgreSQL adatkönyvtár (NEM szinkronizálni!)
│   └── backups\           JSON backup snapshot-ok
│
├── main.py                FastAPI belépőpont v1.0
├── auth.py                Auth + Config router
├── sanitize.py            Biztonsági middleware
├── ai_motor.py            AI pipeline (Claude→LoRA→Ollama)
├── lora_router.py         LoRA kezelő API
├── lora_train.py          LoRA tréning szkript
├── chroma_motor.py        ChromaDB motor
├── vision_motor.py        LLaVA Vision motor
├── golden_router.py       Tanítóadat router
├── quotes_router.py       Ajánlat router
├── export_router.py       Export router
├── prices_router.py       Ár router
├── web_sources.py         Web scraper router
├── cikktorzs_parse.py     Fájl parser + OCR
├── db_migrate_v02..v08.py Migrációk
├── requirements.txt       Python függőségek
├── docker-compose.yml     Docker alternatíva
├── start.bat / stop.bat / status.bat / install.bat
├── .env.example           Env változók sablon
├── CLAUDE.md              Claude kontextus (új gépre)
├── CRT_Status.md          Formális státusz dokumentum
└── CRT_Whitebook_v1.0.md  ← EZT OLVASOD
```

---

## 12. FEJLESZTÉSI HISTÓRIA

| Verzió | Dátum | Tartalom |
|--------|-------|---------|
| v0.1 | 2026-05-18 | DB séma – 14 tábla alap |
| v0.2 | 2026-05-18 | FastAPI gerinc + állapotjelző |
| v0.3 | 2026-05-28 | Cikktörzs API + UI + fájl parser + AI azonosítás + GitHub |
| v0.4 | 2026-06-08 | Auth teljes: PIN + OTP + JWT + brute force + sanitize |
| v0.5 | 2026-06-08 | Ajánlatkészítés + export + árak + naplók + beállítások |
| v0.6 | 2026-06-09 | Playwright scraper + Nginx + admin init |
| v0.7 | 2026-06-10 | Ollama fallback + ChromaDB embedding |
| v0.8 | 2026-06-10 | OCR + PDF export + Golden examples + widget + Bootstrap ZIP |
| v0.9 | 2026-06-10 | LLaVA Vision rajzelemző UI |
| **v1.0** | **2026-06-10** | **LoRA finomhangolás pipeline – teljes AI lánc** |

---

## 13. ISMERT KORLÁTOK ÉS TERVEZETT FEJLESZTÉSEK

### Ismert korlátok
- LoRA tréning CPU-n lassú (TinyLlama: ~2–4 óra 50 példán)
- LLaVA Vision csak Ollama-n keresztül elérhető (llava:7b letöltve kell)
- Ha a szerver tréning közben újraindul, a job DB-ben pending marad – törlés UI-ból lehetséges
- SMTP hiányában az OTP csak a naplóba kerül (dev mód – éles rendszeren kötelező beállítani)

### Tervezett (v1.1+)
- Telepítő (`CRT_install.ps1`) éles tesztelése és véglegesítése
- Éles tesztelés: valós ajánlat munkafolyamat + bugfix kör
- Több felhasználós szerepkör (pl. árajánlat-jóváhagyó szerepkör)
- Mobilbarát UI (responsive layout)

---

## 14. ADATBÁZIS KAPCSOLAT

```
Host:     localhost:5432
DB:       crt
User:     crt_user
Password: crt2026
URL:      postgresql://crt_user:crt2026@localhost:5432/crt
```

> **Éles rendszeren a jelszót meg kell változtatni a `.env` fájlban!**

---

*CRT Ajánlatsegéd Whitebook v1.0 – Civil Rendszertechnika Kft. – 2026-06-10*
