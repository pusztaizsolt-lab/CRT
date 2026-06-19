# CRT Böngészős Teszt — PowerShell launcher
# Futtatás: .\browser_test.ps1
#           .\browser_test.ps1 -Headed
#           .\browser_test.ps1 -Headed -Slow 500
#           .\browser_test.ps1 -Page arak
param(
    [switch]$Headed,
    [string]$Page  = "",
    [int]   $Slow  = 0
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Ellenőrzés: fut-e a backend?
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -ne 200) { throw "HTTP $($r.StatusCode)" }
} catch {
    Write-Host ""
    Write-Host "  HIBA: CRT backend nem fut (http://localhost:8000/health)." -ForegroundColor Red
    Write-Host "  Indítsd el: .\start.ps1" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Playwright chromium telepítve?
$playwrightOk = py -3.11 -c "from playwright.sync_api import sync_playwright; print('ok')" 2>&1
if ($playwrightOk -notmatch "ok") {
    Write-Host "  Playwright nem elérhető. Telepítés..." -ForegroundColor Yellow
    py -3.11 -m pip install playwright | Out-Null
    py -3.11 -m playwright install chromium
}

# Argok összeállítása
$args_list = @("_test/browser_test.py")
if ($Headed)   { $args_list += "--headed" }
if ($Page)     { $args_list += "--page"; $args_list += $Page }
if ($Slow -gt 0) { $args_list += "--slow"; $args_list += "$Slow" }

# Futtatás
py -3.11 @args_list
exit $LASTEXITCODE
