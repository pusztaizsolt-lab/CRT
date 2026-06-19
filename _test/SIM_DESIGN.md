# CRT Self-Test Szimulátor — Tervezési Dokumentum

**Szerző:** Civil Rendszertechnika Kft.
**Dátum:** 2026-06-17
**Státusz:** Tervezés kész — implementálásra vár

---

## Az alapgondolat

Minden üzleti rendszernek kellene egy `--self-test` módjának.
Nem külső tesztelő, nem QA kolléga — **a rendszer önmaga teszteli magát**,
szintetikus adatokkal, silent módban, emberi beavatkozás nélkül.

Az AI korszakban ez különösen triviális, mert:

- **Az adatgenerálás már megvan** — ugyanaz az AI motor, ami valós ajánlatot
  azonosít, valószerű teszt bemenetet is tud generálni.
  Nem `"teszt_termék_001"`, hanem:
  `"Schneider Electric A9F74316 16A 3P C karakterisztikájú kismegszakító"`

- **Az értékelés is AI-alapú lehet** — nem `assert response == "exact_string"`,
  hanem fuzzy validáció: *"ez az azonosítás üzletileg elfogadható?"*

- **A specifikáció géppel olvasható** — a whitepaper, a DB séma, a routerek
  mind levezethetővé teszik, mit kell tesztelni.

---

## Futtatási módok

```bash
py -3.11 _test/sim.py                # teljes teszt, cleanup, részletes output
py -3.11 _test/sim.py --mode smoke   # csak service alive + auth
py -3.11 _test/sim.py --mode api     # auth + CRUD + export, AI nélkül
py -3.11 _test/sim.py --mode ai      # csak AI / ChromaDB réteg
py -3.11 _test/sim.py --mode export  # csak export réteg (xlsx/docx/pdf)
py -3.11 _test/sim.py --silent       # csak exit code, output nélkül (CI/CD)
py -3.11 _test/sim.py --no-cleanup   # megtartja a teszt adatokat vizsgálathoz
py -3.11 _test/sim.py --otp XXXXXX   # manuális OTP megadás (ha log nem elérhető)
```

**Exit kódok:**
- `0` — minden OK
- `1` — legalább egy hiba
- `2` — service nem elérhető (smoke failed)

---

## A teljes tesztfolyam

```
[01] Smoke        → PostgreSQL, FastAPI /health, ChromaDB heartbeat
[02] Auth login   → POST /auth/login (admin + PIN)
[03] OTP auto     → OTP kód automatikus kiolvasás backend.log-ból
[04] Auth verify  → POST /auth/verify → JWT token megszerzés
[05] Cikktörzs    → POST /products (szintetikus termék)
                    GET  /products (lista + szűrés)
                    GET  /products/{id}
[06] Árak         → POST /prices (szintetikus ár)
                    GET  /prices?item_id=...
[07] Ajánlat      → POST /quotes (fejléc)
                    POST /quotes/{id}/lines (sor hozzáadás)
                    PUT  /quotes/{id}/status
[08] AI azonosít  → POST /ai/identify (szintetikus leírás)
                    validáció: confidence > 0.5
[09] ChromaDB     → POST /golden (példa feltöltés)
                    POST /ai/search (vektoros keresés)
                    validáció: legalább 1 találat
[10] Export xlsx  → POST /export/{quote_id}/xlsx
                    validáció: fájl méret > 1KB
[11] Export docx  → POST /export/{quote_id}/docx
                    validáció: fájl méret > 1KB
[12] Export pdf   → POST /export/{quote_id}/pdf
                    validáció: fájl méret > 1KB
[13] Web forrás   → POST /web/sources (URL + encrypt)
                    GET  /web/sources (decrypt ellenőrzés)
[14] Audit log    → GET /admin/audit (előző műveletek nyoma)
                    validáció: legalább 10 bejegyzés az ülésből
[15] Cleanup      → DELETE minden teszt rekord (prefix: SIM_TEST_)
```

---

## Szintetikus adatok

A szimulátor saját teszt adatokat használ — minden rekord `SIM_TEST_` prefixű,
így cleanup után semmi nem marad a rendszerben.

