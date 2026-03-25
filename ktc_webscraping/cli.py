import argparse
import os
from pathlib import Path

from .extract import (
    DEFAULT_BASE_URL,
    DEFAULT_MIN_ROWS_PER_PAGE,
    DEFAULT_PAGE_COUNT,
    scrape_rankings,
)
from .load import create_connection, insert_player_data
from .models import ScrapeConfig

DEFAULT_DB_PATH = Path(os.getenv("KTC_DB_PATH", "db/ktc.db"))


def build_config(args: argparse.Namespace) -> ScrapeConfig:
    return ScrapeConfig(
        base_url=args.base_url,
        page_count=args.page_count,
        min_rows_per_page=args.min_rows_per_page,
        db_path=args.db_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape KeepTradeCut rankings into SQLite.")
    parser.add_argument(
        "--page-count",
        type=int,
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
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Ranking URL template with a {page} placeholder.",
    )
    parser.add_argument(
        "--min-rows-per-page",
        type=int,
        default=DEFAULT_MIN_ROWS_PER_PAGE,
        help="Minimum number of ranking rows expected before parsing a page.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chrome with a visible browser window instead of headless mode.",
    )
    return parser


def run(config: ScrapeConfig, headed: bool = False) -> int:
    conn = create_connection(config.db_path)
    try:
        players = scrape_rankings(config=config, headless=not headed)
        insert_player_data(conn, players)
    finally:
        conn.close()

    print(f"Scraped and stored {len(players)} records in {config.db_path}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = build_config(args)
    return run(config=config, headed=args.headed)


if __name__ == "__main__":
    raise SystemExit(main())
