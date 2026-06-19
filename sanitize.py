"""
CRT Ajánlatsegéd – Sanitizálási middleware v0.4
Minden bejövő adat ezen megy át – kivétel nem lehetséges.
FastAPI middleware + önálló segédfüggvények.
"""
import re
import html
import unicodedata
import logging
from typing import Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

log = logging.getLogger("CRT.sanitize")

# ── KONSTANSOK ────────────────────────────────────────────────

# Max méret korlátok
MAX_STRING_LEN   = 2000
MAX_NAME_LEN     = 255
MAX_URL_LEN      = 2048
MAX_JSON_BODY    = 512 * 1024   # 512 KB
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

# Veszélyes minták
_SQL_PATTERN = re.compile(
    r"(--|;|\bDROP\b|\bDELETE\b|\bINSERT\b|\bUPDATE\b|"
    r"\bSELECT\b|\bUNION\b|\bEXEC\b|\bXP_\b|\bOR\s+1=1\b|"
    r"\bAND\s+1=1\b)",
    re.IGNORECASE
)
_XSS_PATTERN = re.compile(
    r"(<script|</script|javascript:|vbscript:|onload=|onerror=|"
    r"onclick=|onmouseover=|<iframe|<object|<embed|data:text/html)",
    re.IGNORECASE
)
_PATH_TRAVERSAL = re.compile(r"\.\.[/\\]")
_NULL_BYTES     = re.compile(r"\x00")
_CONTROL_CHARS  = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Engedélyezett karakterkészlet névmezőkhöz
_SAFE_NAME = re.compile(r"^[a-zA-ZÀ-ÖØ-öø-žÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9 ,.\-_/()&+%#@!?:;\"']+$")

# Engedélyezett URL sémák
_ALLOWED_SCHEMES = {'http', 'https'}


# ── ALAP SZÖVEG TISZTÍTÁS ─────────────────────────────────────

def strip_control(s: str) -> str:
    """Vezérlőkarakterek és null byte eltávolítása."""
    s = _NULL_BYTES.sub('', s)
    s = _CONTROL_CHARS.sub('', s)
    return s


def normalize_unicode(s: str) -> str:
    """Unicode normalizálás – NFC forma, lookalike karakterek kezelése."""
    return unicodedata.normalize('NFC', s)


def sanitize_string(value: str,
                    max_len: int = MAX_STRING_LEN,
                    strip_html: bool = True,
                    allow_newlines: bool = False) -> str:
    """
    Általános szöveg szanitizálás:
    - null byte, vezérlőkarak eltávolítása
    - unicode normalizálás
    - HTML escape
    - max hossz csonkítás
    """
    if not isinstance(value, str):
        value = str(value)

    value = strip_control(value)
    value = normalize_unicode(value)

    if not allow_newlines:
        value = value.replace('\n', ' ').replace('\r', ' ')

    if strip_html:
        value = html.escape(value, quote=True)

    return value[:max_len].strip()


def sanitize_name(value: str) -> str:
    """Terméknév / felhasználónév szanitizálás – szigorúbb szabályok."""
    clean = sanitize_string(value, max_len=MAX_NAME_LEN, strip_html=True)
    if not clean:
        return ''
    # Dupla szóközök összenyomása
    clean = re.sub(r' {2,}', ' ', clean)
    return clean


def sanitize_url(value: str) -> str:
    """URL szanitizálás – csak http/https engedélyezett."""
    value = sanitize_string(value, max_len=MAX_URL_LEN, strip_html=False)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            log.warning("Tiltott URL séma blokkolva: %s", value[:80])
            return ''
    except Exception:
        return ''
    return value


def sanitize_int(value: Any, min_val: int = 0, max_val: int = 10_000_000) -> int | None:
    """Egész szám szanitizálás határokkal."""
    try:
        v = int(value)
        if v < min_val or v > max_val:
            return None
        return v
    except (TypeError, ValueError):
        return None


def sanitize_float(value: Any, min_val: float = 0.0, max_val: float = 1e9) -> float | None:
    """Lebegőpontos szám szanitizálás."""
    try:
        v = float(value)
        if v < min_val or v > max_val or v != v:  # NaN check
            return None
        return round(v, 6)
    except (TypeError, ValueError):
        return None


def sanitize_pin(value: str) -> str:
    """PIN: pontosan 6 számjegy."""
    clean = re.sub(r'\D', '', str(value or ''))
    if len(clean) != 6:
        return ''
    return clean


def sanitize_email(value: str) -> str:
    """Email cím szanitizálás."""
    clean = sanitize_string(value, max_len=254, strip_html=True)
    pattern = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
    if not pattern.match(clean):
        return ''
    return clean.lower()


def sanitize_username(value: str) -> str:
    """Felhasználónév: alfanumerikus + pont + underscore, 3–32 karakter."""
    clean = re.sub(r'[^a-zA-Z0-9._\-]', '', str(value or ''))
    if len(clean) < 3 or len(clean) > 32:
        return ''
    return clean


# ── THREAT DETEKCIÓ ───────────────────────────────────────────

def detect_sql_injection(value: str) -> bool:
    return bool(_SQL_PATTERN.search(value))


def detect_xss(value: str) -> bool:
    return bool(_XSS_PATTERN.search(value))


def detect_path_traversal(value: str) -> bool:
    return bool(_PATH_TRAVERSAL.search(value))


