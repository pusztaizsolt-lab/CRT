"""
env_detect.py – CRT platform detektor és runtime könyvtárkezelő

Három futási mód:
  windows  – natív Windows (Python 3.11 on Win10/11)
  wsl2     – Windows Subsystem for Linux 2 (Ubuntu 22.04 under Windows)
  linux    – natív Linux gép (bare metal / VM)

Minden platformon a CRT_ROOT (a fájl szülőkönyvtára) az egységes gyökér.
A szükséges alkönyvtárakat ensure_runtime_dirs() hozza létre induláskor.
"""

import sys
import os
import platform
import pathlib
import json
import time
import logging

log = logging.getLogger("crt.env")

# ── PLATFORM DETEKCIÓ ──────────────────────────────────────────────────────────

def detect_platform() -> str:
    """
    Visszatér: 'windows' | 'wsl2' | 'linux'

    WSL2 detektálás: /proc/version tartalmaz 'microsoft' vagy 'WSL' stringet.
    Nyers Linux: /proc/version létezik, de nincs benne microsoft.
    """
    if sys.platform == "win32":
        return "windows"
    try:
        proc_ver = pathlib.Path("/proc/version").read_text(errors="replace").lower()
        if "microsoft" in proc_ver or "wsl" in proc_ver:
            return "wsl2"
    except OSError:
        pass
    return "linux"


def get_platform_info() -> dict:
    """Részletes platform információ — health endpoint és logok számára."""
    plat = detect_platform()
    info = {
        "platform":    plat,
        "system":      platform.system(),
        "release":     platform.release(),
        "machine":     platform.machine(),
        "python":      platform.python_version(),
        "pid":         os.getpid(),
    }
    if plat in ("wsl2", "linux"):
        try:
            info["hostname"] = pathlib.Path("/etc/hostname").read_text().strip()
        except OSError:
            info["hostname"] = platform.node()
        try:
            info["distro"] = pathlib.Path("/etc/os-release").read_text()
            for line in info["distro"].splitlines():
                if line.startswith("PRETTY_NAME="):
                    info["distro"] = line.split("=", 1)[1].strip('"')
                    break
        except OSError:
            info["distro"] = "unknown"
        if plat == "wsl2":
            try:
                # WSL2 Windows host verzió
                interop = pathlib.Path("/proc/sys/fs/binfmt_misc/WSLInterop")
                info["wsl_interop"] = interop.exists()
            except Exception:
                pass
    else:
        info["hostname"] = platform.node()
    return info


# ── ÚTVONALAK ─────────────────────────────────────────────────────────────────

def get_crt_root() -> pathlib.Path:
    """CRT gyökérkönyvtár — mindig a env_detect.py szülője."""
    return pathlib.Path(__file__).parent.resolve()


def get_paths(root: pathlib.Path | None = None) -> dict:
    """
    Platform-független útvonaltérkép.
    Minden path a CRT_ROOT-hoz képest relatív, de abszolút Path objektum.
    """
    r = root or get_crt_root()
    return {
        "root":          r,
        "logs":          r / "logs",
        "logs_backend":  r / "logs" / "backend",
        "logs_nginx":    r / "logs" / "nginx",
        "logs_system":   r / "logs" / "system",
        "run":           r / "run",
        "metrics":       r / "metrics",
        "uploads":       r / "uploads",
        "exports":       r / "exports",
        "vectors":       r / "vectors" / "chroma",
        "models_lora":   r / "models" / "lora",
        "models_ollama": r / "models" / "ollama",
        "db_data":       r / "db_data",
        "db_backups":    r / "db_data" / "backups",
        "setup":         r / "_setup",
        "ui":            r / "ui",
    }


def ensure_runtime_dirs(root: pathlib.Path | None = None) -> list[str]:
    """
    Létrehozza az összes futáshoz szükséges alkönyvtárat.
    Visszatér a létrehozott könyvtárak listájával (csak újak).
    """
    paths = get_paths(root)
    runtime_keys = [
        "logs_backend", "logs_nginx", "logs_system",
        "run", "metrics",
        "uploads", "exports",
        "vectors", "models_lora", "models_ollama",
        "db_backups",
    ]
    created = []
    for key in runtime_keys:
        p = paths[key]
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(str(p))
            log.debug(f"Könyvtár létrehozva: {p}")
    return created


# ── SERVICE KEZELŐ PARANCSOK ──────────────────────────────────────────────────

def get_service_commands() -> dict:
    """
    Platform-specifikus service kezelő parancsok.

    WSL2: alapértelmezetten nincs systemd → 'service' parancs
    Bare Linux: systemd → 'systemctl' parancs
    Windows: natív (PostgreSQL portable, subprocess)
    """
    plat = detect_platform()

    if plat == "windows":
        return {
            "type":       "windows",
            "pg_start":   None,   # pg_ctl.exe-n keresztül
            "pg_stop":    None,
            "nginx_start": None,
            "nginx_stop":  None,
            "has_systemd": False,
        }

    # Linux (WSL2 vagy natív) — systemd detektálás
    has_systemd = pathlib.Path("/run/systemd/private").exists() or \
                  pathlib.Path("/sys/fs/cgroup/systemd").exists() or \
                  _check_systemctl()

    if has_systemd:
        return {
            "type":        "systemd",
            "pg_start":    "systemctl start postgresql",
            "pg_stop":     "systemctl stop postgresql",
            "pg_status":   "systemctl is-active postgresql",
            "nginx_start": "systemctl start nginx",
            "nginx_stop":  "systemctl stop nginx",
            "has_systemd": True,
        }
    else:
        return {
            "type":        "sysv",
            "pg_start":    "service postgresql start",
            "pg_stop":     "service postgresql stop",
            "pg_status":   "service postgresql status",
            "nginx_start": "service nginx start",
            "nginx_stop":  "service nginx stop",
            "has_systemd": False,
        }


