import time
import pandas as pd
from datetime import datetime  # Import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Setup Selenium Chrome WebDriver
chrome_options = Options()
#chrome_options.add_argument("--headless")  # Runs Chrome in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Explicit wait object with a timeout of 60 seconds
wait = WebDriverWait(driver, 60)

# Navigate to the website
url = "https://keeptradecut.com/dynasty-rankings?page=0&filters=QB|WR|RB|TE|RDP&format=2"
driver.get(url)

# Function to extract player data from a single page
def extract_player_data():
    players = []
    
    # Ensure that the rankings table is loaded
    rankings_table = wait.until(EC.presence_of_element_located((By.ID, 'rankings-page-rankings')))
    
    # Find all player rows within the rankings table
    player_rows = rankings_table.find_elements(By.CLASS_NAME, 'onePlayer')
    
    # Wait until all 50 player rows are loaded (adjust if the number of players differs)
    wait.until(lambda driver: len(player_rows) >= 50)

    for row in player_rows:
        try:
            rank = row.find_element(By.CLASS_NAME, 'rank-number').text
            # Extract player name only from the <a> tag
            player_name = row.find_element(By.TAG_NAME, 'a').text
            # Extract position and split it into position type and rank
            position_full = row.find_element(By.CLASS_NAME, 'position').text
            
            if not 'PICK' in position_full:
                team = row.find_element(By.CLASS_NAME, 'player-team').text
                # Extract age and remove 'y.o.'
                age_text = row.find_element(By.CLASS_NAME, 'age').text
                age = age_text.replace(' y.o.', '')  # Remove ' y.o.'
                
                # Split the position into alphabetic part (position) and numeric part (position rank)
                position = ''.join(filter(str.isalpha, position_full))  # Extract alphabetic part (e.g., QB, WR)
                position_rank = ''.join(filter(str.isdigit, position_full))  # Extract numeric part (e.g., 1, 10)
            else:
                team = 'None'
                age = 'None'
                position = position_full
                position_rank = 'None'
                
            tier = row.find_element(By.CLASS_NAME, 'player-tier').text
            value = row.find_element(By.CLASS_NAME, 'value').text
            players.append([rank, player_name, position, position_rank, team, age, tier, value])
        except Exception as e:
            print(f"Error extracting row data: {e}")
            continue  # In case of missing data, skip the row
    
    return players

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
        

# Loop to navigate through pages and scrape data
all_players_data = []
for page in range(10):  # Adjust as needed for more pages
    print(f"Scraping page {page + 1}")
    
    time.sleep(5)
    # Handle the popup before extracting player data
    close_popup()
    
    # Extract player data
    all_players_data.extend(extract_player_data())
    
    # Find and click the right arrow button for the next page
    try:
        next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'pagination-arrow.arrow-right')))
        driver.execute_script("arguments[0].click();", next_button)
        
        # Wait for the next page to load by ensuring the rankings table is present again
        wait.until(EC.presence_of_element_located((By.ID, 'rankings-page-rankings')))
        
    except Exception as e:
        print(f"Error navigating to next page: {e}")
        break  # If there's an error, stop the loop

# Convert the data to a pandas DataFrame
columns = ['Rank', 'Player Name', 'Position', 'Position Rank', 'Team', 'Age', 'Tier', 'Value']
df = pd.DataFrame(all_players_data, columns=columns)

# Generate a timestamp for the filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS
filename = f'dynasty_rankings_{timestamp}.csv'  # Create the filename with timestamp

# Save to CSV
df.to_csv(filename, index=False)

# Close the WebDriver
driver.quit()

print(df.head())  # Display the first few rows of the dataframe
print(f"Data saved to {filename}")  # Print confirmation with the filename
