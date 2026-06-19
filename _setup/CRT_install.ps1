# ===============================================================
# CRT Ajanlatseged - Intelligens telepito v1.1
# Futtatás: install.bat (rendszergazdakent)
# ===============================================================
param(
    [string]$InstallDir = (Split-Path $PSScriptRoot -Parent)
)

$Host.UI.RawUI.WindowTitle = "CRT Telepito"
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "logs\install") | Out-Null
Set-Location $InstallDir

$LogFile = Join-Path $InstallDir "logs\install\install_$(Get-Date -f 'yyyyMMdd_HHmmss').log"

function Log {
    param([string]$msg, [string]$col = "Gray")
    $ts   = Get-Date -f "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line -ForegroundColor $col
    Add-Content $LogFile $line -Encoding UTF8
}
function LogOK($msg)   { Log "  OK $msg" "Green"   }
function LogWarn($msg) { Log "  !! $msg" "Yellow"  }
function LogErr($msg)  { Log "  XX $msg" "Red"     }
function LogHead($msg) { Log "`n== $msg" "Cyan"    }

# ===============================================================
# 1. HELYIGENY FELMERES
# ===============================================================
LogHead "HELYIGENY FELMERES"

$components = [ordered]@{
    "WSL2 Ubuntu alap"         = 1200
    "Python 3.11 + csomagok"   = 800
    "PostgreSQL"               = 400
    "ChromaDB"                 = 300
    "Ollama motor"             = 200
    "LLM modell llama3 8b"    = 5100
    "LLM modell mistral 7b"   = 4500
    "Alkalmazas kod"           = 50
    "Foglalt puffer log/tmp"   = 500
}

$totalMB = ($components.Values | Measure-Object -Sum).Sum
$totalGB  = [math]::Round($totalMB / 1024, 1)

Log "Szukseges hely komponensenkent:"
foreach ($c in $components.GetEnumerator()) {
    $gb  = [math]::Round($c.Value / 1024, 1)
    $pad = $c.Key.PadRight(36)
    Log "    $pad $($c.Value) MB  (~$gb GB)"
}
Log ""
Log "  OSSZESEN: ~$totalGB GB" "Cyan"

$drive    = Split-Path $InstallDir -Qualifier
$disk     = Get-PSDrive ($drive.TrimEnd(':'))
$freeMB   = [math]::Round($disk.Free / 1MB)
$freeGB   = [math]::Round($freeMB / 1024, 1)
$neededMB = $totalMB + 2048

Log ""
Log "  Telepitesi hely: $InstallDir"
Log "  Szabad hely:     $freeGB GB  ($freeMB MB)"
Log "  Szukseges hely:  $([math]::Round($neededMB/1024,1)) GB"

if ($freeMB -lt $neededMB) {
    LogErr "NINCS ELEG SZABAD HELY!"
    LogErr "Hiany: $([math]::Round(($neededMB - $freeMB)/1024,1)) GB"
    Read-Host "Nyomj Enter-t a kilepeshez"
    exit 1
}
LogOK "Elegendo szabad hely: $freeGB GB"

# ===============================================================
# 2. RENDSZER FELFEDEZESE
# ===============================================================
LogHead "RENDSZER FELFEDEZESE"

$winVer = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").DisplayVersion
LogOK "Windows: $winVer"

$wslInstalled = $false
try {
    $null = wsl --version 2>$null
    if ($LASTEXITCODE -eq 0) { $wslInstalled = $true; LogOK "WSL2 telepitve" }
} catch {}
if (-not $wslInstalled) { LogWarn "WSL2 nincs telepitve - telepitjuk" }

$hasGPU = $false
try {
    $gpu = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" }
    if ($gpu) { $hasGPU = $true; LogOK "NVIDIA GPU: $($gpu.Name)" }
    else       { LogWarn "NVIDIA GPU nem talalhato - Ollama CPU modban fut" }
} catch { LogWarn "GPU ellenorzes nem sikerult" }

$hasInternet = Test-NetConnection -ComputerName "8.8.8.8" -Port 53 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($hasInternet) { LogOK "Internet kapcsolat OK" }
else { LogErr "Nincs internet kapcsolat - szukseges a telepiteshez!"; exit 1 }

# ===============================================================
# 3. TELEPITESI TERV
# ===============================================================
LogHead "TELEPITESI TERV"

