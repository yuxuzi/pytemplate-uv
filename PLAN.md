# PLAN.md — Phase 3.1–3.3: pytemplate-uv 3.0

This is the working plan for the **3.0.0** PyPI release. It turns the generator into a
deterministic application factory built from three parts:
- profiles, which own an application's shape;
- composable components, which add narrow capabilities;
- explicitly selected external template packs.

The Phase 2 record (Copier migration, green generated projects, `copier update`) is archived in
[docs/plans/phase-2.md](docs/plans/phase-2.md).

Status key: `[x]` done and verified, `[ ]` open.

## 1. Context

What already works:
- `list-*` and `describe-*` with `--json`;
- `validate` and `create-from-config`;
- a SHA-256 manifest inventory and `copier update`.

Three gaps remain:
1. **Components are decorative.** `profiles.resolve_components()` requires the selection to equal
   `default_components`, and every manifest's `template_fragments` names the whole template.
   Selecting components changes nothing. This is open critique item 5 from Phase 2.
2. **The FastAPI profile is not a foundation.** It always ships SQLModel and a database. It has
   no readiness endpoint, structured logging, layering, or authentication.
3. **Callers cannot extend the factory without forking it.** Other projects need their own
   profiles (for example, domain-specific tool packages), but the bundled templates are the only
   source.

## 2. Decisions

- **No dependency on any consumer.** pytemplate-uv is generic. It never imports, depends on, or
  names a downstream framework. Downstream projects call it from outside, through
  `uvx pytemplate-uv==3.0.*` with JSON in and out, or through the `pytemplate.api` Python API.
  They ship their own profiles as a template pack.
- **The contract is versioned separately from releases.** `contract = 1` covers the
  profile/component/pack manifest format. A breaking change to the format raises the contract
  number. Profile and component `version`s change whenever their generated output changes.
- **Composition stays inside Copier.** Component files live in the compatible profile's tree
  behind conditional path names, and a `components` multiselect question is stored in
  `.copier-answers.yml`, so `copier update` keeps working. A test checks the manifests against the
  rendered output. There is no second merge engine.
- **Packs are explicit, never discovered.** They are selected by path or git ref on each request,
  with no entry points or scanning. They render under the same rules: `unsafe=False`, and no
  `_tasks`, `_migrations`, or `_jinja_extensions`.
- **Advanced features are opt-in.** The default FastAPI service needs no database, Docker, or
  identity provider.
- **Release number 3.0.0.** A major release, because it breaks compatibility with 2.x.
  Breaking changes: FastAPI's default drops the database, the manifest moves to v2, and
  component errors become stricter.

## 3. Phase 3.1: the factory contract

### Manifests

`profile.toml`:

| Key | Meaning |
| --- | --- |
| `contract` | Manifest format version (`1`) |
| `id`, `name`, `description`, `version`, `aliases` | As today |
| `kind` | `library`, `cli`, or `service` |
| `status` | `stable` or `experimental` |
| `supported_python` | CPython minors, 3.11–3.14 |
| `default_components`, `optional_components` | What is always included and what may be added |
| `dependencies`, `dependency_groups` | The profile's own runtime requirements and PEP 735 groups (for example `dev`) |
| `questions` | The subset of `questions.yml` this profile asks |
| `lifecycle_commands`, `security_posture` | As today |

`components/<id>.toml`:

| Key | Meaning |
| --- | --- |
| `contract`, `id`, `name`, `description`, `version`, `status` | Identity; `status` is `stable`, `experimental`, or `planned` |
| `compatible_profiles`, `requires`, `conflicts` | Resolution constraints |
| `dependencies` | Runtime requirements added to `[project] dependencies` |
| `dependency_groups` | Table `{group = ["spec", ...]}` added to `[dependency-groups]`; both can be inspected without rendering |
| `paths` | Globs of files the component owns in the rendered project |
| `settings` | Env vars: name, type, `required_in_production`, `secret` |
| `lifecycle_commands`, `security_notes` | Commands and notes the component adds |

Unknown keys, wrong types, duplicate list entries, and an unsupported `contract` fail at load
time, and the error names the file. `check_catalog()` also checks the references between
manifests:
- every name in `compatible_profiles`, `requires`, `requires_any`, and `conflicts` exists;
- profiles and components list each other in both directions;
- no default component is `planned`.

A `planned` component shows up in `list-components` and `describe-component`, but selecting it
fails with an actionable error. Every bundled component is `stable` in 3.0; `planned` is kept for
packs and future components.

