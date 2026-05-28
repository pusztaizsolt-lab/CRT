"""
CRT Ajánlatsegéd – Fejlesztői Környezet Ellenőrző és Telepítő
Futtasd: python crt_setup.py
"""
import subprocess, sys, os

REQUIRED = {
    "fastapi":               "Web szerver",
    "uvicorn":               "ASGI szerver",
    "celery":                "Task queue",
    "redis":                 "Celery broker",
    "sqlalchemy":            "PostgreSQL ORM",
    "psycopg2-binary":       "PostgreSQL driver",
    "pydantic":              "JSON validáció",
    "alembic":               "DB migráció",
    "httpx":                 "Async HTTP",
    "python-dotenv":         "Env változók",
    "chromadb":              "Vektoros DB",
    "anthropic":             "Claude API",
    "google-generativeai":   "Gemini API",
    "sentence-transformers": "Embedding",
    "llama-cpp-python":      "Helyi béta motor",
    "openpyxl":              "Excel",
    "python-docx":           "Word",
    "pdfplumber":            "PDF olvasás",
    "pytesseract":           "OCR",
    "Pillow":                "Képkezelés",
    "beautifulsoup4":        "Web scraping",
    "lxml":                  "XML parser",
    "playwright":            "Web automáció",
    "bcrypt":                "PIN hash",
    "cryptography":          "AES-256",
    "python-jose":           "JWT",
    "passlib":               "Jelszó kezelés",
    "weasyprint":            "PDF generálás",
    "reportlab":             "PDF alternatív",
    "jinja2":                "Sablonok",
    "ntplib":                "NTP szinkron",
    "requests":              "HTTP",
    "pandas":                "Adatkezelés",
    "numpy":                 "Számítás",
    "matplotlib":            "Grafikonok",
    "scikit-learn":          "ML statisztika",
}

def pip(args):
    return subprocess.run([sys.executable,"-m","pip"]+args, capture_output=True, text=True)

def installed():
    r = pip(["list","--format=columns"])
    out = {}
    for line in r.stdout.split("\n")[2:]:
        p = line.split()
        if len(p)>=2: out[p[0].lower().replace("-","_")] = p[1]
    return out

def check():
    inst = installed()
    ok, missing = {}, {}
    for pkg,desc in REQUIRED.items():
        k = pkg.lower().replace("-","_")
        if k in inst: ok[pkg] = (inst[k], desc)
        else: missing[pkg] = desc
    return ok, missing

def install(missing):
    print("\n📦 Telepítés indul...\n")
    failed = []
    for i,(pkg,desc) in enumerate(missing.items(),1):
        print(f"  [{i}/{len(missing)}] {pkg}...", end=" ", flush=True)
        r = pip(["install", pkg, "--quiet"])
        if r.returncode == 0: print("✅")
        else:
            r2 = pip(["install", pkg, "--quiet", "--break-system-packages"])
            if r2.returncode == 0: print("✅")
            else: print("❌ HIBA"); failed.append(pkg)
    return failed

def main():
    os.system("cls" if os.name=="nt" else "clear")
    print("╔══════════════════════════════════════════╗")
    print("║  CRT Ajánlatsegéd – Környezet ellenőrző  ║")
    print("╚══════════════════════════════════════════╝")
    print(f"\n🐍 Python: {sys.version.split()[0]}  |  {sys.executable}\n")

    print("🔍 Lekérdezés...\n")
    ok, missing = check()

    print(f"{'='*50}")
    print(f"  ✅  MEGVAN ({len(ok)} csomag)")
    print(f"{'='*50}")
    for pkg,(ver,desc) in sorted(ok.items()):
        print(f"  ✓  {pkg:<28} {ver:<10} {desc}")

    print(f"\n{'='*50}")
    print(f"  ❌  HIÁNYZIK ({len(missing)} csomag)")
    print(f"{'='*50}")
    for pkg,desc in sorted(missing.items()):
        print(f"  ✗  {pkg:<28} {desc}")

    if not missing:
        print("\n🎉 Minden telepítve! Fejlesztés mehet.\n")
        return

    print(f"\n{'='*50}")
    ans = input("  Telepítsük a hiányzókat most? (i/n): ").strip().lower()
    if ans == "i":
        failed = install(missing)
        print(f"\n{'='*50}")
        if not failed:
            print("  🎉 Minden sikeresen telepítve!\n")
        else:
            print(f"  ⚠️  Ezek kézzel kellenek: {', '.join(failed)}\n")
            print("  Torch (CPU):")
            print("  pip install torch --index-url https://download.pytorch.org/whl/cpu\n")
    else:
        pkgs = " ".join(missing.keys())
        print(f"\n  📋 Parancs ha később akarod:")
        print(f"  pip install {pkgs}\n")

if __name__ == "__main__":
    main()
