import os
import random
import time
from datetime import UTC, datetime
from logging import getLogger

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .models import PlayerRecord, ScrapeConfig
from .transform import (
    parse_player_rows,
    parse_player_rows_from_text,
    parse_player_text_lines,
)

DEFAULT_BASE_URL = (
    "https://keeptradecut.com/dynasty-rankings?page={page}&filters=QB|WR|RB|TE|RDP&format=2"
)
DEFAULT_MIN_ROWS_PER_PAGE = 50
DEFAULT_ROW_COUNT_TOLERANCE = 10
DEFAULT_ROW_COUNT_POLL_TIMEOUT = 15
DEFAULT_PAGE_DELAY_SECONDS = 3.0
LOGGER = getLogger(__name__)


def detect_block_page(page_source: str) -> str | None:
    """Return a likely anti-bot marker when the page looks blocked."""

    lowered = page_source.lower()
    markers = [
        "verify you are human",
        "captcha",
        "access denied",
        "just a moment",
        "enable javascript",
        "cloudflare",
    ]
    for marker in markers:
        if marker in lowered:
            return marker
    return None


def build_driver(headless: bool = True) -> tuple[webdriver.Chrome, WebDriverWait]:
    """Create a Selenium Chrome driver with sensible defaults for local and CI use."""

    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1600,1200")

    chrome_binary = os.getenv("GOOGLE_CHROME_BIN")
    if chrome_binary:
        chrome_options.binary_location = chrome_binary

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except WebDriverException:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver, WebDriverWait(driver, 60)


def close_popup(driver: webdriver.Chrome) -> None:
    """Dismiss the landing modal if it is present."""

    try:
        popup_wait = WebDriverWait(driver, 5)
        popup = popup_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "modal-content")))
        close_button = popup.find_element(By.ID, "dont-know")
        driver.execute_script("arguments[0].click();", close_button)
        popup_wait.until(EC.invisibility_of_element(popup))
    except (TimeoutException, ElementNotInteractableException, NoSuchElementException):
        return


def wait_for_rankings(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    min_rows_per_page: int,
    row_count_tolerance: int = 0,
    row_count_poll_timeout: int = DEFAULT_ROW_COUNT_POLL_TIMEOUT,
) -> None:
    """Block until the rankings container is ready and populated.

    KeepTradeCut regularly serves a fully-loaded page (no anti-bot markers,
    correct title/url) whose row count lands a bit short of a normal full
    page. That shortfall doesn't recover with more waiting: the row count is
    already settled once the page reports ``readyState == "complete"``, and
    stays essentially the same across repeated attempts at the same page.
    ``row_count_tolerance`` accepts a page that's close enough instead of
    failing the whole run over it. Because waiting longer never helps, the
    row-count check uses its own short ``row_count_poll_timeout`` (rather
    than the much longer page-load ``wait``) so a page that's going to land
    short does so quickly instead of burning a minute per attempt.
    """

    wait.until(
        lambda current_driver: (
            current_driver.execute_script("return document.readyState") == "complete"
        )
    )
    close_popup(driver)

    row_count_wait = WebDriverWait(driver, row_count_poll_timeout)
    try:
        row_count_wait.until(
            lambda current_driver: (
                len(
                    current_driver.find_elements(
                        By.CSS_SELECTOR, "#rankings-page-rankings .onePlayer"
                    )
                )
                >= min_rows_per_page
            )
        )
    except TimeoutException as exc:
        page_source = driver.page_source
        title = driver.title
        current_url = driver.current_url
        block_marker = detect_block_page(page_source)
        row_count = len(driver.find_elements(By.CSS_SELECTOR, "#rankings-page-rankings .onePlayer"))

        acceptable_floor = max(min_rows_per_page - row_count_tolerance, 1)
        if block_marker is None and row_count >= acceptable_floor:
            LOGGER.warning(
                "Accepting short rankings page: wanted >= %s rows, found %s "
                "(tolerance=%s). title=%r, url=%r",
                min_rows_per_page,
                row_count,
                row_count_tolerance,
                title,
                current_url,
            )
            return

        detail = (
            f"Timed out waiting for rankings rows. title={title!r}, url={current_url!r}, "
            f"row_count={row_count}, block_marker={block_marker!r}"
        )
        raise RuntimeError(detail) from exc


def load_page_html(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    page_number: int,
    base_url: str,
    min_rows_per_page: int,
    row_count_tolerance: int = 0,
    row_count_poll_timeout: int = DEFAULT_ROW_COUNT_POLL_TIMEOUT,
) -> str:
    """Load one rankings page and return its HTML once the rows are available."""

    driver.get(base_url.format(page=page_number))
    wait_for_rankings(driver, wait, min_rows_per_page, row_count_tolerance, row_count_poll_timeout)
    return driver.page_source


