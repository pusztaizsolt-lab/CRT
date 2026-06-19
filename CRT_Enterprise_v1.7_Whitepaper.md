# CRT Ajánlatsegéd — Enterprise Architektúra Whitepaper v1.7
**Civil Rendszertechnika Kft. | Bizalmas belső dokumentum**
*Kiadás: 2026-06-19 | Szerző: Pusztai Zsolt + Claude Sonnet 4.6*

---

## 1. Összefoglalás

A CRT Ajánlatsegéd jelenlegi v1.1 verziója egy **single-tenant, Windows-natív, monolit** rendszer — szándékosan egyszerű, tesztelhetőbb és üzemeltethető egy gép egy cég számára. Ez a whitepaper az **enterprise irányú bővítés módszertanát** rögzíti: hogyan lehet a meglévő kódot érintetlenül hagyva plugin-szerűen kibővíteni, és mikor/hogyan érdemes dinamikusan méretezni.

**Alapelv: a meglévő v1.1 kód nem törik meg — minden enterprise funkció ráépül, nem belé.**

---

## 2. Jelenlegi architektúra (v1.1 baseline)

```
┌─────────────────────────────────────────────┐
│  Browser (Vanilla HTML/JS, 13 oldal)        │
└──────────────────┬──────────────────────────┘
                   │ HTTP/REST
┌──────────────────▼──────────────────────────┐
│  FastAPI (main.py + routerek)               │
│  auth · cikktorzs · arak · ajanlat          │
│  web · golden · lora · export · vision      │
└──────┬───────────┬──────────────────────────┘
       │           │
┌──────▼──┐  ┌─────▼──────┐
│PostgreSQL│  │ChromaDB    │
│port 5433 │  │port 8001   │
└──────────┘  └─────┬──────┘
                    │
              ┌─────▼──────┐
              │Ollama LLM  │
              │llama3:8b   │
              └────────────┘
```

**Erősségek:** egyszerű, tesztelt (45/45), git-verziókezelt, SMTP kész, AI lánc működik
**Korlátok:** egy bérlő, szinkron AI hívások, nincs háttér-ütemező, vanilla JS

---

## 3. Enterprise Plugin Architektúra

### 3.1 Alapelv: Middleware-first bővítés

Minden enterprise funkció **middleware rétegként** épül a meglévő routerek elé — a routerek kódja nem változik.

```python
# main.py jelenlegi struktúra (nem változik):
app.include_router(prices_router)
app.include_router(quotes_router)

# Enterprise réteg hozzáadva (ráépül):
app.add_middleware(TenantMiddleware)      # multi-tenant
app.add_middleware(RateLimitMiddleware)  # API throttling
app.add_middleware(AuditMiddleware)      # bővített audit
app.include_router(tenants_router)       # új router, régi nem változik
app.include_router(billing_router)       # új router
```

### 3.2 Plugin regisztrációs minta

```python
# plugins/__init__.py
ENABLED_PLUGINS = [
    "plugins.multi_tenant",   # feature flag
    "plugins.billing",
    "plugins.sso",
    "plugins.webhooks",
]

def load_plugins(app: FastAPI):
    for plugin_path in ENABLED_PLUGINS:
        module = importlib.import_module(plugin_path)
        module.register(app)  # minden plugin register() függvényt implementál
```

```python
# plugins/multi_tenant.py — példa plugin
def register(app: FastAPI):
    app.add_middleware(TenantMiddleware)
    app.include_router(tenants_router, prefix="/tenants")
```

**Feature flag:** egy plugin kikapcsolásához csak töröld a listából — a többi változatlan.

---

## 4. Multi-Tenant Plugin — Részletes Terv

### 4.1 Adatmodell kiterjesztés

