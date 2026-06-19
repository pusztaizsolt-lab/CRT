# CRT Ajánlatsegéd – Kezelői Kézikönyv v1.0
> Civil Rendszertechnika Kft. · Admin és Kezelői útmutató
> Rendszer verzió: v1.0 · Utolsó frissítés: 2026-06-10

---

## TARTALOM

1. [Rendszer áttekintés](#1-rendszer-áttekintés)
2. [Indítás és leállítás](#2-indítás-és-leállítás)
3. [Belépés (PIN + 2FA)](#3-belépés-pin--2fa)
4. [Főmenü](#4-főmenü)
5. [Cikktörzs kezelés](#5-cikktörzs-kezelés)
6. [Ajánlatkészítés](#6-ajánlatkészítés)
7. [Árkezelés](#7-árkezelés)
8. [Webes árfigyelés](#8-webes-árfigyelés)
9. [AI funkciók](#9-ai-funkciók)
10. [LoRA finomhangolás](#10-lora-finomhangolás)
11. [Beállítások](#11-beállítások)
12. [Admin konzol](#12-admin-konzol)
13. [Naplók és audit](#13-naplók-és-audit)
14. [Backup és visszaállítás](#14-backup-és-visszaállítás)
15. [Hibaelhárítás](#15-hibaelhárítás)

---

## 1. RENDSZER ÁTTEKINTÉS

A **CRT Ajánlatsegéd** a Civil Rendszertechnika Kft. belső, helyi AI alapú ajánlatkészítő rendszere. Az összes adat a céges gépen marad — nem kerül felhőbe.

### Mit tud a rendszer?

| Funkció | Leírás |
|---------|--------|
| **AI azonosítás** | Ajánlatkérő dokumentumból automatikusan azonosítja a tételeket (kábelcsatorna, szerelvény, stb.) |
| **Árfigyelés** | Szállítói weboldalak automatikus figyelése, kézi ár bevitel |
| **Ajánlatkészítés** | Ajánlat generálás 3 módban, xlsx/docx/PDF export |
| **Helyi LLM** | Internet nélkül is működik – Ollama (llama3:8b) |
| **LoRA finomhangolás** | Saját példákból betanított, CRT-specifikus AI modell |
| **Rajzelemzés** | Tervrajzok, fotók elemzése – termékek automatikus felismerése |

### Szerepkörök

| Szerepkör | Jogosultságok |
|-----------|---------------|
| **admin** | Minden funkció + felhasználókezelés + rendszer konfig + backup |
| **user** | Cikktörzs, ajánlatkészítés, árkezelés, AI, LoRA |

---

## 2. INDÍTÁS ÉS LEÁLLÍTÁS

### Napi indítás
```
start.bat    (dupla kattintás a CRT mappából)
```
A rendszer automatikusan elindítja:
- PostgreSQL adatbázist
- FastAPI backend szervert (`:8000`)
- ChromaDB vektoros keresőt (`:8001`)
- Ollama helyi LLM-et (`:11434`)

Ezután megnyílik a böngészőben: `http://localhost` (Nginx) vagy `ui/login.html`

### Leállítás
```
stop.bat
```

### Állapot ellenőrzés
```
status.bat
```
Látható: futó szolgáltatások, port-ok, verzió.

### Widget
Az élő rendszerállapot elérhető: `ui/widget.html` — ez beágyazható képernyővédőbe vagy második monitorra.

---

## 3. BELÉPÉS (PIN + 2FA)

A CRT kétlépéses belépést alkalmaz minden felhasználónak.

### 1. lépés – PIN
1. Nyisd meg: `ui/login.html` (vagy `http://localhost/login.html`)
2. Add meg a **felhasználónevedet**
3. Add meg a **6 jegyű numerikus PIN**-t a cellákba (kattintás vagy Tab-bal mozogj)
4. Kattints: **Belépés**

### 2. lépés – OTP kód
1. A rendszer elküld egy egyszeri belépési kódot az email-edre (10 perc érvényes)
2. Add meg a 6 jegyű kódot
3. Kattints: **Ellenőrzés**

> **Megjegyzés:** Ha nincs SMTP beállítva (fejlesztési mód), az OTP kód a szerver logban jelenik meg — ez éles rendszeren nem elfogadható, be kell állítani az SMTP-t.

### Téma választás
A belépési oldalon 4 szín téma érhető el: Éjszaka (alapértelmezett), Óceán, Erdő, Acél. A választás az összes oldalon érvényes és localStorage-ban tárolódik.

### Brute force védelem
- 4 hibás PIN-kísérlet → **30 perces automatikus zárolás**
- A zárolás feloldható az Admin konzolból
- Zárolás ideje visszaszámlálóként jelenik meg

---

## 4. FŐMENÜ

Belépés után a főmenü jelenik meg (`ui/fomenu.html`) — 10 funkciókártyával.

| Kártya | Oldal | Funkció |
|--------|-------|---------|
| 📦 Cikktörzs | `cikktorzs.html` | Termékek és tevékenységek kezelése |
| 📋 Ajánlatkészítő | `ajanlatkezelo.html` | Ajánlatok létrehozása, exportálása |
| 💰 Árak | `arak.html` | Árlisták, kézi ár bevitel |
| 🌐 Webes árak | `webes_arak.html` | Automatikus árfigyelés |
| ⚙️ Beállítások | `beallitasok.html` | Rendszer konfiguráció |
| 👤 Admin | `admin.html` | Felhasználókezelés (admin) |
| 📋 Naplók | `naplok.html` | Audit napló |
| 🖼 Rajzelemző | `rajz_elemzo.html` | Tervrajz/fotó AI elemzés |
| 🧠 LoRA | `lora.html` | AI finomhangolás |
| 📊 Diagnosztika | `kezelőpult_v2.html` | Rendszerállapot |

A státusz chipek mutatják: API / DB / Ollama / ChromaDB él-e.

---

## 5. CIKKTÖRZS KEZELÉS

### Mi a cikktörzs?
A CRT összes ismert terméke és tevékenysége — egy belső adatbázis, amiből az AI ajánlat tételeket azonosít.

### Fájl feltöltés és AI azonosítás

1. Nyisd meg: **Cikktörzs** (`ui/cikktorzs.html`)
2. Kattints: **Fájl feltöltés**
3. Válaszd ki az ajánlatkérő dokumentumot (xlsx, csv, pdf, docx, html, md)
4. A rendszer kinyeri a sorokat (OCR-rel is, ha szükséges)
5. Kattints: **AI azonosítás**

Az AI minden sort azonosítani próbál:
- 🟢 **Zöld** (>70% bizonyosság): azonosítva, termék megvan a cikktörzsben
- 🟡 **Sárga** (50-70%): bizonytalan — ellenőrizd manuálisan
- 🔴 **Piros** (<50%): nem azonosítva — kézi kezelés szükséges

### Eredmény jóváhagyása és mentése
- Egyenként: kattints a tételre → módosítás → **Jóváhagy**
- Egyszerre: **Mindent elfogad** → az összes zöld tétel mentésre kerül
- Mentés után a tételek bekerülnek a cikktörzsbe és tanítóadat-adatbázisba

### Fa struktúra
A termékek kategória fában vannak szervezve (bal panel). Kattintással szűrhető a lista.

### Keresés
A keresőmezőben: terméknév, gyártó, CRT-kód — azonnali szűrés.

---

## 6. AJÁNLATKÉSZÍTÉS

### Három indítási mód

| Mód | Leírás | Mikor |
|-----|--------|-------|
| **Üres ajánlat** | Új, üres ajánlat | Kézzel viszed fel a tételeket |
| **Fájlból** | Feltölt + AI azonosít | Megkaptad az ajánlatkérőt fájlban |
| **Korábbi alapján** | Meglévő ajánlatból másolás | Visszatérő projekt, hasonló igény |

### Ajánlat munkafolyamat

1. Nyisd meg: **Ajánlatkészítő** (`ui/ajanlatkezelo.html`)
2. Kattints: **Új ajánlat** → válaszd a módot
3. Töltsd fel a fájlt (ha fájl módban)
4. AI azonosítás után ellenőrizd a tételeket
5. Minden sorhoz: mennyiség, egységár (automatikusan töltődik ha van ár a rendszerben)
6. Kattints: **Összesítő** → látod a végösszeget
7. Export: **xlsx** / **docx** / **PDF**

### Cellaállapot jelzők

| Jelző | Jelentés |
|-------|----------|
| 🟢 Zöld | AI bizonyosan azonosított |
| 🟡 Sárga | Bizonytalan — ellenőrizd |
| 🔴 Piros | Nem azonosított — kézi kitöltés |
| ⚪ Szürke | Nincs ár az adatbázisban |

### Export formátumok
- **xlsx** — Excel, szerkeszthető, CRT fejléc
- **docx** — Word, szerkeszthető, céglogóval, aláírás sorral
- **PDF** — végleges, A4, sötét témával, összesítő sorral

### Mentett ajánlatok
Az ajánlatok listája az oldal tetején. Kattintással megnyitható, módosítható.

> **Figyelem:** A Törlés gomb visszafordíthatatlan (v1.0-ban nincs kukó funkció).

---

## 7. ÁRKEZELÉS

### Árak oldal (`ui/arak.html`)

Megjeleníti az összes ismert árat, forrással és időbélyeggel.

**Szűrők:**
- Terméknév keresés
- Ártípus: lista / kisker / nagyker / egyedi
- Forrás: kézi / web forrás neve

**Kézi ár bevitel:**
1. Kattints: **+ Új ár**
2. Add meg: termék (keresőből), ár, típus, forrás neve, érvényesség
3. Mentés → azonnal elérhető az ajánlatkészítőben

**Kor jelzők:**
- 🟢 Friss (30 napnál fiatalabb)
- 🟡 Régi (30-90 nap)
- 🔴 Elavult (90 nap+)

Az elavultság küszöb a Beállítások → Webes árak → Max. áradat kora paraméterrel állítható.

---

## 8. WEBES ÁRFIGYELÉS

### Árforrások kezelése (`ui/webes_arak.html`)

A rendszer automatikusan figyeli a megadott szállítói weboldalakat (Playwright alapú web scraper).

### Forrás hozzáadása
1. Kattints: **+ Új forrás**
2. Add meg: forrás neve, alap URL, forrástípus (webshop/Excel/API)
3. **Ping teszt** → ellenőrzi az elérhetőséget
4. Mentés

### Script rögzítés (lépéssor)
1. Válaszd ki a forrást → **Script szerkesztés**
2. Add meg a lépéseket JSONB formátumban:
   - `navigate` → URL megnyitás
   - `find` → keresőmező selector
   - `type` → szöveg begépelés
   - `click` → gomb kattintás
   - `extract` → ár kinyerés (CSS selector + regex)
3. **Teszt futtatás** → egy termékre kipróbálja
4. Ha OK → **Aktiválás**

### Automatikus futtatás
- Beállítások → Webes árak → Scrape intervallum (alapért. 24 óra)
- Manuálisan: **▶ Azonnali futtatás** gomb a Beállítások oldalon

### Tanít gomb
Ha a scraper talált árat egy termékhez → **Tanít** → a talált ár bekerül a golden_examples adatbázisba (LoRA tanítóadat).

---

## 9. AI FUNKCIÓK

### AI prioritási lánc

A rendszer három AI motort használ, prioritás sorrendben:

```
1. Claude API (cloud) ── ha API kulcs be van állítva
       ↓ ha nincs / hibás
2. LoRA fine-tuned   ── ha aktiválva van egy tréning
       ↓ ha nincs aktiválva
3. Ollama helyi LLM  ── mindig elérhető (internet nélkül)
```

### Claude API beállítása
1. Beállítások → AI → Claude API
2. API kulcs: `sk-ant-...` (Anthropic Console)
3. Modell: `claude-sonnet-4-6` (alapértelmezett, ajánlott)
4. **Kapcsolat teszt** → zöld badge ha OK

### Ollama helyi LLM
Automatikusan elérhető ha a szerver fut (`http://localhost:11434`).
- Modell: `llama3:8b` (alapértelmezett) / `mistral:7b`
- Lassabb a Claude-nál, de offline is működik
- WSL2 módban automatikusan elindul a `start.bat`-tal

### AI azonosítás forrás jelzése
Az azonosítás eredményében mindig látható az AI forrás:
- `[Claude]` — felhős, legpontosabb
- `[LoRA]` — finomhangolt, CRT-specifikus
- `[Ollama]` — helyi, általános

### Rajzelemző (`ui/rajz_elemzo.html`)
1. Húzd be a tervrajzot vagy fotót (jpg, png, pdf)
2. Kattints: **Elemzés**
3. Az LLaVA Vision modell azonosítja a látható termékeket
4. Eredmény kártyák → kattintással bekerülhetnek az ajánlatba
5. CSV export az azonosított tételekről

---

## 10. LoRA FINOMHANGOLÁS

A LoRA (Low-Rank Adaptation) lehetővé teszi, hogy a rendszer saját jóváhagyott példáidból tanuljon — így az AI egyre jobban ismeri a CRT-specifikus termékneveket és jelölésrendszert.

### Mikor érdemes tréninget indítani?
- Legalább **10 jóváhagyott azonosítás** szükséges (ajánlatkészítőből „Mindent elfogad")
- Ajánlott: 50+ példa, rendszeresen ismételt tréning
- A tréning nem blokkolja a rendszer többi funkcióját

### Tréning indítása (`ui/lora.html`)

1. Nyisd meg: **LoRA** a főmenüből
2. Ellenőrizd a stat boxokat: **Arany példák száma** (minimum 10 kell)
3. Beállítások (opcionális):
   - **HuggingFace modell**: `microsoft/Phi-3-mini-4k-instruct` (GPU) vagy `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (CPU)
   - **Epochok**: 3 (alapértelmezett, elegendő 50 példánál)
   - **LoRA rank**: 8 (alapértelmezett)
4. Kattints: **Tréning indítása**

### Tréning folyamata

| Fázis | Leírás | Időtartam |
|-------|--------|-----------|
| Init | Inicializálás | néhány mp |
| Modell betöltés | Alapmodell letöltése/betöltése | 1-5 perc |
| Előkészítés | Adatok formázása | 1-2 perc |
| Tréning | Tényleges tanítás | GPU: ~30 perc / CPU: ~2-4 óra |
| Kész | Adapter mentve | — |

A progress bar és a live státusz élőben frissül (3 mp-enként).

### Aktiválás
1. Tréning befejezése után → **Aktiválás** gomb a job sorában
2. Az AI pipeline-ban a LoRA modell veszi át a 2. helyet (Claude után)
3. Az aktív modell az oldal tetején chipként jelenik meg

### Deaktiválás
- **Deaktiválás** gomb → visszaáll Ollama-ra (ha Claude nincs beállítva)

> **Megjegyzés:** CPU módban a tréning hosszú ideig fut. A rendszer többi funkciója (ajánlatkészítés, árak) eközben is elérhető.

---

## 11. BEÁLLÍTÁSOK

Az összes rendszerparaméter a Beállítások oldalon (`ui/beallitasok.html`) — bal oldali navigáció szekciókba rendezi.

### SMTP – Email kiszolgáló

Az OTP kódok küldéséhez szükséges. Gmail esetén App Password kell (nem a rendes jelszó).

| Mező | Érték (Gmail példa) |
|------|---------------------|
| Host | `smtp.gmail.com` |
| Port | `587` |
| Felhasználó | `valaki@gmail.com` |
| Jelszó | App Password (Gmail fiók → Biztonság → 2-lépéses → App jelszavak) |
| STARTTLS | Bekapcsolva |

**Teszt küldés** gomb → teszt emailt küld a bejelentkezett admin email-jére.

### AI beállítások

- **Claude API kulcs**: Anthropic Console-ból (`sk-ant-...`)
- **Modell**: `claude-sonnet-4-6` (ajánlott), `claude-opus-4-8` (lassabb, drágább), `claude-haiku-4-5-20251001` (gyors, olcsó)
- **Ollama URL**: `http://localhost:11434` (WSL2-n automatikus)
- **Azonosítási küszöbök**: Biztos: 70% / Bizonytalan: 50% (módosítható)

### Webes árak ütemezés

- **Scrape intervallum**: hány óránként frissüljön (1-168 óra)
- **Max. áradat kora**: ennyi napnál régebbi ár sárga jelzőt kap
- **Automatikus scrape**: be/ki kapcsoló

### PIN csere

Saját 6 jegyű PIN módosítása. A jelenlegi PIN szükséges. Más felhasználó PIN-jét az Admin konzolból lehet módosítani.

### Megjelenés

4 szín téma: **Éjszaka** / **Óceán** / **Erdő** / **Acél**.
Az ajánlat fejléc cégneve és adószáma is itt állítható be.

---

## 12. ADMIN KONZOL

Az Admin konzol (`ui/admin.html`) kizárólag **admin szerepkörű** felhasználóknak elérhető.

### Felhasználókezelés

#### Új felhasználó létrehozása
1. Kattints: **+ Új felhasználó**
2. Add meg:
   - **Felhasználónév**: egyedi, 3-32 karakter (betű, szám, `.`, `_`, `-`)
   - **PIN**: pontosan 6 számjegy
   - **Email cím**: kötelező! (OTP 2FA kód ide érkezik)
   - **Szerepkör**: `user` (kezelő) vagy `admin` (rendszergazda)
3. Kattints: **Létrehozás**

> **Fontos:** Email nélkül a belépési kód csak a szerver logba kerül — éles rendszeren minden felhasználóhoz meg kell adni az email-t!

#### Felhasználó táblázat oszlopai

| Oszlop | Leírás |
|--------|--------|
| Azonosító | Belső sorszám |
| Felhasználónév | Belépési név |
| Email | OTP kód célcíme |
| Szerepkör | user / admin |
| Állapot | Aktív / Inaktív |
| Zárolás | Zárolva ha hibás PIN próbálkozás |
| Kísérletek | Hibás PIN próbálkozások száma |

#### Felhasználó kezelése

- **PIN reset**: ha a felhasználó elfelejtette a PIN-t → admin beállíthat újat
- **Feloldás**: zárolás feloldása (brute force után)
- **Inaktiválás**: a felhasználó nem tud belépni (adatok megmaradnak)
- **Törlés**: végleges törlés (visszafordíthatatlan!)

### SMTP konfiguráció (Admin konzol is tartalmazza)

Ugyanaz mint a Beállítások oldalon — az admin konzolon is elérhető kényelmi célból.

### Audit napló (gyors)

Az admin konzolon az utolsó 20 naplóbejegyzés látható. Teljes napló: **Naplók** oldal.

---

## 13. NAPLÓK ÉS AUDIT

### Audit napló (`ui/naplok.html`)

Minden esemény naplózva van: belépés, módosítás, törlés, backup, fenyegetés blokkolás.

**Szűrők:**
- Dátum tartomány
- Felhasználó
- Esemény típus (login, create, update, delete, backup, security)
- Entitás (users, quotes, products, stb.)

**CSV export**: A szűrt napló exportálható.

**Auto-refresh**: 30 másodpercenként automatikusan frissül (kikapcsolható).

### Mit mutat egy bejegyzés?

| Mező | Leírás |
|------|--------|
| Időbélyeg | Mikor történt |
| Felhasználó | Ki végezte a műveletet |
| Esemény | login / create / update / delete / backup / security_threat |
| Entitás | Mire vonatkozott (quotes, products, users, stb.) |
| Entitás ID | A konkrét rekord azonosítója |
| Leírás | Szöveges leírás |
| IP cím | Honnan érkezett a kérés |

### Biztonsági napló

A `sanitize.py` middleware minden blokkolást naplóz (`security_threat` esemény):
- SQL injection kísérlet
- XSS kísérlet
- Path traversal kísérlet

Ha sok ilyen bejegyzést látsz, értesítsd a rendszergazdát.

---

## 14. BACKUP ÉS VISSZAÁLLÍTÁS

### Manuális backup

1. Beállítások → Backup → **📥 Export indítása**
2. A rendszer JSON fájlba exportálja az összes adatot
3. Fájl helye: `db_data\backups\backup_YYYYMMDD_HHMMSS.json`
4. **Fontos:** Ez a mappa ki van zárva a Google Drive szinkronból — manuálisan másold el!

### Mi kerül a backupba?
- Cikktörzs (products, activities, categories)
- Árak és web források
- Ajánlatok és tételsorok
- Golden examples (AI tanítóadatok)
- Rendszer konfiguráció (jelszavak nélkül)
- Audit napló

**Nem kerül bele:** felhasználók PIN hash-ei (biztonsági okból)

### Visszaállítás

1. Beállítások → Backup → Visszaállítás
2. Add meg a backup fájl elérési útját (pl. `db_data\backups\backup_20260610.json`)
3. Kattints: **♻️ Visszaállítás**

> ⚠️ **FIGYELEM:** A visszaállítás az aktuális adatot **felülírja**! Előtte készíts új backupot!

### Google Drive szinkron — kizárási lista

Ezeket a mappákat **SOHA ne szinkronizáld** futás közben:
- `db_data\` — PostgreSQL adatfájlok (sérülhet szinkron közben)
- `models\` — LLM modellek (~14 GB, felesleges)
- `wsl\` — WSL2 image (~1.2 GB, felesleges)
- `.env` — titkos kulcsok

---

## 15. HIBAELHÁRÍTÁS

### A belépési oldal nem tölt be

**Ellenőrzés:**
1. Fut-e a backend? → `status.bat`
2. Elérhető-e: `http://localhost:8000/health` → zöld badge kell
3. Ha nem: `start.bat` → várj 30 másodpercet

**Gyakori ok:** WSL2 nem indult el, vagy PostgreSQL nem tudott elindulni.

---

### "Adatbázis nem elérhető" üzenet

**Ellenőrzés:**
```
status.bat
```
Ha PostgreSQL le van állva:
- WSL2 módban: `start.bat` újraindítja
- Windows natív módban: `C:\CRT\db_start.bat`

---

### Az OTP kód nem érkezik meg

1. Ellenőrizd a spam/junk mappát
2. Ellenőrizd a Beállítások → SMTP → **Teszt küldés** → működik-e?
3. Ha nincs SMTP: a kód a szerver logban van (`logs\backend\backend.log`)

---

### AI azonosítás nem működik / "503 Service Unavailable"

Az AI pipeline sorban próbálja a motorokat. Ha mind sikertelen:
1. **Claude**: Beállítások → AI → Kapcsolat teszt → van-e érvényes kulcs?
2. **Ollama**: fut-e? → `http://localhost:11434` → elérhető?
3. **LoRA**: aktiválva van-e egy befejezett job?

Legalább egy motornak működnie kell.

---

### Scraper nem fut

1. Webes árak → forrás → **Ping teszt** → elérhető a weboldal?
2. Script lépések helyesek? → **Teszt futtatás** egyetlen termékre
3. Playwright telepítve van? → `python -m playwright install chromium`

---

### LoRA tréning leáll / "befagyott" job

Ha a szerver újraindult tréning közben, a job `pending` státuszban ragad:
1. LoRA oldal → job sorában → **Törlés** gomb
2. (A sor törölhető, mert a szerver ellenőrzi a tényleges futást `status.json` alapján)
3. Indíts új tréninget

---

### "Hozzáférés megtagadva" — 403 hiba

- **Admin oldalak** nem admin szerepkörrel → kérd az admint hogy emeljék a jogosultságod
- **Zárolva** vagyok → várj 30 percet, vagy kérd az admint: Admin konzol → felhasználó → **Feloldás**

---

### Export (xlsx/docx/PDF) nem tölt le

1. Van-e böngésző letöltési blokkolója?
2. Van-e az `exports\` mappa? (`ensure_runtime_dirs()` létrehozza induláskor)
3. Ellenőrizd a szerver logot: `logs\backend\backend.log`

---

### Diagnosztika (`ui/kezelőpult_v2.html`)

Az összes szolgáltatás állapota egy helyen:
- API szerver: verzió, uptime, platform (Windows/WSL2/Linux)
- PostgreSQL: kapcsolat, tábla count
- Ollama: fut-e, modellek listája
- ChromaDB: vektorok száma
- Szín paletta szerkesztő: témák tesztelése

---

## GYORSSEGÉLY KÁRTYÁK

### Bejelentkezési kód nem érkezett meg
→ Várj 1 percet → spam mappa → SMTP teszt adminnak → log fájl (`logs\backend\backend.log`)

### Elfelejtett PIN
→ Admin konzol → PIN reset (admin szükséges)

### Fiók zárolva
→ Admin konzol → Feloldás (admin szükséges)

### Ajánlatot véletlenül töröltem
→ v1.0-ban nincs kukó — backup szükséges visszaállításhoz

### AI rosszul azonosít
→ Javítsd manuálisan → Jóváhagy → Golden examples gyűlik → LoRA tréning indítása

### Új szállítói ár bekerítése
→ Árak → + Új ár → kézi bevitel  
→ VAGY: Webes árak → forrás hozzáadása → script rögzítése

---

*CRT Ajánlatsegéd Kezelői Kézikönyv v1.0 · Civil Rendszertechnika Kft. · 2026-06-10*
