# CRT Ajánlatsegéd – Biztonsági Audit v1.0
> Civil Rendszertechnika Kft. · Belső használatra · 2026-06-10
> Auditált verzió: v1.0 (LoRA pipeline kész)
> Auditált fájlok: `auth.py`, `sanitize.py`, `main.py`, `lora_router.py`, `export_router.py`, `cikktorzs_parse.py`, `.env.example`

---

## ÖSSZESÍTŐ

| Prioritás | Darab | Státusz |
|-----------|-------|---------|
| 🔴 Kritikus | 2 | Javítandó éles telepítés előtt |
| 🟡 Közepes  | 5 | Javítandó hamarosan |
| 🔵 Alacsony | 4 | Következő fejlesztési körben |
| ✅ Rendben  | 14 | Jól implementált |

---

## 🔴 KRITIKUS PROBLÉMÁK

### K-1: Hardcoded adatbázis jelszó a forráskódban

**Fájl:** `auth.py:31`, `main.py:46`

```python
DB_URL = "postgresql://crt_user:crt2026@localhost:5432/crt"
```

**Probléma:** Az adatbázis jelszó (`crt2026`) minden fájlban hardcoded. Ha a forráskód kikerül (GitHub, backup, másolás), a DB azonnal kompromittálható.

**Kockázat:** Magas — adatbázis teljes tartalma elérhető.

**Javítás:**
```python
import os
DB_URL = os.environ.get(
    "CRT_DB_URL",
    "postgresql://crt_user:crt2026@localhost:5432/crt"  # csak dev default!
)
```
Éles rendszeren a `.env` fájlba: `CRT_DB_URL=postgresql://crt_user:ERŐS_JELSZÓ@localhost:5432/crt`

---

### K-2: JWT secret alapértelmezetten fejlesztési érték

**Fájl:** `auth.py:32`

```python
JWT_SECRET = os.environ.get("CRT_JWT_SECRET", "crt_dev_secret_CHANGE_IN_PRODUCTION")
```

**Probléma:** Ha a `CRT_JWT_SECRET` env var nincs beállítva, az összes JWT token a könnyen kitalálható fejlesztési secrettel íródik alá. Bárki aki ismeri ezt az értéket (forráskód olvasásából), tetszőleges felhasználóként tud tokent hamisítani, beleértve az admin szerepkört.

**Kockázat:** Kritikus — teljes authentikáció megkerülhető.

**Javítás:** A `.env` fájlban **kötelező** megadni:
```
CRT_JWT_SECRET=<legalább 32 véletlenszerű karakter>
```
Generálás: `python -c "import secrets; print(secrets.token_hex(32))"`

A telepítőnek (`db_init.bat` / `build_wsl.sh`) figyelmeztetnie kell ha az env var nincs beállítva.

---

## 🟡 KÖZEPES PROBLÉMÁK

### K-3: JWT logout nem invalidálja a tokent

**Fájl:** `auth.py:289-297`

```python
@router.post("/logout")
async def logout(...):
    # Csak naplóz — a token érvényes marad 8 óráig
    log.info(f"Logout: {p.get('username')}")
    return {"status": "ok", "message": "Kijelentkezve"}
```

**Probléma:** A logout csak kliens oldalon törli a tokent. Ha egy JWT-t valaki megszerez (hálózati sniffing, vágólap, böngésző history), 8 óráig érvényes marad kijelentkezés után is.

**Kockázat:** Közepes — belső hálózati környezetben alacsonyabb, de elveszett eszköz esetén magasabb.

**Javítás lehetőségek:**
1. Token blacklist az `auth_tokens` táblában (egyszerűbb — lejárt tokenek törlésével karbantartható)
2. JWT érvényesség csökkentése 8h → 2h + frontend auto-megújítás
3. Redis-alapú token revoke (overkill a jelenlegi rendszerhez)

---

### K-4: OTP verify endpoint nincs brute-force védve

**Fájl:** `auth.py:242-286`

