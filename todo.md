## Goal
Turn this repo into a credible proof project for remote QA / SDET / Quality Engineering roles by demonstrating:
- automation architecture
- deterministic test design
- CI/CD integration
- scheduled execution
- database-backed persistence
- maintainable engineering practices

## Current Status

- Phase 0 is complete
- Phase 1 is complete
- Phase 2 is complete
- Live Phase 1 scrape is verified through `./.venv/bin/python -m ktc_webscraping.cli --page-count 10`
- Most recent verified full run inserted `500` records into `db/ktc.db`
- `pytest` coverage is in place for transform, load, and CLI behavior
- Phase 3 is the next implementation focus
- CI/CD workflows are planned but not implemented yet

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

- [ ] Create `.github/workflows/ci.yml`
- [ ] Trigger workflow on push
- [ ] Trigger workflow on pull request
- [ ] Add repository checkout step
- [ ] Add Python setup step
- [ ] Add dependency installation step
- [ ] Add test execution step
- [ ] Fail workflow when tests fail
- [ ] Verify workflow passes from a clean environment

### Optional CI upgrades
- [ ] Add Ruff or flake8
- [ ] Add formatting check if desired
- [ ] Add coverage reporting
- [ ] Add minimum coverage threshold
- [ ] Add badge(s) to README after CI is stable

**Definition of done**
- Every code change is automatically validated
- Repo shows CI discipline publicly
- This becomes visible proof of engineering maturity

---

## Phase 4 - Add Local Database Persistence

- [ ] Create initial SQLite database integration
- [ ] Define `ktc_rankings` schema with fields such as:
  - [ ] `scrape_date`
  - [ ] `player_name`
  - [ ] `position`
  - [ ] `rank_overall`
  - [ ] `rank_position`
  - [ ] `team`
  - [ ] `source`
- [ ] Decide on primary key or uniqueness logic
- [ ] Implement insert / upsert strategy
- [ ] Prevent duplicate records for the same scrape date and player
- [ ] Verify historical rows can accumulate over time
- [ ] Add configuration for local DB path
- [ ] Document how to inspect the SQLite database locally

**Definition of done**
- Data is stored in a structured database
- Historical scraping becomes possible
- Project moves beyond one-off output files

---

## Phase 5 - Add Scheduled Automation

- [ ] Create `.github/workflows/scrape.yml`
- [ ] Add cron schedule for automatic runs
- [ ] Add manual `workflow_dispatch` trigger
- [ ] Make scheduled job run the CLI entrypoint
- [ ] Ensure scheduled job installs dependencies correctly
- [ ] Decide persistence path for automation:
  - [ ] CSV commit-back approach
  - [ ] or database-backed persistence
- [ ] Handle secrets securely if external services are used
- [ ] Add basic logging / output visibility for scheduled runs
- [ ] Verify workflow can run without manual intervention

**Definition of done**
- Pipeline runs on a schedule
- Scraping is automated, not dependent on you babysitting it like some cursed houseplant

---

## Phase 6 - Prepare for Hosted Database Upgrade

- [ ] Evaluate Neon vs Supabase for hosted Postgres
- [ ] Choose one provider
- [ ] Create hosted Postgres database
- [ ] Add environment variable support for connection settings
- [ ] Store secrets in GitHub Secrets
- [ ] Adapt `load.py` for Postgres compatibility
- [ ] Validate inserts / upserts against hosted DB
- [ ] Keep SQLite as the local dev option if practical
- [ ] Document local vs cloud configuration paths

**Definition of done**
- Repo demonstrates cloud-ready persistence design
- You can talk about config, secrets, and environment separation in interviews without sounding rehearsed

---

## Phase 7 - Create a Professional CLI and Dev Experience

- [ ] Make `cli.py` support clear commands or flags
- [ ] Add at least one standard run command to README
- [ ] Support local run flow end-to-end
- [ ] Support optional output destination selection
- [ ] Add helpful error messages
- [ ] Ensure exceptions do not fail silently
- [ ] Keep logs readable and useful
- [ ] Make project setup straightforward for another engineer

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
- [ ] Add scheduling / automation section
- [X] Add database persistence section
- [X] Add setup instructions
- [X] Add local run instructions
- [ ] Add test run instructions
- [ ] Add workflow overview
- [X] Add future enhancements section

### README positioning
- [X] Frame the project as an automation engineering artifact
- [X] Emphasize deterministic validation
- [ ] Emphasize CI/CD enforcement
- [X] Emphasize maintainability and modularity
- [X] Use language that maps to remote QA / SDET roles
- [X] Avoid overselling Selenium as the headline achievement

**Definition of done**
- A recruiter or hiring manager can understand the project in 2 to 3 minutes
- The README sells the engineering story without sounding like résumé fan fiction

---

## Phase 9 - Polish Code Quality

- [ ] Standardize naming conventions
- [ ] Remove dead code
- [ ] Remove commented-out junk
- [ ] Add docstrings where useful
- [ ] Add type hints where practical
- [ ] Improve function boundaries
- [ ] Reduce duplicate logic
- [ ] Improve error handling
- [ ] Keep imports organized
- [ ] Keep config separate from logic
- [ ] Make data models explicit and readable

**Definition of done**
- Code is easier to review, explain, and maintain
- Repo reflects deliberate engineering decisions

---

## Phase 10 - Make It Resume and Interview Ready

### Resume translation
- [ ] Write 3 to 5 resume bullets based on the finished repo
- [ ] Focus bullets on architecture, validation, CI/CD, automation, and persistence
- [ ] Quantify what you can honestly quantify
- [ ] Keep wording aligned to remote QA / SDET roles

### Interview readiness
- [ ] Prepare a 60-second project summary
- [ ] Prepare a 2-minute technical walkthrough
- [ ] Be ready to explain:
  - [ ] Why ETL separation matters
  - [ ] Why transform tests were prioritized
  - [ ] Why Selenium was not the main CI test target
  - [ ] Why SQLite came before hosted Postgres
  - [ ] How GitHub Actions improved reliability
  - [ ] How scheduling changes the system design
- [ ] Be ready to discuss tradeoffs and future improvements

### Portfolio readiness
- [ ] Pin the repo on GitHub if it becomes one of your best proof projects
- [ ] Ensure commit history looks consistent
- [ ] Make sure repo name and description are clean
- [ ] Add topics/tags on GitHub if helpful

**Definition of done**
- The repo supports your remote job narrative directly
- You can explain it clearly without rambling or sounding fake

---

## Recommended Build Order

- [ ] 1. Activate repo
- [ ] 2. Refactor architecture
- [ ] 3. Write transform tests
- [ ] 4. Add load tests with SQLite
- [ ] 5. Add CI workflow
- [ ] 6. Add scheduled automation
- [ ] 7. Upgrade to hosted Postgres
- [ ] 8. Polish README and interview story

---

## Stretch Goals

- [ ] Add coverage badge
- [ ] Add lint badge
- [ ] Add sample dataset artifact
- [ ] Add Makefile or simple task runner
- [ ] Add `.env.example`
- [ ] Add lightweight configuration module
- [ ] Add logging configuration
- [ ] Add retry handling around scraping if needed
- [ ] Add data quality checks before load
- [ ] Add simple analytics query examples against the database

---

## What This Repo Should Prove When Finished

- [ ] You can design modular automation systems
- [ ] You can write deterministic tests around meaningful logic
- [ ] You understand CI/CD validation patterns
- [ ] You can automate recurring execution
- [ ] You can persist and manage structured data
- [ ] You can present engineering work in a way remote employers actually care about
