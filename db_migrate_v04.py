"""
CRT Ajánlatsegéd – DB Migráció v0.4
Auth rendszer: users bővítés + auth_tokens tábla
Futtatás: py -3.11 db_migrate_v04.py
"""
import psycopg2
import getpass
import os
import sys
from datetime import datetime
from env_detect import get_db_url

DB_URL = get_db_url()

STEPS = [
    ("users.email mező",
     "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);"),

    ("users.locked_until mező",
     "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;"),

    ("users.attempt_count mező",
     "ALTER TABLE users ADD COLUMN IF NOT EXISTS attempt_count INTEGER DEFAULT 0;"),

    ("auth_tokens tábla", """
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
            code        VARCHAR(6)  NOT NULL,
            expires_at  TIMESTAMP   NOT NULL,
            used        BOOLEAN     DEFAULT false,
            created_at  TIMESTAMP   DEFAULT NOW()
        );
    """),

    ("auth_tokens index",
     "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(user_id, used);"),

    ("audit_log.ip_address mező",
     "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);"),

    ("system_config SMTP sorok", """
        INSERT INTO system_config (key, value, description) VALUES
          ('smtp_host', '',     'SMTP szerver (pl. smtp.gmail.com)')
        ON CONFLICT (key) DO NOTHING;
        INSERT INTO system_config (key, value, description) VALUES
          ('smtp_port', '587',  'SMTP port (587=STARTTLS, 465=SSL)')
        ON CONFLICT (key) DO NOTHING;
        INSERT INTO system_config (key, value, description) VALUES
          ('smtp_user', '',     'SMTP felhasználónév / email cím')
        ON CONFLICT (key) DO NOTHING;
        INSERT INTO system_config (key, value, description) VALUES
          ('smtp_pass', '',     'SMTP jelszó (app password)')
        ON CONFLICT (key) DO NOTHING;
        INSERT INTO system_config (key, value, description) VALUES
          ('smtp_from', '',     'Feladó email cím')
        ON CONFLICT (key) DO NOTHING;
    """),
]


def run():
    print("=" * 54)
    print("  CRT DB Migráció v0.4 – Auth rendszer")
    print("=" * 54)

    try:
        conn = psycopg2.connect(DB_URL)
    except Exception as e:
        print(f"\n❌ DB kapcsolat sikertelen: {e}")
        print("   Ellenőrizd hogy a PostgreSQL fut és a DB_URL helyes.")
        sys.exit(1)

    cur = conn.cursor()
    ok = 0

    for name, sql in STEPS:
        try:
            cur.execute(sql)
            conn.commit()
            print(f"  ✅  {name}")
            ok += 1
        except Exception as e:
            conn.rollback()
            print(f"  ❌  {name}: {e}")

    # ── Admin user ────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    admin_count = cur.fetchone()[0]

    if admin_count == 0:
        print("\n  ⚠️  Nincs admin felhasználó – létrehozás szükséges")
        try:
            import bcrypt
        except ImportError:
            print("  ❌  bcrypt hiányzik: py -3.11 -m pip install bcrypt")
            conn.close()
            sys.exit(1)

        env_user = os.environ.get("CRT_ADMIN_USER", "").strip()
        env_pin  = os.environ.get("CRT_ADMIN_PIN",  "").strip()
        env_mail = os.environ.get("CRT_ADMIN_EMAIL","").strip()

        if env_user and env_pin:
            username = env_user
            pin      = env_pin
            email    = env_mail
        else:
            username = input("\n  Admin felhasználónév: ").strip()
            while True:
                pin = getpass.getpass("  Admin PIN (6 számjegy): ").strip()
                if len(pin) == 6 and pin.isdigit():
                    break
                print("  ⚠️  Pontosan 6 számjegy kell!")
            email = input("  Admin email cím (2FA kódhoz): ").strip()

        pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
        try:
            cur.execute("""
                INSERT INTO users (username, pin_hash, email, role, active, created_at)
                VALUES (%s, %s, %s, 'admin', true, %s)
            """, (username, pin_hash, email, datetime.now()))
            conn.commit()
            print(f"\n  ✅  Admin létrehozva: {username} ({email})")
        except Exception as e:
            conn.rollback()
            print(f"\n  ❌  Admin létrehozási hiba: {e}")
    else:
        print(f"\n  ℹ️   Admin felhasználó már létezik ({admin_count} db) – kihagyva")

    cur.close()
    conn.close()

    print(f"\n{'=' * 54}")
    print(f"  Migráció kész: {ok}/{len(STEPS)} lépés sikeres")
    print(f"{'=' * 54}")
    print("\n  Következő lépés: py -3.11 -m uvicorn main:app --reload")


if __name__ == "__main__":
    run()
