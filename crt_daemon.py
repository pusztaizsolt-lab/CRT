"""
CRT Daemon — háttérszolgáltatás és felügyelő szerver
Port: 8099  |  Asyncio + aiohttp  |  Nincs DB függés

Feladatok:
  - ping pipe-ok: minden CRT port + router 20s-ként
  - watchdog: ha le → restart + email
  - scheduler: heartbeat email
  - HTTP :8099 /  /status  /metrics  /events  /restart/<id>
  - SSE: valós idejű push dashboard frissítéshez

Indítás: py -3.11 crt_daemon.py
NSSM:    nssm install CRT-Daemon py -3.11 D:\\CRT\\crt_daemon.py
"""
import asyncio, socket, logging, json, sys, time, smtplib, subprocess
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText

try:
    import aiohttp
    from aiohttp import web
    AIOHTTP = True
except ImportError:
    AIOHTTP = False

try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

# ── KONFIG ────────────────────────────────────────────────────
ROOT               = Path(__file__).parent
DAEMON_PORT        = 8099
PING_INTERVAL      = 20    # másodperc — TCP + HTTP ping
AI_DEEP_INTERVAL   = 300   # másodperc — AI inference teszt (5 perc)
AUTO_MATCH_INTERVAL = 900  # másodperc — autonóm AI egyeztetés (15 perc)
API_BASE           = "http://127.0.0.1:8000"
LOG_FILE           = ROOT / "logs" / "daemon.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("CRT.daemon")

# ── KOMPONENS TÁBLA ───────────────────────────────────────────
COMPONENTS = [
    # ── PROCESS SZINT (TCP socket ping) ──────────────────────
    {
        "id": "postgresql", "label": "PostgreSQL", "type": "process",
        "host": "127.0.0.1", "port": 5433,
        "restart": str(ROOT / "pg_start.bat"),
    },
    {
        "id": "fastapi", "label": "CRT Backend", "type": "process",
        "host": "127.0.0.1", "port": 8000,
        "restart": str(ROOT / "start_backend.bat"),
        "http_check": "http://127.0.0.1:8000/health",
    },
    {
        "id": "chromadb", "label": "ChromaDB", "type": "process",
        "host": "127.0.0.1", "port": 8001,
        "restart": None,
        "http_check": "http://127.0.0.1:8001/api/v1/heartbeat",
    },
    {
        "id": "ollama", "label": "Ollama LLM", "type": "process",
        "host": "127.0.0.1", "port": 11434,
        "restart": None,
        "http_check": "http://127.0.0.1:11434/api/tags",
    },

    # ── ROUTER SZINT (HTTP ping a FastAPI-ra) ─────────────────
    {"id": "auth",    "label": "Auth",        "type": "router", "http_check": "http://127.0.0.1:8000/health"},
    {"id": "prices",  "label": "Árak",        "type": "router", "http_check": "http://127.0.0.1:8000/prices/stats"},
    {"id": "quotes",  "label": "Ajánlatok",   "type": "router", "http_check": "http://127.0.0.1:8000/quotes/"},
    {"id": "web",     "label": "Web scraper", "type": "router", "http_check": "http://127.0.0.1:8000/web/sources"},
    {"id": "golden",  "label": "Golden",      "type": "router", "http_check": "http://127.0.0.1:8000/golden/stats"},
    {"id": "lora",    "label": "LoRA",        "type": "router", "http_check": "http://127.0.0.1:8000/lora/stats"},
    {"id": "export",  "label": "Export",      "type": "router", "http_check": "http://127.0.0.1:8000/export/"},

    # ── MOTOR SZINT ───────────────────────────────────────────
    {"id": "ai_motor",     "label": "AI Motor", "type": "motor", "http_check": "http://127.0.0.1:8000/ollama/status"},
    {"id": "chroma_motor", "label": "Chroma",   "type": "motor", "http_check": "http://127.0.0.1:8000/chroma/stats"},
    {"id": "vision",       "label": "Vision",   "type": "motor", "http_check": "http://127.0.0.1:8000/vision/status"},

    # ── STATS ─────────────────────────────────────────────────
    {"id": "dashboard", "label": "Dashboard", "type": "stats", "http_check": "http://127.0.0.1:8000/stats/dashboard"},
]

