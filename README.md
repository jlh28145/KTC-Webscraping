# KTC Webscraping

`KTC Webscraping` is a portfolio ETL project built around scraping KeepTradeCut dynasty rankings, normalizing the results, and persisting them into SQLite for downstream API and dashboard use.

The project is being developed intentionally as a proof repo for remote QA, SDET, and Quality Engineering roles. The goal is not just to scrape data, but to show engineering habits that translate well to production systems: layered design, deterministic parsing, testability, automation readiness, and a clear path to CI/CD.

## Why This Project Exists

This repo is meant to demonstrate:

- separation of extract, transform, and load concerns
- deterministic parsing logic that can be tested without a browser
- a CLI-driven workflow that is friendly to automation
- database-backed persistence instead of one-off script output
- a structure that can grow into CI, scheduled jobs, and hosted persistence

## Current Status

Current implementation status as of March 21, 2026:

- Phase 0 is complete: the repo runs locally with a documented setup flow
- Phase 1 is complete: the scraper has been refactored into a proper Python package
- A full live scrape now succeeds through the new CLI and writes to SQLite
- Phase 2 is planned next: deterministic tests for transform, load, and CLI behavior
- CI/CD workflow files are not implemented yet, but the codebase is now structured to support them cleanly

Most recent verified live run:

- Command: `./.venv/bin/python -m ktc_webscraping.cli --page-count 10`
- Result: `500` records written to `db/ktc.db`

## Architecture

The scraper is organized as a small ETL package:

- [ktc_webscraping/extract.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/extract.py): Selenium-driven page loading and ranking extraction
- [ktc_webscraping/transform.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/transform.py): parsing and normalization logic for ranking rows
- [ktc_webscraping/load.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/load.py): SQLite connection setup and inserts
- [ktc_webscraping/models.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/models.py): shared `PlayerRecord` and `ScrapeConfig` data models
- [ktc_webscraping/cli.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/cli.py): command-line entrypoint used for local runs and future automation

Supporting application surfaces already in the repo:

- [app/main.py](/home/vhinson/dev/KTC-Webscraping/app/main.py): FastAPI read API over the SQLite data
- [dashboard/dashboard.py](/home/vhinson/dev/KTC-Webscraping/dashboard/dashboard.py): Streamlit dashboard prototype
- [src/scraper.py](/home/vhinson/dev/KTC-Webscraping/src/scraper.py): compatibility shim to the package CLI

## ETL Flow

The current runtime flow is:

1. Selenium opens the KeepTradeCut rankings pages.
2. The extract layer waits for ranking rows and handles the landing modal.
3. The transform layer converts live page content into typed `PlayerRecord` objects.
4. The load layer inserts the normalized records into SQLite.
5. The FastAPI app and dashboard can read from the same persisted data.

This separation matters for CI/CD because it makes the transform and load layers testable in isolation, which is the foundation for reliable automated validation in GitHub Actions later.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python target:

- `3.12` via [`.python-version`](/home/vhinson/dev/KTC-Webscraping/.python-version)

## Running the Scraper

Preferred package entrypoint:

```bash
./.venv/bin/python -m ktc_webscraping.cli --page-count 10
```

Run with a visible browser:

```bash
./.venv/bin/python -m ktc_webscraping.cli --page-count 10 --headed
```

Backwards-compatible legacy entrypoint:

```bash
./.venv/bin/python -m src.scraper --page-count 10
```

The scraper writes to:

- SQLite database: `db/ktc.db`
- Table: `players`

## Data Model

The current record shape includes:

- `rank`
- `player_name`
- `position`
- `position_rank`
- `team`
- `age`
- `tier`
- `value`
- `scraped_at`

The current schema is intentionally simple. Historical deduplication, uniqueness rules, and upsert behavior are planned for the next persistence phase.

## Quality Strategy

This repo is being shaped around deterministic validation instead of fragile browser-only testing.

Current quality-oriented implementation choices:

- transform logic is separated from Selenium concerns
- modules can be imported without triggering a scrape
- the CLI provides a stable automation entrypoint
- the scraper now fails loudly with useful diagnostics instead of silently reporting empty results
- shared models make the boundaries between layers explicit

Planned next quality milestones:

- `pytest` coverage for transform parsing behavior
- SQLite-focused tests for schema creation and inserts
- CLI argument and import-safety tests
- regression protection for live-layout parsing edge cases

## CI/CD Roadmap

CI/CD is the main portfolio story this repo is growing toward.

The implementation path is deliberately staged:

1. Refactor the code into testable layers.
2. Add deterministic local tests.
3. Add GitHub Actions to run those tests on push and pull request.
4. Add scheduled execution for recurring scrapes.
5. Promote persistence from local SQLite to a hosted database with environment-based configuration.

That progression is useful in interviews because it mirrors real delivery work: stabilize the code first, then automate validation, then automate execution, then harden deployment boundaries.

Planned GitHub Actions scope:

- repository checkout
- Python environment setup
- dependency installation
- automated test execution
- failure on regression
- later additions such as linting, coverage reporting, and scheduled scrape runs

## Repository Layout

```text
.
├── app/
├── dashboard/
├── data/
│   └── samples/
├── ktc_webscraping/
│   ├── cli.py
│   ├── extract.py
│   ├── load.py
│   ├── models.py
│   └── transform.py
├── src/
├── requirements.txt
└── todo.md
```

## Local Data Handling

- `db/ktc.db` is local runtime state and should not be committed
- representative fixture/sample data belongs in the repo, such as [players_sample.json](/home/vhinson/dev/KTC-Webscraping/data/samples/players_sample.json)
- repeated scrape runs currently append rows
- duplicate prevention and upsert behavior are planned, not finished

## Roadmap

The implementation roadmap lives in [todo.md](/home/vhinson/dev/KTC-Webscraping/todo.md).

Immediate next phases:

- Phase 2: deterministic tests
- Phase 3: GitHub Actions CI
- Phase 4: stronger persistence design
- Phase 5: scheduled automation

## Resume-Style Talking Points

This project is being built to support conversations around:

- designing automation that is testable instead of tightly coupled to browser execution
- reducing scraping regressions with deterministic parsing tests
- building CI pipelines around meaningful checks instead of decorative automation
- treating data persistence, configuration, and scheduled execution as part of quality engineering
- evolving a script into a maintainable, automation-ready project structure
