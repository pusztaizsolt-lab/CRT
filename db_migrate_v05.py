"""
CRT Ajánlatsegéd – DB Migráció v0.5
Web scraping infrastruktúra + termék/ajánlat bővítés
Futtatás: py -3.11 db_migrate_v05.py
"""
import psycopg2
import sys
from env_detect import get_db_url
from datetime import datetime

DB_URL = get_db_url()

STEPS = [

    # ── WEB SOURCES – nagykereskedői weboldalak ──────────────
    ("web_sources tábla", """
        CREATE TABLE IF NOT EXISTS web_sources (
            id           SERIAL PRIMARY KEY,
            name         VARCHAR(255)  NOT NULL,
            url          TEXT          NOT NULL,
            source_type  VARCHAR(20)   NOT NULL DEFAULT 'public',
            -- 'public' | 'login_required' | 'api'
            login_url    TEXT,
            username     VARCHAR(255),
            password_enc TEXT,
            -- jelszó AES titkosítva (kulcs: CRT_ENCRYPT_KEY env var)
            api_key_enc  TEXT,
            -- API kulcs ha van (titkosítva)
            status       VARCHAR(20)   NOT NULL DEFAULT 'new',
            -- 'new' | 'reachable' | 'learned' | 'error' | 'disabled'
            last_reached TIMESTAMP,
            last_scraped TIMESTAMP,
            error_msg    TEXT,
            notes        TEXT,
            created_by   INTEGER REFERENCES users(id),
            created_at   TIMESTAMP     DEFAULT NOW(),
            updated_at   TIMESTAMP     DEFAULT NOW()
        );
    """),

    ("web_sources index (url)", """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_web_sources_url
        ON web_sources(url);
    """),

    # ── WEB SCRIPTS – Playwright lépések ─────────────────────
    ("web_scripts tábla", """
        CREATE TABLE IF NOT EXISTS web_scripts (
            id           SERIAL PRIMARY KEY,
            source_id    INTEGER NOT NULL REFERENCES web_sources(id) ON DELETE CASCADE,
            script_type  VARCHAR(30) NOT NULL DEFAULT 'login',
            -- 'login' | 'navigate' | 'extract' | 'search'
            version      INTEGER     NOT NULL DEFAULT 1,
            active       BOOLEAN     NOT NULL DEFAULT true,
            script_json  JSONB       NOT NULL DEFAULT '[]'::jsonb,
            -- [{action, selector, value, wait_ms}, ...]
            recorded_by  INTEGER REFERENCES users(id),
            recorded_at  TIMESTAMP   DEFAULT NOW(),
            last_run     TIMESTAMP,
            last_run_ok  BOOLEAN,
            run_count    INTEGER     DEFAULT 0,
            notes        TEXT
        );
    """),

    ("web_scripts index", """
        CREATE INDEX IF NOT EXISTS idx_web_scripts_source
        ON web_scripts(source_id, script_type, active);
    """),

    # ── WEB PRICES – weboldalakról gyűjtött árak ─────────────
    ("web_prices tábla", """
        CREATE TABLE IF NOT EXISTS web_prices (
            id           SERIAL PRIMARY KEY,
            source_id    INTEGER NOT NULL REFERENCES web_sources(id) ON DELETE CASCADE,
            item_id      UUID,
            -- NULL = még nem lett párosítva a products/activities táblával
            raw_name     TEXT NOT NULL,
            raw_price    NUMERIC(14,4),
            currency     VARCHAR(3)  DEFAULT 'HUF',
            unit         VARCHAR(30),
            manufacturer VARCHAR(255),
            url_detail   TEXT,
            scraped_at   TIMESTAMP   DEFAULT NOW(),
            valid_until  TIMESTAMP,
            matched      BOOLEAN     DEFAULT false,
            match_confidence NUMERIC(4,3)
        );
    """),

    ("web_prices index (source + scraped)", """
        CREATE INDEX IF NOT EXISTS idx_web_prices_source_scraped
        ON web_prices(source_id, scraped_at DESC);
    """),

    ("web_prices index (item_id)", """
        CREATE INDEX IF NOT EXISTS idx_web_prices_item
        ON web_prices(item_id) WHERE item_id IS NOT NULL;
    """),

    # ── PRODUCTS bővítés ──────────────────────────────────────
    ("products.description mező", """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS description TEXT;
    """),

    ("products.ean mező", """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS ean VARCHAR(20);
    """),

    ("products.part_number mező", """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS part_number VARCHAR(100);
    """),

    ("products.weight_kg mező", """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS weight_kg NUMERIC(10,4);
    """),

    ("products.tags mező", """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
    """),

    # ── QUOTES – ajánlatok fej ────────────────────────────────
    ("quotes tábla", """
        CREATE TABLE IF NOT EXISTS quotes (
            id            SERIAL PRIMARY KEY,
            quote_number  VARCHAR(50) UNIQUE,
            title         VARCHAR(500),
            client_name   VARCHAR(255),
            client_ref    VARCHAR(100),
            -- ügyfél saját referenciaszáma
            status        VARCHAR(30) NOT NULL DEFAULT 'draft',
            -- 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired'
            source_file   TEXT,
            -- feltöltött ajánlatkérő fájl neve
            source_mode   VARCHAR(20) DEFAULT 'upload',
            -- 'upload' | 'manual' | 'copy'
            base_quote_id INTEGER REFERENCES quotes(id),
            -- korábbi ajánlat alapján létrehozva
            valid_until   TIMESTAMP,
            notes         TEXT,
            created_by    INTEGER REFERENCES users(id),
            created_at    TIMESTAMP DEFAULT NOW(),
            updated_at    TIMESTAMP DEFAULT NOW()
        );
    """),

    ("quotes index (status)", """
        CREATE INDEX IF NOT EXISTS idx_quotes_status
        ON quotes(status, created_at DESC);
    """),

    ("quotes index (client_name)", """
        CREATE INDEX IF NOT EXISTS idx_quotes_client
        ON quotes(LOWER(client_name));
    """),

    # ── QUOTE LINES – ajánlat sorok ──────────────────────────
    ("quote_lines tábla", """
        CREATE TABLE IF NOT EXISTS quote_lines (
            id           SERIAL PRIMARY KEY,
            quote_id     INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
            line_no      INTEGER NOT NULL,
            item_type    VARCHAR(20) DEFAULT 'product',
            -- 'product' | 'activity' | 'manual' | 'skip'
            item_id      UUID,
            raw_name     TEXT,
            -- eredeti szöveg a feltöltött dokumentumból
            name         VARCHAR(500),
            manufacturer VARCHAR(255),
            quantity     NUMERIC(12,4) DEFAULT 1,
            unit         VARCHAR(30),
            unit_price   NUMERIC(14,4),
            total_price  NUMERIC(14,4),
            currency     VARCHAR(3) DEFAULT 'HUF',
            confidence   NUMERIC(4,3),
            -- AI azonosítás megbízhatósága
            cell_status  VARCHAR(20) DEFAULT 'raw',
            -- 'raw' | 'identified' | 'uncertain' | 'manual' | 'skip' | 'done'
            price_source VARCHAR(30),
            -- 'db' | 'web' | 'manual' | null
            price_date   TIMESTAMP,
            notes        TEXT
        );
    """),

    ("quote_lines index (quote_id)", """
        CREATE INDEX IF NOT EXISTS idx_quote_lines_quote
        ON quote_lines(quote_id, line_no);
    """),

    # ── SYSTEM CONFIG bővítés ─────────────────────────────────
    ("system_config: scrape_interval_hours", """
        INSERT INTO system_config (key, value, description) VALUES
          ('scrape_interval_hours', '24',
           'Webes ár lekérdezés ciklusa (óra)')
        ON CONFLICT (key) DO NOTHING;
    """),

    ("system_config: max_price_age_days", """
        INSERT INTO system_config (key, value, description) VALUES
          ('max_price_age_days', '30',
           'Ennyi nap után az ár "régi" (sárga jelző)')
        ON CONFLICT (key) DO NOTHING;
    """),

    ("system_config: quote_validity_days", """
        INSERT INTO system_config (key, value, description) VALUES
          ('quote_validity_days', '30',
           'Ajánlat érvényességi ideje napokban')
        ON CONFLICT (key) DO NOTHING;
    """),

    ("system_config: encrypt_key_hint", """
        INSERT INTO system_config (key, value, description) VALUES
          ('encrypt_key_hint', '',
           'AES kulcs fingerprint (maga a kulcs csak CRT_ENCRYPT_KEY env var-ban)')
        ON CONFLICT (key) DO NOTHING;
    """),
]


def run():
    print("=" * 58)
    print("  CRT DB Migráció v0.5 – Web scraping + Quotes")
    print("=" * 58)

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
            # Több utasítást tartalmazó SQL blokk darabolása
            for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
                cur.execute(stmt)
            conn.commit()
            print(f"  ✅  {name}")
            ok += 1
        except Exception as e:
            conn.rollback()
            print(f"  ❌  {name}: {e}")

    cur.close()
    conn.close()

    print(f"\n{'=' * 58}")
    print(f"  Migráció kész: {ok}/{len(STEPS)} lépés sikeres")
    print(f"{'=' * 58}")
    print()
    print("  Új táblák:")
    print("    web_sources  – nagykereskedői URL-ek, login adatok")
    print("    web_scripts  – Playwright lépések (Tanít gomb eredménye)")
    print("    web_prices   – weboldalakról begyűjtött árak")
    print("    quotes       – ajánlatok fejadata")
    print("    quote_lines  – ajánlat sorok AI cellajelzőkkel")
    print()
    print("  Következő lépés: py -3.11 -m uvicorn main:app --reload")


if __name__ == "__main__":
    run()
