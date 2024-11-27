# Dynasty Rankings Scraper

This Python script automates the process of scraping dynasty rankings from [KeepTradeCut](https://keeptradecut.com). It uses Selenium to navigate through multiple pages of rankings, extracts player data, and saves the results to a CSV file.

## Features

- Scrapes player rankings, names, positions, teams, ages, tiers, and values.
- Handles popups dynamically to ensure uninterrupted data extraction.
- Supports pagination to scrape data across multiple pages.
- Saves extracted data in a timestamped CSV file for easy access.

## Requirements

The script uses the following Python libraries:

- `time`
- `pandas`
- `datetime`
- `selenium`
- `webdriver_manager`

Ensure you have Python 3.7 or higher installed.

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   Create a `requirements.txt` file with the following content:
   ```
   pandas
   selenium
   webdriver-manager
   ```

## Usage

1. Update the `url` variable in the script if necessary to point to the desired page on KeepTradeCut.

2. Run the script:
   ```bash
   python scrape_dynasty_rankings.py
   ```

3. The script will:
   - Navigate through pages of rankings.
   - Handle popups dynamically.
   - Extract player data and save it to a timestamped CSV file.

4. The saved file will be located in the same directory as the script, with a filename like:
   ```
   dynasty_rankings_YYYYMMDD_HHMMSS.csv
   ```

## Key Points

- The script is configured with an explicit wait of 60 seconds to ensure all elements load properly before interaction.
- It uses dynamic selectors for elements like popups and pagination buttons.
- By default, it scrapes 10 pages of rankings. You can adjust the number of pages by modifying the `range(10)` in the script.

## Debugging Tips

- If the script encounters issues with elements not being found, ensure the website's structure hasn't changed.
- You can uncomment the line `chrome_options.add_argument("--headless")` to run the browser in headless mode (no UI).
- Adjust the sleep timer (`time.sleep(5)`) to account for slower or faster page loads.

## Disclaimer

This script is intended for educational purposes only. Ensure you comply with the website's terms of service and avoid overloading their servers with excessive requests.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

