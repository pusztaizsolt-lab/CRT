"""
CRT Vision Motor v0.9 – LLaVA alapú rajz/kép elemzés
Modell: llava:7b (Ollama-n futtatva)
Használat: tervrajzok, fotók, képes PDF oldalak feldolgozása
"""
import base64, json, re, logging, os
import httpx
from sqlalchemy import text

log = logging.getLogger("CRT.vision")

_VISION_PROMPT = """Te egy magyar villamossági és építési anyag azonosító szakértő vagy.
Az alábbi kép egy tervrajzot, anyagjegyzéket vagy helyszíni fotót mutat.
Azonosítsd a látható termékeket, szerelvényeket, kábeleket és anyagokat.
Adj vissza KIZÁRÓLAG JSON array formában.

Válasz formátuma (CSAK JSON, semmi más):
[
  {{"name": "termék megnevezése", "manufacturer": "gyártó vagy null",
    "unit": "db/m/kg/stb", "category": "kategória magyarul",
    "confidence": 0.85, "location": "kép melyik részén látható"}},
  ...
]

Szabályok:
- Ha nem látható konkrét termék: confidence < 0.5
- unit: legyen szabványos (db, m, fm, kg, l)
- Ha bizonytalan: jelezd alacsony confidence értékkel
- Csak valóban látható elemeket sorolj fel
- Ha üres a kép vagy nem értelmezhető: adj vissza []"""


def _load_ollama_config(engine) -> tuple[str, str]:
    url   = "http://localhost:11434"
    model = "llava:7b"
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT key, value FROM system_config "
                "WHERE key IN ('ollama_url', 'vision_model')"
            )).fetchall()
            cfg = {r[0]: r[1] for r in rows}
            url   = cfg.get("ollama_url", url)
            model = cfg.get("vision_model", model)
    except Exception:
        pass
    return url, model


def _parse_json(raw: str) -> list:
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def analyze_image(image_bytes: bytes, mime: str, engine) -> dict:
    """
    Kép elemzése LLaVA-val.
    image_bytes: nyers képadat (PNG/JPEG/WebP)
    mime: 'image/png' | 'image/jpeg' | 'image/webp'
    Visszatér: {results, source, model, error?}
    """
    url, model = _load_ollama_config(engine)

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model":  model,
        "prompt": _VISION_PROMPT,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 1024},
    }

    try:
        resp = httpx.post(
            f"{url}/api/generate",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        raw     = resp.json().get("response", "")
        results = _parse_json(raw)
        log.info("Vision (%s): %d tétel azonosítva", model, len(results))
        return {"results": results, "source": "llava", "model": model}
    except Exception as e:
        log.error("Vision hiba: %s", e)
        return {"results": [], "source": "llava", "model": model, "error": str(e)}


def analyze_pdf_page(pdf_bytes: bytes, page_num: int, engine) -> dict:
    """
    PDF oldal renderelése és LLaVA-val elemzése.
    Csak képes/rajzos oldalaknál érdemes hívni.
    """
    try:
        import pdfplumber
        from PIL import Image
        import io
    except ImportError:
        return {"results": [], "error": "pdfplumber vagy Pillow hiányzik"}

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_num >= len(pdf.pages):
                return {"results": [], "error": f"Nincs {page_num}. oldal"}
            page = pdf.pages[page_num]
            img  = page.to_image(resolution=150).original
            buf  = io.BytesIO()
            if not isinstance(img, Image.Image):
                from PIL import Image as PILImage
                img = PILImage.fromarray(img)
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
    except Exception as e:
        return {"results": [], "error": f"PDF renderelési hiba: {e}"}

    return analyze_image(png_bytes, "image/png", engine)


def llava_available(ollama_url: str = "http://localhost:11434") -> bool:
    """LLaVA modell elérhető-e az Ollama-ban"""
    try:
        r = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        models = [m["name"] for m in r.json().get("models", [])]
        return any("llava" in m.lower() for m in models)
    except Exception:
        return False
