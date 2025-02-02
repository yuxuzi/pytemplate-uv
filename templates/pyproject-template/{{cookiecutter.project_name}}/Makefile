# Detect the operating system
ifeq ($(OS),Windows_NT)
    VENV_ACTIVATE = .venv\Scripts\activate
    PYTHON = .venv\Scripts\python
    RM = rmdir /s /q
    MKDIR = mkdir
else
    VENV_ACTIVATE = . .venv/bin/activate
    PYTHON = .venv/bin/python
    RM = rm -rf
    MKDIR = mkdir -p
endif

# Global prerequisite to ensure virtual environment is activated
.PHONY: venv-activate
venv-activate:
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Creating..."; \
		uv venv; \
	fi
	@echo "Activating virtual environment..."
	@$(VENV_ACTIVATE)

# Apply venv-activate as a global prerequisite
.PHONY: all
all: venv-activate

# Define common commands
PYTEST = pytest
UV_PIP_INSTALL = uv pip install
BLACK = black
RUFF = ruff
PDOC = pdoc
BUILD = python -m build
TWINE = twine

# Targets
.PHONY: help setup dev start run lint lint-fix format format-check test test-cov clean docs build publish

help: venv-activate
	@echo " {{cookiecutter.project_name}} - Project Management Commands"
	@echo ""
	@echo "Development:"
	@echo "  make setup    - Create virtual environment and install dependencies"
	@echo "  make dev      - Set up development environment (pre-commit, etc.)"
	@echo "  make start    - Start the application"
	@echo "  make run      - Alias for 'start'"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint     - Run code linting"
	@echo "  make lint-fix - Run linter with auto-fix"
	@echo "  make format   - Format code using Black"
	@echo "  make format-check - Check code formatting"
	@echo ""
	@echo "Testing:"
	@echo "  make test     - Run tests"
	@echo "  make test-cov - Run tests with coverage report"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs     - Generate documentation"
	@echo ""
	@echo "Packaging:"
	@echo "  make build    - Build distribution packages"
	@echo "  make publish  - Publish package to PyPI"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean    - Remove virtual environment and cache files"

# Setup project dependencies
setup: venv-activate
	@echo "Installing dependencies..."
	$(UV_PIP_INSTALL) -e ".[dev, docs, test]" && pre-commit install

# Start the application
start: venv-activate
	@echo "Starting application..."
	$(PYTHON) -m {{cookiecutter.package_name}}.cli

# Alias for start
run: start

# Linting
lint: venv-activate
	@echo "Running linter..."
	$(RUFF) check .

# Linting with auto-fix
lint-fix: venv-activate
	@echo "Running linter with auto-fix..."
	$(RUFF) check . --fix

# Code formatting
format: venv-activate
	@echo "Formatting code with Black..."
	$(BLACK) .

# Check code formatting
format-check: venv-activate
	@echo "Checking code formatting..."
	$(BLACK) . --check

# Run tests
test: venv-activate
	@echo "Running tests..."
	$(PYTEST) tests/

# Run tests with coverage
test-cov: venv-activate
	@echo "Running tests with coverage..."
	$(PYTEST) --cov={{cookiecutter.package_name}} --cov-report=term-missing 

# Clean up virtual environment and cache files
clean:
	@echo "Cleaning up..."
	$(RM) .venv
	$(RM) .pytest_cache
	$(RM) .coverage
	find . -type d -name "__pycache__" -exec $(RM) {} +

# Generate documentation
docs: venv-activate
	@echo "Generating documentation..."
	$(PDOC) -o docs {{cookiecutter.package_name}}

# Build distribution packages
build: venv-activate
	@echo "Building distribution packages..."
	$(UV_PIP_INSTALL) build
	$(BUILD)

# Publish to PyPI
publish: build
	@echo "Publishing to PyPI..."
	$(UV_PIP_INSTALL) $(TWINE)
	$(TWINE) upload dist/*