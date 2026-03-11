import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from src.database import create_connection, insert_player_data

URL = "https://keeptradecut.com/dynasty-rankings?page=0&filters=QB|WR|RB|TE|RDP&format=2"
DB_PATH = "db/ktc.db"
PAGE_COUNT = 10


def build_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")
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
        close_button.click()
        popup_wait.until(EC.invisibility_of_element(popup))
    except TimeoutException:
        print("No popup detected.")
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


def extract_player_data(wait):
    players = []
    scrape_timestamp = datetime.now().isoformat()
    rankings_table = wait.until(EC.presence_of_element_located((By.ID, "rankings-page-rankings")))
    wait.until(lambda driver: len(rankings_table.find_elements(By.CLASS_NAME, "onePlayer")) >= 50)
    player_rows = rankings_table.find_elements(By.CLASS_NAME, "onePlayer")

    for row in player_rows:
        try:
            rank = safe_int(row.find_element(By.CLASS_NAME, "rank-number").text)
            player_name = row.find_element(By.TAG_NAME, "a").text
            position_full = row.find_element(By.CLASS_NAME, "position").text

            if "PICK" not in position_full:
                team = row.find_element(By.CLASS_NAME, "player-team").text
                age = safe_float(row.find_element(By.CLASS_NAME, "age").text.replace(" y.o.", ""))
                position = "".join(filter(str.isalpha, position_full))
                position_rank = safe_int("".join(filter(str.isdigit, position_full)))
            else:
                team = "None"
                age = None
                position = position_full
                position_rank = None

            tier = safe_int(row.find_element(By.CLASS_NAME, "player-tier").text.replace("Tier ", ""))
            value = safe_float(row.find_element(By.CLASS_NAME, "value").text)
            players.append([rank, player_name, position, position_rank, team, age, tier, value, scrape_timestamp])
        except Exception as exc:
            print(f"Row failed: {exc}")

    return players


def main():
    conn = create_connection(DB_PATH)
    driver, wait = build_driver()
    driver.get(URL)
    time.sleep(5)
    close_popup(driver)
    all_players = []

    try:
        for page in range(PAGE_COUNT):
            print(f"Scraping page {page + 1}")
            all_players.extend(extract_player_data(wait))
            try:
                next_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".pagination-arrow.arrow-right"))
                )
                driver.execute_script("arguments[0].click();", next_button)
                wait.until(EC.presence_of_element_located((By.ID, "rankings-page-rankings")))
            except Exception:
                print("No more pages.")
                break
    finally:
        driver.quit()

    insert_player_data(conn, all_players)
    conn.close()
    print(f"Scraped and stored {len(all_players)} records in {DB_PATH}.")


if __name__ == "__main__":
    main()