```sql
-- Új tábla — a meglévők mellé, nem helyett
CREATE TABLE companies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(50)  UNIQUE NOT NULL,  -- url-ben: crt.local/acme/
    plan        VARCHAR(20)  DEFAULT 'starter', -- starter|pro|enterprise
    active      BOOLEAN      DEFAULT true,
    created_at  TIMESTAMP    DEFAULT NOW()
);

-- Meglévő táblák kiterjesztése migrációval (nem újraírás):
ALTER TABLE products    ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE quotes      ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE prices      ADD COLUMN company_id UUID REFERENCES companies(id);
ALTER TABLE users       ADD COLUMN company_id UUID REFERENCES companies(id);

-- Row-level security (PostgreSQL natív)
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON products
    USING (company_id = current_setting('app.tenant_id')::UUID);
```

### 4.2 Tenant Middleware

```python
# plugins/multi_tenant.py
class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Tenant azonosítás: subdomain VAGY JWT claim VAGY header
        tenant_id = (
            self._from_subdomain(request) or
            self._from_jwt(request) or
            self._from_header(request)
        )
        if not tenant_id:
            return JSONResponse({"detail": "Tenant nem azonosítható"}, 401)

        # PostgreSQL session-szintű beállítás → RLS automatikusan szűr
        request.state.tenant_id = tenant_id
        with engine.connect() as conn:
            conn.execute(text(f"SET app.tenant_id = '{tenant_id}'"))

        return await call_next(request)
```

### 4.3 Meglévő routerek — változatlanok

A routerek `tenant_id`-t **nem látják**, a PostgreSQL RLS csinálja a szűrést. Ez a kulcsa annak hogy a v1.1 kód változatlan marad.

---

## 5. Háttér Feladatok Plugin (Celery/ARQ)

### 5.1 Miért kell

Jelenlegi problémák:
- AI azonosítás: 17-31s → blokkolja a kéréseket
- Webes scraping: Playwright blokkoló
- LoRA tanítás: percek-órák, nem szinkron

### 5.2 ARQ (könnyűsúlyú, Redis alapú)

```python
# plugins/background_jobs.py
import arq

async def ai_identify_task(ctx, items: list, quote_id: int):
    """Háttérben fut, eredményt DB-be írja"""
    result = await ai_motor.identify_async(items)
    # WebSocket-en értesíti a frontendet
    await notify_client(quote_id, result)

class WorkerSettings:
    functions = [ai_identify_task, scrape_source_task, lora_train_task]
    redis_settings = arq.connections.RedisSettings(host='localhost', port=6379)

# Indítás: arq plugins.background_jobs.WorkerSettings
```

```python
# main.py — minimális változás
@app.post("/cikktorzs/identify")
async def identify(body: dict, _auth=Depends(require_auth)):
    if BACKGROUND_JOBS_ENABLED:
        job = await arq_pool.enqueue_job('ai_identify_task', body["items"])
        return {"job_id": job.job_id, "status": "queued"}
    else:
        # Régi szinkron út — v1.1 kompatibilis
        result = await loop.run_in_executor(None, ai_motor.identify, ...)
        return result
```

### 5.3 Szükséges infrastruktúra

```
Redis 7.x (Windows: Redis for Windows vagy WSL)
→ pip install arq redis
→ arq plugins.background_jobs.WorkerSettings (külön folyamat)
```

---

## 6. OAuth / SSO Plugin

### 6.1 Jelenlegi auth (v1.1) — változatlan

```
PIN (6 jegy bcrypt) → email OTP → JWT (8h)
```

### 6.2 OAuth réteg mellé (nem helyett)

```python
# plugins/sso.py
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register("microsoft", ...)  # Azure AD
oauth.register("google", ...)

@router.get("/auth/sso/microsoft")
async def sso_microsoft(request: Request):
    redirect_uri = request.url_for("sso_callback_microsoft")
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)

@router.get("/auth/sso/microsoft/callback")
async def sso_callback_microsoft(request: Request):
    token = await oauth.microsoft.authorize_access_token(request)
    # → ugyanolyan JWT-t állít elő mint a PIN/OTP flow
    # → a meglévő require_auth() decorator nem változik
```

A meglévő `require_auth()` JWT-t vár — mind a két flow (PIN+OTP és SSO) **ugyanolyan JWT-t** állít elő. A routerek nem tudják melyik útvonalon jött.

