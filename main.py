"""
CRT Ajánlatsegéd – Backend Gerinc v1.0
Indítás: py -3.11 -m uvicorn main:app --reload
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import ntplib, logging, uuid, json, os, re
from auth import router as auth_router, require_auth
from sanitize import SanitizeMiddleware
from web_sources import router as web_router
from quotes_router import router as quotes_router
from export_router  import router as export_router
from prices_router  import router as prices_router
import ai_motor
import chroma_motor
import vision_motor
from golden_router import router as golden_router
from lora_router   import router as lora_router
import env_detect

# ── IDŐ ───────────────────────────────────────────────────
CET  = timezone(timedelta(hours=1))
CEST = timezone(timedelta(hours=2))

def local_now(utc_dt=None):
    if utc_dt is None:
        utc_dt = datetime.utcnow()
    tz = CEST if 3 <= utc_dt.month <= 10 else CET
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz)

# ── LOGGING ───────────────────────────────────────────────
# ── RUNTIME KÖNYVTÁRAK + PLATFORM ────────────────────────────
_CRT_ROOT = env_detect.get_crt_root()
env_detect.ensure_runtime_dirs(_CRT_ROOT)
_PLATFORM = env_detect.detect_platform()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(str(_CRT_ROOT / "logs" / "backend" / "backend.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("CRT")

# ── ADATBÁZIS ─────────────────────────────────────────────
DB_URL = env_detect.get_db_url()

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False
)
SessionLocal = sessionmaker(bind=engine)

def db_ping():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        log.error(f"DB hiba: {e}")
        return False

# ── APP ───────────────────────────────────────────────────
app = FastAPI(
    title="CRT Ajánlatsegéd API",
    version="1.0",
    description="Civil Rendszertechnika Kft. – AI alapú ajánlatkészítő"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SanitizeMiddleware, log_threats=True)

app.include_router(auth_router)
app.include_router(web_router)
app.include_router(quotes_router)
app.include_router(export_router)
app.include_router(prices_router)
app.include_router(golden_router)
app.include_router(lora_router)

app.mount("/ui", StaticFiles(directory="ui"), name="ui")

# ── NTP ───────────────────────────────────────────────────
def ntp_now():
    try:
        c = ntplib.NTPClient()
        r = c.request("time.google.com", version=3)
        return local_now(datetime.utcfromtimestamp(r.tx_time))
    except:
        log.warning("NTP hiba – rendszeridő használva")
        return local_now()

# ── MODELLEK ──────────────────────────────────────────────
class PingResponse(BaseModel):
    status:   str
    version:  str
    time_ntp: str
    db:       str
    message:  str

class PromptRequest(BaseModel):
    text:      str
    max_chars: int = 50

class PromptResponse(BaseModel):
    input:   str
    chars:   int
    valid:   bool
    message: str

# ── STARTUP ───────────────────────────────────────────────
_REQUIRED_COLS = {
    "audit_log":   ["description", "ip_address", "entity_id"],
    "prices":      ["source_id", "supplier_code", "currency"],
    "quotes":      ["source_mode", "client_ref", "base_quote_id"],
    "quote_lines": ["confidence", "price_source", "item_id"],
    "golden_examples": ["raw_text"],
    "chroma_index":    ["collection"],
    "lora_jobs":       ["job_id", "status"],
}

@app.on_event("startup")
async def startup():
    env_detect.print_env_summary()
    env_detect.write_pid()
    env_detect.write_runtime_status({"api_version": "1.0"})
    log.info("CRT Backend indul...")
    if not db_ping():
        log.error("❌ PostgreSQL nem elérhető!")
        return
    log.info("✅ PostgreSQL kapcsolat OK")
    try:
        with engine.connect() as conn:
            missing = []
            for table, cols in _REQUIRED_COLS.items():
                for col in cols:
                    row = conn.execute(text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name=:t AND column_name=:c"
                    ), {"t": table, "c": col}).fetchone()
                    if not row:
                        missing.append(f"{table}.{col}")
            if missing:
                log.warning(
                    "⚠️  Hiányzó DB oszlopok – futtasd sorban: "
                    "db_migrate_v04 → v05 → v06 → v07 → v08\n   %s",
                    ", ".join(missing)
                )
            else:
                log.info("✅ DB séma ellenőrzés OK (v1.0)")
    except Exception as e:
        log.warning("DB séma ellenőrzés hiba: %s", e)
    # ChromaDB elérhetőség (nem blokkoló)
    try:
        if chroma_motor.is_available():
            st = chroma_motor.stats()
            log.info("✅ ChromaDB OK – raw:%d clean:%d", st["raw_count"], st["clean_count"])
        else:
            log.warning("⚠️  ChromaDB nem elérhető (localhost:8001) – vektoros funkciók kikapcsolva")
    except Exception as e:
        log.warning("ChromaDB ellenőrzés hiba: %s", e)

@app.on_event("shutdown")
async def shutdown():
    env_detect.clear_pid()
    log.info("CRT Backend leállt.")

# ── ENDPOINTOK ────────────────────────────────────────────

@app.get("/", response_model=PingResponse)
async def root():
    """Rendszer életjel"""
    t  = ntp_now()
    db = "ok" if db_ping() else "hiba"
    return {
        "status":   "ok",
        "version":  "1.0",
        "time_ntp": t.strftime("%Y-%m-%d %H:%M:%S CEST"),
        "db":       db,
        "message":  "CRT Ajánlatsegéd – Dzseppettó műhelye kész 🪵"
    }

@app.get("/health")
async def health():
    return {
        "server":   "ok",
        "ntp":      ntp_now().strftime("%H:%M:%S CEST"),
        "db":       "ok" if db_ping() else "hiba",
        "version":  "1.0",
        "platform": _PLATFORM,
    }

@app.get("/status/widget")
async def widget_status():
    """Állapotjelző – zöld/piros"""
    ntp_ok = False
    try:
        ntp_now()
        ntp_ok = True
    except:
        pass
    db_ok = db_ping()
    checks = {"server": True, "ntp": ntp_ok, "db": db_ok}
    return {
        "status": "green" if all(checks.values()) else "red",
        "checks": checks,
        "time":   local_now().strftime("%H:%M:%S CEST")
    }

@app.get("/db/test")
async def db_test():
    """PostgreSQL kapcsolat teszt"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version(), current_database(), current_user"))
            row = result.fetchone()
            return {
                "status":   "ok",
                "version":  row[0],
                "database": row[1],
                "user":     row[2],
                "time":     local_now().strftime("%H:%M:%S CEST")
            }
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {str(e)}")

