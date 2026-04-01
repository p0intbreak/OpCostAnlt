PYTHON ?= python
PIP ?= $(PYTHON) -m pip

.PHONY: install test run-pipeline build-dashboard

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

test:
	$(PYTHON) -m pytest

run-pipeline:
	$(PYTHON) scripts/run_pipeline.py

build-dashboard:
	$(PYTHON) scripts/build_dashboard.py

