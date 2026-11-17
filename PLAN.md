# PLAN.md — pytemplate-uv 3.2: a friendlier CLI, a faster core, a stronger package

This is the working plan for the next release. The 3.1 plan (agent-ready projects) is finished
and released to PyPI; its record is in the git history and the 3.1.0 CHANGELOG entry.

Status key: `[x]` done and verified, `[ ]` open, `[?]` needs the maintainer's decision first.

## 1. Review findings (2026-11-17, on 3.1.0)

Baseline: `uv run pytest` 326 passed, 28 skipped (smoke); ruff and strict mypy clean. The code is
small (2,600 lines), layered, and well tested. The findings below were reproduced on `main`.

### Command-line experience

| # | Finding | Evidence |
| --- | --- | --- |
| U1 | `create` without `--no-input` fails outside a terminal, after doing the work, with Copier's own advice (`--defaults`, `--data-file`), which are not pytemplate options. It exits 2 (render failure), although nothing about the request was wrong. | `pytemplate create demo </dev/null` |
| U2 | There is no short flag for the most common option. Every README example, the skill, and CI spell out `--no-input`. The community convention (uv, npm, pip, apt, `uv init`) is `-y`/`--yes`. | README lines 98-245 |
| U3 | Errors go to stdout, not stderr, and Rich wraps them at 80 columns, which breaks log parsing and `2>` redirection. | `create Bad_Name ... 2>/dev/null` still prints the error |
| U4 | Unknown identifiers give the full list but no suggestion. | `-c datbase` lists nine components instead of "did you mean 'database'?" |
| U5 | After `create`, the user is not told what to do next, though the profile knows its lifecycle commands. | `create` prints two lines |
| U6 | Interactive mode prompts for text answers but never for components; you must know `-c` names first. | `questions.yml`: `components` is always passed as data |
| U7 | `--json` with prompting enabled would interleave prompts with JSON. | `create --json` without `--no-input` |
| U8 | No shell completion of profile and component identifiers. | Typer supports `autocompletion=` |
| U9 | A pure library cannot be generated: `cli` is a default component of `python`, and defaults cannot be removed. `library` is already a declared profile kind with no profile. | `python/profile.toml` |
| U10 | Three executables (`pytemplate`, `pytemplate-uv`, `create-project`). `create-project` is a generic name that can shadow another tool on `PATH`. | `[project.scripts]` |

### Code

| # | Finding | Evidence |
| --- | --- | --- |
| C1 | `import pytemplate.main` takes about 400 ms; Copier is half of it, and `--help`, `--version`, `list-*`, `describe-*`, and `schema` never use it. | `python -X importtime` |
| C2 | `validate` opens the catalog twice (`validate_request`, then `plan`). For a git pack that is two clones. | `main.py` `validate_config` |
| C3 | `create --dry-run` checks less than `validate`: it skips Copier's answer validators, so a dry run can pass and the real run fail. | `rendering.render` returns before rendering |
| C4 | `git clone` runs with no timeout and with credential prompts enabled, so a private or mistyped pack URL can hang an unattended run. | `packs._clone` |
| C5 | `--template-ref` must be a branch or tag (`clone --branch`); a commit hash cannot be used as the ref, though a commit is the strongest pin. | `packs._clone` |
| C6 | Every command clones a git pack again, even when it is pinned to a commit and a digest, which are immutable. | `open_catalog` |
| C7 | Request errors have two hierarchies: `RequestError` and five `ValueError` subclasses, so the CLI keeps a tuple and API users must catch six types. | `main._REQUEST_ERRORS`, `api.py` docstring |
| C8 | Seven commands repeat the same twelve options and the same `_request(...)` call. | `main.py` is 656 lines |
| C9 | The unsafe-setting check of a pack is a regex over top-level `*.yml` files; it misses flow-style YAML and `!include`d files. Copier's `unsafe=False` remains the real guard, so this is defence in depth only. | `packs._UNSAFE_SETTINGS` |
| C10 | Small items: `pytemplate/__init__.py` has a stray comment and no `__version__`; `exclude_patterns()` is computed twice per render; the manifest writer checks `is_file()` twice. | |

