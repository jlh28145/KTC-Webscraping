import pytest

from ktc_webscraping import extract
from ktc_webscraping.models import PlayerRecord


def test_extract_page_records_with_retry_retries_then_succeeds(monkeypatch) -> None:
    observed = {"calls": 0}
    expected = [
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

    def fake_extract_page_records(**kwargs):
        observed["calls"] += 1
        if observed["calls"] < 3:
            raise RuntimeError("temporary layout failure")
        return expected

    monkeypatch.setattr(extract, "extract_page_records", fake_extract_page_records)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    records = extract.extract_page_records_with_retry(
        driver=object(),
        wait=object(),
        page_number=0,
        base_url="https://example.com?page={page}",
        min_rows_per_page=1,
        scrape_timestamp="2026-03-21T00:00:00",
        retry_attempts=2,
    )

    assert records == expected
    assert observed["calls"] == 3


def test_extract_page_records_with_retry_raises_after_final_attempt(monkeypatch) -> None:
    def fake_extract_page_records(**kwargs):
        raise RuntimeError("still failing")

    monkeypatch.setattr(extract, "extract_page_records", fake_extract_page_records)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="failed after 3 attempts: still failing"):
        extract.extract_page_records_with_retry(
            driver=object(),
            wait=object(),
            page_number=1,
            base_url="https://example.com?page={page}",
            min_rows_per_page=1,
            scrape_timestamp="2026-03-21T00:00:00",
            retry_attempts=2,
        )
