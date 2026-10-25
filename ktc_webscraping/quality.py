"""Data-quality gate applied to a scrape before anything is stored or published.

The scraper deliberately tolerates a bad page (retries, skips, layout fallbacks)
so one hiccup doesn't lose a whole run. The gate is the other half of that
bargain: a degraded run is reported and rejected rather than quietly becoming
the snapshot a downstream consumer syncs.
"""

import math
from collections import Counter

from .models import ScrapeResult

DEFAULT_MIN_ROW_RATIO = 0.98


def check_scrape(
    result: ScrapeResult,
    expected_rows_per_page: int,
    min_row_ratio: float = DEFAULT_MIN_ROW_RATIO,
) -> list[str]:
    """Return a human-readable problem for each failed check; empty means the run passed."""

    problems: list[str] = []

    if result.failed_pages:
        problems.append(
            f"{len(result.failed_pages)} of {result.page_count} page(s) failed after retries: "
            f"{result.failed_pages}"
        )

    if result.fallback_pages:
        pages = ", ".join(
            f"page {page} ({parser})" for page, parser in sorted(result.fallback_pages.items())
        )
        problems.append(
            f"Parsed by a fallback parser, so the site layout may have changed: {pages}"
        )

    expected_rows = result.page_count * expected_rows_per_page
    # The epsilon keeps float noise (0.07 * 100 = 7.000000000000001) from adding a row.
    minimum_rows = math.ceil(expected_rows * min_row_ratio - 1e-9)
    if len(result.records) < minimum_rows:
        problems.append(
            f"Only {len(result.records)} rows scraped; expected at least {minimum_rows} "
            f"({min_row_ratio:.0%} of {expected_rows})"
        )

    name_counts = Counter((record.scrape_date, record.player_name) for record in result.records)
    duplicate_names = sorted(name for (_, name), count in name_counts.items() if count > 1)
    if duplicate_names:
        problems.append(f"Duplicate players in one snapshot: {duplicate_names[:5]}")

    rank_counts = Counter(
        (record.scrape_date, record.rank_overall)
        for record in result.records
        if record.rank_overall is not None
    )
    duplicate_ranks = sorted(rank for (_, rank), count in rank_counts.items() if count > 1)
    if duplicate_ranks:
        problems.append(f"Duplicate overall ranks in one snapshot: {duplicate_ranks[:5]}")

    return problems