### Package and community

| # | Finding |
| --- | --- |
| P1 | Lower bounds (`rich>=13.7.0`, `typer>=0.12.0`, `copier>=9.4`) are never tested; CI only runs the lock file. |
| P2 | This repository's own Actions are pinned to tags, not commit SHAs, and nothing scans the workflows (zizmor). |
| P3 | Releases do not attach PEP 740 attestations; check whether `uv publish` produces them, or use `pypa/gh-action-pypi-publish`, which does by default. |
| P4 | The README (15 KB) is the only documentation; there is no docs site, no `Documentation` URL, and no badges. |
| P5 | No `SECURITY.md` for reporting vulnerabilities in the generator, and no issue templates. |
| P6 | `Development Status :: 4 - Beta` at a third major version with a written compatibility policy. |

## 2. Decisions

- **`-y`/`--yes` replaces `--no-input`.** It becomes the documented spelling everywhere: README,
  skill, CI, and the hub's generated commands. The compatibility policy (rule 3) requires a
  deprecation period for CLI options, so `--no-input` keeps working, hidden from `--help`, with
  a warning on stderr, and is removed in 4.0. The request-file key `no_input` and the API field
  `RenderRequest.no_input` stay; Quant App Factory uses the API field. If the maintainer wants
  `--no-input` gone in 3.2, record it as a second exception under rule 3, as 3.1.0 did.
- **No prompt without a terminal.** When stdin is not a TTY and `--yes` is absent, `create` exits
  1 before rendering, naming `-y` and `--data KEY=VALUE`. It does not silently accept defaults.
- **`--json` implies `--yes`.** Machine output never prompts. Agents already pass both.
- **Determinism is unchanged.** Interactive defaults may read `git config user.name` and
  `user.email`, because the answers are recorded in `.copier-answers.yml`; the `--yes` path
  never reads the environment.
- **Running programs after rendering is opt-in only.** `--git` (initialise a repository and make
  the first commit) and `--lock` (`uv lock`) are never defaults and never run in `plan`,
  `validate`, or `--dry-run`.
- **No model calls and no new runtime dependency without approval.** Items marked `[?]` name the
  dependency they would add.

## 3. Steps

### Phase 1: command-line experience (PR 1)

- [x] 1. `-y`/`--yes` on `create` and `create-project`; `--no-input` hidden and deprecated with
       a stderr warning. Tests for both spellings and the warning. (U2)
- [x] 2. Refuse to prompt without a TTY (exit 1, actionable message); `--json` implies `--yes`.
       (U1, U7)
- [x] 3. Errors and warnings on stderr through one `Console(stderr=True, soft_wrap=True)`; JSON
       stays on stdout. (U3)
- [x] 4. "Did you mean" suggestions with `difflib.get_close_matches` for profiles, components,
       schemas, and `--data` keys. (U4)
- [x] 5. Next steps after `create`: `cd`, then the profile's lifecycle commands. Human output
       only; JSON already carries `lifecycle_commands`. (U5)
- [x] 6. Shell completion of profile and component identifiers from the bundled catalog. (U8)
- [x] 7. README, skill (`SKILL.md`), CONTRIBUTING, CI workflow, and CHANGELOG use `-y`.
       `tests/test_skill.py` still passes.

### Phase 2: core and performance (PR 2)

- [x] 8. Import Copier and PyYAML lazily, inside the functions that render; add a test that
       `import pytemplate.main` does not import `copier`. Target: `--help` under 150 ms. (C1)
- [x] 9. One pass for `validate`: `plan()` already validates, so add the target check to it and
       drop the second catalog open. (C2)
- [x] 10. `create --dry-run` runs the same checks as `validate`, answers included. (C3)
- [x] 11. Git hardening: `GIT_TERMINAL_PROMPT=0`, a timeout (default 120 s), and an error that
        names the URL and the cause. (C4)
