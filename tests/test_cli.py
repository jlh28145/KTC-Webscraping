from pathlib import Path

from ktc_webscraping import cli
from ktc_webscraping.models import PlayerRecord
from src import scraper as legacy_scraper


def test_build_parser_uses_expected_defaults() -> None:
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.page_count == cli.DEFAULT_PAGE_COUNT
    assert args.db_path == cli.DEFAULT_DB_PATH
    assert args.base_url == cli.DEFAULT_BASE_URL
    assert args.min_rows_per_page == cli.DEFAULT_MIN_ROWS_PER_PAGE
    assert args.headed is False


def test_build_config_maps_args_into_scrape_config(tmp_path: Path) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "--page-count",
            "3",
            "--db-path",
            str(tmp_path / "custom.db"),
            "--base-url",
            "https://example.com?page={page}",
            "--min-rows-per-page",
            "25",
            "--headed",
        ]
    )

    config = cli.build_config(args)

    assert config.page_count == 3
    assert config.db_path == tmp_path / "custom.db"
    assert config.base_url == "https://example.com?page={page}"
    assert config.min_rows_per_page == 25


def test_run_uses_load_and_extract_layers(monkeypatch, tmp_path: Path, capsys) -> None:
    config = cli.ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=1,
        min_rows_per_page=1,
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

    def fake_create_connection(db_path):
        observed["db_path"] = db_path
        return object()

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

    def fake_create_connection_with_close(db_path):
        observed["db_path"] = db_path
        return connection

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
    assert "Scraped and stored 1 records" in captured.out


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


def test_modules_import_without_triggering_a_scrape() -> None:
    assert callable(cli.main)
    assert callable(legacy_scraper.main)
