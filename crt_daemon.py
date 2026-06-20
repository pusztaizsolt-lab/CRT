"""
CRT Daemon — háttérszolgáltatás és felügyelő szerver
Port: 8099  |  Asyncio + aiohttp  |  Nincs DB függés

Feladatok:
  - ping pipe-ok: minden CRT port + router 20s-ként
  - watchdog: ha le → restart
  - scheduler: scraper, backup, heartbeat email
  - HTTP :8099 /status /metrics /ui
  - tálca ikon (opcionális)

Indítás: py -3.11 crt_daemon.py
NSSM:    nssm install CRT-Daemon py -3.11 D:\CRT\crt_daemon.py
"""
import asyncio, socket, logging, json, os, sys, time, smtplib, subprocess
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
ROOT      = Path(__file__).parent
DAEMON_PORT = 8099
PING_INTERVAL = 20          # másodperc
LOG_FILE  = ROOT / "logs" / "daemon.log"
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
# Amit a main.py importál — ez a ping pipe forrása
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
    {"id": "auth",       "label": "Auth",       "type": "router", "http_check": "http://127.0.0.1:8000/health"},
    {"id": "prices",     "label": "Árak",       "type": "router", "http_check": "http://127.0.0.1:8000/prices/stats"},
    {"id": "quotes",     "label": "Ajánlatok",  "type": "router", "http_check": "http://127.0.0.1:8000/quotes/"},
    {"id": "web",        "label": "Web scraper","type": "router", "http_check": "http://127.0.0.1:8000/web/sources"},
    {"id": "golden",     "label": "Golden",     "type": "router", "http_check": "http://127.0.0.1:8000/golden/stats"},
    {"id": "lora",       "label": "LoRA",       "type": "router", "http_check": "http://127.0.0.1:8000/lora/stats"},
    {"id": "export",     "label": "Export",     "type": "router", "http_check": "http://127.0.0.1:8000/export/"},

    # ── MOTOR SZINT ───────────────────────────────────────────
    {"id": "ai_motor",    "label": "AI Motor",   "type": "motor",  "http_check": "http://127.0.0.1:8000/ollama/status"},
    {"id": "chroma_motor","label": "Chroma",     "type": "motor",  "http_check": "http://127.0.0.1:8000/chroma/stats"},
    {"id": "vision",      "label": "Vision",     "type": "motor",  "http_check": "http://127.0.0.1:8000/vision/status"},

    # ── STATS ─────────────────────────────────────────────────
    {"id": "dashboard",   "label": "Dashboard",  "type": "stats",  "http_check": "http://127.0.0.1:8000/stats/dashboard"},
]

# ── STATE ─────────────────────────────────────────────────────
state = {
    c["id"]: {
        "id":      c["id"],
        "label":   c["label"],
        "type":    c["type"],
        "status":  "unknown",
        "last_ok": None,
        "last_check": None,
        "error":   None,
        "restarts": 0,
    }
    for c in COMPONENTS
}
_last_email_error: dict[str, float] = {}


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
        return True   # ha nincs aiohttp, átugorjuk
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                return r.status < 500
    except Exception:
        return False


async def ping_component(c: dict) -> bool:
    """Egy komponens teljes ping pipe-ja."""
    cid = c["id"]

    # TCP szint (process típusoknál)
    if "port" in c:
        tcp_ok = _tcp_ping(c["host"], c["port"])
        if not tcp_ok:
            state[cid]["status"]     = "down"
            state[cid]["error"]      = f"TCP port {c['port']} nem válaszol"
            state[cid]["last_check"] = datetime.now().isoformat()
            return False

    # HTTP szint (ha van)
    if "http_check" in c:
        http_ok = await _http_ping(c["http_check"])
        if not http_ok:
            state[cid]["status"]     = "degraded"
            state[cid]["error"]      = f"HTTP {c['http_check']} nem válaszol"
            state[cid]["last_check"] = datetime.now().isoformat()
            return False

    # OK
    state[cid]["status"]     = "ok"
    state[cid]["last_ok"]    = datetime.now().isoformat()
    state[cid]["last_check"] = datetime.now().isoformat()
    state[cid]["error"]      = None
    return True


