#!/bin/bash
# =============================================================================
# CRT Ajánlatsegéd – Univerzális Linux indító
# Működik: WSL2 Ubuntu 22.04 ÉS natív Linux gépen (bare metal / VM)
#
# Futási mód detektálás:
#   WSL2   → /proc/version tartalmaz "microsoft"
#   Linux  → /proc/version létezik, nincs "microsoft"
#
# Service kezelés:
#   systemd elérhető → systemctl
#   nincs systemd    → service (SysV init, WSL2 alapértelmezett)
# =============================================================================

set -e

# ── Könyvtár: mindig a wsl_start.sh melletti CRT root ────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$CRT_DIR"

# ── Logolás ───────────────────────────────────────────────────────────────────
mkdir -p "$CRT_DIR/logs/system" "$CRT_DIR/logs/backend" "$CRT_DIR/logs/nginx"
mkdir -p "$CRT_DIR/run" "$CRT_DIR/metrics"
LOG="$CRT_DIR/logs/system/startup.log"
exec > >(tee -a "$LOG") 2>&1

ts() { date '+%Y-%m-%d %H:%M:%S'; }
ok()   { echo "$(ts) [OK]    $*"; }
warn() { echo "$(ts) [WARN]  $*"; }
info() { echo "$(ts) [INFO]  $*"; }
err()  { echo "$(ts) [ERROR] $*"; }

info "============================================"
info " CRT Ajánlatsegéd – Indítás"
info " Mappa: $CRT_DIR"
info "============================================"

# ── Platform detektálás ───────────────────────────────────────────────────────
detect_platform() {
    if grep -qi "microsoft\|WSL" /proc/version 2>/dev/null; then
        echo "wsl2"
    else
        echo "linux"
    fi
}

detect_service_manager() {
    if systemctl is-system-running &>/dev/null || \
       [ -d /run/systemd/private ] || \
       [ -d /sys/fs/cgroup/systemd ]; then
        echo "systemd"
    else
        echo "sysv"
    fi
}

PLATFORM=$(detect_platform)
SVC_MGR=$(detect_service_manager)

info "Platform:  $PLATFORM"
info "Service:   $SVC_MGR"
info "Python:    $(python3.11 --version 2>/dev/null || echo 'hiányzik')"

# Platform info mentése
cat > "$CRT_DIR/metrics/runtime.json" << REOF
{
  "platform": "$PLATFORM",
  "service_mgr": "$SVC_MGR",
  "crt_dir": "$CRT_DIR",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "started_by": "wsl_start.sh"
}
REOF

# ── Service indító helper ──────────────────────────────────────────────────────
start_service() {
    local name="$1"
    if [ "$SVC_MGR" = "systemd" ]; then
        systemctl start "$name" 2>/dev/null && ok "$name (systemd)" || warn "$name systemctl start sikertelen"
    else
        service "$name" start 2>/dev/null && ok "$name (sysv)" || warn "$name service start sikertelen"
    fi
}

service_running() {
    local name="$1"
    if [ "$SVC_MGR" = "systemd" ]; then
        systemctl is-active --quiet "$name" 2>/dev/null
    else
        service "$name" status &>/dev/null
    fi
}

# ── PostgreSQL ────────────────────────────────────────────────────────────────
info "[1/5] PostgreSQL..."
if service_running postgresql; then
    ok "PostgreSQL már fut"
else
    start_service postgresql
    sleep 2
    if service_running postgresql; then
        ok "PostgreSQL elindult"
    else
        warn "PostgreSQL nem indult el — ellenőrizd: $CRT_DIR/logs/system/startup.log"
    fi
fi

# ── Nginx ─────────────────────────────────────────────────────────────────────
info "[2/5] Nginx..."
if [ -f "$SCRIPT_DIR/nginx/nginx.conf" ]; then
    # UI fájlok szinkronizálása /var/www/html/crt/ alá
    mkdir -p /var/www/html/crt
    rsync -a --delete "$CRT_DIR/ui/" /var/www/html/crt/ 2>/dev/null || \
        cp -r "$CRT_DIR/ui/." /var/www/html/crt/
    if service_running nginx; then
        ok "Nginx már fut"
    else
        start_service nginx
    fi
