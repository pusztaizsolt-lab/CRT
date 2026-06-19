# ===============================================================
# CRT Ajanlatseged - WSL2 disztribucio exportalo
# Hasznalat: powershell -File _setup\wsl_export.ps1
# Letrehoz: wsl\crt_export_YYYYMMDD.tar  (~1-2GB tomoritve)
# ===============================================================

$InstallDir = Split-Path $PSScriptRoot -Parent
$ExportDir  = Join-Path $InstallDir "wsl"
$DateStr    = Get-Date -f "yyyyMMdd_HHmmss"
$ExportFile = Join-Path $ExportDir "crt_export_$DateStr.tar"

function Log($msg, $col = "Gray") {
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] $msg" -ForegroundColor $col
}

Log "CRT WSL2 Export" "Cyan"
Log "Cel: $ExportFile"
Log ""

# CRT disztribucio ellenorzese
$distros = wsl --list --quiet 2>$null
if (-not ($distros | Where-Object { $_ -match "CRT" })) {
    Log "HIBA: CRT WSL disztribucio nem talalhato!" "Red"
    Log "Futtasd elobb: install.bat" "Yellow"
    Read-Host "Enter a kilepeshez"
    exit 1
}

# Leallitas exportalas elott
Log "Szolgaltatasok leallitasa exportalas elott..."
$wslInstDir = "/mnt/" + $InstallDir[0].ToString().ToLower() + ($InstallDir.Substring(2) -replace "\\", "/")
wsl -d CRT -- bash -c "bash '$wslInstDir/_setup/wsl_stop.sh' 2>/dev/null; sleep 2"
Log "Leallitva." "Green"

# Export
New-Item -ItemType Directory -Force -Path $ExportDir | Out-Null
Log "Export folyamatban (ez 2-5 percig tarthat)..."
wsl --export CRT $ExportFile

if ($LASTEXITCODE -eq 0) {
    $sizeMB = [math]::Round((Get-Item $ExportFile).Length / 1MB)
    Log "Export kesz: $ExportFile  ($sizeMB MB)" "Green"
    Log ""
    Log "Uj gepre telepites:" "Cyan"
    Log "  wsl --import CRT D:\CRT\wsl $ExportFile --version 2"
    Log "  Majd: start.bat"
} else {
    Log "HIBA: wsl --export sikertelen!" "Red"
    exit 1
}

Log ""
Read-Host "Enter a kilepeshez"
