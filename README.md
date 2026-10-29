# pytemplate-uv

[![PyPI](https://img.shields.io/pypi/v/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![Python](https://img.shields.io/pypi/pyversions/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![CI](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A deterministic application factory that generates **uv-native** Python projects. It has three
parts:
- a **profile**, which sets the application's shape;
- **components**, each adding one capability (a database, authentication, background jobs, and
  so on);
- optional external **template packs**.

Every generated project needs only [uv](https://docs.astral.sh/uv/) and `uvx`: no pip, no
virtualenv activation, no `make`.

## What you get

- **Profiles:**
  - `python`: a typed package with a Typer CLI.
  - `fastapi`: a layered service with these parts:
    - routers and schemas, use cases, domain ports, and adapters;
    - `/health/live` and `/health/ready`;
    - JSON logs with request IDs;
    - one error envelope;
    - deny-by-default host and CORS policies.
- **Components you choose:**

  | Component | Adds |
  | --- | --- |
  | `database` | SQLAlchemy 2.x, Alembic, and a repository with a unit of work; SQLite locally, plus a PostgreSQL group |
  | `worker` | A task-queue port with an in-process adapter and job endpoints |
  | `auth-api-key` | API-key authentication, behind a principal and scopes |
  | `auth-oidc` | OpenID Connect authentication, behind a principal and scopes |
  | `container` | A Dockerfile, for both profiles |

  Required components are added automatically. Invalid combinations fail before anything is
  written.
- **Green from the first commit:** every component combination passes its own `ruff check`,
  `ruff format --check`, strict `mypy`, and `pytest` in this repository's CI.
- **Inspectable and scriptable:**
  - `plan` shows the exact files and dependencies without writing anything;
  - every command has `--json` output and stable exit codes;
  - `schema` prints JSON Schemas for requests, manifests, and packs.
- **Extensible without forking:** render your own profiles from a template pack directory or git
  tag with `--template`.
- **Upgradable:** `pytemplate update` merges newer template releases into existing projects with
  `copier update`, keeping your edits.
- **Deterministic and safe:**
  - identical requests produce byte-identical projects;
  - rendering never runs template code, reads your environment, or touches the network;
  - failed renders leave nothing behind.

## Install

```bash
uvx pytemplate-uv --help            # run without installing
uv tool install pytemplate-uv       # or install the `pytemplate` command
```

Python 3.11–3.14 is supported. `pip install pytemplate-uv` also works.

## Create a project

```bash
pytemplate create market-data --no-input                          # python profile
pytemplate create pricing-api -p fastapi --no-input               # FastAPI, no infrastructure
pytemplate create pricing-api -p fastapi -c database -c auth-oidc -c worker --no-input
pytemplate create pricing-api -p fastapi -o ./projects \
  --data description="Pricing service" --data author="Quant Team" --no-input

cd pricing-api
uv sync
uv run pytest
```

Preview first, without writing anything:

```bash
pytemplate plan --name pricing-api -p fastapi -c database      # components, dependencies, files
pytemplate validate --name pricing-api -p fastapi -c auth      # fails: auth needs a mode
```

Here is the second command's output:

```
Error: Component 'auth' needs one of: auth-api-key, auth-oidc; add --component auth-api-key.
```

`create-project` is an optional shortcut with the same arguments and options as
`pytemplate create`:

```bash
uvx --from pytemplate-uv create-project pricing-api -p fastapi --no-input
```

### Commands

| Command | Purpose |
| --- | --- |
| `pytemplate create NAME` | Render a project into `OUTPUT_DIR/NAME` |
| `pytemplate plan [FILE]` | Show the resolved components, dependencies, settings, and file list; writes nothing |
| `pytemplate validate [FILE]` | Validate a request, including the template's answer checks; writes nothing |
| `pytemplate create-from-config FILE` | Render a TOML render request |
| `pytemplate list-profiles` / `describe-profile ID` | Show profiles and their template inputs |
| `pytemplate list-components` / `describe-component ID` | Show components: requirements, conflicts, dependencies, owned files, settings |
| `pytemplate schema NAME` | Print the JSON Schema for `profile`, `component`, `pack`, `request`, or `manifest` |
| `pytemplate update [DIR] [--to TAG] [--apply]` | Merge a newer template release (dry run by default) |
| `pytemplate skill install` / `skill show` | Install or print the AI project-creation skill |
| `pytemplate --version` | Show the installed version |

Notes:
- `plan` and `validate` take a request file or the same options as `create`, with `--name`.
- Every command except `update` and `skill` accepts `--json`.
- The inspection commands, `plan`, `validate`, and `create` accept `--template` to work with a
  template pack.

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
  - Inputs are `package_name`, `description`, `author`, `email`, `python_version` (3.11–3.14),
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

`pytemplate.api` is the supported Python interface, and everything else is internal:

```python
from pathlib import Path
from pytemplate import api

request = api.RenderRequest("fastapi", "pricing-api", Path("."), components=("database",))
print(api.plan(request).files)       # nothing is written
api.render(request)
```

Tools in other languages can call the CLI with `--json` and validate their requests against
`pytemplate schema request`.

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

## Development

```bash
uv sync                                   # install the dev group
uv run pytest                             # unit, contract, and composition tests
PYTEMPLATE_SMOKE=1 uv run pytest          # also run every generated combination's quality gates
uv run ruff check . && uv run ruff format --check pytemplate tests
uv run mypy
uv build
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md) (instructions for AI coding
agents), [docs/compatibility.md](docs/compatibility.md), and [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