def has_threats(value: str) -> tuple[bool, str]:
    """
    Fenyegetés detekció egy szövegen.
    Visszatér: (van_fenyegetés, típus)
    """
    if detect_sql_injection(value):
        return True, "sql_injection"
    if detect_xss(value):
        return True, "xss"
    if detect_path_traversal(value):
        return True, "path_traversal"
    return False, ""


def scan_dict(data: dict, path: str = '') -> list[dict]:
    """
    Rekurzív dict/lista szkenner.
    Visszatér a talált fenyegetések listájával: [{path, type, snippet}]
    """
    findings = []
    if isinstance(data, dict):
        for k, v in data.items():
            findings.extend(scan_dict(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            findings.extend(scan_dict(v, f"{path}[{i}]"))
    elif isinstance(data, str):
        found, threat_type = has_threats(data)
        if found:
            findings.append({
                "path":    path,
                "type":    threat_type,
                "snippet": data[:60],
            })
    return findings


# ── DICT REKURZÍV SZANITIZÁLÁS ────────────────────────────────

def sanitize_dict(data: Any, max_depth: int = 8, _depth: int = 0) -> Any:
    """
    Rekurzív dict/lista szanitizálás.
    Minden string értéket átküld sanitize_string()-en.
    """
    if _depth > max_depth:
        return None
    if isinstance(data, dict):
        return {k: sanitize_dict(v, max_depth, _depth+1) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_dict(v, max_depth, _depth+1) for v in data]
    if isinstance(data, str):
        return sanitize_string(data)
    if isinstance(data, (int, float, bool)) or data is None:
        return data
    return str(data)[:MAX_STRING_LEN]


# ── FASTAPI MIDDLEWARE ────────────────────────────────────────

class SanitizeMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware – minden JSON kérés body-ját átvizsgálja.
    Ha SQL injection, XSS vagy path traversal kísérlet látható → 400.
    Méretkorlát ellenőrzés → 413.
    """

    def __init__(self, app: ASGIApp, log_threats: bool = True):
        super().__init__(app)
        self._log_threats = log_threats

    async def dispatch(self, request: Request, call_next) -> Response:
        # Csak JSON kérések vizsgálata
        ct = request.headers.get("content-type", "")
        if "application/json" in ct:
            body = await request.body()

            # Méretkorlát
            if len(body) > MAX_JSON_BODY:
                log.warning(
                    "Túl nagy JSON kérés blokkolva: %d byte [%s %s]",
                    len(body), request.method, request.url.path
                )
                return Response(
                    content='{"detail":"Kérés mérete meghaladja a korlátot"}',
                    status_code=413,
                    media_type="application/json"
                )

            # Gyors string szkenner a raw body-n
            text = body.decode('utf-8', errors='replace')
            found, threat_type = has_threats(text)
            if found:
                if self._log_threats:
                    log.warning(
                        "Biztonsági fenyegetés blokkolva [%s]: %s @ %s %s",
                        threat_type, text[:80], request.method, request.url.path
                    )
                return Response(
                    content=f'{{"detail":"Tiltott tartalom: {threat_type}"}}',
                    status_code=400,
                    media_type="application/json"
                )

            # Kérés body visszaállítása (Starlette-nek kell)
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request = Request(request.scope, receive=receive)

        return await call_next(request)


# ── MAIN.PY-BA BEKÖTÉS ────────────────────────────────────────
# Használat a main.py-ban:
#
#   from sanitize import SanitizeMiddleware
#   app.add_middleware(SanitizeMiddleware, log_threats=True)
#
# A middleware UTÁN add hozzá a CORSMiddleware-t, mert
# Starlette fordított sorrendben hajtja végre őket.


# ── ÖNÁLLÓ TESZT ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("OK szöveg",        "Kábelcsatorna 40x40mm PE",           False),
        ("SQL injection",     "'; DROP TABLE users; --",            True),
        ("XSS kísérlet",      "<script>alert(1)</script>",          True),
        ("Path traversal",    "../../../etc/passwd",                True),
        ("Null byte",         "hello\x00world",                     False),  # szanitizálva, nem blokkolt
        ("OK email",          "teszt@example.com",                  False),
        ("Rossz email",       "nem_email",                          False),
        ("PIN OK",            "123456",                             False),
        ("PIN rossz",         "12345a",                             False),
    ]

    print("\n── Sanitize modul önálló teszt ──")
    for name, val, expect_threat in tests:
        threat, ttype = has_threats(val)
        clean  = sanitize_string(val)
        status = "✅" if threat == expect_threat else "❌"
        print(f"  {status}  {name:<20} threat={threat:<5} ({ttype or '–':<15}) → '{clean[:40]}'")

    print("\n── Email / PIN tesztek ──")
    print(f"  sanitize_email('info@crt.hu')  = '{sanitize_email('info@crt.hu')}'")
    print(f"  sanitize_email('nem_email')    = '{sanitize_email('nem_email')}'")
    print(f"  sanitize_pin('123456')         = '{sanitize_pin('123456')}'")
    print(f"  sanitize_pin('12abc6')         = '{sanitize_pin('12abc6')}'")
    print(f"  sanitize_url('https://ok.hu')  = '{sanitize_url('https://ok.hu')}'")
    print(f"  sanitize_url('javascript:..') = '{sanitize_url('javascript:alert(1)')}'")
    print()
