"""
CRT Scraper – Alap osztály
Minden forrás-specifikus scraper ebből örökíti a közös logikát.
"""
import re, logging
from datetime import datetime
from sqlalchemy import create_engine, text
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env_detect import get_db_url

log    = logging.getLogger("CRT.scraper")
engine = create_engine(get_db_url(), pool_pre_ping=True, pool_size=2)


def parse_price(raw: str) -> float | None:
    """'1 234,50 Ft' → 1234.50 · '12.345,90' → 12345.90"""
    if not raw:
        return None
    cleaned = raw.replace('\xa0', '').replace(' ', '').replace('.', '').replace(',', '.')
    m = re.search(r'(\d+\.?\d*)', cleaned)
    return float(m.group(1)) if m else None


def save_price(source_id: int, raw_name: str, raw_price: float,
               unit: str = "db", manufacturer: str = None,
               supplier_code: str = None, url: str = None):
    """Egy ár mentése web_prices táblába."""
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO web_prices "
            "(source_id, raw_name, raw_price, currency, unit, "
            " manufacturer, url_detail, scraped_at) "
            "VALUES (:sid,:name,:price,'HUF',:unit,:mfr,:url,NOW())"
        ), {
            "sid":   source_id,
            "name":  raw_name[:500] if raw_name else "",
            "price": raw_price,
            "unit":  unit,
            "mfr":   manufacturer,
            "url":   url,
        })


def update_source_status(source_id: int, ok: bool, error: str = None):
    with engine.begin() as conn:
        if ok:
            conn.execute(text(
                "UPDATE web_sources SET status='reachable', last_scraped=NOW(), "
                "error_msg=NULL, updated_at=NOW() WHERE id=:id"
            ), {"id": source_id})
        else:
            conn.execute(text(
                "UPDATE web_sources SET status='error', "
                "error_msg=:err, updated_at=NOW() WHERE id=:id"
            ), {"id": source_id, "err": (error or "")[:500]})


def get_or_create_source(name: str, url: str, source_type: str = "public") -> int:
    """Web forrás lekérése vagy létrehozása, visszaadja az id-t."""
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT id FROM web_sources WHERE url=:url"
        ), {"url": url}).fetchone()
        if row:
            return row[0]
        r = conn.execute(text(
            "INSERT INTO web_sources (name,url,source_type,status,created_at) "
            "VALUES (:n,:u,:t,'new',NOW()) RETURNING id"
        ), {"n": name, "u": url, "t": source_type}).fetchone()
        return r[0]
