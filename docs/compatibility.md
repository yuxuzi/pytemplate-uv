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
   - One exception: 3.1.0 removed `pytemplate update`, the `update` API, `--template-source`, and
     the request key `template_source` without a deprecation period. Merging a template release
     into a project its owner has changed was not safe to keep offering.
4. **Questions are never renamed or removed**, because request files and scripts pass answers by
   name. Add a new question instead.
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
   - The generator and every stable profile support each CPython minor release from 3.11 to 3.15.
   - Raising the minimum version is a major-release decision.

## Status levels

| Status | Meaning |
| --- | --- |
| `stable` | Covered by the rules above and by the generated-project smoke tests in CI |
| `experimental` | Selectable, but output may change in a minor release; the CHANGELOG says how |
| `planned` | Described for discovery only; selecting it fails with an actionable error |

## Generated projects

- Each project records its sources in two files:
  - `.copier-answers.yml` records the Copier answers and the template source and tag;
  - `.pytemplate.toml` records the generator, template, profile, and component versions, the
    sanitized answers, and a hash and owner for every generated file.
- A generated project belongs to its owner. pytemplate-uv does not merge later template releases
  into it.

## Template packs

- A pack is selected explicitly for each request, with `--template` or `template =` in a request
  file. There is no discovery of installed packs.
- Packs follow the same contract and safety rules as the bundled templates:
  - they render with `unsafe=False`;
  - they may not declare `_tasks`, `_migrations`, or `_jinja_extensions`;
  - they may not contain symlinks.
- A pack versions itself: its git tags and its `pytemplate-pack.toml` `version`.
- A git pack can be pinned with `--template-commit` and `--template-digest`, or `template_commit`
  and `template_digest` in a request file, alongside its ref. A pack that does not match is refused
  with exit code 1, before any of it is read.
- The digest format is stable. It is a SHA-256 over every file in the checkout, without `.git`, in
  order of their path components compared as case-sensitive strings. For each file, it hashes the
  path with forward slashes, a NUL byte, the file's bytes, and another NUL byte.