```python
TEST_PRODUCT = {
    "name":        "SIM_TEST Schneider A9F74316",
    "crt_code":    "SIM-001",
    "unit":        "db",
    "description": "16A 3P C karakterisztikájú kismegszakító — TESZT REKORD"
}

TEST_QUOTE = {
    "client_name": "SIM_TEST Kft.",
    "client_ref":  "SIM-2026-001",
    "notes":       "Automatikus szimulátorteszt — törölhető"
}

TEST_AI_INPUT = "Schneider Electric kismegszakító 16 amperes háromfázisú"

TEST_WEB_SOURCE = {
    "name":     "SIM_TEST Forrás",
    "base_url": "https://example.com/sim-test"
}
```

---

## OTP automatikus kiolvasás

SMTP hiányában a kód a backend.log-ban jelenik meg. A szimulátor ezt olvassa:

```python
def auto_otp(log_path: str, max_age_sec: int = 60) -> str | None:
    """Legutóbbi OTP kód kiolvasása a logból, ha max_age_sec-nél frissebb."""
    import re, time
    from datetime import datetime
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*OTP kód a loggban: (\d{6})")
    for line in reversed(open(log_path, encoding="utf-8").readlines()):
        m = pattern.search(line)
        if m:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            age = time.time() - ts.timestamp()
            if age <= max_age_sec:
                return m.group(2)
    return None
```

---

## Várható kimenet

```
══════════════════════════════════════════════════════
  CRT Rendszer Szimulátor v1.0
  2026-06-17 22:30:00  |  platform: windows  |  full
══════════════════════════════════════════════════════

  [01] Smoke: PostgreSQL        ✓   12ms
  [01] Smoke: FastAPI /health   ✓   45ms
  [01] Smoke: ChromaDB          ✓   89ms
  [02] Auth login               ✓  234ms
  [03] OTP kiolvasás (logból)   ✓   kód: 123456
  [04] Auth verify / JWT        ✓  312ms
  [05] Cikktörzs CREATE         ✓   87ms
  [05] Cikktörzs READ           ✓   34ms
  [06] Ár rögzítés              ✓   56ms
  [07] Ajánlat CREATE           ✓  123ms
  [07] Ajánlat sor              ✓   78ms
  [08] AI azonosítás            ⚠  2341ms  conf=0.41 (küszöb alatt)
  [09] ChromaDB vektoros        ✓  567ms   1 találat
  [10] Export xlsx              ✓ 1240ms   28KB
  [11] Export docx              ✓  890ms   19KB
  [12] Export pdf               ✗   hiba: reportlab ImportError
  [13] Web forrás encrypt       ✓   45ms
  [14] Audit log ellenőrzés     ✓   23ms   14 bejegyzés
  [15] Cleanup                  ✓   67ms   9 rekord törölve

══════════════════════════════════════════════════════
  Eredmény: 17/19 OK | 1 figyelmeztetés | 1 hiba
  Futási idő: 6.2 másodperc
══════════════════════════════════════════════════════

  ⚠  AI konfidencia alacsony (0.41) — golden example-ök hiánya
  ✗  Export PDF — pip install reportlab szükséges
```

---

## Miért nincs ez mindenhol

A hagyományos fejlesztési kultúrában a teszt **utólag** készül, nem az
architektúra részeként. A rendszert megcsinálják, majd valaki megírja a
tesztet — ha egyáltalán.

Az AI korszak ezt felforgatja:
- A teszt és a rendszer **egyszerre tervezhető**
- Az AI a specifikációból mindkettőt le tudja vezetni
- A szimulátor nem külön projekt — **a rendszer önismerete**

A CRT esetében: a sim.py futtatható telepítés után, minden módosítás után,
production deploymentváltás előtt. 2 perc alatt látszik minden hiba —
kézi klikkelés nélkül.

---

## Implementációs terv

1. `_test/sim.py` — fő szimulátor script (~400 sor)
2. `_test/sim_data.py` — szintetikus adatok, konstansok
3. `_test/sim_report.py` — kimenet formázás, riport generálás

**Függőségek** (már telepítve a venv-ben):
- `requests` — HTTP hívások
- `colorama` — színes terminál output (opcionális)

**Nincs szükség:**
- Seleniumra / Playwrightra (API szintű teszt)
- Külső teszt frameworkre (pytest nem kell)
- Mock-ra (valódi DB, valódi backend)
