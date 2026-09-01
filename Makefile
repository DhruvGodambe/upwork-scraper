.DEFAULT_GOAL := help

UV ?= uv

.PHONY: help install check test lint format-check typecheck validate validate-config validate-login hooks security

help:
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Synchronize the locked uv environment
	$(UV) sync --locked

check: test lint format-check typecheck ## Run the complete local quality check suite

test: ## Run automated tests
	$(UV) run pytest

lint: ## Run Ruff lint checks
	$(UV) run ruff check .

format-check: ## Verify formatting without changing files
	$(UV) run ruff format --check .

typecheck: ## Run mypy
	$(UV) run mypy upwork_scraper

validate: validate-config ## Validate local configuration and browser discovery

validate-config: ## Validate configuration without logging in
	$(UV) run upwork-scraper --check-config

validate-login: ## Perform the live Upwork login validation
	$(UV) run upwork-scraper --validate-login

hooks: ## Install maintainer/contributor pre-commit hooks
	$(UV) run pre-commit install

security: ## Scan Git history for secrets (requires Gitleaks)
	gitleaks git --redact .