def _check_systemctl() -> bool:
    """Megpróbálja meghívni a systemctl-t — sikeres → systemd fut."""
    import subprocess
    try:
        r = subprocess.run(
            ["systemctl", "is-system-running"],
            capture_output=True, timeout=2
        )
        return r.returncode in (0, 1)   # 0=running, 1=degraded — mindkettő OK
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── RUNTIME STÁTUSZ FÁJL ──────────────────────────────────────────────────────

def write_runtime_status(extra: dict | None = None):
    """
    Futáskor frissíti a metrics/runtime.json fájlt.
    Az API health endpoint és a diagnosztikai felület olvassa.
    """
    root = get_crt_root()
    metrics_dir = root / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "started_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pid":         os.getpid(),
        **get_platform_info(),
        "service_mgr": get_service_commands()["type"],
    }
    if extra:
        status.update(extra)
    out = metrics_dir / "runtime.json"
    out.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    return status


def read_runtime_status() -> dict | None:
    """Visszaolvassa a metrics/runtime.json tartalmát, vagy None ha nem létezik."""
    p = get_crt_root() / "metrics" / "runtime.json"
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ── PID FÁJL ──────────────────────────────────────────────────────────────────

def write_pid():
    """run/crt.pid fájlba írja az aktuális PID-et."""
    pid_path = get_crt_root() / "run" / "crt.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))


def clear_pid():
    """Törli a run/crt.pid fájlt leálláskor."""
    pid_path = get_crt_root() / "run" / "crt.pid"
    try:
        pid_path.unlink(missing_ok=True)
    except OSError:
        pass


# ── QUICK INFO (CLI / log) ─────────────────────────────────────────────────────

def print_env_summary():
    """Induláskor a logba kerülő összefoglaló sor."""
    info = get_platform_info()
    svc  = get_service_commands()
    plat_label = {
        "windows": "Windows natív",
        "wsl2":    "WSL2 Ubuntu",
        "linux":   "Linux natív",
    }.get(info["platform"], info["platform"])
    print(
        f"[CRT env] {plat_label} | "
        f"{info.get('distro', info['system'])} | "
        f"Python {info['python']} | "
        f"service: {svc['type']} | "
        f"PID: {info['pid']}"
    )


# ── KONFIGURÁCIÓS SEGÉDFÜGGVÉNYEK ────────────────────────────────────────────

def get_db_url() -> str:
    """
    PostgreSQL kapcsolat URL.
    Prioritás: CRT_DB_URL env var → platform-detektált default.
    WSL2 / Linux: port 5432  |  Windows natív: port 5433
    """
    url = os.environ.get("CRT_DB_URL")
    if url:
        return url
    port = "5432" if detect_platform() in ("wsl2", "linux") else "5433"
    return f"postgresql://crt_user:crt2026@localhost:{port}/crt"


def get_jwt_secret() -> str:
    """JWT aláíró kulcs. Éles telepítés előtt kötelező a CRT_JWT_SECRET env var!"""
    secret = os.environ.get("CRT_JWT_SECRET", "crt_dev_secret_CHANGE_IN_PRODUCTION")
    if secret == "crt_dev_secret_CHANGE_IN_PRODUCTION":
        log.warning("FIGYELEM: Fejlesztési JWT secret van használatban! "
                    "Éles rendszeren állítsd be a CRT_JWT_SECRET env változót.")
    return secret


def get_encrypt_key() -> str:
    """Web scraper AES kulcs. Éles telepítés előtt kötelező a CRT_ENCRYPT_KEY env var!"""
    key = os.environ.get("CRT_ENCRYPT_KEY", "crt_dev_key_CHANGE_IN_PRODUCTION")
    if key == "crt_dev_key_CHANGE_IN_PRODUCTION":
        log.warning("FIGYELEM: Fejlesztési titkosítási kulcs van használatban! "
                    "Éles rendszeren állítsd be a CRT_ENCRYPT_KEY env változót.")
    return key


# ── ÖNÁLLÓ FUTTATÁS (diagnosztika) ────────────────────────────────────────────

if __name__ == "__main__":
    import pprint
    print("=== CRT Platform Detektor ===")
    print_env_summary()
    print()
    print("Platform részletek:")
    pprint.pprint(get_platform_info())
    print()
    print("Service kezelő:")
    pprint.pprint(get_service_commands())
    print()
    print("Útvonalak:")
    for k, v in get_paths().items():
        exists = "OK" if v.exists() else "HIANY"
        print(f"  [{exists}] {k:15s} {v}")
    print()
    created = ensure_runtime_dirs()
    if created:
        print(f"Létrehozva ({len(created)} könyvtár):")
        for c in created:
            print(f"  + {c}")
    else:
        print("Minden könyvtár már létezik.")
