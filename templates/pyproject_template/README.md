# {{cookiecutter.project_name}}

{{cookiecutter.description}}

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   python -m {{cookiecutter.package_name}}.main
   ```

## Docker Usage

```bash
docker build -t {{cookiecutter.package_name}} .
docker run -it {{cookiecutter.package_name}}
```
