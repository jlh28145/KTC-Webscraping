import pytest
from selenium.common.exceptions import TimeoutException

from ktc_webscraping import extract
from ktc_webscraping.models import PlayerRecord


class _FakeDriver:
    """Minimal Selenium driver stand-in for exercising wait_for_rankings."""

    def __init__(self, row_count: int, page_source: str = "<html>ok</html>") -> None:
        self.row_count = row_count
        self.page_source = page_source
        self.title = "Dynasty Rankings - KeepTradeCut"
        self.current_url = "https://keeptradecut.com/dynasty-rankings?page=0"

    def execute_script(self, script: str) -> str:
        return "complete"

    def find_elements(self, by, value):
        return [object()] * self.row_count


class _FakeWait:
    """Minimal WebDriverWait stand-in that evaluates a condition exactly once."""

    def __init__(self, driver: _FakeDriver) -> None:
        self.driver = driver

    def until(self, condition):
        result = condition(self.driver)
        if not result:
            raise TimeoutException("timed out")
        return result


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


def test_wait_for_rankings_accepts_page_within_tolerance(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    driver = _FakeDriver(row_count=48)
    wait = _FakeWait(driver)

    extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=5)


def test_wait_for_rankings_raises_when_short_beyond_tolerance(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    driver = _FakeDriver(row_count=10)
    wait = _FakeWait(driver)

    with pytest.raises(RuntimeError, match="Timed out waiting for rankings rows"):
        extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=5)


def test_wait_for_rankings_raises_when_no_tolerance_configured(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    driver = _FakeDriver(row_count=48)
    wait = _FakeWait(driver)

    with pytest.raises(RuntimeError, match="Timed out waiting for rankings rows"):
        extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=0)


def test_wait_for_rankings_raises_when_block_marker_detected(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    driver = _FakeDriver(row_count=48, page_source="<html>please verify you are human</html>")
    wait = _FakeWait(driver)

    with pytest.raises(RuntimeError, match="block_marker='verify you are human'"):
        extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=5)
