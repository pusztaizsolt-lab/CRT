"""
CRT LoRA Router v1.0
LoRA finomhangolás indítása, monitorozása, aktiválása
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import create_engine, text
from auth import require_auth
import subprocess, json, uuid, logging, os, sys
from pathlib import Path
from env_detect import get_db_url

router = APIRouter(prefix="/lora", tags=["lora"])
log    = logging.getLogger("CRT.lora")

DB_URL   = get_db_url()
LORA_DIR = os.environ.get("CRT_LORA_DIR", "models/lora")
engine   = create_engine(DB_URL, pool_pre_ping=True, pool_size=2)

# Python interpreter – Linux/WSL2: python3.11, Windows: py -3.11
_PYTHON = "python3.11" if sys.platform != "win32" else "py"
_PY_ARG = [] if sys.platform != "win32" else ["-3.11"]


def _r2d(row) -> dict:
    d = dict(row._mapping)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# ── STATS ──────────────────────────────────────────────────────

@router.get("/stats")
async def lora_stats(_auth: dict = Depends(require_auth)):
    """Tanítóadat darabszám + aktuális job státusz"""
    try:
        with engine.connect() as conn:
            golden = conn.execute(text(
                "SELECT COUNT(*) FROM golden_examples "
                "WHERE clean_name IS NOT NULL AND clean_name != ''"
            )).fetchone()[0]
            jobs_total = conn.execute(text("SELECT COUNT(*) FROM lora_jobs")).fetchone()[0]
            last = conn.execute(text(
                "SELECT job_id, status, base_model, examples, train_loss, finished_at "
                "FROM lora_jobs ORDER BY started_at DESC LIMIT 1"
            )).fetchone()
            active = conn.execute(text(
                "SELECT value FROM system_config WHERE key = 'lora_active_job_id'"
            )).fetchone()
        return {
            "golden_examples": golden,
            "jobs_total":      jobs_total,
            "last_job":        _r2d(last) if last else None,
            "active_job_id":   (active[0] or None) if active else None,
            "ready_to_train":  golden >= 10,
            "min_required":    10,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── TRÉNING INDÍTÁS ────────────────────────────────────────────

@router.post("/train")
async def start_training(payload: dict = {}, _auth: dict = Depends(require_auth)):
    """LoRA tréning indítása háttérfolyamatként"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")

    with engine.connect() as conn:
        golden = conn.execute(text(
            "SELECT COUNT(*) FROM golden_examples "
            "WHERE clean_name IS NOT NULL AND clean_name != ''"
        )).fetchone()[0]
    if golden < 10:
        raise HTTPException(400, f"Kevés tanítóadat: {golden} / minimum 10 szükséges")

    # Folyamatban lévő job ellenőrzés
    with engine.connect() as conn:
        running = conn.execute(text(
            "SELECT COUNT(*) FROM lora_jobs WHERE status IN ('pending','running')"
        )).fetchone()[0]
    if running > 0:
        raise HTTPException(409, "Már fut egy tréning – előbb várd be a végét")

    job_id   = f"lora_{uuid.uuid4().hex[:8]}"
    hf_model = (payload.get("hf_model") or "").strip()
    epochs   = max(1, min(int(payload.get("epochs", 3)), 20))
    lora_r   = max(4, min(int(payload.get("lora_r", 16)), 64))

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO lora_jobs "
            "(job_id, status, base_model, examples, epochs, started_at, created_by) "
            "VALUES (:jid, 'pending', :model, :ex, :ep, NOW(), :by)"
        ), {
            "jid":   job_id,
            "model": hf_model or "auto",
            "ex":    golden,
            "ep":    epochs,
            "by":    _auth.get("username"),
        })

    script = str(Path(__file__).parent / "lora_train.py")
    cmd = [_PYTHON] + _PY_ARG + [
        script,
        "--job-id",       job_id,
        "--db-url",       DB_URL,
        "--output-dir",   LORA_DIR,
        "--epochs",       str(epochs),
        "--lora-r",       str(lora_r),
    ]
    if hf_model:
        cmd += ["--hf-model", hf_model]

    log.info("LoRA tréning indul: %s (%d példa, %d epoch)", job_id, golden, epochs)
    subprocess.Popen(cmd, cwd=str(Path(__file__).parent))

    return {"job_id": job_id, "examples": golden, "epochs": epochs, "status": "started"}


