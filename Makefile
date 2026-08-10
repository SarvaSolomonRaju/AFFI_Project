# ============================================================================
#  FloodAI - Production Makefile
#  Upper Sonoita Creek pilot (Patagonia, AZ - HUC-12 150503010204)
# ============================================================================
PY      ?= python
PIP     ?= pip
PYTEST  ?= pytest

.DEFAULT_GOAL := help

.PHONY: help install data local-assets infrastructure forecast map dashboard all test lint clean veryclean docker-build docker-run docker-up docker-down serve-api frontend-install frontend-test frontend-test-e2e

help:
	@echo "FloodAI - Real-data flood forecasting pipeline"
	@echo ""
	@echo "  make install     - install Python dependencies"
	@echo "  make data        - acquire FEMA + USGS data and build flood library"
	@echo "  make local-assets - download OSM roads/buildings, tag with 100-yr flood depth, build infrastructure GeoJSON"
	@echo "  make forecast    - run Task 4 (probabilistic) and Task 5 (benchmarking)"
	@echo "  make map         - rebuild interactive Leaflet/Folium map"
	@echo "  make dashboard   - rebuild full HTML dashboard"
	@echo "  make serve-api   - run the FastAPI backend on http://127.0.0.1:8000 (docs at /docs)"
	@echo "  make all         - full end-to-end pipeline (data + forecast + map)"
	@echo "  make test        - run pytest (102 tests expected to pass)"
	@echo "  make clean       - remove outputs/ and pycache"
	@echo "  make veryclean   - also remove data/ (forces full re-download)"
	@echo "  make docker-build / docker-run - single-container API image workflow"
	@echo "  make docker-up   - one command: API + frontend + scheduler, http://localhost:3000"
	@echo "  make docker-down - stop the docker-up stack"

install:
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

data:
	$(PY) scripts/00_run_all.py --only data

local-assets:
	$(PY) scripts/14_build_local_assets.py
	$(PY) scripts/15_build_infrastructure.py

infrastructure:
	$(PY) scripts/15_build_infrastructure.py

forecast:
	$(PY) scripts/00_run_all.py --only forecast

map:
	$(PY) -m src.dashboard.interactive_map
	$(PY) scripts/build_dashboard.py

dashboard: map

serve-api:
	AFFI_AUTH_DISABLED=true uvicorn src.api.server:app --host 127.0.0.1 --port 8000 --reload

all:
	$(PY) scripts/00_run_all.py

test:
	$(PYTEST) tests/ -q
	$(MAKE) frontend-test

frontend-install:
	cd frontend && npm install

frontend-test:
	cd frontend && npm run typecheck && npm run test

frontend-test-e2e:
	@echo "Requires 'make serve-api' running separately (AFFI_AUTH_DISABLED=true)"
	cd frontend && npm run test:e2e

lint:
	$(PY) -m pyflakes src/ scripts/ || true

clean:
	rm -rf outputs/_map_layer_*.png outputs/__pycache__ src/**/__pycache__ scripts/__pycache__ .pytest_cache
	find . -name "*.pyc" -delete

veryclean: clean
	rm -rf data/fema_nfhl data/fema_fis data/usgs data/terrain data/flood_library_real

docker-build:
	docker build -t floodai:latest .

docker-run:
	docker run --rm -p 8000:8000 -v $$(pwd)/outputs:/app/outputs floodai:latest

docker-up:
	docker compose up --build -d
	@echo "Frontend: http://localhost:3000  |  API docs: http://localhost:8000/docs"

docker-down:
	docker compose down