### Resolution

`pytemplate/resolution.py`: `resolve(profile, requested, catalog=None)` works as follows:
- the selection is the profile defaults plus the requested components (defaults are always
  included);
- `requires` is expanded transitively;
- each component is checked against the profile's component lists and for `planned` status;
- `conflicts` are checked from either side.

The result depends only on the set of requested components, never their order. `catalog`
defaults to the bundled components; template packs pass their own.

Errors name the component, the reason, and the fix, for example:
- ``Component 'store' (required by 'cache') is not available for profile 'demo'. Components for
  'demo': base, metrics.``
- ``Components 'metrics' and 'queue' cannot be combined; select at most one of them.``

The result is a `Resolution`:
- components, ordered by identifier;
- `requested`, the caller's explicit choices, and `added`, the components pulled in by
  `requires`. Both are kept so update tooling can explain why each component is present;
- merged and deduplicated `dependencies` and `dependency_groups`;
- owned paths;
- settings: two components declaring the same setting differently is a `ManifestError`;
- lifecycle commands and security notes.

### Commands and interfaces

- `pytemplate plan [flags | --config FILE] [--json]` prints the resolution and the exact file list
  without writing anything. It renders into a temporary directory and discards it.
- `--json` on `validate` and `create`, with stable exit codes: `0` ok, `1` invalid request,
  `2` render failure.
- `pytemplate schema {profile,component,pack,request,manifest}` emits a JSON Schema, so callers
  can validate requests without importing this package.
- `--template DIR|gh:org/repo` with `--template-ref TAG` (and `template` / `template_ref` in a
  request TOML) selects an external pack.
- `pytemplate.api` exposes `plan`, `validate`, `render`, and `load_request` as the documented
  Python surface. Everything else is private.

### Template packs

A pack has the same layout as the bundled templates:

```
my-pack/
  pytemplate-pack.toml   # contract = 1, id, version
  questions.yml          # shared questions (may extend the bundled ones)
  copier.yml             # _subdirectory: "{{ profile }}/template"
  <profile>/profile.toml
  <profile>/template/...
  components/<id>.toml
```

The pack's source and ref are recorded in `.pytemplate.toml` and `.copier-answers.yml`, so
`pytemplate update` works for pack-generated projects too.

### Generation manifest v2 (`.pytemplate.toml`)

It contains:
- `schema = 2`;
- the generator name and version;
- the template source (bundled or pack, with its ref);
- the profile id and version;
- `[[components]]` with id and version;
- `[answers]`, the sanitized render answers, never secrets or environment values;
- `[[files]]` with `path`, `sha256`, and `owner` (a profile or component id).

`update` keeps reading v1 manifests.

### Compatibility policy (`docs/compatibility.md`)

- **Contract number:** a breaking change to the manifest format is a major release.
- **Versions:** profile and component `version`s are bumped when their output changes.
- **Dependencies:** generated projects pin them through their own `uv.lock`.
- **Deprecation:** a deprecated component or question stays for at least one minor release, with
  a warning.
- **Questions:** never renamed or removed, only added (a `copier update` constraint).

### Acceptance criteria

- Profiles, components, inputs, constraints, dependency groups, and the file list can all be
  inspected without rendering into the target directory.
- An invalid combination fails before rendering, with a specific, actionable error and exit code
  `1`.
- Each generated project records the generator, template source, profile and component versions,
  and the selected options.
- Adding a component edits only its manifest, its files in compatible profile trees, and the
  question choices. It does not touch `main.py`, `rendering.py`, or unrelated profiles.
  `tests/test_composition.py` enforces this.
- A pack fixture renders through `--template`, is recorded in the manifest, and is rejected if it
  declares `_tasks`, `_migrations`, or `_jinja_extensions`.
- The generator, manifest, and contract tests pass on CPython 3.11–3.14 on Linux, Windows, and
  macOS.

## 4. Phase 3.2: FastAPI service foundation

### Layout of the generated package

```
{{ package_name }}/
  api/             # routers, request/response schemas, FastAPI dependencies
  application/     # services / use cases
  domain/          # models and ports (typing.Protocol)
  infrastructure/  # adapters behind the ports
  bootstrap/       # settings, logging, create_app()
  cli.py           # `serve` (uvicorn, --reload for development)
```

Route handlers only receive dependencies. They never construct infrastructure clients.

### Default (`api` component, no external infrastructure)

