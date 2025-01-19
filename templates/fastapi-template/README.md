# {{cookiecutter.project_name}}

{{cookiecutter.description}}

## Setup

1. Install dependencies:
   ```bash
   uvx install
   ```

2. Run the app:
   ```bash
   uvx start
   ```

## Docker Usage

```bash
docker build -t {{cookiecutter.package_name}} .
docker run -p 8000:8000 {{cookiecutter.package_name}}
```

## Testing

Run the tests using:
```bash
uvx test
```

## Documentation

Generate API documentation using:
```bash
uvx make-docs
```
