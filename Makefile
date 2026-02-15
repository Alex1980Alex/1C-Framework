# PDF Vector & Graph Framework — Makefile
# Кросс-платформенные команды для разработки и деплоя

.DEFAULT_GOAL := help
SHELL := /bin/bash

# === Variables ===
PYTHON := python
UV := uv
VENV := .venv
SRC := src
TESTS := tests
API_PORT := 8000
UI_PORT := 7860

# Detect OS
ifeq ($(OS),Windows_NT)
    ACTIVATE := $(VENV)/Scripts/activate
    PIP := $(VENV)/Scripts/pip
    PYTHON_VENV := $(VENV)/Scripts/python
else
    ACTIVATE := $(VENV)/bin/activate
    PIP := $(VENV)/bin/pip
    PYTHON_VENV := $(VENV)/bin/python
endif

# ============================================================
#  Setup
# ============================================================

.PHONY: setup
setup: ## Install all dependencies (uses uv if available)
	@if command -v $(UV) >/dev/null 2>&1; then \
		echo "[uv] Creating venv..."; \
		$(UV) venv $(VENV); \
		echo "[uv] Installing dependencies..."; \
		$(UV) pip install -e ".[dev,qdrant,docling,morphology]"; \
	else \
		echo "[pip] Creating venv..."; \
		$(PYTHON) -m venv $(VENV); \
		echo "[pip] Installing dependencies..."; \
		$(PIP) install -e ".[dev,qdrant,docling,morphology]"; \
	fi
	@echo "[OK] Setup complete"

.PHONY: setup-all
setup-all: ## Install ALL optional dependencies
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) pip install -e ".[all,dev]"; \
	else \
		$(PIP) install -e ".[all,dev]"; \
	fi

# ============================================================
#  Development
# ============================================================

.PHONY: lint
lint: ## Run ruff linter
	$(PYTHON_VENV) -m ruff check $(SRC)/

.PHONY: lint-fix
lint-fix: ## Run ruff linter with auto-fix
	$(PYTHON_VENV) -m ruff check --fix $(SRC)/

.PHONY: format
format: ## Format code with ruff
	$(PYTHON_VENV) -m ruff format $(SRC)/

.PHONY: format-check
format-check: ## Check formatting without changes
	$(PYTHON_VENV) -m ruff format --check $(SRC)/

.PHONY: typecheck
typecheck: ## Run mypy type checking
	$(PYTHON_VENV) -m mypy $(SRC)/

.PHONY: docstrings
docstrings: ## Check docstring coverage (interrogate)
	$(PYTHON_VENV) -m interrogate $(SRC)/ -v

.PHONY: test
test: ## Run all tests
	$(PYTHON_VENV) -m pytest $(TESTS)/ -v

.PHONY: test-cov
test-cov: ## Run tests with coverage
	$(PYTHON_VENV) -m pytest $(TESTS)/ --cov=$(SRC) --cov-report=html --cov-report=term

.PHONY: test-fast
test-fast: ## Run tests excluding slow integration tests
	$(PYTHON_VENV) -m pytest $(TESTS)/ -v -m "not slow"

.PHONY: check
check: lint format-check typecheck docstrings test ## Run all checks (lint + format + typecheck + docstrings + tests)
	@echo "[OK] All checks passed"

# ============================================================
#  Run Services
# ============================================================

.PHONY: api
api: ## Start FastAPI server
	$(PYTHON_VENV) -m uvicorn src.api.app:app --host 0.0.0.0 --port $(API_PORT) --reload

.PHONY: ui
ui: ## Start Gradio UI
	$(PYTHON_VENV) -m src.cli.main ui

.PHONY: mcp
mcp: ## Start MCP server
	$(PYTHON_VENV) -m src.mcp_server

.PHONY: cli
cli: ## Show CLI help
	$(PYTHON_VENV) -m src.cli.main --help

# ============================================================
#  Docker
# ============================================================

.PHONY: docker-up
docker-up: ## Start all Docker services
	docker compose -f docker/docker-compose.yml up -d

.PHONY: docker-down
docker-down: ## Stop all Docker services
	docker compose -f docker/docker-compose.yml down

.PHONY: docker-build
docker-build: ## Build Docker image
	docker compose -f docker/docker-compose.yml build

.PHONY: docker-logs
docker-logs: ## Tail Docker logs
	docker compose -f docker/docker-compose.yml logs -f api

.PHONY: qdrant-up
qdrant-up: ## Start only Qdrant
	docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v qdrant_data:/qdrant/storage qdrant/qdrant:v1.12.0

.PHONY: qdrant-down
qdrant-down: ## Stop Qdrant
	docker stop qdrant && docker rm qdrant

# ============================================================
#  Indexing
# ============================================================

.PHONY: index
index: ## Index a PDF file (usage: make index PDF=path/to/file.pdf)
	$(PYTHON_VENV) -m src.cli.main index $(PDF)

.PHONY: reindex
reindex: ## Reindex via API (requires running API server)
	curl -X POST http://localhost:$(API_PORT)/documents/reindex

.PHONY: rebuild-bm25
rebuild-bm25: ## Rebuild BM25 FTS5 index
	curl -X POST http://localhost:$(API_PORT)/documents/rebuild-bm25

.PHONY: rebuild-sparse
rebuild-sparse: ## Rebuild sparse vectors in Qdrant
	curl -X POST http://localhost:$(API_PORT)/documents/rebuild-sparse

# ============================================================
#  Utilities
# ============================================================

.PHONY: clean
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info

.PHONY: clean-data
clean-data: ## Remove indexed data (requires re-indexing)
	@echo "WARNING: This will delete all indexed data!"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf data/vector_db data/bm25_index.db data/graph_store

.PHONY: health
health: ## Check API health
	curl -s http://localhost:$(API_PORT)/health | python -m json.tool

.PHONY: docs
docs: ## Open API docs in browser
	@echo "Opening http://localhost:$(API_PORT)/docs"
	@open http://localhost:$(API_PORT)/docs 2>/dev/null || \
		xdg-open http://localhost:$(API_PORT)/docs 2>/dev/null || \
		start http://localhost:$(API_PORT)/docs 2>/dev/null || \
		echo "Visit: http://localhost:$(API_PORT)/docs"

# ============================================================
#  Help
# ============================================================

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
