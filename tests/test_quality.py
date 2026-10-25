import pytest

from ktc_webscraping.models import PlayerRecord, ScrapeResult
from ktc_webscraping.quality import check_scrape


def _player(rank: int | None, name: str, scrape_date: str = "2026-10-25") -> PlayerRecord:
    return PlayerRecord(
        scrape_date=scrape_date,
        player_name=name,
        position="PICK" if rank is None else "WR",
        rank_overall=rank,
        rank_position=rank,
        team=None,
        source="keeptradecut",
        age=None,
        tier=1,
        value=1000.0,
        scraped_at=f"{scrape_date}T17:00:00+00:00",
    )


def _clean(count: int = 10) -> list[PlayerRecord]:
    return [_player(rank, f"Player {rank}") for rank in range(1, count + 1)]


def test_a_clean_full_scrape_passes() -> None:
    result = ScrapeResult(records=_clean(10), page_count=2)

    assert check_scrape(result, expected_rows_per_page=5) == []


def test_unranked_picks_do_not_count_as_duplicate_ranks() -> None:
    records = _clean(8) + [_player(None, "2027 Early 1st"), _player(None, "2027 Mid 1st")]

    assert check_scrape(ScrapeResult(records=records, page_count=2), 5) == []


@pytest.mark.parametrize(
    ("rows", "ratio", "passes"),
    [(10, 0.98, True), (9, 0.98, False), (9, 0.9, True), (8, 0.9, False)],
)
def test_row_count_floor_rounds_up(rows, ratio, passes) -> None:
    problems = check_scrape(ScrapeResult(records=_clean(rows), page_count=2), 5, ratio)

    assert (problems == []) is passes


def test_failed_pages_are_reported() -> None:
    result = ScrapeResult(records=_clean(10), page_count=2, failed_pages=[2])

    assert check_scrape(result, 5) == ["1 of 2 page(s) failed after retries: [2]"]


def test_fallback_parsers_are_reported_in_page_order() -> None:
    result = ScrapeResult(
        records=_clean(10), page_count=2, fallback_pages={2: "html-text", 1: "dom-row-text"}
    )

    assert check_scrape(result, 5) == [
        "Parsed by a fallback parser, so the site layout may have changed: "
        "page 1 (dom-row-text), page 2 (html-text)"
    ]


def test_duplicate_players_and_ranks_are_reported() -> None:
    """The 2026-10-25 rerun bug: a stale player left a second row at rank 463."""

    records = _clean(9) + [_player(9, "Player 9")]

    problems = check_scrape(ScrapeResult(records=records, page_count=2), 5)

    assert problems == [
        "Duplicate players in one snapshot: ['Player 9']",
        "Duplicate overall ranks in one snapshot: [9]",
    ]


def test_same_player_on_different_dates_is_not_a_duplicate() -> None:
    records = [_player(1, "Josh Allen", "2026-10-24"), _player(1, "Josh Allen", "2026-10-25")]

    assert check_scrape(ScrapeResult(records=records, page_count=1), 2) == []


def test_row_floor_ignores_float_noise() -> None:
    records = _clean(7)

    assert check_scrape(ScrapeResult(records=records, page_count=1), 100, 0.07) == []
