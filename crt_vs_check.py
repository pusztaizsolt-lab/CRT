"""
CRT – Visual Studio Build Tools Komponens Ellenőrző és Telepítő
Futtasd: py -3.11 crt_vs_check.py
vagy:    python crt_vs_check.py

Megkeresi a gépen lévő VS telepítőt,
ellenőrzi a szükséges komponenseket,
és telepíti ami hiányzik.
"""
import os, sys, subprocess, json, urllib.request, tempfile

# ── SZÜKSÉGES KOMPONENSEK ─────────────────────────────────
REQUIRED_COMPONENTS = [
    # C++ alap (llama-cpp-python-hoz kötelező)
    "Microsoft.VisualStudio.Workload.NativeDesktop",
    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
    "Microsoft.VisualStudio.Component.Windows11SDK.22621",
    "Microsoft.VisualStudio.Component.VC.CMake.Project",
]

# ── VS TELEPÍTŐ HELYEK ────────────────────────────────────
VS_PATHS = [
    r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vs_installer.exe",
    r"C:\Program Files\Microsoft Visual Studio\Installer\vs_installer.exe",
    r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\devenv.exe",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\devenv.exe",
]

BUILD_TOOLS_URL = "https://aka.ms/vs/17/release/vs_buildtools.exe"

def step(msg):
    print(f"\n{'='*55}")
    print(f"  ▶  {msg}")
    print(f"{'='*55}")

def ok(msg):   print(f"  ✅  {msg}")
def warn(msg): print(f"  ⚠️   {msg}")
def err(msg):  print(f"  ❌  {msg}")
def info(msg): print(f"  ℹ️   {msg}")

# ── VS TELEPÍTŐ MEGKERESÉSE ───────────────────────────────
def find_vs_installer():
    for path in VS_PATHS:
        if os.path.exists(path):
            return path
    # Keresés C:\Program Files (x86)\Microsoft Visual Studio alatt
    base = r"C:\Program Files (x86)\Microsoft Visual Studio"
    if os.path.exists(base):
        for root, dirs, files in os.walk(base):
            for f in files:
                if f == "vs_installer.exe":
                    return os.path.join(root, f)
    return None

