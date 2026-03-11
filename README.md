# KTC Webscraping

Proof-of-concept project for scraping KeepTradeCut dynasty rankings into SQLite, with a small FastAPI app and Streamlit dashboard in the repo.

## Current Baseline

Phase 0 is now verified against the local workspace:

- Python target: `3.12` via [`.python-version`](/home/vhinson/dev/KTC-Webscraping/.python-version)
- Local environment: `.venv`
- Dependencies install successfully from [requirements.txt](/home/vhinson/dev/KTC-Webscraping/requirements.txt)
- Baseline scraper entrypoint: [src/scraper.py](/home/vhinson/dev/KTC-Webscraping/src/scraper.py)

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Baseline Run

```bash
python -m src.scraper
```

Current runtime inputs:

- Source URL: `https://keeptradecut.com/dynasty-rankings?page=0&filters=QB|WR|RB|TE|RDP&format=2`
- Database path: `db/ktc.db`
- Page target: 10 pages
- Browser dependency: local Chrome plus `webdriver-manager`

Current outputs:

- SQLite database at `db/ktc.db`
- Table: `players`
- Existing local baseline data: 500 rows already present in the database from a prior scrape

Known issues from the March 11, 2026 baseline run:

- Dependency installation succeeds, but it requires network access to PyPI.
- The scraper now launches Chrome and Chromedriver successfully.
- The live scrape timed out after 120 seconds before inserting a fresh batch of rows.
- No new `players` rows were written during the timed verification run; the latest `scraped_at` remained `2025-04-12T05:38:25.086550`.
- The API and dashboard code exist, but they were not validated in phase 0.

## Repo Layout

- [src/scraper.py](/home/vhinson/dev/KTC-Webscraping/src/scraper.py): Selenium scraper baseline
- [src/database.py](/home/vhinson/dev/KTC-Webscraping/src/database.py): SQLite setup and inserts
- [app/main.py](/home/vhinson/dev/KTC-Webscraping/app/main.py): FastAPI app
- [dashboard/dashboard.py](/home/vhinson/dev/KTC-Webscraping/dashboard/dashboard.py): Streamlit dashboard
- [todo.md](/home/vhinson/dev/KTC-Webscraping/todo.md): implementation roadmap

## Next Phase 0 Follow-up

The remaining cleanup is functional rather than setup-related: make the live scraper complete reliably, then tighten the README setup around the API and dashboard once those paths are verified.
