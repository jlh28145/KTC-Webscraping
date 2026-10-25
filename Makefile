.PHONY: install lock lint format test scrape api dashboard ci

PYTHON ?= ./.venv/bin/python
PAGE_COUNT ?= 10
DB_PATH ?= db/ktc.db
HEADED ?= 0
API_PORT ?= 8000

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install --no-deps -e .

# Regenerate the pinned lock file from pyproject.toml (requires uv). Releases from the last
# 14 days are skipped so the lock never pins a version that is brand new or not yet mirrored.
lock:
	uv pip compile pyproject.toml --extra dev --python-version 3.12 --upgrade --exclude-newer "14 days" \
		--quiet --custom-compile-command "make lock" -o requirements.txt

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .

test:
	$(PYTHON) -m pytest --cov --cov-report=term-missing --cov-fail-under=90

scrape:
	$(PYTHON) -m ktc_webscraping.cli scrape --page-count $(PAGE_COUNT) --db-path $(DB_PATH) $(if $(filter 1 true TRUE yes YES,$(HEADED)),--headed,)

api:
	KTC_DB_PATH=$(DB_PATH) $(PYTHON) -m uvicorn app.main:app --reload --port $(API_PORT)

dashboard:
	KTC_API_URL=http://localhost:$(API_PORT) $(PYTHON) -m streamlit run dashboard/dashboard.py

ci: lint test
