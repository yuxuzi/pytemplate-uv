# Engineering Review and Evolution Plan: AI-Powered Quantitative Application Factory

## Product direction

`uv-template` is an existing Python project generator. Its intended direction is to become an **AI-powered application factory** for creating well-structured quantitative-finance applications, while remaining useful for straightforward Python projects.

The product should make it easier to create reliable projects through a combination of curated project profiles, explicit configuration, and AI-assisted guidance or generation where that is genuinely valuable. The basic generator must remain understandable, deterministic, and lightweight; AI features should be optional rather than becoming a hidden dependency of every generated project.

## Objectives

1. Inspect the current implementation and document its real behavior, limitations, and quality level.
2. Critically evaluate the existing design against the target of an AI-powered quantitative application factory.
3. Identify confirmed issues, design constraints, and risks in the current implementation.
4. Propose a phased, minimal plan to improve the generator without prematurely building every future capability.
5. Recommend the single highest-value next implementation task, then wait for approval before making implementation changes.

## Scope and constraints

This document guides the engineering review. During the review:

- Inspect files and run only safe, relevant existing commands.
- Do not modify, create, delete, or reformat project files other than this plan document.
- Do not install dependencies, make external changes, or run destructive commands without approval.
- Do not expose secrets if encountered.
- Base conclusions on inspected files and actual command output.
- Clearly distinguish confirmed defects, design preferences, and speculative risks.
- Do not implement recommendations until approval is given.

## Phase 1 — Establish the current baseline

### Repository and execution flow

- Explain the purpose of important files, packages, modules, templates, and configuration files.
- Identify public interfaces and entry points, including CLI commands.
- Trace the full path from a user command to a generated project.
- Explain how templates are stored, discovered, rendered, copied, and validated.

### Packaging and developer experience

- Review `pyproject.toml`, the build backend, dependencies, Python-version support, and `uv` usage.
- Evaluate alignment with current Python packaging practices.
- Identify unnecessary dependencies, questionable version constraints, and portability concerns.

### Tests and observable behavior

- Inventory existing tests and state precisely what each test verifies.
- Run relevant existing tests without installing dependencies; report actual results and any blockers.
- Evaluate coverage of success paths, invalid input, missing files, output-directory conflicts, and failure recovery.
- Do not state coverage percentages unless they are measured.

## Phase 2 — Critique the existing design

Evaluate the implementation critically rather than merely describing it.

- Assess separation of concerns, modularity, error handling, configuration, logging, observability, and maintainability.
- Assess whether profiles can be added without changing unrelated core logic.
- Identify brittle assumptions in paths, templates, user input, filesystem behavior, platform support, and subprocess execution.
- Identify security concerns relevant to generating files, rendering templates, and executing commands.
- Rank findings as critical, high, medium, or low, with file paths and evidence.
- Separate confirmed defects from preferences and risks that require further validation.

## Phase 3 — Evaluate the AI-powered quant-app target

Assess the gap between the current generator and a reliable AI-powered quantitative application factory.

### Target capabilities to assess

- A minimal Python library or CLI project.
- A FastAPI application.
- A quantitative-finance application, such as research, data ingestion, backtesting, or trading-service foundations.
- An AI-agent application with optional MCP integration.
- Reusable project profiles with configurable dependencies and optional components.
- AI assistance for profile selection, configuration drafting, explanation, or code scaffolding.

### Design principles for the target

- Generated projects should be deterministic, reviewable, and usable without an AI service.
- AI-assisted functionality should be opt-in, bounded by clear inputs and outputs, and never silently execute unsafe actions.
- Profiles should declare their metadata, dependencies, templates, validation rules, and optional modules through stable extension points.
- Quantitative-finance and AI-agent profiles should be composable where practical, but not coupled to the minimal starter profile.
- MCP support should be optional and isolated behind an integration boundary.
- Secrets, credentials, provider-specific configuration, and network actions must be explicit and safely handled.

## Phase 4 — Produce the engineering review

Deliver a prioritized report containing:

1. Executive summary and current maturity assessment.
2. Architecture and execution-flow explanation.
3. Strengths worth preserving.
4. Findings ranked by severity, with evidence and affected file paths.
5. Test results, test gaps, and limitations of the test run.
6. Recommended target architecture for deterministic core generation, profiles, and optional AI capabilities.
7. Risks, trade-offs, and features to defer.
8. The single highest-value next task.

## Phase 5 — Proposed implementation roadmap

After the review, propose milestones with scope and acceptance criteria. The roadmap should remain minimal and revise priorities based on Phase 1–4 evidence.

