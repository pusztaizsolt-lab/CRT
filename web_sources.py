"""
CRT Ajánlatsegéd – Web Sources router v0.5
Nagykereskedői URL-ek, login adatok, Playwright scriptek kezelése
prefix: /web
Függőségek: auth.require_auth · require_admin
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from sqlalchemy import create_engine, text
from typing import Optional
import logging
import os
import tempfile
import shutil

from auth import require_auth, require_admin
from env_detect import get_db_url, get_encrypt_key

router = APIRouter(prefix="/web", tags=["web_sources"])
log    = logging.getLogger("CRT.web")

DB_URL = get_db_url()
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=3)


# ── MODELLEK ──────────────────────────────────────────────────

class SourceCreate(BaseModel):
    name:        str
    url:         str
    source_type: str = "public"   # public | login_required | api
    login_url:   Optional[str]  = None
    username:    Optional[str]  = None
    password:    Optional[str]  = None   # titkosítva tárolódik
    api_key:     Optional[str]  = None   # titkosítva tárolódik
    notes:       Optional[str]  = None

class SourceUpdate(BaseModel):
    name:        Optional[str]  = None
    source_type: Optional[str]  = None
    login_url:   Optional[str]  = None
    username:    Optional[str]  = None
    password:    Optional[str]  = None
    api_key:     Optional[str]  = None
    notes:       Optional[str]  = None
    status:      Optional[str]  = None   # new | reachable | learned | error | disabled

class ScriptStep(BaseModel):
    action:   str            # click | fill | navigate | wait | screenshot
    selector: Optional[str] = None
    value:    Optional[str] = None
    wait_ms:  Optional[int] = None

class ScriptSave(BaseModel):
    source_id:   int
    script_type: str = "login"   # login | navigate | extract | search
    steps:       list[ScriptStep]
    notes:       Optional[str] = None


# ── SEGÉDFÜGGVÉNYEK ───────────────────────────────────────────

def _encrypt(value: str) -> str:
    """Egyszerű XOR + base64 — valós deployban AES-256-GCM kell (CRT_ENCRYPT_KEY env)."""
    key = get_encrypt_key()
    encoded = bytes(
        b ^ ord(key[i % len(key)])
        for i, b in enumerate(value.encode())
    )
    import base64
    return "enc1:" + base64.b64encode(encoded).decode()


def _decrypt(value: str) -> str:
    if not value or not value.startswith("enc1:"):
        return value or ""
    import base64
    key = get_encrypt_key()
    raw = base64.b64decode(value[5:])
    return bytes(
        b ^ ord(key[i % len(key)])
        for i, b in enumerate(raw)
    ).decode()


def _row2dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, 'isoformat'):
            d[k] = v.isoformat()
    # Jelszó és API kulcs soha nem kerül ki plain-text-ben
    if 'password_enc' in d:
        d['has_password'] = bool(d.pop('password_enc'))
    if 'api_key_enc' in d:
        d['has_api_key'] = bool(d.pop('api_key_enc'))
    return d


# ── WEB SOURCES CRUD ──────────────────────────────────────────

@router.get("/sources")
async def list_sources(payload: dict = Depends(require_auth)):
    """Összes forrás lista (jelszavak nélkül)."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, url, source_type, status, "
            "last_reached, last_scraped, error_msg, notes, created_at, "
            "password_enc, api_key_enc "
            "FROM web_sources ORDER BY name"
        )).fetchall()
    return {"sources": [_row2dict(r) for r in rows], "total": len(rows)}


@router.get("/sources/{source_id}")
async def get_source(source_id: int, payload: dict = Depends(require_auth)):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, name, url, source_type, login_url, username, "
            "status, last_reached, last_scraped, error_msg, notes, created_at, "
            "password_enc, api_key_enc "
            "FROM web_sources WHERE id=:id"
        ), {"id": source_id}).fetchone()
    if not row:
        raise HTTPException(404, "Forrás nem található")
    return _row2dict(row)


