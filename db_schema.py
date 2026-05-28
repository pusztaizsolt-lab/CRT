"""
CRT Ajánlatsegéd – Adatbázis Séma v0.1
Futtasd: py -3.11 db_schema.py
Létrehozza az összes táblát a crt adatbázisban
"""
from sqlalchemy import (
    create_engine, text,
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid
import logging

# ── KONFIG ────────────────────────────────────────────────
DB_URL = "postgresql://crt_user:crt2026@localhost:5432/crt"
engine = create_engine(DB_URL, echo=False)
Base   = declarative_base()
log    = logging.getLogger("CRT.schema")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ── TÁBLÁK ────────────────────────────────────────────────

class User(Base):
    """Felhasználók – PIN kód, jogosultság"""
    __tablename__ = "users"
    user_id      = Column(String(16),  primary_key=True)
    pin_hash     = Column(String(128), nullable=False)
    role         = Column(String(20),  default="user")   # user / admin
    created_at   = Column(DateTime,    nullable=False)
    last_login   = Column(DateTime)
    active       = Column(Boolean,     default=True)

class AuditLog(Base):
    """Audit napló – minden művelet"""
    __tablename__ = "audit_log"
    log_id       = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String(16),  nullable=False)
    action       = Column(String(100), nullable=False)
    target       = Column(String(200))
    detail       = Column(Text)
    timestamp    = Column(DateTime,    nullable=False)
    ip           = Column(String(50))

class Category(Base):
    """Kategória fa – hierarchikus"""
    __tablename__ = "categories"
    category_id  = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id    = Column(String(36),  ForeignKey("categories.category_id"), nullable=True)
    name         = Column(String(100), nullable=False)
    item_class   = Column(String(20),  default="materiális")  # materiális / immateriális
    sort_order   = Column(Integer,     default=0)
    active       = Column(Boolean,     default=True)

class Product(Base):
    """Cikktörzs – materiális termékek"""
    __tablename__ = "products"
    item_id       = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    crt_code      = Column(String(20),  unique=True)               # CRT-P-000001
    supplier_code = Column(String(100))                            # kereskedői kód (pl. KKM-12)
    manufacturer  = Column(String(100))                            # gyártó (pl. Paradox)
    model         = Column(String(100))                            # típus neve (pl. MG-5050)
    name          = Column(String(200), nullable=False)            # teljes megnevezés
    category_id   = Column(String(36),  ForeignKey("categories.category_id"))
    unit          = Column(String(20),  default="db")
    software_flag = Column(Boolean,     default=False)
    version       = Column(Integer,     default=1)
    status        = Column(String(20),  default="active")          # active / invalidated / recycled
    created_at    = Column(DateTime,    nullable=False)
    created_by    = Column(String(16))

class Activity(Base):
    """Tevékenységi törzs – immateriális munkák"""
    __tablename__ = "activities"
    activity_id  = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    crt_code     = Column(String(20),  unique=True)                # CRT-A-000001
    name         = Column(String(200), nullable=False)
    category_id  = Column(String(36),  ForeignKey("categories.category_id"))
    unit_type    = Column(String(20),  default="óra")              # óra / nap / méter / db
    version      = Column(Integer,     default=1)
    status       = Column(String(20),  default="active")
    created_at   = Column(DateTime,    nullable=False)
    created_by   = Column(String(16))

class Price(Base):
    """Árnapló – típus + minőségi szint"""
    __tablename__ = "prices"
    price_id     = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id      = Column(String(36),  nullable=False)             # → product vagy activity
    item_class   = Column(String(20),  nullable=False)             # materiális / immateriális
    price_type   = Column(String(20),  default="lista")            # lista / kisker / nagyker / egyedi
    price        = Column(Float,       nullable=False)
    currency     = Column(String(5),   default="HUF")
    unit         = Column(String(20))
    supplier     = Column(String(100))
    source_type  = Column(String(30))  # file_upload / web_auth / web_public / partner_api / manual / editor
    source_url   = Column(String(500))
    confidence   = Column(Float,       default=1.0)
    db_level     = Column(String(20),  default="db1_raw")          # db1_raw / db2_refined / db_master
    offer_date   = Column(DateTime)
    db_inserted  = Column(DateTime,    nullable=False)
    user_id      = Column(String(16))
    version      = Column(Integer,     default=1)
    status       = Column(String(20),  default="active")

class Supplier(Base):
    """Beszállítók / forgalmazók"""
    __tablename__ = "suppliers"
    supplier_id  = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    name         = Column(String(100), nullable=False)
    contact      = Column(String(200))
    api_url      = Column(String(500))
    last_sync    = Column(DateTime)
    active       = Column(Boolean,     default=True)

