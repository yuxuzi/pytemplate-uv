# AGENTS.md

Instructions and context for AI coding agents working on **pytemplate-uv** itself. Generated
projects carry their own `CLAUDE.md`. Claude Code reads this file through `CLAUDE.md`.

## What this project is

A deterministic application factory: a Typer CLI (`pytemplate`, also `pytemplate-uv`, plus a
`create-project` shortcut) that renders [Copier](https://copier.readthedocs.io/) templates into
uv-native projects. A project is built from:
- a **profile**, which sets the application's shape;
- **components**, each adding one capability, declared in versioned manifests (factory contract
  1);
- optionally, an external **template pack**.

It can also upgrade those projects later with `copier update`. It is published to PyPI as
`pytemplate-uv` and supports CPython 3.11–3.14 on Windows, macOS, and Linux. `uv` and `uvx` are
the only required tools; never use pip, virtualenv activation, or make. The roadmap is
[PLAN.md](PLAN.md), and the versioning rules are in
[docs/compatibility.md](docs/compatibility.md).

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

- `pytemplate/main.py`: Typer commands (`create`, `plan`, `validate`, `create-from-config`,
  `list-*`/`describe-*`, `schema`, `update`, `skill show|install`), with `--json` and exit codes 0, 1
  (invalid request), and 2 (render failure). Presentation only.
- `pytemplate/api.py`: the supported Python interface; re-exports only.
- `pytemplate/profiles.py`: strict loading of contract-1 manifests into a `Catalog`, plus
  `check_catalog()` and `bundled_catalog()`.
- `pytemplate/resolution.py`: `resolve()` turns a profile plus requested components into a
  `Resolution`. It handles `requires`, `requires_any`, and `conflicts`, merges dependencies, and
  assigns path ownership through `Resolution.owner()`.
- `pytemplate/packs.py`: `open_catalog()` for the bundled templates or an explicit pack
  (directory or git source), safety checks, and `TemplateSource`.
- `pytemplate/rendering.py`: request validation, `plan()`, Copier `run_copy` into a staging
  directory, atomic publish, answers-file source recording, and the schema-2 `.pytemplate.toml`.
- `pytemplate/updating.py`: the `copier update` wrapper. It is a dry run by default, requires a
  clean git tree, marks conflicts inline, and maps legacy components.
- `pytemplate/schema.py`: published JSON Schemas; `tests/test_schema.py` keeps them in step.
- `pytemplate/errors.py`: `RenderError`, `RequestError`, and `PackError`.
- `pytemplate/configuration.py`: TOML render requests.
- `pytemplate/agent_skill.py` and `pytemplate/skills/pytemplate/SKILL.md`: the bundled AI skill.
- `pytemplate/templates/`:
  - `questions.yml`: shared settings and questions;
  - `copier.yml`: bundled entry point;
  - `<profile>/profile.toml`: the profile manifest;
  - `<profile>/template/`: the project tree. Only `*.jinja` files are rendered. Component files use
    conditional names such as `{% if 'database' in components %}migrations{% endif %}`.
- `pytemplate/components/<id>.toml`: component manifests.
- `copier.yml` (repo root): the git entry point that `copier update` uses at `vX.Y.Z` tags.
- `tests/`:
  - unit and CLI tests;
  - `test_composition.py`: every distinct component set renders exactly its components' owned
    paths and dependencies;
  - `test_packs.py` (fixture pack in `conftest.py`);
  - `test_updating.py` (local git fixture);
  - `test_generated_projects.py`: opt-in smoke tests of every component set.

## Invariants

- **No consumer coupling:** this is a generic factory. Never import, depend on, or name a
  downstream framework or product in code, templates, or dependencies. Downstream
  projects call the CLI or `pytemplate.api` and ship their own profiles as template packs. The
  current roadmap is [PLAN.md](PLAN.md); earlier phases are in [docs/plans/](docs/plans/).
- **Deterministic rendering:** no environment variables, clock values, or network access in the
  template context. Identical requests produce byte-identical projects.
- **Safe templates:** never add Copier `_tasks` or `_migrations`, and keep `unsafe=False`.
- **Components own their files:** a component's `paths` render exactly when it is selected, no
  file has two owners, and the generated `pyproject.toml` declares exactly the resolved
  dependencies. `tests/test_composition.py` enforces this. Adding a component means a manifest,
  its files in compatible profile trees, and a `components` choice in `questions.yml`, and never
  a CLI or renderer change.
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
- Bump a profile's or component's `version` when its generated output changes, and add a
  `CHANGELOG.md` entry under "Unreleased" for user-visible changes.
- Templated lines must fit 100 characters even for a 41-character project name. Write multi-name
  imports of the generated package in exploded form, with a trailing comma.

## Boundaries

Ask before you:
- change release or CI workflows;
- bump the package version;
- create tags;
- publish;
- loosen a safety invariant above.

Never commit secrets or tokens.