$plan = @()
if (-not $wslInstalled) {
    $plan += "WSL2 engedelyezese es Ubuntu telepitese"
} else {
    $crtDistro = wsl --list --quiet 2>$null | Where-Object { $_ -match "CRT" }
    if (-not $crtDistro) { $plan += "CRT Ubuntu disztrubucio letrehozasa" }
    else { LogOK "CRT WSL disztribucio mar letezik" }
}
$plan += "Python 3.11 + osszes csomag telepitese (WSL-ben)"
$plan += "PostgreSQL telepitese es konfigaralasa (WSL-ben)"
$plan += "ChromaDB telepitese (WSL-ben)"
$plan += "Ollama telepitese (WSL-ben)"
if ($hasGPU) { $plan += "NVIDIA GPU driver konfiguracio (WSL-ben)" }
$plan += "LLM modellek letoltese: llama3:8b (~5GB), mistral:7b (~4.5GB)"
$plan += "CRT adatbazis schema inicializalasa"
$plan += "Windows inditoparancsfajlok letrehozasa"

Log "A kovetkezo lepesek kerulnek vegrehajtasra:"
$i = 1
foreach ($p in $plan) { Log "  $i. $p"; $i++ }

Log ""
Log "  Telepitesi mappa: $InstallDir" "Cyan"
Log "  Becsult ido: 15-45 perc (internet sebessegtoI fugg)" "Cyan"
Log ""

$confirm = Read-Host "  Folytatod a telepitест? (I/N)"
if ($confirm -notmatch "^[Ii]") { Log "Telepites megszakitva."; exit 0 }

# ===============================================================
# ADMIN FIOK - adatok bekérése mielőtt a hosszu telepites indul
# ===============================================================
LogHead "ADMIN FIOK BEALLITASA"
Log "Az elso admin felhasznalo adatait add meg most."
Log ""

$adminUser = ""
while ($adminUser.Trim().Length -lt 2) {
    $adminUser = Read-Host "  Admin felhasznalonev (min. 2 karakter)"
}

$adminPin = ""
while ($adminPin -notmatch "^\d{6}$") {
    $adminPin = Read-Host "  Admin PIN (pontosan 6 szamjegy)"
}

$adminPin2 = ""
while ($adminPin2 -ne $adminPin) {
    $adminPin2 = Read-Host "  Admin PIN megerosites"
    if ($adminPin2 -ne $adminPin) { LogWarn "A ket PIN nem egyezik!" }
}

$adminEmail = Read-Host "  Admin email (opcionalis, 2FA OTP-hez - Enter ha nincs)"

LogOK "Admin adatok elfogadva: $($adminUser.Trim())"
Log ""

# ===============================================================
# 4. WSL2 TELEPITES
# ===============================================================
LogHead "WSL2 BEALLITAS"

if (-not $wslInstalled) {
    Log "WSL2 engedelyezese..."
    wsl --install --no-distribution 2>&1 | ForEach-Object { Log "  $_" }
    LogWarn "UJRAINDITAS SZUKSEGES a WSL2 aktivalasahoz."
    LogWarn "Inditsd ujra a gepet, majd futtasd ujra az install.bat-ot."
    Read-Host "Nyomj Enter-t a kilepeshez"
    exit 0
}

$crtDistro = wsl --list --quiet 2>$null | Where-Object { $_ -match "CRT" }
$wslDir    = Join-Path $InstallDir "wsl"
New-Item -ItemType Directory -Force -Path $wslDir | Out-Null

if (-not $crtDistro) {
    Log "Ubuntu alap letoltese WSL2-hoz..."
    $ubuntuTar = Join-Path $wslDir "ubuntu-base.tar.gz"
    if (-not (Test-Path $ubuntuTar)) {
        $ubuntuUrl = "https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04-base-amd64.tar.gz"
        Log "  Letoltes: $ubuntuUrl"
        Invoke-WebRequest -Uri $ubuntuUrl -OutFile $ubuntuTar -UseBasicParsing
    }
    Log "  CRT Ubuntu disztribucio importalasa..."
    wsl --import CRT $wslDir $ubuntuTar --version 2
    if ($LASTEXITCODE -ne 0) { LogErr "WSL2 import sikertelen"; exit 1 }
    LogOK "CRT Ubuntu disztribucio letrehozva"
} else {
    LogOK "CRT Ubuntu disztribucio mar letezik"
}

