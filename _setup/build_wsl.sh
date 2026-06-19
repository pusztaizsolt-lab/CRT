#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# CRT Ajánlatsegéd – Linux telepítő
# Futtatja: CRT_install.ps1 (WSL2) VAGY kézzel (bare Linux)
#
# Használat:
#   WSL2-ből:    bash build_wsl.sh /mnt/h/Saját\ meghajtó/CRT
#   Linux gépen: sudo bash build_wsl.sh /opt/crt
#   Alapértelmezett: /opt/crt
# ═══════════════════════════════════════════════════════════════
set -e

# ── Platform detektálás ──────────────────────────────────────────
if grep -qi "microsoft\|WSL" /proc/version 2>/dev/null; then
    PLATFORM="wsl2"
    CRT_DIR_DEFAULT="/mnt/h/Saját meghajtó/CRT"
else
    PLATFORM="linux"
    CRT_DIR_DEFAULT="/opt/crt"
fi

CRT_DIR="${1:-$CRT_DIR_DEFAULT}"

# Bare Linux: ha nem létezik a mappa, létrehozzuk
if [ "$PLATFORM" = "linux" ] && [ ! -d "$CRT_DIR" ]; then
    mkdir -p "$CRT_DIR"
fi

LOG="$CRT_DIR/logs/install/wsl_build.log"
mkdir -p "$(dirname "$LOG")"

