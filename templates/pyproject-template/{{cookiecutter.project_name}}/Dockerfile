FROM python:{{cookiecutter.python_version}}-slim as builder

WORKDIR /{{cookiecutter.project_name}}

# Install uv and make
RUN pip install --no-cache-dir uv && \
    apt-get update && apt-get install -y make

# Copy only the files needed for dependency installation
COPY pyproject.toml Makefile ./
COPY {{cookiecutter.project_name}} ./{{cookiecutter.project_name}}

# Use uv to install dependencies
RUN uv pip install --system .

FROM python:{{cookiecutter.python_version}}-slim

WORKDIR /{{cookiecutter.project_name}}

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    pip install --no-cache-dir uv && \
    apt-get update && apt-get install -y make

# Copy the installed dependencies and project files
COPY --from=builder /usr/local/lib/python*/site-packages /usr/local/lib/python*/site-packages/
COPY {{cookiecutter.project_name}} ./{{cookiecutter.project_name}}
COPY pyproject.toml Makefile ./

# Switch to non-root user
USER appuser

# Use make start to run the application
ENTRYPOINT ["make"]
CMD ["start"]
