"""
CRT Adatbázis Migrációs Script v0.2
Futtatás: py -3.11 db_migrate_v02.py

Változások:
  products   → +crt_code, +supplier_code, +model
  activities → +crt_code
  prices     → +price_type
"""
from sqlalchemy import create_engine, text
import logging
from env_detect import get_db_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("CRT.migrate")

DB_URL = get_db_url()
engine = create_engine(DB_URL, echo=False)

# ── MIGRÁCIÓK ─────────────────────────────────────────────────
# Minden lépés idempotens: IF NOT EXISTS / DO NOTHING

MIGRATIONS = [

    # ── products: crt_code ────────────────────────────────────
    ("products.crt_code",
     "ALTER TABLE products ADD COLUMN IF NOT EXISTS crt_code VARCHAR(20) UNIQUE"),

    # ── products: supplier_code ───────────────────────────────
    ("products.supplier_code",
     "ALTER TABLE products ADD COLUMN IF NOT EXISTS supplier_code VARCHAR(100)"),

    # ── products: model ───────────────────────────────────────
    ("products.model",
     "ALTER TABLE products ADD COLUMN IF NOT EXISTS model VARCHAR(100)"),

    # ── activities: crt_code ──────────────────────────────────
    ("activities.crt_code",
     "ALTER TABLE activities ADD COLUMN IF NOT EXISTS crt_code VARCHAR(20) UNIQUE"),

    # ── prices: price_type ────────────────────────────────────
    ("prices.price_type",
     "ALTER TABLE prices ADD COLUMN IF NOT EXISTS price_type VARCHAR(20) DEFAULT 'lista'"),

    # ── index: gyorsabb keresés crt_code-ra ───────────────────
    ("idx_products_crt_code",
     "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_crt_code ON products(crt_code) WHERE crt_code IS NOT NULL"),

    ("idx_activities_crt_code",
     "CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_crt_code ON activities(crt_code) WHERE crt_code IS NOT NULL"),

    ("idx_prices_price_type",
     "CREATE INDEX IF NOT EXISTS idx_prices_price_type ON prices(price_type)"),
]

# ── CRT KÓD GENERÁTOR ─────────────────────────────────────────
def generate_crt_codes(conn):
    """Meglévő soroknak generál CRT kódot ha nincs még"""

    # Termékek
    prods = conn.execute(text(
        "SELECT item_id FROM products WHERE crt_code IS NULL ORDER BY created_at"
    )).fetchall()

    for i, row in enumerate(prods, start=1):
        code = f"CRT-P-{i:06d}"
        conn.execute(text(
            "UPDATE products SET crt_code = :code WHERE item_id = :id AND crt_code IS NULL"
        ), {"code": code, "id": row[0]})

    if prods:
        log.info(f"  Termék CRT kódok generálva: {len(prods)} db")

    # Tevékenységek
    acts = conn.execute(text(
        "SELECT item_id FROM activities WHERE crt_code IS NULL ORDER BY created_at"
    )).fetchall()

    for i, row in enumerate(acts, start=1):
        code = f"CRT-A-{i:06d}"
        conn.execute(text(
            "UPDATE activities SET crt_code = :code WHERE item_id = :id AND crt_code IS NULL"
        ), {"code": code, "id": row[0]})

    if acts:
        log.info(f"  Tevékenység CRT kódok generálva: {len(acts)} db")

    # Árak – price_type default beállítás db_level alapján
    conn.execute(text("""
        UPDATE prices SET price_type = 'lista'
        WHERE price_type IS NULL OR price_type = 'lista'
    """))

# ── SEQUENCE FUNKCIÓ DB-BEN ───────────────────────────────────
# A jövőbeli INSERT-ekhez auto-incrementáló CRT kód
SEQUENCE_SQL = """
CREATE OR REPLACE FUNCTION next_crt_code(prefix TEXT)
RETURNS TEXT AS $$
DECLARE
    seq_val INT;
BEGIN
    IF prefix = 'CRT-P' THEN
        SELECT COALESCE(MAX(CAST(SUBSTRING(crt_code FROM 7) AS INT)), 0) + 1
        INTO seq_val FROM products WHERE crt_code LIKE 'CRT-P-%';
    ELSE
        SELECT COALESCE(MAX(CAST(SUBSTRING(crt_code FROM 7) AS INT)), 0) + 1
        INTO seq_val FROM activities WHERE crt_code LIKE 'CRT-A-%';
    END IF;
    RETURN prefix || '-' || LPAD(seq_val::TEXT, 6, '0');
END;
$$ LANGUAGE plpgsql;
"""

# ── FŐ FUTTATÁS ───────────────────────────────────────────────
def run():
    print("\n╔══════════════════════════════════════════════╗")
    print("║   CRT – Adatbázis Migráció v0.2             ║")
    print("╚══════════════════════════════════════════════╝\n")

    with engine.begin() as conn:

        # 1. Oszlopok hozzáadása
        print("  [1/3] Séma bővítés...")
        for name, sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                log.info(f"  ✅  {name}")
            except Exception as e:
                log.warning(f"  ⚠️   {name}: {e}")

        # 2. Sequence funkció
        print("\n  [2/3] next_crt_code() funkció telepítése...")
        try:
            conn.execute(text(SEQUENCE_SQL))
            log.info("  ✅  next_crt_code() OK")
        except Exception as e:
            log.warning(f"  ⚠️   {e}")

        # 3. Meglévő sorok kódolása
        print("\n  [3/3] Meglévő sorok CRT kód generálás...")
        generate_crt_codes(conn)

    # Ellenőrzés
    print("\n  Ellenőrzés...")
    with engine.connect() as conn:
        checks = [
            ("products.crt_code",      "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='products' AND column_name='crt_code'"),
            ("products.supplier_code", "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='products' AND column_name='supplier_code'"),
            ("products.model",         "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='products' AND column_name='model'"),
            ("activities.crt_code",    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='activities' AND column_name='crt_code'"),
            ("prices.price_type",      "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='prices' AND column_name='price_type'"),
        ]
        all_ok = True
        for label, sql in checks:
            exists = conn.execute(text(sql)).scalar() > 0
            print(f"  {'✅' if exists else '❌'}  {label}")
            if not exists:
                all_ok = False

        # Statisztika
        p_count = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        a_count = conn.execute(text("SELECT COUNT(*) FROM activities")).scalar()
        p_coded = conn.execute(text("SELECT COUNT(*) FROM products WHERE crt_code IS NOT NULL")).scalar()
        a_coded = conn.execute(text("SELECT COUNT(*) FROM activities WHERE crt_code IS NOT NULL")).scalar()

        print(f"\n  Termékek:     {p_count} db  ({p_coded} kódolt)")
        print(f"  Tevékenységek:{a_count} db  ({a_coded} kódolt)")

    if all_ok:
        print("\n  🎉 Migráció sikeres! Az adatbázis v0.2-re frissült.\n")
    else:
        print("\n  ❌ Egyes lépések nem sikerültek – ellenőrizd a logot!\n")

if __name__ == "__main__":
    run()
