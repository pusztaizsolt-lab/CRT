"""
CRT Ajánlatsegéd – Projekt Struktúra Létrehozó
Futtasd: py -3.11 crt_struktura.py

Létrehozza a teljes önhordó mappastruktúrát
Bárhova másolható – a horgony mindenhol megtalálja magát!
"""
import os, sys, json, time

# ── HORGONY ───────────────────────────────────────────────
# Ez a fájl MINDIG a projekt gyökerében van
# Relatív útvonalak innen számítódnak
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE       = os.path.join(SCRIPT_DIR)

def p(path): return os.path.join(BASE, path)

# ── MAPPA STRUKTÚRA ───────────────────────────────────────
MAPPAK = [
    "core",
    "api/routes",
    "api/middleware",
    "db/pgsql",
    "db/db_data",
    "db/chroma_db1",
    "db/chroma_db2",
    "db/migrations",
    "ai/local_beta",
    "ocr/draw_compare",
    "ui/meta",
    "security",
    "utils/widget",
    "logs",
    "uploads",
    "exports",
    "backups",
]

# ── ALAP FÁJLOK ───────────────────────────────────────────
def config_py():
    return '''"""
CRT Ajánlatsegéd – Konfiguráció
HORGONY: Ez a fájl a projekt gyökerében van
Minden útvonal relatívan számítódik – bárhova másolható!
"""
import os
from dotenv import load_dotenv

# ── HORGONY ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)  # egy szinttel feljebb

def rel(*parts):
    """Relatív útvonal a projekt gyökeréhez képest"""
    return os.path.join(ROOT_DIR, *parts)

# Betöltés
load_dotenv(rel(".env"))

# ── ADATBÁZIS ─────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "crt")
DB_USER     = os.getenv("DB_USER", "crt_user")
DB_PASS     = os.getenv("DB_PASS", "crt2026")
DB_URL      = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── ÚTVONALAK (relatív – hordozható!) ────────────────────
PGSQL_BIN   = rel("db", "pgsql", "bin")
PG_CTL      = os.path.join(PGSQL_BIN, "pg_ctl.exe")
PSQL        = os.path.join(PGSQL_BIN, "psql.exe")
DATA_DIR    = rel("db", "db_data")
CHROMA_DB1  = rel("db", "chroma_db1")
CHROMA_DB2  = rel("db", "chroma_db2")
AI_DIR      = rel("ai", "local_beta")
UPLOAD_DIR  = rel("uploads")
EXPORT_DIR  = rel("exports")
LOG_DIR     = rel("logs")
UI_DIR      = rel("ui")
BACKUP_DIR  = rel("backups")

# ── API ───────────────────────────────────────────────────
API_PORT    = int(os.getenv("API_PORT", "8000"))
NTP_SERVER  = os.getenv("NTP_SERVER", "time.google.com")

# ── AI API KULCSOK ────────────────────────────────────────
CLAUDE_KEY  = os.getenv("CLAUDE_API_KEY", "")
GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")

# ── KONFIDENCIA KÜSZÖBÖK ─────────────────────────────────
CONF_AUTO   = 0.90   # Automatikusan elfogadva
CONF_WARN   = 0.70   # Figyelmeztetéssel elfogadva
CONF_STOP   = 0.50   # Megáll, megerősítés kell
# < 0.50 = eldobva, kézi bevitel
'''

def env_template():
    return """# CRT Ajánlatsegéd – Környezeti változók
# Másold ki és töltsd ki!

# Adatbázis
DB_HOST=localhost
DB_PORT=5432
DB_NAME=crt
DB_USER=crt_user
DB_PASS=crt2026

# API
API_PORT=8000
NTP_SERVER=time.google.com

# AI API kulcsok (opcionális fejlesztési fázisban)
CLAUDE_API_KEY=
GEMINI_API_KEY=
"""

def start_bat():
    pg_ctl = os.path.join("db", "pgsql", "bin", "pg_ctl.exe")
    data   = os.path.join("db", "db_data")
    log    = os.path.join("logs", "pg.log")
    return f"""@echo off
cd /d "%~dp0"
echo CRT Ajanlatseged indul...
echo.
echo [1/3] PostgreSQL inditas...
"{pg_ctl}" start -D "{data}" -l "{log}"
timeout /t 3 /nobreak > nul
echo.
echo [2/3] Backend inditas...
py -3.11 -m uvicorn core.main:app --reload --port 8000
echo.
echo [3/3] Kesz! http://localhost:8000
pause
"""

def gitignore():
    return """# CRT Ajánlatsegéd
.env
db/db_data/
db/chroma_db1/
db/chroma_db2/
logs/
uploads/
exports/
backups/
__pycache__/
*.pyc
*.log
"""

def readme():
    return """# CRT Ajánlatsegéd

## Gyors indítás
1. Dupla klikk: start.bat
2. Böngésző: http://localhost:8000

## Mappa struktúra
- core/      → Backend (FastAPI)
- api/       → Endpoint-ok
- db/        → Adatbázisok (PostgreSQL + ChromaDB)
- ai/        → AI motorok (helyi béta + API)
- ocr/       → Dokumentum feldolgozás
- ui/        → Felhasználói felületek
- security/  → Biztonsági réteg
- utils/     → Segédeszközök

## Önhordó
Ez a projekt bárhova másolható és ott is fut!
Minden útvonal relatív – nincs hardcoded path.
"""

# ── LÉTREHOZÁS ────────────────────────────────────────────
def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║   CRT – Projekt Struktúra Létrehozó          ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"\n  📁 Gyökér: {BASE}\n")

    # Mappák
    print("  Mappák létrehozása...")
    for mappa in MAPPAK:
        full = p(mappa)
        os.makedirs(full, exist_ok=True)
        print(f"  ✅  {mappa}")

    print()

    # Fájlok
    print("  Alap fájlok létrehozása...")

    fajlok = {
        "core/config.py":  config_py(),
        ".env.template":   env_template(),
        "start.bat":       start_bat(),
        ".gitignore":      gitignore(),
        "README.md":       readme(),
    }

    for nev, tartalom in fajlok.items():
        full = p(nev)
        if not os.path.exists(full):
            with open(full, "w", encoding="utf-8") as f:
                f.write(tartalom)
            print(f"  ✅  {nev}")
        else:
            print(f"  ⏭️   {nev} (már létezik)")

    # .env csak ha nincs
    env_path = p(".env")
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_template())
        print(f"  ✅  .env")

    # Horgony teszt
    print("\n  Horgony teszt...")
    from core.config import BASE_DIR, DB_URL, UPLOAD_DIR
    print(f"  ✅  BASE_DIR:   {BASE_DIR}")
    print(f"  ✅  DB_URL:     {DB_URL[:40]}...")
    print(f"  ✅  UPLOAD_DIR: {UPLOAD_DIR}")

    print(f"\n{'='*50}")
    print(f"  🎉 Struktúra kész!")
    print(f"  📁 {BASE}")
    print(f"  🚀 Indítás: start.bat")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    main()
