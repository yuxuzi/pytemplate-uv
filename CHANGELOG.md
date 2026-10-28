# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [2.1.0] — Unreleased

### Changed

- Rendering uses Copier instead of Cookiecutter. Templates live in
  `pytemplate/templates/<profile>/` with a `copier.yml`; only `*.jinja` files are rendered.
- Generated projects depend only on `uv` and `uvx`: `uv_build` backend, PEP 735
  `[dependency-groups]`, `uv run` commands everywhere, pre-commit through `uvx`, and Dockerfiles
  that copy `uv` from its official image. Makefiles are gone.
- Generated projects pass their own `ruff check`, `ruff format --check`, strict `mypy`, and
  `pytest`; CI enforces this for every profile.
- The FastAPI profile was rebuilt:
  - an application factory and a `/health` endpoint;
  - typed settings with deny-by-default `ALLOWED_HOSTS` and CORS, and wildcards rejected in
    production;
  - structured `AppError` responses;
  - full CRUD including `PATCH`;
  - a `serve` CLI command;
  - an isolated in-memory test database.
- The package builds with `uv_build`; development tools moved to a `dev` dependency group.

### Added

- `pytemplate update [DIR] [--to vX.Y.Z] [--apply]` upgrades generated projects with
  `copier update`:
  - a three-way merge that keeps user edits;
  - a dry run by default;
  - requires a clean git tree.
- Generated projects include `.copier-answers.yml` pointing at `gh:yuxuzi/pytemplate-uv` and the
  release tag. `--template-source` and the TOML key `template_source` support forks.
- A repo-root `copier.yml` git entry point, with questions shared through
  `pytemplate/templates/questions.yml`.
- A bundled agent skill for creating projects with Claude: `pytemplate skill install
  [--project|--dest DIR]` installs it and `pytemplate skill show` prints it. `--json` was added to
  the `list-*` and `describe-*` commands.
- `AGENTS.md` with instructions for AI coding agents working on this repository; `CLAUDE.md`
  imports it.
- Every generated project includes a profile-specific `CLAUDE.md`.
- `--data KEY=VALUE` on `create`, and a `[data]` table in TOML render requests.
- `describe-profile` lists template inputs.
- `pytemplate --version`.
- A `create-project NAME [OPTIONS]` executable that runs `create` directly. `pytemplate
  create-project` is now a visible, fully equivalent alias; previously it was hidden and lacked
  `--component`, `--data`, and `--template-source`.
- `.pytemplate.toml` records a SHA-256 inventory of rendered files.
- Validators for `package_name`, `license` (SPDX), and single-line text answers.
- A release workflow that publishes to PyPI through Trusted Publishing.

### Fixed

- Template `.gitignore` files are now `.gitignore.jinja`. Their `.env.*` rule had silently kept
  the FastAPI `.env.example` template out of git.
- Output no longer depends on `$USER` or other environment variables.
- `--force` replaces the project instead of merging into it, and failed renders leave no partial
  output.
- Template dotfiles (`.gitignore`, CI workflow, pre-commit config) are included in the wheel.
- Generated `.gitignore` excludes `.env`. FastAPI now ships `.env.example` instead of a tracked
  `.env` with placeholder secrets.
- FastAPI:
  - the Content-Security-Policy no longer blocks `/docs`;
  - CORS no longer combines `*` with credentials;
  - the Docker healthcheck targets an existing endpoint without needing `curl`;
  - the container can write its SQLite database.
- The `license` and `python_version` answers now affect generated metadata, classifiers, and the CI
  matrix.

### Removed

- Cookiecutter dependency, `cookiecutter.json` files, and the unused template toggles.
- black (ruff formats the code).

## [2.0.0]

- Previous release.
