# AGENTS.md

Instructions and context for AI coding agents working on **pytemplate-uv** itself. Generated
projects carry their own `CLAUDE.md`. Claude Code reads this file through `CLAUDE.md`.

## What this project is

A Typer CLI (`pytemplate`, also `pytemplate-uv`, plus a `create-project` shortcut) that renders bundled
[Copier](https://copier.readthedocs.io/) templates into uv-native projects. It can also upgrade
those projects later with `copier update`. It is published to PyPI as `pytemplate-uv` and supports
CPython 3.11–3.14 on Windows, macOS, and Linux. `uv` and `uvx` are the only required tools; never
use pip, virtualenv activation, or make.

## Commands

| Task | Command |
| --- | --- |
| Install the dev environment | `uv sync` |
| Unit tests | `uv run pytest` |
| Generated-project gates (needs network) | `PYTEMPLATE_SMOKE=1 uv run pytest tests/test_generated_projects.py` |
| Lint | `uv run ruff check .` |
| Format check | `uv run ruff format --check pytemplate tests` |
| Type-check (strict) | `uv run mypy` |
| Build and check distributions | `uv build && uvx twine check --strict dist/*` |

Before reporting work as done, run the unit tests, lint, format check, and type-check. After any
template change, also run the smoke tests. Report the real results.

## Layout

- `pytemplate/main.py`: Typer commands (`create`, `create-from-config`, `validate`, `update`,
  `list-*`/`describe-*` with `--json`, `skill show|install`). Presentation only.
- `pytemplate/rendering.py`: request validation, Copier `run_copy` into a staging directory,
  atomic publish, answers-file source recording, and the `.pytemplate.toml` manifest.
- `pytemplate/updating.py`: `copier update` wrapper (dry run by default, clean git tree required,
  inline conflicts).
- `pytemplate/profiles.py`: profile and component discovery; questions from `questions.yml`.
- `pytemplate/configuration.py`: TOML render requests.
- `pytemplate/agent_skill.py` and `pytemplate/skills/pytemplate/SKILL.md`: the bundled AI skill.
- `pytemplate/templates/`:
  - `questions.yml`: shared settings and questions;
  - `copier.yml`: bundled entry point;
  - `<profile>/profile.toml`: the factory contract;
  - `<profile>/template/`: the project tree. Only `*.jinja` files are rendered.
- `copier.yml` (repo root): the git entry point that `copier update` uses at `vX.Y.Z` tags.
- `tests/`:
  - unit and CLI tests;
  - `test_updating.py` (local git fixture);
  - `test_generated_projects.py` (opt-in smoke tests).

## Invariants

- **Deterministic rendering:** no environment variables, clock values, or network access in the
  template context. Identical requests produce byte-identical projects.
- **Safe templates:** never add Copier `_tasks` or `_migrations`, and keep `unsafe=False`.
- **Green generated projects:** every profile must pass its `lifecycle_commands`. Those commands
  are mirrored in each template's `CLAUDE.md.jinja` and CI workflow, and tests enforce the match.
- **Updatable projects:**
  - The repo-root `copier.yml` and `pytemplate/templates/copier.yml` must render identically
    (tested).
  - Add new questions instead of renaming or removing existing ones.
  - Release tags `vX.Y.Z` must contain exactly the templates shipped in that wheel; the release
    workflow checks the tag against the version.
  - Never rewrite or move published tags.
- **Nothing inside `pytemplate/templates/` may be git-ignored** (tested). Name template ignore
  files `.gitignore.jinja` so their rules do not apply to this repository.
- **No secrets:** manifests and answers files never store secrets or environment values, and
  generated `.env` files stay git-ignored.

## Conventions

- Strict mypy, ruff (line length 100), and docstrings on public functions.
- Keep the CLI thin and put logic in modules that can be tested without Typer.
- Raise the module's error type (`RenderError`, `UpdateError`, `ConfigurationError`,
  `SkillInstallError`) with an actionable message; the CLI prints it and exits with code 1.
- Tests use `tmp_path` and never touch the network, except the opt-in smoke tests.
- Bump a profile's `version` in `profile.toml` when its generated output changes, and add a
  `CHANGELOG.md` entry under "Unreleased" for user-visible changes.

## Boundaries

Ask before you:
- change release or CI workflows;
- bump the package version;
- create tags;
- publish;
- loosen a safety invariant above.

Never commit secrets or tokens.
