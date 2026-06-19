"""
CRT Ajánlatsegéd – Ár API v0.5
Prefix: /prices
Árszintek: lista / kisker / nagyker / egyedi
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import create_engine, text
from auth import require_auth
from datetime import datetime, timezone, timedelta
import logging
from env_detect import get_db_url

router = APIRouter(prefix="/prices", tags=["prices"])
log    = logging.getLogger("CRT.prices")

DB_URL = get_db_url()
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=3)


def _row2dict(r):
    d = dict(r._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _age_status(inserted) -> str:
    """Visszaadja az ár frissességét: fresh / warn / old"""
    if not inserted:
        return "unknown"
    try:
        age_days = (datetime.utcnow() - inserted).days
    except Exception:
        return "unknown"
    if age_days <= 7:
        return "fresh"
    if age_days <= 30:
        return "warn"
    return "old"


# ── LISTA ENDPOINT ────────────────────────────────────────────

@router.get("/")
async def list_prices(
    item_id:    str  = Query(None, description="Termék/tevékenység ID (UUID)"),
    q:          str  = Query("",   description="Névben keres"),
    price_type: str  = Query("",   description="lista|kisker|nagyker|egyedi"),
    source_id:  int  = Query(None, description="Web forrás ID"),
    fresh_only: bool = Query(False,description="Csak ≤30 napos árak"),
    limit:      int  = Query(50,   ge=1, le=500),
    offset:     int  = Query(0,    ge=0),
    _auth: dict = Depends(require_auth),
):
    """Árlista lekérdezés – szűrhető termék, típus, forrás szerint"""
    conditions, params = [], {}

    if item_id:
        conditions.append("pr.item_id = :item_id")
        params["item_id"] = item_id
    if q:
        conditions.append(
            "(LOWER(COALESCE(p.name,'')) LIKE LOWER(:q) "
            "OR LOWER(COALESCE(a.name,'')) LIKE LOWER(:q))"
        )
        params["q"] = f"%{q}%"
    if price_type:
        conditions.append("pr.price_type = :price_type")
        params["price_type"] = price_type
    if source_id is not None:
        conditions.append("pr.source_id = :source_id")
        params["source_id"] = source_id
    if fresh_only:
        conditions.append("pr.db_inserted >= NOW() - INTERVAL '30 days'")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.update({"limit": limit, "offset": offset})

    sql = f"""
        SELECT
            pr.price_id AS id,
            pr.item_id,
            COALESCE(p.name, a.name, pr.item_id::text) AS item_name,
            CASE WHEN p.item_id IS NOT NULL THEN 'termék' ELSE 'tevékenység' END AS item_type,
            COALESCE(p.unit, a.unit, 'db') AS unit,
            pr.price_type,
            pr.net_price AS price,
            pr.currency,
            pr.source_id,
            ws.name AS source_name,
            pr.db_inserted,
            pr.supplier_code
        FROM prices pr
        LEFT JOIN products   p  ON p.item_id  = pr.item_id
        LEFT JOIN activities a  ON a.item_id  = pr.item_id
        LEFT JOIN web_sources ws ON ws.id = pr.source_id
        {where}
        ORDER BY pr.db_inserted DESC
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*)
        FROM prices pr
        LEFT JOIN products   p  ON p.item_id  = pr.item_id
        LEFT JOIN activities a  ON a.item_id  = pr.item_id
        LEFT JOIN web_sources ws ON ws.id = pr.source_id
        {where}
    """

    try:
        with engine.connect() as conn:
            total = conn.execute(text(count_sql), params).fetchone()[0]
            rows  = conn.execute(text(sql), params).fetchall()

        result = []
        for r in rows:
            d = _row2dict(r)
            d["age_status"] = _age_status(r._mapping.get("db_inserted"))
            result.append(d)

        return {"prices": result, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {e}")


# ── LEGOLCSÓBB ÁR TERMÉKHEZ ───────────────────────────────────

@router.get("/best/{item_id}")
async def best_price(
    item_id:    str,
    price_type: str = Query("", description="Ha üres: összes típus"),
    _auth: dict = Depends(require_auth),
):
    """Legjobb (legolcsóbb) ár egy termékhez – frissesség szerinti sorrend"""
    params: dict = {"item_id": item_id}
    type_clause = "AND pr.price_type = :price_type" if price_type else ""
    if price_type:
        params["price_type"] = price_type

    sql = f"""
        SELECT
            pr.price_id AS id, pr.item_id, pr.price_type, pr.net_price AS price, pr.currency,
            pr.source_id, ws.name AS source_name,
            pr.db_inserted, pr.supplier_code,
            COALESCE(p.name, a.name) AS item_name,
            COALESCE(p.unit, a.unit, 'db') AS unit
        FROM prices pr
        LEFT JOIN products   p  ON p.item_id  = pr.item_id
        LEFT JOIN activities a  ON a.item_id  = pr.item_id
        LEFT JOIN web_sources ws ON ws.id = pr.source_id
        WHERE pr.item_id = :item_id
        {type_clause}
        AND pr.db_inserted >= NOW() - INTERVAL '90 days'
        ORDER BY pr.net_price ASC, pr.db_inserted DESC
        LIMIT 5
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        if not rows:
            return {"best": None, "alternatives": []}
        result = [_row2dict(r) for r in rows]
        for r in result:
            r["age_status"] = _age_status(rows[result.index(r)]._mapping.get("db_inserted"))
        return {"best": result[0], "alternatives": result[1:]}
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {e}")