- `/health/live` and `/health/ready`. Readiness runs the registered checks, and each component
  contributes its own.
- JSON structured logging with a correlation ID in a `contextvar`. An incoming `X-Request-ID` is
  honoured, and the ID is echoed in the response.
- One error envelope for application, validation, and unhandled errors.
- Environment-prefixed settings, with production validation.
- An example use case backed by an in-memory repository behind a domain port.
- `uv run <package> serve --reload` as the local development command.

### Optional components

| Component | Adds |
| --- | --- |
| `database` | SQLAlchemy 2.x typed ORM (SQLModel removed), Alembic with an initial migration, a repository and unit of work behind the domain port, async SQLite by default, a `postgres` dependency group (`asyncpg`), and a database readiness check |
| `worker` | A `TaskQueue` port, an in-process `BackgroundTaskQueue` adapter, and a job-status endpoint. No queue backend is chosen. |
| `container` | `Dockerfile` and `.dockerignore`, moved out of the default |

For `database`:
- `DATABASE_URL` comes only from settings.
- Migrations are a documented command (`uv run alembic upgrade head`) and never run on startup or
  render.
- Test fixtures apply migrations to a per-test temporary SQLite database.

### Acceptance criteria

- The default service starts locally, passes its tests, and serves both health endpoints with no
  external infrastructure.
- With `database`:
  - migrations are repeatable (`upgrade head` twice is a no-op);
  - test databases are isolated;
  - no database URL is hard-coded in application code.
- The domain, application, and infrastructure layers have separate unit tests, and one
  integration test goes through the real ASGI request path.
- Generated-service tests pass in Linux and Windows CI for every stable component combination.

## 5. Phase 3.3: authentication and security

### Components: `auth` plus exactly one mode

The design changed during implementation. The mode is a component, not an `auth_mode` question,
so each mode's dependencies live in its own manifest. A new generic contract key, `requires_any`,
makes `auth` need at least one mode, and the two modes conflict with each other.

| Component | Behaviour |
| --- | --- |
| `auth` | The principal and scopes, audit, and the rate-limit seam. `requires = ["api"]`, `requires_any = ["auth-api-key", "auth-oidc"]`. Selecting it alone fails with "add --component auth-api-key". |
| `auth-api-key` | Keys come from the environment as SHA-256 hashes and are compared with `hmac.compare_digest` against every entry. A `hash-api-key` CLI command prints the entry to configure. For service-to-service use. |
| `auth-oidc` | JWT validation against a configured JWKS URL, with issuer, audience, expiry, and `sub` checks. Only asymmetric algorithms are allowed (HMAC and `none` are refused in settings). Keys are fetched lazily, off the event loop. Uses `pyjwt[crypto]` in the generated project only. |

Selecting either mode adds `auth` automatically. Leaving out every auth component means no
authentication, for local or internal prototypes.

### Shared pieces

- A `Principal` (subject plus scopes) and a `require_scopes(...)` dependency. Routes never parse
  tokens or call provider SDKs.
- An `AuditSink` port with a structured-logging adapter.
- A rate-limit dependency seam, a no-op by default.
- A log redaction filter for `Authorization`, API keys, and every setting marked `secret`.
- Production validation refuses:
  - placeholder or empty secrets;
  - wildcard or localhost hosts and CORS;
  - `DEBUG`.
- A generated `SECURITY.md` covering:
  - the threat-model assumptions;
  - the deployment responsibilities;
  - the explicit deferral of password and account management.

### Acceptance criteria

- A project can leave out auth, or enable exactly one mode, through the component contract.
- Positive and negative integration tests cover each mode: missing, malformed, expired,
  wrong-issuer and wrong-audience credentials, and insufficient scope.
- Tests use synthetic credentials (locally generated RSA keys for OIDC) and never contact an
  identity provider.
- Production settings with placeholder secrets or permissive CORS fail at startup.

## 6. Steps

### Contract (3.1)

- [x] 1. Contract-1 dataclasses and strict loaders in `profiles.py`, with a reusable `Catalog`
       and `load_catalog()`; slug ids; manifests for every component.
- [x] 2. `resolve()` and `Resolution` in `resolution.py`: `requires`, `requires_any`, and
       `conflicts`; merged dependencies; path ownership through `owner()`.
- [x] 3. A `components` multiselect question, stored in the answers file; conditional paths in
       templates; `tests/test_composition.py` over every distinct component set.
