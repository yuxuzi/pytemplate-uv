# Compatibility policy

This page says what pytemplate-uv keeps stable, what may change, and how changes are announced.
It covers the generator, the factory contract (profiles, components, and template packs), and
the projects it generates.

## What is versioned

| Thing | Version | Where | Changes when |
| --- | --- | --- | --- |
| pytemplate-uv | Semantic version, such as `3.0.0` | PyPI, git tag `v3.0.0` | Every release |
| Factory contract | Integer `contract` | `profile.toml`, `components/*.toml`, `pytemplate-pack.toml` | The manifest format changes incompatibly |
| Profile | `version` string | `profile.toml` | The profile's generated output changes |
| Component | `version` string | `components/<id>.toml` | The component's generated output changes |
| Generation manifest | Integer `schema` | `.pytemplate.toml` in each project | The manifest's structure changes |

`pytemplate schema {profile,component,pack,request,manifest}` prints the JSON Schema for each
format.

## Rules

1. **The contract number only changes in a major release.**
   - pytemplate-uv 3.x reads `contract = 1` manifests and nothing else.
   - A pack written for contract 1 keeps working throughout 3.x.
2. **Compatible additions are allowed in minor releases.** These include new optional manifest
   keys, components, profiles, questions, CLI options, JSON output fields, and exit-code
   documentation. Consumers must ignore JSON fields they do not know.
3. **Removals and renames go through deprecation first.** This covers components, questions,
   profile aliases, CLI options, and JSON fields.
   - The item keeps working, with a warning, for at least one minor release, and the CHANGELOG
     names the replacement.
   - It is removed only in the next major release.
4. **Questions are never renamed or removed**, because `copier update` replays the recorded
   answers. Add a new question instead.
5. **Exit codes are stable.**
   - `0` means success.
   - `1` means an invalid request; nothing was written.
   - `2` means a valid request failed while rendering or writing.
6. **Generated dependencies are pinned by the project, not by pytemplate-uv.**
   - Templates declare lower bounds.
   - Each generated project commits its own `uv.lock` (`uv lock`) and runs `uv sync --locked`
     in CI.
   - Upgrading a dependency is the project's decision.
7. **Supported Python versions.**
   - The generator and every stable profile support each CPython minor release from 3.11 to 3.14.
   - Raising the minimum version is a major-release decision.

## Status levels

| Status | Meaning |
| --- | --- |
| `stable` | Covered by the rules above and by the generated-project smoke tests in CI |
| `experimental` | Selectable, but output may change in a minor release; the CHANGELOG says how |
| `planned` | Described for discovery only; selecting it fails with an actionable error |

## Generated projects and updates

- Each project records its sources in two files:
  - `.copier-answers.yml` records the template source and tag, so `pytemplate update` can merge
    newer templates with `copier update`;
  - `.pytemplate.toml` records the generator, template, profile, and component versions, the
    sanitized answers, and a hash and owner for every generated file.
- `pytemplate update` is a dry run unless `--apply` is given, and it requires a clean git tree.
  Conflicts are marked inline and never resolved silently.
- **Projects from 2.0** have no answers file and cannot be updated; regenerate them with 3.0.
- **Projects from 2.1 development builds** never recorded their components.
  - `pytemplate update` keeps everything such a project already had: the components in its
    manifest, plus the profile's `legacy_components` (`container`, and `database` for
    `fastapi`).
  - It then records the components, so later updates behave like any 3.x project.
- Plain `copier copy` from the git repository is not a supported entry point. pytemplate passes
  the resolved `components` and validates the request first; use `pytemplate create` instead.

## Template packs

- A pack is selected explicitly for each request, with `--template` or `template =` in a request
  file. There is no discovery of installed packs.
- Packs follow the same contract and safety rules as the bundled templates:
  - they render with `unsafe=False`;
  - they may not declare `_tasks`, `_migrations`, or `_jinja_extensions`;
  - they may not contain symlinks.
- A pack versions itself: its git tags and its `pytemplate-pack.toml` `version`. Pack-generated
  projects are updated with `pytemplate update --to <pack tag>`.
