import runpy
from importlib import metadata
from pathlib import Path

import pytest

from ktc_webscraping import cli
from ktc_webscraping.config import DEFAULT_DB_PATH, DEFAULT_PAGE_COUNT, DEFAULT_RETRY_ATTEMPTS
from ktc_webscraping.models import PlayerRecord


@pytest.fixture(autouse=True)
def _clear_ktc_environment(monkeypatch) -> None:
    for name in ("KTC_DB_PATH", "KTC_DATABASE_URL", "KTC_PAGE_COUNT", "KTC_RETRY_ATTEMPTS"):
        monkeypatch.delenv(name, raising=False)


def test_build_parser_uses_expected_defaults() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["scrape"])

    assert args.command == "scrape"
    assert args.page_count == DEFAULT_PAGE_COUNT
    assert args.db_path == DEFAULT_DB_PATH
    assert args.database_url is None
    assert args.base_url == cli.DEFAULT_BASE_URL
    assert args.min_rows_per_page == cli.DEFAULT_MIN_ROWS_PER_PAGE
    assert args.retry_attempts == DEFAULT_RETRY_ATTEMPTS
    assert args.row_count_tolerance == cli.DEFAULT_ROW_COUNT_TOLERANCE
    assert args.page_delay_seconds == cli.DEFAULT_PAGE_DELAY_SECONDS
    assert args.row_count_poll_timeout == cli.DEFAULT_ROW_COUNT_POLL_TIMEOUT
    assert args.headed is False


def test_build_parser_reads_defaults_from_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KTC_PAGE_COUNT", "3")
    monkeypatch.setenv("KTC_RETRY_ATTEMPTS", "0")
    monkeypatch.setenv("KTC_DB_PATH", str(tmp_path / "env.db"))
    monkeypatch.setenv("KTC_DATABASE_URL", "sqlite:///tmp/env.db")

    args = cli.build_parser().parse_args(["scrape"])

    assert args.page_count == 3
    assert args.retry_attempts == 0
    assert args.db_path == tmp_path / "env.db"
    assert args.database_url == "sqlite:///tmp/env.db"


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
            "--row-count-tolerance",
            "3",
            "--page-delay-seconds",
            "1.5",
            "--row-count-poll-timeout",
            "8",
            "--headed",
        ]
    )

    config = cli.build_config(args)

    assert config.page_count == 3
    assert config.db_path == tmp_path / "custom.db"
    assert config.base_url == "https://example.com?page={page}"
    assert config.min_rows_per_page == 25
    assert config.retry_attempts == 4
    assert config.row_count_tolerance == 3
    assert config.page_delay_seconds == 1.5
    assert config.row_count_poll_timeout == 8
    assert config.database_url is None
    assert config.row_count_tolerance == 3
    assert config.page_delay_seconds == 1.5
    assert config.row_count_poll_timeout == 8


def test_parser_rejects_non_positive_page_count() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["scrape", "--page-count", "0"])


def test_parser_rejects_negative_row_count_tolerance() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["scrape", "--row-count-tolerance", "-1"])


def test_parser_accepts_zero_row_count_tolerance() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["scrape", "--row-count-tolerance", "0"])

    assert args.row_count_tolerance == 0


def test_parser_rejects_negative_page_delay_seconds() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["scrape", "--page-delay-seconds", "-1"])


def test_parser_accepts_zero_page_delay_seconds() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["scrape", "--page-delay-seconds", "0"])

    assert args.page_delay_seconds == 0


def test_parser_rejects_non_positive_row_count_poll_timeout() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["scrape", "--row-count-poll-timeout", "0"])


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


def test_main_passes_database_url_through_config(monkeypatch, tmp_path: Path) -> None:
    observed = {}

    def fake_run(config, headed):
        observed["config"] = config
        return 0

    monkeypatch.setattr(cli, "run", fake_run)

    result = cli.main(
        [
            "--db-path",
            str(tmp_path / "main.db"),
            "--database-url",
            "sqlite:///tmp/override.db",
        ]
    )

    assert result == 0
    assert observed["config"].database_url == "sqlite:///tmp/override.db"


def test_run_prefers_database_url_over_db_path(monkeypatch, tmp_path: Path) -> None:
    observed = {}
    url_db_path = tmp_path / "from_url.db"
    config = cli.ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=1,
        min_rows_per_page=1,
        retry_attempts=0,
        db_path=tmp_path / "ignored.db",
        database_url=f"sqlite:///{url_db_path}",
    )

    class DummyConnection:
        def close(self):
            pass

    def fake_create_connection(db_path, database_url=None):
        observed["database_url"] = database_url
        return DummyConnection()

    monkeypatch.setattr(cli, "create_connection", fake_create_connection)
    monkeypatch.setattr(cli, "scrape_rankings", lambda *, config, headless: [])
    monkeypatch.setattr(cli, "insert_player_data", lambda conn, rows: None)

    assert cli.run(config=config) == 0
    assert observed["database_url"] == f"sqlite:///{url_db_path}"


def test_main_reports_invalid_environment_defaults(monkeypatch, capsys) -> None:
    monkeypatch.setenv("KTC_PAGE_COUNT", "ten")

    result = cli.main([])

    assert result == 2
    assert "KTC_PAGE_COUNT must be an integer, got 'ten'" in capsys.readouterr().err


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


def test_main_returns_zero_and_prints_help_for_help_flag(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "usage:" in captured.out


def test_cli_module_main_block_raises_system_exit(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["ktc_webscraping.cli", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("ktc_webscraping.cli", run_name="__main__")

    assert exc_info.value.code == 0


def test_ktc_scrape_console_script_points_at_cli_main() -> None:
    scripts = metadata.entry_points(group="console_scripts")
    matches = [entry for entry in scripts if entry.name == "ktc-scrape"]
    if not matches:
        pytest.skip("ktc-webscraping is not installed; run `make install`")

    assert matches[0].load() is cli.main
