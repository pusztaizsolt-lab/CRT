"""
CRT Ajanlatseged - Adatbazis Schema v1.0
Letrehozza az alap tablakat (users, products, prices, stb.)
A quotes, quote_lines, web_*, golden_examples, chroma_index, lora_jobs
tablakat a v05/v07/v08 migraciok hozzak letre.

Futtatás: py -3.11 db_schema.py
"""
from sqlalchemy import (
    create_engine, text,
    Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, ARRAY
)
from sqlalchemy.orm import declarative_base
import os
import logging
from env_detect import get_db_url

DB_URL = get_db_url()
engine = create_engine(DB_URL, echo=False)
Base   = declarative_base()
log    = logging.getLogger("CRT.schema")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# -- USERS ---------------------------------------------------------
# Modern schema: id SERIAL PK, username VARCHAR UNIQUE
# (regi user_id VARCHAR PK schema mar nem hasznalt)

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer,     primary_key=True, autoincrement=True)
    username      = Column(String(100), unique=True, nullable=False)
    pin_hash      = Column(String(128), nullable=False)
    email         = Column(String(255))
    role          = Column(String(20),  nullable=False, default="user")
    active        = Column(Boolean,     nullable=False, default=True)
    created_at    = Column(DateTime,    nullable=False)
    last_login    = Column(DateTime)
    locked_until  = Column(DateTime)
    attempt_count = Column(Integer,     nullable=False, default=0)

# -- AUDIT LOG -----------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"
    log_id       = Column(String(36),  primary_key=True)
    user_id      = Column(String(36),  nullable=False)
    action       = Column(String(100), nullable=False)
    target       = Column(String(200))
    detail       = Column(Text)
    description  = Column(Text)
    entity_id    = Column(String(128))
    timestamp    = Column(DateTime,    nullable=False)
    ip_address   = Column(String(45))
    ip           = Column(String(50))

# -- CATEGORIES ----------------------------------------------------
class Category(Base):
    __tablename__ = "categories"
    category_id  = Column(String(36),  primary_key=True)
    parent_id    = Column(String(36),  ForeignKey("categories.category_id"), nullable=True)
    name         = Column(String(100), nullable=False)
    item_class   = Column(String(20),  default="materialis")
    sort_order   = Column(Integer,     default=0)
    active       = Column(Boolean,     default=True)

# -- PRODUCTS ------------------------------------------------------
class Product(Base):
    __tablename__ = "products"
    item_id       = Column(String(36),  primary_key=True)
    crt_code      = Column(String(20),  unique=True)
    supplier_code = Column(String(100))
    model         = Column(String(100))
    category_id   = Column(String(36),  ForeignKey("categories.category_id"))
    name          = Column(String(200), nullable=False)
    description   = Column(Text)
    unit          = Column(String(20))
    item_class    = Column(String(20),  default="materialis")
    active        = Column(Boolean,     default=True)
    created_at    = Column(DateTime,    nullable=False)
    updated_at    = Column(DateTime)
    tags          = Column(Text)

# -- ACTIVITIES ----------------------------------------------------
class Activity(Base):
    __tablename__ = "activities"
    item_id       = Column(String(36),  primary_key=True)
    crt_code      = Column(String(20),  unique=True)
    category_id   = Column(String(36),  ForeignKey("categories.category_id"))
    name          = Column(String(200), nullable=False)
    description   = Column(Text)
    unit          = Column(String(20))
    active        = Column(Boolean,     default=True)
    created_at    = Column(DateTime,    nullable=False)
    updated_at    = Column(DateTime)

# -- PRICES --------------------------------------------------------
class Price(Base):
    __tablename__ = "prices"
    price_id     = Column(String(36),  primary_key=True)
    item_id      = Column(String(36),  nullable=False)
    item_class   = Column(String(20))
    price_type   = Column(String(20),  default="lista")
    net_price    = Column(Float)
    currency     = Column(String(3),   default="HUF")
    source_id    = Column(Integer)
    supplier_code= Column(String(100))
    valid_from   = Column(DateTime)
    valid_to     = Column(DateTime)
    db_inserted  = Column(DateTime,    nullable=False)
    source       = Column(String(50))
    notes        = Column(Text)

# -- SUPPLIERS -----------------------------------------------------
class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id  = Column(String(36),  primary_key=True)
    name         = Column(String(200), nullable=False)
    contact_name = Column(String(100))
    email        = Column(String(200))
    phone        = Column(String(50))
    notes        = Column(Text)
    active       = Column(Boolean,     default=True)
    created_at   = Column(DateTime)

# -- CONNECTIONS ---------------------------------------------------
class Connection(Base):
    __tablename__ = "connections"
    conn_id      = Column(String(36),  primary_key=True)
    product_id   = Column(String(36))
    activity_id  = Column(String(36))
    relation     = Column(String(50))
    notes        = Column(Text)

# -- TENDERS -------------------------------------------------------
class Tender(Base):
    __tablename__ = "tenders"
    tender_id    = Column(String(36),  primary_key=True)
    category     = Column(String(100))
    winning_price= Column(Float)
    submitted_price = Column(Float)
    tender_date  = Column(DateTime)
    result       = Column(String(20))
    has_detail   = Column(Boolean,     default=False)
    notes        = Column(Text)

# -- RECYCLE BIN ---------------------------------------------------
class RecycleBin(Base):
    __tablename__ = "recycle_bin"
    recycle_id   = Column(String(36),  primary_key=True)
    item_type    = Column(String(50),  nullable=False)
    item_id      = Column(String(36),  nullable=False)
    data_json    = Column(Text,        nullable=False)
    deleted_by   = Column(String(36),  nullable=False)
    deleted_at   = Column(DateTime,    nullable=False)
    restored     = Column(Boolean,     default=False)

# -- SYSTEM CONFIG -------------------------------------------------
class SystemConfig(Base):
    __tablename__ = "system_config"
    key          = Column(String(100), primary_key=True)
    value        = Column(Text)
    description  = Column(Text)
    encrypted    = Column(Boolean,     default=False)
    updated_by   = Column(String(36))
    updated_at   = Column(DateTime)

# -- LETREHOZAS ----------------------------------------------------
def create_schema():
    print("\nCRT - Adatbazis Schema v1.0 Letrehozo\n")

    base_tables = [
        "users", "audit_log", "categories",
        "products", "activities", "prices",
        "suppliers", "connections", "tenders",
        "recycle_bin", "system_config"
    ]

    print("  Tablak letrehozasa...\n")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        for table in base_tables:
            result = conn.execute(text(
                f"SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_name='{table}'"
            ))
            exists = result.scalar() > 0
            print(f"  {'OK' if exists else 'HIBA'}  {table}")

    print(f"\n  Schema kesz! {len(base_tables)} alaptabla.\n")
    print("  Kovetkezo lepes: migrate.bat (v04 -> v08)\n")

if __name__ == "__main__":
    create_schema()
