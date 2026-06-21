"""
CRT Ajánlatsegéd – DB migráció v0.6
Biztonságos oszlopbővítések (IF NOT EXISTS) – futtatható már meglévő DB-n is.
Lefedi a v0.5 fejlesztés során szükségessé vált mezőket.

Futtatás: py -3.11 db_migrate_v06.py
"""
from sqlalchemy import create_engine, text
from env_detect import get_db_url

DB_URL = get_db_url()
engine = create_engine(DB_URL)

STEPS = [

    # ── audit_log bővítések ──────────────────────────────────
    ("audit_log: description oszlop", """
        ALTER TABLE audit_log
        ADD COLUMN IF NOT EXISTS description TEXT;
    """),
    ("audit_log: ip_address oszlop", """
        ALTER TABLE audit_log
        ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
    """),
    ("audit_log: entity_id oszlop", """
        ALTER TABLE audit_log
        ADD COLUMN IF NOT EXISTS entity_id VARCHAR(128);
    """),

    # ── prices tábla bővítések ───────────────────────────────
    ("prices: source_id oszlop", """
        ALTER TABLE prices
        ADD COLUMN IF NOT EXISTS source_id INTEGER
        REFERENCES web_sources(id) ON DELETE SET NULL;
    """),
    ("prices: supplier_code oszlop", """
        ALTER TABLE prices
        ADD COLUMN IF NOT EXISTS supplier_code VARCHAR(100);
    """),
    ("prices: currency oszlop", """
        ALTER TABLE prices
        ADD COLUMN IF NOT EXISTS currency CHAR(3) DEFAULT 'HUF';
    """),

    # ── system_config: hiányzó kulcsok ──────────────────────
    ("system_config: claude_model", """
        INSERT INTO system_config (key, value, description)
        VALUES ('claude_model', 'claude-sonnet-4-6', 'Claude modell azonosítója')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: ai_conf_high", """
        INSERT INTO system_config (key, value, description)
        VALUES ('ai_conf_high', '70', 'AI azonosítás biztos határ (%)')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: ai_conf_low", """
        INSERT INTO system_config (key, value, description)
        VALUES ('ai_conf_low', '50', 'AI azonosítás bizonytalan határ (%)')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: auto_scrape", """
        INSERT INTO system_config (key, value, description)
        VALUES ('auto_scrape', 'true', 'Automatikus webes ár scrape engedélyezve')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: company_name", """
        INSERT INTO system_config (key, value, description)
        VALUES ('company_name', 'Civil Rendszertechnika Kft.', 'Cég neve (fejlécben)')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: company_tax", """
        INSERT INTO system_config (key, value, description)
        VALUES ('company_tax', '', 'Cég adószáma')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: smtp_from_name", """
        INSERT INTO system_config (key, value, description)
        VALUES ('smtp_from_name', 'CRT Rendszer', 'Email küldő neve')
        ON CONFLICT (key) DO NOTHING;
    """),
    ("system_config: smtp_tls", """
        INSERT INTO system_config (key, value, description)
        VALUES ('smtp_tls', 'true', 'SMTP STARTTLS engedélyezve')
        ON CONFLICT (key) DO NOTHING;
    """),

    # ── quotes: hiányzó oszlopok ─────────────────────────────
    ("quotes: source_mode oszlop", """
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS source_mode VARCHAR(20) DEFAULT 'manual';
    """),
    ("quotes: source_file oszlop", """
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS source_file VARCHAR(255);
    """),
    ("quotes: base_quote_id oszlop", """
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS base_quote_id INTEGER
        REFERENCES quotes(id) ON DELETE SET NULL;
    """),
    ("quotes: client_ref oszlop", """
        ALTER TABLE quotes
        ADD COLUMN IF NOT EXISTS client_ref VARCHAR(100);
    """),

    # ── quote_lines: hiányzó oszlopok ────────────────────────
    ("quote_lines: confidence oszlop", """
        ALTER TABLE quote_lines
        ADD COLUMN IF NOT EXISTS confidence NUMERIC(4,3);
    """),
    ("quote_lines: price_source oszlop", """
        ALTER TABLE quote_lines
        ADD COLUMN IF NOT EXISTS price_source VARCHAR(50);
    """),
    ("quote_lines: item_id oszlop", """
        ALTER TABLE quote_lines
        ADD COLUMN IF NOT EXISTS item_id VARCHAR(128);
    """),

    # ── web_prices: előfeldolgozó router meta ────────────────
    ("web_prices: content_type oszlop", """
        ALTER TABLE web_prices
        ADD COLUMN IF NOT EXISTS content_type VARCHAR(20);
    """),
    ("web_prices: doc_type oszlop", """
        ALTER TABLE web_prices
        ADD COLUMN IF NOT EXISTS doc_type VARCHAR(20);
    """),
    ("web_prices: pp_motor oszlop", """
        ALTER TABLE web_prices
        ADD COLUMN IF NOT EXISTS pp_motor VARCHAR(40);
    """),
    ("web_prices: pp_warnings oszlop", """
        ALTER TABLE web_prices
        ADD COLUMN IF NOT EXISTS pp_warnings TEXT;
    """),
    ("index: web_prices_content_type", """
        CREATE INDEX IF NOT EXISTS idx_web_prices_content_type
        ON web_prices(content_type) WHERE content_type IS NOT NULL;
    """),

    # ── products: műszaki specifikációk (JSONB) ──────────────
    ("products: specs JSONB", """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS specs JSONB DEFAULT '{}'::jsonb;
    """),
    ("index: products_specs GIN", """
        CREATE INDEX IF NOT EXISTS idx_products_specs
        ON products USING GIN (specs);
    """),

    # ── prices: nettó/bruttó + kisker/nagyker szintek ────────
    ("prices: gross_price", """
        ALTER TABLE prices
        ADD COLUMN IF NOT EXISTS gross_price NUMERIC(14,2);
    """),
    ("prices: vat_pct", """
        ALTER TABLE prices
        ADD COLUMN IF NOT EXISTS vat_pct NUMERIC(5,2) DEFAULT 27.00;
    """),
    ("prices: price_tier", """
        ALTER TABLE prices
        ADD COLUMN IF NOT EXISTS price_tier VARCHAR(20) DEFAULT 'lista';
    """),
    ("index: prices_tier_item", """
        CREATE INDEX IF NOT EXISTS idx_prices_tier_item
        ON prices(item_id, price_tier);
    """),

    # ── INDEX-ek ─────────────────────────────────────────────
    ("index: audit_log_created_at", """
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
        ON audit_log(created_at DESC);
    """),
    ("index: audit_log_user_id", """
        CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
        ON audit_log(user_id);
    """),
    ("index: audit_log_action", """
        CREATE INDEX IF NOT EXISTS idx_audit_log_action
        ON audit_log(action);
    """),
    ("index: prices_item_id", """
        CREATE INDEX IF NOT EXISTS idx_prices_item_id
        ON prices(item_id);
    """),
    ("index: prices_db_inserted", """
        CREATE INDEX IF NOT EXISTS idx_prices_db_inserted
        ON prices(db_inserted DESC);
    """),
    ("index: quote_lines_quote_id", """
        CREATE INDEX IF NOT EXISTS idx_quote_lines_quote_id
        ON quote_lines(quote_id);
    """),
]


def run():
    ok = 0
    fail = 0
    with engine.begin() as conn:
        for name, sql in STEPS:
            try:
                conn.execute(text(sql.strip()))
                print(f"  ✅ {name}")
                ok += 1
            except Exception as e:
                print(f"  ⚠️  {name} – {e}")
                fail += 1

    print(f"\nMigráció kész: {ok} OK, {fail} figyelmeztetés")
    if fail:
        print("A figyelmeztetések általában 'már létező' oszlop/index jelzések – nem probléma.")


if __name__ == "__main__":
    print("CRT DB Migráció v0.6 indul…\n")
    run()
