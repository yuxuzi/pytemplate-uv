# PyTemplate UV

## Overview

PyTemplate is a deterministic CLI for generating Python project foundations from bundled profiles. It uses Cookiecutter for rendering and is compatible with `uv`, but does not require `uv` to run.

## Features

- 🚀 Quick project initialization
- 🔧 Bundled Python and FastAPI profiles
- 📦 Package-safe profile discovery
- 🧪 Validated output paths and dry runs
- 🔍 Explicit profile metadata

## Prerequisites

- Python 3.11+
- `cookiecutter` is installed automatically as a package dependency

## Installation

```bash
pip install pytemplate-uv
# or
uv pip install pytemplate-uv
```

## Usage

### Create a Project

```bash
# Discover the available profiles
pytemplate list-profiles

# Create a Python CLI/library project
pytemplate create my-python-project --no-input

# Create a FastAPI project in an existing parent directory
pytemplate create market-data-api --profile fastapi --output-dir ./projects --no-input

# Check the selected target without writing files
pytemplate create market-data-api --profile fastapi --output-dir ./projects --dry-run
```

### Project Creation Options

- `--profile`, `-p`: Choose a profile (default: `python`)
- `--output-dir`, `-o`: Existing parent directory for the generated project
- `--no-input`: Use profile defaults without Cookiecutter prompts
- `--dry-run`: Validate the request and show the target without writing files
- `--force`, `-f`: Permit Cookiecutter to overwrite an existing output directory

### Next Steps After Project Creation

1. `cd` into your generated project directory.
2. Follow its generated README and dependency instructions.
3. Use `uv` or another supported Python workflow to create its environment.

## Development

### Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. Install development dependencies:
   ```bash
   uv pip install -e .[dev]
   ```

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check .
black .
mypy .
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contact

Leo Liu - [GitHub](https://github.com/yuxuzi)

---

*Simplifying Python project creation with modern best practices* 🐍✨
