# src/scraper.py
import time
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from database import create_connection, insert_player_data

# Setup Chrome
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Uncomment for headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 60)

url = "https://keeptradecut.com/dynasty-rankings?page=0&filters=QB|WR|RB|TE|RDP&format=2"
driver.get(url)

def close_popup():
    try:
        # Wait for the popup to appear (change 'popup-class' to the actual class or ID of the popup)
        popup = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'modal-content')))
        
        # Close the popup (adjust the selector for the close button accordingly)
        close_button = popup.find_element(By.ID, 'dont-know')
        close_button.click()
        print("Popup closed successfully.")
        
        # Wait for the popup to disappear before continuing
        wait.until(EC.invisibility_of_element(popup))
        
    except Exception as e:
        print(f"No popup detected or unable to close: {e}")

def safe_float(text):
    try:
        return float(text)
    except:
        return None

def safe_int(text):
    try:
        return int(text)
    except:
        return None

def extract_player_data():
    players = []
    scrape_timestamp = datetime.now().isoformat()

    # Ensure that the rankings table is loaded
    rankings_table = wait.until(EC.presence_of_element_located((By.ID, 'rankings-page-rankings')))
    
    # Find all player rows within the rankings table
    player_rows = rankings_table.find_elements(By.CLASS_NAME, 'onePlayer')
    
    # Wait until all 50 player rows are loaded (adjust if the number of players differs)
    wait.until(lambda driver: len(player_rows) >= 50)

    for row in player_rows:
        try:
            rank = row.find_element(By.CLASS_NAME, 'rank-number').text
            player_name = row.find_element(By.TAG_NAME, 'a').text
            position_full = row.find_element(By.CLASS_NAME, 'position').text
            
            if not 'PICK' in position_full:
                team = row.find_element(By.CLASS_NAME, 'player-team').text
                age_text = row.find_element(By.CLASS_NAME, 'age').text
                age = safe_float(age_text.replace(' y.o.', ''))
                
                position = ''.join(filter(str.isalpha, position_full))
                position_rank = ''.join(filter(str.isdigit, position_full))
            else:
                team = 'None'
                age = None
                position = position_full
                position_rank = None
            
            tier_text = row.find_element(By.CLASS_NAME, 'player-tier').text
            tier = safe_int(tier_text.replace("Tier ", ""))

            value_text = row.find_element(By.CLASS_NAME, 'value').text
            value = safe_float(value_text)

            players.append([rank, player_name, position, position_rank, team, age, tier, value, scrape_timestamp])
        
        except Exception as e:
            print(f"Row failed: {e}")
            continue

    return players


# Scrape and insert data into SQLite
conn = create_connection("db/ktc.db")
time.sleep(5)
close_popup()
all_players = []

for page in range(10):  # Adjust for more pages
    print(f"Scraping page {page + 1}")
    all_players.extend(extract_player_data())
    try:
        next_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'pagination-arrow.arrow-right')))
        driver.execute_script("arguments[0].click();", next_btn)
        wait.until(EC.presence_of_element_located((By.ID, 'rankings-page-rankings')))
    except Exception:
        print("No more pages.")
        break

insert_player_data(conn, all_players)
driver.quit()
print(f"Scraped and stored {len(all_players)} records.")
