.PHONY: test eval-phase1 eval-phase2 eval-phase3 eval-all eval-full evaluate ui ui-uvicorn

PYTHON := python3
ifneq ("$(wildcard .venv/bin/python3)","")
PYTHON := .venv/bin/python3
endif

test:
	$(PYTHON) -m pytest

eval-phase1:
	$(PYTHON) scripts/evaluate_phase1.py

eval-phase2:
	$(PYTHON) scripts/evaluate_phase2.py

eval-phase3:
	$(PYTHON) scripts/evaluate_phase3.py

eval-all: eval-phase1 eval-phase2 eval-phase3

eval-full:
	$(PYTHON) scripts/evaluate_all.py --full

evaluate: test eval-all

ui:
	$(PYTHON) scripts/comparative_charts.py

ui-uvicorn:
	$(PYTHON) scripts/comparative_charts.py --use-uvicorn

