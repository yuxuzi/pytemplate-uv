# pytemplate-uv

<p align="center">
  <img src="https://raw.githubusercontent.com/yuxuzi/pytemplate-uv/main/.github/assets/logo.svg" alt="pytemplate-uv logo" width="160">
</p>

<p align="center"><strong>Generate once. Own your code.</strong></p>

<p align="center">

[![PyPI](https://img.shields.io/pypi/v/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![Python](https://img.shields.io/pypi/pyversions/pytemplate-uv)](https://pypi.org/project/pytemplate-uv/)
[![CI](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuzi/pytemplate-uv/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</p>

pytemplate-uv is a deterministic application factory that generates **uv-native** Python
projects: choose a profile (a typed CLI package, a library, or a FastAPI service), add components
(database, authentication, background jobs), and get a project that passes linting, formatting,
type-checking, and tests from its first commit.

**Documentation: <https://yuxuzi.github.io/pytemplate-hub/learn/>.** The tutorial and every guide
live on the website; this README is a summary that links to them.

```bash
uvx pytemplate-uv@latest create my-tool -y
cd my-tool
uv run pytest
```

- **Deterministic:** identical requests produce byte-identical projects.
- **Checked:** every bundled component combination is generated and checked in CI.
- **uv-native:** generated projects need only `uv` and `uvx` (no pip, virtualenv activation, or make).
- **Type-safe:** strict mypy on generated code; requests are validated before anything is written.
- **Extensible:** template packs add your own profiles and components without forking.

## Documentation

| Page | What it covers |
| --- | --- |
| [Tutorial](https://yuxuzi.github.io/pytemplate-hub/learn/tutorial/) | Your first project, a pack from the hub, and a pack of your own, listed |
| [Using pytemplate-uv](https://yuxuzi.github.io/pytemplate-hub/learn/guide/) | Every command and option, request files, coding agents, and the Python API |
| [Template packs](https://yuxuzi.github.io/pytemplate-hub/learn/packs/) | Using a pack from the hub, writing one, and pinning it |
| [Publish a pack](https://yuxuzi.github.io/pytemplate-hub/publish/) | Listing your pack on the hub |
| [Compatibility and versioning](https://yuxuzi.github.io/pytemplate-hub/learn/compatibility/) | What each release keeps stable |
| [Changelog](CHANGELOG.md) | What changed in each release |

## Install

No installation is needed: `uvx pytemplate-uv@latest` runs the latest release. To install the
`pytemplate` command, run `uv tool install pytemplate-uv`. It requires Python 3.11 to 3.15, on
Linux, macOS, or Windows.

## What you get

- **Profiles:** `python` (a typed package with a Typer CLI), `library` (a typed package with no
  CLI), and `fastapi` (a layered REST API service).
- **Components:** `database`, `worker`, `auth-api-key`, `auth-oidc`, `container`, `devcontainer`,
  `release`, and `mcp`. The generator checks combinations and adds what each one requires.
- **For coding agents:** every project carries an `AGENTS.md`, and `uvx pytemplate-uv@latest skill
  install` teaches Claude Code and other agents to create projects with your confirmation.

```bash
uvx pytemplate-uv@latest create my-api -p fastapi -c database -c auth-oidc -y
uvx pytemplate-uv@latest plan --name my-api -p fastapi -c database   # preview; writes nothing
```

[Using pytemplate-uv](https://yuxuzi.github.io/pytemplate-hub/learn/guide/) covers every profile,
component, command, and option.

## Find templates on the hub

[pytemplate-hub](https://yuxuzi.github.io/pytemplate-hub/) is the official index of template
packs. Name a listed pack with `-h` (`--hub`): pytemplate-uv reads the tag, commit, and digest the
hub checked, and refuses the pack if anything changed since.

```bash
uvx pytemplate-uv@latest list-profiles -h yuxuzi/pytemplate-starters@v1.0.0
uvx pytemplate-uv@latest create my-app -h yuxuzi/pytemplate-starters@v1.0.0 -p cli -y
```

For CI and offline use, and for writing your own pack, see
[Template packs](https://yuxuzi.github.io/pytemplate-hub/learn/packs/).

## Contribute

```bash
uv sync
uv run pytest                    # unit tests
PYTEMPLATE_SMOKE=1 uv run pytest # every component combination, generated and checked
uv run ruff check .
uv run mypy
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, and [AGENTS.md](AGENTS.md) for coding
agents. A new kind of project usually belongs in your own template pack rather than in the bundled
catalog: [publish it on the hub](https://yuxuzi.github.io/pytemplate-hub/publish/). The website's
pages are edited in [pytemplate-hub](https://github.com/yuxuzi/pytemplate-hub).

## License

MIT. See [LICENSE](LICENSE).
