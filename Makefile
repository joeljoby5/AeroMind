# AeroMind - common tasks.  `make setup && make seed && make dev`
PYTHON   ?= python3
VENV     ?= .venv
BIN      := $(VENV)/bin
export PYTHONPATH := $(CURDIR):$(CURDIR)/backend
export DATABASE_URL ?= sqlite:///$(CURDIR)/aeromind.db

.PHONY: setup seed reseed train notebook evaluate test checklist jupyter dev backend frontend clean

setup:            ## create venv, install Python + frontend dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements.txt
	$(BIN)/python -m ipykernel install --user --name python3 >/dev/null 2>&1 || true
	cd frontend && npm install

seed:             ## create tables, 4 drones and the sample mission (idempotent)
	cd backend && ../$(BIN)/python -m app.seed

reseed:           ## wipe the database and seed again
	cd backend && ../$(BIN)/python -m app.seed --reset

train:            ## regenerate the dataset, retrain the energy model, re-execute the notebook
	$(BIN)/python -m ai.energy_model.generate_dataset
	$(BIN)/python -m ai.energy_model.train
	$(BIN)/python notebooks/build_notebook.py

notebook:         ## re-execute the notebook only
	$(BIN)/python notebooks/build_notebook.py

evaluate:         ## ML vs baseline over 200 random missions (writes docs/allocation_comparison.png)
	$(BIN)/python -m ai.evaluate_allocation

test:             ## AI + backend tests (frontend: type-check and build)
	$(BIN)/python -m pytest -q
	cd frontend && npx tsc --noEmit

checklist:        ## verify everything is demo-ready and print what is stubbed
	$(BIN)/python scripts/final_checklist.py

jupyter:          ## open the notebook in JupyterLab
	$(BIN)/jupyter lab notebooks/01_energy_model.ipynb

backend:          ## API on :8000
	$(BIN)/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload

frontend:         ## dashboard on :3000
	cd frontend && npm run dev

dev: seed         ## run API + dashboard together (SQLite, no Docker)
	@trap 'kill 0' INT TERM EXIT; \
	$(BIN)/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 & \
	(cd frontend && npm run dev) & \
	wait

clean:
	rm -f aeromind.db backend/aeromind.db
