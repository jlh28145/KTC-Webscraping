## Goal
Turn this repo into a credible proof project for remote QA / SDET / Quality Engineering roles by demonstrating:
- automation architecture
- deterministic test design
- CI/CD integration
- scheduled execution
- database-backed persistence
- maintainable engineering practices

## Current Status

As of 2026-10-25:

- Phases 0–5, 7–16 and the hardening pass (17–27, below) are complete; Phase 6 is partly on hold by decision
- 203 deterministic tests (30 against Postgres), 99% coverage over every module, 90% gate in CI; `main` requires a green CI check
- Every scheduled scrape since Oct 1 has succeeded; each run passes a quality gate before anything is stored or published
- The published artifact is a one-snapshot contract with a downstream app, which is notified by `repository_dispatch` and syncs within seconds
- Remaining open items: hosted Postgres for the daily job (on hold), and interview rehearsal (personal)

---

## Phase 0 - Activate the Repo

- [X] Unarchive the repository
- [X] Confirm the repo is public and visible
- [X] Enable GitHub Actions for the repo
- [X] Verify Python version target for the project
- [X] Create or clean up `requirements.txt`
- [X] Create a local virtual environment
- [X] Install dependencies successfully
- [X] Run the current scraper locally to establish the baseline behavior
- [X] Document current inputs, outputs, and known issues
- [X] Add a `.gitignore` for Python, virtual envs, caches, and local DB files

**Definition of done**
- Repo runs locally without mystery steps
- Dependencies install cleanly
- Current script behavior is understood and documented

---

## Phase 1 - Refactor into a Real Project Structure

- [X] Create package structure:
  - [X] `ktc_webscraping/extract.py`
  - [X] `ktc_webscraping/transform.py`
  - [X] `ktc_webscraping/load.py`
  - [X] `ktc_webscraping/cli.py`
  - [X] `ktc_webscraping/models.py`
- [X] Move Selenium scraping logic into `extract.py`
- [X] Move parsing and cleaning logic into `transform.py`
- [X] Move persistence logic into `load.py`
- [X] Create a command-line entrypoint in `cli.py`
- [X] Define record shape / schema in `models.py`
- [X] Remove script-level side effects where possible
- [X] Make transform functions pure and deterministic
- [X] Pass data between layers using clear structures
- [X] Ensure modules are importable without executing the scraper
- [X] Keep file and function names readable and professional

**Definition of done**
- Extraction, transform, and load logic are separated
- Transform layer can be tested without Selenium
- Repo looks like an actual engineering project, not a loose script pile
- Full live scrape succeeds through the package CLI

---

## Phase 2 - Build Deterministic Test Coverage

### Test setup
- [X] Add `pytest`
- [X] Create `tests/` directory
- [X] Add `tests/test_transform.py`
- [X] Add `tests/test_load.py`
- [X] Add `tests/test_cli.py`
- [X] Add `pytest.ini`
- [X] Add any reusable fixtures needed
- [X] Use sample HTML or static inputs for transform tests

### Transform tests
- [X] Test successful HTML parsing
- [X] Test single-row parsing via `parse_player_row`
- [X] Test player name extraction
- [X] Test position extraction
- [X] Test overall rank extraction
- [X] Test position rank extraction
- [X] Test team extraction if available
- [X] Test `PICK` rows keep `position_rank` and team empty as expected
- [X] Test normalization of whitespace / formatting
- [X] Test malformed row handling
- [X] Test missing value handling
- [X] Test deterministic output shape
- [X] Test `PlayerRecord` field values and types
- [X] Test duplicate row handling if relevant in transform layer

### CLI and import safety tests
- [X] Test CLI argument parsing
- [X] Test config creation from CLI args
- [X] Test modules import without executing Selenium or a scrape
- [X] Test legacy `src.scraper` shim still resolves the package CLI entrypoint

