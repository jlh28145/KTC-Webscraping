import os
from pathlib import Path

import pytest

from ktc_webscraping import cli
from ktc_webscraping.models import PlayerRecord
from src import scraper as legacy_scraper


def test_build_parser_uses_expected_defaults() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["scrape"])

    assert args.command == "scrape"
    assert args.page_count == cli.DEFAULT_PAGE_COUNT
    assert args.db_path == cli.DEFAULT_DB_PATH
    assert args.base_url == cli.DEFAULT_BASE_URL
    assert args.min_rows_per_page == cli.DEFAULT_MIN_ROWS_PER_PAGE
    assert args.retry_attempts == 2
    assert args.headed is False


def test_build_config_maps_args_into_scrape_config(tmp_path: Path) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "scrape",
            "--page-count",
            "3",
            "--db-path",
            str(tmp_path / "custom.db"),
            "--base-url",
            "https://example.com?page={page}",
            "--min-rows-per-page",
            "25",
            "--retry-attempts",
            "4",
            "--headed",
        ]
    )

    config = cli.build_config(args)

    assert config.page_count == 3
    assert config.db_path == tmp_path / "custom.db"
    assert config.base_url == "https://example.com?page={page}"
    assert config.min_rows_per_page == 25
    assert config.retry_attempts == 4


def test_parser_rejects_non_positive_page_count() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["scrape", "--page-count", "0"])


def test_run_uses_load_and_extract_layers(monkeypatch, tmp_path: Path, capsys) -> None:
    config = cli.ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=1,
        min_rows_per_page=1,
        retry_attempts=2,
        db_path=tmp_path / "run.db",
    )
    players = [
        PlayerRecord(
            scrape_date="2026-03-21",
            player_name="Josh Allen",
            position="QB",
            rank_overall=1,
            rank_position=1,
            team="BUF",
            source="keeptradecut",
            age=29.8,
            tier=1,
            value=9989.0,
            scraped_at="2026-03-21T00:00:00",
        )
    ]
    observed = {}

    def fake_scrape_rankings(*, config, headless):
        observed["config"] = config
        observed["headless"] = headless
        return players

    def fake_insert_player_data(conn, rows):
        observed["conn"] = conn
        observed["rows"] = rows

    class DummyConnection:
        def close(self):
            observed["closed"] = True

    connection = DummyConnection()
    original_build_database_config = cli.build_database_config

    def fake_build_database_config(*, db_path, database_url):
        observed["database_url"] = database_url
        observed["db_path"] = db_path
        return original_build_database_config(db_path=db_path, database_url=database_url)

    def fake_create_connection_with_close(db_path, database_url=None):
        observed["db_path"] = db_path
        observed["connection_url"] = database_url
        return connection

    monkeypatch.delenv("KTC_DATABASE_URL", raising=False)
    monkeypatch.setattr(cli, "build_database_config", fake_build_database_config)
    monkeypatch.setattr(cli, "create_connection", fake_create_connection_with_close)
    monkeypatch.setattr(cli, "scrape_rankings", fake_scrape_rankings)
    monkeypatch.setattr(cli, "insert_player_data", fake_insert_player_data)

    exit_code = cli.run(config=config, headed=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert observed["db_path"] == config.db_path
    assert observed["config"] == config
    assert observed["headless"] is True
    assert observed["rows"] == players
    assert observed["closed"] is True
    assert observed["connection_url"] == f"sqlite:///{config.db_path}"
    assert "Scraped and stored 1 records using sqlite" in captured.out
    assert f"Destination: sqlite:///{config.db_path}" in captured.out


def test_main_parses_arguments_and_calls_run(monkeypatch, tmp_path: Path) -> None:
    observed = {}

    def fake_run(config, headed):
        observed["config"] = config
        observed["headed"] = headed
        return 0

    monkeypatch.setattr(cli, "run", fake_run)

    result = cli.main(
        [
            "--page-count",
            "2",
            "--db-path",
            str(tmp_path / "main.db"),
            "--headed",
        ]
    )

    assert result == 0
    assert observed["config"].page_count == 2
    assert observed["config"].db_path == tmp_path / "main.db"
    assert observed["headed"] is True


def test_main_sets_database_url_from_cli_arg(monkeypatch, tmp_path: Path) -> None:
    observed = {}

    def fake_run(config, headed):
        observed["config"] = config
        observed["headed"] = headed
        observed["database_url"] = os.getenv("KTC_DATABASE_URL")
        return 0

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.delenv("KTC_DATABASE_URL", raising=False)

    result = cli.main(
        [
            "--db-path",
            str(tmp_path / "main.db"),
            "--database-url",
            "sqlite:///tmp/override.db",
        ]
    )

    assert result == 0
    assert observed["database_url"] == "sqlite:///tmp/override.db"


def test_main_supports_scrape_subcommand(monkeypatch, tmp_path: Path) -> None:
    observed = {}

    def fake_run(config, headed):
        observed["config"] = config
        observed["headed"] = headed
        return 0

    monkeypatch.setattr(cli, "run", fake_run)

    result = cli.main(
        [
            "scrape",
            "--page-count",
            "4",
            "--db-path",
            str(tmp_path / "subcommand.db"),
        ]
    )

    assert result == 0
    assert observed["config"].page_count == 4
    assert observed["config"].db_path == tmp_path / "subcommand.db"
    assert observed["headed"] is False


def test_main_returns_one_and_prints_runtime_errors(monkeypatch, tmp_path: Path, capsys) -> None:
    def fake_run(config, headed):
        raise RuntimeError("chrome did not start")

    monkeypatch.setattr(cli, "run", fake_run)

    result = cli.main(["--db-path", str(tmp_path / "failure.db")])

    captured = capsys.readouterr()
    assert result == 1
    assert "Scrape failed: chrome did not start" in captured.err


def test_main_exits_with_configuration_error_for_bad_database_url(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    def fake_run(config, headed):
        raise ValueError("Unsupported database URL scheme: mysql://bad")

    monkeypatch.setattr(cli, "run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "--db-path",
                str(tmp_path / "bad.db"),
                "--database-url",
                "mysql://bad",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "Configuration error: Unsupported database URL scheme: mysql://bad" in captured.err


def test_modules_import_without_triggering_a_scrape() -> None:
    assert callable(cli.main)
    assert callable(legacy_scraper.main)
