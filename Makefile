.PHONY: help install setup start-ollama pull-model test-connection ask do dry-run clean lint format check-deps update-deps dev-install uninstall backup restore list-models switch-model

# Default target
.DEFAULT_GOAL := help

# Colors for output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Configuration
PYTHON := python3
POETRY := poetry
OLLAMA_MODEL := llama3.2:3b
OLLAMA_HOST := http://localhost:11434

help: ## Show this help message
	@echo "$(CYAN)Terminal Agent - Makefile Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup & Installation:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(install|setup|start|pull|test-connection)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Usage:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(ask|do|dry-run)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(clean|lint|format|check|update|dev)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Models & Configuration:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(list-models|switch-model)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Utilities:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(backup|restore|uninstall)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make install                    # First-time setup"
	@echo "  make ask QUERY=\"what is Python?\" # Ask a question"
	@echo "  make do QUERY=\"find readme\"      # Execute action"
	@echo "  make dry-run QUERY=\"delete logs\" # Preview actions"

# ============================================
# Setup & Installation
# ============================================

install: ## Install dependencies and set up the project
	@echo "$(GREEN)Installing dependencies with Poetry...$(NC)"
	$(POETRY) install
	@echo "$(GREEN)✓ Installation complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Run 'make start-ollama' (in new terminal)"
	@echo "  2. Run 'make pull-model' to download LLM"
	@echo "  3. Run 'make test-connection' to verify setup"

lock: ## Update and lock dependencies
	@echo "$(GREEN)Updating and locking dependencies...$(NC)"
	$(POETRY) lock
	@echo "$(GREEN)✓ Dependencies updated and locked!$(NC)"

setup: install start-ollama pull-model test-connection ## Complete setup: install, start Ollama, pull model, test

start-ollama: ## Start Ollama service (run in separate terminal)
	@echo "$(GREEN)Starting Ollama service...$(NC)"
	@echo "$(YELLOW)Note: This will keep running. Press Ctrl+C to stop.$(NC)"
	ollama serve

pull-model: ## Download the default LLM model (llama3.2:3b)
	@echo "$(GREEN)Pulling model: $(OLLAMA_MODEL)...$(NC)"
	ollama pull $(OLLAMA_MODEL)
	@echo "$(GREEN)✓ Model downloaded!$(NC)"

test-connection: ## Test connection to Ollama and verify setup
	@echo "$(GREEN)Testing Ollama connection...$(NC)"
	@if curl -s $(OLLAMA_HOST) > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Ollama is running at $(OLLAMA_HOST)$(NC)"; \
		ollama list; \
	else \
		echo "$(RED)✗ Cannot connect to Ollama$(NC)"; \
		echo "$(YELLOW)Please run 'make start-ollama' in another terminal$(NC)"; \
		exit 1; \
	fi

# ============================================
# Usage Commands
# ============================================

ask: ## Ask a question (no actions executed). Usage: make ask QUERY="your question"
	@if [ -z "$(QUERY)" ]; then \
		echo "$(RED)Error: QUERY is required$(NC)"; \
		echo "$(YELLOW)Usage: make ask QUERY=\"what is Python?\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Asking: $(QUERY)$(NC)"
	$(POETRY) run python agent_cli.py ask "$(QUERY)"

do: ## Execute an action. Usage: make do QUERY="find readme"
	@if [ -z "$(QUERY)" ]; then \
		echo "$(RED)Error: QUERY is required$(NC)"; \
		echo "$(YELLOW)Usage: make do QUERY=\"find readme\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Executing: $(QUERY)$(NC)"
	$(POETRY) run python agent_cli.py do "$(QUERY)"

dry-run: ## Preview actions without executing. Usage: make dry-run QUERY="delete files"
	@if [ -z "$(QUERY)" ]; then \
		echo "$(RED)Error: QUERY is required$(NC)"; \
		echo "$(YELLOW)Usage: make dry-run QUERY=\"delete files\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Dry run: $(QUERY)$(NC)"
	$(POETRY) run python agent_cli.py do --dry-run "$(QUERY)"

# ============================================
# Development & Maintenance
# ============================================

clean: ## Clean up temporary files and caches
	@echo "$(GREEN)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/ 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete!$(NC)"

lint: ## Run code quality checks (if linters installed)
	@echo "$(GREEN)Running linters...$(NC)"
	@if command -v ruff > /dev/null; then \
		ruff check .; \
	elif command -v flake8 > /dev/null; then \
		flake8 .; \
	else \
		echo "$(YELLOW)No linter found. Install with: poetry add --group dev ruff$(NC)"; \
	fi

format: ## Format code (if formatter installed)
	@echo "$(GREEN)Formatting code...$(NC)"
	@if command -v ruff > /dev/null; then \
		ruff format .; \
	elif command -v black > /dev/null; then \
		black .; \
	else \
		echo "$(YELLOW)No formatter found. Install with: poetry add --group dev ruff$(NC)"; \
	fi

check-deps: ## Check for outdated dependencies
	@echo "$(GREEN)Checking dependencies...$(NC)"
	$(POETRY) show --outdated

update-deps: ## Update dependencies to latest versions
	@echo "$(GREEN)Updating dependencies...$(NC)"
	$(POETRY) update
	@echo "$(GREEN)✓ Dependencies updated!$(NC)"