@router.post("/sources")
async def create_source(body: SourceCreate, payload: dict = Depends(require_admin)):
    """Új forrás létrehozása — admin jog szükséges."""
    pwd_enc = _encrypt(body.password) if body.password else None
    key_enc = _encrypt(body.api_key)  if body.api_key  else None
    try:
        with engine.begin() as conn:
            row = conn.execute(text(
                "INSERT INTO web_sources "
                "(name, url, source_type, login_url, username, password_enc, api_key_enc, "
                " notes, status, created_by, created_at) "
                "VALUES (:name,:url,:stype,:lurl,:uname,:pwd,:key,:notes,'new',:uid,NOW()) "
                "RETURNING id"
            ), {
                "name":  body.name.strip(),
                "url":   body.url.strip(),
                "stype": body.source_type,
                "lurl":  body.login_url,
                "uname": body.username,
                "pwd":   pwd_enc,
                "key":   key_enc,
                "notes": body.notes,
                "uid":   payload["user_id"],
            }).fetchone()
        log.info("Új web source: %s (id=%d, admin=%s)", body.name, row[0], payload["username"])
        return {"status": "ok", "id": row[0]}
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(400, "Ez az URL már szerepel")
        raise HTTPException(500, f"Hiba: {e}")


@router.patch("/sources/{source_id}")
async def update_source(source_id: int, body: SourceUpdate,
                        payload: dict = Depends(require_admin)):
    updates, params = [], {"id": source_id}
    if body.name        is not None: updates.append("name=:name");            params["name"]  = body.name.strip()
    if body.source_type is not None: updates.append("source_type=:stype");    params["stype"] = body.source_type
    if body.login_url   is not None: updates.append("login_url=:lurl");       params["lurl"]  = body.login_url
    if body.username    is not None: updates.append("username=:uname");       params["uname"] = body.username
    if body.notes       is not None: updates.append("notes=:notes");          params["notes"] = body.notes
    if body.status      is not None: updates.append("status=:status");        params["status"]= body.status
    if body.password    is not None:
        updates.append("password_enc=:pwd")
        params["pwd"] = _encrypt(body.password) if body.password else None
    if body.api_key     is not None:
        updates.append("api_key_enc=:key")
        params["key"] = _encrypt(body.api_key) if body.api_key else None
    if not updates:
        raise HTTPException(400, "Nincs módosítandó adat")
    updates.append("updated_at=NOW()")
    with engine.begin() as conn:
        conn.execute(text(
            f"UPDATE web_sources SET {', '.join(updates)} WHERE id=:id"
        ), params)
    return {"status": "ok"}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, payload: dict = Depends(require_admin)):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM web_sources WHERE id=:id"), {"id": source_id})
    log.info("Web source törölve: id=%d (admin=%s)", source_id, payload["username"])
    return {"status": "ok"}


# ── ELÉRHETŐSÉG ELLENŐRZÉS ────────────────────────────────────

