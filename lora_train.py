#!/usr/bin/env python3
"""
CRT LoRA Finomhangolás – v1.0
Tanítóadat: golden_examples tábla → LoRA adapter
Futtatás: python3.11 lora_train.py [--job-id ...] [--epochs 3] [--hf-model ...]
"""
import argparse, json, logging, os, sys, time
from datetime import datetime
from pathlib import Path
from env_detect import get_db_url

log = logging.getLogger("CRT.lora")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()],
)

DB_URL   = get_db_url()
LORA_DIR = os.environ.get("CRT_LORA_DIR", "models/lora")


# ── SEGÉDFÜGGVÉNYEK ────────────────────────────────────────────

def write_status(status_path: Path, **data):
    status_path.write_text(
        json.dumps({"updated": datetime.now().isoformat(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_examples(db_url: str, min_count: int) -> list:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT raw_text, clean_name, manufacturer, category, unit "
            "FROM golden_examples "
            "WHERE clean_name IS NOT NULL AND clean_name != '' "
            "ORDER BY created_at"
        )).fetchall()
    examples = [
        {"raw": r[0], "name": r[1], "mfr": r[2] or "", "cat": r[3] or "", "unit": r[4] or "db"}
        for r in rows
    ]
    if len(examples) < min_count:
        raise ValueError(f"Kevés tanítóadat: {len(examples)} < {min_count} szükséges")
    return examples


def format_texts(examples: list, tokenizer) -> list:
    """golden példák → chat template szövegek SFTTrainer-hez"""
    texts = []
    for ex in examples:
        messages = [
            {
                "role": "user",
                "content": (
                    "Te egy magyar villamossági és építési anyag azonosító vagy.\n"
                    f"Azonosítsd ezt a tételt: {ex['raw']}"
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "name":         ex["name"],
                        "manufacturer": ex["mfr"],
                        "category":     ex["cat"],
                        "unit":         ex["unit"],
                        "confidence":   1.0,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
        except Exception:
            # fallback ha az adott tokenizer nem ismeri a chat template-et
            text = (
                f"### User:\n{messages[0]['content']}\n"
                f"### Assistant:\n{messages[1]['content']}"
            )
        texts.append(text)
    return texts


# ── TRÉNING ────────────────────────────────────────────────────

def train(args) -> tuple:
    """Visszatér: (train_loss: float|None, adapter_path: str)"""
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from trl import SFTTrainer
    from datasets import Dataset

    # --- Elérési utak ---
    out_dir     = Path(args.output_dir) / args.job_id
    adapter_dir = out_dir / "adapter"
    ckpt_dir    = out_dir / "checkpoints"
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / "status.json"

    write_status(status_path, status="init", job_id=args.job_id)

    # --- GPU detektálás ---
    has_gpu = torch.cuda.is_available()
    if has_gpu:
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb  = torch.cuda.get_device_properties(0).total_memory / 1e9
        log.info("GPU: %s  VRAM: %.1f GB", gpu_name, vram_gb)
    else:
        log.info("GPU nem elérhető – CPU módban fut (lassabb)")

    # --- Alapmodell kiválasztás ---
    if args.hf_model:
        base_model = args.hf_model
    elif has_gpu:
        # Phi-3-mini: nyílt, nincs HF auth, 3.8B, kiváló instruction following
        base_model = "microsoft/Phi-3-mini-4k-instruct"
    else:
        # TinyLlama: CPU-n is kezelhető, 1.1B
        base_model = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

    log.info("Alapmodell: %s | GPU: %s", base_model, has_gpu)
    write_status(
        status_path,
        status="loading_model",
        base_model=base_model,
        has_gpu=has_gpu,
        job_id=args.job_id,
    )

    # --- Tanítóadatok ---
    log.info("Golden examples betöltése...")
    examples = fetch_examples(args.db_url, args.min_examples)
    log.info("%d tanítóadat betöltve", len(examples))
    write_status(
        status_path,
        status="preparing",
        base_model=base_model,
        examples=len(examples),
        job_id=args.job_id,
    )

    # --- Tokenizer ---
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    texts   = format_texts(examples, tokenizer)
    dataset = Dataset.from_dict({"text": texts})
    log.info("Dataset: %d sor formázva", len(dataset))

    # --- Modell betöltés ---
    if has_gpu:
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=bnb_cfg,
            device_map="auto",
            trust_remote_code=True,
        )
        model = prepare_model_for_kbit_training(model)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            device_map="cpu",
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )

    # --- LoRA target modulok (modell-specifikus) ---
    bm = base_model.lower()
    if "phi" in bm:
        target_modules = ["q_proj", "v_proj", "k_proj", "o_proj",
                          "gate_up_proj", "down_proj"]
    elif any(x in bm for x in ("llama", "tinyllama", "mistral")):
        target_modules = ["q_proj", "v_proj", "k_proj", "o_proj"]
    else:
        target_modules = ["q_proj", "v_proj"]

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=target_modules,
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # --- TrainingArguments ---
    train_args = TrainingArguments(
        output_dir=str(ckpt_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=2 if has_gpu else 1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=has_gpu,
        logging_steps=5,
        save_strategy="epoch",
        report_to="none",
        dataloader_pin_memory=has_gpu,
        remove_unused_columns=False,
    )

    write_status(
        status_path,
        status="training",
        base_model=base_model,
        examples=len(examples),
        epochs=args.epochs,
        job_id=args.job_id,
    )
    log.info("Tréning indul: %d epoch, %d példa", args.epochs, len(examples))
    t0 = time.time()

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=train_args,
        dataset_text_field="text",
        max_seq_length=512,
    )
    trainer.train()

    elapsed = int(time.time() - t0)
    log.info("Tréning kész: %.1f perc", elapsed / 60)

    # --- Adapter mentés ---
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    log.info("LoRA adapter mentve: %s", adapter_dir)

    # --- Végső loss ---
    train_loss = None
    if trainer.state.log_history:
        losses = [h["loss"] for h in trainer.state.log_history if "loss" in h]
        if losses:
            train_loss = round(losses[-1], 4)

    write_status(
        status_path,
        status="done",
        job_id=args.job_id,
        base_model=base_model,
        examples=len(examples),
        epochs=args.epochs,
        train_loss=train_loss,
        elapsed_sec=elapsed,
        adapter_path=str(adapter_dir.resolve()),
    )
    log.info("LoRA pipeline kész | Loss: %s | Adapter: %s", train_loss, adapter_dir)
    return train_loss, str(adapter_dir.resolve())


# ── DB FRISSÍTÉS ───────────────────────────────────────────────

def update_db(args, train_loss, adapter_path, error_msg=None):
    from sqlalchemy import create_engine, text
    try:
        engine = create_engine(args.db_url)
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE lora_jobs SET "
                "status = :status, train_loss = :loss, adapter_path = :path, "
                "finished_at = NOW(), error_msg = :err "
                "WHERE job_id = :jid"
            ), {
                "status": "error" if error_msg else "done",
                "loss":   train_loss,
                "path":   adapter_path,
                "err":    error_msg,
                "jid":    args.job_id,
            })
    except Exception as e:
        log.warning("DB frissítés sikertelen: %s", e)


# ── MAIN ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CRT LoRA finomhangolás")
    parser.add_argument("--job-id",       default=f"lora_{int(time.time())}")
    parser.add_argument("--db-url",       default=DB_URL)
    parser.add_argument("--hf-model",     default="",
                        help="HuggingFace modell ID (pl. microsoft/Phi-3-mini-4k-instruct)")
    parser.add_argument("--output-dir",   default=LORA_DIR)
    parser.add_argument("--epochs",       type=int, default=3)
    parser.add_argument("--lora-r",       type=int, default=16)
    parser.add_argument("--lora-alpha",   type=int, default=32)
    parser.add_argument("--min-examples", type=int, default=10)
    args = parser.parse_args()

    train_loss, adapter_path, error = None, None, None
    try:
        train_loss, adapter_path = train(args)
    except Exception as e:
        error = str(e)
        log.error("Tréning hiba: %s", e)
        out_dir = Path(args.output_dir) / args.job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        write_status(
            out_dir / "status.json",
            status="error",
            job_id=args.job_id,
            error=error,
        )

    update_db(args, train_loss, adapter_path, error)
    sys.exit(1 if error else 0)


if __name__ == "__main__":
    main()
