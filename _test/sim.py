#!/usr/bin/env python3
"""
CRT Rendszer Szimulátor v2 — teljes API lefedés
Futtatás: py -3.11 _test/sim.py [--mode smoke|api|ai|export|full] [--silent] [--no-cleanup] [--otp XXXXXX]
"""
import sys
import os
import re
import time
import argparse
import requests
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SIM_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_BASE = "http://localhost:8000"

# OTP logfájlok keresési sorrendje
_LOG_CANDIDATES = [
    os.path.join(SIM_ROOT, "backend.err"),
    os.path.join(SIM_ROOT, "backend.log"),
    os.path.join(SIM_ROOT, "logs", "backend", "backend.log"),
]

ADMIN_USER = os.environ.get("CRT_ADMIN_USER", "admin")
ADMIN_PIN  = os.environ.get("CRT_ADMIN_PIN",  "123456")

_RUN_ID = str(int(time.time()))[-6:]
TEST_PRODUCT = {
    "name":        f"SIM_TEST Schneider A9F74316 {_RUN_ID}",
    "crt_code":    f"SIM-{_RUN_ID}",
    "unit":        "db",
    "description": "16A 3P C kismegszakító — SZIMULÁTORTESZT",
    "ean":         None,
    "part_number": "A9F74316",
}
TEST_QUOTE = {
    "client_name": f"SIM_TEST Bt. {_RUN_ID}",
    "client_ref":  f"SIM-2026-{_RUN_ID}",
    "notes":       "Automatikus szimulátorteszt — törölhető",
}
TEST_AI_INPUT = "Schneider Electric kismegszakító 16 amperes háromfázisú C karakterisztika"
TEST_WEB_SOURCE = {
    "name":        f"SIM_TEST Forrás {_RUN_ID}",
    "url":         "https://example.com/sim-test",
    "source_type": "login_required",
    "username":    "simuser",
    "password":    "simpass123",
}

results = []
SILENT  = False


def record(step, desc, ok, ms, note=""):
    results.append((step, desc, ok, ms, note))


def err(msg):
    print(f"\n  FATALIS HIBA: {msg}", flush=True)
    print_report()
    sys.exit(2)


def p(msg):
    if not SILENT:
        print(msg, flush=True)


def tick(step, desc, ok, ms, note=""):
    record(step, desc, ok, ms, note)
    if SILENT:
        return
    icon      = "✓" if ok else ("⚠" if note.startswith("⚠") else "✗")
    color_on  = "\033[92m" if ok else ("\033[93m" if note.startswith("⚠") else "\033[91m")
    color_off = "\033[0m"
    note_str  = f"  {note}" if note else ""
    print(f"  [{step:>3}] {color_on}{icon}{color_off}  {desc:<32} {ms:>6.0f}ms{note_str}", flush=True)


def auto_otp(max_age_sec=90):
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*OTP k.*a loggban: (\d{6})")
    for path in _LOG_CANDIDATES:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for line in reversed(lines):
                m = pattern.search(line)
                if m:
                    ts  = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    age = time.time() - ts.timestamp()
                    if age <= max_age_sec:
                        return m.group(2)
        except FileNotFoundError:
            continue
    return None