# ── KÉZI ÁR RÖGZÍTÉS ─────────────────────────────────────────

@router.post("/")
async def add_price(
    body: dict,
    _auth: dict = Depends(require_auth),
):
    """Kézi áradat rögzítése"""
    item_id    = (body.get("item_id") or "").strip()
    price_type = (body.get("price_type") or "lista").strip()
    price      = body.get("price")
    currency   = (body.get("currency") or "HUF").strip().upper()
    source_id  = body.get("source_id")
    supplier_code = (body.get("supplier_code") or "").strip() or None

    if not item_id:
        raise HTTPException(400, "item_id kötelező")
    if price is None:
        raise HTTPException(400, "price kötelező")
    try:
        price = float(price)
        if price < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(400, "price érvénytelen szám")
    if price_type not in ("lista", "kisker", "nagyker", "egyedi"):
        raise HTTPException(400, "price_type: lista|kisker|nagyker|egyedi")

    try:
        with engine.begin() as conn:
            import uuid as _uuid
            pid = str(_uuid.uuid4())
            conn.execute(text(
                "INSERT INTO prices (price_id, item_id, price_type, net_price, currency, "
                "source_id, supplier_code, db_inserted) "
                "VALUES (:pid,:item_id,:pt,:price,:cur,:src,:sc,NOW())"
            ), {
                "pid":     pid,
                "item_id": item_id,
                "pt":      price_type,
                "price":   price,
                "cur":     currency,
                "src":     source_id,
                "sc":      supplier_code,
            })
        log.info("Ár rögzítve: %s %s %s %s", item_id, price_type, price, currency)
        return {"status": "ok", "id": pid}
    except Exception as e:
        raise HTTPException(500, f"Mentési hiba: {e}")


# ── ÁR TÖRLÉS ────────────────────────────────────────────────

@router.delete("/{price_id}")
async def delete_price(price_id: str, _auth: dict = Depends(require_auth)):
    """Áradat törlése (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.begin() as conn:
            res = conn.execute(text("DELETE FROM prices WHERE price_id=:id"), {"id": price_id})
        if res.rowcount == 0:
            raise HTTPException(404, "Nem található")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Törlési hiba: {e}")


# ── ÖSSZESÍTŐ STATISZTIKA ─────────────────────────────────────

@router.get("/stats")
async def price_stats(_auth: dict = Depends(require_auth)):
    """Árlista összesítő: darabszámok, források, utolsó frissítés"""
    sql = """
        SELECT
            COUNT(*)                                             AS total,
            COUNT(*) FILTER (WHERE price_type='lista')          AS cnt_lista,
            COUNT(*) FILTER (WHERE price_type='kisker')         AS cnt_kisker,
            COUNT(*) FILTER (WHERE price_type='nagyker')        AS cnt_nagyker,
            COUNT(*) FILTER (WHERE price_type='egyedi')         AS cnt_egyedi,
            COUNT(*) FILTER (WHERE db_inserted >= NOW()-INTERVAL '7 days')  AS fresh_7d,
            COUNT(*) FILTER (WHERE db_inserted >= NOW()-INTERVAL '30 days') AS fresh_30d,
            MAX(db_inserted)                                     AS last_update,
            COUNT(DISTINCT source_id)                           AS source_count,
            COUNT(DISTINCT item_id)                             AS item_count
        FROM prices
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(text(sql)).fetchone()
        d = _row2dict(row)
        return d
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {e}")
