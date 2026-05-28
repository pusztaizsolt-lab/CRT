"""
CRT – PostgreSQL Inicializáló és Indító
Futtasd: py -3.11 db_init.py
"""
import subprocess, os, sys, time

# ── KONFIG ────────────────────────────────────────────────
BASE     = os.path.dirname(os.path.abspath(__file__))
DB_DIR   = os.path.join(BASE, "db", "pgsql")
BIN      = os.path.join(DB_DIR, "bin")
DATA     = os.path.join(BASE, "db_data")
PG_CTL   = os.path.join(BIN, "pg_ctl.exe")
INITDB   = os.path.join(BIN, "initdb.exe")
PSQL     = os.path.join(BIN, "psql.exe")
PORT     = "5432"
DB_NAME  = "crt"
DB_USER  = "crt_user"
DB_PASS  = "crt2026"

def run(cmd, capture=True):
    return subprocess.run(
        cmd, capture_output=capture,
        text=True, shell=True
    )

def step(msg):
    print(f"\n▶ {msg}")

def ok(msg):
    print(f"  ✅ {msg}")

def err(msg):
    print(f"  ❌ {msg}")

def main():
    print("╔══════════════════════════════════════════╗")
    print("║   CRT – PostgreSQL Inicializáló          ║")
    print("╚══════════════════════════════════════════╝")

    # 1. Ellenőrzés
    step("PostgreSQL binárisok ellenőrzése...")
    if not os.path.exists(PG_CTL):
        err(f"Nem találom: {PG_CTL}")
        err("Ellenőrizd hogy a db\\ mappába bontottad ki!")
        sys.exit(1)
    ok("pg_ctl.exe megvan")

    # 2. Adatmappa inicializálás
    step("Adatmappa inicializálása...")
    if os.path.exists(DATA):
        ok(f"Már létezik: {DATA} – kihagyva")
    else:
        os.makedirs(DATA, exist_ok=True)
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASS
        r = run(f'"{INITDB}" -D "{DATA}" -U postgres -E UTF8 --locale=C')
        if r.returncode == 0:
            ok("Adatmappa létrehozva")
        else:
            err(f"Hiba: {r.stderr}")
            sys.exit(1)

    # 3. PostgreSQL indítás
    step("PostgreSQL indítása...")
    r = run(f'"{PG_CTL}" -D "{DATA}" -l "{BASE}\\pg.log" start')
    if r.returncode == 0:
        ok("PostgreSQL elindult!")
    else:
        if "already running" in r.stdout or "already running" in r.stderr:
            ok("Már fut – folytatás")
        else:
            err(f"Hiba: {r.stderr}")

    time.sleep(2)

    # 4. CRT adatbázis és user létrehozás
    step("CRT adatbázis létrehozása...")

    cmds = [
        f"CREATE USER {DB_USER} WITH PASSWORD '{DB_PASS}';",
        f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};",
        f"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};",
    ]

    for cmd in cmds:
        r = run(f'"{PSQL}" -U postgres -p {PORT} -c "{cmd}"')
        if r.returncode == 0 or "already exists" in r.stderr:
            ok(cmd[:50]+"...")
        else:
            print(f"  ⚠️  {r.stderr.strip()[:80]}")

    # 5. Kapcsolat teszt
    step("Kapcsolat teszt...")
    r = run(f'"{PSQL}" -U {DB_USER} -d {DB_NAME} -p {PORT} -c "SELECT version();"')
    if r.returncode == 0:
        ok("PostgreSQL kapcsolat OK!")
        print(f"\n  {r.stdout.strip()[:80]}")
    else:
        err(f"Kapcsolat hiba: {r.stderr[:80]}")

    # 6. .env fájl
    step(".env fájl létrehozása...")
    env_content = f"""# CRT Ajánlatsegéd – Környezeti változók
DATABASE_URL=postgresql://{DB_USER}:{DB_PASS}@localhost:{PORT}/{DB_NAME}
DB_HOST=localhost
DB_PORT={PORT}
DB_NAME={DB_NAME}
DB_USER={DB_USER}
DB_PASS={DB_PASS}
API_PORT=8000
NTP_SERVER=time.google.com
"""
    env_path = os.path.join(BASE, ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write(env_content)
        ok(".env fájl létrehozva")
    else:
        ok(".env már létezik – kihagyva")

    print("\n" + "="*50)
    print("  🎉 PostgreSQL kész!")
    print(f"  Host:     localhost:{PORT}")
    print(f"  DB:       {DB_NAME}")
    print(f"  User:     {DB_USER}")
    print(f"  Log:      pg.log")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
