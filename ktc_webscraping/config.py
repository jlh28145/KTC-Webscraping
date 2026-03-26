import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    db_path: Path
    database_url: str | None


def load_runtime_config() -> RuntimeConfig:
    database_url = os.getenv("KTC_DATABASE_URL") or None
    db_path = Path(os.getenv("KTC_DB_PATH", "db/ktc.db"))
    return RuntimeConfig(db_path=db_path, database_url=database_url)