# ── WATCHDOG LOOP ─────────────────────────────────────────────

async def watchdog_loop():
    """Minden komponenst pingel PING_INTERVAL másodpercenként."""
    log.info("Watchdog indul — %ds interval", PING_INTERVAL)
    while True:
        fastapi_ok = True
        for c in COMPONENTS:
            cid = c["id"]
            prev = state[cid]["status"]
            ok   = await ping_component(c)

            # ── DB deep health (írás+olvasás echo) ──────────────
            if cid == "postgresql" and ok:
                db_h = await _db_health_check()
                state[cid]["db_echo"] = db_h["echo"]
                if not db_h["ok"]:
                    state[cid]["status"] = "degraded"
                    state[cid]["error"]  = f"DB echo fail: {db_h['echo']}"
                    ok = False
                else:
                    log.debug("DB echo: %s", db_h["echo"])

            # ── AI deep health (modell + mini inference) ─────────
            if cid == "ollama" and ok:
                ai_h = await _ai_health_check()
                state[cid]["ai_models"] = ai_h.get("models", [])
                state[cid]["ai_echo"]   = ai_h.get("echo", "")
                if not ai_h["ok"]:
                    state[cid]["status"] = "degraded"
                    state[cid]["error"]  = f"AI echo fail: {ai_h.get('reason', ai_h.get('echo','?'))}"
                    ok = False
                else:
                    log.debug("AI echo: %s @ %s", ai_h.get("echo"), ai_h.get("model"))

            if not ok and prev == "ok":
                log.warning("LEÁLLT: %s", cid)
                await _on_down(c)

            if ok and prev in ("down", "degraded", "unknown"):
                log.info("VISSZAÁLLT: %s", cid)

            if cid == "fastapi" and not ok:
                fastapi_ok = False

            # Router/motor szint: ha FastAPI le → ne pingeljük
            if not fastapi_ok and c["type"] in ("router", "motor", "stats"):
                state[cid]["status"] = "down"
                state[cid]["error"]  = "FastAPI nem fut"

        await asyncio.sleep(PING_INTERVAL)


async def _on_down(c: dict):
    """Komponens leállt — restart ha van parancs, email küldés."""
    cid = c["id"]
    state[cid]["restarts"] = state[cid].get("restarts", 0) + 1

    # Restart kísérlet
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

    # Email — legfeljebb 30 percenként ugyanarról a komponensről
    now = time.time()
    if now - _last_email_error.get(cid, 0) > 1800:
        _last_email_error[cid] = now
        await asyncio.get_event_loop().run_in_executor(
            None, _send_email,
            f"CRT Daemon: {c['label']} leállt",
            f"Komponens: {cid}\nHiba: {state[cid].get('error','?')}\n"
            f"Restart kísérlet: {state[cid]['restarts']}\n"
            f"Idő: {datetime.now().isoformat()}"
        )


# ── EMAIL ─────────────────────────────────────────────────────

def _load_smtp_config() -> dict:
    """SMTP konfig .env-ből vagy system_config táblából (egyszerű fallback)."""
    cfg = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip()
    return cfg


def _send_email(subject: str, body: str):
    cfg = _load_smtp_config()
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
        log.info("Email elküldve: %s → %s", subject, to)
    except Exception as e:
        log.error("Email hiba: %s", e)


# ── DB HEALTH — írás + olvasás echo ──────────────────────────