# ── TELEPÍTETT KOMPONENSEK LEKÉRDEZÉSE ────────────────────
def get_installed_components():
    installer = find_vs_installer()
    if not installer:
        return []
    try:
        r = subprocess.run(
            [installer, "export", "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(r.stdout)
        components = []
        for inst in data.get("instances", []):
            for comp in inst.get("packages", []):
                components.append(comp.get("id", ""))
        return components
    except:
        return []

# ── NMAKE ELLENŐRZÉS ──────────────────────────────────────
def check_nmake():
    paths = [
        r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Tools\MSVC",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
        r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC",
    ]
    for base in paths:
        if os.path.exists(base):
            for ver in os.listdir(base):
                nmake = os.path.join(base, ver, "bin", "Hostx64", "x64", "nmake.exe")
                if os.path.exists(nmake):
                    return nmake
    # where nmake paranccsal
    r = subprocess.run(["where", "nmake"], capture_output=True, text=True, shell=True)
    if r.returncode == 0:
        return r.stdout.strip()
    return None

# ── CL.EXE ELLENŐRZÉS ────────────────────────────────────
def check_cl():
    r = subprocess.run(["where", "cl"], capture_output=True, text=True, shell=True)
    if r.returncode == 0:
        return r.stdout.strip()
    return None

# ── CMAKE ELLENŐRZÉS ──────────────────────────────────────
def check_cmake():
    r = subprocess.run(["cmake", "--version"], capture_output=True, text=True, shell=True)
    if r.returncode == 0:
        return r.stdout.split("\n")[0]
    return None

# ── BUILD TOOLS LETÖLTÉS ──────────────────────────────────
def download_build_tools():
    print("\n  Letöltés folyamatban...")
    tmp = os.path.join(tempfile.gettempdir(), "vs_buildtools.exe")
    try:
        urllib.request.urlretrieve(
            BUILD_TOOLS_URL, tmp,
            reporthook=lambda b,bs,ts: print(
                f"  {min(100,int(b*bs/ts*100))}%", end="\r", flush=True
            ) if ts > 0 else None
        )
        print()
        return tmp
    except Exception as e:
        err(f"Letöltési hiba: {e}")
        return None

# ── KOMPONENS TELEPÍTÉS ───────────────────────────────────
def install_components(installer, missing):
    comp_args = []
    for comp in missing:
        comp_args.extend(["--add", comp])

    cmd = [
        installer,
        "modify",
        "--quiet",
        "--norestart",
    ] + comp_args

    info(f"Telepítési parancs: {' '.join(cmd[:6])}...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0

# ── FŐ PROGRAM ────────────────────────────────────────────
def main():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   CRT – Visual Studio Komponens Ellenőrző           ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Platform: Windows")
    print(f"  Python:   {sys.version.split()[0]}\n")

    # ── 1. FORDÍTÓK ELLENŐRZÉSE ───────────────────────────
    step("1. Fordítók ellenőrzése")

    nmake = check_nmake()
    cl    = check_cl()
    cmake = check_cmake()

    if nmake:
        ok(f"nmake.exe: {nmake[:60]}")
    else:
        err("nmake.exe: NEM TALÁLHATÓ")

    if cl:
        ok(f"cl.exe: {cl[:60]}")
    else:
        err("cl.exe: NEM TALÁLHATÓ")

    if cmake:
        ok(f"cmake: {cmake}")
    else:
        warn("cmake: nem található (de nem kritikus)")

    # ── 2. VS TELEPÍTŐ KERESÉS ────────────────────────────
    step("2. Visual Studio telepítő keresése")
    installer = find_vs_installer()

    if installer:
        ok(f"VS Installer: {installer}")
    else:
        warn("VS Installer nem található!")
        info("Letöltöm a Build Tools telepítőt...")

        ans = input("\n  Letöltsük a Build Tools-t? (i/n): ").strip().lower()
        if ans == "i":
            tmp = download_build_tools()
            if tmp:
                ok(f"Letöltve: {tmp}")
                print("\n  Telepítés indul – válaszd ki:")
                print("  ✅ Desktop development with C++")
                subprocess.Popen([tmp])
                print("\n  Telepítés után indítsd újra ezt a scriptet!")
            return
        else:
            info("Manuális letöltés:")
            info("https://visualstudio.microsoft.com/visual-cpp-build-tools/")
            return

    # ── 3. LLAMA-CPP-PYTHON TESZT ─────────────────────────
    step("3. llama-cpp-python telepíthetőség teszt")

    if nmake and cl:
        ok("Minden fordító megvan – llama-cpp-python telepíthető!")
        ans = input("\n  Telepítsük most? (i/n): ").strip().lower()
        if ans == "i":
            print("\n  Telepítés folyamatban – türelmesen várj...\n")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install",
                 "llama-cpp-python", "--prefer-binary"],
                text=True
            )
            if r.returncode == 0:
                ok("llama-cpp-python telepítve! 🦙")
            else:
                err("Telepítési hiba – próbáld Developer Command Prompt-ból!")
    else:
        warn("Fordítók hiányoznak – llama-cpp-python nem telepíthető így!")
        print()
        print("  Megoldás 1: Visual Studio Installer → Modify")
        print("  → ✅ Desktop development with C++")
        print()
        print("  Megoldás 2: Developer Command Prompt-ból futtasd:")
        print("  py -3.11 -m pip install llama-cpp-python --prefer-binary")

    # ── 4. ÖSSZEFOGLALÁS ──────────────────────────────────
    step("4. Összefoglalás")

    tabla = [
        ("nmake.exe",         "✅" if nmake  else "❌", "C++ fordítás"),
        ("cl.exe",            "✅" if cl     else "❌", "C++ kompiler"),
        ("cmake",             "✅" if cmake  else "⚠️",  "Build rendszer"),
        ("VS Installer",      "✅" if installer else "❌", "Komponens kezelő"),
    ]

    for nev, stat, leiras in tabla:
        print(f"  {stat}  {nev:<20} {leiras}")

    print()
    if nmake and cl:
        print("  🎉 Fordítói környezet KÉSZ!")
        print("  → llama-cpp-python telepíthető")
    else:
        print("  ⚠️  Telepítsd: Desktop development with C++")
        print("  → https://visualstudio.microsoft.com/visual-cpp-build-tools/")
    print()

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Ez a script csak Windows-on fut!")
        sys.exit(1)
    main()
