# KTC Webscraping

[![CI](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/ci.yml/badge.svg)](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/ci.yml)
[![Scheduled Scrape](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/scrape.yml/badge.svg)](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/scrape.yml)
[![Coverage gate](https://img.shields.io/badge/coverage%20gate-%E2%89%A590%25-brightgreen)](.coveragerc)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-blue)](pyproject.toml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](.python-version)

A tested ETL pipeline that takes a daily snapshot of [KeepTradeCut](https://keeptradecut.com) dynasty fantasy-football rankings. Each run stores the rankings as history in SQLite and serves them through a read-only API.

The scraper is the easy part. This repo is a quality-engineering project. It shows how to make an automation that depends on a live, changing website **testable, deterministic in CI, and dependable on a schedule**.

## What this project demonstrates

- **Layered design that can be tested.** Extract, transform and load are separate modules. Parsing is pure and runs without a browser, and Selenium sits behind a narrow interface that tests replace with fakes.
- **Deterministic tests over brittle end-to-end ones.** 114 tests run in about 2 seconds without network access or a browser. That includes a golden-file test against real KeepTradeCut markup, so a site redesign fails CI instead of quietly lowering data quality.
- **CI as a quality gate.** Every push and pull request runs Ruff lint, a format check, and the tests with a 90% coverage floor that counts every module, plus a smoke test of the installed command.
- **Unattended scheduled runs.** A daily GitHub Actions job scrapes about 500 rankings, carries the database forward between runs to build history, and publishes the database and a run summary as artifacts.
- **Resilience learned from production.** Retries, pacing and per-page failure isolation were each added in response to observed live-site behavior, and each one has a regression test (see [Reliability design](#reliability-design)).
- **Reproducible environments.** Dependencies are declared in `pyproject.toml` and locked with `uv`, skipping releases newer than 14 days.

## Architecture

```mermaid
flowchart TB
    subgraph Extract["extract.py"]
        S[Selenium + headless Chrome] -->|page HTML| E[retry · pacing · page-level isolation]
    end
    subgraph Transform["transform.py (pure)"]
        P[HTML parser<br/>legacy + current layouts] -.->|fallback| T[text-layout parser]
    end
    subgraph Load["load.py"]
        L[validate → upsert<br/>UNIQUE scrape_date, player, source]
    end
    E --> P
    P --> R([PlayerRecord])
    T --> R
    R --> L --> DB[(SQLite<br/>ktc_rankings)]
    DB --> API[FastAPI<br/>app/main.py] --> D[Streamlit<br/>dashboard]
    CLI[ktc-scrape CLI] --> Extract
```

| Module | Responsibility |
| --- | --- |
| [`ktc_webscraping/cli.py`](ktc_webscraping/cli.py) | `ktc-scrape` entry point: argument parsing, config wiring, exit codes |
| [`ktc_webscraping/config.py`](ktc_webscraping/config.py) | `KTC_*` environment defaults, read when the CLI runs (never at import) |
| [`ktc_webscraping/extract.py`](ktc_webscraping/extract.py) | Browser control, waits, retries, pacing, block-page detection |
| [`ktc_webscraping/transform.py`](ktc_webscraping/transform.py) | Pure parsing of ranking rows into typed `PlayerRecord`s |
| [`ktc_webscraping/load.py`](ktc_webscraping/load.py) | Schema creation, record validation, idempotent upserts |
| [`ktc_webscraping/models.py`](ktc_webscraping/models.py) | Frozen dataclasses shared across layers |
| [`app/main.py`](app/main.py) | Read-only FastAPI service over the stored snapshots |
| [`dashboard/dashboard.py`](dashboard/dashboard.py) | Streamlit demo UI on top of the API |

## Quick start

Requires Python 3.12 and Google Chrome.

```bash
python3 -m venv .venv && source .venv/bin/activate
make install                 # pinned deps from requirements.txt + editable package

ktc-scrape --page-count 10   # ~500 rankings into db/ktc.db
make api                     # http://localhost:8000/docs
make dashboard               # in a second terminal
```

Run the same checks CI runs:

```bash
make ci                      # ruff check, ruff format --check, pytest with the 90% coverage gate
```

Inspect the data directly. Starter queries, such as the biggest risers between snapshots, are in [`data/samples/analytics_queries.sql`](data/samples/analytics_queries.sql).

```bash
sqlite3 db/ktc.db "SELECT scrape_date, player_name, position, rank_overall, value
                   FROM ktc_rankings ORDER BY scrape_date DESC, rank_overall LIMIT 10;"
```

## Testing strategy

The live website is the least dependable part of the system, so it's the one thing CI never touches. Everything around it is exercised with realistic inputs.

| Layer | Tests | Approach |
| --- | ---: | --- |
| Transform | 25 | Pure-function tests on HTML and text fixtures, including a **golden-file snapshot of real KeepTradeCut markup** ([`tests/fixtures/`](tests/fixtures/)), malformed rows, draft picks, and names like `Kenneth Walker III` |
| Extract | 20 | Selenium replaced by small fake drivers and waits: retry exhaustion, Selenium timeouts, short-page tolerance, block-page detection, every parsing fallback, driver setup |
| Load | 19 | Real SQLite in `tmp_path`: schema, unique index, upserts, history across dates, validation failures |
| API | 24 | FastAPI `TestClient` against a seeded two-snapshot database: filters, pagination, input validation, and 404/422/501/503 paths |
| CLI and config | 26 | Argument parsing, environment defaults, exit codes, and the installed `ktc-scrape` entry point |

Coverage is enforced at 90% over **every** module, including the Selenium layer (currently about 98%). Coverage is a floor, not the goal: tests target behaviors that broke, or could break, against the live site.

## CI/CD and scheduled automation

**[`ci.yml`](.github/workflows/ci.yml)** runs on every push and pull request: install from the lock, Ruff lint, format check, pytest with the coverage gate, then a smoke test of `ktc-scrape --help`. All of it runs in about 35 seconds.

**[`scrape.yml`](.github/workflows/scrape.yml)** runs daily (13:00 UTC) or on manual dispatch:

1. Restores the previous run's database from the Actions cache, so `ktc_rankings` keeps building history.
2. Runs `ktc-scrape` for 10 pages (about 500 rankings).
3. Writes a summary (row counts, distinct snapshot dates, top 10) and uploads the database and summary as artifacts kept for 14 days.

Runtime state stays out of Git: the database lives in the cache and in artifacts, never in commits.

## Reliability design

Most of these came from failures observed on the live site or in scheduled runs; the rest from code review. All are covered by tests.

| Observed behavior | Response |
| --- | --- |
| KeepTradeCut often serves a fully loaded page a few rows short of 50, with no block markers | `--row-count-tolerance` (default 10) accepts a near-complete page instead of failing the run |
| Waiting longer never fixes a short page, but each retry burned the full 60-second page-load timeout, turning a 1.5-minute run into 15+ minutes | A separate short `--row-count-poll-timeout` (default 15 seconds) for the row-count check |
| Rapid sequential requests from shared CI IPs seemed to get trimmed | `--page-delay-seconds` pacing with random jitter between pages |
| One bad page discarded the whole run | Failures are isolated per page; the run fails only if every page fails |
| Selenium timeouts bypassed the retry loop and ended the run | Retries cover `TimeoutException` and `WebDriverException` as well as parse failures |
| The site redesigned its row markup and the HTML parser silently matched nothing | The parser handles both layouts, and a golden-file test on captured live markup guards against the next change |
| Pages that never populate | Anti-bot markers (captcha, Cloudflare, …) are detected and reported in the failure message |

## Configuration

Environment variables (see [`.env.example`](.env.example)) set the defaults, and CLI flags override them.

| Variable | Default | Purpose |
| --- | --- | --- |
| `KTC_DB_PATH` | `db/ktc.db` | SQLite file for the scraper and the API |
| `KTC_DATABASE_URL` | unset | `sqlite:///…` URL; takes precedence over `KTC_DB_PATH` |
| `KTC_PAGE_COUNT` | `10` | Pages to scrape (50 rankings each) |
| `KTC_RETRY_ATTEMPTS` | `2` | Retries per page after the first failure |
| `KTC_LOG_LEVEL` | `INFO` | Log verbosity |
| `KTC_API_URL` | `http://localhost:8000` | API address used by the dashboard |

Run `ktc-scrape --help` for the tuning flags (`--row-count-tolerance`, `--row-count-poll-timeout`, `--page-delay-seconds`, `--headed`, …).

## Data model

Each run writes one snapshot to `ktc_rankings`. A unique index on `(scrape_date, player_name, source)` makes re-running the same day idempotent (an upsert), while different days accumulate history. Every record in a run shares a single UTC timestamp, so a run that crosses midnight still lands on one `scrape_date`.

| Column | Notes |
| --- | --- |
| `scrape_date`, `scraped_at` | UTC snapshot date and full timestamp |
| `player_name`, `position`, `team` | Team codes follow KeepTradeCut (`KCC`, `SFO`, `FA`, …) |
| `rank_overall`, `rank_position` | `NULL` for draft picks, which KeepTradeCut lists without a rank |
| `age`, `tier`, `value` | `value` is KeepTradeCut's trade value (top player = 9999) |

A sample in the current schema is in [`data/samples/players_sample.json`](data/samples/players_sample.json).

## API

`make api`, then open `http://localhost:8000/docs` for the interactive schema.

| Endpoint | Returns |
| --- | --- |
| `GET /rankings` | Latest snapshot by default; filter by `scrape_date`, `position`, `team`, `tier`; paginate with `page`/`limit` |
| `GET /rankings/{id}` | One stored row, or 404 |
| `GET /player?name=` | A player's history across every snapshot, newest first |
| `GET /scrape-dates` | Stored snapshot dates |
| `GET /health` | Liveness check that doesn't need a database |

The API opens the database read-only and returns 503 with a clear message if no scrape has been stored yet.

## Repository layout

```text
ktc_webscraping/    ETL package and ktc-scrape CLI
app/                FastAPI read API
dashboard/          Streamlit demo
tests/              pytest suite and captured live-markup fixtures
data/samples/       sample records and analytics SQL
.github/workflows/  CI and the scheduled scrape
pyproject.toml      package metadata, extras, tool config
requirements.txt    pinned lock generated by `make lock`
```

## Roadmap

- **Hosted Postgres.** Add a Postgres load path (Neon) behind the existing `KTC_DATABASE_URL` setting, tested in CI against a Postgres service container, so history no longer depends on the Actions cache.
- Detailed phase-by-phase history and decisions are in [`todo.md`](todo.md).
