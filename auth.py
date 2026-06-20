"""
CRT Ajánlatsegéd – Auth modul v0.4
PIN + Email 2FA + JWT + Brute force védelem
Függőségek: bcrypt · python-jose[cryptography]
  py -3.11 -m pip install bcrypt python-jose[cryptography]
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
import bcrypt
import secrets
import smtplib
import logging
import uuid
import os
from env_detect import get_db_url, get_jwt_secret
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

router = APIRouter(prefix="/auth", tags=["auth"])
log    = logging.getLogger("CRT.auth")
security = HTTPBearer(auto_error=False)

# ── KONFIGURÁCIÓ ──────────────────────────────────────────────
DB_URL       = get_db_url()
JWT_SECRET   = get_jwt_secret()
JWT_ALGO     = "HS256"
JWT_HOURS    = 8
MAX_ATTEMPTS = 4
LOCKOUT_MIN  = 30

engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=3)

# ── MODELLEK ──────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    pin: str

class VerifyRequest(BaseModel):
    username: str
    code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    username:     str
    role:         str
    expires_in:   int

class UserCreate(BaseModel):
    username: str
    pin:      str
    email:    str
    role:     str = "user"

class UserUpdate(BaseModel):
    email:  str | None = None
    role:   str | None = None
    active: bool | None = None

# ── SEGÉDFÜGGVÉNYEK ───────────────────────────────────────────

def get_config(key: str) -> str | None:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM system_config WHERE key = :k"), {"k": key}
            ).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def create_jwt(user_id: int, username: str, role: str) -> str:
    if not JWT_AVAILABLE:
        raise HTTPException(500, "JWT lib hiányzik – telepítés: py -3.11 -m pip install python-jose[cryptography]")
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS)
    payload = {
        "user_id":  user_id,
        "username": username,
        "role":     role,
        "exp":      exp,
        "iat":      datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_jwt(token: str) -> dict:
    if not JWT_AVAILABLE:
        raise HTTPException(500, "JWT lib hiányzik")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError as e:
        raise HTTPException(401, f"Érvénytelen vagy lejárt token: {e}")


def send_otp_email(to_email: str, code: str, username: str) -> bool:
    host = get_config("smtp_host") or os.environ.get("CRT_SMTP_HOST", "")
    port = int(get_config("smtp_port") or os.environ.get("CRT_SMTP_PORT", "587"))
    user = get_config("smtp_user") or os.environ.get("CRT_SMTP_USER", "")
    pwd  = get_config("smtp_pass") or os.environ.get("CRT_SMTP_PASS", "")
    frm  = get_config("smtp_from") or user

    if not host:
        log.warning(f"[DEV] SMTP nincs beállítva – OTP kód a loggban: {code}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"CRT Ajánlatsegéd – Belépési kód: {code}"
        msg["From"]    = frm
        msg["To"]      = to_email
        body = (
            f"Szia {username}!\n\n"
            f"A CRT Ajánlatsegédbe való belépéshez szükséges kód:\n\n"
            f"  {code}\n\n"
            f"A kód 10 percig érvényes.\n"
            f"Ha nem te próbáltál belépni, értesítsd a rendszergazdát.\n\n"
            f"– CRT Ajánlatsegéd"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(host, port, timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(user, pwd)
            srv.sendmail(frm, to_email, msg.as_string())
        log.info(f"OTP email elküldve: {to_email}")
        log.warning(f"[DEV] OTP kód a loggban: {code}")
        return True
    except Exception as e:
        log.error(f"Email küldési hiba ({to_email}): {e}")
        log.warning(f"[DEV] OTP kód a loggban (email hiba): {code}")
        return False


def email_hint(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


# ── AUTH FÜGGŐSÉGEK (más routerekhez) ─────────────────────────

def _read_daemon_token() -> str:
    """DAEMON_TOKEN olvasás .env-ből — daemon service account auth."""
    try:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("DAEMON_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.environ.get("DAEMON_TOKEN", "")


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency – JWT ellenőrzés, bármely bejelentkezett user.
    Daemon service account: DAEMON_TOKEN a .env-ben static bearer tokenként.
    """
    if not credentials:
        raise HTTPException(401, "Bejelentkezés szükséges")
    daemon_token = _read_daemon_token()
    if daemon_token and credentials.credentials == daemon_token:
        return {"user_id": 0, "username": "daemon", "role": "admin"}
    return decode_jwt(credentials.credentials)


def require_admin(payload: dict = Depends(require_auth)) -> dict:
    """FastAPI dependency – admin role ellenőrzés"""
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin jogosultság szükséges")
    return payload


# ── ENDPOINTOK ────────────────────────────────────────────────