# ── STATE ─────────────────────────────────────────────────────
state: dict[str, dict] = {
    c["id"]: {
        "id":         c["id"],
        "label":      c["label"],
        "type":       c["type"],
        "status":     "unknown",
        "last_ok":    None,
        "last_check": None,
        "error":      None,
        "restarts":   0,
    }
    for c in COMPONENTS
}
_last_email_error: dict[str, float] = {}
_last_ai_deep: float = 0.0      # epoch — utolsó AI inference teszt
_ai_deep_result: dict = {}      # cache az utolsó AI teszt eredményéből

# ── AUTO MATCH ÁLLAPOT ────────────────────────────────────────
_match_state: dict = {
    "last_run":       None,   # ISO timestamp
    "motor":          None,   # "claude" | "ollama" | None
    "matched":        0,      # auto-commit darab (session)
    "golden":         0,      # golden example darab (session)
    "pending":        0,      # kézi jóváhagyásra vár
    "total_today":    0,      # mai összes egyeztetett
    "error":          None,
}


# ── PING PIPE-OK ──────────────────────────────────────────────

def _tcp_ping(host: str, port: int, timeout: float = 2.0) -> bool:
    """Nyers TCP socket ping — oprendszer szintű."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _http_ping(url: str, timeout: float = 4.0) -> bool:
    """HTTP GET ping — router/motor szintű."""
    if not AIOHTTP:
        return True
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                return r.status < 500
    except Exception:
        return False


async def ping_component(c: dict) -> bool:
    """Egy komponens teljes ping pipe-ja."""
    cid = c["id"]

    if "port" in c:
        if not _tcp_ping(c["host"], c["port"]):
            state[cid].update(
                status="down",
                error=f"TCP port {c['port']} nem válaszol",
                last_check=datetime.now().isoformat()
            )
            return False

    if "http_check" in c:
        if not await _http_ping(c["http_check"]):
            state[cid].update(
                status="degraded",
                error=f"HTTP nem válaszol: {c['http_check']}",
                last_check=datetime.now().isoformat()
            )
            return False

    state[cid].update(
        status="ok",
        last_ok=datetime.now().isoformat(),
        last_check=datetime.now().isoformat(),
        error=None
    )
    return True


# ── WATCHDOG LOOP ─────────────────────────────────────────────

async def watchdog_loop():
    global _last_ai_deep, _ai_deep_result
    log.info("Watchdog indul — ping: %ds  AI deep: %ds", PING_INTERVAL, AI_DEEP_INTERVAL)
    while True:
        fastapi_ok = True
        for c in COMPONENTS:
            cid  = c["id"]
            prev = state[cid]["status"]
            ok   = await ping_component(c)

            # ── DB deep health (SELECT NOW — olvasás echo) ──────────
            if cid == "postgresql" and ok:
                db_h = await _db_health_check()
                state[cid]["db_echo"] = db_h["echo"]
                if not db_h["ok"]:
                    state[cid].update(status="degraded", error=f"DB echo: {db_h['echo']}")
                    ok = False

            # ── AI deep health (csak 5 percenként) ─────────────────
            if cid == "ollama" and ok:
                now = time.time()
                if now - _last_ai_deep >= AI_DEEP_INTERVAL:
                    ai_h = await _ai_health_check()
                    _last_ai_deep   = now
                    _ai_deep_result = ai_h
                    state[cid]["ai_models"] = ai_h.get("models", [])
                    state[cid]["ai_echo"]   = ai_h.get("echo", "")
                    if not ai_h["ok"]:
                        state[cid].update(
                            status="degraded",
                            error=f"AI inference: {ai_h.get('reason', ai_h.get('echo', '?'))}"
                        )
                        ok = False
                else:
                    # cache-elt eredmény alkalmazása
                    if not _ai_deep_result.get("ok", True):
                        state[cid].update(
                            status="degraded",
                            error=f"AI (cached): {_ai_deep_result.get('reason', '?')}"
                        )
                        ok = False

            if not ok and prev == "ok":
                log.warning("LEÁLLT: %s", cid)
                await _on_down(c)

            if ok and prev in ("down", "degraded", "unknown"):
                log.info("VISSZAÁLLT: %s", cid)

            if cid == "fastapi":
                fastapi_ok = ok

            # Router/motor szint: ha FastAPI le → automatikusan down
            if not fastapi_ok and c["type"] in ("router", "motor", "stats"):
                state[cid].update(status="down", error="FastAPI nem fut")

        await asyncio.sleep(PING_INTERVAL)


async def _on_down(c: dict):
    """Komponens leállt — restart ha van parancs, email küldés."""
    cid = c["id"]
    state[cid]["restarts"] = state[cid].get("restarts", 0) + 1

    restart_cmd = c.get("restart")
    if restart_cmd and Path(restart_cmd).exists():
        log.info("Restart: %s → %s", cid, restart_cmd)
        try:
            subprocess.Popen(
                restart_cmd, shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
        except Exception as e:
            log.error("Restart hiba %s: %s", cid, e)

    now = time.time()
    if now - _last_email_error.get(cid, 0) > 1800:
        _last_email_error[cid] = now
        await asyncio.get_event_loop().run_in_executor(
            None, _send_email,
            f"CRT Daemon: {c['label']} leállt",
            f"Komponens: {cid}\nHiba: {state[cid].get('error', '?')}\n"
            f"Restart kísérlet: {state[cid]['restarts']}\n"
            f"Idő: {datetime.now().isoformat()}"
        )


# ── EMAIL ─────────────────────────────────────────────────────

def _load_smtp_config() -> dict:
    cfg = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip()
    return cfg


def _send_email(subject: str, body: str):
    cfg  = _load_smtp_config()
    host = cfg.get("SMTP_HOST") or cfg.get("smtp_host", "")
    port = int(cfg.get("SMTP_PORT") or cfg.get("smtp_port", 587))
    user = cfg.get("SMTP_USER") or cfg.get("smtp_user", "")
    pwd  = cfg.get("SMTP_PASS") or cfg.get("smtp_pass", "")
    to   = cfg.get("ADMIN_EMAIL") or user
    if not host or not user:
        log.warning("Email: SMTP nincs beállítva, kihagyva")
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[CRT] {subject}"
        msg["From"]    = user
        msg["To"]      = to
        srv = smtplib.SMTP(host, port, timeout=10)
        srv.ehlo(); srv.starttls(); srv.login(user, pwd)
        srv.sendmail(user, [to], msg.as_string())
        srv.quit()
        log.info("Email: %s → %s", subject, to)
    except Exception as e:
        log.error("Email hiba: %s", e)


# ── AUTO MATCH — autonóm AI egyeztetési mag ───────────────────
# A daemon minden AUTO_MATCH_INTERVAL másodpercben:
#   1. lekérdezi a párosítatlan web_prices-ok számát
#   2. meghívja az ai-suggest endpointot (Claude → Ollama fallback)
#   3. auto-commit: confidence >= 0.90 → azonnal elfogad
#   4. 0.75–0.89: pending státusz → kézi jóváhagyás a UI-ban
#
# Szükséges: DAEMON_TOKEN a .env-ben + FastAPI-ban accept-álva.
# Ha DAEMON_TOKEN nincs beállítva → a loop üzemmód kimarad, csak figyelmeztetés.

def _daemon_token() -> str:
    cfg = _load_smtp_config()
    return cfg.get("DAEMON_TOKEN", "")


async def _api_post(path: str, body: dict, token: str) -> dict | None:
    """Belső FastAPI POST hívás a daemon saját token-jével."""
    if not AIOHTTP:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{API_BASE}{path}",
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                if r.status in (200, 201):
                    return await r.json()
                txt = await r.text()
                log.warning("API %s → %d: %s", path, r.status, txt[:120])
                return None
    except Exception as e:
        log.warning("API hívás hiba %s: %s", path, str(e)[:80])
        return None


async def auto_match_loop():
    """
    Autonóm AI egyeztetési ciklus.
    FastAPI-ra vár (max 120s), majd AUTO_MATCH_INTERVAL-onként fut.
    """
    global _match_state
    token = _daemon_token()
    if not token:
        log.warning(
            "AUTO MATCH: DAEMON_TOKEN nincs beállítva a .env-ben → "
            "automatikus egyeztetés kikapcsolva. "
            "Add hozzá: DAEMON_TOKEN=<long-lived-jwt>"
        )
        return

    # Megvárjuk hogy a FastAPI elinduljon
    log.info("Auto match: FastAPI-ra vár (max 120s)…")
    for _ in range(24):
        if state.get("fastapi", {}).get("status") == "ok":
            break
        await asyncio.sleep(5)
    else:
        log.warning("Auto match: FastAPI nem indult el 120s alatt, kihagyva")
        return

    log.info("Auto match ciklus indul — %ds-enként", AUTO_MATCH_INTERVAL)

    while True:
        await asyncio.sleep(AUTO_MATCH_INTERVAL)
        await _run_auto_match(token)


async def _run_auto_match(token: str):
    global _match_state

    # FastAPI elérhetőség — ha le van, kihagyjuk
    if state.get("fastapi", {}).get("status") != "ok":
        _match_state["error"] = "FastAPI nem elérhető"
        return

    log.info("Auto match: egyeztetés indul…")
    _match_state["error"] = None

    # 1. Javaslat kérés (max 50 tétel / futás)
    suggest = await _api_post(
        "/web/prices/ai-suggest",
        {"limit": 50},
        token,
    )
    if not suggest:
        _match_state["error"] = "ai-suggest sikertelen"
        return

    motor       = suggest.get("motor", "none")
    suggestions = suggest.get("suggestions", [])
    _match_state["motor"]    = motor
    _match_state["last_run"] = datetime.now().isoformat()

    if not suggestions:
        log.info("Auto match: nincs egyeztetendő ár")
        _match_state["pending"] = 0
        return

    # 2. Szétválasztás: auto-commit (conf ≥ 0.90) vs. pending
    auto_approvals = []
    pending_count  = 0
    for s in suggestions:
        conf    = s.get("confidence", 0.0)
        item_id = s.get("item_id")
        if item_id and conf >= 0.90:
            auto_approvals.append({
                "price_id":   s["price_id"],
                "item_id":    item_id,
                "confidence": conf,
                "accepted":   True,
            })
        else:
            pending_count += 1

    _match_state["pending"] = pending_count

    if not auto_approvals:
        log.info(
            "Auto match (%s): %d javaslat, mind kézi jóváhagyásra vár (conf<0.90)",
            motor, len(suggestions)
        )
        return

    # 3. Auto-commit
    commit = await _api_post(
        "/web/prices/ai-commit",
        {"approvals": auto_approvals},
        token,
    )
    if commit:
        matched = commit.get("committed", 0)
        golden  = commit.get("golden_created", 0)
        _match_state["matched"]     = matched
        _match_state["golden"]      = golden
        _match_state["total_today"] = _match_state.get("total_today", 0) + matched
        log.info(
            "Auto match (%s): %d egyezés mentve, %d golden példa, %d kézi vár",
            motor, matched, golden, pending_count
        )
    else:
        _match_state["error"] = "ai-commit sikertelen"


# ── DB HEALTH — SELECT NOW (olvasás echo, nincs audit_log szennyezés) ──

async def _db_health_check() -> dict:
    """
    Read-only DB health: SELECT NOW() bizonyítja a kapcsolatot és a DB válaszkészségét.
    Nem ír audit_log-ba.
    """
    try:
        import psycopg2
        cfg = _load_smtp_config()  # .env-ből veszi a DB adatokat is
        dsn = (
            f"host=127.0.0.1 port={cfg.get('DB_PORT', 5433)} "
            f"dbname={cfg.get('DB_NAME', 'crt')} "
            f"user={cfg.get('DB_USER', 'crt_user')} "
            f"password={cfg.get('DB_PASS', '')} "
            f"connect_timeout=3"
        )
        conn = await asyncio.get_event_loop().run_in_executor(
            None, lambda: psycopg2.connect(dsn)
        )
        cur = conn.cursor()
        cur.execute("SELECT NOW()")
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"ok": bool(row), "echo": str(row[0])[:20] if row else "no result"}
    except Exception as e:
        return {"ok": False, "echo": str(e)[:120]}


# ── AI HEALTH — modell lista + mini inference ─────────────────

async def _ai_health_check() -> dict:
    """
    Valódi AI health: model lista + 1-token inference.
    Csak AI_DEEP_INTERVAL-onként hívódik (5 perc).
    """
    if not AIOHTTP:
        return {"ok": False, "reason": "aiohttp nincs"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "http://127.0.0.1:11434/api/tags",
                timeout=aiohttp.ClientTimeout(total=4)
            ) as r:
                if r.status != 200:
                    return {"ok": False, "reason": f"tags HTTP {r.status}"}
                data   = await r.json()
                models = [m["name"] for m in data.get("models", [])]
                if not models:
                    return {"ok": False, "reason": "nincs betöltött modell"}

            payload = json.dumps({
                "model":   models[0],
                "prompt":  "1+1=",
                "stream":  False,
                "options": {"num_predict": 2, "temperature": 0.0},
            }).encode()
            async with s.post(
                "http://127.0.0.1:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r2:
                if r2.status != 200:
                    return {"ok": False, "reason": f"generate HTTP {r2.status}", "models": models}
                resp   = await r2.json()
                answer = (resp.get("response") or "").strip()
                return {
                    "ok":     bool(answer),
                    "models": models,
                    "echo":   answer[:20] or "(üres)",
                    "model":  models[0],
                }

    except asyncio.TimeoutError:
        return {"ok": False, "reason": "timeout (>15s) — modell betölt?"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


# ── OS METRIKÁK ───────────────────────────────────────────────

def _os_metrics() -> dict:
    if not PSUTIL:
        return {"psutil": "nincs telepítve"}
    disk = psutil.disk_usage(str(ROOT))
    return {
        "cpu_pct":      psutil.cpu_percent(interval=0.2),
        "ram_pct":      psutil.virtual_memory().percent,
        "ram_free_mb":  psutil.virtual_memory().available // 1_048_576,
        "disk_free_gb": disk.free // 1_073_741_824,
        "disk_pct":     disk.percent,
        "uptime_s":     int(time.time() - psutil.boot_time()),
    }


# ── HTTP SZERVER (:8099) ──────────────────────────────────────

_CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}


def _json_resp(data: dict, status: int = 200) -> "web.Response":
    return web.Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status,
        headers=_CORS,
    )


async def handle_status(_req) -> "web.Response":
    data = {
        "daemon":     "ok",
        "time":       datetime.now().isoformat(),
        "components": list(state.values()),
        "summary": {
            "ok":       sum(1 for s in state.values() if s["status"] == "ok"),
            "down":     sum(1 for s in state.values() if s["status"] == "down"),
            "degraded": sum(1 for s in state.values() if s["status"] == "degraded"),
            "unknown":  sum(1 for s in state.values() if s["status"] == "unknown"),
        },
        "metrics":    _os_metrics(),
        "auto_match": _match_state,
    }
    return _json_resp(data)


async def handle_metrics(_req) -> "web.Response":
    return _json_resp(_os_metrics())


async def handle_events(req) -> "web.StreamResponse":
    """
    Server-Sent Events — a szerver tolja az adatot 5s-ként.
    Bármelyik kliens feliratkozhat: daemon saját dashboardja,
    CRT kezelőpult widget, bare metal monitoring tool.
    """
    resp = web.StreamResponse(headers={
        "Content-Type":                "text/event-stream",
        "Cache-Control":               "no-cache",
        "X-Accel-Buffering":           "no",
        "Access-Control-Allow-Origin": "*",
    })
    await resp.prepare(req)
    try:
        while True:
            payload = {
                "time": datetime.now().isoformat(),
                "components": list(state.values()),
                "summary": {
                    "ok":       sum(1 for s in state.values() if s["status"] == "ok"),
                    "down":     sum(1 for s in state.values() if s["status"] == "down"),
                    "degraded": sum(1 for s in state.values() if s["status"] == "degraded"),
                },
                "metrics":    _os_metrics(),
                "auto_match": _match_state,
            }
            await resp.write(
                f"data: {json.dumps(payload, default=str)}\n\n".encode()
            )
            await asyncio.sleep(5)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    return resp


async def handle_restart(req) -> "web.Response":
    cid  = req.match_info.get("component_id")
    comp = next((c for c in COMPONENTS if c["id"] == cid), None)
    if not comp:
        return _json_resp({"error": "nem található"}, 404)
    await _on_down(comp)
    return _json_resp({"status": "restart kísérlet indítva", "id": cid})


async def handle_match_now(_req) -> "web.Response":
    """Azonnali egyeztetési futás — dashboard 'Most futtat' gomb."""
    token = _daemon_token()
    if not token:
        return _json_resp({"error": "DAEMON_TOKEN nincs beállítva"}, 503)
    asyncio.create_task(_run_auto_match(token))
    return _json_resp({"status": "egyeztetés indítva", "time": datetime.now().isoformat()})


async def handle_match_state(_req) -> "web.Response":
    return _json_resp(_match_state)


async def handle_ui(_req) -> "web.Response":
    """Dashboard HTML — SSE alapú, nincs oldal-újratöltés."""
    return web.Response(
        text=_DASHBOARD_HTML,
        content_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


# ── DASHBOARD HTML ────────────────────────────────────────────
# SSE EventSource: szerver tolja az adatot 5s-ként → JS frissíti a DOM-ot
# Restart gomb: POST /restart/<id> → watchdog újraindítja a folyamatot

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<title>CRT Daemon :8099</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0a0a12;color:#e0e0f0;min-height:100vh;padding:1rem 1.25rem}
header{display:flex;align-items:center;gap:.75rem;padding:.5rem 0 .9rem;border-bottom:1px solid #1e1e30;margin-bottom:.9rem}
.pulse{width:12px;height:12px;border-radius:50%;background:#3ecf8e;flex-shrink:0;transition:background .4s}
.pulse.down{background:#e74c3c;animation:blink 1s infinite}
.pulse.warn{background:#f5a623}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}
h1{font-size:1rem;font-weight:600;flex:1;letter-spacing:.01em}
h1 span{color:#3a3a6a}
#clock{font-size:.8rem;color:#5a5a7a;font-variant-numeric:tabular-nums}
#summary-bar{font-size:.82rem;color:#9898b8}
#metrics-bar{display:flex;gap:1.75rem;padding:.45rem 0 .9rem;font-size:.77rem;color:#6868a0;border-bottom:1px solid #1a1a2e;margin-bottom:.9rem;flex-wrap:wrap}
.mi span{color:#c0c0e0;font-weight:600;margin-left:.25rem}
.sections{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
@media(max-width:580px){.sections{grid-template-columns:1fr}}
.section{background:#0e0e1c;border:1px solid #1e1e30;border-radius:8px;padding:.7rem .8rem}
.section h2{font-size:.65rem;letter-spacing:.12em;color:#4a4a6a;text-transform:uppercase;margin-bottom:.55rem}
.cr{display:flex;align-items:center;gap:.45rem;padding:.28rem 0;border-bottom:1px solid #131320;font-size:.8rem}
.cr:last-child{border-bottom:none}
.sd{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.ok{background:#3ecf8e}
.dn{background:#e74c3c;animation:blink 1s infinite}
.dg{background:#f5a623}
.un{background:#383850}
.lbl{flex:1;font-weight:500}
.err{font-size:.68rem;color:#e05050;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tms{font-size:.63rem;color:#363654}
.rb{font-size:.62rem;padding:.12rem .35rem;background:#141428;border:1px solid #2a2a44;color:#7c6af7;border-radius:3px;cursor:pointer;flex-shrink:0}
.rb:hover{background:#222240}
footer{margin-top:1.2rem;font-size:.7rem;color:#333352;text-align:center}
footer a{color:#5050c0;text-decoration:none;margin:0 .35rem}
#lu{font-size:.68rem;color:#2e2e50;margin-left:1rem}
</style>
</head>
<body>
<header>
  <div class="pulse" id="mp"></div>
  <h1>CRT Daemon <span>:8099</span></h1>
  <span id="summary-bar">csatlakozás…</span>
  &nbsp;·&nbsp;
  <span id="clock"></span>
</header>

<div id="metrics-bar">
  <div class="mi">CPU<span id="m-cpu">–</span>%</div>
  <div class="mi">RAM<span id="m-ram">–</span>%</div>
  <div class="mi">Disk<span id="m-disk">–</span> GB szabad</div>
  <div class="mi">Uptime<span id="m-up">–</span></div>
</div>

<div class="sections">
  <div class="section"><h2>Process</h2><div id="g-process"></div></div>
  <div class="section"><h2>Router</h2><div id="g-router"></div></div>
  <div class="section"><h2>Motor</h2><div id="g-motor"></div></div>
  <div class="section"><h2>Stats</h2><div id="g-stats"></div></div>
</div>

<div style="margin-top:.9rem;background:#0a0a14;border:1px solid #1e1e30;border-radius:8px;padding:.7rem .9rem;">
  <div style="font-size:.65rem;letter-spacing:.12em;color:#4a4a6a;text-transform:uppercase;margin-bottom:.55rem;">Auto Match – AI egyeztetési mag</div>
  <div style="display:flex;gap:1.5rem;font-size:.78rem;flex-wrap:wrap;align-items:center;">
    <div>Motor: <span id="am-motor" style="color:#9898b8;">–</span></div>
    <div>Utolsó futás: <span id="am-last" style="color:#9898b8;">–</span></div>
    <div>Mai egyezés: <span id="am-matched" style="color:#3ecf8e;">–</span></div>
    <div>Golden: <span id="am-golden" style="color:#7c6af7;">–</span></div>
    <div>Kézi vár: <span id="am-pending" style="color:#f5a623;">–</span></div>
    <div id="am-err" style="color:#e74c3c;display:none;"></div>
    <button onclick="matchNow()" style="margin-left:auto;font-size:.65rem;padding:.2rem .55rem;background:#141428;border:1px solid #2a2a44;color:#7c6af7;border-radius:3px;cursor:pointer;">▶ Most futtat</button>
  </div>
</div>

<footer>
  CRT Daemon
  <a href="/status">JSON</a>
  <a href="/metrics">OS</a>
  <a href="/events">SSE</a>
  <a href="http://localhost:8000/ui/kezelőpult.html">CRT →</a>
  <span id="lu"></span>
</footer>

<script>
const G = {process:'g-process', router:'g-router', motor:'g-motor', stats:'g-stats'};

function fmtUp(s){
  if(s<60) return s+'s';
  if(s<3600) return Math.floor(s/60)+'p';
  if(s<86400) return Math.floor(s/3600)+'ó '+Math.floor((s%3600)/60)+'p';
  return Math.floor(s/86400)+'n '+Math.floor((s%86400)/3600)+'ó';
}
function fmtT(iso){ return iso ? iso.slice(11,19) : '–'; }

function render(components){
  const byType={process:[],router:[],motor:[],stats:[]};
  for(const c of components) if(byType[c.type]) byType[c.type].push(c);
  for(const [t,gid] of Object.entries(G)){
    const el=document.getElementById(gid); if(!el) continue;
    el.innerHTML=byType[t].map(c=>{
      const dc=c.status==='ok'?'ok':c.status==='down'?'dn':c.status==='degraded'?'dg':'un';
      const info=c.error
        ?`<span class="err" title="${c.error.replace(/"/g,'&quot;')}">${c.error}</span>`
        :`<span class="tms">${fmtT(c.last_ok)}</span>`;
      const btn=c.type==='process'
        ?`<button class="rb" onclick="rst('${c.id}')">↺</button>`:'';
      return `<div class="cr"><div class="sd ${dc}"></div><span class="lbl">${c.label}</span>${info}${btn}</div>`;
    }).join('');
  }
}

function upd(data){
  const s=data.summary, tot=data.components.length;
  const mp=document.getElementById('mp');
  mp.className=s.down>0?'pulse down':s.degraded>0?'pulse warn':'pulse';
  document.getElementById('summary-bar').textContent=
    `${s.ok}/${tot} OK`+(s.down?`  ✗ ${s.down}`:'')+(s.degraded?`  ⚠ ${s.degraded}`:'');
  const m=data.metrics||{};
  document.getElementById('m-cpu').textContent  = m.cpu_pct!=null?m.cpu_pct.toFixed(0):'–';
  document.getElementById('m-ram').textContent  = m.ram_pct!=null?m.ram_pct.toFixed(0):'–';
  document.getElementById('m-disk').textContent = m.disk_free_gb??'–';
  document.getElementById('m-up').textContent   = m.uptime_s!=null?fmtUp(m.uptime_s):'–';
  render(data.components);
  document.getElementById('lu').textContent='frissítve '+fmtT(data.time);
  if(data.auto_match) updAutoMatch(data.auto_match);
}

async function rst(cid){
  if(!confirm(`Restart: ${cid}?`)) return;
  await fetch(`/restart/${cid}`,{method:'POST'});
}

async function matchNow(){
  const r = await fetch('/match-now',{method:'POST'});
  const d = await r.json();
  document.getElementById('am-last').textContent = d.error || 'indítva…';
}

function updAutoMatch(am){
  if(!am) return;
  document.getElementById('am-motor').textContent   = am.motor || '–';
  document.getElementById('am-matched').textContent = am.total_today ?? am.matched ?? '–';
  document.getElementById('am-golden').textContent  = am.golden ?? '–';
  document.getElementById('am-pending').textContent = am.pending ?? '–';
  const lastEl = document.getElementById('am-last');
  lastEl.textContent = am.last_run ? am.last_run.slice(11,19) : '–';
  const errEl = document.getElementById('am-err');
  if(am.error){ errEl.textContent='✗ '+am.error; errEl.style.display=''; }
  else { errEl.style.display='none'; }
}

function sse(){
  const es=new EventSource('/events');
  es.onmessage=e=>{ try{upd(JSON.parse(e.data));}catch(_){} };
  es.onerror=()=>{ es.close(); setTimeout(sse,5000); };
}

setInterval(()=>{ document.getElementById('clock').textContent=new Date().toLocaleTimeString('hu'); },1000);
sse();
</script>
</body>
</html>"""