else
    warn "Nginx konfig nem található, kihagyva"
fi

# ── ChromaDB ──────────────────────────────────────────────────────────────────
info "[3/5] ChromaDB..."
mkdir -p "$CRT_DIR/vectors/chroma"
if pgrep -f "chromadb" > /dev/null 2>&1; then
    ok "ChromaDB már fut"
else
    nohup python3.11 -m chromadb.cli.cli run \
        --host 127.0.0.1 --port 8001 \
        --path "$CRT_DIR/vectors/chroma" \
        >> "$CRT_DIR/logs/system/chroma.log" 2>&1 &
    CHROMA_PID=$!
    echo "$CHROMA_PID" > "$CRT_DIR/run/chroma.pid"
    sleep 2
    if kill -0 "$CHROMA_PID" 2>/dev/null; then
        ok "ChromaDB elindult (PID: $CHROMA_PID)"
    else
        warn "ChromaDB indítás sikertelen — folytatás nélküle"
    fi
fi

# ── Ollama ────────────────────────────────────────────────────────────────────
info "[4/5] Ollama..."
OLLAMA_MODELS_DIR="$CRT_DIR/models/ollama"
mkdir -p "$OLLAMA_MODELS_DIR"
if pgrep -x "ollama" > /dev/null 2>&1; then
    ok "Ollama már fut"
elif command -v ollama &>/dev/null; then
    OLLAMA_MODELS="$OLLAMA_MODELS_DIR" nohup ollama serve \
        >> "$CRT_DIR/logs/system/ollama.log" 2>&1 &
    OLLAMA_PID=$!
    echo "$OLLAMA_PID" > "$CRT_DIR/run/ollama.pid"
    sleep 3
    if kill -0 "$OLLAMA_PID" 2>/dev/null; then
        ok "Ollama elindult (PID: $OLLAMA_PID)"
    else
        warn "Ollama indítás sikertelen — AI fallback: csak Claude API"
    fi
else
    warn "Ollama nincs telepítve — AI fallback: csak Claude API"
fi

# ── FastAPI backend ───────────────────────────────────────────────────────────
info "[5/5] CRT Backend (FastAPI)..."
if [ -f "$CRT_DIR/run/crt.pid" ]; then
    OLD_PID=$(cat "$CRT_DIR/run/crt.pid" 2>/dev/null)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "Backend már fut (PID: $OLD_PID), leállítás..."
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
fi

# .env betöltése ha létezik
if [ -f "$CRT_DIR/.env" ]; then
    set -a; source "$CRT_DIR/.env"; set +a
fi

nohup python3.11 -m uvicorn main:app \
    --host 0.0.0.0 --port 8000 --workers 2 \
    >> "$CRT_DIR/logs/backend/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$CRT_DIR/run/crt.pid"

# Várjuk meg hogy a backend elinduljon (max 30s)
info "Várakozás a backend indulására..."
for i in $(seq 1 15); do
    sleep 2
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        ok "Backend kész (PID: $BACKEND_PID)"
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        err "Backend leállt! Napló: $CRT_DIR/logs/backend/backend.log"
        exit 1
    fi
    info "  ... $((i*2))s"
done

# ── Runtime state frissítése ──────────────────────────────────────────────────
cat > "$CRT_DIR/metrics/runtime.json" << REOF
{
  "platform": "$PLATFORM",
  "service_mgr": "$SVC_MGR",
  "crt_dir": "$CRT_DIR",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "started_by": "wsl_start.sh",
  "backend_pid": $BACKEND_PID,
  "status": "running"
}
REOF

info "============================================"
ok "CRT Ajánlatsegéd fut!"
info "  Backend API:  http://localhost:8000"
info "  API docs:     http://localhost:8000/docs"
if nginx -t &>/dev/null 2>&1; then
    info "  UI (Nginx):   http://localhost"
else
    info "  UI (direkt):  ui/login.html (böngészőben)"
fi
info "  Naplók:       $CRT_DIR/logs/"
info "  Metrikák:     $CRT_DIR/metrics/runtime.json"
info "============================================"

# Tartjuk a processt (WSL2 igényli hogy a shell ne lépjen ki)
wait $BACKEND_PID