- [x] 12. Accept a full commit hash as `--template-ref` (`git init` + `fetch --depth 1 origin
        <sha>`). (C5)
- [x] 13. One request-error hierarchy: the profile, component, manifest, and configuration errors
        also subclass `RequestError` (keeping `ValueError` for compatibility). The CLI and API
        catch one type. (C7)
- [x] 14. Shared request options in `main.py` (one options object built once per command),
        without changing any option name or default. (C8)
- [x] 15. Parse pack YAML (with includes) for unsafe settings instead of a regex. (C9)
- [x] 16. Small cleanups and `pytemplate.__version__`. (C10)

### Phase 3: package and community (PR 3; workflow edits need approval)

- [x] 17. A CI job that runs the unit tests with `uv sync --resolution lowest-direct`, and raise
        any lower bound that fails. (P1)
- [x] 18. SHA-pin this repository's Actions, add zizmor to CI, and Dependabot for Actions. (P2;
        CI edit)
- [x] 19. PEP 740 attestations on release. (P3; release-workflow edit)
- [x] 20. README badges (PyPI version, Python versions, CI, licence), a `Documentation` URL, a
        `SECURITY.md`, and issue templates for bugs and template requests. (P4, P5)
- [x] 21. A docs site generated from the existing Markdown (MkDocs Material or Zensical) on
        GitHub Pages. (P4; dev dependency and a Pages workflow)
- [x] 22. Classifier `5 - Production/Stable`. (P6)

### Phase 4: features (one PR each)

- [x] 23. `library` profile: a package with tests and tooling but no CLI, `kind = "library"`. One
        combination per optional component. (U9)
- [x] 24. Interactive component picker when `create` runs in a terminal with no `-c`: a
        multi-select of the profile's optional components, with `requires` added and
        `conflicts` refused as now. Needs `questionary` as a direct dependency (Copier already
        installs it). (U6)
- [x] 25. `pytemplate status [PATH]`: read `.pytemplate.toml` and list generated files that were
        changed, deleted, or added since generation. Read-only; it never merges or rewrites, so
        it does not reopen the 3.1.0 decision on `update`.
- [x] 26. Opt-in `--git` and `--lock` on `create`.
- [x] 27. `release` component for `python` and `library`: a trusted-publishing release
        workflow with a tag-equals-version check, like this repository's own.
- [x] 28. `devcontainer` component (already a 3.1 candidate).
- [x] 29. SHA-pinned Actions and a dependency cooldown (`exclude-newer`) in generated CI. Needs
        a way to keep the pins current, since `update` is gone: Dependabot config in the
        generated project is the likely answer.
- [x] 31. Cache git packs pinned to a commit and a digest, keyed by both, under the user cache
        directory; `--no-cache` to bypass. Needs `platformdirs` or a small cache-path
        function. (C6)

### Release

- [ ] 32. CHANGELOG (done), version 3.2.0, `uv.lock`, and the hub's commands updated to `-y` after
        release.
- [ ] 33. Maintainer only: confirm CI is green on all runners, then tag `v3.2.0`.

## 4. Acceptance criteria

- `pytemplate create demo -y` and `pytemplate create demo --no-input` produce byte-identical
  projects; the second prints one deprecation warning on stderr.
- `pytemplate create demo </dev/null` exits 1 before rendering and names `-y`.
- No error text appears on stdout outside `--json`.
- `pytemplate --help` imports no Copier module.
- `pytemplate validate --template <git pack>` clones once.
- Every existing request file, JSON field, exit code, and question works unchanged.
- The 28 generated combinations still pass their lifecycle commands, plus the new `library`
  combinations.

## 5. Not planned

| Idea | Why not |
| --- | --- |
| A bundled LLM-application profile | It must choose a provider SDK; it belongs in a template pack. |
| Prompting or generating with a model | The generator stays deterministic and offline. |
| Bringing back `update` | Merging a template release into a changed project was not safe (3.1.0). `status` reports drift without changing files. |
| `pytemplate mcp` | Still waits for approval of an optional `mcp` dependency; `--json` and the skill cover it. |
