#!/usr/bin/env bash
# CRT Smoke Test – minden indításkor lefut, ~30 másodperc
# Visszatérési érték: 0 = minden OK, 1 = valami nem él

set -euo pipefail

PASS=0; FAIL=0
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  OK${NC}  $1"; ((PASS++)); }
fail() { echo -e "${RED}FAIL${NC}  $1: $2"; ((FAIL++)); }

check() {
    local label="$1"; shift
    if eval "$@" &>/dev/null; then ok "$label"; else fail "$label" "$*"; fi
}

DB_URL="${CRT_DB_URL:-postgresql://crt_user:crt2026@localhost:5432/crt}"

echo "=== CRT Smoke Test $(date '+%Y-%m-%d %H:%M:%S') ==="

check "PostgreSQL"   "psql '$DB_URL' -c 'SELECT 1' -t"
check "FastAPI"      "curl -sf --max-time 5 http://localhost:8000/health"
check "Nginx"        "curl -sf --max-time 5 http://localhost/"
check "Ollama"       "curl -sf --max-time 5 http://localhost:11434/api/tags"
check "ChromaDB"     "curl -sf --max-time 5 http://localhost:8001/api/v1/heartbeat"

echo ""
echo "Eredmény: ${PASS} OK  /  ${FAIL} FAIL"

if [ "$FAIL" -gt 0 ]; then
    echo "SMOKE SIKERTELEN – a rendszer nem indítható el élesben." >&2
    exit 1
fi

echo "Minden szolgáltatás él."
exit 0