---

## 7. Dinamikus Méretezés

### 7.1 Vertikális (egy gép, több erőforrás)

```bash
# Jelenlegi: 1 uvicorn worker
uvicorn main:app --workers 1

# Bővítés: több worker (CPU mag szerint)
uvicorn main:app --workers 4
# vagy Gunicorn előtt:
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

**Mikor elég:** ~50 párhuzamos felhasználóig egy erős gépen

### 7.2 Horizontális (több gép)

```
                    ┌─────────────┐
                    │  Nginx/     │
Browser ──────────► │  Traefik    │ ◄── health check
                    │  (LB)       │
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────▼┐ ┌▼─┐ ┌▼────────┐
              │CRT App 1│ │..│ │CRT App N│  (Docker containers)
              └────────┬┘ └──┘ └┬────────┘
                       │        │
              ┌────────▼────────▼────────┐
              │   PostgreSQL (shared)    │
              │   + Redis (shared)       │
              └──────────────────────────┘
```

### 7.3 Docker Compose — enterprise verzió

```yaml
# docker-compose.enterprise.yml
version: '3.9'
services:
  app:
    build: .
    deploy:
      replicas: 3          # skálázható
    environment:
      - DATABASE_URL=postgresql://crt_user:${DB_PASS}@db:5432/crt
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]

  worker:
    build: .
    command: arq plugins.background_jobs.WorkerSettings
    deploy:
      replicas: 2

  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
```

### 7.4 Managed Cloud (ha szükséges)

| Komponens | Helyi | Cloud megfelelő |
|-----------|-------|----------------|
| PostgreSQL | lokális | Supabase / AWS RDS |
| Redis | lokális | Redis Cloud / ElastiCache |
| App | uvicorn | Railway / Fly.io / ECS |
| ChromaDB | lokális | Pinecone / Weaviate |
| Ollama | lokális | GPU instance (marad) |

---

## 8. Fejlesztési Metodológia

### 8.1 Verzióstratégia

```
v1.x  — Single-tenant Windows natív (JELENLEGI)
v2.x  — Plugin réteg + háttér feladatok (ARQ)
v3.x  — Multi-tenant + SSO
v4.x  — Horizontális skálázás + managed cloud opció
```

**Alapszabály:** minden verzió visszafelé kompatibilis az előzővel. v2.x rendszeren v1.x kliens működik.

### 8.2 Feature Flag mintázat

```python
# config.py
FEATURES = {
    "multi_tenant":    os.getenv("FEATURE_MULTI_TENANT",    "false") == "true",
    "background_jobs": os.getenv("FEATURE_BACKGROUND_JOBS", "false") == "true",
    "sso":             os.getenv("FEATURE_SSO",             "false") == "true",
    "billing":         os.getenv("FEATURE_BILLING",         "false") == "true",
}
```

Minden enterprise funkció **kikapcsolt alapértelmezetten** — a v1.1 viselkedés az alap.

### 8.3 Tesztelési stratégia

```
Szimulátor (_test/sim.py):
  Smoke     → mindig fut (S1-S4)
  API       → minden commit után (A1-AU1)
  Plugin    → csak ha plugin aktív (P_TENANT1-P_TENANT5)
  Load      → hetente (locust vagy k6)
  E2E       → kiadás előtt (Playwright)
