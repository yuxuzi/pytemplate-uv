# pytemplate-uv

[![PyPI](https://img.shields.io/pypi/v/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![Python](https://img.shields.io/pypi/pyversions/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![CI](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A deterministic CLI that generates **uv-native** Python projects from bundled
[Copier](https://copier.readthedocs.io/) templates. Every generated project needs only
[uv](https://docs.astral.sh/uv/) and `uvx`: no pip, no virtualenv activation, no `make`.

## What you get

- **Two profiles:** `python` (typed package with a Typer CLI) and `fastapi` (async FastAPI service
  with SQLModel, typed settings, structured errors, request IDs, and deny-by-default host/CORS).
- **Green from the first commit:** every generated project passes its own `ruff check`,
  `ruff format --check`, strict `mypy`, and `pytest`, which this repository's CI verifies on every change.
- **Modern packaging:** `uv_build` backend, PEP 735 `[dependency-groups]`, PEP 639 license metadata,
  `py.typed`, and a GitHub Actions workflow for Windows, macOS, and Linux.
- **Agent-ready:** a profile-specific `CLAUDE.md` in every project, a bundled Claude skill that
  creates projects through a validate-then-confirm flow, and `--json` output for any AI tool.
- **Upgradable:** `pytemplate update` merges newer template releases into existing projects with
  `copier update`, keeping your edits.
- **Deterministic and safe:** identical requests produce byte-identical projects; rendering never
  runs template code, reads your environment, or touches the network; failed renders leave nothing
  behind.

## Install

```bash
uvx pytemplate-uv --help            # run without installing
uv tool install pytemplate-uv       # or install the `pytemplate` command
```

Python 3.11–3.14 is supported. `pip install pytemplate-uv` also works.

## Create a project

```bash
pytemplate create market-data --no-input                     # python profile
pytemplate create pricing-api --profile fastapi --no-input   # FastAPI profile
pytemplate create pricing-api -p fastapi -o ./projects \
  --data description="Pricing service" --data author="Quant Team" --no-input

cd pricing-api
uv sync
uv run pytest
```

Without `--no-input`, Copier prompts for each template question.

### Commands

| Command | Purpose |
| --- | --- |
| `pytemplate create NAME` | Render a project into `OUTPUT_DIR/NAME` |
| `pytemplate list-profiles` / `describe-profile ID` | Show profiles and their template inputs |
| `pytemplate list-components` / `describe-component ID` | Show the component contract |
| `pytemplate validate FILE` | Validate a TOML render request without writing files |
| `pytemplate create-from-config FILE` | Render a TOML render request |
| `pytemplate update [DIR] [--to vX.Y.Z] [--apply]` | Merge a newer template release (dry run by default) |
| `pytemplate skill install` / `skill show` | Install or print the AI project-creation skill |
| `pytemplate --version` | Show the installed version |

The `list-*` and `describe-*` commands accept `--json`.

### `create` options

- `--profile`, `-p`: profile identifier (default `python`).
- `--output-dir`, `-o`: existing parent directory (default `.`).
- `--data`, `-d KEY=VALUE`: answer a template question; repeat as needed. Inputs are
  `package_name`, `description`, `author`, `email`, `python_version` (3.11–3.14), and `license`
  (an SPDX expression).
- `--no-input`: accept defaults instead of prompting.
- `--dry-run`: validate and show the target without writing.
- `--force`, `-f`: replace an existing directory. The project is rendered into a staging directory
  and swapped in only after rendering succeeds, so no stale files remain.
- `--component`, `-c`: select profile components (current profiles require their full foundation
  set).

### Reproducible render requests

```toml
# pricing-api.toml
project_name = "pricing-api"
profile = "fastapi"
output_dir = "./projects"   # relative to this file

[data]
description = "Pricing service"
author = "Quant Team"
```

```bash
pytemplate validate pricing-api.toml
pytemplate create-from-config pricing-api.toml
```

Each project records its generator, profile, component versions, and a SHA-256 inventory of the
rendered files in `.pytemplate.toml`, plus its Copier answers and template source in
`.copier-answers.yml`. Neither file stores secrets or environment values.

## Update an existing project

Projects created by 2.1+ can pull in newer template releases. The update is a three-way merge:
your edits are kept, and real conflicts are marked inline. It needs `git` and network access to
`github.com/yuxuzi/pytemplate-uv`.

```bash
cd pricing-api                 # a git repository with no uncommitted changes
pytemplate update              # dry run: shows what would change
pytemplate update --apply      # merge the templates of the installed pytemplate version
pytemplate update --apply --to v2.2.0
git diff                       # review, resolve any <<<<<<< markers, run the checks, commit
```

`uvx copier update` works too, because projects carry a standard `.copier-answers.yml`. Projects
generated by older releases have no answers file; regenerate them with the same answers and move
your changes over.

## Create projects with Claude or other AI tools

pytemplate-uv ships a Claude Code skill (`SKILL.md`) that teaches Claude to:
- ask for any missing inputs;
- write and `validate` a render request;
- **wait for your confirmation**;
- create the project and run its checks.

```bash
uvx pytemplate-uv skill install            # ~/.claude/skills/pytemplate/SKILL.md (all projects)
uvx pytemplate-uv skill install --project  # ./.claude/skills/pytemplate/SKILL.md (this repo)
```

Then ask, for example, *"Create a FastAPI service called pricing-api for Python 3.12"*. For other
AI tools, give them the instructions from `uvx pytemplate-uv skill show`; they use the same
`--json` discovery commands.

## Generated project layout (fastapi)

```
pricing-api/
  CLAUDE.md  README.md  pyproject.toml  Dockerfile  .env.example  .copier-answers.yml
  .github/workflows/ci.yml  .pre-commit-config.yaml  .gitignore  .dockerignore
  pricing_api/  main.py  cli.py  db.py  models.py  routers/  core/  py.typed
  tests/        conftest.py  test_api.py  test_cli.py  test_config.py
```

## How templates work

Profiles live in `pytemplate/templates/<profile>/`:

- `pytemplate/templates/questions.yml`: shared questions and validators. The `profile` answer
  selects the subtree.
- `pytemplate/templates/copier.yml` (bundled) and the repo-root `copier.yml` (used from git tags
  by `copier update`): two entry points that render identically.
- `<profile>/profile.toml`: the factory contract (version, components, lifecycle commands).
- `<profile>/template/`: the project tree. Only files ending in `.jinja` are rendered; everything
  else, including GitHub Actions workflows, is copied verbatim.

Templates must not declare Copier `_tasks` or `_migrations`, and both rendering and updating run
with `unsafe=False`.

## Development

```bash
uv sync                                   # install the dev group
uv run pytest                             # unit tests
PYTEMPLATE_SMOKE=1 uv run pytest          # also run each generated project's quality gates
uv run ruff check . && uv run ruff format --check pytemplate tests
uv run mypy
uv build
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md) (instructions for AI coding
agents), and [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