@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """1. lépés: felhasználónév + PIN → OTP email küldés"""
    ip = request.client.host if request.client else "unknown"

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, username, pin_hash, email, role, active, "
            "locked_until, attempt_count "
            "FROM users WHERE LOWER(username) = LOWER(:u)"
        ), {"u": req.username.strip()}).fetchone()

    # Mindig ugyanolyan hibaüzenet – nem deríthető ki létezik-e a user
    generic_err = "Hibás felhasználónév vagy PIN"

    if not row:
        raise HTTPException(401, generic_err)

    uid, uname, pin_hash, email, role, active, locked_until, attempts = row

    if not active:
        raise HTTPException(403, "A fiók inaktív – fordulj a rendszergazdához")

    if locked_until and datetime.now() < locked_until:
        mins = int((locked_until - datetime.now()).total_seconds() / 60) + 1
        raise HTTPException(403, f"Fiók zárolva – próbáld újra {mins} perc múlva")

    pin_ok = bcrypt.checkpw(
        req.pin.encode(),
        pin_hash.encode() if isinstance(pin_hash, str) else pin_hash
    )

    if not pin_ok:
        new_attempts = (attempts or 0) + 1
        with engine.begin() as conn:
            if new_attempts >= MAX_ATTEMPTS:
                lockout_until = datetime.now() + timedelta(minutes=LOCKOUT_MIN)
                conn.execute(text(
                    "UPDATE users SET attempt_count=:a, locked_until=:l WHERE id=:id"
                ), {"a": new_attempts, "l": lockout_until, "id": uid})
                log.warning(f"Fiók zárolva ({LOCKOUT_MIN} perc): {uname} [{ip}]")
                raise HTTPException(403,
                    f"Fiók {LOCKOUT_MIN} percre zárolva – {MAX_ATTEMPTS} hibás kísérlet")
            else:
                conn.execute(text(
                    "UPDATE users SET attempt_count=:a WHERE id=:id"
                ), {"a": new_attempts, "id": uid})
        remaining = MAX_ATTEMPTS - new_attempts
        raise HTTPException(401, f"Hibás PIN – még {remaining} kísérlet")

    # PIN OK – OTP generálás
    code       = str(secrets.randbelow(900000) + 100000)
    expires_at = datetime.now() + timedelta(minutes=10)

    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM auth_tokens WHERE user_id=:uid AND used=false"
        ), {"uid": uid})
        conn.execute(text(
            "INSERT INTO auth_tokens (user_id, code, expires_at) VALUES (:uid,:code,:exp)"
        ), {"uid": uid, "code": code, "exp": expires_at})
        conn.execute(text(
            "UPDATE users SET attempt_count=0, locked_until=NULL WHERE id=:id"
        ), {"id": uid})

    sent = send_otp_email(email, code, uname) if email else False
    if not email:
        log.warning(f"Nincs email cím: {uname} – OTP: {code}")

    log.info(f"Login 1. lépés OK: {uname} [{ip}]")
    return {
        "status":     "otp_sent",
        "message":    "Kód elküldve – ellenőrizd az email-t (10 perc érvényes)",
        "email_hint": email_hint(email),
    }


@router.post("/verify", response_model=TokenResponse)
async def verify(req: VerifyRequest, request: Request):
    """2. lépés: OTP kód → JWT token kiadás"""
    ip = request.client.host if request.client else "unknown"

    with engine.connect() as conn:
        user = conn.execute(text(
            "SELECT id, username, role FROM users "
            "WHERE LOWER(username)=LOWER(:u) AND active=true"
        ), {"u": req.username.strip()}).fetchone()

    if not user:
        raise HTTPException(401, "Érvénytelen kérés")

    uid, uname, role = user

    with engine.connect() as conn:
        tok = conn.execute(text(
            "SELECT id FROM auth_tokens "
            "WHERE user_id=:uid AND code=:code "
            "AND used=false AND expires_at > NOW()"
        ), {"uid": uid, "code": req.code.strip()}).fetchone()

    if not tok:
        raise HTTPException(401, "Érvénytelen vagy lejárt kód")

    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE auth_tokens SET used=true WHERE id=:id"
        ), {"id": tok[0]})
        conn.execute(text(
            "INSERT INTO audit_log (log_id, user_id, action, timestamp, ip_address) "
            "VALUES (:lid, :uid, 'login', NOW(), :ip)"
        ), {"lid": str(uuid.uuid4()), "uid": str(uid), "ip": ip})

    token = create_jwt(uid, uname, role)
    log.info(f"Login sikeres: {uname} role={role} [{ip}]")

    return {
        "access_token": token,
        "token_type":   "bearer",
        "username":     uname,
        "role":         role,
        "expires_in":   JWT_HOURS * 3600,
    }


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials:
        try:
            p = decode_jwt(credentials.credentials)
            log.info(f"Logout: {p.get('username')}")
        except Exception:
            pass
    return {"status": "ok", "message": "Kijelentkezve"}