def api(method, path, token=None, timeout=15, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{API_BASE}{path}", headers=headers, timeout=timeout, **kwargs)


# ── SMOKE ─────────────────────────────────────────────────────────

def step_smoke():
    p("\n  — Smoke —")

    t = time.time()
    try:
        r = api("GET", "/health")
        ok = r.status_code == 200 and r.json().get("db") == "ok"
    except Exception:
        ok = False
    tick("S1", "FastAPI /health", ok, (time.time()-t)*1000)
    if not ok:
        err("Backend nem elérhető — indítsd el a szervert.")

    t = time.time()
    try:
        r = requests.get("http://localhost:8001/api/v2/heartbeat", timeout=5)
        ok = r.status_code == 200
        note = ""
    except Exception:
        ok = False
        note = "⚠ ChromaDB nem fut (nem blokkoló)"
    tick("S2", "ChromaDB heartbeat", ok or bool(note), (time.time()-t)*1000, note)

    t = time.time()
    try:
        r = api("GET", "/status/widget")
        ok = r.status_code == 200
        note = ""
    except Exception:
        ok = False
        note = r.text[:40] if 'r' in dir() else ""
    tick("S3", "Status widget", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r = api("GET", "/db/test")
        ok = r.status_code == 200
    except Exception:
        ok = False
    tick("S4", "DB kapcsolat teszt", ok, (time.time()-t)*1000)


# ── AUTH ──────────────────────────────────────────────────────────

def step_auth(manual_otp=None):
    p("\n  — Auth —")

    t = time.time()
    try:
        r = api("POST", "/auth/login", json={"username": ADMIN_USER, "pin": ADMIN_PIN})
        ok = r.status_code == 200 and r.json().get("status") == "otp_sent"
    except Exception:
        ok = False
    tick("A1", "Login (PIN)", ok, (time.time()-t)*1000)
    if not ok:
        err(f"Login sikertelen. user='{ADMIN_USER}' pin='{ADMIN_PIN}'")

    if manual_otp:
        otp = manual_otp
        tick("A2", "OTP (manuális)", True, 0, f"kód: {otp}")
    else:
        p("     OTP kiolvasás logból...")
        time.sleep(1.5)
        otp = auto_otp(max_age_sec=90)
        ok  = otp is not None
        tick("A2", "OTP (logból)", ok, 0, f"kód: {otp}" if ok else "nem található")
        if not ok:
            err("OTP nem olvasható. Add meg kézzel: --otp XXXXXX")

    t = time.time()
    try:
        r = api("POST", "/auth/verify", json={"username": ADMIN_USER, "code": otp})
        ok    = r.status_code == 200 and "access_token" in r.json()
        token = r.json().get("access_token") if ok else None
    except Exception:
        ok = False; token = None
    tick("A3", "OTP verify / JWT", ok, (time.time()-t)*1000)
    if not ok:
        err("OTP verify sikertelen.")

    t = time.time()
    try:
        r = api("GET", "/auth/me", token=token)
        ok   = r.status_code == 200
        note = r.json().get("username", "") if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("A4", "Auth /me", ok, (time.time()-t)*1000, note)

    return token


# ── CIKKTÖRZS ────────────────────────────────────────────────────

def step_products(token):
    p("\n  — Cikktörzs —")
    item_id = None

    t = time.time()
    try:
        r = api("POST", "/cikktorzs/save", token=token,
                json={"items": [TEST_PRODUCT], "tipus": "termek"})
        ok = r.status_code == 200 and r.json().get("saved", 0) > 0
    except Exception:
        ok = False
    tick("P1", "Termék CREATE", ok, (time.time()-t)*1000)
    if not ok:
        return None

    t = time.time()
    try:
        r = api("GET", "/cikktorzs/search?q=SIM_TEST", token=token)
        ok = r.status_code == 200
        if ok:
            hits = r.json().get("results", r.json() if isinstance(r.json(), list) else [])
            ok = len(hits) > 0
            item_id = hits[0].get("item_id") if ok else None
    except Exception:
        ok = False
    tick("P2", "Termék KERESÉS", ok, (time.time()-t)*1000,
         f"id={item_id[:8]}…" if item_id else "")

    t = time.time()
    try:
        r  = api("GET", "/cikktorzs/tree", token=token)
        ok = r.status_code == 200
        d  = r.json() if ok else {}
        cats  = len(d.get("categories", []))
        items = len(d.get("products", [])) + len(d.get("activities", []))
        note  = f"{cats} kat, {items} tétel" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("P3", "Cikktörzs fa", ok, (time.time()-t)*1000, note)

    return item_id


# ── ÁRAK ─────────────────────────────────────────────────────────

def step_prices(token, item_id):
    p("\n  — Árak —")
    price_id = None

    t = time.time()
    try:
        r = api("POST", "/prices/", token=token, json={
            "item_id": item_id, "price_type": "lista",
            "price": 4250.0, "currency": "HUF",
        })
        ok       = r.status_code in (200, 201)
        price_id = r.json().get("id") if ok else None
    except Exception:
        ok = False
    tick("PR1", "Ár rögzítés", ok, (time.time()-t)*1000)

    t = time.time()
    try:
        r  = api("GET", f"/prices/best/{item_id}", token=token)
        ok = r.status_code == 200
        d  = r.json() if ok else {}
        note = f"legolcsóbb: {d.get('best', {}).get('price','?')} HUF" if ok and d.get("best") else (
               "nincs ár" if ok else r.text[:40])
    except Exception:
        ok = False; note = ""
    tick("PR2", "Legjobb ár lekérés", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r     = api("GET", f"/prices/?item_id={item_id}", token=token)
        ok    = r.status_code == 200
        count = len(r.json().get("prices", [])) if ok else 0
        note  = f"{count} ár" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("PR3", "Árlista (filter)", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r  = api("GET", "/prices/stats", token=token)
        ok = r.status_code == 200
        note = f"total={r.json().get('total','?')}" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("PR4", "Ár statisztika", ok, (time.time()-t)*1000, note)

    # Egy extra árat rögzítünk, majd töröljük (DELETE teszt)
    del_id = None
    try:
        r2 = api("POST", "/prices/", token=token, json={
            "item_id": item_id, "price_type": "egyedi",
            "price": 3999.0, "currency": "HUF",
        })
        del_id = r2.json().get("id") if r2.status_code in (200,201) else None
    except Exception:
        pass

    t = time.time()
    if del_id:
        try:
            r  = api("DELETE", f"/prices/{del_id}", token=token)
            ok = r.status_code in (200, 204)
            note = "" if ok else r.text[:40]
        except Exception:
            ok = False; note = ""
    else:
        ok = False; note = "nincs price_id"
    tick("PR5", "Ár törlés", ok, (time.time()-t)*1000, note)

    return price_id


# ── AJÁNLAT ──────────────────────────────────────────────────────

def step_quotes(token, item_id):
    p("\n  — Ajánlat —")
    quote_id = None
    line_id  = None

    t = time.time()
    try:
        r = api("POST", "/quotes/", token=token, json={
            "client_name": TEST_QUOTE["client_name"],
            "client_ref":  TEST_QUOTE["client_ref"],
            "notes":       TEST_QUOTE["notes"],
            "valid_days":  30,
        })
        ok       = r.status_code in (200, 201)
        quote_id = r.json().get("id") if ok else None
    except Exception:
        ok = False
    tick("Q1", "Ajánlat CREATE", ok, (time.time()-t)*1000,
         f"id={quote_id}" if quote_id else "")
    if not ok:
        return None, None

    t = time.time()
    try:
        r = api("POST", f"/quotes/{quote_id}/lines", token=token, json={
            "line_no": 1, "item_type": "product", "item_id": item_id,
            "name": TEST_PRODUCT["name"], "quantity": 2.0,
            "unit": "db", "unit_price": 4250.0, "currency": "HUF",
            "notes": "SIM_TEST sor",
        })
        ok      = r.status_code in (200, 201)
        line_id = r.json().get("id") if ok else None
    except Exception:
        ok = False
    tick("Q2", "Ajánlat sor", ok, (time.time()-t)*1000)

    t = time.time()
    try:
        r  = api("GET", f"/quotes/{quote_id}", token=token)
        ok = r.status_code == 200
    except Exception:
        ok = False
    tick("Q3", "Ajánlat READ", ok, (time.time()-t)*1000)

    t = time.time()
    try:
        r     = api("GET", "/quotes/", token=token)
        ok    = r.status_code == 200
        count = len(r.json()) if ok and isinstance(r.json(), list) else (
                r.json().get("total", "?") if ok else "")
        note  = f"{count} ajánlat" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("Q4", "Ajánlat lista", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r  = api("PATCH", f"/quotes/{quote_id}", token=token,
                 json={"notes": "SIM_TEST frissítés"})
        ok = r.status_code in (200, 204)
        note = "" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("Q5", "Ajánlat PATCH", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r    = api("GET", f"/quotes/{quote_id}/summary", token=token)
        ok   = r.status_code == 200
        note = f"nettó: {r.json().get('grand_total','?')}" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("Q6", "Ajánlat összesítő", ok, (time.time()-t)*1000, note)

    # Sor törlés (ha volt line_id)
    t = time.time()
    if line_id:
        try:
            r  = api("DELETE", f"/quotes/{quote_id}/lines/{line_id}", token=token)
            ok = r.status_code in (200, 204)
            note = "" if ok else r.text[:40]
        except Exception:
            ok = False; note = ""
    else:
        ok = False; note = "nincs line_id"
    tick("Q7", "Ajánlat sor törlés", ok, (time.time()-t)*1000, note)

    return quote_id, line_id


# ── WEB FORRÁS ────────────────────────────────────────────────────

def step_web_source(token):
    p("\n  — Web forrás —")
    src_id = None

    t = time.time()
    try:
        r = api("POST", "/web/sources", token=token, json=TEST_WEB_SOURCE)
        ok     = r.status_code in (200, 201)
        src_id = r.json().get("id") if ok else None
    except Exception:
        ok = False
    tick("W1", "Web forrás CREATE", ok, (time.time()-t)*1000)

    t = time.time()
    try:
        r  = api("GET", f"/web/sources/{src_id}", token=token)
        ok = r.status_code == 200
    except Exception:
        ok = False
    tick("W2", "Web forrás READ", ok, (time.time()-t)*1000)

    t = time.time()
    try:
        r     = api("GET", "/web/sources", token=token)
        ok    = r.status_code == 200
        d     = r.json() if ok else {}
        count = d.get("total", len(d.get("sources", []))) if ok else "?"
        note  = f"{count} forrás" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("W3", "Web forrás lista", ok, (time.time()-t)*1000, note)

    t = time.time()
    if src_id:
        try:
            r  = api("PATCH", f"/web/sources/{src_id}", token=token,
                     json={"name": f"SIM_TEST Frissítve {_RUN_ID}"})
            ok = r.status_code in (200, 204)
            note = "" if ok else r.text[:40]
        except Exception:
            ok = False; note = ""
    else:
        ok = False; note = "nincs src_id"
    tick("W4", "Web forrás PATCH", ok, (time.time()-t)*1000, note)

    t = time.time()
    if src_id:
        try:
            r  = api("POST", f"/web/sources/{src_id}/ping", token=token)
            ok = r.status_code in (200, 202)
            note = r.json().get("status","") if ok else r.text[:40]
        except Exception:
            ok = False; note = ""
    else:
        ok = False; note = "nincs src_id"
    tick("W5", "Web forrás ping", ok, (time.time()-t)*1000, note)

    return src_id


# ── AI ────────────────────────────────────────────────────────────

def step_ai(token):
    p("\n  — AI azonosítás —")

    t = time.time()
    try:
        r = api("POST", "/cikktorzs/identify", token=token,
                timeout=60, json={"items": [TEST_AI_INPUT]})
        ok = r.status_code == 200
        if ok:
            res  = r.json().get("results", [])
            conf = res[0].get("confidence", 0) if res else 0
            note = f"conf={conf:.2f}" if conf >= 0.5 else f"⚠ conf={conf:.2f}"
        else:
            note = r.text[:50]
    except Exception as e:
        ok = False; note = f"⚠ {str(e)[:40]}"
    tick("AI1", "AI azonosítás", ok, (time.time()-t)*1000, note)


# ── CHROMA / GOLDEN ───────────────────────────────────────────────

def step_chroma(token, item_id):
    p("\n  — ChromaDB / Golden —")
    example_id = None

    t = time.time()
    try:
        r = api("POST", "/golden", token=token, json={
            "item_id": item_id, "raw_text": TEST_AI_INPUT,
            "clean_name": "Schneider Electric A9F74316", "source": "sim_test",
        })
        ok         = r.status_code in (200, 201)
        example_id = r.json().get("id") or r.json().get("example_id") if ok else None
    except Exception:
        ok = False
    tick("C1", "Golden example mentés", ok, (time.time()-t)*1000)

    t = time.time()
    try:
        r     = api("GET", f"/chroma/search?q={TEST_AI_INPUT[:30]}&limit=3", token=token)
        ok    = r.status_code == 200
        count = len(r.json()) if ok else 0
        note  = f"{count} találat" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("C2", "Vektoros keresés", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r     = api("GET", "/golden", token=token)
        ok    = r.status_code == 200
        count = len(r.json()) if ok and isinstance(r.json(), list) else (
                r.json().get("total", "?") if ok else "")
        note  = f"{count} példa" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("GL1", "Golden lista", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r    = api("GET", "/golden/stats", token=token)
        ok   = r.status_code == 200
        note = f"total={r.json().get('total','?')}" if ok else r.text[:40]
    except Exception:
        ok = False; note = ""
    tick("GL2", "Golden statisztika", ok, (time.time()-t)*1000, note)

    if example_id:
        t = time.time()
        try:
            r  = api("DELETE", f"/golden/{example_id}", token=token)
            ok = r.status_code in (200, 204)
            note = "" if ok else r.text[:40]
        except Exception:
            ok = False; note = ""
        tick("GL3", "Golden törlés", ok, (time.time()-t)*1000, note)


# ── EXPORT ────────────────────────────────────────────────────────

def step_export(token, quote_id):
    p("\n  — Export —")
    for i, fmt in enumerate(["xlsx", "docx", "pdf"], 1):
        t = time.time()
        try:
            r    = api("GET", f"/quotes/{quote_id}/export?format={fmt}", token=token)
            ok   = r.status_code == 200 and len(r.content) > 512
            note = f"{len(r.content)//1024}KB" if ok else r.text[:60]
        except Exception as e:
            ok = False; note = f"⚠ {str(e)[:40]}"
        tick(f"E{i}", f"Export {fmt.upper()}", ok, (time.time()-t)*1000, note)


# ── ADMIN ─────────────────────────────────────────────────────────

def step_admin(token):
    p("\n  — Admin —")

    t = time.time()
    try:
        r    = api("POST", "/admin/backup", token=token)
        ok   = r.status_code in (200, 201)
        note = r.json().get("file", r.json().get("path","")) if ok else r.text[:40]
    except Exception as e:
        ok = False; note = str(e)[:40]
    tick("AD1", "Admin backup", ok, (time.time()-t)*1000, note)

    t = time.time()
    try:
        r    = api("GET", "/ollama/status", token=token)
        ok   = r.status_code == 200
        note = r.json().get("status","") if ok else r.text[:40]
        if ok and "not" in note.lower():
            note = f"⚠ {note}"
    except Exception:
        ok = False; note = ""
    tick("AD2", "Ollama státusz", ok, (time.time()-t)*1000, note)


# ── AUDIT LOG ─────────────────────────────────────────────────────

def step_stats(token):
    p("\n  — Stats dashboard —")

    t = time.time()
    try:
        r    = api("GET", "/stats/dashboard", token=token)
        ok   = r.status_code == 200
        d    = r.json() if ok else {}
        sys_ = d.get("system", {})
        ai_  = d.get("ai", {})
        pr_  = d.get("prices", {})
        note = (f"db:{sys_.get('db','?')} | "
                f"motor:{ai_.get('active_motor','?')} | "
                f"lefed:{pr_.get('coverage_pct','?')}%") if ok else r.text[:60]
    except Exception as e:
        ok = False; note = str(e)[:50]
    tick("ST1", "Stats dashboard", ok, (time.time()-t)*1000, note)

    if ok:
        # 3 operatív kérdés eredménye
        t = time.time()
        sys_ok = sys_.get("db") == "ok"
        tick("ST2", "Rendszer el-e?", sys_ok, (time.time()-t)*1000,
             f"ChromaDB:{sys_.get('chromadb')} Ollama:{sys_.get('ollama')}")

        t = time.time()
        ai_ok = ai_.get("golden_count", 0) > 0
        tick("ST3", "AI alap megvan?", ai_ok, (time.time()-t)*1000,
             f"golden:{ai_.get('golden_count')} lora_kesz:{ai_.get('lora_ready')}")

        t = time.time()
        cov = pr_.get("coverage_pct", 0)
        price_ok = pr_.get("total", 0) > 0
        tick("ST4", "Arak leteznek?", price_ok, (time.time()-t)*1000,
             f"total:{pr_.get('total')} lefed:{cov}% fresh7d:{pr_.get('fresh_7d')}")


def step_audit(token):
    p("\n  — Audit log —")
    t = time.time()
    try:
        r     = api("GET", "/audit/logs?limit=50", token=token)
        ok    = r.status_code == 200
        data  = r.json() if ok else {}
        count = data.get("total", len(data) if isinstance(data, list) else 0)
        note  = f"{count} bejegyzés"
        ok    = ok and count > 0
    except Exception:
        ok = False; note = ""
    tick("AU1", "Audit log ellenőrzés", ok, (time.time()-t)*1000, note)


# ── CLEANUP ───────────────────────────────────────────────────────

def step_cleanup(token, quote_id, src_id):
    p("\n  — Cleanup —")
    deleted = 0
    for path in [
        f"/quotes/{quote_id}" if quote_id else None,
        f"/web/sources/{src_id}" if src_id else None,
    ]:
        if path:
            try:
                r = api("DELETE", path, token=token)
                if r.status_code in (200, 204):
                    deleted += 1
            except Exception:
                pass
    tick("CL", "Cleanup", True, 0, f"{deleted} rekord törölve (termék manuális)")


# ── RIPORT ────────────────────────────────────────────────────────

def print_report():
    if SILENT:
        return
    total  = len(results)
    ok_n   = sum(1 for r in results if r[2])
    warn_n = sum(1 for r in results if r[4].startswith("⚠"))
    err_n  = total - ok_n

    p("\n" + "═" * 56)
    p(f"  Eredmeny: {ok_n}/{total} OK | {warn_n} figyelmezetes | {err_n - warn_n} hiba")
    p("═" * 56)
    for _, _, ok, _, note in results:
        if not ok and note:
            p(f"  {'!' if note.startswith(chr(10060)) else 'X'}  {note}")
    if all(r[2] for r in results):
        p("  Minden lepes sikeres.")
    p("")


# ── MAIN ──────────────────────────────────────────────────────────

def main():
    global SILENT
    parser = argparse.ArgumentParser(description="CRT Rendszer Szimulator v2")
    parser.add_argument("--mode",       choices=["smoke","api","ai","export","full"], default="full")
    parser.add_argument("--silent",     action="store_true")
    parser.add_argument("--no-cleanup", action="store_true")
    parser.add_argument("--otp",        type=str, default=None)
    args   = parser.parse_args()
    SILENT = args.silent

    start = time.time()
    p("═" * 56)
    p(f"  CRT Rendszer Szimulator v2")
    p(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  mod: {args.mode}")
    p("═" * 56)

    step_smoke()
    if args.mode == "smoke":
        print_report()
        sys.exit(0 if all(r[2] for r in results) else 1)

    token = step_auth(manual_otp=args.otp)

    item_id  = None
    quote_id = None
    src_id   = None

    if args.mode in ("api", "full"):
        item_id  = step_products(token)

        if item_id:
            step_prices(token, item_id)
            quote_id, _ = step_quotes(token, item_id)
            src_id      = step_web_source(token)

        if args.mode == "full":
            step_ai(token)
            if item_id:
                step_chroma(token, item_id)

        if args.mode == "full" and quote_id:
            step_export(token, quote_id)

        step_stats(token)
        step_admin(token)
        step_audit(token)

        if not args.no_cleanup:
            step_cleanup(token, quote_id, src_id)

    elif args.mode == "ai":
        step_ai(token)

    elif args.mode == "export":
        p("\n  Export modhoz quote_id kell — futtasd full modban eloszor.")

    p(f"\n  Futasi ido: {time.time()-start:.1f} masodperc")
    print_report()
    sys.exit(0 if all(r[2] for r in results) else 1)


if __name__ == "__main__":
    main()
