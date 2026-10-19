from pathlib import Path

import pytest

from ktc_webscraping.config import (
    DEFAULT_DB_PATH,
    DEFAULT_PAGE_COUNT,
    DEFAULT_RETRY_ATTEMPTS,
    load_runtime_config,
)

KTC_ENV_VARS = ("KTC_DB_PATH", "KTC_DATABASE_URL", "KTC_PAGE_COUNT", "KTC_RETRY_ATTEMPTS")


def test_load_runtime_config_uses_defaults(monkeypatch) -> None:
    for name in KTC_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    config = load_runtime_config()

    assert config.db_path == DEFAULT_DB_PATH
    assert config.database_url is None
    assert config.page_count == DEFAULT_PAGE_COUNT
    assert config.retry_attempts == DEFAULT_RETRY_ATTEMPTS


def test_load_runtime_config_treats_blank_values_as_unset(monkeypatch) -> None:
    for name in KTC_ENV_VARS:
        monkeypatch.setenv(name, "")

    config = load_runtime_config()

    assert config.db_path == DEFAULT_DB_PATH
    assert config.database_url is None
    assert config.page_count == DEFAULT_PAGE_COUNT


def test_load_runtime_config_reads_environment_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KTC_DB_PATH", str(tmp_path / "custom.db"))
    monkeypatch.setenv("KTC_DATABASE_URL", "sqlite:///tmp/test.db")
    monkeypatch.setenv("KTC_PAGE_COUNT", "4")
    monkeypatch.setenv("KTC_RETRY_ATTEMPTS", "1")

    config = load_runtime_config()

    assert config.db_path == tmp_path / "custom.db"
    assert config.database_url == "sqlite:///tmp/test.db"
    assert config.page_count == 4
    assert config.retry_attempts == 1


def test_load_runtime_config_rejects_non_integer_page_count(monkeypatch) -> None:
    monkeypatch.setenv("KTC_PAGE_COUNT", "ten")

    with pytest.raises(ValueError, match="KTC_PAGE_COUNT must be an integer"):
        load_runtime_config()
