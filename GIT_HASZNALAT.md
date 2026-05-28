# CRT – Git & GitHub gyorslap

## Repó helye
https://github.com/pusztaizsolt-lab/CRT

---

## Napi munka (ezen a gépen)

### Változások feltöltése GitHub-ra
```
cd "H:\Saját meghajtó\CRT"
git add .
git commit -m "mit csináltam"
git push
```

### Letöltés ha másik gépen is dolgoztál
```
cd "H:\Saját meghajtó\CRT"
git pull
```

### Mi változott utoljára?
```
git log --oneline -10
```

---

## Másik gép – első alkalommal

### 1. Git telepítése (ha nincs)
https://git-scm.com/download/win → 64-bit installer → Next Next Install

### 2. Repó letöltése
```
git clone https://github.com/pusztaizsolt-lab/CRT.git "H:\Saját meghajtó\CRT"
```

### 3. Gép beállítása
```
powershell -ExecutionPolicy Bypass -File "H:\Saját meghajtó\CRT\_setup\setup_new_machine.ps1"
```

### 4. Indítás
```
H:\Saját meghajtó\CRT\start.bat
```

---

## Hasznos parancsok

| Mit akarok | Parancs |
|---|---|
| Feltöltés | `git add . && git commit -m "leírás" && git push` |
| Letöltés | `git pull` |
| Mi változott? | `git status` |
| Előzmények | `git log --oneline -10` |
| Visszavonás (még nem commit) | `git checkout -- .` |

---

## Fontos tudnivalók

- A `db_data\` mappa **nem kerül fel** GitHub-ra (`.gitignore` kizárja)
- A `db\pgsql\` (PostgreSQL bináris) szintén **nem kerül fel** – minden gépen lokális
- Minden egyéb fájl (Python, HTML, MD) **szinkronizálódik**
- Ha conflict van (két gép egyszerre módosított valamit) → szólj, megoldom

---

## GitHub bejelentkezés
Felhasználó: **pusztaizsolt-lab**
Repó: **https://github.com/pusztaizsolt-lab/CRT**
