# PLAN.md — pytemplate-uv 3.1: agent-ready projects

This is the working plan for the next release. It adds what comparable generators offer for AI
coding agents, where that fits a deterministic, safe factory. The 3.0 plan (factory contract,
FastAPI foundation, authentication) is finished; its record is in the git history and the 3.0.0
CHANGELOG entry.

Status key: `[x]` done and verified, `[ ]` open.

## 1. Comparison (2026-11-11)

Read from each project's PyPI metadata or repository README on that date. "No" means the page
does not show it.

| Project | Kind | Agent guidance in generated projects | Agent tooling | Other notable features |
| --- | --- | --- | --- | --- |
| pytemplate-uv 3.0 | PyPI CLI, Copier | `CLAUDE.md` only | Claude Code skill; `--json` on every command | Components with resolution, template packs with pins, 26 combinations checked in CI |
| [pjkm](https://pypi.org/project/pjkm/) 0.1.1 | PyPI CLI | No | The generator is an MCP server | 105 groups, 22 recipes, a LangGraph agent recipe |
| [dev-ready](https://pypi.org/project/dev-ready/) 0.13.0 | PyPI CLI | `AGENTS.md`, skills in `.agents/skills/`, links for each agent | Its own skill; MCP config | One FastAPI and React base fetched from GitHub at render time |
| [agent-scaffold-cli](https://pypi.org/project/agent-scaffold-cli/) 0.4 | PyPI CLI | No | Asks a model to write the project; needs an API key | Agent projects for several frameworks |
| [agentic-devkit](https://pypi.org/project/agentic-devkit/) 0.1.16 | PyPI CLI | `AGENTS.md` as a router to layered documents | Adapters for Cursor, Claude, and Copilot | Overlay onto an existing repository |
| [simple-modern-uv](https://github.com/jlevy/simple-modern-uv) | Copier template | `AGENTS.md`, and a `CLAUDE.md` that imports it | Skill in the Agent Skills format for several agents | 14-day dependency cooldown, SHA-pinned Actions |
| [python-copier-template](https://github.com/mjun0812/python-copier-template) | Copier template | `AGENTS.md` and `CLAUDE.md` | `.claude/settings.json` permissions, a format hook, Codex hooks | Devcontainer with the agents installed |
| [python-production-template](https://github.com/oedokumaci/python-production-template) | Copier template | `CLAUDE.md`, Cursor rules | Project skills: commit, release, review, docs | ty, taskipy, docs site |
| [uv-forge](https://uv-forge.readthedocs.io/en/latest/overview.html) | Copier template | No | No | zizmor, Sigstore signing, SLSA provenance, 100% coverage |
| [cookiecutter-uv](https://github.com/osprey-oss/cookiecutter-uv) | Cookiecutter template | No | No | Docs site, devcontainer, tox-uv, PyPI publishing |
| [PyScaffold](https://pypi.org/project/pyscaffold/) 4.6 (2024) | PyPI CLI | No | No | Extensions; pip and tox based |

What pytemplate-uv already does better: no other project here resolves components against
manifests, checks every combination in CI, pins external templates to a digest, or renders
without the network, a model, or code execution.

What it lacks:

1. **`AGENTS.md`.** Four competitors write the cross-agent file; pytemplate-uv writes guidance
   only Claude Code reads by default.
2. **A project that is itself an agent tool.** Competitors either ask a model to write one or
   ship a framework recipe. None renders a tested MCP server deterministically.
3. **A skill for agents other than Claude Code.** `skill install` only knows `.claude/skills`.
4. **Agent harness settings**: permissions and hooks in generated projects.
5. **An MCP server for the generator itself.**
6. **Supply-chain hardening** of generated CI: SHA-pinned Actions and a dependency cooldown.
7. **Devcontainer and a docs site.**

## 2. Decisions

- **3.1 takes gaps 1 to 3.** They are additive, need no new dependency in the generator, and
  can be proven by the existing composition and smoke tests.
- **`AGENTS.md` is the one source of guidance.** `CLAUDE.md` becomes a one-line import of it, so
  the two never drift. This is part of both profiles, not a component: it adds no combination
  to the test matrix.
- **`mcp` is a component of the `python` profile.** It adds a stdio server on the official
  `mcp` SDK (2.x, `MCPServer`), one read-only tool over `core`, a `<package>-mcp` script, a
  `.mcp.json` that registers the server for agents working in the project, and a test that
  calls the tool through the server. The `python` profile goes from 2 to 4 combinations (28 in
  total).
- **No model calls, ever.** The generator stays deterministic and offline. That rules out the
  agent-scaffold approach, and it rules out a bundled "LLM application" profile that would have
  to choose a provider SDK; such a profile belongs in a template pack.
- **Gap 4 waits.** A permissions file pre-approves commands on the user's behalf, and a hook runs
  code. Both need a decision on safe defaults and a check against each agent's current
  settings format before they ship.
- **Gap 5 waits.** It adds the `mcp` SDK as a generator dependency (an extra at most). The CLI's
  `--json` output and the skill already cover the same ground.
- **Gaps 6 and 7 are not agent features.** They are listed in section 5 for a later release.

## 3. Steps

### Agent guidance

- [x] 1. Both profiles render `AGENTS.md` (the former `CLAUDE.md` content) and a `CLAUDE.md`
       that imports it. Profile versions go to `4`.
- [x] 2. Tests: lifecycle commands appear in `AGENTS.md` and the CI workflow; `CLAUDE.md`
       imports `AGENTS.md`.

### MCP server component

- [x] 3. `components/mcp.toml` and its files in the `python` tree; the `mcp` choice in
       `questions.yml`; `mcp` added to the reserved package names.
- [x] 4. Generated `pyproject.toml`, `README.md`, and `AGENTS.md` describe the server when it is
       selected.
- [x] 5. Smoke tests for all four `python` combinations.

### Skill

- [x] 6. `skill install --agent agents` writes to `.agents/skills`, the directory Codex and
       other Agent Skills clients read. `claude` stays the default.
- [x] 7. `SKILL.md` maps "MCP server" and "tools for an AI agent" to the `mcp` component and
       points to `AGENTS.md`.

### Release

- [x] 8. README, `AGENTS.md`, and the CHANGELOG.
- [ ] 9. Maintainer only: choose the version number (see the note below), bump it, confirm CI on
       all runners, and tag.

**Version note.** `main` already holds the removal of `pytemplate update` (PR #9).
[docs/compatibility.md](docs/compatibility.md) rule 3 says removals happen only in a major
release, after a deprecation. Releasing this as 3.1.0 needs either an exception recorded in the
CHANGELOG or the number 4.0.0.

## 4. Acceptance criteria

- Every generated project has an `AGENTS.md` naming its lifecycle commands, and a `CLAUDE.md`
  that imports it.
- `pytemplate create NAME -p python -c mcp` renders a project whose lint, format, strict
  type-check, and tests pass, and whose test calls the tool through the server.
- Without `mcp`, no MCP file or dependency is rendered.
- `skill install --agent agents --project` writes `./.agents/skills/pytemplate/SKILL.md`.
- The generator has no new dependency.

## 5. Later candidates

| Candidate | Needs first |
| --- | --- |
| `mcp` for the `fastapi` profile (streamable HTTP mounted on the service, behind the auth components) | A decision on how tool calls map to scopes |
| Agent settings component: a deny rule for secret files, pre-approved lifecycle commands, a format hook | Safe defaults; a test against each agent's settings format |
| Project skills in generated projects (release, review) | Evidence they help; a rule against scripts in skills |
| `pytemplate mcp`: the generator as an MCP server | Approval of an optional `mcp` dependency |
| SHA-pinned Actions and a dependency cooldown in generated CI | A way to keep pins current without `update` |
| Devcontainer component | Nothing; one more combination per profile |
