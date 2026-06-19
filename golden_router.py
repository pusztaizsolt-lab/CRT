"""
CRT Ajánlatsegéd – Golden Examples router v0.7
Tanítóadat gyűjtés: AI azonosítás jóváhagyásakor automatikusan mentődik
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, text
from auth import require_auth
import io, csv as csv_mod, json, logging, os
from env_detect import get_db_url

router = APIRouter(prefix="/golden", tags=["golden"])
log    = logging.getLogger("CRT.golden")

DB_URL = get_db_url()
engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=2)


def _r2d(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# ── MENTÉS ────────────────────────────────────────────────────

@router.post("")
async def save_golden(payload: dict, _auth: dict = Depends(require_auth)):
    """Egy golden example mentése"""
    raw_text = (payload.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(400, "raw_text kötelező")
    try:
        with engine.begin() as conn:
            row = conn.execute(text(
                "INSERT INTO golden_examples "
                "(item_id, raw_text, clean_name, manufacturer, category, unit, source, created_by, created_at) "
                "VALUES (:iid, :raw, :name, :mfr, :cat, :unit, :src, :by, NOW()) "
                "RETURNING id"
            ), {
                "iid":  payload.get("item_id"),
                "raw":  raw_text,
                "name": (payload.get("clean_name") or payload.get("name") or "").strip(),
                "mfr":  payload.get("manufacturer"),
                "cat":  payload.get("category"),
                "unit": payload.get("unit"),
                "src":  payload.get("source", "ai_accepted"),
                "by":   _auth.get("username"),
            }).fetchone()
        return {"id": row[0], "status": "saved"}
    except Exception as e:
        raise HTTPException(500, f"Mentési hiba: {e}")


@router.post("/batch")
async def save_golden_batch(payload: dict, _auth: dict = Depends(require_auth)):
    """
    Batch golden example mentés.
    Hívja: ajanlatkezelo.html → acceptAll() után automatikusan.
    examples: [{raw_text, clean_name, manufacturer, category, unit, item_id?}, ...]
    """
    examples = payload.get("examples", [])
    if not examples:
        return {"saved": 0}

    saved = 0
    try:
        with engine.begin() as conn:
            for ex in examples:
                raw = (ex.get("raw_text") or "").strip()
                if not raw:
                    continue
                conn.execute(text(
                    "INSERT INTO golden_examples "
                    "(item_id, raw_text, clean_name, manufacturer, category, unit, source, created_by, created_at) "
                    "VALUES (:iid, :raw, :name, :mfr, :cat, :unit, :src, :by, NOW())"
                ), {
                    "iid":  ex.get("item_id"),
                    "raw":  raw,
                    "name": (ex.get("clean_name") or ex.get("name") or "").strip(),
                    "mfr":  ex.get("manufacturer"),
                    "cat":  ex.get("category"),
                    "unit": ex.get("unit"),
                    "src":  ex.get("source", "ai_accepted"),
                    "by":   _auth.get("username"),
                })
                saved += 1
        log.info("Golden batch: %d példa mentve (%s)", saved, _auth.get("username"))
        return {"saved": saved}
    except Exception as e:
        raise HTTPException(500, f"Batch hiba: {e}")


# ── LISTÁZÁS ──────────────────────────────────────────────────

@router.get("")
async def list_golden(
    q:      str = "",
    source: str = "",
    limit:  int = 50,
    offset: int = 0,
    _auth: dict = Depends(require_auth),
):
    """Golden examples listázása szűrőkkel"""
    limit  = min(max(limit, 1), 500)
    offset = max(offset, 0)

    conds, params = [], {"limit": limit, "offset": offset}
    if q:
        conds.append(
            "(LOWER(raw_text) LIKE LOWER(:q) "
            "OR LOWER(COALESCE(clean_name,'')) LIKE LOWER(:q))"
        )
        params["q"] = f"%{q}%"
    if source:
        conds.append("source = :source")
        params["source"] = source

    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    try:
        with engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM golden_examples {where}"), params
            ).fetchone()[0]
            rows = conn.execute(text(
                f"SELECT id, item_id, raw_text, clean_name, manufacturer, "
                f"category, unit, source, created_at, created_by "
                f"FROM golden_examples {where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ), params).fetchall()
        return {
            "examples": [_r2d(r) for r in rows],
            "total":    total,
            "limit":    limit,
            "offset":   offset,
        }
    except Exception as e:
        raise HTTPException(500, f"Lekérdezési hiba: {e}")


@router.get("/stats")
async def golden_stats(_auth: dict = Depends(require_auth)):
    """Golden examples statisztika"""
    try:
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM golden_examples")).fetchone()[0]
            by_source = conn.execute(text(
                "SELECT source, COUNT(*) AS cnt FROM golden_examples GROUP BY source ORDER BY cnt DESC"
            )).fetchall()
            last = conn.execute(text(
                "SELECT MAX(created_at) FROM golden_examples"
            )).fetchone()[0]
        return {
            "total":     total,
            "by_source": [{"source": r[0], "count": r[1]} for r in by_source],
            "last_entry": last.isoformat() if last else None,
        }
    except Exception as e:
        raise HTTPException(500, f"Statisztika hiba: {e}")


# ── EXPORT (LoRA tanítóadat) ───────────────────────────────────

@router.get("/export")
async def export_golden(
    format: str = Query("jsonl", regex="^(jsonl|json|csv)$"),
    _auth:  dict = Depends(require_auth),
):
    """
    Golden examples exportálása LoRA tanítóadathoz.
    JSONL: OpenAI fine-tune kompatibilis formátum
    JSON:  tömbös, emberi olvasásra
    CSV:   Excel-kompatibilis BOM-mal
    """
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT raw_text, clean_name, manufacturer, category, unit "
                "FROM golden_examples "
                "WHERE clean_name IS NOT NULL AND clean_name != '' "
                "ORDER BY created_at"
            )).fetchall()
    except Exception as e:
        raise HTTPException(500, f"DB hiba: {e}")

    if format == "jsonl":
        lines = []
        for r in rows:
            lines.append(json.dumps({
                "messages": [
                    {"role": "user",
                     "content": f"Azonosítsd: {r[0]}"},
                    {"role": "assistant",
                     "content": json.dumps({
                         "name":         r[1],
                         "manufacturer": r[2] or "",
                         "category":     r[3] or "",
                         "unit":         r[4] or "db",
                         "confidence":   1.0,
                     }, ensure_ascii=False)},
                ]
            }, ensure_ascii=False))
        content  = "\n".join(lines) + "\n"
        media    = "application/x-ndjson"
        filename = "crt_golden.jsonl"

    elif format == "json":
        data = [{
            "input":        r[0],
            "name":         r[1],
            "manufacturer": r[2],
            "category":     r[3],
            "unit":         r[4],
        } for r in rows]
        content  = json.dumps(data, ensure_ascii=False, indent=2)
        media    = "application/json"
        filename = "crt_golden.json"

    else:  # csv
        buf = io.StringIO()
        w   = csv_mod.writer(buf)
        w.writerow(["raw_text", "clean_name", "manufacturer", "category", "unit"])
        for r in rows:
            w.writerow([r[0], r[1], r[2] or "", r[3] or "", r[4] or "db"])
        content  = "﻿" + buf.getvalue()
        media    = "text/csv; charset=utf-8-sig"
        filename = "crt_golden.csv"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── TÖRLÉS ────────────────────────────────────────────────────

@router.delete("/{example_id}")
async def delete_golden(example_id: int, _auth: dict = Depends(require_auth)):
    """Golden example törlése (csak admin)"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.begin() as conn:
            r = conn.execute(text(
                "DELETE FROM golden_examples WHERE id = :id"
            ), {"id": example_id})
        if r.rowcount == 0:
            raise HTTPException(404, "Nem található")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Törlési hiba: {e}")
