"""
CRT Ajánlatsegéd – Quotes router v0.5
Ajánlatok (quotes) + sorok (quote_lines) CRUD
prefix: /quotes
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from typing import Optional
import logging
import uuid

from auth import require_auth
from env_detect import get_db_url

router = APIRouter(prefix="/quotes", tags=["quotes"])
log    = logging.getLogger("CRT.quotes")

DB_URL = get_db_url()
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=3)

CET  = timezone(timedelta(hours=1))
CEST = timezone(timedelta(hours=2))

def local_now():
    utc = datetime.utcnow()
    tz  = CEST if 3 <= utc.month <= 10 else CET
    return utc.replace(tzinfo=timezone.utc).astimezone(tz)


# ── MODELLEK ──────────────────────────────────────────────────

class QuoteCreate(BaseModel):
    title:        Optional[str] = None
    client_name:  Optional[str] = None
    client_ref:   Optional[str] = None
    source_file:  Optional[str] = None
    source_mode:  str           = "manual"    # upload | manual | copy
    base_quote_id:Optional[int] = None
    valid_days:   int           = 30
    notes:        Optional[str] = None

class QuoteUpdate(BaseModel):
    title:       Optional[str] = None
    client_name: Optional[str] = None
    client_ref:  Optional[str] = None
    status:      Optional[str] = None   # draft|sent|accepted|rejected|expired
    notes:       Optional[str] = None
    valid_until: Optional[str] = None   # ISO date string

class LineCreate(BaseModel):
    line_no:     int
    item_type:   str           = "product"    # product|activity|manual|skip
    item_id:     Optional[str] = None         # UUID string
    raw_name:    Optional[str] = None
    name:        Optional[str] = None
    manufacturer:Optional[str] = None
    quantity:    float         = 1.0
    unit:        Optional[str] = None
    unit_price:  Optional[float] = None
    currency:    str           = "HUF"
    confidence:  Optional[float] = None
    cell_status: str           = "raw"
    price_source:Optional[str] = None
    notes:       Optional[str] = None

class LineUpdate(BaseModel):
    name:         Optional[str]   = None
    manufacturer: Optional[str]   = None
    quantity:     Optional[float] = None
    unit:         Optional[str]   = None
    unit_price:   Optional[float] = None
    currency:     Optional[str]   = None
    cell_status:  Optional[str]   = None
    price_source: Optional[str]   = None
    notes:        Optional[str]   = None


# ── SEGÉD ─────────────────────────────────────────────────────

def _row2dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
    return d


def _next_quote_number(conn) -> str:
    """Egyedi ajánlatszám: CRT-YYYY-NNNN"""
    year = local_now().year
    row = conn.execute(text(
        "SELECT COUNT(*) FROM quotes "
        "WHERE EXTRACT(YEAR FROM created_at) = :yr"
    ), {"yr": year}).fetchone()
    seq = (row[0] or 0) + 1
    return f"CRT-{year}-{seq:04d}"


# ── LISTÁK ────────────────────────────────────────────────────

@router.get("/")
async def list_quotes(
    status:      Optional[str] = None,
    client_name: Optional[str] = None,
    limit:       int           = 50,
    offset:      int           = 0,
    payload: dict = Depends(require_auth)
):
    conditions, params = [], {"limit": min(limit, 200), "offset": offset}
    if status:
        conditions.append("status=:status")
        params["status"] = status
    if client_name:
        conditions.append("LOWER(client_name) LIKE LOWER(:cn)")
        params["cn"] = f"%{client_name}%"
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT id, quote_number, title, client_name, client_ref, "
            f"status, source_mode, valid_until, created_at, updated_at "
            f"FROM quotes {where} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ), params).fetchall()

        total = conn.execute(text(
            f"SELECT COUNT(*) FROM quotes {where}"
        ), {k: v for k, v in params.items() if k not in ('limit', 'offset')}).fetchone()[0]

    return {
        "quotes": [_row2dict(r) for r in rows],
        "total":  total,
        "offset": offset,
        "limit":  min(limit, 200),
    }


@router.get("/{quote_id}")
async def get_quote(quote_id: int, payload: dict = Depends(require_auth)):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT * FROM quotes WHERE id=:id"
        ), {"id": quote_id}).fetchone()
    if not row:
        raise HTTPException(404, "Ajánlat nem található")
    return _row2dict(row)


# ── LÉTREHOZÁS ────────────────────────────────────────────────

@router.post("/")
async def create_quote(body: QuoteCreate, payload: dict = Depends(require_auth)):
    now         = local_now()
    valid_until = now + timedelta(days=body.valid_days)

    try:
        with engine.begin() as conn:
            q_num = _next_quote_number(conn)
            row = conn.execute(text(
                "INSERT INTO quotes "
                "(quote_number, title, client_name, client_ref, status, "
                " source_file, source_mode, base_quote_id, valid_until, "
                " notes, created_by, created_at, updated_at) "
                "VALUES (:qn,:title,:cn,:cr,'draft',:sf,:sm,:bq,:vu,"
                "        :notes,:uid,:now,:now) "
                "RETURNING id"
            ), {
                "qn":    q_num,
                "title": body.title,
                "cn":    body.client_name,
                "cr":    body.client_ref,
                "sf":    body.source_file,
                "sm":    body.source_mode,
                "bq":    body.base_quote_id,
                "vu":    valid_until,
                "notes": body.notes,
                "uid":   payload["user_id"],
                "now":   now,
            }).fetchone()

        log.info("Új ajánlat: %s (id=%d, user=%s)", q_num, row[0], payload["username"])
        return {"status": "ok", "id": row[0], "quote_number": q_num}

    except Exception as e:
        raise HTTPException(500, f"Létrehozási hiba: {e}")


# ── MÓDOSÍTÁS / TÖRLÉS ────────────────────────────────────────

@router.patch("/{quote_id}")
async def update_quote(quote_id: int, body: QuoteUpdate,
                       payload: dict = Depends(require_auth)):
    updates, params = ["updated_at=NOW()"], {"id": quote_id}
    if body.title       is not None: updates.append("title=:title");            params["title"]  = body.title
    if body.client_name is not None: updates.append("client_name=:cn");         params["cn"]     = body.client_name
    if body.client_ref  is not None: updates.append("client_ref=:cr");          params["cr"]     = body.client_ref
    if body.status      is not None: updates.append("status=:status");          params["status"] = body.status
    if body.notes       is not None: updates.append("notes=:notes");            params["notes"]  = body.notes
    if body.valid_until is not None: updates.append("valid_until=:vu::timestamp"); params["vu"]   = body.valid_until

    if len(updates) == 1:
        raise HTTPException(400, "Nincs módosítandó adat")

    with engine.begin() as conn:
        conn.execute(text(
            f"UPDATE quotes SET {', '.join(updates)} WHERE id=:id"
        ), params)
    return {"status": "ok"}


@router.delete("/{quote_id}")
async def delete_quote(quote_id: int, payload: dict = Depends(require_auth)):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM quotes WHERE id=:id"), {"id": quote_id})
    log.info("Ajánlat törölve: id=%d (user=%s)", quote_id, payload["username"])
    return {"status": "ok"}


# ── SOROK ─────────────────────────────────────────────────────

@router.get("/{quote_id}/lines")
async def get_lines(quote_id: int, payload: dict = Depends(require_auth)):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT * FROM quote_lines WHERE quote_id=:qid ORDER BY line_no"
        ), {"qid": quote_id}).fetchall()
    return {"lines": [_row2dict(r) for r in rows]}


@router.post("/{quote_id}/lines")
async def add_line(quote_id: int, body: LineCreate,
                   payload: dict = Depends(require_auth)):
    try:
        with engine.begin() as conn:
            row = conn.execute(text(
                "INSERT INTO quote_lines "
                "(quote_id, line_no, item_type, item_id, raw_name, name, "
                " manufacturer, quantity, unit, unit_price, "
                " total_price, currency, confidence, cell_status, "
                " price_source, notes) "
                "VALUES (:qid,:lno,:itype,:iid,:rname,:name,"
                "        :mfr,:qty,:unit,:uprice,"
                "        CASE WHEN :uprice IS NOT NULL AND :qty IS NOT NULL "
                "             THEN :uprice * :qty ELSE NULL END,"
                "        :cur,:conf,:cstat,:psrc,:notes) "
                "RETURNING id"
            ), {
                "qid":   quote_id,
                "lno":   body.line_no,
                "itype": body.item_type,
                "iid":   body.item_id,
                "rname": body.raw_name,
                "name":  body.name,
                "mfr":   body.manufacturer,
                "qty":   body.quantity,
                "unit":  body.unit,
                "uprice":body.unit_price,
                "cur":   body.currency,
                "conf":  body.confidence,
                "cstat": body.cell_status,
                "psrc":  body.price_source,
                "notes": body.notes,
            }).fetchone()
        return {"status": "ok", "id": row[0]}
    except Exception as e:
        raise HTTPException(500, f"Sor hozzáadási hiba: {e}")


@router.post("/{quote_id}/lines/bulk")
async def bulk_add_lines(quote_id: int, body: dict,
                         payload: dict = Depends(require_auth)):
    """Több sor egyszerre — feltöltés utáni tömegbetöltés."""
    lines = body.get("lines", [])
    if not lines:
        return {"saved": 0}

    saved = 0
    try:
        with engine.begin() as conn:
            # Meglévő sorok törlése ha replace=true
            if body.get("replace", False):
                conn.execute(text(
                    "DELETE FROM quote_lines WHERE quote_id=:qid"
                ), {"qid": quote_id})

            for i, line in enumerate(lines):
                qty    = float(line.get("quantity", 1) or 1)
                uprice = line.get("unit_price")
                uprice = float(uprice) if uprice is not None else None
                conn.execute(text(
                    "INSERT INTO quote_lines "
                    "(quote_id, line_no, item_type, item_id, raw_name, name, "
                    " manufacturer, quantity, unit, unit_price, total_price, "
                    " currency, confidence, cell_status, price_source, notes) "
                    "VALUES (:qid,:lno,:itype,:iid,:rname,:name,"
                    "        :mfr,:qty,:unit,:uprice,"
                    "        CASE WHEN :uprice IS NOT NULL THEN :uprice*:qty ELSE NULL END,"
                    "        :cur,:conf,:cstat,:psrc,:notes)"
                ), {
                    "qid":   quote_id,
                    "lno":   line.get("line_no", i + 1),
                    "itype": line.get("item_type", "manual"),
                    "iid":   line.get("item_id"),
                    "rname": line.get("raw_name"),
                    "name":  line.get("name"),
                    "mfr":   line.get("manufacturer"),
                    "qty":   qty,
                    "unit":  line.get("unit"),
                    "uprice":uprice,
                    "cur":   line.get("currency", "HUF"),
                    "conf":  line.get("confidence"),
                    "cstat": line.get("cell_status", "raw"),
                    "psrc":  line.get("price_source"),
                    "notes": line.get("notes"),
                })
                saved += 1

            # Ajánlat updated_at frissítése
            conn.execute(text(
                "UPDATE quotes SET updated_at=NOW() WHERE id=:id"
            ), {"id": quote_id})

        log.info("Bulk sorok betöltve: ajánlat=%d sorok=%d", quote_id, saved)
        return {"saved": saved}

    except Exception as e:
        raise HTTPException(500, f"Tömeg-betöltési hiba: {e}")


@router.patch("/{quote_id}/lines/{line_id}")
async def update_line(quote_id: int, line_id: int, body: LineUpdate,
                      payload: dict = Depends(require_auth)):
    updates, params = [], {"id": line_id, "qid": quote_id}
    if body.name         is not None: updates.append("name=:name");          params["name"]   = body.name
    if body.manufacturer is not None: updates.append("manufacturer=:mfr");   params["mfr"]    = body.manufacturer
    if body.quantity     is not None: updates.append("quantity=:qty");       params["qty"]    = body.quantity
    if body.unit         is not None: updates.append("unit=:unit");          params["unit"]   = body.unit
    if body.unit_price   is not None: updates.append("unit_price=:uprice");  params["uprice"] = body.unit_price
    if body.currency     is not None: updates.append("currency=:cur");       params["cur"]    = body.currency
    if body.cell_status  is not None: updates.append("cell_status=:cstat");  params["cstat"]  = body.cell_status
    if body.price_source is not None: updates.append("price_source=:psrc");  params["psrc"]   = body.price_source
    if body.notes        is not None: updates.append("notes=:notes");        params["notes"]  = body.notes

    # total_price újraszámolás ha quantity vagy unit_price változott
    if body.quantity is not None or body.unit_price is not None:
        updates.append(
            "total_price = CASE WHEN unit_price IS NOT NULL AND quantity IS NOT NULL "
            "THEN unit_price * quantity ELSE NULL END"
        )

    if not updates:
        raise HTTPException(400, "Nincs módosítandó adat")

    with engine.begin() as conn:
        conn.execute(text(
            f"UPDATE quote_lines SET {', '.join(updates)} "
            f"WHERE id=:id AND quote_id=:qid"
        ), params)
        conn.execute(text(
            "UPDATE quotes SET updated_at=NOW() WHERE id=:qid"
        ), {"qid": quote_id})
    return {"status": "ok"}


@router.delete("/{quote_id}/lines/{line_id}")
async def delete_line(quote_id: int, line_id: int,
                      payload: dict = Depends(require_auth)):
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM quote_lines WHERE id=:id AND quote_id=:qid"
        ), {"id": line_id, "qid": quote_id})
    return {"status": "ok"}


# ── ÖSSZESÍTÉS ────────────────────────────────────────────────

@router.get("/{quote_id}/summary")
async def quote_summary(quote_id: int, payload: dict = Depends(require_auth)):
    """Ajánlat összesítő — sorok száma, cellástátusz eloszlás, végösszeg."""
    with engine.connect() as conn:
        quote = conn.execute(text(
            "SELECT quote_number, title, client_name, status, valid_until "
            "FROM quotes WHERE id=:id"
        ), {"id": quote_id}).fetchone()
        if not quote:
            raise HTTPException(404, "Ajánlat nem található")

        stats = conn.execute(text(
            "SELECT cell_status, COUNT(*) as cnt, "
            "SUM(COALESCE(total_price,0)) as total "
            "FROM quote_lines WHERE quote_id=:id "
            "GROUP BY cell_status"
        ), {"id": quote_id}).fetchall()

        grand = conn.execute(text(
            "SELECT COUNT(*), SUM(COALESCE(total_price,0)) "
            "FROM quote_lines WHERE quote_id=:id"
        ), {"id": quote_id}).fetchone()

    status_dist = {r[0]: {"count": r[1], "total": float(r[2] or 0)} for r in stats}

    return {
        "quote_number": quote[0],
        "title":        quote[1],
        "client_name":  quote[2],
        "status":       quote[3],
        "valid_until":  quote[4].isoformat() if quote[4] else None,
        "line_count":   grand[0],
        "grand_total":  float(grand[1] or 0),
        "currency":     "HUF",
        "status_dist":  status_dist,
    }
