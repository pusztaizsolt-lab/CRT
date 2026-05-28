# CRT Ajánlatsegéd – Teljes Tech Stack és Projekt Struktúra
## v1.0 – 2026. május

---

## 1. PROJEKT STRUKTÚRA – Önhordó, hordozható

```
C:\SEGÉD\                          ← Gyökér (bárhova másolható!)
│
├── core\                          ← Rendszermag
│   ├── main.py                    ← FastAPI backend
│   ├── config.py                  ← Konfiguráció (relatív útvonalak!)
│   ├── .env                       ← Környezeti változók
│   └── start.bat                  ← Egy kattintásos indítás
│
├── api\                           ← API réteg
│   ├── routes\                    ← Endpoint-ok
│   │   ├── quotes.py              ← Ajánlat kezelés
│   │   ├── products.py            ← Cikktörzs
│   │   ├── activities.py          ← Tevékenységi törzs
│   │   ├── prices.py              ← Árak
│   │   ├── upload.py              ← Fájl befogadás
│   │   ├── ai.py                  ← AI motor hívások
│   │   └── admin.py               ← Admin funkciók
│   └── middleware\
│       ├── auth.py                ← PIN hitelesítés
│       ├── sanitize.py            ← Sanitizálási réteg
│       └── log.py                 ← Napló middleware
│
├── db\                            ← Adatbázis
│   ├── pgsql\                     ← Portable PostgreSQL 16.x
│   │   └── bin\pg_ctl.exe
│   ├── db_data\                   ← PostgreSQL adatfájlok
│   ├── chroma_db1\                ← ChromaDB – nyers vektorok
│   ├── chroma_db2\                ← ChromaDB – tisztított vektorok
│   ├── schema.py                  ← SQLAlchemy modellek
│   └── migrations\                ← Alembic migrációk
│
├── ai\                            ← AI motorok
│   ├── local_beta\                ← llamafile / llama-cpp
│   │   └── motor.exe              ← llamafile (modell+runtime)
│   ├── embeddings.py              ← Embedding kezelés
│   ├── identifier.py              ← Termék/tevékenység azonosítás
│   ├── sanitizer.py               ← Adat sanitizálás
│   └── golden_store.py            ← Arany Példatár kezelés
│
├── ocr\                           ← OCR és dokumentum feldolgozás
│   ├── processor.py               ← Fő OCR motor
│   ├── structure_detect.py        ← Dokumentum struktúra felismerés
│   ├── template_learn.py          ← Sablon tanulás
│   └── draw_compare\              ← Rajz komparálás (99-es pont)
│       └── vision.py              ← LLaVA Vision AI
│
├── ui\                            ← Felhasználói felületek
│   ├── felhasznalo.html            ← Fő felhasználói UI
│   ├── admin.html                 ← Admin konzol
│   ├── kategoriak.html            ← Kategória kezelő
│   └── meta\                      ← META fejlesztői platform
│       └── fejleszto.html
│
├── security\                      ← Biztonsági réteg
│   ├── auth.py                    ← PIN, bcrypt, JWT
│   ├── encryption.py              ← AES-256 titkosítás
│   └── konzol_indito.exe          ← Admin konzol belépő
│
├── utils\                         ← Segédeszközök
│   ├── ntp.py                     ← NTP szinkron
│   ├── export.py                  ← Excel/Word/PDF export
│   └── widget\
│       └── statusz_widget.exe     ← Tálca státusz jelző
│
├── logs\                          ← Naplók
│   ├── crt.log
│   ├── pg.log
│   └── ai.log
│
├── uploads\                       ← Feltöltött fájlok (temp)
├── exports\                       ← Exportált ajánlatok
└── backups\                       ← Adatbázis mentések
```

---

## 2. HORGONY – Önhordó relatív útvonal rendszer

```python
# config.py – MINDEN útvonal ehhez képest számítódik
import os

# A horgony: a config.py helye = projekt gyökér
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ha kimásolod → BASE_DIR automatikusan az új helyre mutat!

# Összes útvonal relatívan
DB_DIR      = os.path.join(BASE_DIR, "..", "db")
PGSQL_DIR   = os.path.join(DB_DIR, "pgsql", "bin")
DATA_DIR    = os.path.join(DB_DIR, "db_data")
CHROMA_DB1  = os.path.join(DB_DIR, "chroma_db1")
CHROMA_DB2  = os.path.join(DB_DIR, "chroma_db2")
AI_DIR      = os.path.join(BASE_DIR, "..", "ai", "local_beta")
UPLOAD_DIR  = os.path.join(BASE_DIR, "..", "uploads")
EXPORT_DIR  = os.path.join(BASE_DIR, "..", "exports")
LOG_DIR     = os.path.join(BASE_DIR, "..", "logs")
UI_DIR      = os.path.join(BASE_DIR, "..", "ui")
```

---

## 3. SZOFTVER ELEMEK – Teljes lista

### BACKEND (Python – Közép/Magas szintű)

