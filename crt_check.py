import subprocess, sys

def pip_list():
    r = subprocess.run(
        ["py", "-3.11", "-m", "pip", "list", "--format=columns"],
        capture_output=True, text=True, shell=True
    )
    out = {}
    for line in r.stdout.split("\n")[2:]:
        p = line.split()
        if len(p)>=2:
            out[p[0].lower().replace("-","_")] = p[1]
    return out

REQUIRED = {
    "fastapi":               "Web szerver",
    "uvicorn":               "ASGI szerver",
    "celery":                "Task queue",
    "redis":                 "Celery broker",
    "sqlalchemy":            "PostgreSQL ORM",
    "psycopg2_binary":       "PostgreSQL driver",
    "pydantic":              "JSON validáció",
    "alembic":               "DB migráció",
    "httpx":                 "Async HTTP",
    "python_dotenv":         "Env változók",
    "chromadb":              "Vektoros DB",
    "anthropic":             "Claude API",
    "google_generativeai":   "Gemini API",
    "sentence_transformers": "Embedding",
    "llama_cpp_python":      "Helyi béta motor 🦙",
    "torch":                 "ML alap",
    "openpyxl":              "Excel",
    "python_docx":           "Word",
    "pdfplumber":            "PDF olvasás",
    "pytesseract":           "OCR",
    "pillow":                "Képkezelés",
    "beautifulsoup4":        "Web scraping",
    "lxml":                  "XML parser",
    "playwright":            "Web automáció",
    "bcrypt":                "PIN hash",
    "cryptography":          "AES-256",
    "python_jose":           "JWT",
    "passlib":               "Jelszó kezelés",
    "weasyprint":            "PDF generálás",
    "reportlab":             "PDF alternatív",
    "jinja2":                "Sablonok",
    "ntplib":                "NTP szinkron",
    "requests":              "HTTP",
    "pandas":                "Adatkezelés",
    "numpy":                 "Számítás",
    "matplotlib":            "Grafikonok",
    "scikit_learn":          "ML statisztika",
}

inst = pip_list()
ok, missing = {}, {}
for pkg,desc in REQUIRED.items():
    if pkg in inst: ok[pkg] = (inst[pkg], desc)
    else: missing[pkg] = desc

print("\n╔══════════════════════════════════════════════════╗")
print("║   CRT – Python 3.11 Környezet állapot           ║")
print("╚══════════════════════════════════════════════════╝\n")

print(f"{'='*55}")
print(f"  ✅  MEGVAN ({len(ok)}/{len(REQUIRED)} csomag)")
print(f"{'='*55}")
for pkg,(ver,desc) in sorted(ok.items()):
    print(f"  ✓  {pkg:<30} {ver:<12} {desc}")

print(f"\n{'='*55}")
print(f"  ❌  HIÁNYZIK ({len(missing)} csomag)")
print(f"{'='*55}")
if missing:
    for pkg,desc in sorted(missing.items()):
        print(f"  ✗  {pkg:<30} {desc}")
    print(f"\n  📋 Telepítési parancs:")
    pkgs = " ".join(k.replace("_","-") for k in missing.keys())
    print(f"  py -3.11 -m pip install {pkgs}")
else:
    print("  🎉 Minden telepítve!")

print()