### Load tests
- [X] Set up SQLite-based tests
- [X] Test table creation
- [X] Test insert behavior
- [X] Test inserts from `PlayerRecord` instances
- [X] Test upsert behavior
- [X] Test duplicate prevention
- [X] Test expected schema constraints
- [X] Test scrape date persistence
- [X] Test float persistence for `age` and `value`
- [X] Test behavior on empty inputs

### Test quality
- [X] Keep tests focused on logic, not browser behavior
- [X] Avoid brittle end-to-end Selenium assertions in CI
- [X] Use realistic fixture data
- [X] Make failures easy to understand
- [X] Keep naming clean and consistent

**Definition of done**
- `pytest` runs locally
- Core transform and load logic are regression protected
- Tests feel deliberate, not decorative

---

## Phase 3 - Add CI with GitHub Actions

Purpose: turn the current refactor plus deterministic tests into visible, recruiter-friendly proof of CI discipline.

- [X] Create `.github/workflows/ci.yml`
- [X] Trigger workflow on push
- [X] Trigger workflow on pull request
- [X] Add repository checkout step
- [X] Add Python setup step
- [X] Add dependency installation step
- [X] Add test execution step
- [X] Fail workflow when tests fail
- [X] Verify workflow passes from a clean environment

### Optional CI upgrades
- [X] Add Ruff or flake8
- [X] Add formatting check if desired
- [X] Add coverage reporting
- [X] Add minimum coverage threshold
- [X] Add badge(s) to README after CI is stable

**Definition of done**
- Every code change is automatically validated
- Repo shows CI discipline publicly
- This becomes visible proof of engineering maturity

---

## Phase 4 - Add Local Database Persistence

- [X] Create initial SQLite database integration
- [X] Define `ktc_rankings` schema with fields such as:
  - [X] `scrape_date`
  - [X] `player_name`
  - [X] `position`
  - [X] `rank_overall`
  - [X] `rank_position`
  - [X] `team`
  - [X] `source`
- [X] Decide on primary key or uniqueness logic
- [X] Implement insert / upsert strategy
- [X] Prevent duplicate records for the same scrape date and player
- [X] Verify historical rows can accumulate over time
- [X] Add configuration for local DB path
- [X] Document how to inspect the SQLite database locally

**Definition of done**
- Data is stored in a structured database
- Historical scraping becomes possible
- Project moves beyond one-off output files

---

## Phase 5 - Add Scheduled Automation

- [X] Create `.github/workflows/scrape.yml`
- [X] Add cron schedule for automatic runs
- [X] Add manual `workflow_dispatch` trigger
- [X] Make scheduled job run the CLI entrypoint
- [X] Ensure scheduled job installs dependencies correctly
- [X] Decide persistence path for automation:
  - ~~CSV commit-back approach~~ (not chosen: database-backed persistence instead)
- [X] or database-backed persistence
- [X] Handle secrets securely if external services are used (the downstream dispatch token and repo name are GitHub Secrets, and database passwords are masked in logs)
- [X] Add basic logging / output visibility for scheduled runs
- [X] Verify workflow can run without manual intervention

**Definition of done**
- Pipeline runs on a schedule
- Scraping is automated, not dependent on you babysitting it like some cursed houseplant

---

## Phase 6 - Prepare for Hosted Database Upgrade

Status (2026-10-19): the Postgres load path is complete and tested in CI against a `postgres:17` service container. Decision: the scheduled scrape stays on SQLite for now, so the GitHub secret and hosted Neon validation remain open.

- [X] Evaluate Neon vs Supabase for hosted Postgres
- [X] Choose one provider
- [X] Create hosted Postgres database
- [X] Add environment variable support for connection settings
- [ ] Store secrets in GitHub Secrets (on hold: scheduled scrape stays on SQLite)
- [X] Adapt `load.py` for Postgres compatibility
- [ ] Validate inserts / upserts against hosted DB (on hold; validated against a Postgres 17 service container in CI)
- [X] Keep SQLite as the local dev option if practical
- [X] Document local vs cloud configuration paths

**Definition of done**
- Repo demonstrates cloud-ready persistence design
- You can talk about config, secrets, and environment separation in interviews without sounding rehearsed

---