**Probléma:** A `POST /auth/verify` endpoint (OTP kód ellenőrzés) nincs sebességkorlátozva. 6 jegyű numerikus OTP → 900 000 lehetséges érték. Gyors automatizált próbálkozással (néhány perc alatt) feltörhető.

**Kockázat:** Közepes — az OTP 10 percig érvényes, ez az ablak szűk, de nem nulla.

**Javítás:**
```python
# auth_tokens táblában OTP próbálkozás számláló
otp_attempts = conn.execute(text(
    "SELECT otp_attempts FROM auth_tokens WHERE id=:id"
), {"id": tok[0]}).fetchone()[0]
if otp_attempts >= 3:
    raise HTTPException(429, "Túl sok próbálkozás — kérj új kódot")
conn.execute(text(
    "UPDATE auth_tokens SET otp_attempts = otp_attempts + 1 WHERE id=:id"
), {"id": tok[0]})
```

---

### K-5: CORS allow_origins=["*"]

**Fájl:** `main.py:74-78`

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

**Probléma:** Minden origin engedélyezett. Ha a géphez hozzáfér valaki a belső hálózaton, bármely weblapról AJAX kérést küldhet a CRT API-ra (CSRF-szerű támadás).

**Kockázat:** Alacsony-Közepes — belső hálózaton üzemel, de érdemes korlátozni.

**Javítás:**
```python
allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1:8000"]
```

---

### K-6: OTP dev módban logba kerül

**Fájl:** `auth.py:111`

```python
if not host:
    log.warning(f"[DEV] SMTP nincs beállítva – OTP kód a loggban: {code}")
    return True  # sikeresnek jelenti!
```

**Probléma:** Ha nincs SMTP beállítva, az OTP a `crt.log` / `logs/backend/backend.log` fájlba kerül. Ha a log fájl olvasható a felhasználók számára, a 2FA teljesen megkerülhető.

**Kockázat:** Közepes éles rendszeren (dev módban elfogadható).

**Javítás:**
- Éles rendszeren SMTP **kötelező** legyen — a startup validátor figyelmeztessen ha nincs beállítva
- A log fájlok csak root/admin számára legyenek olvashatók

---

### K-7: SMTP TLS tanúsítvány nem ellenőrzött

**Fájl:** `auth.py:128-131`

```python
with smtplib.SMTP(host, port, timeout=10) as srv:
    srv.ehlo()
    srv.starttls()   # nincs cert ellenőrzés!
    srv.login(user, pwd)
```

**Probléma:** A `starttls()` alapértelmezetten nem ellenőrzi a szerver tanúsítványát. Man-in-the-middle támadással az SMTP forgalom (beleértve OTP kódokat) lehallgatható.

**Kockázat:** Alacsony — belső hálózaton MitM nehezebb, de nem lehetetlen.

**Javítás:**
```python
import ssl
ctx = ssl.create_default_context()
with smtplib.SMTP(host, port, timeout=10) as srv:
    srv.ehlo()
    srv.starttls(context=ctx)
    srv.login(user, pwd)
```

---

## 🔵 ALACSONY PRIORITÁSÚ PROBLÉMÁK

### A-1: Soft delete hiánya az ajánlatoknál

**Fájl:** `quotes_router.py:212-215`

A `DELETE /quotes/{id}` hard DELETE-t végez. Véletlen törlés esetén nincs visszaállítási lehetőség (backup nélkül).

**Javítás:** `is_deleted` boolean mező + `deleted_at` timestamp + törlés helyett soft delete.

---

### A-2: auth.py saját adatbázis engine

**Fájl:** `auth.py:38`, `main.py:48`

Mindkét fájl saját SQLAlchemy engine-t hoz létre ugyanarra a DB-re. Ez redundáns connection pool-t eredményez.

**Javítás:** Közös `db.py` modul a motor és session kezeléshez (refactoring — nem biztonsági kockázat, de erőforrás pazarlás).

---

### A-3: UserUpdate email validáció

**Fájl:** `auth.py:341-352`

