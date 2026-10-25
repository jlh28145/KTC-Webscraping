# KTC Webscraping

[![CI](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/ci.yml/badge.svg)](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/ci.yml)
[![Scheduled Scrape](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/scrape.yml/badge.svg)](https://github.com/jlh28145/KTC-Webscraping/actions/workflows/scrape.yml)
[![Coverage gate](https://img.shields.io/badge/coverage%20gate-%E2%89%A590%25-brightgreen)](.coveragerc)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-blue)](pyproject.toml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](.python-version)

A tested ETL pipeline that takes a daily snapshot of [KeepTradeCut](https://keeptradecut.com) dynasty fantasy-football rankings. Each run stores the rankings as history in SQLite or Postgres and serves them through a read-only API.

The scraper is the easy part. This repo is a quality-engineering project. It shows how to make an automation that depends on a live, changing website **testable, deterministic in CI, and dependable on a schedule**.

## What this project demonstrates

- **Layered design that can be tested.** Extract, transform and load are separate modules. Parsing is pure and runs without a browser, and Selenium sits behind a narrow interface that tests replace with fakes.
- **Deterministic tests over brittle end-to-end ones.** 124 tests run in about 2 seconds without network access or a browser (7 of them against a throwaway Postgres container). That includes a golden-file test against real KeepTradeCut markup, so a site redesign fails CI instead of quietly lowering data quality.
- **CI as a quality gate.** Every push and pull request runs Ruff lint, a format check, and the tests with a 90% coverage floor that counts every module, plus a smoke test of the installed command.
- **Unattended scheduled runs.** A daily GitHub Actions job scrapes about 500 rankings, carries the database forward between runs to build history, and publishes a stable one-snapshot artifact for a downstream repo.
- **Resilience learned from production.** Retries, pacing and per-page failure isolation were each added in response to observed live-site behavior, and each one has a regression test (see [Reliability design](#reliability-design)).
- **Portable persistence.** One schema and one idempotent upsert run on SQLite locally and on Postgres. The Postgres path is integration-tested in CI against a real `postgres:17` service container.
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
    R --> L --> DB[(SQLite or Postgres<br/>ktc_rankings)]
    DB --> API[FastAPI<br/>app/main.py] --> D[Streamlit<br/>dashboard]
    CLI[ktc-scrape CLI] --> Extract
```

| Module | Responsibility |
| --- | --- |
| [`ktc_webscraping/cli.py`](ktc_webscraping/cli.py) | `ktc-scrape` entry point: argument parsing, config wiring, exit codes |
| [`ktc_webscraping/config.py`](ktc_webscraping/config.py) | `KTC_*` environment defaults, read when the CLI runs (never at import) |
| [`ktc_webscraping/extract.py`](ktc_webscraping/extract.py) | Browser control, waits, retries, pacing, block-page detection |
| [`ktc_webscraping/transform.py`](ktc_webscraping/transform.py) | Pure parsing of ranking rows into typed `PlayerRecord`s |
| [`ktc_webscraping/load.py`](ktc_webscraping/load.py) | Schema creation, record validation, idempotent upserts (SQLite and Postgres dialects) |
| [`ktc_webscraping/export.py`](ktc_webscraping/export.py) | Cuts the latest snapshot and run summary out of the history database for the published artifact |
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
| Load (SQLite) | 22 | Real SQLite in `tmp_path`: schema, unique index, upserts, history across dates, validation failures, per-dialect SQL |
| Load (Postgres) | 7 | Real `postgres:17` service container in CI: schema parity, type round-trips, upserts, history, CLI end-to-end. Skipped locally unless `KTC_TEST_POSTGRES_URL` is set, and a **hard failure** in CI if the URL is missing, so the tests can't silently skip |
| API | 24 | FastAPI `TestClient` against a seeded two-snapshot database: filters, pagination, input validation, and 404/422/501/503 paths |
| CLI and config | 33 | Argument parsing, environment defaults, exit codes, the quality gate's accept/reject/override paths, and the installed `ktc-scrape` entry point |
| Quality gate | 11 | Each check on its own: failed pages, fallback parsers, the row floor, duplicate players and ranks |

Coverage is enforced at 90% over **every** module, including the Selenium layer (currently about 98%). Coverage is a floor, not the goal: tests target behaviors that broke, or could break, against the live site.

## CI/CD and scheduled automation

**[`ci.yml`](.github/workflows/ci.yml)** runs on every push and pull request with a Postgres 17 service container: install from the lock, Ruff lint, format check, pytest (SQLite and Postgres) with the coverage gate, then a smoke test of `ktc-scrape --help`. All of it runs in about 35 seconds.

**[`scrape.yml`](.github/workflows/scrape.yml)** runs daily (13:00 UTC) or on manual dispatch:

1. Restores the previous run's database from the Actions cache, so `ktc_rankings` keeps building history. If the cache misses (evicted after 7 days unused, a failed save, or a new `actions/cache` major), it restores the newest `ktc-history` artifact instead. If neither exists, the job fails rather than silently starting an empty history; a manual run with `start_fresh` begins a new one on purpose.
2. Runs `ktc-scrape` for 10 pages (about 500 rankings). A **quality gate** rejects a degraded run before anything is stored: failed pages, pages read by a fallback parser, fewer than 98% of the expected rows, or duplicate players or ranks. The job then fails (exit 3) and publishes nothing, so downstream consumers keep the last good snapshot.
3. Publishes two artifacts, each kept for 14 days:
   - `scheduled-scrape-<run id>`: `ktc.db` with **only the latest snapshot**, plus `scrape_summary.txt` (row counts, history size, top 10). This is a contract: a downstream repo downloads the newest one daily and commits its `ktc.db`, so the file stays one snapshot (about 95 KB) instead of growing every day.
   - `ktc-history-<run id>`: the full history database.

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
| Retries, skips and fallbacks kept a degraded run green, and its artifact became what downstream synced | A quality gate rejects the run instead (exit 3, nothing stored or published); `--allow-degraded` is a deliberate manual override |
| Rankings can shift while the 10 pages load, so one player is listed on two pages and another is missed. The old name key quietly merged the two rows | Players are keyed by KeepTradeCut id, the gate flags the duplicate, and the run is re-scraped once (`--quality-retries`) before being rejected |

## Configuration

Environment variables (see [`.env.example`](.env.example)) set the defaults, and CLI flags override them.

| Variable | Default | Purpose |
| --- | --- | --- |
| `KTC_DB_PATH` | `db/ktc.db` | SQLite file for the scraper and the API |
| `KTC_DATABASE_URL` | unset | `sqlite:///…` or `postgresql://…`; takes precedence over `KTC_DB_PATH` |
| `KTC_PAGE_COUNT` | `10` | Pages to scrape (50 rankings each) |
| `KTC_RETRY_ATTEMPTS` | `2` | Retries per page after the first failure |
| `KTC_LOG_LEVEL` | `INFO` | Log verbosity |
| `KTC_API_URL` | `http://localhost:8000` | API address used by the dashboard |

To load into Postgres instead of SQLite, run `ktc-scrape --database-url postgresql://user:pass@host/db`.

Run `ktc-scrape --help` for the tuning flags (`--row-count-tolerance`, `--row-count-poll-timeout`, `--page-delay-seconds`, `--min-row-ratio`, `--allow-degraded`, `--headed`, …).

## Data model

Each run writes one snapshot to `ktc_rankings`, with the same columns on SQLite and Postgres. A unique index on `(scrape_date, player_key, source)` keeps one row per player per day. `player_key` is `ktc:<id>`, using KeepTradeCut's own player id from the profile link, so two players who share a name stay separate. Rows from before ids were collected, or from a text fallback parser, use `name:<player name>`. Re-running the same day replaces that day's snapshot: players who dropped out since the earlier run are removed, and the rest are updated in place. Different days accumulate history. Every record in a run shares a single UTC timestamp, so a run that crosses midnight still lands on one `scrape_date`.

| Column | Notes |
| --- | --- |
| `scrape_date`, `scraped_at` | UTC snapshot date and full timestamp |
| `player_name`, `position`, `team` | Team codes follow KeepTradeCut (`KCC`, `SFO`, `FA`, …) |
| `ktc_player_id`, `player_key` | KeepTradeCut's numeric player id (e.g. `1415` from `/players/jahmyr-gibbs-1415`) and the identity key built from it |
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

The API opens the database read-only and returns 503 with a clear message if no scrape has been stored yet. It reads from SQLite. A Postgres URL returns 501 until the API gets its own Postgres path.

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

- **Hosted Postgres for the scheduled scrape.** The Postgres load path is built and tested. Pointing the daily job at Neon only needs a `KTC_DATABASE_URL` repo secret, and then history no longer depends on the Actions cache. For now the scheduled scrape stays on SQLite.
- **Postgres reads in the API**, so the API and dashboard can serve the hosted history.
- Detailed phase-by-phase history and decisions are in [`todo.md`](todo.md).