## Phase 7 - Create a Professional CLI and Dev Experience

- [X] Make `cli.py` support clear commands or flags
- [X] Add at least one standard run command to README
- [X] Support local run flow end-to-end
- [X] Support optional output destination selection
- [X] Add helpful error messages
- [X] Ensure exceptions do not fail silently
- [X] Keep logs readable and useful
- [X] Make project setup straightforward for another engineer

**Definition of done**
- Someone can clone the repo and understand how to run it
- The project feels usable, not just technically present

---

## Phase 8 - Improve README for Remote Job Positioning

### README core sections
- [X] Add project overview
- [X] Add architecture summary
- [X] Add ETL flow explanation
- [X] Add testing strategy section
- [X] Add CI/CD section
- [X] Add scheduling / automation section
- [X] Add database persistence section
- [X] Add setup instructions
- [X] Add local run instructions
- [X] Add test run instructions
- [X] Add workflow overview
- [X] Add future enhancements section

### README positioning
- [X] Frame the project as an automation engineering artifact
- [X] Emphasize deterministic validation
- [X] Emphasize CI/CD enforcement
- [X] Emphasize maintainability and modularity
- [X] Use language that maps to remote QA / SDET roles
- [X] Avoid overselling Selenium as the headline achievement

**Definition of done**
- A recruiter or hiring manager can understand the project in 2 to 3 minutes
- The README sells the engineering story without sounding like résumé fan fiction

---

## Phase 9 - Polish Code Quality

- [X] Standardize naming conventions
- [X] Remove dead code
- [X] Remove commented-out junk
- [X] Add docstrings where useful
- [X] Add type hints where practical
- [X] Improve function boundaries
- [X] Reduce duplicate logic
- [X] Improve error handling
- [X] Keep imports organized
- [X] Keep config separate from logic
- [X] Make data models explicit and readable

**Definition of done**
- Code is easier to review, explain, and maintain
- Repo reflects deliberate engineering decisions

---

## Phases 11–15 - Finish-Up Pass (from the October 2026 repo review)