class Connection(Base):
    """Kapcsolatok – URL lista, API kulcsok"""
    __tablename__ = "connections"
    conn_id      = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    name         = Column(String(100), nullable=False)
    url          = Column(String(500))
    url_type     = Column(String(30),  default="preferred_wholesale")
    credentials  = Column(Text)        # AES-256 titkosítva
    category     = Column(String(100))
    active       = Column(Boolean,     default=True)
    last_sync    = Column(DateTime)
    created_by   = Column(String(16))

class Quote(Base):
    """Ajánlat dokumentumok"""
    __tablename__ = "quotes"
    quote_id     = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id  = Column(String(50))
    requester    = Column(String(100))
    supplier     = Column(String(100))
    offer_date   = Column(DateTime)
    db_inserted  = Column(DateTime,    nullable=False)
    status       = Column(String(20),  default="draft")  # draft / exported / winning / losing
    total        = Column(Float)
    total_material  = Column(Float,    default=0)
    total_activity  = Column(Float,    default=0)
    prepared_by  = Column(String(16))
    notes        = Column(Text)

class QuoteCell(Base):
    """Ajánlat tételek"""
    __tablename__ = "quote_cells"
    cell_id      = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    quote_id     = Column(String(36),  ForeignKey("quotes.quote_id"), nullable=False)
    item_id      = Column(String(36),  nullable=False)
    item_class   = Column(String(20))  # materiális / immateriális
    item_name    = Column(String(200))
    quantity     = Column(Float,       default=1)
    unit         = Column(String(20))
    unit_price   = Column(Float)
    total_price  = Column(Float)
    source       = Column(String(30))
    confidence   = Column(Float)
    age_days     = Column(Integer)
    cell_status  = Column(String(20))  # green / yellow / red / web

class Tender(Base):
    """Pályázati historikus adatok"""
    __tablename__ = "tenders"
    tender_id    = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    category     = Column(String(100))
    winning_price= Column(Float)
    submitted_price = Column(Float)
    tender_date  = Column(DateTime)
    result       = Column(String(20))  # winning / losing
    has_detail   = Column(Boolean,     default=False)
    notes        = Column(Text)

class GoldenExample(Base):
    """Arany Példatár – LoRA tanítóadat"""
    __tablename__ = "golden_examples"
    example_id   = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_text     = Column(Text,        nullable=False)   # eredeti bizonytalan szöveg
    correct_json = Column(Text,        nullable=False)   # helyes JSON válasz
    source       = Column(String(30))  # human / claude / gemini
    confidence   = Column(Float)
    created_at   = Column(DateTime,    nullable=False)
    created_by   = Column(String(16))
    used_in_lora = Column(Boolean,     default=False)

class RecycleBin(Base):
    """Kuka – soft delete"""
    __tablename__ = "recycle_bin"
    recycle_id   = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    item_type    = Column(String(50),  nullable=False)   # product / activity / price / ...
    item_id      = Column(String(36),  nullable=False)
    data_json    = Column(Text,        nullable=False)   # teljes rekord JSON-ban
    deleted_by   = Column(String(16),  nullable=False)
    deleted_at   = Column(DateTime,    nullable=False)
    restored     = Column(Boolean,     default=False)

class SystemConfig(Base):
    """Rendszer beállítások – konzol kód, NTP, stb."""
    __tablename__ = "system_config"
    key          = Column(String(100), primary_key=True)
    value        = Column(Text)
    encrypted    = Column(Boolean,     default=False)
    updated_by   = Column(String(16))
    updated_at   = Column(DateTime)

# ── LÉTREHOZÁS ────────────────────────────────────────────
def create_schema():
    print("\n╔══════════════════════════════════════════╗")
    print("║   CRT – Adatbázis Séma Létrehozó v0.1   ║")
    print("╚══════════════════════════════════════════╝\n")

    tables = [
        "users", "audit_log", "categories",
        "products", "activities", "prices",
        "suppliers", "connections", "quotes",
        "quote_cells", "tenders", "golden_examples",
        "recycle_bin", "system_config"
    ]

    print("  Táblák létrehozása...\n")
    Base.metadata.create_all(engine)

    # Ellenőrzés
    with engine.connect() as conn:
        for table in tables:
            result = conn.execute(text(
                f"SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_name='{table}'"
            ))
            exists = result.scalar() > 0
            print(f"  {'✅' if exists else '❌'}  {table}")

    print(f"\n  🎉 Séma kész! {len(tables)} tábla létrehozva.\n")

if __name__ == "__main__":
    create_schema()