@router.post("/sources/{source_id}/ping")
async def ping_source(source_id: int, payload: dict = Depends(require_auth)):
    """HTTP GET-tel ellenőrzi az URL elérhetőségét."""
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT url FROM web_sources WHERE id=:id"
        ), {"id": source_id}).fetchone()
    if not row:
        raise HTTPException(404, "Forrás nem található")

    url = row[0]
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CRT-Bot/0.5 (+http://localhost:8000)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            ok = resp.status < 400
            status_code = resp.status
    except Exception as e:
        ok = False
        status_code = 0
        log.warning("Ping hiba [%s]: %s", url, e)

    with engine.begin() as conn:
        if ok:
            conn.execute(text(
                "UPDATE web_sources SET status='reachable', last_reached=NOW(), "
                "error_msg=NULL, updated_at=NOW() WHERE id=:id"
            ), {"id": source_id})
        else:
            conn.execute(text(
                "UPDATE web_sources SET status='error', "
                "error_msg=:err, updated_at=NOW() WHERE id=:id"
            ), {"id": source_id, "err": f"HTTP {status_code} – nem elérhető"})

    return {
        "reachable":   ok,
        "status_code": status_code,
        "url":         url,
    }


# ── PLAYWRIGHT SCRIPTEK ───────────────────────────────────────

@router.get("/sources/{source_id}/scripts")
async def list_scripts(source_id: int, payload: dict = Depends(require_auth)):
    """Forráshoz tartozó scriptek listája."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, script_type, version, active, recorded_at, "
            "last_run, last_run_ok, run_count, notes "
            "FROM web_scripts WHERE source_id=:sid ORDER BY script_type, version DESC"
        ), {"sid": source_id}).fetchall()
    return {"scripts": [_row2dict(r) for r in rows]}


@router.get("/scripts/{script_id}")
async def get_script(script_id: int, payload: dict = Depends(require_auth)):
    """Script lépései (a Tanít gomb által rögzített szekvencia)."""
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, source_id, script_type, version, active, "
            "script_json, recorded_at, last_run, last_run_ok, run_count, notes "
            "FROM web_scripts WHERE id=:id"
        ), {"id": script_id}).fetchone()
    if not row:
        raise HTTPException(404, "Script nem található")
    return _row2dict(row)


@router.post("/scripts")
async def save_script(body: ScriptSave, payload: dict = Depends(require_auth)):
    """
    Tanít gomb által rögzített Playwright lépések mentése.
    Automatikusan deaktiválja az előző azonos típusú scriptet.
    """
    import json

    steps_json = json.dumps([s.model_dump() for s in body.steps])

    with engine.begin() as conn:
        # Előző aktív script deaktiválása
        conn.execute(text(
            "UPDATE web_scripts SET active=false "
            "WHERE source_id=:sid AND script_type=:stype AND active=true"
        ), {"sid": body.source_id, "stype": body.script_type})

        # Új verzió számának meghatározása
        ver_row = conn.execute(text(
            "SELECT COALESCE(MAX(version),0)+1 FROM web_scripts "
            "WHERE source_id=:sid AND script_type=:stype"
        ), {"sid": body.source_id, "stype": body.script_type}).fetchone()
        next_ver = ver_row[0]

        row = conn.execute(text(
            "INSERT INTO web_scripts "
            "(source_id, script_type, version, active, script_json, "
            " recorded_by, recorded_at, notes) "
            "VALUES (:sid,:stype,:ver,true,:json::jsonb,:uid,NOW(),:notes) "
            "RETURNING id"
        ), {
            "sid":   body.source_id,
            "stype": body.script_type,
            "ver":   next_ver,
            "json":  steps_json,
            "uid":   payload["user_id"],
            "notes": body.notes,
        }).fetchone()

        # Forrás státuszát "learned"-re állítja ha legalább 1 aktív script van
        conn.execute(text(
            "UPDATE web_sources SET status='learned', updated_at=NOW() "
            "WHERE id=:sid"
        ), {"sid": body.source_id})

    log.info("Script rögzítve: source=%d type=%s ver=%d lépés=%d (user=%s)",
             body.source_id, body.script_type, next_ver,
             len(body.steps), payload["username"])

    return {"status": "ok", "script_id": row[0], "version": next_ver}


@router.delete("/scripts/{script_id}")
async def delete_script(script_id: int, payload: dict = Depends(require_admin)):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM web_scripts WHERE id=:id"), {"id": script_id})
    return {"status": "ok"}


@router.post("/scripts/{script_id}/run")
async def run_script(script_id: int, payload: dict = Depends(require_auth)):
    """
    Playwright script futtatása – ténylegesen böngészőt indít, árakat gyűjt.
    A rögzített lépések alapján navigál, kitölti a keresőmezőket, majd
    az 'extract' lépéseknél a találatokat a web_prices táblába menti.
    """
    import json as _json
    import re

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(400, "playwright csomag hiányzik – pip install playwright && playwright install chromium")

    # Script + forrás adatok
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ws.id, ws.source_id, ws.script_type, ws.script_json, ws.version, "
            "src.url, src.username, src.password_enc "
            "FROM web_scripts ws "
            "JOIN web_sources src ON src.id = ws.source_id "
            "WHERE ws.id = :id"
        ), {"id": script_id}).fetchone()

    if not row:
        raise HTTPException(404, "Script nem található")

    script_data = dict(row._mapping)
    steps       = _json.loads(script_data["script_json"] or "[]")
    password    = _decrypt(script_data["password_enc"] or "")
    source_id   = script_data["source_id"]

    extracted  = []
    errors     = []
    prices_saved = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page    = await browser.new_page()
        page.set_default_timeout(15_000)

        try:
            for step in steps:
                action   = step.get("action", "")
                selector = step.get("selector") or ""
                value    = step.get("value") or ""
                wait_ms  = step.get("wait_ms") or 500

                if action == "navigate":
                    await page.goto(value or script_data["url"])

                elif action == "click":
                    await page.click(selector)

                elif action == "fill":
                    fill_value = password if value == "__password__" else value
                    await page.fill(selector, fill_value)

                elif action == "wait":
                    await page.wait_for_timeout(wait_ms)

                elif action == "wait_selector":
                    await page.wait_for_selector(selector)

                elif action == "screenshot":
                    pass  # diagnosztikai lépés – nem mentjük

                elif action == "extract":
                    # Árak kinyerése a megadott CSS selectorral
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        raw = (await el.inner_text()).strip()
                        if not raw:
                            continue
                        extracted.append(raw[:300])

                        # Ár szám kinyerése (pl. "1 234,50 Ft" → 1234.50)
                        cleaned = re.sub(r'[^\d,.]', '', raw.replace('\xa0', '').replace(' ', ''))
                        price_match = re.search(r'\d+[,.]?\d*', cleaned)
                        if price_match:
                            try:
                                price_val = float(price_match.group(0).replace(',', '.'))
                                with engine.begin() as conn:
                                    conn.execute(text(
                                        "INSERT INTO web_prices "
                                        "(source_id, raw_name, raw_price, currency, scraped_at) "
                                        "VALUES (:sid, :name, :price, 'HUF', NOW())"
                                    ), {
                                        "sid":   source_id,
                                        "name":  raw[:500],
                                        "price": price_val,
                                    })
                                prices_saved += 1
                            except Exception as e:
                                errors.append(f"parse: {raw[:60]}: {e}")

        except Exception as e:
            errors.append(f"script hiba: {e}")
            log.warning("Playwright script hiba (id=%d): %s", script_id, e)
        finally:
            await browser.close()

    success = not errors
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE web_scripts SET "
            "last_run=NOW(), last_run_ok=:ok, run_count=COALESCE(run_count,0)+1 "
            "WHERE id=:id"
        ), {"ok": success, "id": script_id})
        if prices_saved > 0:
            conn.execute(text(
                "UPDATE web_sources SET last_scraped=NOW(), updated_at=NOW() WHERE id=:id"
            ), {"id": source_id})

    log.info("Script futtatva: id=%d lépés=%d ár=%d ok=%s user=%s",
             script_id, len(steps), prices_saved, success, payload["username"])

    return {
        "status":          "ok" if success else "partial",
        "steps_executed":  len(steps),
        "prices_saved":    prices_saved,
        "extracted_count": len(extracted),
        "extracted":       extracted[:50],
        "errors":          errors[:20],
    }


# ── WEB PRICES (csak olvasás — scraper tölti fel) ─────────────

@router.get("/prices")
async def list_web_prices(
    source_id: Optional[int] = None,
    matched:   Optional[bool] = None,
    limit:     int = 100,
    payload: dict = Depends(require_auth)
):
    """Weboldalakról begyűjtött árak listája."""
    conditions = []
    params: dict = {"limit": min(limit, 500)}
    if source_id is not None:
        conditions.append("source_id=:sid")
        params["sid"] = source_id
    if matched is not None:
        conditions.append("matched=:matched")
        params["matched"] = matched

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT id, source_id, item_id, raw_name, raw_price, currency, "
            f"unit, manufacturer, scraped_at, matched, match_confidence "
            f"FROM web_prices {where} "
            f"ORDER BY scraped_at DESC LIMIT :limit"
        ), params).fetchall()

    return {"prices": [_row2dict(r) for r in rows], "count": len(rows)}


# ── WEB PRICE MATCHING → GOLDEN PIPELINE ─────────────────────
#
# Attention layer wiring:
# web_prices.matched = true  →  golden_examples (LoRA tanítóadat)
#
# Lánc: scraper/feltöltés → web_prices (raw) → PATCH /match →
#        web_prices.matched=true + golden_examples INSERT → LoRA export

@router.patch("/prices/{price_id}/match")
async def match_web_price(
    price_id: int,
    body:     dict,
    payload:  dict = Depends(require_auth),
):
    """
    Manuális vagy AI-vezérelt egyeztetés: web_price → cikktörzs tétel.

    Body: { "item_id": "<uuid>", "confidence": 0.0–1.0 }

    Ha confidence >= 0.75: automatikusan golden_example-t is létrehoz.
    Ez zárja le az attention loop-ot:
      web scraping → raw_name → egyeztetés → golden tanítóadat → LoRA
    """
    item_id    = (body.get("item_id") or "").strip()
    confidence = float(body.get("confidence", 1.0))

    if not item_id:
        raise HTTPException(400, "item_id kötelező")
    if not (0.0 <= confidence <= 1.0):
        raise HTTPException(400, "confidence: 0.0–1.0")

    with engine.connect() as conn:
        # Lekérjük a web_prices sort
        wp = conn.execute(text(
            "SELECT id, source_id, raw_name, raw_price, currency, unit, manufacturer "
            "FROM web_prices WHERE id = :id"
        ), {"id": price_id}).fetchone()
        if not wp:
            raise HTTPException(404, "web_price nem található")

        # Lekérjük a cikktörzs tétel clean nevét
        prod = conn.execute(text(
            "SELECT item_id, name, unit FROM products WHERE item_id = :id AND active = true"
        ), {"id": item_id}).fetchone()
        if not prod:
            prod = conn.execute(text(
                "SELECT item_id, name, unit FROM activities WHERE item_id = :id AND active = true"
            ), {"id": item_id}).fetchone()
        if not prod:
            raise HTTPException(404, f"Cikktörzs tétel nem található: {item_id}")

        clean_name = prod[1]
        item_unit  = prod[2]

    try:
        with engine.begin() as conn:
            # 1. web_prices frissítése
            conn.execute(text(
                "UPDATE web_prices "
                "SET matched = true, item_id = :iid, match_confidence = :conf "
                "WHERE id = :pid"
            ), {"iid": item_id, "conf": confidence, "pid": price_id})

            golden_id = None

            # 2. Ha elég magas a konfidencia → golden_examples automatikus feltöltés
            if confidence >= 0.75:
                mfr = wp[6] or None
                row = conn.execute(text(
                    "INSERT INTO golden_examples "
                    "(item_id, raw_text, clean_name, manufacturer, unit, source, created_by, created_at) "
                    "VALUES (:iid, :raw, :name, :mfr, :unit, 'web_price_match', :by, NOW()) "
                    "RETURNING id"
                ), {
                    "iid":  item_id,
                    "raw":  (wp[2] or "")[:500],
                    "name": clean_name,
                    "mfr":  mfr,
                    "unit": item_unit,
                    "by":   payload.get("username", "system"),
                }).fetchone()
                golden_id = row[0]

        log.info(
            "web_price #%d → item_id=%s conf=%.2f golden=%s user=%s",
            price_id, item_id, confidence,
            golden_id or "skip (<0.75)", payload["username"]
        )
        return {
            "status":     "ok",
            "price_id":   price_id,
            "item_id":    item_id,
            "confidence": confidence,
            "golden_id":  golden_id,
            "golden_created": golden_id is not None,
        }

    except Exception as e:
        raise HTTPException(500, f"Match hiba: {e}")


@router.post("/prices/match-batch")
async def match_web_prices_batch(
    body:    dict,
    payload: dict = Depends(require_auth),
):
    """
    Batch egyeztetés: [{"price_id": N, "item_id": "...", "confidence": 0.9}, ...]
    Minden elemet feldolgoz, minden confidence >= 0.75 sor golden_example lesz.
    """
    items = body.get("matches", [])
    if not items:
        return {"matched": 0, "golden_created": 0}

    matched_count = 0
    golden_count  = 0

    for m in items:
        try:
            pid  = int(m["price_id"])
            iid  = str(m["item_id"]).strip()
            conf = float(m.get("confidence", 1.0))
            if not iid or not (0.0 <= conf <= 1.0):
                continue

            with engine.connect() as conn:
                wp = conn.execute(text(
                    "SELECT raw_name, manufacturer, unit FROM web_prices WHERE id = :id"
                ), {"id": pid}).fetchone()
                if not wp:
                    continue
                prod = conn.execute(text(
                    "SELECT name, unit FROM products WHERE item_id = :id AND active = true"
                ), {"id": iid}).fetchone()
                if not prod:
                    prod = conn.execute(text(
                        "SELECT name, unit FROM activities WHERE item_id = :id AND active = true"
                    ), {"id": iid}).fetchone()
                if not prod:
                    continue
                clean_name = prod[0]
                unit       = prod[1]

            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE web_prices SET matched=true, item_id=:iid, match_confidence=:conf WHERE id=:pid"
                ), {"iid": iid, "conf": conf, "pid": pid})
                matched_count += 1

                if conf >= 0.75:
                    conn.execute(text(
                        "INSERT INTO golden_examples "
                        "(item_id, raw_text, clean_name, manufacturer, unit, source, created_by, created_at) "
                        "VALUES (:iid, :raw, :name, :mfr, :unit, 'web_price_match', :by, NOW())"
                    ), {
                        "iid":  iid,
                        "raw":  (wp[0] or "")[:500],
                        "name": clean_name,
                        "mfr":  wp[1],
                        "unit": unit,
                        "by":   payload.get("username", "system"),
                    })
                    golden_count += 1

        except Exception as e:
            log.warning("Batch match hiba (price_id=%s): %s", m.get("price_id"), e)
            continue

    log.info("Batch match: %d egyeztetve, %d golden létrehozva (%s)",
             matched_count, golden_count, payload["username"])
    return {"matched": matched_count, "golden_created": golden_count}


# ── AI TANÍTÁS PIPE ──────────────────────────────────────────
#
# POST /web/prices/ai-suggest  — Claude (vagy Ollama) javasol egyezést
# POST /web/prices/ai-commit   — felhasználó által jóváhagyott javaslatok rögzítése
#
# Ha Claude API nincs vagy kiesik → csendesen Ollama öntanulás módra vált
# confidence >= 0.75 → automatikusan golden_example is keletkezik

_MATCH_PROMPT = """Magyar villamossági és építőipari szállítói árlisták egyeztetése termékkatalógussal.

TERMÉKKATALÓGUS:
{catalog}

EGYEZTETENDŐ SZÁLLÍTÓI TÉTELEK:
{prices}

Minden szállítói tételhez add meg a legjobb katalógusbeli egyezést.
- Ha nincs megfelelő tétel (confidence < 0.60): item_id = null
- Ha bizonytalan (0.60–0.84): adj rövid, magyarul megfogalmazott kérdést (question mező)
- Ha biztos (>= 0.85): question = null

Válasz KIZÁRÓLAG JSON array, semmi magyarázat:
[
  {{"price_id": 1, "item_id": "uuid-vagy-null", "confidence": 0.95, "question": null}},
  ...
]"""


@router.post("/prices/ai-suggest")
async def ai_suggest_matches(body: dict, payload: dict = Depends(require_auth)):
    """
    Claude Haiku vagy Ollama javaslatot ad unmatched web_prices-ekhez.
    Ha Claude API nem elérhető: csendesen Ollama öntanulás módra vált (nincs hiba, nincs villogás).
    Nem commitál — a /prices/ai-commit végpont rögzíti jóváhagyás után.
    """
    limit = min(int(body.get("limit", 20)), 50)

    with engine.connect() as conn:
        price_rows = conn.execute(text(
            "SELECT id, raw_name, raw_price, currency "
            "FROM web_prices WHERE (matched IS NULL OR matched = false) "
            "AND raw_name IS NOT NULL AND raw_name != '' "
            "ORDER BY scraped_at DESC LIMIT :limit"
        ), {"limit": limit}).fetchall()

        if not price_rows:
            return {"suggestions": [], "motor": "none", "reason": "Nincs egyeztetetlen ár"}

        prod_rows = conn.execute(text(
            "SELECT item_id, name, unit FROM products WHERE active = true ORDER BY name LIMIT 150"
        )).fetchall()
        act_rows = conn.execute(text(
            "SELECT item_id, name, unit FROM activities WHERE active = true ORDER BY name LIMIT 80"
        )).fetchall()

        cfg_rows = conn.execute(text(
            "SELECT key, value FROM system_config "
            "WHERE key IN ('claude_api_key','ollama_url','ollama_model')"
        )).fetchall()
        cfg = {r[0]: r[1] for r in cfg_rows}

    claude_key   = cfg.get("claude_api_key") or ""
    ollama_url   = cfg.get("ollama_url") or "http://localhost:11434"
    ollama_model = cfg.get("ollama_model") or "llama3:8b"

    catalog = [{"item_id": r[0], "name": r[1], "unit": r[2]}
               for r in list(prod_rows) + list(act_rows)]
    prices  = [{"price_id": r[0], "raw_name": r[1],
                "raw_price": float(r[2] or 0), "currency": r[3]}
               for r in price_rows]

    catalog_text = "\n".join(f"{c['item_id']} | {c['name']} [{c['unit']}]" for c in catalog)
    prices_text  = "\n".join(
        f"{p['price_id']}. {p['raw_name']} ({p['raw_price']} {p['currency']})"
        for p in prices
    )
    prompt = _MATCH_PROMPT.format(catalog=catalog_text, prices=prices_text)

    motor, suggestions = "none", []

    # ── 1. Claude Haiku ──────────────────────────────────────────
    if claude_key.strip():
        try:
            from anthropic import Anthropic as _Ant
            import json as _j, re as _re
            resp = _Ant(api_key=claude_key).messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            m = _re.search(r'\[.*\]', resp.content[0].text, _re.DOTALL)
            if m:
                suggestions = _j.loads(m.group(0))
                motor = "claude"
        except Exception as e:
            log.info("Claude suggest nem elérhető (%s) — Ollama öntanulás", e)

    # ── 2. Ollama fallback — csendesen, nem hiba ─────────────────
    if not suggestions:
        try:
            import httpx as _hx, json as _j, re as _re
            r = _hx.post(
                f"{ollama_url}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": 2048, "temperature": 0.1}},
                timeout=90.0,
            )
            if r.status_code == 200:
                m = _re.search(r'\[.*\]', r.json().get("response", ""), _re.DOTALL)
                if m:
                    suggestions = _j.loads(m.group(0))
                    motor = "ollama"
        except Exception as e:
            log.warning("Ollama suggest hiba: %s", e)

    catalog_map = {c["item_id"]: c for c in catalog}
    price_map   = {p["price_id"]: p for p in prices}

    result = []
    for s in suggestions:
        pid  = s.get("price_id")
        iid  = s.get("item_id")
        conf = min(max(float(s.get("confidence", 0)), 0.0), 1.0)
        cat  = catalog_map.get(iid or "")
        result.append({
            "price_id":       pid,
            "raw_name":       price_map.get(pid, {}).get("raw_name", ""),
            "raw_price":      price_map.get(pid, {}).get("raw_price", 0),
            "item_id":        iid,
            "suggested_name": cat["name"] if cat else None,
            "suggested_unit": cat["unit"] if cat else None,
            "confidence":     conf,
            "question":       s.get("question"),
            "auto_ok":        conf >= 0.90 and not s.get("question") and iid,
        })

    return {
        "suggestions":    result,
        "motor":          motor,
        "self_learn":     motor == "ollama",
        "total":          len(result),
        "unmatched_total": len(price_rows),
    }


@router.post("/prices/ai-commit")
async def ai_commit_matches(body: dict, payload: dict = Depends(require_auth)):
    """
    Felhasználó által jóváhagyott javaslatok rögzítése.
    approvals: [{price_id, item_id, confidence, accepted}]
    accepted=true  → web_prices.matched=true + golden_example (ha conf>=0.75)
    accepted=false → kihagyás
    """
    approvals = body.get("approvals", [])
    committed = golden = skipped = 0

    for a in approvals:
        if not a.get("accepted"):
            skipped += 1
            continue
        pid  = int(a["price_id"])
        iid  = (a.get("item_id") or "").strip()
        conf = min(max(float(a.get("confidence", 1.0)), 0.0), 1.0)
        if not iid:
            skipped += 1
            continue
        try:
            with engine.connect() as conn:
                wp = conn.execute(text(
                    "SELECT raw_name, manufacturer, unit FROM web_prices WHERE id = :id"
                ), {"id": pid}).fetchone()
                if not wp:
                    continue
                prod = (
                    conn.execute(text(
                        "SELECT name, unit FROM products WHERE item_id=:id AND active=true"
                    ), {"id": iid}).fetchone() or
                    conn.execute(text(
                        "SELECT name, unit FROM activities WHERE item_id=:id AND active=true"
                    ), {"id": iid}).fetchone()
                )
                if not prod:
                    continue

            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE web_prices SET matched=true, item_id=:iid, "
                    "match_confidence=:conf WHERE id=:pid"
                ), {"iid": iid, "conf": conf, "pid": pid})
                committed += 1

                if conf >= 0.75:
                    conn.execute(text(
                        "INSERT INTO golden_examples "
                        "(item_id, raw_text, clean_name, manufacturer, unit, "
                        " source, created_by, created_at) "
                        "VALUES (:iid, :raw, :name, :mfr, :unit, 'ai_teach', :by, NOW())"
                    ), {
                        "iid":  iid, "raw": (wp[0] or "")[:500],
                        "name": prod[0], "mfr": wp[1], "unit": prod[1],
                        "by":   payload.get("username", "system"),
                    })
                    golden += 1

        except Exception as e:
            log.warning("ai-commit hiba (pid=%s): %s", a.get("price_id"), e)

    log.info("AI commit: %d egyeztetve, %d golden, %d kihagyva (%s)",
             committed, golden, skipped, payload["username"])
    return {"committed": committed, "golden_created": golden, "skipped": skipped}


# ── DOKUMENTUM FELTÖLTÉS (PUSH csatorna) ──────────────────────

ALLOWED_EXT = {".xlsx", ".xls", ".xlsm", ".pdf", ".docx", ".doc"}

@router.post("/upload")
async def upload_price_list(
    file:      UploadFile = File(...),
    source_id: Optional[int] = Form(None),
    payload:   dict = Depends(require_auth)
):
    """
    PUSH csatorna: szállítói Excel/PDF/Word árlista feltöltés.
    Az AI (llama3:8b) kinyeri a termékeket és árakat → web_prices tábla.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scrapers.ai_extractor import extract_from_file

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Nem támogatott formátum: {ext}. Elfogadott: {', '.join(sorted(ALLOWED_EXT))}")

    # Ideiglenes fájl mentése
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        log.info("Dokumentum feltöltés: %s (%s) user=%s", file.filename, ext, payload["username"])
        products = extract_from_file(tmp_path)
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(500, f"Kinyerési hiba: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not products:
        return {"status": "ok", "saved": 0, "message": "Nem található termék a dokumentumban"}

    # Forrás: ha nincs megadva, létrehozunk egyet a fájl neve alapján
    if source_id is None:
        with engine.begin() as conn:
            row = conn.execute(text(
                "INSERT INTO web_sources (name, url, source_type, status, created_at) "
                "VALUES (:n, :u, 'document', 'reachable', NOW()) RETURNING id"
            ), {"n": file.filename[:200], "u": f"file://{file.filename}"}).fetchone()
            source_id = row[0]

    saved = 0
    with engine.begin() as conn:
        for p in products:
            conn.execute(text(
                "INSERT INTO web_prices "
                "(source_id, raw_name, raw_price, currency, unit, scraped_at) "
                "VALUES (:sid, :name, :price, 'HUF', 'db', NOW())"
            ), {"sid": source_id, "name": f"[DOC] {p['name']}"[:500], "price": p["price"]})
            saved += 1

    log.info("Dokumentum feldolgozva: %s → %d ár mentve (source_id=%d)", file.filename, saved, source_id)
    return {
        "status":    "ok",
        "filename":  file.filename,
        "source_id": source_id,
        "saved":     saved,
        "products":  products[:20],
    }
