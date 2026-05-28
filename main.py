"""
CRT Ajánlatsegéd – Backend Gerinc v0.2
Indítás: py -3.11 -m uvicorn main:app --reload
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import ntplib, logging, uuid, json, os, re

# ── IDŐ ───────────────────────────────────────────────────
CET  = timezone(timedelta(hours=1))
CEST = timezone(timedelta(hours=2))

def local_now(utc_dt=None):
    if utc_dt is None:
        utc_dt = datetime.utcnow()
    tz = CEST if 3 <= utc_dt.month <= 10 else CET
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz)

# ── LOGGING ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("crt.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("CRT")

# ── ADATBÁZIS ─────────────────────────────────────────────
DB_URL = "postgresql://crt_user:crt2026@localhost:5432/crt"

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
    version="0.2",
    description="Civil Rendszertechnika Kft. – AI alapú ajánlatkészítő"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
@app.on_event("startup")
async def startup():
    log.info("CRT Backend indul...")
    if db_ping():
        log.info("✅ PostgreSQL kapcsolat OK")
    else:
        log.error("❌ PostgreSQL nem elérhető!")

# ── ENDPOINTOK ────────────────────────────────────────────

@app.get("/", response_model=PingResponse)
async def root():
    """Rendszer életjel"""
    t  = ntp_now()
    db = "ok" if db_ping() else "hiba"
    return {
        "status":   "ok",
        "version":  "0.2",
        "time_ntp": t.strftime("%Y-%m-%d %H:%M:%S CEST"),
        "db":       db,
        "message":  "CRT Ajánlatsegéd – Dzseppettó műhelye kész 🪵"
    }

@app.get("/health")
async def health():
    return {
        "server":  "ok",
        "ntp":     ntp_now().strftime("%H:%M:%S CEST"),
        "db":      "ok" if db_ping() else "hiba",
        "version": "0.2"
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
async def cikktorzs_tree():
    """Kategória fa termékekkel és tevékenységekkel, utolsó ár időbélyeggel"""
    try:
        with engine.connect() as conn:
            cats = conn.execute(text(
                "SELECT category_id, parent_id, name, item_class, sort_order "
                "FROM categories WHERE active = true ORDER BY sort_order, name"
            )).fetchall()

            prods = conn.execute(text(
                "SELECT p.item_id, p.name, p.category_id, p.manufacturer, p.unit, "
                "p.created_at, p.status, MAX(pr.db_inserted) AS last_price "
                "FROM products p "
                "LEFT JOIN prices pr ON pr.item_id = p.item_id "
                "WHERE p.status = 'active' "
                "GROUP BY p.item_id ORDER BY p.name"
            )).fetchall()

            acts = conn.execute(text(
                "SELECT a.activity_id, a.name, a.category_id, a.unit_type, "
                "a.created_at, a.status, MAX(pr.db_inserted) AS last_price "
                "FROM activities a "
                "LEFT JOIN prices pr ON pr.item_id = a.activity_id "
                "WHERE a.status = 'active' "
                "GROUP BY a.activity_id ORDER BY a.name"
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
async def cikktorzs_search(q: str = "", tipus: str = "mind"):
    """Névben / gyártóban keres – min. 2 karakter"""
    if len(q) < 2:
        return {"results": [], "count": 0}
    try:
        with engine.connect() as conn:
            results = []
            if tipus in ("mind", "termek"):
                rows = conn.execute(text(
                    "SELECT item_id, name, manufacturer, unit, created_at, 'termék' AS tipus "
                    "FROM products WHERE status='active' "
                    "AND (LOWER(name) LIKE LOWER(:q) OR LOWER(COALESCE(manufacturer,'')) LIKE LOWER(:q)) "
                    "ORDER BY name LIMIT 25"
                ), {"q": f"%{q}%"}).fetchall()
                results += [dict(r._mapping) for r in rows]
            if tipus in ("mind", "tevekenyseg"):
                rows = conn.execute(text(
                    "SELECT activity_id AS item_id, name, '' AS manufacturer, unit_type AS unit, "
                    "created_at, 'tevékenység' AS tipus "
                    "FROM activities WHERE status='active' AND LOWER(name) LIKE LOWER(:q) "
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


@app.post("/cikktorzs/upload")
async def cikktorzs_upload(file: UploadFile = File(...)):
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
async def identify_items(payload: dict):
    """AI alapú termék azonosítás – Claude API"""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise HTTPException(400, "anthropic csomag hiányzik – telepítés: py -3.11 -m pip install anthropic")

    items = payload.get("items", [])
    if not items:
        return {"results": []}

    api_key = None
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT value FROM system_config WHERE key = 'claude_api_key'"
            )).fetchone()
            if row:
                api_key = row[0]
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(400, "Claude API kulcs nem beállítva (system_config: claude_api_key vagy ANTHROPIC_API_KEY env var)")

    client = Anthropic(api_key=api_key)
    items_text = "\n".join([f"{i+1}. {it}" for i, it in enumerate(items)])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""Te egy magyar villamossági és építési anyag azonosító szakértő vagy.
Az alábbi sorokat egy ajánlatkérő vagy szállítói dokumentumból olvastuk ki.
Azonosítsd az egyes tételeket és add vissza KIZÁRÓLAG JSON array formában.

Sorok:
{items_text}

Válasz formátuma (CSAK JSON, semmi más):
[
  {{"index": 1, "name": "tisztított megnevezés", "manufacturer": "gyártó vagy null", "unit": "db/m/kg/óra/stb", "category": "javasolt kategória magyarul", "confidence": 0.95}},
  ...
]

Szabályok:
- confidence: 0.0–1.0 (mennyire biztos az azonosítás)
- Ha bizonytalan (pl. rövidítés, hiányos adat): confidence < 0.55
- unit: legyen szabványos (db, m, fm, kg, l, óra, nap, csomag)
- category: legyen rövid és logikus (pl. Kábelek, Szerelvények, Munka, Szoftver)
- Ha az azonosítás egyáltalán nem lehetséges: confidence: 0.1"""
        }]
    )

    try:
        raw = response.content[0].text
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not m:
            raise ValueError("Nincs JSON array a válaszban")
        results = json.loads(m.group(0))
        used_tokens = response.usage.input_tokens + response.usage.output_tokens
        log.info(f"AI azonosítás: {len(items)} tétel, {used_tokens} token")
        return {"results": results, "tokens_used": used_tokens}
    except Exception as e:
        raise HTTPException(500, f"AI válasz feldolgozási hiba: {str(e)}")


@app.post("/cikktorzs/save")
async def save_items(payload: dict):
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
                            "(item_id, name, category_id, manufacturer, unit, created_at, created_by, status, version) "
                            "VALUES (:id, :name, :cat, :mfr, :unit, :now, :by, 'active', 1)"
                        ), {"id": item_id, "name": name,
                            "cat":  it.get("category_id"),
                            "mfr":  it.get("manufacturer"),
                            "unit": it.get("unit", "db"),
                            "now":  now, "by": user_id})
                    else:
                        conn.execute(text(
                            "INSERT INTO activities "
                            "(activity_id, name, category_id, unit_type, created_at, created_by, status, version) "
                            "VALUES (:id, :name, :cat, :unit, :now, :by, 'active', 1)"
                        ), {"id": item_id, "name": name,
                            "cat":  it.get("category_id"),
                            "unit": it.get("unit", "óra"),
                            "now":  now, "by": user_id})
                    saved += 1
                    log.info(f"Cikktörzs mentés: {name}")
                except Exception as e:
                    errors.append(f"{name}: {str(e)}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
