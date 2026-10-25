import argparse
import sys
from logging import getLogger
from pathlib import Path

from .config import RuntimeConfig, load_runtime_config
from .extract import (
    DEFAULT_BASE_URL,
    DEFAULT_MIN_ROWS_PER_PAGE,
    DEFAULT_PAGE_DELAY_SECONDS,
    DEFAULT_ROW_COUNT_POLL_TIMEOUT,
    DEFAULT_ROW_COUNT_TOLERANCE,
    scrape_rankings,
)
from .load import build_database_config, create_connection, insert_player_data
from .logging_config import configure_logging
from .models import ScrapeConfig
from .quality import DEFAULT_MIN_ROW_RATIO, check_scrape

LOGGER = getLogger(__name__)
EXIT_QUALITY_FAILED = 3


def positive_int(value: str) -> int:
    """Argparse validator for positive integer CLI options."""

    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def non_negative_int(value: str) -> int:
    """Argparse validator for zero-or-greater integer CLI options."""

    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or a positive integer")
    return parsed


def non_negative_float(value: str) -> float:
    """Argparse validator for zero-or-greater float CLI options."""

    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or a positive number")
    return parsed


def row_ratio(value: str) -> float:
    """Argparse validator for a fraction between 0 (exclusive) and 1."""

    parsed = float(value)
    if not 0 < parsed <= 1:
        raise argparse.ArgumentTypeError("value must be greater than 0 and at most 1")
    return parsed


def build_config(args: argparse.Namespace) -> ScrapeConfig:
    """Map parsed CLI arguments into a strongly typed scrape config."""

    return ScrapeConfig(
        base_url=args.base_url,
        page_count=args.page_count,
        min_rows_per_page=args.min_rows_per_page,
        retry_attempts=args.retry_attempts,
        db_path=args.db_path,
        row_count_tolerance=args.row_count_tolerance,
        page_delay_seconds=args.page_delay_seconds,
        row_count_poll_timeout=args.row_count_poll_timeout,
        database_url=args.database_url or None,
        min_row_ratio=args.min_row_ratio,
        allow_degraded=args.allow_degraded,
    )


def build_parser(runtime_config: RuntimeConfig | None = None) -> argparse.ArgumentParser:
    """Build the CLI parser used by local runs and automation.

    Option defaults come from ``runtime_config`` (the environment, by default),
    so ``KTC_*`` variables set defaults and explicit flags override them.
    """

    runtime_config = runtime_config or load_runtime_config()

    parser = argparse.ArgumentParser(
        description=("Scrape KeepTradeCut rankings into a local SQLite database or Postgres.")
    )
    subparsers = parser.add_subparsers(dest="command")

    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Run the rankings scraper and persist results.",
        description="Scrape KeepTradeCut rankings and store the normalized records.",
    )
    _add_scrape_arguments(scrape_parser, runtime_config)
    return parser


def _add_scrape_arguments(parser: argparse.ArgumentParser, runtime_config: RuntimeConfig) -> None:
    """Register arguments shared by the scraper entrypoint."""

    parser.add_argument(
        "--page-count",
        type=positive_int,
        default=runtime_config.page_count,
        help="Number of ranking pages to scrape.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=runtime_config.db_path,
        help="SQLite database destination. Ignored when a database URL is set.",
    )
    parser.add_argument(
        "--database-url",
        default=runtime_config.database_url,
        help=(
            "Database URL (defaults to KTC_DATABASE_URL). Takes precedence over --db-path. "
            "Supports sqlite:///path and postgresql://user:pass@host/db."
        ),
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
        "--retry-attempts",
        type=non_negative_int,
        default=runtime_config.retry_attempts,
        help="Number of retry attempts for a page after the initial failure.",
    )
    parser.add_argument(
        "--row-count-tolerance",
        type=non_negative_int,
        default=DEFAULT_ROW_COUNT_TOLERANCE,
        help=(
            "Rows short of --min-rows-per-page still accepted as a complete page. "
            "KeepTradeCut occasionally serves a page a few rows short of a full "
            "page without any anti-bot markers; use 0 to require an exact match."
        ),
    )
    parser.add_argument(
        "--page-delay-seconds",
        type=non_negative_float,
        default=DEFAULT_PAGE_DELAY_SECONDS,
        help=(
            "Base delay (plus random jitter up to the same amount) between "
            "successful page loads, to avoid bursting requests at KeepTradeCut. "
            "Use 0 to disable the delay."
        ),
    )
    parser.add_argument(
        "--row-count-poll-timeout",
        type=positive_int,
        default=DEFAULT_ROW_COUNT_POLL_TIMEOUT,
        help=(
            "Seconds to poll for --min-rows-per-page rows before falling back to "
            "--row-count-tolerance. The row count doesn't grow with more waiting, "
            "so this is intentionally much shorter than the page-load timeout."
        ),
    )
    parser.add_argument(
        "--min-row-ratio",
        type=row_ratio,
        default=DEFAULT_MIN_ROW_RATIO,
        help=(
            "Quality gate: the run is rejected (exit 3, nothing stored) if it scrapes fewer "
            "than this fraction of page-count x min-rows-per-page rows."
        ),
    )
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help=(
            "Store the run even if the quality gate fails (failed pages, fallback parsers, "
            "too few rows, duplicates). For manual recovery only."
        ),
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chrome with a visible browser window instead of headless mode.",
    )


def run(config: ScrapeConfig, headed: bool = False) -> int:
    """Execute a scrape run and persist the normalized results."""

    database_config = build_database_config(
        db_path=config.db_path, database_url=config.database_url
    )
    LOGGER.info("Starting scrape run with database %s", database_config.display_url)
    conn = create_connection(config.db_path, database_url=database_config.url)
    try:
        result = scrape_rankings(config=config, headless=not headed)
        problems = check_scrape(result, config.min_rows_per_page, config.min_row_ratio)
        if problems and not config.allow_degraded:
            for problem in problems:
                LOGGER.error("Quality gate: %s", problem)
            print("Quality gate failed; nothing was stored:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return EXIT_QUALITY_FAILED
        for problem in problems:
            LOGGER.warning("Quality gate overridden by --allow-degraded: %s", problem)
        players = result.records
        insert_player_data(conn, players)
    finally:
        conn.close()

    LOGGER.info("Stored %s records", len(players))
    print(f"Scraped and stored {len(players)} records using {database_config.scheme}.")
    print(f"Destination: {database_config.display_url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    try:
        runtime_config = load_runtime_config()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    parser = build_parser(runtime_config)
    raw_argv = argv if argv is not None else sys.argv[1:]
    normalized_argv = raw_argv
    if not raw_argv or raw_argv[0] not in {"scrape", "-h", "--help"}:
        normalized_argv = ["scrape", *raw_argv]

    args = parser.parse_args(normalized_argv)
    if args.command != "scrape":
        parser.print_help()
        return 0

    try:
        config = build_config(args)
        return run(config=config, headed=args.headed)
    except ValueError as exc:
        parser.exit(2, f"Configuration error: {exc}\n")
    except Exception as exc:
        LOGGER.exception("Scrape failed")
        print(f"Scrape failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
