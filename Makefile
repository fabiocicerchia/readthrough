IMAGE ?= readthrough
TAG   ?= dev

.PHONY: help setup lint test build dist install uninstall docs selfscan clean run format analyze

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install the package (editable, with dev extras) and the pre-commit hook
	pip install -e ".[dev]"
	pre-commit install

lint: ## Run all pre-commit checks on the whole tree
	pre-commit run --all-files

test: ## Run the test suite
	python3 -m pytest -q

build: ## Build the container image (override IMAGE=, TAG=)
	docker build -t $(IMAGE):$(TAG) .

dist: ## Build the wheel and sdist into dist/
	python3 -m pip install --quiet --upgrade build
	python3 -m build

install: ## Install from this working tree onto your PATH (pipx, else pip --user)
	@if command -v pipx >/dev/null 2>&1; then \
		pipx install --force . ; \
	else \
		echo "pipx not found; falling back to pip --user" >&2 ; \
		python3 -m pip install --user --upgrade . ; \
	fi
	@command -v readthrough >/dev/null 2>&1 \
		|| echo 'installed, but not on PATH — add: export PATH="$$HOME/.local/bin:$$PATH"' >&2

uninstall: ## Remove it again
	@pipx uninstall readthrough 2>/dev/null || python3 -m pip uninstall -y readthrough

docs: ## Serve the documentation site locally
	pip install --require-hashes -r docs/requirements.txt
	mkdocs serve

selfscan: ## Audit this repo with itself, offline (no API calls, no cost)
	python3 -m readthrough scan . --fake --out /tmp/readthrough-selfscan

clean: ## Remove build, cache and scan output
	rm -rf build/ dist/ *.egg-info/ .ruff_cache/ .pytest_cache/ site/
	rm -rf readthrough-reports/
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

run: ## Run readthrough
	readthrough --help

format: ## Rewrite the sources to canonical form
	ruff format .

analyze: ## Type-check the package
	basedpyright