# ── HEARTBEAT EMAIL (naponta) ─────────────────────────────────

async def heartbeat_loop():
    """24 óránként státusz email."""
    await asyncio.sleep(60)
    while True:
        ok  = sum(1 for s in state.values() if s["status"] == "ok")
        dn  = sum(1 for s in state.values() if s["status"] == "down")
        met = _os_metrics()
        body = (
            f"CRT Daemon napi jelentés — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Komponensek: {ok}/{len(state)} OK, {dn} leállott\n"
            f"CPU: {met.get('cpu_pct','?')}%  RAM: {met.get('ram_pct','?')}%  "
            f"Disk szabad: {met.get('disk_free_gb','?')} GB\n"
            f"Uptime: {fmtUptime(met.get('uptime_s', 0))}\n\n"
        )
        for s in state.values():
            if s["status"] != "ok":
                body += f"  ! {s['label']}: {s.get('error', '?')}\n"
        await asyncio.get_event_loop().run_in_executor(
            None, _send_email, "Napi státusz", body
        )
        await asyncio.sleep(86400)


def fmtUptime(s: int) -> str:
    if s < 60:    return f"{s}s"
    if s < 3600:  return f"{s//60}p"
    if s < 86400: return f"{s//3600}ó {(s%3600)//60}p"
    return f"{s//86400}n {(s%86400)//3600}ó"


# ── MAIN ──────────────────────────────────────────────────────

async def main():
    log.info("CRT Daemon indul — port %d", DAEMON_PORT)

    if AIOHTTP:
        app = web.Application()
        app.router.add_get("/",                        handle_ui)
        app.router.add_get("/ui",                      handle_ui)
        app.router.add_get("/status",                  handle_status)
        app.router.add_get("/metrics",                 handle_metrics)
        app.router.add_get("/events",                  handle_events)
        app.router.add_post("/restart/{component_id}", handle_restart)
        app.router.add_post("/match-now",              handle_match_now)
        app.router.add_get("/match-state",             handle_match_state)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", DAEMON_PORT)
        await site.start()
        log.info(
            "HTTP: http://localhost:%d  SSE: http://localhost:%d/events",
            DAEMON_PORT, DAEMON_PORT
        )
    else:
        log.warning("aiohttp nincs — HTTP kikapcsolva (pip install aiohttp)")

    asyncio.create_task(watchdog_loop())
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(auto_match_loop())

    log.info("Daemon fut. Ctrl+C a leállításhoz.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        log.info("Daemon leáll.")


if __name__ == "__main__":
    asyncio.run(main())