```

### 8.4 Migrációs protocol

1. Új tábla/oszlop: `db_migrate_vXX.py` — mindig additive (nincs DROP, nincs RENAME)
2. Rollback: minden migrációhoz `_down()` függvény
3. Zero-downtime: `ALTER TABLE ... ADD COLUMN` PostgreSQL-ben nem zár táblát

---

## 9. TODO — Enterprise Roadmap

### Fázis 1 — Alap plugin rendszer (1-2 hét)
- [ ] `plugins/` mappa + `load_plugins()` regisztrátor
- [ ] Feature flag rendszer (`.env` alapú)
- [ ] Plugin-specifikus tesztek a sim.py-ba
- [ ] `docker-compose.enterprise.yml` alapverzió

### Fázis 2 — Háttér feladatok (1-2 hét)
- [ ] Redis telepítés (WSL vagy Windows)
- [ ] ARQ worker: `ai_identify_task`, `scrape_task`
- [ ] WebSocket endpoint (`/ws/jobs/{job_id}`) — progress értesítés
- [ ] Frontend: polling helyett WebSocket státusz kijelzés

### Fázis 3 — Multi-tenant (3-4 hét)
- [ ] `companies` tábla + migráció
- [ ] `company_id` oszlop meglévő táblákba
- [ ] PostgreSQL Row-Level Security bekapcsolás
- [ ] `TenantMiddleware` implementáció
- [ ] Tenant admin felület (új HTML oldal)
- [ ] Tesztek: bérlők adatizoláció ellenőrzése

### Fázis 4 — SSO (2-3 hét)
- [ ] `authlib` + `httpx-oauth` függőségek
- [ ] Microsoft Azure AD integráció (cégeknek)
- [ ] Google Workspace integráció (opcionális)
- [ ] SSO callback → JWT flow (meglévő auth vége)
- [ ] Beállítások oldal: SSO konfiguráció UI

### Fázis 5 — Skálázás (1-2 hét)
- [ ] Gunicorn multi-worker konfig
- [ ] Nginx reverse proxy + SSL (Let's Encrypt)
- [ ] Health check endpoint bővítés (worker count, queue depth)
- [ ] Monitoring: Prometheus metrics endpoint
- [ ] Alerting: Grafana dashboard alap

### Fázis 6 — Hordozható telepítő (2-3 hét)
- [ ] `install.ps1` wizard (PostgreSQL + Python + DB init + admin)
- [ ] Docker image build + publish
- [ ] `.exe` wrapper (PyInstaller, offline telepítőhöz)
- [ ] Frissítő script (`update.ps1` — git pull + migráció + restart)

---

## 10. Know-How — Kulcsdöntések és Indoklásuk

| Döntés | Miért |
|--------|-------|
| FastAPI router mint plugin egység | Önálló fájl, önálló prefix, mountolható/demountolható |
| PostgreSQL RLS tenant izolációhoz | Nem az app kód véd, az adatbázis — biztonságosabb |
| ARQ vs Celery | ARQ egyszerűbb, pure Python, Redis-en fut, FastAPI-val natív |
| Middleware-first | Meglévő routerek kódja soha nem változik enterprise funkcióért |
| Feature flag `.env`-ben | Futás közben is kapcsolható, nem kell újraépíteni |
| Additive migrációk | Soha nincs rollback kockázat production-ben |
| JWT mindkét auth flowban | SSO és PIN+OTP ugyanolyan tokent ad — a többi kód nem tud különbséget |

---

## 11. Erőforrásigény (becsült)

| Fázis | Fejlesztési idő | Infrastruktúra többlet |
|-------|----------------|----------------------|
| Plugin rendszer | 1-2 hét | semmi |
| Háttér feladatok | 1-2 hét | Redis (~50MB RAM) |
| Multi-tenant | 3-4 hét | semmi (csak DB séma) |
| SSO | 2-3 hét | semmi |
| Horizontális skálázás | 1-2 hét | második gép vagy VM |
| **Összesen** | **~3 hónap** | **minimális** |

---

## 12. Amit NEM kell megváltoztatni

- `main.py` routing logika
- `auth.py` JWT kezelés
- Összes meglévő router (`prices_router.py`, `quotes_router.py`, stb.)
- Frontend HTML oldalak (új oldalak jönnek mellé)
- PostgreSQL séma meglévő táblái (csak bővülnek)
- `_test/sim.py` meglévő tesztjei (új tesztek jönnek mellé)

**A v1.1 rendszer az enterprise verzió alapja — nem a helyettesítendő örökség.**

---

*CRT Enterprise Whitepaper v1.7 | Civil Rendszertechnika Kft. | 2026-06-19*
*Következő felülvizsgálat: v2.0 release előtt*