@app.get("/cikktorzs/tree")
async def cikktorzs_tree(_auth: dict = Depends(require_auth)):
    """Kategória fa termékekkel és tevékenységekkel, utolsó ár időbélyeggel"""
    try:
        with engine.connect() as conn:
            cats = conn.execute(text(
                "SELECT category_id, parent_id, name, item_class, sort_order "
                "FROM categories WHERE active = true ORDER BY sort_order, name"
            )).fetchall()

            prods = conn.execute(text(
                "SELECT p.item_id, p.name, p.category_id, p.crt_code, p.unit, "
                "p.created_at, p.active, MAX(pr.db_inserted) AS last_price "
                "FROM products p "
                "LEFT JOIN prices pr ON pr.item_id = p.item_id "
                "WHERE p.active = true "
                "GROUP BY p.item_id ORDER BY p.name"
            )).fetchall()

            acts = conn.execute(text(
                "SELECT a.item_id, a.name, a.category_id, a.unit, "
                "a.created_at, a.active, MAX(pr.db_inserted) AS last_price "
                "FROM activities a "
                "LEFT JOIN prices pr ON pr.item_id = a.item_id "
                "WHERE a.active = true "
                "GROUP BY a.item_id ORDER BY a.name"
            )).fetchall()

            def row2dict(r):
                d = dict(r._mapping)
                for k, v in d.items():
                    if hasattr(v, 'isoformat'):
                        d[k] = v.isoformat()
                return d

            return {
                "categories": [row2dict(r) for r in cats],
                "products":   [row2dict(r) for r in prods],
                "activities": [row2dict(r) for r in acts],
            }
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {str(e)}")


@app.get("/cikktorzs/search")
async def cikktorzs_search(q: str = "", tipus: str = "mind", _auth: dict = Depends(require_auth)):
    """Névben / gyártóban keres – min. 2 karakter"""
    if len(q) < 2:
        return {"results": [], "count": 0}
    try:
        with engine.connect() as conn:
            results = []
            if tipus in ("mind", "termek"):
                rows = conn.execute(text(
                    "SELECT item_id, name, crt_code, unit, created_at, 'termék' AS tipus "
                    "FROM products WHERE active=true "
                    "AND (LOWER(name) LIKE LOWER(:q) OR LOWER(COALESCE(crt_code,'')) LIKE LOWER(:q)) "
                    "ORDER BY name LIMIT 25"
                ), {"q": f"%{q}%"}).fetchall()
                results += [dict(r._mapping) for r in rows]
            if tipus in ("mind", "tevekenyseg"):
                rows = conn.execute(text(
                    "SELECT item_id, name, crt_code, unit, created_at, 'tevékenység' AS tipus "
                    "FROM activities WHERE active=true AND LOWER(name) LIKE LOWER(:q) "
                    "ORDER BY name LIMIT 25"
                ), {"q": f"%{q}%"}).fetchall()
                results += [dict(r._mapping) for r in rows]
            for r in results:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {str(e)}")