@router.get("/me")
async def me(payload: dict = Depends(require_auth)):
    return {
        "user_id":  payload["user_id"],
        "username": payload["username"],
        "role":     payload["role"],
    }


# ── ADMIN – FELHASZNÁLÓKEZELÉS ────────────────────────────────

@router.get("/admin/users")
async def list_users(payload: dict = Depends(require_admin)):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, username, email, role, active, locked_until, "
            "attempt_count, created_at FROM users ORDER BY id"
        )).fetchall()
    return {"users": [dict(r._mapping) for r in rows]}


@router.post("/admin/users")
async def create_user(body: UserCreate, payload: dict = Depends(require_admin)):
    try:
        import bcrypt as _bcrypt
    except ImportError:
        raise HTTPException(500, "bcrypt hiányzik")

    pin_hash = _bcrypt.hashpw(body.pin.encode(), _bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (username, pin_hash, email, role, active, created_at) "
                "VALUES (:u, :ph, :e, :r, true, NOW())"
            ), {"u": body.username, "ph": pin_hash, "e": body.email, "r": body.role})
    except Exception as e:
        raise HTTPException(400, f"Létrehozási hiba: {e}")
    log.info(f"Új user: {body.username} (admin: {payload['username']})")
    return {"status": "ok", "username": body.username}


@router.patch("/admin/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate,
                      payload: dict = Depends(require_admin)):
    updates, params = [], {"id": user_id}
    if body.email  is not None: updates.append("email=:email");   params["email"]  = body.email
    if body.role   is not None: updates.append("role=:role");     params["role"]   = body.role
    if body.active is not None: updates.append("active=:active"); params["active"] = body.active
    if not updates:
        raise HTTPException(400, "Nincs módosítandó adat")
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE users SET {', '.join(updates)} WHERE id=:id"), params)
    return {"status": "ok"}


@router.post("/admin/users/{user_id}/unlock")
async def unlock_user(user_id: int, payload: dict = Depends(require_admin)):
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE users SET locked_until=NULL, attempt_count=0 WHERE id=:id"
        ), {"id": user_id})
    log.info(f"User feloldva: id={user_id} (admin: {payload['username']})")
    return {"status": "ok"}


@router.patch("/admin/users/{user_id}/pin")
async def reset_pin(user_id: int, body: dict, payload: dict = Depends(require_admin)):
    new_pin = body.get("pin", "")
    if len(new_pin) != 6 or not new_pin.isdigit():
        raise HTTPException(400, "A PIN pontosan 6 számjegy kell legyen")
    try:
        import bcrypt as _bcrypt
    except ImportError:
        raise HTTPException(500, "bcrypt hiányzik")
    pin_hash = _bcrypt.hashpw(new_pin.encode(), _bcrypt.gensalt()).decode()
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE users SET pin_hash=:ph WHERE id=:id"
        ), {"ph": pin_hash, "id": user_id})
    log.info(f"PIN módosítva: id={user_id} (admin: {payload['username']})")
    return {"status": "ok"}


# ── VÉSZKULCS – JWT nélküli admin visszaállítás ───────────────
# Aktiválás: CRT_EMERGENCY_KEY env var beállítása (legalább 16 karakter)
# Használat: POST /auth/emergency  {"key":"...", "username":"...", "new_pin":"123456"}

class EmergencyRequest(BaseModel):
    key:      str
    username: str
    new_pin:  str = ""

@router.post("/emergency")
async def emergency_reset(body: EmergencyRequest, request: Request):
    emergency_key = os.environ.get("CRT_EMERGENCY_KEY", "")
    if not emergency_key or len(emergency_key) < 16:
        raise HTTPException(503, "Vészkulcs nincs beállítva (CRT_EMERGENCY_KEY env var)")
    if body.key != emergency_key:
        log.warning(f"Vészkulcs: hibás kulcs kísérlet  ip={request.client.host}")
        raise HTTPException(403, "Érvénytelen vészkulcs")

    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT id FROM users WHERE username=:u"
        ), {"u": body.username}).fetchone()
        if not row:
            raise HTTPException(404, f"Felhasználó nem található: {body.username}")
        user_id = row[0]

        conn.execute(text(
            "UPDATE users SET locked_until=NULL, attempt_count=0 WHERE id=:id"
        ), {"id": user_id})

        if body.new_pin:
            if len(body.new_pin) != 6 or not body.new_pin.isdigit():
                raise HTTPException(400, "A PIN pontosan 6 számjegy kell legyen")
            pin_hash = bcrypt.hashpw(body.new_pin.encode(), bcrypt.gensalt()).decode()
            conn.execute(text(
                "UPDATE users SET pin_hash=:ph WHERE id=:id"
            ), {"ph": pin_hash, "id": user_id})

        conn.execute(text(
            "INSERT INTO audit_log (log_id, user_id, action, description, timestamp, ip_address) "
            "VALUES (:lid, :uid, 'emergency_reset', :desc, NOW(), :ip)"
        ), {"lid": str(uuid.uuid4()), "uid": str(user_id), "desc": f"Vészkulcs: {body.username}", "ip": request.client.host})

    log.warning(f"VÉSZKULCS HASZNÁLVA: {body.username}  ip={request.client.host}")
    return {"status": "ok", "username": body.username, "pin_changed": bool(body.new_pin)}