dev-install: ## Install with development dependencies
	@echo "$(GREEN)Installing with dev dependencies...$(NC)"
	$(POETRY) install --with dev
	@echo "$(GREEN)✓ Dev installation complete!$(NC)"

# ============================================
# Model Management
# ============================================

list-models: ## List all available Ollama models
	@echo "$(GREEN)Available Ollama models:$(NC)"
	@ollama list

switch-model: ## Switch to a different model. Usage: make switch-model MODEL=llama3.2:7b
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: MODEL is required$(NC)"; \
		echo "$(YELLOW)Usage: make switch-model MODEL=llama3.2:7b$(NC)"; \
		echo "$(YELLOW)Available models:$(NC)"; \
		ollama list; \
		exit 1; \
	fi
	@echo "$(GREEN)Pulling model: $(MODEL)...$(NC)"
	ollama pull $(MODEL)
	@echo "$(YELLOW)Update service/llm_client.py to use: $(MODEL)$(NC)"
	@echo "$(YELLOW)Change line: self.model = \"$(MODEL)\"$(NC)"

# ============================================
# Utilities
# ============================================

backup: ## Backup configuration and important files
	@echo "$(GREEN)Creating backup...$(NC)"
	@mkdir -p backups
	@tar -czf backups/terminal-agent-backup-$$(date +%Y%m%d-%H%M%S).tar.gz \
		--exclude='backups' \
		--exclude='.venv' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		. 2>/dev/null || true
	@echo "$(GREEN)✓ Backup created in backups/$(NC)"
	@ls -lh backups/ | tail -1

restore: ## Restore from latest backup. Usage: make restore BACKUP=filename.tar.gz
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)Error: BACKUP is required$(NC)"; \
		echo "$(YELLOW)Available backups:$(NC)"; \
		ls -lh backups/ 2>/dev/null || echo "No backups found"; \
		echo "$(YELLOW)Usage: make restore BACKUP=terminal-agent-backup-YYYYMMDD-HHMMSS.tar.gz$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring from backup: $(BACKUP)$(NC)"
	@tar -xzf backups/$(BACKUP)
	@echo "$(GREEN)✓ Restore complete!$(NC)"

uninstall: ## Uninstall the project and clean up
	@echo "$(YELLOW)This will remove all installed dependencies and caches.$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "$(GREEN)Uninstalling...$(NC)"; \
		$(POETRY) env remove --all 2>/dev/null || true; \
		make clean; \
		echo "$(GREEN)✓ Uninstalled!$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

# ============================================
# Quick Examples
# ============================================

example-search: ## Example: Search for files
	$(POETRY) run python agent_cli.py do "find readme file"

example-list: ## Example: List directory contents
	$(POETRY) run python agent_cli.py do "list files in current directory"

example-info: ## Example: Get file information
	$(POETRY) run python agent_cli.py do "show me information about pyproject.toml"

example-summarize: ## Example: Summarize a file
	$(POETRY) run python agent_cli.py do "summarize README.md"

example-search-content: ## Example: Search within files
	$(POETRY) run python agent_cli.py do "search for 'def' in python files"

# ============================================
# Diagnostics
# ============================================

diagnose: ## Run diagnostics to check system status
	@echo "$(CYAN)=== System Diagnostics ===$(NC)"
	@echo ""
	@echo "$(GREEN)Python version:$(NC)"
	@$(PYTHON) --version || echo "$(RED)Python not found$(NC)"
	@echo ""
	@echo "$(GREEN)Poetry version:$(NC)"
	@$(POETRY) --version || echo "$(RED)Poetry not found$(NC)"
	@echo ""
	@echo "$(GREEN)Ollama status:$(NC)"
	@if curl -s $(OLLAMA_HOST) > /dev/null 2>&1; then \
		echo "$(GREEN)✓ Ollama is running$(NC)"; \
		ollama list; \
	else \
		echo "$(RED)✗ Ollama is not running$(NC)"; \
		echo "$(YELLOW)Run 'make start-ollama' in another terminal$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)Installed dependencies:$(NC)"
	@$(POETRY) show --tree | head -20 || echo "$(RED)Dependencies not installed$(NC)"

# ============================================
# Advanced
# ============================================

shell: ## Open a poetry shell with activated environment
	@echo "$(GREEN)Opening poetry shell...$(NC)"
	$(POETRY) shell

run-python: ## Run python in poetry environment
	$(POETRY) run python

test: ## Run tests (if test suite exists)
	@echo "$(GREEN)Running tests...$(NC)"
	@if [ -d "tests" ] && [ "$$(ls -A tests)" ]; then \
		$(POETRY) run pytest tests/ -v; \
	else \
		echo "$(YELLOW)No tests found in tests/ directory$(NC)"; \
	fi

coverage: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	@if [ -d "tests" ] && [ "$$(ls -A tests)" ]; then \
		$(POETRY) run pytest tests/ --cov=. --cov-report=html --cov-report=term; \
		echo "$(GREEN)Coverage report generated in htmlcov/$(NC)"; \
	else \
		echo "$(YELLOW)No tests found in tests/ directory$(NC)"; \
	fi

watch: ## Watch for file changes and run tests (requires pytest-watch)
	@echo "$(GREEN)Watching for changes...$(NC)"
	$(POETRY) run ptw tests/
