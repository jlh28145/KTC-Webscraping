from pathlib import Path

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

from ktc_webscraping import extract
from ktc_webscraping.models import PlayerRecord, ScrapeConfig
from ktc_webscraping.transform import extract_rankings_text_lines


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


@pytest.mark.parametrize(
    "error",
    [TimeoutException("readyState never completed"), WebDriverException("net::ERR_TIMED_OUT")],
)
def test_extract_page_records_with_retry_retries_selenium_errors(monkeypatch, error) -> None:
    observed = {"calls": 0}

    def fake_extract_page_records(**kwargs):
        observed["calls"] += 1
        raise error

    monkeypatch.setattr(extract, "extract_page_records", fake_extract_page_records)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="Page 1 failed after 3 attempts"):
        extract.extract_page_records_with_retry(
            driver=object(),
            wait=object(),
            page_number=0,
            base_url="https://example.com?page={page}",
            min_rows_per_page=1,
            scrape_timestamp="2026-03-21T00:00:00",
            retry_attempts=2,
        )

    assert observed["calls"] == 3


def test_wait_for_rankings_accepts_page_within_tolerance(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    monkeypatch.setattr(extract, "WebDriverWait", lambda driver, timeout: _FakeWait(driver))
    driver = _FakeDriver(row_count=48)
    wait = _FakeWait(driver)

    extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=5)


def test_wait_for_rankings_raises_when_short_beyond_tolerance(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    monkeypatch.setattr(extract, "WebDriverWait", lambda driver, timeout: _FakeWait(driver))
    driver = _FakeDriver(row_count=10)
    wait = _FakeWait(driver)

    with pytest.raises(RuntimeError, match="Timed out waiting for rankings rows"):
        extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=5)


def test_wait_for_rankings_raises_when_no_tolerance_configured(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    monkeypatch.setattr(extract, "WebDriverWait", lambda driver, timeout: _FakeWait(driver))
    driver = _FakeDriver(row_count=48)
    wait = _FakeWait(driver)

    with pytest.raises(RuntimeError, match="Timed out waiting for rankings rows"):
        extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=0)


def test_wait_for_rankings_raises_when_block_marker_detected(monkeypatch) -> None:
    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    monkeypatch.setattr(extract, "WebDriverWait", lambda driver, timeout: _FakeWait(driver))
    driver = _FakeDriver(row_count=48, page_source="<html>please verify you are human</html>")
    wait = _FakeWait(driver)

    with pytest.raises(RuntimeError, match="block_marker='verify you are human'"):
        extract.wait_for_rankings(driver, wait, min_rows_per_page=50, row_count_tolerance=5)


def test_wait_for_rankings_uses_short_poll_timeout_for_row_count(monkeypatch) -> None:
    """The row-count phase must use its own short timeout, not the page-load wait."""

    monkeypatch.setattr(extract, "close_popup", lambda driver: None)
    observed_timeouts = []

    def fake_web_driver_wait(driver, timeout):
        observed_timeouts.append(timeout)
        return _FakeWait(driver)

    monkeypatch.setattr(extract, "WebDriverWait", fake_web_driver_wait)
    driver = _FakeDriver(row_count=48)
    wait = _FakeWait(driver)

    extract.wait_for_rankings(
        driver,
        wait,
        min_rows_per_page=50,
        row_count_tolerance=5,
        row_count_poll_timeout=7,
    )

    assert observed_timeouts == [7]


class _StubDriver:
    """Driver stand-in that only needs to support quit() for scrape_rankings tests."""

    def quit(self) -> None:
        return None


def _make_player(rank: int) -> PlayerRecord:
    return PlayerRecord(
        scrape_date="2026-03-21",
        player_name=f"Player {rank}",
        position="QB",
        rank_overall=rank,
        rank_position=rank,
        team="BUF",
        source="keeptradecut",
        age=29.8,
        tier=1,
        value=9989.0,
        scraped_at="2026-03-21T00:00:00",
    )


def test_scrape_rankings_skips_failed_page_and_keeps_others(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(extract, "build_driver", lambda headless: (_StubDriver(), object()))

    def fake_extract_with_retry(**kwargs):
        page_number = kwargs["page_number"]
        if page_number == 1:
            raise RuntimeError("still failing")
        return [_make_player(page_number)]

    monkeypatch.setattr(extract, "extract_page_records_with_retry", fake_extract_with_retry)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    config = ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=3,
        min_rows_per_page=1,
        retry_attempts=2,
        db_path=tmp_path / "run.db",
    )

    players = extract.scrape_rankings(config=config, headless=True)

    assert [player.rank_overall for player in players] == [0, 2]


def test_scrape_rankings_raises_when_every_page_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(extract, "build_driver", lambda headless: (_StubDriver(), object()))

    def fake_extract_with_retry(**kwargs):
        raise RuntimeError("still failing")

    monkeypatch.setattr(extract, "extract_page_records_with_retry", fake_extract_with_retry)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    config = ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=2,
        min_rows_per_page=1,
        retry_attempts=2,
        db_path=tmp_path / "run.db",
    )

    with pytest.raises(RuntimeError, match="All 2 page.s. failed"):
        extract.scrape_rankings(config=config, headless=True)


def test_scrape_rankings_uses_one_utc_timestamp_for_every_page(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(extract, "build_driver", lambda headless: (_StubDriver(), object()))
    observed_timestamps: list[str] = []

    def fake_extract_with_retry(**kwargs):
        observed_timestamps.append(kwargs["scrape_timestamp"])
        return [_make_player(kwargs["page_number"])]

    monkeypatch.setattr(extract, "extract_page_records_with_retry", fake_extract_with_retry)
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)

    config = ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=3,
        min_rows_per_page=1,
        retry_attempts=0,
        db_path=tmp_path / "run.db",
    )

    extract.scrape_rankings(config=config, headless=True)

    assert len(set(observed_timestamps)) == 1
    assert observed_timestamps[0].endswith("+00:00")