log()  { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
ok()   { log "  OK $*"; }
warn() { log "  WARN $*"; }
err()  { log "  ERR $*"; exit 1; }
head() { log ""; log "== $*"; }

log "============================================"
log " CRT Ajánlatsegéd – Linux telepítő"
log " Platform:  $PLATFORM"
log " CRT mappa: $CRT_DIR"
log "============================================"

head "RENDSZER FRISSÍTÉS"
apt-get update -qq && apt-get upgrade -y -qq
ok "apt frissítve"

# Alapeszközök
apt-get install -y -qq \
    curl wget git unzip sudo dos2unix \
    build-essential ca-certificates gnupg lsb-release \
    locales tzdata
locale-gen hu_HU.UTF-8
update-locale LANG=hu_HU.UTF-8
ok "Alapeszközök telepítve"

# Időzóna
ln -sf /usr/share/zoneinfo/Europe/Budapest /etc/localtime
ok "Időzóna: Budapest"

head "POSTGRESQL 16"
if ! command -v psql &>/dev/null; then
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq postgresql-16 postgresql-client-16
    ok "PostgreSQL 16 telepítve"
else
    ok "PostgreSQL már telepítve"
fi

# PostgreSQL konfig – adatkönyvtár a CRT mappába
PG_DATA="$CRT_DIR/db_data/pg"
mkdir -p "$PG_DATA"
chown -R postgres:postgres "$CRT_DIR/db_data"

PG_CONF="/etc/postgresql/16/main/postgresql.conf"
PG_HBA="/etc/postgresql/16/main/pg_hba.conf"

# data_directory módosítása
sed -i "s|data_directory = .*|data_directory = '$PG_DATA'|" "$PG_CONF" 2>/dev/null || true

# Inicializálás ha szükséges
if [ ! -f "$PG_DATA/PG_VERSION" ]; then
    sudo -u postgres /usr/lib/postgresql/16/bin/initdb -D "$PG_DATA" -E UTF8 --locale=hu_HU.UTF-8
    ok "PostgreSQL adatkönyvtár inicializálva: $PG_DATA"
fi

# pg_hba.conf – lokális hozzáférés jelszóval
cat > "$PG_HBA" << 'EOF'
local   all             postgres                                peer
local   all             all                                     md5
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
EOF

service postgresql start
sleep 2

# CRT adatbázis és felhasználó létrehozása
sudo -u postgres psql -c "CREATE USER crt_user WITH PASSWORD 'crt2026';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE crt OWNER crt_user;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE crt TO crt_user;" 2>/dev/null || true
ok "PostgreSQL adatbázis: crt (felhasználó: crt_user)"

head "PYTHON 3.11"
if ! python3.11 --version &>/dev/null; then
    apt-get install -y -qq software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3-pip
    ok "Python 3.11 telepítve"
else
    ok "Python 3.11 már telepítve: $(python3.11 --version)"
fi

# pip frissítés
python3.11 -m pip install --upgrade pip -q
ok "pip frissítve"

head "PYTHON CSOMAGOK"
pip3.11 install --quiet \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.30.6" \
    sqlalchemy==2.0.35 \
    psycopg2-binary==2.9.9 \
    pydantic==2.9.2 \
    bcrypt==4.2.0 \
    "python-jose[cryptography]==3.3.0" \
    openpyxl==3.1.5 \
    pdfplumber==0.11.4 \
    python-docx==1.1.2 \
    beautifulsoup4==4.12.3 \
    xlrd==2.0.1 \
    chardet==5.2.0 \
    "anthropic>=0.34.0" \
    ntplib==0.4.0 \
    python-multipart==0.0.12 \
    chromadb \
    sentence-transformers \
    playwright
ok "Python csomagok telepítve"

head "LORA FINOMHANGOLÁS CSOMAGOK"
pip3.11 install --quiet \
    "transformers>=4.40.0" \
    "peft>=0.10.0" \
    "trl>=0.8.0" \
    "datasets>=2.18.0" \
    "accelerate>=0.28.0"
# bitsandbytes: 4-bit QLoRA GPU-hoz; CPU módban is települ, de kvantálás csak CUDA-val
pip3.11 install --quiet bitsandbytes && ok "bitsandbytes (4-bit QLoRA) telepítve" \
    || warn "bitsandbytes nem települt – CPU módban fut (lassabb, de működik)"
ok "LoRA csomagok telepítve (transformers / peft / trl / datasets / accelerate)"

# Playwright böngészők
python3.11 -m playwright install chromium --with-deps 2>/dev/null && ok "Playwright Chromium telepítve" || warn "Playwright telepítés nem sikerült"

head "CHROMADB SERVICE"
cat > /etc/systemd/system/crt-chroma.service << EOF
[Unit]
Description=CRT ChromaDB vektoros adatbázis
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$CRT_DIR
ExecStart=python3.11 -m chromadb.cli.cli run --host 127.0.0.1 --port 8001 --path $CRT_DIR/vectors/chroma
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
ok "ChromaDB service regisztrálva (port: 8001)"

head "OLLAMA (HELYI LLM)"
if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
    ok "Ollama telepítve"
else
    ok "Ollama már telepítve"
fi

# Ollama service – modellek a CRT mappában
mkdir -p "$CRT_DIR/models/ollama"
cat > /etc/systemd/system/crt-ollama.service << EOF
[Unit]
Description=CRT Ollama LLM szerver
After=network.target

[Service]
Type=simple
User=root
Environment=OLLAMA_MODELS=$CRT_DIR/models/ollama
Environment=OLLAMA_HOST=0.0.0.0:11434
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl enable crt-ollama 2>/dev/null && ok "Ollama service engedélyezve" || warn "systemd nem elérhető (WSL2 – kézzel indul)"

head "LLM MODELLEK LETÖLTÉSE"
warn "Ez sok időt vehet igénybe (llama3:8b ~5GB, mistral:7b ~4.5GB)"
warn "Internet kapcsolat szükséges"

# Ollama indítása letöltéshez
OLLAMA_MODELS="$CRT_DIR/models/ollama" ollama serve &>/dev/null &
OLLAMA_PID=$!
sleep 5

if curl -sf http://localhost:11434 &>/dev/null; then
    log "  Letöltés: llama3:8b (~5GB)..."
    OLLAMA_MODELS="$CRT_DIR/models/ollama" ollama pull llama3:8b 2>&1 | tail -5 | tee -a "$LOG"
    ok "llama3:8b letöltve"

    log "  Letöltés: mistral:7b (~4.5GB)..."
    OLLAMA_MODELS="$CRT_DIR/models/ollama" ollama pull mistral:7b 2>&1 | tail -5 | tee -a "$LOG"
    ok "mistral:7b letöltve"

    log "  Letöltés: llava:7b (~4.1GB) – tervrajz / képelemzés..."
    OLLAMA_MODELS="$CRT_DIR/models/ollama" ollama pull llava:7b 2>&1 | tail -5 | tee -a "$LOG"
    ok "llava:7b letöltve"
else
    warn "Ollama nem válaszol – modellek letöltése kihagyva"
    warn "Kézzel: OLLAMA_MODELS=$CRT_DIR/models/ollama ollama pull llama3:8b"
    warn "Kézzel: OLLAMA_MODELS=$CRT_DIR/models/ollama ollama pull llava:7b"
fi

kill $OLLAMA_PID 2>/dev/null || true

head "NGINX (UI KISZOLGÁLÓ)"
apt-get install -y -qq nginx
mkdir -p "$CRT_DIR/logs/nginx"

# Konfig a sablon alapján (placeholderek behelyettesítése)
sed "s|__CRT_DIR__|$CRT_DIR|g" "$CRT_DIR/_setup/nginx/nginx.conf" \
    > /etc/nginx/sites-available/crt
ln -sf /etc/nginx/sites-available/crt /etc/nginx/sites-enabled/crt
rm -f /etc/nginx/sites-enabled/default
nginx -t && ok "Nginx konfiguráció OK" || warn "Nginx konfig hiba"

head "CRT BACKEND SERVICE"
cat > /etc/systemd/system/crt-backend.service << EOF
[Unit]
Description=CRT Ajánlatsegéd FastAPI Backend
After=postgresql.service network.target

[Service]
Type=simple
User=root
WorkingDirectory=$CRT_DIR
Environment=CRT_ENV=production
Environment=CRT_DB_URL=postgresql://crt_user:crt2026@localhost:5432/crt
Environment=CRT_OLLAMA_URL=http://localhost:11434
Environment=CRT_CHROMA_URL=http://localhost:8001
EnvironmentFile=-$CRT_DIR/.env
ExecStart=python3.11 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:$CRT_DIR/logs/backend/backend.log
StandardError=append:$CRT_DIR/logs/backend/error.log

[Install]
WantedBy=multi-user.target
EOF
ok "CRT Backend service regisztrálva"

head "WSL INDÍTÓSZKRIPT"
# wsl_start.sh már a csomagban van – csak futtathatóvá tesszük
if [ -f "$CRT_DIR/_setup/wsl_start.sh" ]; then
    dos2unix "$CRT_DIR/_setup/wsl_start.sh" 2>/dev/null || true
    chmod +x "$CRT_DIR/_setup/wsl_start.sh"
    ok "wsl_start.sh jogosultság beállítva"
else
    warn "wsl_start.sh nem található: $CRT_DIR/_setup/wsl_start.sh"
fi

head "TELEPÍTÉS BEFEJEZVE"
log ""
ok "CRT WSL2 Ubuntu környezet kész!"
log "  PostgreSQL:  localhost:5432"
log "  Backend API: localhost:8000"
log "  ChromaDB:    localhost:8001"
log "  Ollama LLM:  localhost:11434"
log "  UI:          http://localhost"
