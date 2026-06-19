# ═══════════════════════════════════════════════════════════════
# CRT Ajánlatsegéd – Bootstrap ZIP csomag készítő
# Kimenet: CRT_bootstrap_vX.X_YYYYMMDD.zip  (~50MB)
# Ez a csomag elegendő az install.bat futtatásához.
# A WSL2 Ubuntu, modellek és adatbázis NEM kerülnek bele –
# azokat az install.bat tölti le / telepíti helyben.
# ═══════════════════════════════════════════════════════════════

param(
    [string]$Version    = "0.8",
    [string]$SourceDir  = "$PSScriptRoot\..",
    [string]$OutputDir  = "$PSScriptRoot\..\exports"
)

$ErrorActionPreference = "Stop"
$Date     = Get-Date -Format "yyyyMMdd"
$ZipName  = "CRT_bootstrap_v${Version}_${Date}.zip"
$TempDir  = "$env:TEMP\CRT_pack_$Date"
$ZipPath  = "$OutputDir\$ZipName"

# ── Segédfüggvények ───────────────────────────────────────────
function Log([string]$msg, [string]$col = "Cyan") {
    Write-Host "  $msg" -ForegroundColor $col
}

function Sep { Write-Host ("═" * 54) -ForegroundColor DarkGray }

# ── Kizárt mappák / fájlok ────────────────────────────────────
# Ezek NEM kerülnek a csomagba:
$EXCLUDE_DIRS = @(
    "db_data",       # PostgreSQL adatok
    "models",        # LLM modellek (~10GB)
    "vectors",       # ChromaDB vektorok
    "wsl",           # WSL2 ext4.vhdx (~1.2GB)
    "uploads",       # Feltöltött fájlok
    "exports",       # Export fájlok
    "logs",          # Futási naplók
    "__pycache__",   # Python cache
    ".git",          # Git repository
    "old",           # Archív fájlok
    ".vscode",       # VS Code konfig
    "wheels"         # Offline wheel-ek
)

$EXCLUDE_EXTS = @(
    ".pyc", ".pyo",  # Python bytecode
    ".log",          # Naplók
    ".zip",          # Korábbi csomagok
    ".xlsx", ".docx", ".pdf",  # Export fájlok
    ".jsonl", ".json.bak"      # Backup fájlok
)

$EXCLUDE_FILES = @(
    ".env",          # Titkos kulcsok
    "pg.log",
    "crt.log"
)

# ── Főprogram ─────────────────────────────────────────────────
Sep
Write-Host "  CRT Bootstrap Csomag Készítő" -ForegroundColor Magenta
Write-Host "  Verzió: $Version | Dátum: $Date" -ForegroundColor DarkGray
Sep

# Forrás könyvtár ellenőrzés
$src = (Resolve-Path $SourceDir).Path
if (-not (Test-Path "$src\main.py")) {
    Write-Host "  HIBA: Nem CRT mappa: $src" -ForegroundColor Red
    exit 1
}
Log "Forrás: $src"

# Output könyvtár
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
$out = (Resolve-Path $OutputDir).Path
Log "Kimenet: $out\$ZipName"

# Temp könyvtár
if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force }
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

# ── Fájlok másolása ───────────────────────────────────────────
Log "Fájlok összegyűjtése..." "Yellow"

$copied = 0
$skipped = 0

Get-ChildItem -Path $src -Recurse | ForEach-Object {
    $item     = $_
    $relPath  = $item.FullName.Substring($src.Length + 1)
    $parts    = $relPath -split "\\"

    # Kizárt mappák ellenőrzése
    $exclude = $false
    foreach ($excDir in $EXCLUDE_DIRS) {
        if ($parts -contains $excDir) { $exclude = $true; break }
    }
    if ($exclude) { $skipped++; return }

    # Kizárt kiterjesztések
    if (-not $item.PSIsContainer) {
        $ext = $item.Extension.ToLower()
        if ($EXCLUDE_EXTS -contains $ext) { $skipped++; return }
        if ($EXCLUDE_FILES -contains $item.Name) { $skipped++; return }
    }

    # Másolás
    $dest = Join-Path $TempDir $relPath
    if ($item.PSIsContainer) {
        if (-not (Test-Path $dest)) {
            New-Item -ItemType Directory -Path $dest -Force | Out-Null
        }
    } else {
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -Path $item.FullName -Destination $dest -Force
        $copied++
    }
}

Log "  Másolt fájlok: $copied  |  Kihagyott: $skipped" "Gray"

# ── Szükséges üres mappák létrehozása ─────────────────────────
$REQUIRED_DIRS = @(
    "db_data\pg",
    "db_data\backups",
    "models\ollama",
    "vectors\chroma",
    "logs\backend",
    "logs\nginx",
    "logs\install",
    "uploads",
    "exports\excel",
    "exports\word",
    "exports\pdf",
    "wsl"
)

foreach ($d in $REQUIRED_DIRS) {
    $path = Join-Path $TempDir $d
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    # .gitkeep hogy a ZIP ne hagyja ki az üres mappákat
    $keep = Join-Path $path ".gitkeep"
    if (-not (Test-Path $keep)) {
        "" | Out-File -FilePath $keep -Encoding utf8
    }
}
Log "Üres mappák előkészítve (${REQUIRED_DIRS.Count} db)" "Gray"

# ── ZIP készítése ─────────────────────────────────────────────
Log "ZIP tömörítés..." "Yellow"

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $TempDir,
    $ZipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

# ── Összefoglaló ──────────────────────────────────────────────
$sizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)

Sep
Log "Csomag kész: $ZipName" "Green"
Log "Méret:       ${sizeMB} MB" "Green"
Log ""
Log "Tartalom NEM tartalmaz:" "DarkGray"
Log "  • db_data\ (PostgreSQL adatok)"
Log "  • models\  (LLM modellek ~10GB)"
Log "  • wsl\     (Ubuntu ext4.vhdx ~1.2GB)"
Log "  • .env     (titkos kulcsok)"
Log ""
Log "Telepítés:" "Yellow"
Log "  1. Másold a ZIP-et a célgépre (pl. 250GB SSD D:\)"
Log "  2. Csomagold ki: D:\CRT\"
Log "  3. Futtasd: D:\CRT\install.bat  (Admin jogosultság kell)"
Sep

# Temp törlés
Remove-Item $TempDir -Recurse -Force