- [X] Phase 11: retries cover Selenium exceptions; free-agent name/team split; one UTC timestamp per run; upserts refresh `scraped_at`; scheduled runs keep history (PR #10)
- [X] Phase 12: HTML parser supports KeepTradeCut's current layout, guarded by a golden-file fixture of real markup; config loaded when the CLI runs; dead files removed; `extract.py` counted in coverage (PR #11)
- [X] Phase 13: API reads shared config, opens the DB read-only, returns proper 404/503 status codes, defaults to the latest snapshot; 24 `TestClient` tests (PR #12)
- [X] Phase 14: `pyproject.toml` package with `ktc-scrape` entry point and extras; `uv`-generated lock with a 14-day release cooldown (PR #13)
- [X] Phase 15: README rewritten for hiring-manager readers with relative links and an architecture diagram (PR #14)
- [X] Phase 16: Postgres load path with SQLite/Postgres dialects, `postgres` extra, 7 integration tests against a CI service container that fail loudly if it's missing

---

## Phases 17–27 - Hardening Pass (October 2026)

Prompted by a downstream app that consumes the scheduled-scrape artifact, then by a review of what could still fail silently.

- [X] Phase 17: `todo.md` close-out (PR #16)
- [X] Phase 18: the published artifact is one snapshot again, with full history shipped as a separate `ktc-history` artifact; summary Top 10 fixed (PR #17)
- [X] Phase 19: a same-day rerun replaces that day's snapshot instead of mixing runs (PR #18)
- [X] Phase 20: actions pinned by commit SHA, Dependabot for GitHub Actions, `runpy` test warning fixed (PR #19)
- [X] Phase 21: quality gate rejects degraded runs before storing or publishing anything (exit 3) (PR #20)
- [X] Phase 22: history restored from the newest `ktc-history` artifact when the cache misses (PR #21)
- [X] Phase 23: players keyed by KeepTradeCut id with an in-place migration; one automatic re-scrape when the gate fails, after it caught a live mid-scrape ranking shift (PR #22)
- [X] Phase 24: API reads Postgres as well as SQLite, with every API test run on both; headless dashboard tests (PR #23)
- [X] Phase 25: `repository_dispatch` notifies the downstream app as soon as a snapshot is published (PR #24, plus the consumer's PR #23)
- [X] Phase 26: GitHub Actions major upgrades via Dependabot (PR #25)
- [X] Phase 27: `make lock` now upgrades; lock refreshed; Dependabot pip updates removed because per-pin bumps broke the resolver lock (PR #27)
- [X] Branch protection on `main`: PR plus green CI required
- [X] Verified end to end on 2026-10-25: scrape, gate, migration, publish, dispatch, and the consumer's sync and commit

---

## Phase 10 - Make It Resume and Interview Ready

### Resume translation
- [X] Write 3 to 5 resume bullets based on the finished repo
- [X] Focus bullets on architecture, validation, CI/CD, automation, and persistence
- [X] Quantify what you can honestly quantify
- [X] Keep wording aligned to remote QA / SDET roles

### Interview readiness
- [X] Prepare a 60-second project summary
- [X] Prepare a 2-minute technical walkthrough
- [X] Be ready to explain:
  - [X] Why ETL separation matters
  - [X] Why transform tests were prioritized
  - [X] Why Selenium was not the main CI test target
  - [X] Why SQLite came before hosted Postgres
  - [X] How GitHub Actions improved reliability
  - [X] How scheduling changes the system design
- [X] Be ready to discuss tradeoffs and future improvements

Resume bullets, scripts, answers, and known limits live in a private prep doc, outside this public repo. Remaining: rehearse them aloud.

### Portfolio readiness
- [X] Pin the repo on GitHub if it becomes one of your best proof projects
- [X] Ensure commit history looks consistent (reviewed; early commits left as-is rather than rewriting public history)
- [X] Make sure repo name and description are clean
- [X] Add topics/tags on GitHub if helpful

**Definition of done**
- The repo supports your remote job narrative directly
- You can explain it clearly without rambling or sounding fake

---

## Recommended Build Order

- [X] 1. Activate repo
- [X] 2. Refactor architecture
- [X] 3. Write transform tests
- [X] 4. Add load tests with SQLite
- [X] 5. Add CI workflow
- [X] 6. Add scheduled automation
- [ ] 7. Upgrade to hosted Postgres (load path done and tested; scheduled scrape stays on SQLite for now)
- [X] 8. Polish README (interview story remains in Phase 10)

---

## Stretch Goals

- [X] Add coverage badge
- [X] Add lint badge
- [X] Add sample dataset artifact
- [X] Add Makefile or simple task runner
- [X] Add `.env.example`
- [X] Add lightweight configuration module
- [X] Add logging configuration
- [X] Add retry handling around scraping if needed
- [X] Add data quality checks before load
- [X] Add simple analytics query examples against the database

---

## What This Repo Should Prove When Finished

Reviewed 2026-10-22 against the repo, CI, and GitHub.

- [X] You can design modular automation systems: separate ETL layers, Selenium behind an interface tests can fake, one load path for SQLite and Postgres, `ktc-scrape` entry point
- [X] You can write deterministic tests around meaningful logic: 127 tests in about 2.4 s with no network or browser, a golden-file test of real markup, 99% coverage with a 90% gate over every module
- [X] You understand CI/CD validation patterns: lint, format, test, and coverage gates on every change; Postgres tests that fail rather than skip; locked dependencies. Caveat: CI plus scheduled operations, no deployment step
- [X] You can automate recurring execution: daily scheduled scrape, 17 consecutive green runs (Oct 5–21, 2026), history carried forward between runs. Caveat: a partly degraded run still finishes green
- [X] You can persist and manage structured data: unique key, idempotent upserts, history across dates, validation before load, same schema on two databases. Caveat: rows are keyed on player name rather than a player ID
- [X] You can present engineering work in a way remote employers actually care about: README written for hiring managers, repo pinned with a current description and topics, private interview prep doc