class _FakeElement:
    def __init__(self, text: str) -> None:
        self.text = text


class _PageDriver:
    """Driver stand-in for extract_page_records: serves fixed HTML and live-DOM text."""

    def __init__(self, page_source: str, row_texts=(), container_text: str | None = None):
        self.page_source = page_source
        self.row_texts = list(row_texts)
        self.container_text = container_text
        self.title = "Dynasty Rankings - KeepTradeCut"
        self.current_url = "https://keeptradecut.com/dynasty-rankings?page=0"
        self.visited: list[str] = []

    def get(self, url: str) -> None:
        self.visited.append(url)

    def find_elements(self, by, value):
        return [_FakeElement(text) for text in self.row_texts]

    def find_element(self, by, value):
        if self.container_text is None:
            raise NoSuchElementException("no container")
        return _FakeElement(self.container_text)


def _extract_from(driver: _PageDriver, monkeypatch) -> list[PlayerRecord]:
    monkeypatch.setattr(extract, "wait_for_rankings", lambda *args: None)
    return extract.extract_page_records(
        driver=driver,
        wait=object(),
        page_number=2,
        base_url="https://example.com?page={page}",
        min_rows_per_page=1,
        scrape_timestamp="2026-03-21T00:00:00+00:00",
    )


def test_extract_page_records_parses_page_html(monkeypatch, legacy_row_html: str) -> None:
    driver = _PageDriver(legacy_row_html)

    records = _extract_from(driver, monkeypatch)

    assert driver.visited == ["https://example.com?page=2"]
    assert [record.player_name for record in records] == ["Josh Allen"]


def test_extract_page_records_falls_back_to_live_row_text(monkeypatch) -> None:
    driver = _PageDriver(
        "<html></html>",
        row_texts=["1\nBijan RobinsonATL\nRB1\n24.1 y.o.\nTier 1\n1\n9999", "   "],
    )

    records = _extract_from(driver, monkeypatch)

    assert [(record.player_name, record.team) for record in records] == [("Bijan Robinson", "ATL")]


def test_extract_page_records_falls_back_to_container_text(
    monkeypatch, text_layout_html: str
) -> None:
    container_text = extract_rankings_text_lines(text_layout_html)
    driver = _PageDriver("<html></html>", container_text="\n".join(container_text))

    records = _extract_from(driver, monkeypatch)

    assert [record.player_name for record in records] == ["Bijan Robinson", "2027 Early 1st"]


def test_extract_page_records_raises_with_diagnostics_when_nothing_parses(monkeypatch) -> None:
    driver = _PageDriver("<html>Just a moment...</html>")

    with pytest.raises(RuntimeError, match="parsed 0 ranking rows.*block_marker='just a moment'"):
        _extract_from(driver, monkeypatch)


class _ChromeRecorder:
    """Records how build_driver constructs Chrome, failing the first attempt if asked."""

    def __init__(self, fail_first: bool) -> None:
        self.fail_first = fail_first
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first and len(self.calls) == 1:
            raise WebDriverException("chromedriver not on PATH")
        return object()


def test_build_driver_configures_headless_chrome(monkeypatch) -> None:
    chrome = _ChromeRecorder(fail_first=False)
    monkeypatch.setattr(extract.webdriver, "Chrome", chrome)
    monkeypatch.setenv("GOOGLE_CHROME_BIN", "/opt/chrome/chrome")

    driver, wait = extract.build_driver(headless=True)

    options = chrome.calls[0]["options"]
    assert "--headless=new" in options.arguments
    assert options.binary_location == "/opt/chrome/chrome"
    assert wait._timeout == 60
    assert wait._driver is driver


def test_build_driver_falls_back_to_webdriver_manager(monkeypatch) -> None:
    chrome = _ChromeRecorder(fail_first=True)
    monkeypatch.setattr(extract.webdriver, "Chrome", chrome)
    monkeypatch.setattr(extract, "Service", lambda path: f"service:{path}")
    monkeypatch.setattr(
        extract, "ChromeDriverManager", lambda: type("M", (), {"install": lambda self: "/drv"})()
    )
    monkeypatch.delenv("GOOGLE_CHROME_BIN", raising=False)

    extract.build_driver(headless=False)

    assert len(chrome.calls) == 2
    assert chrome.calls[1]["service"] == "service:/drv"
    assert "--headless=new" not in chrome.calls[1]["options"].arguments


class _PopupWait:
    def __init__(self, popup) -> None:
        self.popup = popup

    def until(self, condition):
        if self.popup is None:
            raise TimeoutException("no modal")
        return self.popup


def test_close_popup_clicks_dismiss_button(monkeypatch) -> None:
    clicked = []

    class Popup:
        def find_element(self, by, value):
            return f"button#{value}"

    class Driver:
        def execute_script(self, script, element):
            clicked.append(element)

    monkeypatch.setattr(extract, "WebDriverWait", lambda driver, timeout: _PopupWait(Popup()))

    extract.close_popup(Driver())

    assert clicked == ["button#dont-know"]


def test_close_popup_ignores_missing_modal(monkeypatch) -> None:
    monkeypatch.setattr(extract, "WebDriverWait", lambda driver, timeout: _PopupWait(None))

    assert extract.close_popup(object()) is None