async def _db_health_check() -> dict:
    """
    Valódi DB health: nem csak port ping —
    test sort ír, visszaolvassa, törli. Echo = oda-vissza adat.
    """
    try:
        import psycopg2
        from env_detect import get_db_url
        url = get_db_url()
        conn = await asyncio.get_event_loop().run_in_executor(
            None, lambda: psycopg2.connect(url, connect_timeout=3)
        )
        cur = conn.cursor()

        # Write
        ts = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO audit_log (log_id, user_id, action, description, timestamp) "
            "VALUES (%s, %s, %s, %s, NOW())",
            ("daemon-ping", "0", "daemon_ping", f"health:{ts}")
        )
        conn.commit()

        # Read back (echo)
        cur.execute(
            "SELECT description FROM audit_log WHERE action='daemon_ping' "
            "ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        echo_ok = row and "health:" in (row[0] or "")

        # Cleanup
        cur.execute("DELETE FROM audit_log WHERE action='daemon_ping'")
        conn.commit()
        cur.close(); conn.close()

        return {"ok": echo_ok, "echo": "write→read OK" if echo_ok else "echo fail"}

    except Exception as e:
        return {"ok": False, "echo": str(e)[:120]}


# ── AI HEALTH — modell + mini inference ───────────────────────

async def _ai_health_check() -> dict:
    """
    Valódi AI health: modellek listája + 1 tokenes inference teszt.
    Ha az inference nem válaszol 10s alatt → degraded.
    """
    if not AIOHTTP:
        return {"ok": False, "reason": "aiohttp nincs"}
    try:
        async with aiohttp.ClientSession() as s:
            # Modell lista
            async with s.get("http://127.0.0.1:11434/api/tags",
                              timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status != 200:
                    return {"ok": False, "reason": f"tags HTTP {r.status}"}
                data  = await r.json()
                models = [m["name"] for m in data.get("models", [])]
                if not models:
                    return {"ok": False, "reason": "nincs betöltött modell"}

            # Mini inference — 1 token echo teszt
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
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r2:
                if r2.status != 200:
                    return {"ok": False, "reason": f"generate HTTP {r2.status}", "models": models}
                resp = await r2.json()
                answer = (resp.get("response") or "").strip()
                return {
                    "ok":     bool(answer),
                    "models": models,
                    "echo":   answer[:20] or "(üres)",
                    "model":  models[0],
                }

    except asyncio.TimeoutError:
        return {"ok": False, "reason": "timeout (>12s) — modell betölt?"}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


# ── OS METRIKÁK ───────────────────────────────────────────────

def _os_metrics() -> dict:
    if not PSUTIL:
        return {"psutil": "nincs telepítve"}
    disk = psutil.disk_usage(str(ROOT))
    return {
        "cpu_pct":    psutil.cpu_percent(interval=0.2),
        "ram_pct":    psutil.virtual_memory().percent,
        "ram_free_mb": psutil.virtual_memory().available // 1_048_576,
        "disk_free_gb": disk.free // 1_073_741_824,
        "disk_pct":   disk.percent,
        "uptime_s":   int(time.time() - psutil.boot_time()),
    }


# ── HTTP SZERVER (:8099) ──────────────────────────────────────

async def handle_status(req):
    data = {
        "daemon":     "ok",
        "time":       datetime.now().isoformat(),
        "components": list(state.values()),
        "summary": {
            "ok":       sum(1 for s in state.values() if s["status"] == "ok"),
            "down":     sum(1 for s in state.values() if s["status"] == "down"),
            "degraded": sum(1 for s in state.values() if s["status"] == "degraded"),
            "unknown":  sum(1 for s in state.values() if s["status"] == "unknown"),
        }
    }
    return web.Response(
        text=json.dumps(data, ensure_ascii=False),
        content_type="application/json"
    )


async def handle_metrics(req):
    return web.Response(
        text=json.dumps(_os_metrics(), ensure_ascii=False),
        content_type="application/json"
    )


async def handle_ui(req):
    ok_count   = sum(1 for s in state.values() if s["status"] == "ok")
    down_count = sum(1 for s in state.values() if s["status"] == "down")
    total      = len(state)
    color      = "#3ecf8e" if down_count == 0 else ("#f5a623" if down_count < 3 else "#e74c3c")

    rows = ""
    for s in state.values():
        sc = {"ok": "#3ecf8e", "down": "#e74c3c", "degraded": "#f5a623"}.get(s["status"], "#888")
        rows += (
            f"<tr>"
            f"<td>{s['label']}</td>"
            f"<td><span style='color:{sc};font-weight:700'>{s['status'].upper()}</span></td>"
            f"<td style='color:#888;font-size:.8em'>{s['type']}</td>"
            f"<td style='color:#888;font-size:.75em'>{s.get('last_ok','–')[:19] if s.get('last_ok') else '–'}</td>"
            f"<td style='color:#e74c3c;font-size:.75em'>{s.get('error','') or ''}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html><html lang="hu"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="20">
<title>CRT Daemon :8099</title>
<style>
  body{{font-family:'Segoe UI',sans-serif;background:#0d0d14;color:#e8e8f0;margin:0;padding:1.5rem;}}
  h1{{font-size:1.1rem;margin-bottom:1rem;}}
  .dot{{display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};margin-right:.5rem;}}
  table{{border-collapse:collapse;width:100%;font-size:.85rem;}}
  th{{text-align:left;padding:.4rem .6rem;color:#9898b8;border-bottom:1px solid #2a2a3e;}}
  td{{padding:.35rem .6rem;border-bottom:1px solid #1a1a2e;}}
  .meta{{font-size:.75rem;color:#5a5a7a;margin-top:1rem;}}
</style></head><body>
<h1><span class="dot"></span>CRT Daemon — {ok_count}/{total} OK &nbsp;·&nbsp; {datetime.now().strftime('%H:%M:%S')}</h1>
<table><thead><tr><th>Komponens</th><th>Státusz</th><th>Típus</th><th>Utolsó OK</th><th>Hiba</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="meta">Frissítés: 20s &nbsp;·&nbsp; CRT Daemon :8099 &nbsp;·&nbsp;
<a href="/status" style="color:#7c6af7">JSON</a> &nbsp;·&nbsp;
<a href="/metrics" style="color:#7c6af7">OS metrikák</a> &nbsp;·&nbsp;
<a href="http://localhost:8000/ui/kezelőpult.html" style="color:#7c6af7">CRT →</a></div>
</body></html>"""
    return web.Response(text=html, content_type="text/html")


async def handle_restart(req):
    cid = req.match_info.get("component_id")
    comp = next((c for c in COMPONENTS if c["id"] == cid), None)
    if not comp:
        return web.Response(text=json.dumps({"error": "nem található"}),
                            content_type="application/json", status=404)
    await _on_down(comp)
    return web.Response(text=json.dumps({"status": "restart kísérlet", "id": cid}),
                        content_type="application/json")


# ── HEARTBEAT EMAIL (naponta) ─────────────────────────────────

async def heartbeat_loop():
    """24 óránként státusz email."""
    await asyncio.sleep(60)   # indulás után 1 perccel az első
    while True:
        ok  = sum(1 for s in state.values() if s["status"] == "ok")
        dn  = sum(1 for s in state.values() if s["status"] == "down")
        met = _os_metrics()
        body = (
            f"CRT Daemon napi jelentés — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Komponensek: {ok}/{len(state)} OK, {dn} leállott\n"
            f"CPU: {met.get('cpu_pct','?')}%  RAM: {met.get('ram_pct','?')}%  "
            f"Disk szabad: {met.get('disk_free_gb','?')} GB\n\n"
        )
        for s in state.values():
            if s["status"] != "ok":
                body += f"  ✗ {s['label']}: {s.get('error','?')}\n"
        await asyncio.get_event_loop().run_in_executor(
            None, _send_email, "Napi státusz", body
        )
        await asyncio.sleep(86400)   # 24 óra


# ── MAIN ──────────────────────────────────────────────────────

async def main():
    log.info("CRT Daemon indul — port %d", DAEMON_PORT)

    # HTTP szerver
    if AIOHTTP:
        app = web.Application()
        app.router.add_get("/",                  handle_ui)
        app.router.add_get("/ui",                handle_ui)
        app.router.add_get("/status",            handle_status)
        app.router.add_get("/metrics",           handle_metrics)
        app.router.add_post("/restart/{component_id}", handle_restart)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", DAEMON_PORT)
        await site.start()
        log.info("HTTP szerver: http://localhost:%d", DAEMON_PORT)
    else:
        log.warning("aiohttp nincs — HTTP szerver kikapcsolva (pip install aiohttp)")

    # Háttér taskok
    asyncio.create_task(watchdog_loop())
    asyncio.create_task(heartbeat_loop())

    log.info("Daemon fut. Ctrl+C a leállításhoz.")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        log.info("Daemon leáll.")


if __name__ == "__main__":
    asyncio.run(main())
