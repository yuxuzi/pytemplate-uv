# PyTemplate UV

## Overview

PyTemplate UV is a powerful CLI tool for creating Python project templates using the `uv` package manager. It provides a seamless way to generate standardized project structures with modern development practices.

## Features

- 🚀 Quick project initialization
- 🔧 Support for multiple project templates (FastAPI, Standard Python)
- 📦 Integrated with `uv` package management
- 🧪 Comprehensive testing infrastructure
- 🔍 Linting and type checking support

## Prerequisites

- Python 3.11+
- `uv` package manager
- `cookiecutter`

## Installation

```bash
pip install pytemplate-uv
# or
uv pip install pytemplate-uv
```

## Usage

### Create a Project

```bash
# Create a standard Python project (default)
pytemplate-uv create-project

# Create a FastAPI project
pytemplate-uv create-project --template fastapi

# Create a project with a custom name
pytemplate-uv create-project --name my-awesome-project

# Create a project with custom template and name
pytemplate-uv create-project --template fastapi --name my-api-project
```

### Project Creation Options

- `--template`: Choose the project template (default: pyproject)
  - Options: `pyproject`, `fastapi`
- `--name`: Specify a custom project name
- Additional template-specific options can be passed as needed

### Next Steps After Project Creation

1. `cd` into your project directory
2. Run `uv venv` to create a virtual environment
3. Run `uv pip install -e .` to install dependencies
4. Run `make setup` to set up the development environment

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