import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path("db/ktc.db")
DEFAULT_PAGE_COUNT = 10
DEFAULT_RETRY_ATTEMPTS = 2


@dataclass(frozen=True)
class RuntimeConfig:
    """Environment-driven runtime defaults shared by the CLI."""

    db_path: Path
    database_url: str | None
    page_count: int
    retry_attempts: int


def _int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name) or str(default)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


def load_runtime_config() -> RuntimeConfig:
    """Load runtime defaults from the current shell environment.

    Called when the CLI runs rather than at import time, so environment
    changes (and test monkeypatching) are always picked up.
    """

    return RuntimeConfig(
        db_path=Path(os.getenv("KTC_DB_PATH") or DEFAULT_DB_PATH),
        database_url=os.getenv("KTC_DATABASE_URL") or None,
        page_count=_int_from_env("KTC_PAGE_COUNT", DEFAULT_PAGE_COUNT),
        retry_attempts=_int_from_env("KTC_RETRY_ATTEMPTS", DEFAULT_RETRY_ATTEMPTS),
    )
