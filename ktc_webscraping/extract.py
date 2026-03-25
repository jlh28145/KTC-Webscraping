import os
from datetime import datetime

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
DEFAULT_PAGE_COUNT = int(os.getenv("KTC_PAGE_COUNT", "10"))
DEFAULT_MIN_ROWS_PER_PAGE = 50


def detect_block_page(page_source: str) -> str | None:
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
    try:
        popup_wait = WebDriverWait(driver, 5)
        popup = popup_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "modal-content")))
        close_button = popup.find_element(By.ID, "dont-know")
        driver.execute_script("arguments[0].click();", close_button)
        popup_wait.until(EC.invisibility_of_element(popup))
    except (TimeoutException, ElementNotInteractableException, NoSuchElementException):
        return


def wait_for_rankings(
    driver: webdriver.Chrome, wait: WebDriverWait, min_rows_per_page: int
) -> None:
    wait.until(
        lambda current_driver: (
            current_driver.execute_script("return document.readyState") == "complete"
        )
    )
    close_popup(driver)

    try:
        wait.until(
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
) -> str:
    driver.get(base_url.format(page=page_number))
    wait_for_rankings(driver, wait, min_rows_per_page)
    return driver.page_source


def extract_page_records(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    page_number: int,
    base_url: str,
    min_rows_per_page: int,
    scrape_timestamp: str,
) -> list[PlayerRecord]:
    page_html = load_page_html(driver, wait, page_number, base_url, min_rows_per_page)
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


def scrape_rankings(config: ScrapeConfig, headless: bool = True) -> list[PlayerRecord]:
    driver, wait = build_driver(headless=headless)
    all_players: list[PlayerRecord] = []

    try:
        for page in range(config.page_count):
            print(f"Scraping page {page + 1}")
            scrape_timestamp = datetime.now().isoformat()
            page_rows = extract_page_records(
                driver=driver,
                wait=wait,
                page_number=page,
                base_url=config.base_url,
                min_rows_per_page=config.min_rows_per_page,
                scrape_timestamp=scrape_timestamp,
            )
            all_players.extend(page_rows)
    finally:
        driver.quit()

    return all_players
