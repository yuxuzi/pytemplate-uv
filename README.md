# pytemplate-uv

[![PyPI](https://img.shields.io/pypi/v/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![Python](https://img.shields.io/pypi/pyversions/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![CI](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Generate production-ready Python projects in seconds.** Deterministic application factory with
> professions, composable components, and zero configuration.

A modern application factory that generates **uv-native** Python projects that pass linting,
formatting, type-checking, and tests from the first commit. Choose your profile (library, CLI
tool, or FastAPI service), add components (database, authentication, background jobs), and get a
ready-to-deploy project.

- ✅ **Deterministic:** identical requests produce byte-identical projects
- ✅ **Production-ready:** every component combination passes strict quality gates
- ✅ **Fast:** minimal dependencies, `uv`-only (no pip, virtualenv, or make)
- ✅ **Extensible:** use template packs to customize without forking
- ✅ **Type-safe:** strict mypy on generated code, validated inputs

## What you get

### Profiles (choose one)

- **`python`** — a typed package with a Typer CLI; great for tools and libraries
- **`fastapi`** — a layered REST API service with structured logging, health checks, security, and organized architecture

### Components (mix and match)

| Component | Purpose | When to use |
| --- | --- | --- |
| `database` | SQLAlchemy 2.x ORM + Alembic migrations | When you need persistent data |
| `worker` | Background job queue with in-process adapter | For async work and scheduled tasks |
| `auth-api-key` | API key authentication with scopes | For service-to-service auth |
| `auth-oidc` | OpenID Connect (JWT) authentication | For user login via identity provider |
| `container` | Dockerfile and `.dockerignore` | For containerized deployment |

Mix components freely — the generator validates combinations and adds required dependencies.

### Quality from day one

Every generated project passes:
- ✅ `ruff check` and `ruff format --check` (code quality and style)
- ✅ Strict `mypy` (type safety)
- ✅ `pytest` (tests included)

This is verified across 26 component combinations on every commit.

### Built for teams

- **Inspectable:** `plan` shows files and dependencies without writing anything
- **Reproducible:** `.pytemplate.toml` records exact versions and checksums for each file
- **Updatable:** `pytemplate update` does a three-way merge with your edits when a new release comes out
- **Scriptable:** `--json` output and stable exit codes for CI/CD integration
- **Extensible:** bring your own profiles and components via template packs

## Why pytemplate-uv?

**The problem it solves:**
- Boilerplate is brittle—missing auth, wrong config, outdated patterns, integration test gaps
- Every team reimplements auth, logging, database connections, container config
- Generated code is usually messy, missing checks, and needs cleanup

**The solution:**
- Start with patterns that actually work in production
- All combinations validated and tested (26 component mixes on every commit)
- Updated safely with `pytemplate update`—no merge conflicts, your changes preserved
- Write less, deploy faster, fewer bugs

**Who uses it:**
- Teams building FastAPI services and CLI tools
- Projects that need deterministic scaffolding in CI/CD
- Any shop that generates variations of the same app
- Organizations building internal tools and platforms

## Install

**No installation needed to try it:**
```bash
uvx pytemplate-uv --help
```

**To install the `pytemplate` command:**
```bash
uv tool install pytemplate-uv
```

Requires Python 3.11–3.15. Runs on Linux, macOS, and Windows. Also available via `pip install pytemplate-uv`.

## Create a project

### 30-second quickstart

```bash
pytemplate create my-api -p fastapi -c database -c auth-oidc --no-input
cd my-api
uv sync
uv run pytest
```

That's it. You have a production-grade FastAPI service with a database, OIDC auth, tests, CI/CD,
structured logging, health checks, and a clean layered architecture.

### More examples

```bash
# Python CLI tool
pytemplate create my-tool -p python --no-input

# FastAPI service with background jobs
pytemplate create my-service -p fastapi -c worker -c database --no-input

# Containerized API with API key auth
pytemplate create my-api -p fastapi -c auth-api-key -c container --no-input

# Preview before writing anything
pytemplate plan -p fastapi -c database -c auth-oidc --name my-api

# Validate a request (catches mistakes early)
pytemplate validate -p fastapi -c auth    # Error: 'auth' requires one of: auth-api-key, auth-oidc
```

`create-project` is an optional shortcut with the same arguments and options as
`pytemplate create`:

```bash
uvx --from pytemplate-uv create-project pricing-api -p fastapi --no-input
```

### Commands

| Command | What it does |
| --- | --- |
| `create NAME` | Generate a project |
| `plan` | Preview files and dependencies (no write) |
| `validate` | Check for errors before rendering |
| `create-from-config FILE` | Render from a TOML request file |
| `list-profiles` | Show available profiles |
| `list-components` | Show available components and their requirements |
| `update [DIR]` | Merge a new template release into an existing project |
| `schema` | Print JSON Schemas for integration with tools and scripts |

**Tips:**
- All commands support `--json` for scripting and CI/CD
- Use `--template` to render from custom template packs
- `plan` and `update` never write to disk (preview first, then `--apply`)

**Exit codes:**
- `0`: success.
- `1`: an invalid request; nothing was written. With `--json`, the error is printed as
  `{"ok": false, "error": {...}}`.
- `2`: a valid request that failed while rendering or writing.

### `create` options

- `--profile`, `-p`: profile identifier (default `python`).
- `--component`, `-c`: add a component; repeat as needed. Profile defaults are always included,
  and required components are added automatically.
- `--output-dir`, `-o`: existing parent directory (default `.`).
- `--data`, `-d KEY=VALUE`: answer a template question; repeat as needed.
  - Inputs are `package_name`, `description`, `author`, `email`, `python_version` (3.11–3.15),
    and `license` (an SPDX expression).
- `--template`, `-t SOURCE` and `--template-ref REF`: render from a template pack (see below).
- `--no-input`: accept defaults instead of prompting.
- `--dry-run`: validate and show the target without writing.
- `--force`, `-f`: replace an existing directory. The project is rendered into a staging
  directory and swapped in only after rendering succeeds, so no stale files remain.
- `--json`: print the result as JSON.

### Reproducible render requests

```toml
# pricing-api.toml
project_name = "pricing-api"
profile = "fastapi"
components = ["database", "auth-api-key"]
output_dir = "./projects"   # relative to this file

[data]
description = "Pricing service"
author = "Quant Team"
```

```bash
pytemplate validate pricing-api.toml
pytemplate plan pricing-api.toml --json
pytemplate create-from-config pricing-api.toml
```

Each project records how it was generated, and neither file stores secrets or environment
values:
- `.pytemplate.toml` records the generator, template source, and profile and component versions
  (with why each component is present), the answers, and a SHA-256 hash and owner for every
  generated file;
- `.copier-answers.yml` records the Copier answers and the template source.

`pytemplate schema manifest` describes the format.

## Template packs

A template pack is a directory or git repository with your own profiles and components. It has
the same layout as the bundled templates:

```
my-pack/
  pytemplate-pack.toml       # contract = 1, id, name, description, version
  copier.yml                 # _subdirectory: "{{ profile }}/template"; --- !include questions.yml
  questions.yml              # profile, project_name, package_name, components, ...
  <profile>/profile.toml     # the profile manifest (pytemplate schema profile)
  <profile>/template/...     # the project tree; only *.jinja files are rendered
  components/<id>.toml       # component manifests (pytemplate schema component)
```

```bash
pytemplate list-profiles --template ./my-pack
pytemplate create my-tool -p tool --template gh:org/my-pack --template-ref v1.2.0 --no-input
```

- Packs are selected explicitly for each request; nothing is discovered or installed.
- They follow the same rules as the bundled templates:
  - they render with Copier's `unsafe=False`;
  - `_tasks`, `_migrations`, `_jinja_extensions`, and symlinks are rejected.
- Pack-generated projects record the pack's source and tag, so
  `pytemplate update --to <tag>` works for them too.
- See [docs/compatibility.md](docs/compatibility.md) for the versioning rules.

## Update an existing project

Projects created by 3.0 or later can pull in newer template releases.
- The update is a three-way merge: your edits are kept, and real conflicts are marked inline.
- It needs `git` and network access to `github.com/yuxuzi/pytemplate-uv`.

```bash
cd pricing-api                 # a git repository with no uncommitted changes
pytemplate update              # dry run: shows what would change
pytemplate update --apply      # merge the templates of the installed pytemplate version
git diff                       # review, resolve any <<<<<<< markers, run the checks, commit
```

Projects generated by 2.0 have no `.copier-answers.yml` and cannot be updated. Generate a fresh
3.0 project with the same answers and move your code over.

## Create projects with Claude or other AI tools

pytemplate-uv ships a Claude Code skill (`SKILL.md`) that teaches Claude to:
- discover profiles and components;
- write a render request and check it with `plan`;
- **wait for your confirmation**;
- create the project and run its checks.

```bash
uvx pytemplate-uv skill install            # ~/.claude/skills/pytemplate/SKILL.md (all projects)
uvx pytemplate-uv skill install --project  # ./.claude/skills/pytemplate/SKILL.md (this repo)
```

Then ask, for example, *"Create a FastAPI service called pricing-api with a database and OIDC
login"*. For other AI tools, give them the instructions from `uvx pytemplate-uv skill show`.

## Use from Python or other tools

**From Python:**
```python
from pathlib import Path
from pytemplate import api

# Plan without writing
request = api.RenderRequest("fastapi", "my-api", Path("."), components=("database",))
plan = api.plan(request)
print(plan.dependencies)   # inspect what will be added
print(plan.files)          # see all generated files

# Or render the project
api.render(request)
```

**From scripts, CI/CD, or other languages:**
```bash
# Output JSON for integration
pytemplate plan --name my-api -p fastapi -c database --json | jq .

# Validate requests before rendering
pytemplate validate --config request.toml --json

# Get schemas for validation
pytemplate schema request
```

## Generated FastAPI layout

```
pricing-api/
  CLAUDE.md  README.md  pyproject.toml  .env.example  .copier-answers.yml  .pytemplate.toml
  pricing_api/
    api/             routers/, schemas, dependencies, errors, middleware, health
    application/     use cases
    domain/          entities, rules, errors, ports
    infrastructure/  memory adapter (database/ with -c database)
    bootstrap/       settings, logging, container, create_app()
    security/        with -c auth-api-key or -c auth-oidc
  migrations/  alembic.ini       with -c database
  SECURITY.md                    with authentication
  Dockerfile  .dockerignore      with -c container
  tests/unit/  tests/integration/
```

## Contribute

**Getting started:**
```bash
uv sync
uv run pytest                    # run unit tests
PYTEMPLATE_SMOKE=1 uv run pytest # verify all 26 component combinations work
uv run ruff check .
uv run mypy
```

**Adding a component:**
1. Create `pytemplate/components/my-component.toml` with the manifest
2. Add files to `pytemplate/templates/fastapi/template/` with conditional includes
3. Add questions to `pytemplate/templates/questions.yml`
4. Tests run automatically for all combinations

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

## Learn more

- [Compatibility & versioning](docs/compatibility.md)
- [Design decisions](docs/decisions/)
- [CHANGELOG](CHANGELOG.md)
- For AI agents: [AGENTS.md](AGENTS.md)
- For project scaffolding in Claude: `pytemplate skill install`

## FAQ

**Can I use this in production?**
Yes. Every generated component combination passes strict tests (lint, format, type-check, pytest)
on every commit. The `stable` components are production-ready.

**What if I want to customize the templates?**
Use `--template` to point to your own template pack (a directory or git repo). You get all the
composition logic but with your own code.

**How do I keep my project updated?**
Run `pytemplate update`. It does a three-way merge that keeps your edits and merges in new
template improvements. Projects generated by 3.0+ support updates forever.

**Do I need to commit the generated code?**
Yes—generate the project into a git repo and commit it. `.pytemplate.toml` records how it was
made, so you can update it later.

**Is the generated code opinionated?**
Yes, intentionally. We have opinions on:
- Async-first FastAPI with structured logging
- SQLAlchemy 2.x (not SQLModel or ORM auto-magic)
- Layered architecture (domain, application, infrastructure)
- Type safety (strict mypy by default)

These opinions come from production experience and are documented in `CLAUDE.md`.

**Can I generate projects without a network connection?**
Yes. The generator doesn't touch the network or load your environment. Copier runs with
`unsafe=False`, so templates can't execute code.

## License

MIT. See [LICENSE](LICENSE).
