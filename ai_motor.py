"""
CRT AI Motor v1.0 – Claude → LoRA → Ollama fallback
Prioritás: Claude API → LoRA fine-tuned (ha aktiválva) → Ollama helyi LLM
"""
import json, re, logging, os
import httpx
from sqlalchemy import text

log = logging.getLogger("CRT.ai")

# LoRA pipeline cache – betöltve marad a memóriában (ne töltsük újra minden kérésnél)
_lora_pipeline = None
_lora_adapter_path = None


def clear_lora_cache():
    """Aktiválás/deaktiválásnál az ai_motor cache törlése"""
    global _lora_pipeline, _lora_adapter_path
    _lora_pipeline     = None
    _lora_adapter_path = None

_PROMPT = """Te egy magyar villamossági és építési anyag azonosító szakértő vagy.
Az alábbi sorokat egy ajánlatkérő vagy szállítói dokumentumból olvastuk ki.
Azonosítsd az egyes tételeket és add vissza KIZÁRÓLAG JSON array formában.

Sorok:
{items_text}

Válasz formátuma (CSAK JSON, semmi más):
[
  {{"index": 1, "name": "tisztított megnevezés", "manufacturer": "gyártó vagy null", "unit": "db/m/kg/óra/stb", "category": "javasolt kategória magyarul", "confidence": 0.95}},
  ...
]

Szabályok:
- confidence: 0.0–1.0 (mennyire biztos az azonosítás)
- Ha bizonytalan (pl. rövidítés, hiányos adat): confidence < 0.55
- unit: legyen szabványos (db, m, fm, kg, l, óra, nap, csomag)
- category: legyen rövid és logikus (pl. Kábelek, Szerelvények, Munka, Szoftver)
- Ha az azonosítás egyáltalán nem lehetséges: confidence: 0.1"""


def _parse_json(raw: str) -> list:
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not m:
        raise ValueError("Nincs JSON array a válaszban")
    return json.loads(m.group(0))


def _load_config(engine) -> dict:
    cfg = {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT key, value FROM system_config WHERE key IN ("
                "'claude_api_key','claude_model','ollama_url','ollama_model',"
                "'ai_conf_high','ai_conf_low',"
                "'lora_active_job_id','lora_adapter_path')"
            )).fetchall()
            for r in rows:
                cfg[r[0]] = r[1]
    except Exception:
        pass
    return cfg


def _with_claude(items: list, api_key: str, model: str) -> dict:
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    items_text = "\n".join(f"{i+1}. {it}" for i, it in enumerate(items))
    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": _PROMPT.format(items_text=items_text)}]
    )
    results = _parse_json(resp.content[0].text)
    tokens  = resp.usage.input_tokens + resp.usage.output_tokens
    return {"results": results, "tokens_used": tokens, "source": "claude"}


def _with_lora(items: list, adapter_path: str) -> dict:
    """LoRA fine-tuned modell HuggingFace pipeline-on át"""
    global _lora_pipeline, _lora_adapter_path
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    from peft import PeftModel

    if _lora_pipeline is None or _lora_adapter_path != adapter_path:
        log.info("LoRA modell betöltése: %s", adapter_path)
        adapter_cfg_path = os.path.join(adapter_path, "adapter_config.json")
        with open(adapter_cfg_path, encoding="utf-8") as f:
            base_model = json.load(f).get("base_model_name_or_path", "")
        if not base_model:
            raise ValueError("adapter_config.json nem tartalmaz base_model_name_or_path")

        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=True)
        base = AutoModelForCausalLM.from_pretrained(
            base_model, torch_dtype=dtype, trust_remote_code=True,
            device_map="auto" if torch.cuda.is_available() else "cpu",
        )
        merged = PeftModel.from_pretrained(base, adapter_path)
        _lora_pipeline = pipeline(
            "text-generation", model=merged, tokenizer=tokenizer,
            max_new_tokens=512, do_sample=False,
        )
        _lora_adapter_path = adapter_path
        log.info("LoRA pipeline kész (%s)", base_model)

    results = []
    for i, item in enumerate(items, 1):
        prompt = (
            "Te egy magyar villamossági és építési anyag azonosító vagy.\n"
            f"Azonosítsd ezt a tételt: {item}"
        )
        out = _lora_pipeline(prompt)[0]["generated_text"]
        answer = out[len(prompt):].strip()
        try:
            parsed = json.loads(answer)
            parsed["index"] = i
            results.append(parsed)
        except Exception:
            results.append({
                "index": i, "name": item,
                "manufacturer": None, "unit": "db",
                "category": "", "confidence": 0.4,
            })
    return {"results": results, "tokens_used": 0, "source": "lora"}


def _with_ollama(items: list, url: str, model: str) -> dict:
    items_text = "\n".join(f"{i+1}. {it}" for i, it in enumerate(items))
    payload = {
        "model":   model,
        "messages": [{"role": "user", "content": _PROMPT.format(items_text=items_text)}],
        "stream":  False,
        "options": {"temperature": 0.1, "num_predict": 2048},
    }
    resp = httpx.post(f"{url}/api/chat", json=payload, timeout=120.0)
    resp.raise_for_status()
    raw     = resp.json()["message"]["content"]
    results = _parse_json(raw)
    return {"results": results, "tokens_used": 0, "source": "ollama"}


def identify(items: list, engine) -> dict:
    """
    Fő azonosítási pipeline:
      1. Claude API       – ha api_key elérhető (DB vagy env)
      2. LoRA fine-tuned  – ha lora_active_job_id be van állítva
      3. Ollama           – helyi LLM fallback
    Mindhárom ugyanazt a JSON formátumot adja vissza + 'source' mező.
    """
    if not items:
        return {"results": [], "tokens_used": 0, "source": "none"}

    cfg          = _load_config(engine)
    api_key      = cfg.get("claude_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    claude_model = cfg.get("claude_model", "claude-sonnet-4-6")
    ollama_url   = (
        cfg.get("ollama_url") or os.environ.get("CRT_OLLAMA_URL", "http://localhost:11434")
    )
    ollama_model  = cfg.get("ollama_model", "llama3:8b")
    lora_job_id   = cfg.get("lora_active_job_id", "")
    lora_adapter  = cfg.get("lora_adapter_path", "")

    # 1. Claude
    if api_key:
        try:
            result = _with_claude(items, api_key, claude_model)
            log.info(
                "AI (Claude/%s): %d tétel, %d token",
                claude_model, len(items), result["tokens_used"],
            )
            return result
        except Exception as e:
            log.warning("Claude API hiba (%s) – következő fallback", e)

    # 2. LoRA fine-tuned
    if lora_job_id and lora_adapter and os.path.isdir(lora_adapter):
        try:
            result = _with_lora(items, lora_adapter)
            log.info("AI (LoRA/%s): %d tétel", lora_job_id, len(items))
            return result
        except Exception as e:
            log.warning("LoRA hiba (%s) – Ollama próbálkozás", e)

    # 3. Ollama
    try:
        result = _with_ollama(items, ollama_url, ollama_model)
        log.info("AI (Ollama/%s): %d tétel", ollama_model, len(items))
        return result
    except Exception as e:
        log.error("Ollama is sikertelen: %s", e)
        raise RuntimeError(
            f"Minden AI motor elérhetetlen. Claude: nincs kulcs. "
            f"LoRA: {'nincs aktiválva' if not lora_job_id else 'hiba'}. "
            f"Ollama ({ollama_url}): {e}"
        ) from e


def ollama_status(url: str = "http://localhost:11434") -> dict:
    """Ollama elérhetőség ellenőrzés"""
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5.0)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"ok": True, "models": models, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}