@app.get("/cikktorzs/{item_id}/status")
async def cikktorzs_item_status(item_id: str, _auth: dict = Depends(require_auth)):
    """Egy termék/tevékenység ár státusza és frisssége"""
    try:
        with engine.connect() as conn:
            prod = conn.execute(text(
                "SELECT item_id, name, crt_code, unit, active FROM products WHERE item_id=:id"
            ), {"id": item_id}).fetchone()
            act = None
            if not prod:
                act = conn.execute(text(
                    "SELECT item_id, name, crt_code, unit, active FROM activities WHERE item_id=:id"
                ), {"id": item_id}).fetchone()
            if not prod and not act:
                raise HTTPException(404, "Termék/tevékenység nem található")

            item      = dict((prod or act)._mapping)
            item_type = "termék" if prod else "tevékenység"

            price_rows = conn.execute(text("""
                SELECT pr.price_type, pr.net_price, pr.currency,
                       pr.db_inserted, ws.name AS source_name, pr.supplier_code
                FROM prices pr
                LEFT JOIN web_sources ws ON ws.id = pr.source_id
                WHERE pr.item_id = :id
                ORDER BY pr.db_inserted DESC
            """), {"id": item_id}).fetchall()

        from datetime import datetime as _dt
        now = _dt.utcnow()
        prices_by_type = {}
        for r in price_rows:
            pt = r[0]
            age_days = (now - r[3]).days if r[3] else None
            freshness = ("fresh" if age_days is not None and age_days <= 7 else
                         "warn"  if age_days is not None and age_days <= 30 else "old")
            if pt not in prices_by_type:
                prices_by_type[pt] = {
                    "net_price":     float(r[1]) if r[1] else None,
                    "currency":      r[2],
                    "updated":       r[3].isoformat() if r[3] else None,
                    "age_days":      age_days,
                    "freshness":     freshness,
                    "source":        r[4] or "kézi",
                    "supplier_code": r[5],
                }

        missing_types = [t for t in ("lista", "kisker", "nagyker") if t not in prices_by_type]

        return {
            "item_id":             item["item_id"],
            "name":                item["name"],
            "crt_code":            item.get("crt_code"),
            "unit":                item.get("unit"),
            "item_type":           item_type,
            "active":              item.get("active"),
            "prices":              prices_by_type,
            "missing_price_types": missing_types,
            "has_any_price":       len(prices_by_type) > 0,
            "coverage":            ("teljes"   if not missing_types else
                                    "részleges" if prices_by_type   else "hiányzik"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Státusz lekérési hiba: {e}")


@app.post("/cikktorzs/upload")
async def cikktorzs_upload(file: UploadFile = File(...), _auth: dict = Depends(require_auth)):
    """Fájl feltöltés és sorok kiolvasása (xlsx, csv, pdf, docx, html, md)"""
    from cikktorzs_parse import parse_file
    content = await file.read()
    try:
        rows = parse_file(file.filename or "file", content)
        return {"status": "ok", "rows": rows, "count": len(rows), "filename": file.filename}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.error(f"Feltöltési hiba: {e}")
        raise HTTPException(500, f"Feldolgozási hiba: {str(e)}")


@app.post("/cikktorzs/identify")
async def identify_items(payload: dict, _auth: dict = Depends(require_auth)):
    """AI azonosítás – Claude API → Ollama fallback"""
    items = payload.get("items", [])
    if not items:
        return {"results": [], "tokens_used": 0, "source": "none"}

    # ChromaDB: nyers sorok indexelése (DB1) – nem blokkoló
    if chroma_motor.is_available():
        raw_ids = [f"raw_{uuid.uuid4().hex[:8]}_{i}" for i in range(len(items))]
        chroma_motor.add_raw(items, raw_ids, [{"source": "identify"} for _ in items])

    try:
        import asyncio
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_motor.identify, items, engine)
        return result
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/cikktorzs/save")
async def save_items(payload: dict, _auth: dict = Depends(require_auth)):
    """Jóváhagyott tételek mentése az adatbázisba"""
    items  = payload.get("items", [])
    tipus  = payload.get("tipus", "termek")
    user_id = payload.get("user_id", "system")

    if not items:
        return {"saved": 0, "errors": []}

    saved, errors = 0, []
    now = local_now()

    try:
        with engine.begin() as conn:
            for it in items:
                name = (it.get("name") or "").strip()
                if not name:
                    continue
                try:
                    item_id = str(uuid.uuid4())
                    if tipus == "termek":
                        conn.execute(text(
                            "INSERT INTO products "
                            "(item_id, crt_code, name, description, category_id, unit, "
                            " ean, part_number, active, created_at) "
                            "VALUES (:id, :crt, :name, :desc, :cat, :unit, :ean, :pn, true, :now)"
                        ), {"id": item_id, "name": name,
                            "crt":  it.get("crt_code"),
                            "desc": it.get("description"),
                            "cat":  it.get("category_id"),
                            "unit": it.get("unit", "db"),
                            "ean":  it.get("ean"),
                            "pn":   it.get("part_number"),
                            "now":  now})
                    else:
                        conn.execute(text(
                            "INSERT INTO activities "
                            "(item_id, crt_code, name, description, category_id, unit, active, created_at) "
                            "VALUES (:id, :crt, :name, :desc, :cat, :unit, true, :now)"
                        ), {"id": item_id, "name": name,
                            "crt":  it.get("crt_code"),
                            "desc": it.get("description"),
                            "cat":  it.get("category_id"),
                            "unit": it.get("unit", "óra"),
                            "now":  now})
                    saved += 1
                    log.info(f"Cikktörzs mentés: {name}")
                except Exception as e:
                    errors.append(f"{name}: {str(e)}")
        # ChromaDB: jóváhagyott tételek indexelése (DB2) – nem blokkoló
        if saved > 0 and chroma_motor.is_available():
            saved_items = [it for it in items if (it.get("name") or "").strip()]
            for it in saved_items:
                it.setdefault("item_id", str(uuid.uuid4()))
            chroma_motor.add_clean(saved_items)

        return {"saved": saved, "errors": errors}
    except Exception as e:
        raise HTTPException(500, f"Mentési hiba: {str(e)}")


@app.post("/prompt/validate", response_model=PromptResponse)
async def validate_prompt(req: PromptRequest):
    """Prompt validálás – max 50 karakter"""
    text_in = req.text.strip()
    chars   = len(text_in)
    if chars == 0:
        raise HTTPException(400, "Üres prompt")
    if chars > 50:
        return {"input": text_in[:50], "chars": chars, "valid": False, "message": f"Túl hosszú! {chars}/50 kar."}
    return {"input": text_in, "chars": chars, "valid": True, "message": "OK"}

@app.get("/stats/dashboard")
async def stats_dashboard(_auth: dict = Depends(require_auth)):
    """3 operatív kérdés: rendszer él-e / AI megbízható-e / árak lefednek-e"""
    from datetime import datetime as _dt

    with engine.connect() as conn:

        # ── 1. RENDSZER ──────────────────────────────────────────
        total_products = conn.execute(text(
            "SELECT COUNT(*) FROM products WHERE active = true"
        )).scalar() or 0

        total_activities = conn.execute(text(
            "SELECT COUNT(*) FROM activities WHERE active = true"
        )).scalar() or 0

        last_product_row = conn.execute(text(
            "SELECT created_at FROM products ORDER BY created_at DESC LIMIT 1"
        )).fetchone()
        last_product_added = last_product_row[0].isoformat() if last_product_row and last_product_row[0] else None

        last_backup_row = conn.execute(text(
            "SELECT timestamp FROM audit_log WHERE action='export' AND description LIKE 'Backup:%' ORDER BY timestamp DESC LIMIT 1"
        )).fetchone()
        last_backup = last_backup_row[0].isoformat() if last_backup_row and last_backup_row[0] else None

        last_scrape_row = conn.execute(text(
            "SELECT MAX(db_inserted) FROM prices WHERE source_id IS NOT NULL"
        )).fetchone()
        last_scraping = last_scrape_row[0].isoformat() if last_scrape_row and last_scrape_row[0] else None

        # ChromaDB
        try:
            chroma_ok = chroma_motor.is_available()
        except Exception:
            chroma_ok = False

        # Ollama
        try:
            import httpx as _hx
            _r = _hx.get(f"{os.environ.get('CRT_OLLAMA_URL','http://localhost:11434')}/api/tags", timeout=3.0)
            ollama_ok = _r.status_code == 200
            ollama_models = [m["name"] for m in _r.json().get("models", [])]
        except Exception:
            ollama_ok = False
            ollama_models = []

        # ── 2. AI MEGBÍZHATÓSÁG ──────────────────────────────────
        golden_count = conn.execute(text("SELECT COUNT(*) FROM golden_examples")).scalar() or 0

        active_lora = conn.execute(text(
            "SELECT value FROM system_config WHERE key='lora_active_job_id'"
        )).scalar()

        ollama_model_cfg = conn.execute(text(
            "SELECT value FROM system_config WHERE key='ollama_model'"
        )).scalar() or "llama3:8b"

        claude_key_set = bool(conn.execute(text(
            "SELECT value FROM system_config WHERE key='claude_api_key' AND value != ''"
        )).scalar())

        if claude_key_set:
            active_motor = "claude"
        elif active_lora:
            active_motor = f"lora/{active_lora}"
        elif ollama_ok and ollama_models:
            active_motor = ollama_models[0]
        else:
            active_motor = "nincs"

        # ── 3. ÁRFEDETTSÉG ───────────────────────────────────────
        price_stats = conn.execute(text("""
            SELECT
                COUNT(*)                                                  AS total_prices,
                COUNT(DISTINCT item_id)                                   AS items_with_price,
                COUNT(*) FILTER (WHERE db_inserted >= NOW()-INTERVAL '7 days')  AS fresh_7d,
                COUNT(*) FILTER (WHERE db_inserted >= NOW()-INTERVAL '30 days') AS fresh_30d,
                MIN(db_inserted)                                          AS oldest_price,
                MAX(db_inserted)                                          AS newest_price
            FROM prices
        """)).fetchone()

        items_with_price  = price_stats[1] or 0
        total_items       = total_products + total_activities
        items_without     = max(0, total_items - items_with_price)
        coverage_pct      = round(items_with_price / total_items * 100, 1) if total_items else 0

        oldest = price_stats[4]
        oldest_days = ((_dt.utcnow() - oldest).days) if oldest else None

        source_rows = conn.execute(text("""
            SELECT ws.name, COUNT(*) AS cnt
            FROM prices pr
            LEFT JOIN web_sources ws ON ws.id = pr.source_id
            GROUP BY ws.name
            ORDER BY cnt DESC
            LIMIT 10
        """)).fetchall()
        source_breakdown = [{"name": r[0] or "kézi", "count": r[1]} for r in source_rows]

    return {
        "generated_at": _dt.now().isoformat(),
        "system": {
            "api":               "ok",
            "db":                "ok",
            "chromadb":          "ok" if chroma_ok else "nem fut",
            "ollama":            "ok" if ollama_ok else "nem fut",
            "ollama_models":     ollama_models,
            "total_products":    total_products,
            "total_activities":  total_activities,
            "last_product_added": last_product_added,
            "last_backup":       last_backup,
            "last_scraping":     last_scraping,
        },
        "ai": {
            "active_motor":   active_motor,
            "golden_count":   golden_count,
            "lora_ready":     golden_count >= 10,
            "lora_active":    bool(active_lora),
            "claude_api_set": claude_key_set,
            "ollama_ok":      ollama_ok,
        },
        "prices": {
            "total":            price_stats[0] or 0,
            "items_with_price": items_with_price,
            "items_without":    items_without,
            "total_items":      total_items,
            "coverage_pct":     coverage_pct,
            "fresh_7d":         price_stats[2] or 0,
            "fresh_30d":        price_stats[3] or 0,
            "oldest_price_days": oldest_days,
            "newest_price":     price_stats[5].isoformat() if price_stats[5] else None,
            "source_breakdown": source_breakdown,
        },
    }


@app.get("/audit/logs")
async def audit_logs(
    q:           str  = "",
    action:      str  = "",
    user_id:     int  = None,
    from_:       str  = Query("", alias="from"),
    to:          str  = "",
    limit:       int  = 50,
    offset:      int  = 0,
    _auth: dict = Depends(require_auth),
):
    """Audit napló lekérdezés – csak admin"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")

    limit  = min(max(limit, 1), 500)
    offset = max(offset, 0)

    conditions, params = [], {}

    if q:
        conditions.append(
            "(LOWER(COALESCE(u.username,'')) LIKE LOWER(:q) "
            "OR LOWER(COALESCE(a.entity_id,'')) LIKE LOWER(:q) "
            "OR LOWER(COALESCE(a.ip_address,'')) LIKE LOWER(:q) "
            "OR LOWER(COALESCE(a.description,'')) LIKE LOWER(:q))"
        )
        params["q"] = f"%{q}%"
    if action:
        conditions.append("a.action = :action")
        params["action"] = action
    if user_id is not None:
        conditions.append("a.user_id = :user_id")
        params["user_id"] = user_id
    if from_:
        conditions.append("a.timestamp >= :from_")
        params["from_"] = from_
    if to:
        conditions.append("a.timestamp < (:to ::date + INTERVAL '1 day')")
        params["to"] = to

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    base_sql = f"""
        FROM audit_log a
        LEFT JOIN users u ON u.id::text = a.user_id
        {where}
    """

    try:
        with engine.connect() as conn:
            total_row = conn.execute(text(f"SELECT COUNT(*) {base_sql}"), params).fetchone()
            total = total_row[0] if total_row else 0

            action_where = ("WHERE " + " AND ".join(conditions + ["a.action=:_act"])) if conditions else "WHERE a.action=:_act"
            count_login = conn.execute(text(
                f"SELECT COUNT(*) FROM audit_log a LEFT JOIN users u ON u.id::text=a.user_id {action_where}"
            ), {**params, "_act": "login"}).fetchone()[0]
            count_update = conn.execute(text(
                f"SELECT COUNT(*) FROM audit_log a LEFT JOIN users u ON u.id::text=a.user_id {action_where}"
            ), {**params, "_act": "update"}).fetchone()[0]
            count_delete = conn.execute(text(
                f"SELECT COUNT(*) FROM audit_log a LEFT JOIN users u ON u.id::text=a.user_id {action_where}"
            ), {**params, "_act": "delete"}).fetchone()[0]

            rows = conn.execute(text(f"""
                SELECT a.log_id, a.user_id, u.username, a.action,
                       a.entity_id, a.description, a.ip_address, a.timestamp AS created_at
                {base_sql}
                ORDER BY a.timestamp DESC
                LIMIT :limit OFFSET :offset
            """), {**params, "limit": limit, "offset": offset}).fetchall()

        def row2log(r):
            d = dict(r._mapping)
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            return d

        return {
            "logs":         [row2log(r) for r in rows],
            "total":        total,
            "count_login":  count_login,
            "count_update": count_update,
            "count_delete": count_delete,
            "limit":        limit,
            "offset":       offset,
        }
    except Exception as e:
        raise HTTPException(500, f"Napló lekérdezési hiba: {str(e)}")


@app.post("/admin/backup")
async def admin_backup(_auth: dict = Depends(require_auth)):
    """Adatbázis JSON export → db_data/backup_YYYYMMDD_HHMMSS.json"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")

    import json as _json
    from pathlib import Path

    out_dir = Path(__file__).parent / "db_data" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts       = local_now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"backup_{ts}.json"

    tables = [
        "categories", "products", "activities", "prices",
        "quotes", "quote_lines", "web_sources", "web_scripts",
        "web_prices", "users", "system_config", "audit_log",
    ]

    data: dict = {}
    try:
        with engine.connect() as conn:
            for tbl in tables:
                try:
                    rows = conn.execute(text(f"SELECT * FROM {tbl}")).fetchall()
                    data[tbl] = []
                    for r in rows:
                        d = dict(r._mapping)
                        for k, v in d.items():
                            if hasattr(v, "isoformat"):
                                d[k] = v.isoformat()
                        data[tbl].append(d)
                except Exception:
                    data[tbl] = []

        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        size_kb = out_path.stat().st_size // 1024
        log.info("Backup kész: %s (%d KB)", out_path, size_kb)

        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO audit_log (log_id, user_id, action, description, timestamp) "
                    "VALUES (:lid, :uid, 'export', :desc, NOW())"
                ), {"lid": str(__import__('uuid').uuid4()), "uid": str(_auth["user_id"]), "desc": f"Backup: {out_path.name}"})
        except Exception:
            pass

        return {"status": "ok", "path": str(out_path), "size_kb": size_kb, "tables": len(tables)}

    except Exception as e:
        raise HTTPException(500, f"Backup hiba: {e}")