| Csomag | Verzió | Szerepe |
|--------|--------|---------|
| fastapi | 0.110+ | Web szerver, API routing |
| uvicorn | 0.29+ | ASGI szerver |
| celery | 5.3+ | Aszinkron task queue |
| redis | 5.0+ | Celery broker |
| sqlalchemy | 2.0+ | PostgreSQL ORM |
| psycopg2-binary | 2.9+ | PostgreSQL driver |
| pydantic | 2.6+ | JSON validáció, séma |
| alembic | 1.13+ | DB migráció |
| httpx | 0.27+ | Async HTTP kliens |
| python-dotenv | 1.0+ | .env kezelés |

### ADATBÁZIS

| Szoftver | Típus | Szerepe |
|----------|-------|---------|
| PostgreSQL 16.x | Relációs | Fő adattár (portable ZIP) |
| ChromaDB 0.4+ | Vektoros | DB1: nyers, DB2: tisztított |
| Redis 7.x | Cache/Queue | Celery broker |

### AI MOTOROK

| Csomag | Szerepe | Mikor aktív |
|--------|---------|-------------|
| llama-cpp-python | Helyi béta motor | Alapértelmezett |
| llamafile | Alternatív helyi motor | Portable .exe |
| anthropic | Claude API | Fallback, komplex |
| google-generativeai | Gemini API | Keresztellenőrzés |
| sentence-transformers | Embedding matrix | Vektorizálás |
| torch (CPU) | ML alap | Embedding alatt |
| scikit-learn | Statisztika | Ártrend, becslés |

### OCR ÉS DOKUMENTUM FELDOLGOZÁS

| Csomag | Szerepe |
|--------|---------|
| pytesseract | OCR – képből szöveg |
| Pillow | Képkezelés, előfeldolgozás |
| pdfplumber | PDF szöveg kinyerés |
| python-docx | Word feldolgozás |
| openpyxl | Excel olvasás/írás |
| beautifulsoup4 | HTML scraping |
| lxml | XML/HTML parser |
| playwright | Web automatizálás |

### RAJZ KOMPARÁLÁS (99-es pont – jövőbeli)

| Csomag | Szerepe |
|--------|---------|
| LLaVA (Ollama Vision) | Tervrajz értelmezés |
| OpenCV (cv2) | Képfeldolgozás, alakfelismerés |
| pdf2image | PDF → képkonverzió |
| Google Vision API | Alternatív Vision AI |

### EXPORT ÉS KIMENET

| Csomag | Szerepe |
|--------|---------|
| weasyprint | PDF generálás |
| reportlab | PDF alternatív |
| jinja2 | Sablon motor |
| openpyxl | Excel export |
| python-docx | Word export |

### BIZTONSÁG

| Csomag | Szerepe |
|--------|---------|
| bcrypt | PIN hash |
| cryptography | AES-256 titkosítás |
| python-jose | JWT token |
| passlib | Jelszó kezelés |

### HÁLÓZAT ÉS IDŐ

| Csomag | Szerepe |
|--------|---------|
| ntplib | NTP szinkron (time.google.com) |
| requests | HTTP kliens |
| httpx | Async HTTP |

### CSOMAGOLÁS (Plug & Play)

| Eszköz | Szerepe |
|--------|---------|
| Nuitka | Python → natív .exe fordítás |
| PyInstaller | Alternatív csomagoló |

---

## 4. KÜLSŐ API-K

| API | Célra | Prioritás |
|-----|-------|-----------|
| Claude API (Anthropic) | AI fallback, komplex azonosítás | Magas |
| Gemini API (Google) | Keresztellenőrzés, META platform | Magas |
| Google Vision API | Tervrajz felismerés (jövő) | Közepes |
| Google Search API | Kontextus keresés | Közepes |
| NTP (time.google.com) | Időbélyeg szinkron | Kritikus |
| Partner API-k | Árlistaátvétel | Projekt függő |

---

## 5. TECHNIKAI SZINTEK

```
MAGAS SZINTŰ (mi ezt fejlesztünk):
  Python / FastAPI / SQLAlchemy
  JavaScript (vanilla) / HTML / CSS
  ChromaDB Python client
  AI API hívások

KÖZEPES SZINTŰ (használjuk, nem írjuk):
  PostgreSQL SQL lekérdezések
  Pydantic sémák
  Celery task-ok
  Alembic migrációk

ALACSONY SZINTŰ (kerüljük Windows miatt):
  C++ (csak a Build Tools-on át)
  Windows Registry – NEM HASZNÁLJUK
  System Services – NEM HASZNÁLJUK
  Hardcoded paths – NEM HASZNÁLJUK
```

---

## 6. TELEPÍTÉSI SORREND

```
1. Python 3.11
2. Visual Studio Build Tools (C++)
3. pip install [összes csomag]
4. PostgreSQL 16.x portable
5. ChromaDB (pip-pel)
6. llamafile letöltés
7. Projekt struktúra létrehozás
8. .env konfiguráció
9. DB inicializálás
10. Első indítás tesztelés
```

---

## 7. ÖNHORDÓ ELLENŐRZŐLISTA

```
✅ Minden útvonal relatív (config.py horgony)
✅ Nincs registry bejegyzés
✅ Nincs rendszerszolgáltatás telepítés
✅ PostgreSQL portable (ZIP verzió)
✅ llamafile portable (.exe)
✅ .env fájlban minden konfiguráció
✅ start.bat egy kattintásos indítás
✅ Másolás = működő rendszer
```
