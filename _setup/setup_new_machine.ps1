# CRT Ajanlatseged - Uj gep beallitas
# Futtatas: powershell -ExecutionPolicy Bypass -File _setup\setup_new_machine.ps1
#
# Ez a script elvegzi:
#   1. Python 3.11 ellenorzese
#   2. Pip csomagok telepitese
#   3. PostgreSQL adatbazis inicializalasa
#   4. Adatbazis + felhasznalo letrehozasa
#   5. Tabla sema letrehozasa
#   6. Migracio futtatasa (v0.2)

$root = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "  =============================================="
Write-Host "  CRT Ajanlatseged - Uj gep beallitas"
Write-Host "  Projekt: $root"
Write-Host "  =============================================="
Write-Host ""

$ok = $true

# ── 1. PYTHON 3.11 ────────────────────────────────────────────
Write-Host "  [1/6] Python 3.11 ellenorzese..."
$py = $null
foreach ($cmd in @("py -3.11", "python3.11", "python")) {
    try {
        $ver = & cmd /c "$cmd --version 2>&1"
        if ($ver -match "3\.11") { $py = $cmd; break }
    } catch {}
}

if ($py) {
    Write-Host "  OK  Python: $py" -ForegroundColor Green
} else {
    Write-Host "  HIBA: Python 3.11 nem talalhato!" -ForegroundColor Red
    Write-Host "  Telepites: https://www.python.org/downloads/release/python-3119/" -ForegroundColor Yellow
    Write-Host "  Fontos: telepites soran pipald be az 'Add to PATH' opciott!" -ForegroundColor Yellow
    $ok = $false
}

# ── 2. PIP CSOMAGOK ───────────────────────────────────────────
if ($py) {
    Write-Host ""
    Write-Host "  [2/6] Pip csomagok telepitese..."
    $packages = "fastapi uvicorn sqlalchemy psycopg2-binary ntplib openpyxl pdfplumber python-docx beautifulsoup4 anthropic"
    $result = & cmd /c "$py -m pip install $packages --quiet 2>&1"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK  Csomagok telepitve" -ForegroundColor Green
    } else {
        Write-Host "  FIGYELEM: Egyes csomagok telepitese sikertelen" -ForegroundColor Yellow
        Write-Host $result
    }
}

# ── 3. POSTGRESQL INIT ────────────────────────────────────────
Write-Host ""
Write-Host "  [3/6] PostgreSQL adatbazis ellenorzese..."

$pgCtl    = "$root\db\pgsql\bin\pg_ctl.exe"
$psql     = "$root\db\pgsql\bin\psql.exe"
$initdb   = "$root\db\pgsql\bin\initdb.exe"
$dbData   = "$root\db_data"
$pgLog    = "$root\pg.log"

if (-not (Test-Path $pgCtl)) {
    Write-Host "  HIBA: PostgreSQL binarisok nem talalhatok: $root\db\pgsql\" -ForegroundColor Red
    Write-Host "  Ellenorizd hogy a Google Drive szinkronizalt!" -ForegroundColor Yellow
    $ok = $false
} else {
    Write-Host "  OK  PostgreSQL binarisok megvannak" -ForegroundColor Green

    # Letezik-e mar az adatbazis?
    if (Test-Path "$dbData\PG_VERSION") {
        Write-Host "  OK  db_data mar inicializalva van" -ForegroundColor Green
    } else {
        Write-Host "  db_data nem talalhato - inicializalas..."
        New-Item -ItemType Directory -Force -Path $dbData | Out-Null
        $env:PGPASSWORD = ""
        & $initdb -D $dbData -U postgres --encoding=UTF8 --locale=C 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK  PostgreSQL inicializalva" -ForegroundColor Green
        } else {
            Write-Host "  HIBA: PostgreSQL initdb sikertelen!" -ForegroundColor Red
            $ok = $false
        }
    }
}

# ── 4. POSTGRESQL INDITASA + DB LETREHOZASA ───────────────────
if ($ok -and (Test-Path $pgCtl)) {
    Write-Host ""
    Write-Host "  [4/6] PostgreSQL inditas + adatbazis letrehozas..."

    # Fut-e mar?
    $status = & $pgCtl status -D $dbData 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $pgCtl start -D $dbData -l $pgLog -w 2>$null | Out-Null
        Start-Sleep -Seconds 4
    }
    Write-Host "  OK  PostgreSQL fut" -ForegroundColor Green

    # crt_user es crt adatbazis
    $env:PGPASSWORD = ""
    $checkUser = & $psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='crt_user'" 2>$null
    if ($checkUser -ne "1") {
        & $psql -U postgres -c "CREATE USER crt_user WITH PASSWORD 'crt2026';" 2>$null | Out-Null
        Write-Host "  OK  crt_user letrehozva" -ForegroundColor Green
    } else {
        Write-Host "  OK  crt_user mar letezik" -ForegroundColor Green
    }

    $checkDb = & $psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='crt'" 2>$null
    if ($checkDb -ne "1") {
        & $psql -U postgres -c "CREATE DATABASE crt OWNER crt_user ENCODING 'UTF8';" 2>$null | Out-Null
        & $psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE crt TO crt_user;" 2>$null | Out-Null
        Write-Host "  OK  crt adatbazis letrehozva" -ForegroundColor Green
    } else {
        Write-Host "  OK  crt adatbazis mar letezik" -ForegroundColor Green
    }
}

# ── 5. TABLA SEMA ─────────────────────────────────────────────
if ($ok -and $py) {
    Write-Host ""
    Write-Host "  [5/6] Tabla sema letrehozasa..."
    Set-Location $root
    $result = & cmd /c "$py db_schema.py 2>&1"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK  Tablak letrehozva" -ForegroundColor Green
    } else {
        Write-Host "  FIGYELEM: Sema letrehozas problema" -ForegroundColor Yellow
        Write-Host $result
    }
}

# ── 6. MIGRACIO ───────────────────────────────────────────────
if ($ok -and $py) {
    Write-Host ""
    Write-Host "  [6/6] Adatbazis migracio v0.2..."
    Set-Location $root
    $result = & cmd /c "$py db_migrate_v02.py 2>&1"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK  Migracio kesz" -ForegroundColor Green
    } else {
        Write-Host "  FIGYELEM: Migracio problema" -ForegroundColor Yellow
        Write-Host $result
    }
}

# ── EREDMENY ──────────────────────────────────────────────────
Write-Host ""
if ($ok) {
    Write-Host "  =============================================="
    Write-Host "  BEALLITAS KESZ!" -ForegroundColor Cyan
    Write-Host "  Inditas: $root\start.bat" -ForegroundColor Cyan
    Write-Host "  API docs: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "  =============================================="
} else {
    Write-Host "  Egyes lepesek sikertelenek - ellenorizd fent!" -ForegroundColor Yellow
    Write-Host "  Segitseg: CLAUDE.md es CRT_Status.md fajlokban" -ForegroundColor Yellow
}
Write-Host ""