### Milestone A: Stabilize the current generator

- Address confirmed correctness, safety, packaging, and test deficiencies.
- Define reliable input, output, and error-handling behavior.
- Acceptance criteria: core generation paths work predictably; errors are actionable; high-value regression tests cover the supported behavior.

### Milestone B: Establish an extensible profile system

- Introduce a clear profile contract and profile discovery mechanism.
- Keep the minimal profile independent of optional domains.
- Acceptance criteria: a new profile can be added through the defined extension boundary without modifying unrelated core logic.

### Milestone C: Add quantitative-finance foundations

- Add one deliberately scoped quant profile, based on actual user workflows.
- Include only essential structure, configuration, tests, and documentation.
- Acceptance criteria: the generated project is runnable, tested, and useful as a quant-app starting point without unnecessary services or dependencies.

### Milestone D: Add optional AI assistance

- Design explicit AI-provider and AI-feature interfaces.
- Add bounded, opt-in assistance for one valuable workflow, such as project configuration or scaffold selection.
- Acceptance criteria: non-AI generation remains fully functional; AI behavior is transparent, configurable, testable, and safe by default.

### Milestone E: Evaluate optional MCP integration

- Define a narrow MCP use case only if it provides user value beyond direct library integrations.
- Keep MCP adapters isolated from the generator core and profile contract.
- Acceptance criteria: MCP can be enabled or omitted independently, with documented permissions, failure modes, and tests.

## Explicit deferrals

Unless the review supplies compelling evidence, defer:

- A general autonomous coding agent that writes arbitrary project code.
- Supporting multiple AI providers at initial launch.
- Multiple large quant domains or a complete trading platform template.
- Mandatory cloud accounts, credentials, databases, or network services.
- Complex plugin ecosystems before profile boundaries are validated.
- MCP integration before a concrete, well-tested workflow requires it.

## Phase 2 review findings — current CLI generator

The following findings are grounded in the Phase 1 inspection and test output. They describe the current implementation, not the desired design.

### Critical

1. **The test suite is not runnable.** `pytest` recursively collects the unrendered tests under `templates/`, where Cookiecutter expressions are invalid Python syntax. The root test module also imports a nonexistent `cli` module. The recorded run collected zero tests and stopped with four collection errors. Evidence: `pyproject.toml` has no `testpaths`; `tests/test_cli.py` imports `from cli import app`; template tests contain `{{cookiecutter.package_name}}` imports.

2. **Generated FastAPI projects are inconsistent at runtime.** The settings model declares a required `SECRET_KEY`, and a generated `.env` supplies a placeholder. More importantly, application configuration defines `DATABASE_URL`, but `db.py` ignores it and uses a separate hard-coded `sqlite+aiosqlite:///./test.db` URL. Test fixtures create an in-memory engine but do not override the application's `async_session`; endpoint tests can therefore use the hard-coded database instead of the fixture database. Evidence: `templates/fastapi-template/{{cookiecutter.project_name}}/{{cookiecutter.package_name}}/core/config.py`, `db.py`, and `tests/conftest.py`.

### High

1. **The documented and tested CLI contract does not match the implementation.** The actual application exposes one root Typer command with positional `project_name`; the README and root tests expect a `create-project` subcommand and `--name` or `--project-name` options. The documented executable is also `pytemplate-uv`, while package metadata installs `pytemplate` and `create-project`. Evidence: `README.md`, `tests/test_cli.py`, `pytemplate/main.py`, and `pyproject.toml`.

2. **Template availability after package installation is not established.** Runtime template discovery walks from the source module to a sibling top-level `templates/` directory. The package-data declaration attempts to include paths using `../templates`, while the only declared package is `pytemplate`. This makes wheel and installed-package behavior uncertain and must be verified before relying on a published CLI. Evidence: `pytemplate/main.py` and `pyproject.toml`.

3. **The generator mixes orchestration, discovery, configuration, presentation, and process execution in one module.** This impedes focused tests and leaves no stable contract for profiles, validation, output locations, or non-interactive use. Evidence: all generator responsibilities reside in `pytemplate/main.py`.

### Medium

1. **The generator shell-out model provides weak failure diagnostics.** `subprocess.run()` does not capture standard output or error, so the subsequent diagnostic branches normally have no content. It also does not handle a missing `cookiecutter` executable or other `OSError` failures. Evidence: `pytemplate/main.py`.