# ===============================================================
# 5. UBUNTU BELSO TELEPITES
# ===============================================================
LogHead "UBUNTU BELSO TELEPITES"

$wslInstDir = "/mnt/" + $InstallDir[0].ToString().ToLower() + ($InstallDir.Substring(2) -replace "\\", "/")
$wslSetupDir = "/mnt/" + $PSScriptRoot[0].ToString().ToLower() + ($PSScriptRoot.Substring(2) -replace "\\", "/")

Log "Ubuntu belso telepites inditasa..."
Log "  (Ez 10-30 percet vehet igénybe)"
Log ""

$buildCmd = "dos2unix '$wslSetupDir/build_wsl.sh' 2>/dev/null; bash '$wslSetupDir/build_wsl.sh' '$wslInstDir' 2>&1"
wsl -d CRT -- bash -c $buildCmd

if ($LASTEXITCODE -ne 0) {
    LogErr "Ubuntu telepites hibaval zarult. Ellenorizd: $LogFile"
    exit 1
}

LogOK "Ubuntu belso telepites kesz"

# ===============================================================
# 6. WINDOWS INDITOSZKRIPTEK
# ===============================================================
LogHead "WINDOWS INDITOSZKRIPTEK FRISSITESE"

$startBat = Join-Path $InstallDir "start.bat"
$startLines = @(
    '@echo off',
    'chcp 65001 >nul',
    'title CRT Ajanlatseged',
    "wsl -d CRT -- bash -c ""cd '$wslInstDir' ^&^& bash _setup/wsl_start.sh"" &",
    'timeout /t 8 /nobreak >nul',
    'start "" "http://localhost"'
)
Set-Content $startBat $startLines -Encoding UTF8
LogOK "start.bat frissitve"

# ===============================================================
# 7. DB MIGRACIO
# ===============================================================
LogHead "ADATBAZIS INICIALIZALAS"

Log "Varakozas PostgreSQL indulasra (max 30s)..."
$pgReady = $false
for ($i = 0; $i -lt 6; $i++) {
    Start-Sleep 5
    wsl -d CRT -- bash -c "pg_isready -U crt_user -d crt 2>/dev/null" 2>$null
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
}

$adminUserTrim  = $adminUser.Trim()
$adminEmailTrim = $adminEmail.Trim()

$migrateCmd = "set -e; " +
    "cd '$wslInstDir'; " +
    "export CRT_DB_URL=postgresql://crt_user:crt2026@localhost:5432/crt; " +
    "export PYTHONUTF8=1; " +
    "export CRT_ADMIN_USER='$adminUserTrim'; " +
    "export CRT_ADMIN_PIN='$adminPin'; " +
    "export CRT_ADMIN_EMAIL='$adminEmailTrim'; " +
    "python3.11 db_schema.py && " +
    "python3.11 _setup/create_admin.py && " +
    "python3.11 db_migrate_v02.py && " +
    "python3.11 db_migrate_v04.py && " +
    "python3.11 db_migrate_v05.py && " +
    "python3.11 db_migrate_v06.py && " +
    "python3.11 db_migrate_v07.py && " +
    "python3.11 db_migrate_v08.py"

if (-not $pgReady) {
    LogWarn "PostgreSQL nem indult el - migraciót kézzel kell futtatni:"
    LogWarn "  wsl -d CRT -- bash -c 'cd $wslInstDir && python3.11 _setup/create_admin.py'"
} else {
    Log "DB migracio futtatasa (db_schema -> admin -> v02-v08)..."
    wsl -d CRT -- bash -c $migrateCmd
    if ($LASTEXITCODE -eq 0) { LogOK "Adatbazis schema kesz" }
    else { LogWarn "Migracio hiba - ellenorizd a naplot" }
}

# ===============================================================
# 8. KESZ
# ===============================================================
LogHead "TELEPITES KESZ"

Log ""
LogOK "CRT Ajanlatseged sikeresen telepitve!"
Log ""
Log "  Inditas:     double-click start.bat" "Cyan"
Log "  Bongeszobe:  http://localhost" "Cyan"
Log "  Backend API: http://localhost:8000" "Cyan"
Log "  Admin:       $adminUserTrim  (PIN amit megadtal)" "Yellow"
Log ""
Log "  Telepitesi naplo: $LogFile"
Log ""
Read-Host "Nyomj Enter-t a kilepeshez"
