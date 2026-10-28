# PLAN.md — Phase 2: critique, Copier migration, generated CLAUDE.md

Working plan for Phase 2 of the QuantFoundry engineering plan, which now lives in the
[quant-agent-os](https://github.com/yuxuzi/quant-agent-os) repository at `docs/ENGINEERING_REVIEW_PLAN.md`. It replaces the
older "Phase 2 review findings" section there, most of which (unrunnable tests, CLI contract drift,
template packaging, subprocess rendering) was fixed before this phase began.

Status key: `[x]` done and verified, `[ ]` open.

## 1. Critique of the current generator

Evidence comes from reading the source and from command output on 2026-10-27, when the suite
stood at 17 passing tests on CPython 3.11.

### High

1. **Rendering was not deterministic.** `_context()` read `$USER`, `$USER_EMAIL`, and
   `$GITHUB_USERNAME`, so the same request rendered different files on different machines.
   *Fixed:* answers come only from the request and `copier.yml` defaults. Copier user settings
   are ignored by passing an empty `copier.Settings()`.
2. **`--force` merged instead of replacing, and failures left partial output.** Cookiecutter's
   `overwrite_if_exists` wrote over the old tree, so stale files survived, and nothing was staged.
   *Fixed:* projects render into a `.pytemplate-*` staging directory next to the target and are
   swapped in only after rendering and the manifest succeed, with rollback if the swap fails.
3. **The wheel shipped no template dotfiles.** The `templates/**/*` package-data glob skips hidden
   files, so installed users got projects without `.gitignore`, `.env`,
   `.github/workflows/ci.yml`, or `.pre-commit-config.yaml`. CI never caught this because it
   generates from a source checkout. *Fixed:* explicit dotfile patterns in `pyproject.toml`,
   verified by building the wheel, installing it, and generating projects.
4. **Generated projects fail their own quality gates.** On a fresh project:
   - `python`: 9 ruff errors, 3 files that need formatting, 7 mypy (strict) errors;
   - `fastapi`: 56 ruff errors, 10 files that need formatting, 20 mypy errors.

   Their pytest suites do pass (5 and 11 tests). *Fixed:* both templates were rewritten. Every
   lifecycle command now passes, including with a 41-character project name (step 9).
5. **Components are decorative.** `resolve_components()` requires the selection to equal
   `default_components` exactly, and every component's `template_fragments` names the whole
   profile template, so selecting components changes nothing. *Open:* Phase 3.1.

### Medium

6. **Cookiecutter configuration was broken or unused.**
   - `_copy_without_render` listed variable names instead of paths.
   - `_skip_if_present` is not a Cookiecutter key.
   - The `docs`, `coverage`, `dockerfile`, `mypy`, and `envfile` prompts barely affected output.

   *Fixed:* replaced by `copier.yml` with seven real questions.
7. **Template syntax workarounds.** Every file was rendered, so GitHub Actions `${{ }}` needed
   `{% raw %}` wrappers. *Fixed:* only `*.jinja` files are rendered; workflows are copied verbatim.
8. **Generated `.env` was not git-ignored.** It contains `SECRET_KEY=replace-this-before-production`
   and `CORS_ORIGINS=["*"]`. *Fixed:*
   - FastAPI renders `.env.example` only and drops the unused `SECRET_KEY`.
   - Hosts and CORS are deny-by-default, and wildcards are rejected in production.
   - `.env` is git-ignored.
9. **The python profile's lifecycle command was wrong.** It said `uv run --extra dev pytest`, but
   the generated pytest config needs `pytest-cov` from the `test` extra. *Fixed:* now
   `uv run --extra dev --extra test pytest`, matching the README and CI.
10. **Duplicated CLI code.** `_create` and `_create_from_request` repeated the same error handling.
    *Fixed:* merged into `_render_and_report`.
11. **The manifest has no file inventory.** `.pytemplate.toml` has no rendered-file list or hashes,
    which Phase 3.7 updates need. *Fixed:* `[[files]]` entries with SHA-256 hashes (step 12).

### Low

12. **Dead or misleading leftovers.**
    - Stray `.github/` and `.gitignore` sat at template roots (never rendered).
    - `tests/conftest.py` had fixtures pointing at a nonexistent `templates/` path.
    - Both black and ruff were configured.

    *Fixed.* The FastAPI root `.gitignore` was moved into the template, so generated FastAPI
    projects now get one.
13. **Dated generated packaging.**
    - Generated projects use setuptools.
    - Dev and test tools live in overlapping `[project.optional-dependencies]` extras instead of
      PEP 735 `[dependency-groups]`.
    - The README gives `pip install <package>` instructions for packages that are not published.

    *Fixed:* `uv_build`, PEP 735 `[dependency-groups]`, PEP 639 `license`, and uv-only READMEs
    (step 10).
14. **No agent guidance in generated projects.** *Fixed:* profile-specific `CLAUDE.md`.

## 2. Decisions

- **Copier replaces Cookiecutter as the render engine.** Typer remains the CLI. Copier gives
  question validation, the `.jinja` suffix convention (verbatim copy by default), `_subdirectory`
  layouts, and a future path to `copier update`.
- **Templates run with `unsafe=False` and must not declare `_tasks` or `_migrations`.** Rendering
  never executes template-supplied commands.
- **No `.copier-answers.yml` yet.** It would record the installed package path as the template
  source, which is machine-specific and not a git source, so `copier update` could not use it.
  `.pytemplate.toml` stays the source of truth. Updates remain deferred to Phase 3.7, which needs
  a versioned, git-hosted template source.
- **`CLAUDE.md` is generated per profile, and no `AGENTS.md` yet.** This avoids two copies of the
  same instructions. A generated `AGENTS.md` pointer is a follow-up if other agents need it.

## 3. Template layout

```
pytemplate/templates/<profile>/
  profile.toml      # factory contract (id, version, components, lifecycle_commands, ...)
  copier.yml        # questions; _subdirectory: template, _templates_suffix: .jinja
  template/
    CLAUDE.md.jinja
    pyproject.toml.jinja, README.md.jinja, .env.jinja, ...
    .github/workflows/ci.yml    # not .jinja -> copied verbatim
    {{ package_name }}/...      # templated directory name
```

Questions: `project_name`, `package_name` (validated identifier), `description`, `author`,
`email`, `python_version` (3.11–3.14), `license`. Override with `--data KEY=VALUE` or a `[data]`
table in a render-request TOML file.

## 4. Steps

- [x] 1. Write this plan; cross-reference it from `ENGINEERING_REVIEW_PLAN.md`.
- [x] 2. Replace the `cookiecutter` dependency with `copier>=9.4,<10` (resolved: 9.19.1); refresh `uv.lock`.
- [x] 3. Convert both templates to the Copier layout: profile-ID directories, `copier.yml`, `.jinja`
       suffixes, `{{ var }}` syntax, `{% raw %}` and unused toggles removed.
- [x] 4. Rewrite `render()`: Copier `run_copy`, staging plus atomic swap and rollback, deterministic
       context, `data` overrides validated against the profile's questions.
- [x] 5. CLI and configuration: `--data`, `[data]` table, template inputs in `describe-profile`,
       merged reporting helper.
- [x] 6. Add a profile-aware `CLAUDE.md.jinja` to both profiles; ignore `.env` in generated projects.
- [x] 7. Tests (`tests/test_rendering.py`, plus CLI and config cases); README updated.
- [x] 8. Package template dotfiles in the wheel; verify from an installed wheel.
- [x] 9. Rewrite both templates so generated projects pass `uv sync`, `ruff check`,
       `ruff format --check`, strict `mypy`, and `pytest`. `lifecycle_commands` is the single
       source of truth, checked against `CLAUDE.md`, the generated CI, and the opt-in smoke test
       `tests/test_generated_projects.py`.
- [x] 10. Make generated projects uv-only:
   - `uv_build`, `[dependency-groups]`, and `uv run` everywhere;
   - pre-commit runs through `uvx`, with local hooks;
   - Dockerfiles copy `uv` from `ghcr.io/astral-sh/uv`;
   - no Makefiles or `make`, and no `pip install` instructions.
- [x] 11. CI `package` job: build, `twine check --strict`, then generate both profiles from the
       wheel through `uvx` and assert that the dotfiles exist.
- [x] 12. Add a SHA-256 file inventory to `.pytemplate.toml`.

### Round 2: review fixes found while executing

13. **FastAPI template bugs.** *Fixed.*
    - The CSP header blocked Swagger UI's CDN, so `/docs` was broken.
    - CORS allowed `*` with credentials.
    - The Docker `HEALTHCHECK` called a nonexistent `/health` with `curl`, which the image lacks.
    - The container could not write its SQLite file.
    - Tests used the deprecated `event_loop` fixture.
    - `POST` returned 200 instead of 201.
    - The handler reported every exception as a validation error.
    - Table models were returned directly.
14. **The python template's Dockerfile copied a nonexistent `Makefile`** and used `make start`.
    The `license` and `python_version` answers were ignored. *Fixed.*
15. **Free-text answers were inserted into TOML and Python unescaped.** *Fixed:* validators
    reject quotes, backslashes, and newlines; `license` must be an SPDX expression.
16. **Project names such as `class`, `tests`, `typer`, `json`, or `data-` produced broken
    packages.** *Fixed:* keywords, stdlib names, dependency names, the test package, and malformed
    slugs are rejected before rendering.
17. **The package had never been type-checked.** mypy crashed on the template directory, and
    `profiles.py` read TOML values untyped. *Fixed:* strict mypy passes; manifest lists are
    validated; discovery is cached.

### Release readiness

- [x] 18. Packaging:
   - `uv_build` backend; version 2.1.0;
   - PEP 639 license metadata and complete classifiers;
   - `py.typed`, a `Changelog` URL, and tests in the sdist.
- [x] 19. `pytemplate --version`.
- [x] 20. Docs: README (uvx/uv tool install), `CHANGELOG.md`, `CONTRIBUTING.md` (renamed from
       `CONTRIBUTE.md`), and a maintainer `CLAUDE.md`.
- [x] 21. CI jobs:
   - lint and type-check;
   - tests on 3 OSes × CPython 3.11–3.14;
   - generated-project smoke tests;
   - package checks.
- [x] 22. Release workflow: on `v*` tags it checks the tag against the version, tests, builds, runs
       `twine check`, and publishes with `uv publish` through Trusted Publishing.
- [ ] 23. One-time maintainer setup (cannot be done from the repo):
   - on PyPI, add a trusted publisher for `release.yml` and environment `pypi`;
   - create the `pypi` environment in GitHub;
   - push the branch and confirm CI is green on all runners;
   - tag `v2.1.0`.
- [ ] 24. Still open, by design:
   - components remain decorative (critique item 5, Phase 3.1);
   - TestPyPI dry run before the first release.

### Round 3: updates, AI skill, AGENTS.md

- [x] 25. `copier update` support:
   - Questions moved to the shared `pytemplate/templates/questions.yml`.
   - Two entry points (`pytemplate/templates/copier.yml` for bundled rendering, and the repo-root
     `copier.yml` for git tags) are tested to render identically.
   - Generated projects get `.copier-answers.yml` with `_src_path: gh:yuxuzi/pytemplate-uv` and
     `_commit: v<version>`.
   - `pytemplate update [DIR] [--to] [--apply]` is a dry run by default, requires a clean git
     tree, marks conflicts inline, and refreshes the manifest.
   - Tested against a local git fixture: dry run, applied merge, a three-way merge in the same
     file, dirty tree, missing answers file, missing git.
- [x] 26. Bug found by the new tests: each template's `.gitignore` (`.env.*`) was git-ignoring
   `fastapi/template/.env.example.jinja` inside this repo, so it would be missing from release
   tags. Template ignore files are now `.gitignore.jinja`, and a test asserts nothing under
   `pytemplate/templates/` is ignored.
- [x] 27. AI skill:
   - `pytemplate/skills/pytemplate/SKILL.md` defines the flow: discover → ask → write request →
     `validate` → confirm → create → run checks; plus the update flow.
   - `pytemplate skill install [--project|--dest] [--force]` and `skill show`.
   - `--json` on the `list-*` and `describe-*` commands.
- [x] 28. `AGENTS.md` (repo only) is the canonical agent instructions; `CLAUDE.md` imports it with
   `@AGENTS.md`.

## 5. Verification record (round 2: 2026-10-28; round 3 results in the closing summary)

| Check | Result |
| --- | --- |
| `uv sync --locked` | ok |
| `uv run ruff check .` / `ruff format --check pytemplate tests` | clean |
| `uv run mypy` (strict) | no issues in 6 source files |
| `PYTEMPLATE_SMOKE=1 uv run pytest` | 50 passed, including both generated-project smoke tests |
| Generated `python` project | sync, ruff, format, strict mypy, pytest (6 tests), and `uv build` all pass |
| Generated `fastapi` project | sync, ruff, format, strict mypy, and pytest (12 tests) all pass |
| `uv build` + `uvx twine check --strict` | wheel and sdist PASSED |
| `uvx --from <wheel> pytemplate create` (both profiles) | dotfiles, CI, `CLAUDE.md`, manifest present |

Not verified locally:
- the Windows and Linux CI runners;
- Docker image builds;
- an actual PyPI or TestPyPI upload.
