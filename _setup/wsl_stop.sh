#!/bin/bash
# CRT Ajanlatseged - Linux leallito
# Hivas: wsl -d CRT -- bash _setup/wsl_stop.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRT_DIR="$(dirname "$SCRIPT_DIR")"

ts()   { date '+%Y-%m-%d %H:%M:%S'; }
ok()   { echo "$(ts) [OK]  $*"; }
warn() { echo "$(ts) [!!]  $*"; }

echo "$(ts) CRT - Szolgaltatasok leallitasa..."

# FastAPI (uvicorn) - PID fajlbol
if [ -f "$CRT_DIR/run/crt.pid" ]; then
    PID=$(cat "$CRT_DIR/run/crt.pid" 2>/dev/null)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        sleep 1
        kill -9 "$PID" 2>/dev/null || true
        ok "FastAPI leallitva (PID $PID)"
    fi
    rm -f "$CRT_DIR/run/crt.pid"
else
    pkill -f "uvicorn main:app" 2>/dev/null && ok "FastAPI leallitva (pkill)" || true
fi

# ChromaDB
if [ -f "$CRT_DIR/run/chroma.pid" ]; then
    PID=$(cat "$CRT_DIR/run/chroma.pid" 2>/dev/null)
    kill "$PID" 2>/dev/null || true
    rm -f "$CRT_DIR/run/chroma.pid"
    ok "ChromaDB leallitva"
else
    pkill -f "chromadb" 2>/dev/null || true
fi

# Ollama
if [ -f "$CRT_DIR/run/ollama.pid" ]; then
    PID=$(cat "$CRT_DIR/run/ollama.pid" 2>/dev/null)
    kill "$PID" 2>/dev/null || true
    rm -f "$CRT_DIR/run/ollama.pid"
    ok "Ollama leallitva"
else
    pkill -x "ollama" 2>/dev/null || true
fi

# Nginx
if command -v nginx &>/dev/null; then
    nginx -s quit 2>/dev/null && ok "Nginx leallitva" || service nginx stop 2>/dev/null || true
fi

# PostgreSQL
if command -v pg_ctlcluster &>/dev/null; then
    pg_ctlcluster 16 main stop 2>/dev/null && ok "PostgreSQL leallitva" || true
elif command -v service &>/dev/null; then
    service postgresql stop 2>/dev/null && ok "PostgreSQL leallitva" || true
fi

# Runtime state torlese
cat > "$CRT_DIR/metrics/runtime.json" <<'EOF'
{"status": "stopped"}
EOF

echo "$(ts) Minden szolgaltatas leallitva."
