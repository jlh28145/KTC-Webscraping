import os
from pathlib import Path
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from src.database import create_connection, insert_player_data

BASE_URL = "https://keeptradecut.com/dynasty-rankings?page={page}&filters=QB|WR|RB|TE|RDP&format=2"
DB_PATH = Path("db/ktc.db")
PAGE_COUNT = int(os.getenv("KTC_PAGE_COUNT", "10"))
MIN_ROWS_PER_PAGE = 50


def build_driver():
    chrome_options = Options()
    if os.getenv("KTC_HEADLESS", "1") != "0":
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver, WebDriverWait(driver, 60)


def close_popup(driver):
    try:
        popup_wait = WebDriverWait(driver, 5)
        popup = popup_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "modal-content")))
        close_button = popup.find_element(By.ID, "dont-know")
        driver.execute_script("arguments[0].click();", close_button)
        popup_wait.until(EC.invisibility_of_element(popup))
    except TimeoutException:
        return
    except ElementNotInteractableException:
        return
    except Exception as exc:
        print(f"No popup detected or unable to close: {exc}")


def safe_float(text):
    try:
        return float(text)
    except Exception:
        return None


def safe_int(text):
    try:
        return int(text)
    except Exception:
        return None


def optional_text(element, by, value):
    matches = element.find_elements(by, value)
    if not matches:
        return None
    return matches[0].text or None


def parse_player_rows(page_html, scrape_timestamp):
    players = []
    soup = BeautifulSoup(page_html, "html.parser")
    player_rows = soup.select("#rankings-page-rankings .onePlayer")

    for row in player_rows:
        try:
            rank = safe_int(row.select_one(".rank-number").get_text(strip=True))
            player_name = row.select_one(".player-name a").get_text(strip=True)
            position_full = row.select_one(".position-team .position").get_text(strip=True)

            if "PICK" not in position_full:
                team_node = row.select_one(".player-team")
                team = team_node.get_text(strip=True) if team_node else None
                age_node = row.select_one(".age")
                age_text = age_node.get_text(strip=True) if age_node else None
                age = safe_float(age_text.replace(" y.o.", "")) if age_text else None
                position = "".join(filter(str.isalpha, position_full))
                position_rank = safe_int("".join(filter(str.isdigit, position_full)))
            else:
                team = None
                age = None
                position = position_full
                position_rank = None

            tier = safe_int(row.select_one(".player-tier").get_text(strip=True).replace("Tier ", ""))
            value = safe_float(row.select_one(".value").get_text(strip=True))
            players.append([rank, player_name, position, position_rank, team, age, tier, value, scrape_timestamp])
        except Exception as exc:
            print(f"Row failed: {exc}")

    return players


def load_page(driver, wait, page_number):
    driver.get(BASE_URL.format(page=page_number))
    wait.until(lambda current_driver: current_driver.execute_script("return document.readyState") == "complete")
    close_popup(driver)
    wait.until(
        lambda current_driver: len(current_driver.find_elements(By.CSS_SELECTOR, "#rankings-page-rankings .onePlayer"))
        >= MIN_ROWS_PER_PAGE
    )
    return parse_player_rows(driver.page_source, datetime.now().isoformat())


def main():
    conn = create_connection(DB_PATH)
    driver, wait = build_driver()
    all_players = []

    try:
        for page in range(PAGE_COUNT):
            print(f"Scraping page {page + 1}")
            page_rows = load_page(driver, wait, page)
            if not page_rows:
                print("No rows returned for page, stopping early.")
                break
            all_players.extend(page_rows)
    finally:
        driver.quit()

    insert_player_data(conn, all_players)
    conn.close()
    print(f"Scraped and stored {len(all_players)} records in {DB_PATH}.")


if __name__ == "__main__":
    main()
