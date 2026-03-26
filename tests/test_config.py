from pathlib import Path

from ktc_webscraping.config import load_runtime_config


def test_load_runtime_config_uses_defaults(monkeypatch) -> None:
    monkeypatch.delenv("KTC_DB_PATH", raising=False)
    monkeypatch.delenv("KTC_DATABASE_URL", raising=False)

    config = load_runtime_config()

    assert config.db_path == Path("db/ktc.db")
    assert config.database_url is None


def test_load_runtime_config_reads_environment_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KTC_DB_PATH", str(tmp_path / "custom.db"))
    monkeypatch.setenv("KTC_DATABASE_URL", "sqlite:///tmp/test.db")

    config = load_runtime_config()

    assert config.db_path == tmp_path / "custom.db"
    assert config.database_url == "sqlite:///tmp/test.db"
