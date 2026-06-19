#!/usr/bin/env python3
"""
CRT Ajánlatsegéd – Első admin felhasználó létrehozása
Futtatás: py -3.11 _setup/create_admin.py
         vagy WSL2-ben: python3.11 _setup/create_admin.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import bcrypt
except ImportError:
    print("✗ bcrypt csomag hiányzik – pip install bcrypt")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("✗ sqlalchemy csomag hiányzik – pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

def _default_db_url():
    try:
        with open("/proc/version") as f:
            if "microsoft" in f.read().lower():
                return "postgresql://crt_user:crt2026@localhost:5432/crt"  # WSL2
    except OSError:
        pass
    return "postgresql://crt_user:crt2026@localhost:5433/crt"  # Windows natív

DB_URL = os.environ.get("CRT_DB_URL", _default_db_url())

SEP = "═" * 52

def main():
    # Csendes mód: ha CRT_ADMIN_USER és CRT_ADMIN_PIN env var be van állítva
    env_user  = os.environ.get("CRT_ADMIN_USER", "").strip()
    env_pin   = os.environ.get("CRT_ADMIN_PIN",  "").strip()
    env_email = os.environ.get("CRT_ADMIN_EMAIL", "").strip() or None
    silent    = bool(env_user and env_pin)

    print(SEP)
    print("  CRT Ajánlatsegéd – Admin felhasználó létrehozása")
    if silent:
        print("  Mód: csendes (CRT_ADMIN_USER / CRT_ADMIN_PIN env var)")
    print(SEP)
    print(f"  DB: {DB_URL}\n")

    engine = create_engine(DB_URL, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ PostgreSQL kapcsolat OK")
    except Exception as e:
        print(f"✗ PostgreSQL hiba: {e}")
        print("  Ellenőrizd: fut-e a PostgreSQL, helyes-e a CRT_DB_URL?")
        sys.exit(1)

    # Meglévő adminok ellenőrzése
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT COUNT(*) FROM users WHERE role='admin'"
        )).fetchone()
        admin_count = row[0] if row else 0

    if admin_count > 0:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT username, email, created_at FROM users WHERE role='admin' ORDER BY created_at"
            )).fetchall()
        print(f"\n⚠  Már van {admin_count} admin felhasználó:")
        for r in rows:
            email_str = r[1] or "nincs email"
            ts = r[2].strftime("%Y-%m-%d %H:%M") if r[2] else "?"
            print(f"   - {r[0]}  ({email_str})  [{ts}]")

        if silent:
            print("Csendes mód: meglévő admin megtalálva, kilépés.")
            return
        answer = input("\nÚj admin-t akarsz létrehozni mellé? (i/n): ").strip().lower()
        if answer != "i":
            print("Kilépés – nincs változás.")
            return

    print()

    if silent:
        username = env_user
        email    = env_email
        pin      = env_pin
        if len(pin) != 6 or not pin.isdigit():
            print("✗ CRT_ADMIN_PIN pontosan 6 számjegy kell legyen!")
            sys.exit(1)
    else:
        # Felhasználónév
        username = input("Felhasználónév: ").strip()
        if not username or len(username) < 2:
            print("✗ A felhasználónév legalább 2 karakter kell!")
            sys.exit(1)

        # Email (opcionális – 2FA OTP küldéséhez kell)
        email = input("Email (opcionális, 2FA OTP-hez): ").strip() or None

        # PIN bekérése
        while True:
            pin = input("6 számjegyű PIN: ").strip()
            if len(pin) != 6 or not pin.isdigit():
                print("  ✗ A PIN pontosan 6 számjegy kell legyen!")
                continue
            pin2 = input("PIN megerősítés:  ").strip()
            if pin != pin2:
                print("  ✗ A két PIN nem egyezik, próbáld újra!\n")
                continue
            break

    pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (username, pin_hash, email, role, active, created_at, attempt_count) "
                "VALUES (:u, :h, :e, 'admin', true, NOW(), 0)"
            ), {"u": username, "h": pin_hash, "e": email})

        print(f"\n✓ Admin felhasználó létrehozva: {username}")
        if email:
            print(f"  Email: {email}  (2FA OTP erre érkezik)")
        print(f"  Belépés: http://localhost → PIN beírása")
        print(SEP)
    except Exception as e:
        print(f"\n✗ Hiba a mentésnél: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
