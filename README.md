# KTC Webscraping

Proof-of-concept project for scraping KeepTradeCut dynasty rankings into SQLite, with a small FastAPI app and Streamlit dashboard in the repo.

## Current Baseline

Phase 0 is now verified against the local workspace:

- Python target: `3.12` via [`.python-version`](/home/vhinson/dev/KTC-Webscraping/.python-version)
- Local environment: `.venv`
- Dependencies install successfully from [requirements.txt](/home/vhinson/dev/KTC-Webscraping/requirements.txt)
- Baseline scraper entrypoint: [src/scraper.py](/home/vhinson/dev/KTC-Webscraping/src/scraper.py)
- API entrypoint: [app/main.py](/home/vhinson/dev/KTC-Webscraping/app/main.py)

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

The scraper writes to a local SQLite file at `db/ktc.db`. That file is for local runtime state and should not be committed back to Git.

Current runtime inputs:

- Source URL: `https://keeptradecut.com/dynasty-rankings?page=0&filters=QB|WR|RB|TE|RDP&format=2`
- Database path: `db/ktc.db`
- Page target: 10 pages
- Browser dependency: local Chrome plus `webdriver-manager`

Current outputs:

- SQLite database at `db/ktc.db`
- Table: `players`
- Verified full scrape result: 500 rows inserted in a single 10-page run
- Current local database row count after verification: 1,296

Verified behavior from the March 11, 2026 repair pass:

- Dependency installation succeeds, but it requires network access to PyPI.
- `python -m src.scraper` completes a full 10-page run successfully.
- The scraper now uses direct page URLs and static HTML parsing to avoid Selenium pagination and stale-element failures.
- The old duplicate scraper files were removed so there is one clear scraper entrypoint.
- The FastAPI app now resolves the SQLite path from the repo instead of depending on the shell working directory.

Current caveats:

- `db/ktc.db` is still an accumulated local database, so repeated runs append more rows.
- There is no deduplication or upsert behavior yet.
- The Streamlit dashboard file exists, but it has only been syntax-checked, not exercised end-to-end in this phase.

## Data Handling

- Keep the live SQLite database local only: `db/ktc.db` is ignored by Git and treated as runtime state.
- Keep representative sample data in the repo for docs and tests: [data/samples/players_sample.json](/home/vhinson/dev/KTC-Webscraping/data/samples/players_sample.json).
- If you need to inspect local data, query `db/ktc.db` directly or export ad hoc snapshots outside the repo.
- If you want historical retention later, move it to a hosted database or object storage instead of growing the Git history with binary DB files.

If `db/ktc.db` or old CSV snapshots were already tracked earlier, remove them from the Git index once and keep the files locally:

```bash
git rm --cached db/ktc.db dynasty_rankings_20250412_052408.csv
```

## Repo Layout

- [src/scraper.py](/home/vhinson/dev/KTC-Webscraping/src/scraper.py): Selenium scraper baseline
- [src/database.py](/home/vhinson/dev/KTC-Webscraping/src/database.py): SQLite setup and inserts
- [app/main.py](/home/vhinson/dev/KTC-Webscraping/app/main.py): FastAPI app
- [dashboard/dashboard.py](/home/vhinson/dev/KTC-Webscraping/dashboard/dashboard.py): Streamlit dashboard
- [todo.md](/home/vhinson/dev/KTC-Webscraping/todo.md): implementation roadmap

## Next Phase 0 Follow-up

The repo is now in a workable pre-phase-1 state: one scraper entrypoint, successful local scraping, and a fixed API DB path. The next step is structural refactoring, not emergency runtime repair.
