# CRT Ajánlatsegéd — Asztali telepítő
# Futtatás: jobb klikk → Futtatás rendszergazdaként (nem kötelező)
# Amit csinál:
#   1. pip install pywebview pillow  (ha hiányzik)
#   2. crt.ico generálása
#   3. Asztali parancsikon létrehozása
# ==============================================================

$CrtRoot    = "D:\CRT"
$Launcher   = "$CrtRoot\crt_launcher.py"
$IcoPath    = "$CrtRoot\crt.ico"
$Python     = "pythonw"   # nincs konzol ablak
$ShortcutName = "CRT Ajánlatsegéd"

Write-Host ""
Write-Host " CRT Ajánlatsegéd — Asztali telepítő" -ForegroundColor Cyan
Write-Host " ======================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Függőségek ─────────────────────────────────────────────
Write-Host " [1/3] Python csomagok ellenőrzése…" -ForegroundColor Yellow

$packages = @("pywebview", "pillow")
foreach ($pkg in $packages) {
    $check = py -3.11 -c "import $($pkg -replace '-','_')" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "       Telepítés: $pkg" -ForegroundColor Gray
        py -3.11 -m pip install $pkg --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Host "       [OK] $pkg" -ForegroundColor Green
        } else {
            Write-Host "       [!!] $pkg telepítés sikertelen — folytatás..." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "       [OK] $pkg már telepítve" -ForegroundColor Green
    }
}

# ── 2. Ikon generálás ─────────────────────────────────────────
Write-Host ""
Write-Host " [2/3] Ikon generálása…" -ForegroundColor Yellow
py -3.11 "$CrtRoot\_setup\make_icon.py"
if (Test-Path $IcoPath) {
    Write-Host "       [OK] $IcoPath" -ForegroundColor Green
} else {
    Write-Host "       [!!] Ikon generálás sikertelen — parancsikon alapértelmezett ikonnal" -ForegroundColor DarkYellow
    $IcoPath = ""
}

# ── 3. Asztali parancsikon ────────────────────────────────────
Write-Host ""
Write-Host " [3/3] Asztali parancsikon létrehozása…" -ForegroundColor Yellow

$DesktopPath = [Environment]::GetFolderPath("Desktop")
$LinkPath    = "$DesktopPath\$ShortcutName.lnk"

$WshShell  = New-Object -ComObject WScript.Shell
$Shortcut  = $WshShell.CreateShortcut($LinkPath)

$Shortcut.TargetPath       = (Get-Command "py.exe" -ErrorAction SilentlyContinue)?.Source ?? "py.exe"
$Shortcut.Arguments        = "-3.11 `"$Launcher`""
$Shortcut.WorkingDirectory = $CrtRoot
$Shortcut.WindowStyle      = 1   # normál ablak (nem minimalizálva)
$Shortcut.Description      = "CRT Ajánlatsegéd — Civil Rendszertechnika Kft."

if ($IcoPath -and (Test-Path $IcoPath)) {
    $Shortcut.IconLocation = "$IcoPath,0"
}

$Shortcut.Save()

if (Test-Path $LinkPath) {
    Write-Host "       [OK] $LinkPath" -ForegroundColor Green
} else {
    Write-Host "       [!!] Parancsikon létrehozása sikertelen" -ForegroundColor Red
}

# ── Összegzés ─────────────────────────────────────────────────
Write-Host ""
Write-Host " Kész!" -ForegroundColor Green
Write-Host ""
Write-Host "  Dupla klikk az asztali '$ShortcutName' ikonra → CRT elindul"
Write-Host "  (Első indulás lassabb — szerver betöltés ~15-30s)"
Write-Host ""
Write-Host "  Ha nem indul el:" -ForegroundColor DarkYellow
Write-Host "    1. Futtasd kézzel: py -3.11 $Launcher"
Write-Host "    2. Ellenőrizd: $CrtRoot\logs\backend.log"
Write-Host ""
pause
