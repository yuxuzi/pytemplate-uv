---
name: pytemplate
description: Create or update a uv-native Python project (typed package with a CLI, or a layered FastAPI service with optional database, background jobs, API-key or OIDC auth, and Dockerfile) with pytemplate-uv. Use when the user asks to create, scaffold, start, bootstrap, or generate a new Python package, CLI, library, or FastAPI/REST API project, or to upgrade a project that pytemplate-uv generated.
---

# Create Python projects with pytemplate-uv

pytemplate-uv renders reviewed Copier templates into projects that pass their own lint, format,
strict type-check, and test commands from the first commit. Your job is to turn the user's request
into a validated render request, get the user's confirmation, render the project, and prove that
it works. Never hand-write a scaffold that the generator can produce.

Run every command through `uvx pytemplate-uv …`, so nothing has to be installed. If the user
already has the `pytemplate` command, you can use that instead.

## 1. Check the tool

```bash
uvx pytemplate-uv --version
```

If `uvx` is missing, ask the user to install uv (https://docs.astral.sh/uv/) and stop.

## 2. Discover what is available

```bash
uvx pytemplate-uv list-profiles --json
uvx pytemplate-uv describe-profile fastapi --json
uvx pytemplate-uv list-components --json
uvx pytemplate-uv describe-component database --json
```

Use the JSON output, not guesses:
- `question_details` lists every input with its help text, default, and choices.
- `default_components` are always included; `optional_components` may be added.
- Each component lists `requires` (added automatically), `requires_any` (pick one), `conflicts`,
  its dependencies, the files it owns, and the environment `settings` it reads.
- If the user names a template pack, add `--template <dir or gh:org/repo>` (and
  `--template-ref <tag>`) to every command, and set `template`/`template_ref` in the request.

Choose the profile from what the user wants to build:
- `python`: a library or command-line tool.
- `fastapi`: an HTTP API or web service.

If the request fits neither, say so instead of forcing a profile.

For `fastapi`, map the user's needs to components and add only what they asked for:
- persistence, SQL, PostgreSQL, migrations: `database`;
- long-running or background work: `worker`;
- service-to-service keys: `auth-api-key`; user login through an identity provider:
  `auth-oidc` (choose one; `auth` is added automatically);
- a Docker image: `container` (also available for `python`).

## 3. Collect inputs

Ask only for what you cannot infer, in one short message:

- **project_name**: a lowercase slug such as `market-data-api` (letters, digits, single hyphens).
  The package name defaults to the slug with `_`. Names that are Python keywords, standard-library
  modules, or dependencies (for example `json`, `tests`, `typer`, `fastapi`) are rejected.
- **description**: one line, with no double quotes or backslashes.
- **author** and **email**: ask; never invent personal details. If the user declines, keep the
  template defaults and tell them.
- **python_version**: the minimum, 3.11–3.15 (default 3.11).
- **license**: an SPDX expression (default MIT).
- **output directory**: an existing parent directory (default: the current directory).

Never put secrets, tokens, or credentials into any input.

## 4. Write and validate a render request

Write `<project_name>.request.toml` in the output directory:

```toml
project_name = "market-data-api"
profile = "fastapi"
components = ["database", "auth-oidc"]
output_dir = "."            # relative to this file

[data]
description = "Market data ingestion service"
author = "Ada Lovelace"
email = "ada@example.com"
python_version = "3.12"
license = "MIT"
```

Then preview it; this validates everything, including the template's answer checks, and writes
nothing:

```bash
uvx pytemplate-uv plan market-data-api.request.toml --json
```

Exit code 1 means the request is invalid: read `error.message`, which says how to fix it, and
plan again. Keep the plan's `lifecycle_commands`; they are the checks for step 6. **Show the user
the request, the resolved components (including any in `added`), the new dependencies, and the
target path, then wait for explicit confirmation before creating anything.**

## 5. Create the project

```bash
uvx pytemplate-uv create-from-config market-data-api.request.toml
```

If the target already exists, stop and ask. Use `--force` only when the user explicitly wants the
existing directory replaced. Delete the request file afterwards, or keep it if the user wants a
reproducible record.

## 6. Prove it works

Inside the new project, run:

```bash
git init
uv sync
```

Then run every command in the plan's `lifecycle_commands` (replace `{package}` with the package
name): `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy <package>`,
`uv run pytest`, and component commands such as `uv run alembic upgrade head`. Report the real
results. If something fails, show the output; do not hide or
"fix" it by weakening checks. Finish by pointing the user to the generated `README.md` and
`CLAUDE.md`, and suggest committing the initial project (`git add -A && git commit`).

## Updating an existing generated project

Projects created by pytemplate-uv 3.0+ contain `.copier-answers.yml` and can be upgraded with a
three-way merge that keeps user edits.

1. Make sure the project is a git repository with no uncommitted changes. Projects from a
   template pack need `--to <pack tag>`.
2. Preview the update (a dry run that writes nothing):
   ```bash
   uvx pytemplate-uv update path/to/project
   ```
3. With the user's approval, apply it:
   ```bash
   uvx pytemplate-uv update path/to/project --apply
   ```
   Add `--to vX.Y.Z` to target a specific template release.
4. Review `git diff` with the user, resolve any `<<<<<<<` conflict markers, run the lifecycle
   commands again, and let the user commit.

## Rules

- Never edit `.copier-answers.yml` or `.pytemplate.toml` by hand.
- Never run `--force` or `update --apply` without explicit user approval.
- Never put credentials into `.env.example`, a request file, or any answer; generated services
  read secrets from the environment only.
- Use pip, virtualenv activation, or make only if the user asks; generated projects use `uv` and
  `uvx`.
- Report what actually happened, including failures.
