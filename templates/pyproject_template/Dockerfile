FROM python:{{cookiecutter.python_version}}-slim as builder

WORKDIR /{{cookiecutter.project_name}}

# Install uv
RUN pip install --no-cache-dir uv

# Copy only the files needed for dependency installation
COPY pyproject.toml .
COPY {{cookiecutter.project_name}} ./{{cookiecutter.project_name}}

# Use uv to install dependencies
RUN uv pip install --system .

FROM python:{{cookiecutter.python_version}}-slim

WORKDIR /{{cookiecutter.project_name}}

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    pip install --no-cache-dir uv

# Copy the installed dependencies and project files
COPY --from=builder /usr/local/lib/python*/site-packages /usr/local/lib/python*/site-packages/
COPY {{cookiecutter.project_name}} ./{{cookiecutter.project_name}}
COPY pyproject.toml .

# Switch to non-root user
USER appuser

{%- if cookiecutter.cli == "y" %}
ENTRYPOINT ["{{cookiecutter.package_name}}"]
CMD ["--help"]
{%- else %}
CMD ["uv", "start"]
{%- endif %}
