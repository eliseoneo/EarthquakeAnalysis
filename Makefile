.PHONY: test eval-phase1 eval-phase2 eval-phase3 eval-phase4 eval-phase5 eval-all eval-full evaluate ui ui-uvicorn project-venezuela layer-a-run layer-a-run-usgs layer-a-ui layer-b-run layer-b-ui

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

eval-phase4:
	$(PYTHON) scripts/evaluate_phase4.py

eval-phase5:
	$(PYTHON) scripts/evaluate_phase5.py

eval-all: eval-phase1 eval-phase2 eval-phase3 eval-phase4 eval-phase5

eval-full:
	$(PYTHON) scripts/evaluate_all.py --full

evaluate: test eval-all

ui:
	$(PYTHON) scripts/comparative_charts.py

ui-uvicorn:
	$(PYTHON) scripts/comparative_charts.py --use-uvicorn

project-venezuela:
	$(PYTHON) scripts/project_venezuela_probabilities.py

layer-a-run:
	$(PYTHON) scripts/layer_a_pipeline.py

layer-a-run-usgs:
	$(PYTHON) scripts/layer_a_pipeline.py --download-usgs --no-fixtures

layer-a-ui:
	$(PYTHON) scripts/layer_a_ui.py

layer-b-run:
	$(PYTHON) scripts/layer_b_pipeline.py

layer-b-ui:
	$(PYTHON) scripts/layer_b_ui.py

