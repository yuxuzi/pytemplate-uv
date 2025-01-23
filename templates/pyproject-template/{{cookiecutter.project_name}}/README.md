# {{cookiecutter.project_name}}

{{cookiecutter.description}}

## 🚀 Features

- Clean, modern Python project structure
- Comprehensive development tooling
- Easy-to-use CLI
- Robust testing and type checking

## 📦 Installation

```bash
# Using pip
pip install {{cookiecutter.package_name}}

# Using uv
uv pip install {{cookiecutter.package_name}}
```

## 🔧 Development Setup

1. Clone the repository
2. Create a virtual environment
```bash
uv venv
. .venv/bin/activate
```

3. Install dependencies
```bash
make setup
```

## 💻 Usage

### CLI Commands

```bash
# Show help
{{cookiecutter.package_name}} --help

# Hello command
{{cookiecutter.package_name}} hello --name World

# Project info
{{cookiecutter.package_name}} info
```

## 🧪 Testing

Run tests with comprehensive coverage:

```bash
make test
```

## 📝 Development Workflow

- `make lint`: Run code linters
- `make format`: Auto-format code
- `make test`: Run tests
- `make docs`: Generate documentation

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

{{cookiecutter.license}} License

## 👥 Authors

- {{cookiecutter.author}} <{{cookiecutter.email}}>
