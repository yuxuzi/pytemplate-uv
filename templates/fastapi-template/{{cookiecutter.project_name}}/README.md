# {{cookiecutter.project_name}}

{{cookiecutter.description}}

## 🚀 Features

- Modern FastAPI web application
- Async SQLModel database integration
- Comprehensive development tooling
- Robust testing and type checking
- Docker support

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

### API Endpoints

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 🧪 Testing

Run tests with comprehensive coverage:

```bash
make test
```

## 📝 Development Workflow

- `make start`: Start the FastAPI server
- `make lint`: Run code linters
- `make format`: Auto-format code
- `make test`: Run tests
- `make docs`: Generate documentation

## 🐳 Docker Support

Build and run the Docker container:

```bash
# Build the image
docker build -t {{cookiecutter.package_name}} .

# Run the container
docker run -p 8000:8000 {{cookiecutter.package_name}}
```

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