@app.get("/chroma/stats")
async def chroma_stats(_auth: dict = Depends(require_auth)):
    """ChromaDB gyűjtemény-statisztika"""
    return chroma_motor.stats()


@app.get("/chroma/search")
async def chroma_search(
    q:          str = "",
    collection: str = "crt_clean",
    n:          int = 5,
    _auth: dict = Depends(require_auth),
):
    """Vektoros hasonlóság-keresés (q: lekérdező szöveg)"""
    if len(q) < 2:
        raise HTTPException(400, "Minimum 2 karakter szükséges")
    if collection not in ("crt_clean", "crt_raw"):
        raise HTTPException(400, "collection: crt_clean | crt_raw")
    if not chroma_motor.is_available():
        raise HTTPException(503, "ChromaDB nem elérhető")
    results = chroma_motor.search(q, collection, min(n, 20))
    return {"results": results, "count": len(results), "query": q, "collection": collection}


@app.post("/vision/analyze")
async def vision_analyze(
    file: UploadFile = File(...),
    _auth: dict = Depends(require_auth),
):
    """
    Kép vagy PDF oldal elemzése LLaVA-val.
    Támogatott: PNG, JPG, WEBP, PDF (első oldal kerül elemzésre)
    """
    content = await file.read()
    fname   = (file.filename or "").lower()

    if fname.endswith(".pdf"):
        result = vision_motor.analyze_pdf_page(content, 0, engine)
    else:
        mime = "image/jpeg" if fname.endswith((".jpg", ".jpeg")) else "image/png"
        result = vision_motor.analyze_image(content, mime, engine)

    if "error" in result and not result["results"]:
        raise HTTPException(503, result["error"])
    return result


