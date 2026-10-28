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
PYTEMPLATE_SMOKE=1 uv run pytest tests/test_generated_projects.py   # needs network
```

## Changing templates

- Templates are Copier templates in `pytemplate/templates/<profile>/`. Only files ending in
  `.jinja` are rendered; keep GitHub Actions `${{ }}` expressions in non-`.jinja` files, or wrap
  them in `{% raw %}` blocks.
- Generated projects must pass every command in the profile's `lifecycle_commands`. The smoke test
  renders each profile with a long project name and runs them all.
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
