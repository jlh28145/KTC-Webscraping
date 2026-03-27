# KTC Webscraping

[![CI](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/ci.yml/badge.svg)](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/ci.yml)
[![Coverage Gate](https://img.shields.io/badge/coverage-94%25-brightgreen)](/home/vhinson/dev/KTC-Webscraping/README.md)
[![Ruff](https://img.shields.io/badge/lint-ruff-blue)](/home/vhinson/dev/KTC-Webscraping/pyproject.toml)

`KTC Webscraping` is a portfolio ETL project built around scraping KeepTradeCut dynasty rankings, normalizing the results, and persisting them into SQLite for downstream API and dashboard use.

The project is being developed intentionally as a proof repo for remote QA, SDET, and Quality Engineering roles. The goal is not just to scrape data, but to show engineering habits that translate well to production systems: layered design, deterministic parsing, testability, automation readiness, and a clear path to CI/CD.

In practical terms, this repo is meant to tell a simple story quickly: take a browser-driven scrape, refactor it into a testable ETL package, enforce quality gates in CI, automate recurring execution, and keep the project readable enough that another engineer could extend it without guesswork.

## Why This Project Exists

This repo is meant to demonstrate:

- separation of extract, transform, and load concerns
- deterministic parsing logic that can be tested without a browser
- a CLI-driven workflow that is friendly to automation
- database-backed persistence instead of one-off script output
- a structure that can grow into CI, scheduled jobs, and hosted persistence

## Current Status

Current implementation status as of March 27, 2026:

- Phase 0 is complete: the repo runs locally with a documented setup flow
- Phase 1 is complete: the scraper has been refactored into a proper Python package
- Phase 2 is complete: deterministic tests now cover transform, extract, load, logging, and CLI behavior
- Phase 5 is complete: scheduled automation is active through GitHub Actions
- Phase 4 is complete: SQLite persistence now uses a historical `ktc_rankings` schema
- Phase 8 is complete: README positioning now emphasizes automation engineering, deterministic validation, and CI/CD enforcement
- Phase 9 is complete: code quality polish now includes clearer models, docstrings, logging, retries, and stricter load validation
- A full live scrape now succeeds through the new CLI and writes to SQLite
- `pytest` is now part of the local workflow and enforced in GitHub Actions
- GitHub Actions CI is active and passing on the repository
- Ruff linting, formatting checks, and coverage enforcement are part of the CI path
- A scheduled scrape workflow is active for cron-based and manual automation runs
- Database configuration now supports local SQLite by default and environment-driven hosted DB readiness
- Phase 7 is complete: the CLI now supports a first-class `scrape` command, shared config, `.env.example`, and `Makefile` shortcuts
- Stretch goals now include shared logging configuration, sample dataset artifacts, and starter analytics queries
- Scrape execution now retries transient page failures before aborting the run

Most recent verified live run:

- Command: `./.venv/bin/python -m ktc_webscraping.cli --page-count 10`
- Result: `500` records written to `db/ktc.db`

Most recent verified test run:

- Command: `./.venv/bin/python -m pytest --cov --cov-report=term-missing --cov-fail-under=90`
- Result: 47 tests passing with 94.16% total coverage, aligned with the CI quality gate

## Workflow Overview

The repo is organized around one repeatable engineering loop:

1. Run the scraper locally through the CLI.
2. Normalize ranking rows into deterministic `PlayerRecord` objects.
3. Persist historical snapshots into SQLite.
4. Validate changes with Ruff and `pytest` before merge.
5. Let GitHub Actions rerun the same checks on push and pull request.
6. Let the scheduled workflow execute the scraper automatically and publish artifacts.

That flow matters for the portfolio story because it shows validation, automation, and persistence working together instead of existing as disconnected bullet points.

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

Optional local environment file:

```bash
cp .env.example .env
set -a && source .env && set +a
```

Simple task runner shortcuts:

```bash
make lint
make test
make scrape PAGE_COUNT=10
```

Python target:

- `3.12` via [`.python-version`](/home/vhinson/dev/KTC-Webscraping/.python-version)

## Running the Scraper

Preferred package entrypoint:

```bash
./.venv/bin/python -m ktc_webscraping.cli --page-count 10
```

Explicit `scrape` subcommand:

```bash
./.venv/bin/python -m ktc_webscraping.cli scrape --page-count 10
```

Run with bounded retry handling:

```bash
./.venv/bin/python -m ktc_webscraping.cli scrape --page-count 10 --retry-attempts 2
```

Run with a visible browser:

```bash
./.venv/bin/python -m ktc_webscraping.cli scrape --page-count 10 --headed
```

Backwards-compatible legacy entrypoint:

```bash
./.venv/bin/python -m src.scraper --page-count 10
```

The scraper writes to:

- SQLite database: `db/ktc.db`
- Table: `ktc_rankings`
- Legacy `players` table: retired

## Running Tests

Fast local validation:

```bash
make lint
make test
```

Direct commands:

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m ruff format --check .
./.venv/bin/python -m pytest --cov --cov-report=term-missing --cov-fail-under=90
```

These are the same quality gates enforced in GitHub Actions, which keeps local verification aligned with pull request expectations.

## Data Model

The current record shape includes:

- `scrape_date`
- `player_name`
- `position`
- `rank_overall`
- `rank_position`
- `team`
- `source`
- `age`
- `tier`
- `value`
- `scraped_at`

The SQLite persistence layer now stores historical ranking snapshots in `ktc_rankings`.
The uniqueness rule is based on `scrape_date`, `player_name`, and `source`, which allows historical rows to accumulate across days while preventing duplicates within the same scrape-date snapshot.

## Database Configuration

The project now supports environment-based database configuration paths:

- local default: `KTC_DB_PATH=db/ktc.db`
- explicit SQLite URL: `KTC_DATABASE_URL=sqlite:///db/ktc.db`
- future hosted Postgres path: `KTC_DATABASE_URL=postgresql://...`

Current Phase 6 behavior:

- SQLite is still the active local development and automation backend
- the load layer now recognizes Postgres-style URLs as part of the config model
- actual Postgres connectivity is intentionally deferred until hosted database provisioning is complete

## Hosted Database Direction

The recommended Phase 6 provider for this project is **Neon**.

Why Neon is the better fit here:

- it is designed specifically around serverless Postgres, which fits this repo's scheduled GitHub Actions runtime well
- branching is a first-class feature, which makes it easier to discuss safer schema changes and environment separation
- it keeps the hosted database story focused on Postgres itself rather than a broader application platform
- it maps cleanly to the existing `KTC_DATABASE_URL` configuration path already in this repo

Supabase is also a solid option, but Neon is the more direct fit for a project whose next step is hosted Postgres rather than a broader backend platform.

## Quality Strategy

This repo is being shaped around deterministic validation instead of fragile browser-only testing.

Current quality-oriented implementation choices:

- transform logic is separated from Selenium concerns
- modules can be imported without triggering a scrape
- the CLI provides a stable automation entrypoint
- the scraper now fails loudly with useful diagnostics instead of silently reporting empty results
- shared models make the boundaries between layers explicit
- database behavior is covered with schema, insert, duplicate-prevention, and upsert tests
- historical snapshot behavior is covered in SQLite tests
- CI now enforces lint, format, and minimum coverage gates on every change

Current local test coverage includes:

- transform parsing behavior across legacy and current ranking layouts
- SQLite schema creation, inserts, duplicate prevention, and upsert behavior
- CLI argument parsing and config wiring
- import safety for the package and legacy compatibility shim
- regression protection for live-layout parsing edge cases

Current test command:

```bash
./.venv/bin/python -m pytest
```

Relevant local configuration examples:

```bash
./.venv/bin/python -m ktc_webscraping.cli --db-path db/ktc.db
./.venv/bin/python -m ktc_webscraping.cli scrape --db-path db/ktc.db
KTC_DATABASE_URL=sqlite:///db/ktc.db ./.venv/bin/python -m ktc_webscraping.cli
```

The shared runtime defaults live in [ktc_webscraping/config.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/config.py), which keeps environment-based setup logic separate from the CLI behavior.
Logging defaults live in [logging_config.py](/home/vhinson/dev/KTC-Webscraping/ktc_webscraping/logging_config.py) and can be adjusted with `KTC_LOG_LEVEL`.
Page retry behavior is controlled through the CLI `--retry-attempts` flag.

Current CI-quality gate commands:

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m ruff format --check .
./.venv/bin/python -m pytest --cov --cov-report=term-missing --cov-fail-under=90
```

## CI/CD Enforcement

CI/CD is one of the main portfolio signals in this project because it proves the repo is not relying on manual trust.

The implementation path is deliberately staged:

1. Refactor the code into testable layers.
2. Add deterministic local tests.
3. Add GitHub Actions to run those tests on push and pull request.
4. Add scheduled execution for recurring scrapes.
5. Promote persistence from local SQLite to a hosted database with environment-based configuration.

That progression is useful in interviews because it mirrors real delivery work: stabilize the code first, then enforce validation, then automate execution, then harden deployment boundaries.

Current GitHub Actions scope:

- repository checkout
- Python environment setup
- dependency installation
- Ruff linting
- formatting validation
- automated test execution for the core Python package
- coverage reporting in the job logs for the deterministic, CI-friendly package modules
- failure on lint, formatting, or test regression
- later additions such as scheduled scrape runs

Current workflow file:

- [ci.yml](/home/vhinson/dev/KTC-Webscraping/.github/workflows/ci.yml): runs Ruff and `pytest` with coverage on push and pull request using Python `3.12`
- [scrape.yml](/home/vhinson/dev/KTC-Webscraping/.github/workflows/scrape.yml): runs the scraper on a schedule or manual dispatch and uploads the SQLite DB plus a scrape summary as artifacts

## Scheduling And Automation

Scheduled automation now uses GitHub Actions:

- cron schedule: daily at `13:00 UTC`
- manual trigger: `workflow_dispatch`
- runtime entrypoint: `python -m ktc_webscraping.cli`
- artifact outputs: `artifacts/ktc.db` and `artifacts/scrape_summary.txt`

The workflow has been manually verified on `main`, and scheduled runs are now configured to execute from the default branch.

For this phase, the automation path uses database-backed persistence inside the workflow run and publishes the SQLite database as an artifact for inspection. That keeps the execution path aligned with the application architecture while avoiding Git commit-back of binary runtime state.

When hosted persistence is introduced, the workflow is already prepared to read `KTC_DATABASE_URL` from GitHub Secrets. If that secret is absent, the workflow continues using the artifact-backed SQLite path.

This matters for the remote QA / SDET story because it shows the repo handles both kinds of automation work:

- validation automation through CI on code changes
- operational automation through scheduled execution on a recurring cadence

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
- representative fixture/sample data belongs in the repo, such as [players_sample.json](/home/vhinson/dev/KTC-Webscraping/data/samples/players_sample.json) and [ktc_rankings_sample.csv](/home/vhinson/dev/KTC-Webscraping/data/samples/ktc_rankings_sample.csv)
- repeated scrape runs on different dates accumulate historical rows in `ktc_rankings`
- duplicate prevention and upsert behavior apply within the same `scrape_date` and `source`
- legacy `players` tables are automatically retired when the current load layer initializes the database
- load-time validation now rejects records missing required fields like `scrape_date`, `player_name`, `position`, or `source`

Inspect the local database:

```bash
sqlite3 db/ktc.db ".tables"
sqlite3 db/ktc.db "SELECT scrape_date, player_name, rank_overall, rank_position, team FROM ktc_rankings ORDER BY scrape_date DESC, rank_overall ASC LIMIT 20;"
```

Starter analytics queries live in [analytics_queries.sql](/home/vhinson/dev/KTC-Webscraping/data/samples/analytics_queries.sql) for quick SQLite exploration.

## Roadmap

The implementation roadmap lives in [todo.md](/home/vhinson/dev/KTC-Webscraping/todo.md).

Immediate next phases:

- Phase 6: hosted database readiness is deferred
- Phase 10: resume and interview readiness

## Resume-Style Talking Points

This project is being built to support conversations around:

- designing automation that is testable instead of tightly coupled to browser execution
- reducing scraping regressions with deterministic parsing tests
- building CI pipelines around meaningful checks instead of decorative automation
- treating data persistence, configuration, and scheduled execution as part of quality engineering
- evolving a script into a maintainable, automation-ready project structure