2. **Input and output behavior are underspecified.** Project names are passed straight to Cookiecutter; there is no explicit project-slug/package-name validation, output-directory option, dry-run, preflight conflict summary, or structured result. `--force` delegates overwrite behavior directly to Cookiecutter. This is not a confirmed exploit, but it is a reliability and safety risk for a project generator. Evidence: `pytemplate/main.py`.

3. **Template metadata is not a profile contract.** The two templates are discovered only by directory naming. Their `cookiecutter.json` files contain overlapping, unstructured keys and inconsistent Cookiecutter directives, so capabilities, supported options, compatibility, and validation cannot be queried by the CLI. Evidence: both template `cookiecutter.json` files.

4. **The generated projects contain broad and mismatched defaults.** Both profiles include substantial tooling and configuration that the core generator does not use. The FastAPI profile includes database, CORS, security, and pre-commit defaults, with permissive host/CORS defaults and dependencies such as `pre-commit` in runtime dependencies. This is a design concern, not a claim that every default is inherently wrong. Evidence: generated `pyproject.toml`, `.env`, and FastAPI core modules.

### Low

1. **Metadata and release hygiene drift.** `setuptools_scm` is configured although the project version is static, generated `version.py` reports a different development version, and the declared changelog URL points to a file absent from the inspected repository. Evidence: `pyproject.toml`, `version.py`, and repository file inventory.

## Improvement plan: evolve from a template wrapper to a reliable CLI generator

### Phase A — Restore a trustworthy baseline

Scope:

- Define one public CLI contract and make the executable name, command hierarchy, arguments, documentation, and tests agree.
- Configure test discovery to exclude unrendered template source, repair root test imports, and add hermetic tests using temporary output directories.
- Resolve template packaging and add an installed-artifact verification test.
- Remove generator-runtime dependencies that belong only to generated profiles or development tooling.

Acceptance criteria:

- `pytest` completes collection and runs the root generator tests.
- `--help`, documentation, and tests describe the same CLI syntax.
- An installed wheel can list and render its bundled profiles without a source checkout.

### Phase B — Separate the CLI generator core

Scope:

- Split the current module into CLI presentation, profile discovery, request validation, rendering service, and result/error reporting.
- Use Cookiecutter as a library behind a renderer adapter, or retain a subprocess adapter with captured output and explicit executable errors.
- Add `--output-dir`, `--dry-run`, a conflict preflight, and explicit overwrite semantics.
- Validate names and normalize the package identifier according to a documented policy.

Acceptance criteria:

- Core rendering can be tested without Typer or terminal output.
- Invalid requests and filesystem conflicts produce actionable, stable errors.
- A render request yields a structured result containing profile, output path, and affected files.

### Phase C — Introduce versioned profile contracts

Scope:

- Define profile metadata: identifier, display name, version, description, template location, required inputs, optional components, dependency groups, and compatibility constraints.
- Provide `list-profiles` and `describe-profile` commands.
- Keep the minimal Python CLI/library profile independent, then migrate FastAPI as a separately owned profile.
- Prefer declarative profile options over scattered Cookiecutter keys.

Acceptance criteria:

- Adding a profile uses its own manifest and template directory without edits to renderer core logic.
- The CLI validates profile-specific input before files are rendered.
- Profile metadata is independently unit-tested.

### Phase D — Repair and scope the generated profiles

Scope:

- Make generated packaging, scripts, Makefiles, READMEs, tests, and dependency groups internally consistent.
- For FastAPI, use settings as the single source of truth for database configuration; inject database sessions in tests; remove placeholder production secrets from tracked runtime configuration; and make security defaults deliberate.
- Add generation smoke tests for each profile, then run the generated project tests in an isolated temporary environment when dependencies are available.

Acceptance criteria:

- Each generated profile passes its own focused smoke test.
- The FastAPI profile can start and test against a configured isolated database.
- Development tools are not installed as runtime dependencies unless they are required at runtime.

### Phase E — Prepare optional domain and AI extensions

Scope:

- Add one narrowly defined quant profile only after the core profile contract is stable.
- Define optional components such as data access, research notebooks, backtesting, or service APIs as explicit profile capabilities.
- Design AI assistance as an opt-in planning/configuration layer that produces a validated render request; it must not bypass validation, silently run commands, or be required for deterministic generation.
- Evaluate MCP only for a concrete, bounded integration after the CLI and profile boundaries are established.

Acceptance criteria:

- Non-AI generation remains complete and deterministic.
- An AI-assisted request is reviewable before rendering and maps to the same validated request model as manual CLI input.
- Optional integrations can be absent without affecting baseline profiles.
