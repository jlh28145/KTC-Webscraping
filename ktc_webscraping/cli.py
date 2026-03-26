import argparse
import os
import sys
from pathlib import Path

from .config import load_runtime_config
from .extract import (
    DEFAULT_BASE_URL,
    DEFAULT_MIN_ROWS_PER_PAGE,
    DEFAULT_PAGE_COUNT,
    scrape_rankings,
)
from .load import build_database_config, create_connection, insert_player_data
from .models import ScrapeConfig

DEFAULT_RUNTIME_CONFIG = load_runtime_config()
DEFAULT_DB_PATH = DEFAULT_RUNTIME_CONFIG.db_path
DEFAULT_DATABASE_URL = DEFAULT_RUNTIME_CONFIG.database_url


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def build_config(args: argparse.Namespace) -> ScrapeConfig:
    return ScrapeConfig(
        base_url=args.base_url,
        page_count=args.page_count,
        min_rows_per_page=args.min_rows_per_page,
        db_path=args.db_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape KeepTradeCut rankings into a local SQLite database or a future hosted database."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Run the rankings scraper and persist results.",
        description="Scrape KeepTradeCut rankings and store the normalized records.",
    )
    _add_scrape_arguments(scrape_parser)
    return parser


def _add_scrape_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-count",
        type=positive_int,
        default=DEFAULT_PAGE_COUNT,
        help="Number of ranking pages to scrape.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database destination.",
    )
    parser.add_argument(
        "--database-url",
        default=DEFAULT_DATABASE_URL,
        help="Database URL. Supports sqlite:///... now and prepares for hosted Postgres later.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Ranking URL template with a {page} placeholder.",
    )
    parser.add_argument(
        "--min-rows-per-page",
        type=positive_int,
        default=DEFAULT_MIN_ROWS_PER_PAGE,
        help="Minimum number of ranking rows expected before parsing a page.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chrome with a visible browser window instead of headless mode.",
    )


def run(config: ScrapeConfig, headed: bool = False) -> int:
    database_url = os.getenv("KTC_DATABASE_URL")
    database_config = build_database_config(db_path=config.db_path, database_url=database_url)
    conn = create_connection(config.db_path, database_url=database_config.url)
    try:
        players = scrape_rankings(config=config, headless=not headed)
        insert_player_data(conn, players)
    finally:
        conn.close()

    print(f"Scraped and stored {len(players)} records using {database_config.scheme}.")
    print(f"Destination: {database_config.url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = argv if argv is not None else sys.argv[1:]
    normalized_argv = raw_argv
    if not raw_argv or raw_argv[0] not in {"scrape", "-h", "--help"}:
        normalized_argv = ["scrape", *raw_argv]

    args = parser.parse_args(normalized_argv)
    if args.command != "scrape":
        parser.print_help()
        return 0

    if args.database_url:
        os.environ["KTC_DATABASE_URL"] = args.database_url

    try:
        config = build_config(args)
        return run(config=config, headed=args.headed)
    except ValueError as exc:
        parser.exit(2, f"Configuration error: {exc}\n")
    except NotImplementedError as exc:
        parser.exit(2, f"{exc}\n")
    except Exception as exc:
        print(f"Scrape failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
