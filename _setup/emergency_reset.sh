#!/usr/bin/env bash
# ================================================================
# CRT Vészkulcs – Admin zárolás feloldása + PIN visszaállítás
# Közvetlen PostgreSQL elérés (FastAPI nem kell, offline is működik)
#
# Használat:
#   bash _setup/emergency_reset.sh                  # interaktív
#   bash _setup/emergency_reset.sh admin            # csak zárolás törlése
#   bash _setup/emergency_reset.sh admin 123456     # zárolás + PIN csere
# ================================================================

set -euo pipefail

DB_URL="${CRT_DB_URL:-postgresql://crt_user:crt2026@localhost:5432/crt}"
SEP="════════════════════════════════════════════"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}${SEP}${NC}"
echo -e "${CYAN}  CRT Vészkulcs – Felhasználó visszaállítás${NC}"
echo -e "${CYAN}${SEP}${NC}"
echo ""

# ── PostgreSQL kapcsolat ellenőrzés ───────────────────────────────
if ! psql "$DB_URL" -c "SELECT 1" &>/dev/null; then
    echo -e "${RED}HIBA: PostgreSQL nem elérhető.${NC}"
    echo "  Ellenőrizd: fut-e a PostgreSQL (bash _setup/wsl_start.sh)"
    exit 1
fi
echo -e "${GREEN}  PostgreSQL kapcsolat OK${NC}"
echo ""

# ── Meglévő felhasználók listája ──────────────────────────────────
echo "Felhasználók:"
psql "$DB_URL" -t -A -F'|' -c \
    "SELECT username, role, active,
            CASE WHEN locked_until > NOW() THEN 'ZÁROLVA' ELSE 'szabad' END as allapot,
            attempt_count
     FROM users ORDER BY role, username" \
| while IFS='|' read -r user role active allapot attempts; do
    if [ "$allapot" = "ZÁROLVA" ]; then
        echo -e "  ${RED}[ZÁROLVA]${NC} $user  ($role)  — $attempts sikertelen kísérlet"
    else
        echo -e "  ${GREEN}[szabad ]${NC} $user  ($role)"
    fi
done
echo ""

# ── Felhasználónév bekérése ───────────────────────────────────────
USERNAME="${1:-}"
if [ -z "$USERNAME" ]; then
    read -rp "Felhasználónév: " USERNAME
fi
USERNAME="${USERNAME// /}"

# Létezik-e?
EXISTS=$(psql "$DB_URL" -t -A -c \
    "SELECT COUNT(*) FROM users WHERE username='$USERNAME'")
if [ "$EXISTS" = "0" ]; then
    echo -e "${RED}HIBA: '$USERNAME' felhasználó nem létezik.${NC}"
    exit 1
fi

# ── Zárolás törlése ───────────────────────────────────────────────
psql "$DB_URL" -c \
    "UPDATE users SET locked_until=NULL, attempt_count=0 WHERE username='$USERNAME'" \
    &>/dev/null
echo -e "${GREEN}  Zárolás törölve: $USERNAME${NC}"

# ── PIN visszaállítás (opcionális) ────────────────────────────────
NEW_PIN="${2:-}"

if [ -z "$NEW_PIN" ]; then
    echo ""
    read -rp "Új 6 számjegyű PIN (Enter = kihagyás): " NEW_PIN
fi

if [ -n "$NEW_PIN" ]; then
    if ! [[ "$NEW_PIN" =~ ^[0-9]{6}$ ]]; then
        echo -e "${RED}HIBA: A PIN pontosan 6 számjegy kell legyen.${NC}"
        exit 1
    fi

    # bcrypt hash Python-nal (WSL2-ben python3.11 van)
    HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw('$NEW_PIN'.encode(), bcrypt.gensalt()).decode())" 2>/dev/null) || {
        echo -e "${YELLOW}  bcrypt nem elérhető — csak zárolás törölve, PIN nem változott.${NC}"
        exit 0
    }

    psql "$DB_URL" -c \
        "UPDATE users SET pin_hash='$HASH' WHERE username='$USERNAME'" \
        &>/dev/null
    echo -e "${GREEN}  PIN visszaállítva: $USERNAME → $NEW_PIN${NC}"
    echo -e "${YELLOW}  Belépés után azonnal cseréld le!${NC}"
fi

echo ""
echo -e "${CYAN}${SEP}${NC}"
echo -e "${GREEN}  Kész. Belépés: http://localhost${NC}"
echo -e "${CYAN}${SEP}${NC}"
