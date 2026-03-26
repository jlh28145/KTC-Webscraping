.PHONY: install lint format test scrape ci

PYTHON ?= ./.venv/bin/python
PAGE_COUNT ?= 10
DB_PATH ?= db/ktc.db
HEADED ?= 0

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .

test:
	$(PYTHON) -m pytest --cov --cov-report=term-missing --cov-fail-under=90

scrape:
	$(PYTHON) -m ktc_webscraping.cli scrape --page-count $(PAGE_COUNT) --db-path $(DB_PATH) $(if $(filter 1 true TRUE yes YES,$(HEADED)),--headed,)

ci: lint test
