# Contributing

Thanks for helping improve pytemplate-uv. Please be respectful and constructive in issues and
reviews.

## Setup

[uv](https://docs.astral.sh/uv/) is the only prerequisite.

```bash
git clone https://github.com/yuxuzi/pytemplate-uv
cd pytemplate-uv
uv sync
```

## Checks

Run these before opening a pull request. CI runs the same commands.

```bash
uv run ruff check .
uv run ruff format --check pytemplate tests
uv run mypy
uv run pytest
PYTEMPLATE_SMOKE=1 uv run pytest tests/test_generated_projects.py   # needs network, ~3 minutes
PYTEMPLATE_SMOKE=1 PYTEMPLATE_SMOKE_PROFILE=fastapi uv run pytest tests/test_generated_projects.py
```

## Changing templates

- Templates are Copier templates in `pytemplate/templates/<profile>/`. Only files ending in
  `.jinja` are rendered; keep GitHub Actions `${{ }}` expressions in non-`.jinja` files, or wrap
  them in `{% raw %}` blocks.
- Generated projects must pass every resolved `lifecycle_commands` entry. The smoke test renders
  every distinct component set of every profile with a long project name and runs them all.

## Adding a component

1. Write `pytemplate/components/<id>.toml` (`pytemplate schema component`). Declare its
   `requires`, `conflicts`, dependencies, owned `paths`, `settings`, and `security_notes`.
2. Add its files to each compatible profile tree, behind conditional names such as
   `{% if '<id>' in components %}name{% endif %}`. Use `{% if %}` blocks only inside files the
   profile or another component owns.
3. Add its dependencies to the profile's `pyproject.toml.jinja` and its settings to
   `.env.example.jinja`.
4. Add `<id>` to the `components` choices in `questions.yml` and to `optional_components` in each
   compatible `profile.toml`.
5. Run `uv run pytest tests/test_composition.py`, then the smoke tests. Composition fails if
   owned paths, dependencies, or settings drift from the manifest.

No change to `main.py`, `rendering.py`, or unrelated profiles is needed.
- Keep the profile's `CLAUDE.md.jinja`, `README.md.jinja`, CI workflow, and `lifecycle_commands`
  consistent; tests check that the commands match.
- Never add Copier `_tasks` or `_migrations`, network access at render time, or real secrets.
- Questions live in `pytemplate/templates/questions.yml` and are shared by all profiles. Add new
  questions instead of renaming or removing existing ones, so `copier update` keeps working for
  existing projects.
- Keep the repo-root `copier.yml` and `pytemplate/templates/copier.yml` equivalent; a test renders
  both and compares the output.
- Name ignore files inside templates `.gitignore.jinja`; nothing under `pytemplate/templates/`
  may be git-ignored.
- Bump the profile `version` in `profile.toml` when generated output changes.

## AI coding agents

[AGENTS.md](AGENTS.md) holds the instructions and invariants for AI coding agents; `CLAUDE.md`
imports it. Keep it current when commands, layout, or rules change.

## Pull requests

- Keep changes focused, add tests for behavior changes, and update `CHANGELOG.md` under
  "Unreleased".
- Describe what changed and how you verified it.

## Releases

Maintainers bump `version` in `pyproject.toml`, move the changelog entries under the new version,
and push a tag `vX.Y.Z`. The release workflow tests, builds, and publishes to PyPI through Trusted
Publishing.