@app.get("/vision/status")
async def vision_status(_auth: dict = Depends(require_auth)):
    """LLaVA elérhetőség ellenőrzés"""
    from sqlalchemy import text as _text
    url = "http://localhost:11434"
    try:
        with engine.connect() as conn:
            row = conn.execute(_text(
                "SELECT value FROM system_config WHERE key='ollama_url'"
            )).fetchone()
            if row:
                url = row[0]
    except Exception:
        pass
    available = vision_motor.llava_available(url)
    return {"available": available, "url": url,
            "model": "llava:7b", "note": "ollama pull llava:7b" if not available else ""}


@app.get("/auth/admin/users")
async def admin_users_list(_auth: dict = Depends(require_auth)):
    """Felhasználó lista (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, username, email, role, active, created_at, last_login, "
                "locked_until, attempt_count FROM users ORDER BY id"
            )).fetchall()
        def u2d(r):
            d = dict(r._mapping)
            for k, v in d.items():
                if hasattr(v, "isoformat"): d[k] = v.isoformat()
            d.pop("pin_hash", None)
            d["locked"] = bool(d.get("locked_until"))
            return d
        return {"users": [u2d(r) for r in rows], "total": len(rows)}
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {e}")


@app.post("/auth/admin/users")
async def admin_users_create(body: dict, _auth: dict = Depends(require_auth)):
    """Új felhasználó létrehozása (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    username = (body.get("username") or "").strip()
    pin      = (body.get("pin") or "").strip()
    email    = (body.get("email") or "").strip() or None
    role     = (body.get("role") or "user").strip()
    if not username or len(username) < 3:
        raise HTTPException(400, "username legalább 3 karakter")
    if not pin or len(pin) != 6 or not pin.isdigit():
        raise HTTPException(400, "pin: 6 számjegy")
    if role not in ("admin", "user", "viewer"):
        raise HTTPException(400, "role: admin|user|viewer")
    import bcrypt as _bcrypt
    pin_hash = _bcrypt.hashpw(pin.encode(), _bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            row = conn.execute(text(
                "INSERT INTO users (username, pin_hash, email, role, active, created_at, attempt_count) "
                "VALUES (:u, :ph, :e, :r, true, NOW(), 0) RETURNING id"
            ), {"u": username, "ph": pin_hash, "e": email, "r": role}).fetchone()
        return {"status": "ok", "id": row[0], "username": username}
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(409, f"Felhasználónév már létezik: {username}")
        raise HTTPException(500, f"Létrehozási hiba: {e}")


@app.patch("/auth/admin/users/{uid}/pin")
async def admin_users_reset_pin(uid: int, body: dict, _auth: dict = Depends(require_auth)):
    """Felhasználó PIN visszaállítása (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    new_pin = (body.get("new_pin") or "").strip()
    if not new_pin or len(new_pin) != 6 or not new_pin.isdigit():
        raise HTTPException(400, "new_pin: 6 számjegy")
    import bcrypt as _bcrypt
    pin_hash = _bcrypt.hashpw(new_pin.encode(), _bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            res = conn.execute(text(
                "UPDATE users SET pin_hash=:ph, attempt_count=0 WHERE id=:id"
            ), {"ph": pin_hash, "id": uid})
        if res.rowcount == 0:
            raise HTTPException(404, "Felhasználó nem található")
        return {"status": "ok"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500, f"PIN frissítési hiba: {e}")


@app.post("/auth/admin/users/{uid}/unlock")
async def admin_users_unlock(uid: int, _auth: dict = Depends(require_auth)):
    """Felhasználó feloldása zárolás alól (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.begin() as conn:
            res = conn.execute(text(
                "UPDATE users SET locked_until=NULL, attempt_count=0 WHERE id=:id"
            ), {"id": uid})
        if res.rowcount == 0:
            raise HTTPException(404, "Felhasználó nem található")
        return {"status": "ok"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500, f"Feloldási hiba: {e}")


@app.delete("/auth/admin/users/{uid}")
async def admin_users_delete(uid: int, _auth: dict = Depends(require_auth)):
    """Felhasználó deaktiválása (nem törli, csak inaktívvá teszi)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    if uid == _auth.get("user_id"):
        raise HTTPException(400, "Saját fiókot nem lehet deaktiválni")
    try:
        with engine.begin() as conn:
            res = conn.execute(text(
                "UPDATE users SET active=false WHERE id=:id"
            ), {"id": uid})
        if res.rowcount == 0:
            raise HTTPException(404, "Felhasználó nem található")
        return {"status": "ok"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(500, f"Deaktiválási hiba: {e}")


@app.get("/auth/admin/config")
async def admin_config_get(_auth: dict = Depends(require_auth)):
    """Rendszer konfiguráció olvasása (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    CONFIG_KEYS = [
        "smtp_host", "smtp_port", "smtp_user", "smtp_from", "smtp_tls",
        "ollama_url", "ollama_model", "claude_model",
        "ai_conf_high", "ai_conf_low",
        "quote_validity_days", "company_name", "company_tax",
        "scrape_interval_hours", "max_price_age_days", "auto_scrape",
    ]
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT key, value, encrypted FROM system_config WHERE key = ANY(:keys)"
            ), {"keys": CONFIG_KEYS}).fetchall()
        cfg = {}
        for r in rows:
            if r._mapping["encrypted"]:
                cfg[r._mapping["key"]] = "••• (beállítva) •••" if r._mapping["value"] else ""
            else:
                cfg[r._mapping["key"]] = r._mapping["value"] or ""
        # Normalizálás: smtp_from_name alias
        cfg["smtp_from_name"] = cfg.get("smtp_from", "")
        return {"config": cfg}
    except Exception as e:
        raise HTTPException(500, f"Konfig olvasási hiba: {e}")


@app.patch("/auth/admin/config")
async def admin_config_patch(body: dict, _auth: dict = Depends(require_auth)):
    """Rendszer konfiguráció frissítése (admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")

    ENCRYPTED_KEYS = {"smtp_pass", "claude_api_key"}
    ALLOWED_KEYS = {
        "smtp_host", "smtp_port", "smtp_user", "smtp_from", "smtp_from_name",
        "smtp_pass", "smtp_tls", "ollama_url", "ollama_model", "claude_model",
        "claude_api_key", "ai_conf_high", "ai_conf_low",
        "quote_validity_days", "company_name", "company_tax",
        "scrape_interval_hours", "max_price_age_days", "auto_scrape",
    }
    # smtp_from_name → smtp_from alias
    if "smtp_from_name" in body:
        body["smtp_from"] = body.pop("smtp_from_name")

    updated = []
    try:
        with engine.begin() as conn:
            for k, v in body.items():
                if k not in ALLOWED_KEYS:
                    continue
                val = str(v) if not isinstance(v, str) else v
                enc = k in ENCRYPTED_KEYS
                conn.execute(text("""
                    INSERT INTO system_config (key, value, encrypted, updated_by, updated_at)
                    VALUES (:k, :v, :enc, :uid, NOW())
                    ON CONFLICT (key) DO UPDATE
                    SET value=EXCLUDED.value, encrypted=EXCLUDED.encrypted,
                        updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at
                """), {"k": k, "v": val, "enc": enc, "uid": str(_auth["user_id"])})
                updated.append(k)
        return {"status": "ok", "updated": updated}
    except Exception as e:
        raise HTTPException(500, f"Konfig mentési hiba: {e}")


@app.post("/auth/admin/config/test-smtp")
async def admin_config_test_smtp(_auth: dict = Depends(require_auth)):
    """SMTP kapcsolat teszt – teszt email küldése az admin usernek"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT key, value FROM system_config WHERE key IN "
                "('smtp_host','smtp_port','smtp_user','smtp_pass','smtp_from','smtp_tls')"
            )).fetchall()
            row2 = conn.execute(text(
                "SELECT email FROM users WHERE id=:uid"
            ), {"uid": _auth["user_id"]}).fetchone()
        cfg = {r._mapping["key"]: r._mapping["value"] for r in rows}
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {e}")

    smtp_host = cfg.get("smtp_host") or ""
    smtp_port = int(cfg.get("smtp_port") or 587)
    smtp_user = cfg.get("smtp_user") or ""
    smtp_pass = cfg.get("smtp_pass") or ""
    smtp_from = cfg.get("smtp_from") or smtp_user
    use_tls   = (cfg.get("smtp_tls") or "true").lower() not in ("false", "0", "no")

    if not smtp_host:
        raise HTTPException(400, "SMTP host nincs beállítva")
    if not smtp_user:
        raise HTTPException(400, "SMTP felhasználónév nincs beállítva")

    to_addr = (row2._mapping["email"] if row2 and row2._mapping.get("email") else smtp_user)

    import smtplib
    from email.mime.text import MIMEText
    try:
        msg = MIMEText("CRT rendszer SMTP teszt email – minden OK.", "plain", "utf-8")
        msg["Subject"] = "CRT SMTP Teszt"
        msg["From"]    = smtp_from or smtp_user
        msg["To"]      = to_addr
        if use_tls:
            srv = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            srv.ehlo()
            srv.starttls()
        else:
            srv = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        if smtp_pass:
            srv.login(smtp_user, smtp_pass)
        srv.sendmail(smtp_user, [to_addr], msg.as_string())
        srv.quit()
        return {"status": "ok", "message": f"Teszt email elküldve: {to_addr}"}
    except Exception as e:
        raise HTTPException(500, f"SMTP hiba: {e}")


@app.get("/ollama/status")
async def ollama_status(_auth: dict = Depends(require_auth)):
    """Ollama LLM elérhetőség + elérhető modellek"""
    from sqlalchemy import text as _text
    url = "http://localhost:11434"
    try:
        with engine.connect() as conn:
            row = conn.execute(_text(
                "SELECT value FROM system_config WHERE key='ollama_url'"
            )).fetchone()
            if row:
                url = row[0]
    except Exception:
        pass
    return ai_motor.ollama_status(url)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
