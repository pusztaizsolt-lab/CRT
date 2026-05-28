# CRT – Session napló

---

## 2026-05-27 – 1. munkanap

### Elvégzett munka
- Beolvastuk a Whitepaper Felhasználói v1.3 + Mérnöki v1.3 dokumentumokat
- Elkészült `ui/kezelőpult.html` (v1) – fejlesztői dashboard
  - Zöld/sárga/piros/lila kártyák státusz szerint
  - Védett beállítások szekció (lila)
  - AI jóváhagyó popup (F2 tesztelhető)
  - Haladásjelző sáv
- Elkészült `CRT_Status.md` – projekt státusz fa verziószámokkal
- Elkészült `claude/01_architektura_dontesek.md` – döntések + kontextus

### Kulcsdöntések
1. Eredeti dokumentum SOHA nem módosul – másolaton dolgozunk
2. Centrális AI mag – egyszer építjük, minden modul használja
3. Fuzzy komparátor 4 réteg – auto → LLaMA → API (kézi jóváhagyás) → kézi
4. Külső API hívás előtt jóváhagyó popup (token + cost + keret%)
5. Verzióz ás: html fájloknál másolat nagyobb változásnál

### Következő session – Első éles beta
```
v0.3  PIN Auth + JWT
        • bcrypt hash · 6 jegyű PIN
        • JWT token kiadás
        • Brute force védelem (4 kísérlet → 30 perc lockout)
        • /auth/login · /auth/logout · /auth/me endpoint

v0.4  Centrális AI mag (párhuzamosan indítható)
        • OCR / parser alap
        • ChromaDB inicializálás
        • LLaMA kapcsolat
```

### Fájlok
```
C:\CRT\CRT.hta                   ← BELÉPŐPONT – dupla klikk, elindít mindent
C:\CRT\start.bat                 ← alternatív indító (CMD ablakos)
C:\CRT\ui\kezelőpult.html        ← legfrissebb dashboard (F2 = AI popup teszt)
C:\CRT\ui\kezelőpult_v1.html     ← 2026-05-27 snapshot
C:\CRT\CRT_Status.md             ← projekt státusz fa
C:\CRT\CRT_Tech_Stack.md         ← tech stack referencia
C:\CRT\claude\01_architektura_dontesek.md  ← döntések [CTX: crt-arch-v2]
```

### Indítási sorrend
```
CRT.hta  →  PostgreSQL (ellenőriz / indít)
         →  Backend (py -3.11 uvicorn, háttérben)
         →  Vár ~5mp
         →  Megnyitja ui\kezelőpult.html böngészőben
         →  Splash ablak bezárul
```

---

`[CTX: crt-session-1 | 2026-05-27 | kesz | kovetkezo: v0.3-pin-auth]`
