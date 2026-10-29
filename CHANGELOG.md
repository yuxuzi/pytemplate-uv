# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [3.0.0] — Unreleased

3.0.0 is the first release since 2.0.0. It includes the unreleased 2.1 work, listed after the
3.0 additions below. See [docs/compatibility.md](docs/compatibility.md) for the versioning and
deprecation rules that now apply.

### Breaking

- Components are real. Profile defaults are always included, requested components are added,
  and their requirements come in automatically. A selection used to have to equal the defaults
  exactly.
- The FastAPI profile (version 3) is a layered service, and its default needs no database.
  - Add `--component database` for persistence; it uses SQLAlchemy 2.x with Alembic migrations,
    and SQLModel is gone.
  - `/health` became `/health/live` and `/health/ready`.
  - Errors use the envelope `{"error": {"code", "message", "details", "request_id"}}`.
- The Dockerfile moved into the optional `container` component (both profiles).
- `.pytemplate.toml` is generation manifest schema 2:
  - template source and ref;
  - why each component is present;
  - the answers;
  - an owner for every file.
- Invalid requests exit with code 1 and render failures with code 2. Rejected template answers
  are reported as invalid requests.

### Added

- **Factory contract 1:**
  - strict, versioned `profile.toml` and `components/<id>.toml` manifests, with `kind`, `status`,
    `requires`, `requires_any`, `conflicts`, dependencies and groups, owned `paths`,
    environment `settings`, lifecycle commands, and security notes;
  - unknown keys and wrong types fail with the file name.
- `pytemplate plan`: the resolved components, dependencies, settings, and the exact file list,
  without writing anything.
- `--json` on every command except `update` and `skill`.
- `validate` and `plan` accept command-line options as well as a request file, and `validate` now
  runs the template's answer checks.
- `pytemplate schema {profile,component,pack,request,manifest}`: JSON Schemas for other tools.
- **Template packs:** `--template DIR|gh:org/repo` with `--template-ref TAG`, and `template` /
  `template_ref` in request files.
  - Packs render your own profiles under the same safety rules.
  - `_tasks`, `_migrations`, `_jinja_extensions`, and symlinks are rejected.
- `pytemplate.api`, the supported Python interface.
- **FastAPI foundation:**
  - api, application, domain, infrastructure, and bootstrap layers;
  - a service container wired through dependencies;
  - JSON logs with request IDs and secret redaction;
  - health and readiness endpoints;
  - production settings that refuse wildcard or localhost hosts and CORS, and `DEBUG`;
  - `serve` and `info` commands;
  - unit tests per layer, and integration tests through the real request path.
- **FastAPI components:**
  - `database`: SQLAlchemy 2.x async, Alembic, a repository and unit of work, SQLite locally, and
    a `postgres` dependency group, with per-test migrated databases;
  - `worker`: a task-queue port, an in-process adapter, and job endpoints;
  - `auth`, with exactly one of `auth-api-key` (hashed keys, constant-time comparison, a
    `hash-api-key` command) or `auth-oidc` (JWKS, issuer, audience, expiry, and asymmetric
    algorithms only), plus a principal and scopes, an audit sink, a rate-limit seam, and a
    generated `SECURITY.md`;
  - `container`.
- `docs/compatibility.md`.
- The smoke tests run every distinct component combination through its own lifecycle commands.

### Changed

- The bundled skill discovers components and previews requests with `plan --json`.
- CPython 3.15 is supported for the generator and for generated projects:
  - `python_version` accepts `3.15`;
  - classifiers and the generated CI matrices include it;
  - this repository's CI tests 3.11–3.15;
  - smoke tests generate projects whose minimum matches the job's interpreter, so ruff's and
    mypy's rules for the newest target are checked.
- Generated FastAPI code returns `Self` instead of quoted class names, which ruff rejects
  (UP037) for `python_version` 3.14 and later.

### Fixed

- Template paths fit within Windows' 260-character limit. Component files no longer use
  conditional names; `create` and `update` exclude the manifest `paths` of unselected components
  instead. Template paths are now at most 96 characters.
- `pytemplate update`:
  - resolves components against the release being updated to, not the installed one;
  - never adds a component that the target release made a default;
  - removes only the directories its exclusions emptied, leaving other empty directories in
    place;
  - reports pack and catalog problems as update errors before changing anything.
- Test output no longer depends on terminal width.

### From the unreleased 2.1 work

#### Changed

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
- GitHub Actions (this repo and generated projects) use `actions/checkout@v7`,
  `astral-sh/setup-uv@v10.3.2`, `actions/upload-artifact@v7`, and `actions/download-artifact@v8`,
  which run on Node.js 24 instead of the deprecated Node.js 20.

#### Added

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

#### Fixed

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

#### Removed

- Cookiecutter dependency, `cookiecutter.json` files, and the unused template toggles.
- black (ruff formats the code).

## [2.0.0]

- Previous release.