- [x] 4. Manifest schema 2 (template source, component reasons, answers, file owners). `update`
       reads v1 manifests and maps legacy components through the profile's
       `legacy_components`.
- [x] 5. `plan`; `--json` and exit codes 0, 1, and 2 everywhere; `validate` with options and
       template answer checks; `schema` (`pytemplate/schema.py`); `pytemplate/api.py`.
- [x] 6. Template packs (`pytemplate/packs.py`):
       - `--template`, `--template-ref`, and `template` / `template_ref` in request files;
       - shallow git clones with `.git` removed;
       - rejection of symlinks and code-running settings;
       - `tests/test_packs.py`.
- [x] 7. `docs/compatibility.md`.

### FastAPI foundation (3.2)

- [x] 8. The FastAPI template in layers:
       - health and readiness;
       - pure-ASGI request-context middleware with request IDs and a 500 envelope;
       - JSON logs with redaction;
       - the error envelope;
       - settings with production checks;
       - a `Container`;
       - `serve`.
       Health probes skip the host check, so container healthchecks work with production
       `ALLOWED_HOSTS`.
- [x] 9. `database`: SQLAlchemy 2.x, Alembic (URL from settings), a repository and unit of work,
       per-test migrated SQLite, `alembic check`, and a `postgres` group.
- [x] 10. `worker` (task-queue port, in-process adapter, job endpoints) and `container` (both
        profiles).

### Authentication (3.3)

- [x] 11. `auth`, `auth-api-key`, and `auth-oidc`: principal and scopes, audit, redaction, a
        rate-limit seam, `SECURITY.md`, and positive and negative tests per mode.

### Release

- [x] 12. Smoke tests run every distinct component set (26), with a 41-character project name.
- [x] 13. README, `AGENTS.md`, `SKILL.md`, and the CHANGELOG (3.0.0, which includes the unreleased
        2.1 work).
- [x] 14. CI: the smoke matrix split by profile (Linux and Windows × 3.11 and 3.14), and a wheel
        job that inspects, plans, and creates every profile and component.
- [x] 15. Version bumped to 3.0.0 and `uv.lock` refreshed.
- [ ] 16. Maintainer only:
        - push the branch and confirm CI is green on all runners;
        - set up the PyPI trusted publisher and the `pypi` environment;
        - run a TestPyPI dry run;
        - tag `v3.0.0`.

## 7. Verification (2026-10-28, macOS, CPython 3.11 generator, 3.14 generated projects)

| Check | Command | Result |
| --- | --- | --- |
| Unit, contract, composition, and pack tests | `uv run pytest` | 299 passed, 26 skipped (smoke) |
| Lint and format | `uv run ruff check .`, `uv run ruff format --check pytemplate tests` | clean |
| Types | `uv run mypy` | strict, no issues in 13 files |
| Generated combinations | `PYTEMPLATE_SMOKE=1 uv run pytest tests/test_generated_projects.py` | 26 passed: sync, ruff, format, strict mypy, pytest, and `alembic upgrade head` for every component set |
| Generated tests are warning-free | `uv run pytest -W error` in the full API-key and OIDC projects | 54 and 60 passed, 94% coverage |
| Plan writes nothing | `pytemplate plan --name svc -p fastapi -c auth-oidc --json` | 53 files listed, `added: [auth]`, target directory untouched |
| Actionable errors | `pytemplate validate -p python -c auth` and `-p fastapi -c auth` | both exit 1 ("not available for profile 'python'"; "add --component auth-api-key") |
| Service runs | `uv run <package> serve`, then curl | `/health/live` 200; `/health/ready` 200 with `database: ok`; 401 envelope without a key; 400 envelope for an untrusted host; JSON logs |
| Migrations repeatable | generated `test_migrations_are_repeatable_and_match_the_models` | upgrade twice, `check`, downgrade, upgrade: pass |
| Pack rendering | `tests/test_packs.py` | directory and git-tag packs render and are recorded; `_tasks`, `_migrations`, `_jinja_extensions`, and symlinks are rejected |
| No consumer coupling | `uv tree --no-dev --depth 1`; grep for QuantAgentOS | copier, rich, and typer only; no mention in code or docs |
| Distribution | `uv build`, `uvx twine check --strict dist/*`, and the CI wheel script run locally | PASSED; four wheel-generated projects with the expected files |

Not verified locally:
- the Windows and Linux CI runners;
- Docker image builds;
- PostgreSQL (asyncpg) at runtime;
- a TestPyPI or PyPI upload.
