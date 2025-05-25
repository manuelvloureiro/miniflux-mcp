UV := $(shell command -v uv 2>/dev/null || echo "$$HOME/.local/bin/uv")
.DEFAULT_GOAL := help

.PHONY: help setup test test-quick lint format typecheck review clean

# ── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-z][a-z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

ensure-uv: ## Install uv if missing
	@if [ ! -x "$(UV)" ]; then \
		echo "uv not found — installing..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi

setup: ensure-uv ## Install dependencies and pre-commit hooks
	$(UV) sync --group dev
	$(UV) run pre-commit install
	@echo "\033[32m✓ Ready. Run 'make test' to verify.\033[0m"

# ── Quality ──────────────────────────────────────────────────────────────────

lint: ## Lint with ruff
	$(UV) run ruff check src/ tests/

format: ## Format with ruff
	$(UV) run ruff format src/ tests/

typecheck: ## Type-check with pyright
	$(UV) run pyright

test: ## Run tests with coverage (80% gate)
	$(UV) run pytest --cov --cov-report=term-missing --cov-fail-under=80 -q

test-quick: ## Run tests — stop on first failure
	$(UV) run pytest -q --maxfail=1 --disable-warnings

review: lint typecheck test ## Run all quality gates

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts
	@find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" \) -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf htmlcov .coverage dist build *.egg-info 2>/dev/null || true
	@echo "\033[32m✓ Clean.\033[0m"