def extract_page_records(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    page_number: int,
    base_url: str,
    min_rows_per_page: int,
    scrape_timestamp: str,
    row_count_tolerance: int = 0,
    row_count_poll_timeout: int = DEFAULT_ROW_COUNT_POLL_TIMEOUT,
) -> list[PlayerRecord]:
    """Extract ranking records from one page using DOM and text-layout fallbacks."""

    page_html = load_page_html(
        driver,
        wait,
        page_number,
        base_url,
        min_rows_per_page,
        row_count_tolerance,
        row_count_poll_timeout,
    )
    records = parse_player_rows(page_html, scrape_timestamp)
    if records:
        return records

    row_elements = driver.find_elements(By.CSS_SELECTOR, "#rankings-page-rankings .onePlayer")
    dom_records = [
        record
        for record in (
            parse_player_text_lines(row.text.splitlines(), scrape_timestamp)
            for row in row_elements
            if row.text.strip()
        )
        if record is not None
    ]
    if dom_records:
        return dom_records

    try:
        container_text = driver.find_element(By.ID, "rankings-page-rankings").text
    except NoSuchElementException:
        container_text = ""

    if container_text:
        text_records = parse_player_rows_from_text(container_text.splitlines(), scrape_timestamp)
        if text_records:
            return text_records

    title = driver.title
    current_url = driver.current_url
    block_marker = detect_block_page(page_html)
    live_row_count = len(row_elements)
    raise RuntimeError(
        f"Loaded page but parsed 0 ranking rows. title={title!r}, url={current_url!r}, "
        f"block_marker={block_marker!r}, live_row_count={live_row_count}"
    )


def extract_page_records_with_retry(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    page_number: int,
    base_url: str,
    min_rows_per_page: int,
    scrape_timestamp: str,
    retry_attempts: int,
    row_count_tolerance: int = 0,
    row_count_poll_timeout: int = DEFAULT_ROW_COUNT_POLL_TIMEOUT,
) -> list[PlayerRecord]:
    """Retry page extraction a bounded number of times before failing the run."""

    total_attempts = retry_attempts + 1
    last_error: RuntimeError | WebDriverException | None = None

    for attempt in range(1, total_attempts + 1):
        try:
            return extract_page_records(
                driver=driver,
                wait=wait,
                page_number=page_number,
                base_url=base_url,
                min_rows_per_page=min_rows_per_page,
                scrape_timestamp=scrape_timestamp,
                row_count_tolerance=row_count_tolerance,
                row_count_poll_timeout=row_count_poll_timeout,
            )
        except (RuntimeError, WebDriverException) as exc:
            last_error = exc
            if attempt == total_attempts:
                break
            LOGGER.warning(
                "Page %s failed on attempt %s/%s: %s",
                page_number + 1,
                attempt,
                total_attempts,
                exc,
            )
            time.sleep(attempt)

    assert last_error is not None
    raise RuntimeError(
        f"Page {page_number + 1} failed after {total_attempts} attempts: {last_error}"
    ) from last_error


def scrape_rankings(config: ScrapeConfig, headless: bool = True) -> list[PlayerRecord]:
    """Scrape all configured pages and return normalized player records.

    Pages are requested with a small delay (plus jitter) between them to
    avoid bursting requests at KeepTradeCut, which appears to progressively
    trim row counts on rapid sequential requests from the same source
    (e.g. shared CI runner IPs) without ever showing an explicit block page.
    A single page that fails every retry is logged and skipped rather than
    discarding every other page already scraped in the same run; the run
    only fails outright if every page failed.

    Every record in a run shares one UTC timestamp, so a run that crosses
    midnight still lands under a single ``scrape_date``.
    """

    scrape_timestamp = datetime.now(UTC).isoformat()
    driver, wait = build_driver(headless=headless)
    all_players: list[PlayerRecord] = []
    failed_pages: list[int] = []

    try:
        for page in range(config.page_count):
            LOGGER.info("Scraping page %s of %s", page + 1, config.page_count)
            try:
                page_rows = extract_page_records_with_retry(
                    driver=driver,
                    wait=wait,
                    page_number=page,
                    base_url=config.base_url,
                    min_rows_per_page=config.min_rows_per_page,
                    scrape_timestamp=scrape_timestamp,
                    retry_attempts=config.retry_attempts,
                    row_count_tolerance=config.row_count_tolerance,
                    row_count_poll_timeout=config.row_count_poll_timeout,
                )
            except RuntimeError as exc:
                LOGGER.error("Skipping page %s after repeated failures: %s", page + 1, exc)
                failed_pages.append(page + 1)
                continue

            all_players.extend(page_rows)
            LOGGER.info("Parsed %s rows from page %s", len(page_rows), page + 1)

            is_last_page = page == config.page_count - 1
            if not is_last_page and config.page_delay_seconds > 0:
                delay = config.page_delay_seconds + random.uniform(0, config.page_delay_seconds)
                time.sleep(delay)
    finally:
        driver.quit()

    if failed_pages:
        LOGGER.warning(
            "Completed scrape with %s of %s page(s) failed: %s",
            len(failed_pages),
            config.page_count,
            failed_pages,
        )

    if not all_players:
        raise RuntimeError(
            f"All {config.page_count} page(s) failed; nothing was scraped. "
            f"Failed pages: {failed_pages}"
        )

    return all_players
