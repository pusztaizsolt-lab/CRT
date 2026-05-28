# CRT Ajánlatsegéd – Új gép beállítása

## 1. lépés – Python 3.11 telepítése (ha nincs)
Letöltés: https://www.python.org/downloads/release/python-3119/
- Windows Installer (64-bit)
- **Fontos:** pipáld be az „Add Python to PATH" opciót!

## 2. lépés – Beállító script futtatása
Nyiss egy PowerShell ablakot és futtasd:
```
powershell -ExecutionPolicy Bypass -File "H:\Saját meghajtó\CRT\_setup\setup_new_machine.ps1"
```
Ez automatikusan elvégzi:
- pip csomagok telepítése
- PostgreSQL adatbázis inicializálása
- crt adatbázis + felhasználó létrehozása
- Tábla séma + migráció

## 3. lépés – Indítás
```
H:\Saját meghajtó\CRT\start.bat
```
Vagy dupla kattintás a `CRT.hta` fájlra.

## 4. lépés – Ellenőrzés
Böngészőben: http://localhost:8000/docs
Ha megjelenik az API dokumentáció → minden rendben!

---

## Claude Code telepítése (fejlesztéshez)
https://claude.ai/code – letöltés és telepítés
Első indítás után nyisd meg a projektet:
```
claude "H:\Saját meghajtó\CRT"
```
A CLAUDE.md fájl alapján azonnal tudni fogja mi ez a projekt.

---

## Fontos tudnivaló – db_data
A `db_data` mappa PostgreSQL adatokat tartalmaz.
**Google Drive szinkronból ki kell zárni** (Drive beállítások → Kizárt mappák).
Minden gépen külön, lokális adatbázis fut.
