#!/usr/bin/env python3
"""
CRT DB Migráció v0.8 – LoRA jobs tábla
Futtatás: py -3.11 db_migrate_v08.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sqlalchemy import create_engine, text
from env_detect import get_db_url

DB_URL = get_db_url()
engine = create_engine(DB_URL)

STEPS = [
    (
        "lora_jobs tábla",
        """CREATE TABLE IF NOT EXISTS lora_jobs (
            id            SERIAL PRIMARY KEY,
            job_id        VARCHAR(64)   UNIQUE NOT NULL,
            status        VARCHAR(32)   NOT NULL DEFAULT 'pending',
            base_model    VARCHAR(128),
            examples      INTEGER,
            epochs        INTEGER,
            train_loss    FLOAT,
            adapter_path  VARCHAR(512),
            error_msg     TEXT,
            started_at    TIMESTAMP     DEFAULT NOW(),
            finished_at   TIMESTAMP,
            created_by    VARCHAR(128)
        )"""
    ),
    (
        "lora_jobs index (status)",
        "CREATE INDEX IF NOT EXISTS idx_lora_status ON lora_jobs(status)"
    ),
    (
        "lora_jobs index (started_at)",
        "CREATE INDEX IF NOT EXISTS idx_lora_ts ON lora_jobs(started_at)"
    ),
    (
        "system_config: lora_active_job_id",
        "INSERT INTO system_config (key, value) VALUES ('lora_active_job_id', '') "
        "ON CONFLICT (key) DO NOTHING"
    ),
    (
        "system_config: lora_adapter_path",
        "INSERT INTO system_config (key, value) VALUES ('lora_adapter_path', '') "
        "ON CONFLICT (key) DO NOTHING"
    ),
]


def main():
    print("═" * 52)
    print("  CRT Migráció v0.8 – LoRA Jobs tábla")
    print("═" * 52)
    try:
        with engine.begin() as conn:
            for i, (desc, sql) in enumerate(STEPS, 1):
                conn.execute(text(sql))
                print(f"  [{i:02d}/{len(STEPS)}] ✓ {desc}")
        print("\n✓ v0.8 migráció kész")
        print("  Következő lépés: py -3.11 -m uvicorn main:app --reload")
    except Exception as e:
        print(f"\n✗ Migráció hiba: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