# ── ADMIN – SYSTEM CONFIG ─────────────────────────────────────

_CONFIG_ALLOWED = {
    "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_from",
    "smtp_from_name", "smtp_tls",
    "claude_api_key", "claude_model",
    "ai_conf_high", "ai_conf_low",
    "scrape_interval_hours", "max_price_age_days", "auto_scrape",
    "quote_validity_days", "company_name", "company_tax",
}

@router.get("/admin/config")
async def get_config_all(payload: dict = Depends(require_admin)):
    """Összes system_config kulcs visszaadása (jelszavak helyett boolean)"""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT key, value FROM system_config")).fetchall()
    config = {}
    for r in rows:
        k, v = r[0], r[1]
        if k in ("smtp_pass", "claude_api_key"):
            config[k] = bool(v and v.strip())
        else:
            config[k] = v
    return {"config": config}


@router.patch("/admin/config")
async def set_config(body: dict, payload: dict = Depends(require_admin)):
    """Egy vagy több system_config kulcs módosítása"""
    unknown = set(body.keys()) - _CONFIG_ALLOWED
    if unknown:
        raise HTTPException(400, f"Ismeretlen konfig kulcsok: {', '.join(unknown)}")
    if not body:
        raise HTTPException(400, "Üres kérés")
    try:
        with engine.begin() as conn:
            for k, v in body.items():
                val = str(v) if v is not None else ""
                conn.execute(text(
                    "INSERT INTO system_config (key, value) "
                    "VALUES (:k, :v) "
                    "ON CONFLICT (key) DO UPDATE SET value=:v"
                ), {"k": k, "v": val})
        log.info(f"Config módosítva: {list(body.keys())} (admin: {payload['username']})")
        return {"status": "ok", "updated": list(body.keys())}
    except Exception as e:
        raise HTTPException(500, f"Mentési hiba: {e}")


@router.post("/admin/config/test-smtp")
async def test_smtp(payload: dict = Depends(require_admin)):
    """SMTP kapcsolat teszt – teszt emailt küld a bejelentkezett admin email-jére"""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT email FROM users WHERE id=:id"), {"id": payload["user_id"]}).fetchone()
    to_email = row[0] if row else None
    if not to_email:
        raise HTTPException(400, "Az admin fiókhoz nincs email cím megadva")

    host = get_config("smtp_host") or os.environ.get("CRT_SMTP_HOST", "")
    if not host:
        raise HTTPException(400, "SMTP host nincs beállítva")

    ok = send_otp_email(to_email, "TEST-OK", payload["username"])
    if ok:
        return {"status": "ok", "message": f"Teszt email elküldve: {to_email}"}
    raise HTTPException(500, "Email küldési hiba – ellenőrizd az SMTP adatokat")


# ── SAJÁT PIN CSERE ───────────────────────────────────────────

class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str

@router.post("/change-pin")
async def change_own_pin(body: ChangePinRequest, payload: dict = Depends(require_auth)):
    """Bejelentkezett user saját PIN-jét cseréli"""
    if len(body.new_pin) != 6 or not body.new_pin.isdigit():
        raise HTTPException(400, "Az új PIN pontosan 6 számjegy kell legyen")
    if body.current_pin == body.new_pin:
        raise HTTPException(400, "Az új PIN megegyezik a régivel")

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, pin_hash FROM users WHERE id=:id AND active=true"
        ), {"id": payload["user_id"]}).fetchone()

    if not row:
        raise HTTPException(404, "Felhasználó nem található")

    uid, pin_hash = row
    cur_ok = bcrypt.checkpw(
        body.current_pin.encode(),
        pin_hash.encode() if isinstance(pin_hash, str) else pin_hash
    )
    if not cur_ok:
        raise HTTPException(401, "Hibás jelenlegi PIN")

    new_hash = bcrypt.hashpw(body.new_pin.encode(), bcrypt.gensalt()).decode()
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET pin_hash=:ph WHERE id=:id"), {"ph": new_hash, "id": uid})

    log.info(f"Saját PIN csere: {payload['username']}")
    return {"status": "ok", "message": "PIN sikeresen módosítva"}