A `PATCH /auth/admin/users/{id}` endpoint `UserUpdate` modellje nem validálja az email formátumot Pydantic szinten (a sanitize middleware véd, de explicit validáció jobb lenne).

---

### A-4: reset_pin dict body helyett Pydantic model

**Fájl:** `auth.py:366`

```python
async def reset_pin(user_id: int, body: dict, ...):
    new_pin = body.get("pin", "")
```

Egyszerű `dict` helyett Pydantic `ResetPinRequest(pin: str)` modell biztonságosabb és dokumentáltabb.

---

## ✅ JÓL IMPLEMENTÁLT ELEMEK

| # | Elem | Fájl | Megjegyzés |
|---|------|------|------------|
| 1 | bcrypt PIN hash | `auth.py:192,328,374` | `gensalt()` használatával — helyes |
| 2 | Generic hibaüzenet | `auth.py:178` | User enumeration ellen védett |
| 3 | Brute force lockout | `auth.py:200-206` | 4 kísérlet → 30 perc → audit log |
| 4 | OTP kriptografikus | `auth.py:216` | `secrets.randbelow()` — nem `random` |
| 5 | OTP egyszer használható | `auth.py:269-271` | `used=true` jelölés |
| 6 | OTP lejárat | `auth.py:217,262` | 10 perc, DB-szintű ellenőrzés |
| 7 | OTP csere belépéskor | `auth.py:221-222` | Korábbi unused tokenek törlése |
| 8 | SQL injection | `auth.py` összes | SQLAlchemy parameterized queries |
| 9 | XSS védelem | `sanitize.py:33-35` | Regex + `html.escape()` |
| 10 | Path traversal | `sanitize.py:38` | `../` és `..\` blokkolva |
| 11 | Null byte | `sanitize.py:39` | Szűrve |
| 12 | JSON méretkorlát | `sanitize.py:251` | 512 KB limit |
| 13 | Config érzékeny kulcsok | `auth.py:402-403` | `smtp_pass`, `claude_api_key` csak boolean-ként |
| 14 | Audit log | `auth.py:273-275` | Belépés IP-vel, entitás típussal rögzítve |
| 15 | Admin role ellenőrzés | `auth.py:156-160` | Minden admin endpointon `Depends(require_admin)` |
| 16 | URL whitelist | `sanitize.py:46,105` | Csak `http`/`https` sémák engedélyezettek |

---

## JAVÍTÁSI ÜTEMTERV

### Éles telepítés előtt (kötelező)
1. **K-1:** DB URL → `.env` fájl, `CRT_DB_URL` env var
2. **K-2:** JWT secret → erős, véletlenszerű, `.env`-ből olvasva

### Következő sprint (ajánlott)
3. **K-3:** JWT logout token blacklist
4. **K-4:** OTP verify rate limiting (3 kísérlet)
5. **K-5:** CORS origin lista szűkítése
6. **K-6:** Startup figyelmeztetés ha SMTP nincs éles módban
7. **K-7:** SMTP TLS cert ellenőrzés

### Backlog
8. **A-1:** Soft delete quotes-hoz
9. **A-2:** Közös DB motor
10. **A-3:** Email Pydantic validáció

---

## BIZTONSÁGI KONTEXTUS

A CRT Ajánlatsegéd **belső hálózaton** üzemel, internet-hozzáférés nélkül. Ez számos vektort mérsékelt kockázatra csökkent (pl. CORS, MitM), de az éles rendszerre telepítés előtt a **K-1** és **K-2** javítása kötelező — a jelszavak és JWT secret lecserélése nem opcionális.

A rendszer **nem kezeli** üzleti szempontból különösen érzékeny adatokat (sem személyes adatot GDPR értelemben, sem pénzügyi tranzakciót) — az ajánlatok és cikktörzs üzleti adatok, de nem minősített információ. A biztonsági követelmények ehhez mértek.

---

*CRT Ajánlatsegéd Biztonsági Audit v1.0 · Civil Rendszertechnika Kft. · 2026-06-10*
*Belső dokumentum — nem nyilvános*