# ── JOBS LISTA ─────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(_auth: dict = Depends(require_auth)):
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT job_id, status, base_model, examples, epochs, train_loss, "
                "adapter_path, error_msg, started_at, finished_at, created_by "
                "FROM lora_jobs ORDER BY started_at DESC"
            )).fetchall()
        return {"jobs": [_r2d(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── JOB RÉSZLET ────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, _auth: dict = Depends(require_auth)):
    """Job részletek + live status.json olvasás"""
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM lora_jobs WHERE job_id = :jid"
            ), {"jid": job_id}).fetchone()
    except Exception as e:
        raise HTTPException(500, str(e))
    if not row:
        raise HTTPException(404, "Job nem található")

    result = _r2d(row)
    status_file = Path(LORA_DIR) / job_id / "status.json"
    if status_file.exists():
        try:
            result["live_status"] = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return result


# ── AKTIVÁLÁS ─────────────────────────────────────────────────

@router.post("/jobs/{job_id}/activate")
async def activate_job(job_id: str, _auth: dict = Depends(require_auth)):
    """Fine-tuned modell aktiválása: ai_motor.py ettől kezdve ezt használja"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT status, adapter_path FROM lora_jobs WHERE job_id = :jid"
            ), {"jid": job_id}).fetchone()
    except Exception as e:
        raise HTTPException(500, str(e))

    if not row:
        raise HTTPException(404, "Job nem található")
    if row[0] != "done":
        raise HTTPException(400, f"Job még nem kész (státusz: {row[0]})")
    adapter = row[1]
    if not adapter or not Path(adapter).exists():
        raise HTTPException(400, "Adapter könyvtár nem található a lemezen")

    try:
        with engine.begin() as conn:
            for key, val in [("lora_active_job_id", job_id), ("lora_adapter_path", adapter)]:
                conn.execute(text(
                    "INSERT INTO system_config (key, value) VALUES (:k, :v) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                ), {"k": key, "v": val})
    except Exception as e:
        raise HTTPException(500, str(e))

    # ai_motor cache ürítés
    try:
        import ai_motor
        ai_motor.clear_lora_cache()
    except Exception:
        pass

    log.info("LoRA aktiválva: %s → %s", job_id, adapter)
    return {"status": "activated", "job_id": job_id, "adapter_path": adapter}


# ── DEAKTIVÁLÁS ────────────────────────────────────────────────

@router.post("/deactivate")
async def deactivate_lora(_auth: dict = Depends(require_auth)):
    """LoRA deaktiválása – visszaáll Claude/Ollama pipeline-ra"""
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.begin() as conn:
            for key in ("lora_active_job_id", "lora_adapter_path"):
                conn.execute(text(
                    "INSERT INTO system_config (key, value) VALUES (:k, '') "
                    "ON CONFLICT (key) DO UPDATE SET value = ''"
                ), {"k": key})
        try:
            import ai_motor
            ai_motor.clear_lora_cache()
        except Exception:
            pass
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"status": "deactivated"}


# ── TÖRLÉS ────────────────────────────────────────────────────

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, _auth: dict = Depends(require_auth)):
    if _auth.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT status FROM lora_jobs WHERE job_id = :jid"
            ), {"jid": job_id}).fetchone()
        if not row:
            raise HTTPException(404, "Job nem található")

        # Ténylegesen fut-e még? (status.json alapján)
        status_file = Path(LORA_DIR) / job_id / "status.json"
        live_status = ""
        if status_file.exists():
            try:
                live_status = json.loads(status_file.read_text(encoding="utf-8")).get("status", "")
            except Exception:
                pass
        actually_running = row[0] in ("pending", "running") and live_status in (
            "init", "loading_model", "preparing", "training"
        )
        if actually_running:
            raise HTTPException(400, "Tréning most fut – várd be a végét, vagy indítsd újra a szervert")

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM lora_jobs WHERE job_id = :jid"), {"jid": job_id})

        job_dir = Path(LORA_DIR) / job_id
        if job_dir.exists():
            import shutil
            shutil.rmtree(job_dir)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"status": "deleted", "job_id": job_id}
