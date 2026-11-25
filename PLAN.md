# PLAN.md — pytemplate-uv 3.5: a short command for a hub pack

This is the working plan for the next release. The 3.2 plan (a friendlier CLI, a faster core, a
stronger package) is finished and released; its record is in the git history and the CHANGELOG.

Status key: `[x]` done and verified, `[ ]` open, `[?]` needs the maintainer's decision first.

## 1. The problem

Creating a project from a pack on pytemplate-hub takes this command, which the hub's site and the
skill both produce:

```bash
uvx pytemplate-uv@latest create hello-cli -p cli \
  --template gh:yuxuzi/pytemplate-starters --template-ref v1.0.0 \
  --template-commit 2886e570d1b964811e63b6aa93f3e0ede2e8e7d2 \
  --template-digest 9257161472cfe280e79c7452ff0e01618b278ea57b7d74280b882976969de924 -y
```

| # | Finding | Evidence |
| --- | --- | --- |
| H1 | Four flags and 104 characters of hash for one pack. Nobody types it; a copy that loses a line fails or, worse, drops the pin. | The command above |
| H2 | The pins are already on the hub, in `index/<owner>/<pack>.toml`, but the CLI cannot read them, so every caller copies them by hand. | `packs._check_pin` takes them only as flags |
| H3 | The skill clones the whole hub to read one entry, then builds the long command. | `SKILL.md` step 3 |
| H4 | Without `-p`, `create` uses `python`. A pack with no `python` profile fails with "Unknown profile 'python'", even in a terminal where it could ask. | `cli_options._SHARED_PARAMETERS`, `profiles.py` |
| H5 | `-h` is unused: `create -h` says "No such option: -h". | `uvx pytemplate-uv@3.3.0 create -h` |

## 2. The result

```bash
uvx pytemplate-uv@latest create hello-cli -h yuxuzi/pytemplate-starters
```

In a terminal this asks for the profile (H4), then the optional components (as today), and
creates the project from the commit and digest the hub listed for the pack's latest version. The
fully pinned command keeps working unchanged, for CI, offline machines, and anyone who does not
want to trust the hub's index.

## 3. Changes

### U1 `--hub` / `-h`: read the pins from the hub `[x]`

- `-h, --hub OWNER/PACK[@TAG]` on `create`, `validate`, `plan`, `list-profiles`,
  `describe-profile`, `list-components`, and `describe-component` (the commands that take
  `--template`), through the shared options in `cli_options.py`.
- It fetches one file, `index/<owner>/<pack>.toml`, from the hub's `main` branch
  (`https://raw.githubusercontent.com/yuxuzi/pytemplate-hub/main/index/`) with `urllib` from the
  standard library: **no new dependency, and no dependency on the hub's website** being deployed.
  The same timeout as git (`PYTEMPLATE_GIT_TIMEOUT`). `PYTEMPLATE_HUB_URL` replaces the base URL,
  for a firm's private mirror and for tests.
- It reads `repository` and the version's `tag`, `commit`, and `digest`, then runs exactly the
  pinned path that exists today (`_check_pin`, fetch by commit, digest check, cache). The hub is
  only a lookup; the refusal of a moved tag or changed files is unchanged.
- No `@TAG`: the newest version that is not yanked. A yanked `@TAG` is refused, naming the newest.
  An unknown tag lists the listed tags.
- The entry's `format` must be 1; another value says "upgrade pytemplate-uv".
- Before rendering, one line on stderr says what was resolved and how far it is trusted:
  `Using yuxuzi/pytemplate-starters v1.0.0 (commit 2886e57, digest 92571614…), listed on the hub, not reviewed.`
  `--json` output carries the same fields.
- `.pytemplate.toml` records the source as today (repository, tag, commit, digest) plus
  `hub = "yuxuzi/pytemplate-starters"`, so `status` and a rerun know where it came from.
- Errors, all exit code 2 (invalid request), each with the next step:
  - `--hub` with `--template`, `--template-ref`, `--template-commit`, or `--template-digest`:
    "--hub names the pack and its pins; drop --template…".
  - Not listed (HTTP 404): "'acme/foo' is not listed on pytemplate-hub. Browse the listed packs at
    <hub URL>, or pass --template for a pack that is not listed."
  - Network failure: the error, then the fully pinned command is the way to work offline.
  - A malformed `OWNER/PACK`: the expected shape and an example.
- `create-from-config` accepts `hub = "owner/pack@tag"` in the request file, with the same rules.

### U2 `-h` with no value shows help `[x]`

`-h` means help almost everywhere, and the decision (D1) is to give it to `--hub` anyway. So that
the habit still works: `pytemplate create -h` (or `-h` as the last argument, or followed by another
option) prints the command's help and exits 0, instead of "Option '-h' requires an argument".
`--help` is unchanged everywhere. The root command and the commands without `--hub` keep `-h`
unused, so `pytemplate -h` still says "No such option" and suggests `--help`; the README says
`-h` is `--hub`.

### U3 Ask for the profile when `-p` is missing `[x]`

`-p` defaults to "not given" instead of `python`.

| Situation | Behaviour |
| --- | --- |
| `-p` given | Unchanged |
| The catalog (bundled, local folder, git, or hub pack) has one profile | Use it, with no question |
| No `-p`, in a terminal, no `-y` | A `questionary.select` of the profiles, "id - description", with `python` first when it exists. For a hub pack, each shows its lifecycle result from the index (`checks passed`, `checks failed`). Then the existing component picker |
| No `-p`, with `-y` or `--json` | `python` if the catalog has it (today's behaviour for the bundled catalog); otherwise today's error, which lists the profiles |
| No `-p`, no terminal, no `-y` | Today's early error ("standard input is not a terminal") |

Ctrl-C at the question: "Cancelled; nothing was created.", as the component picker does.
`validate` and `plan` never ask: they keep the `-y` rule. `questionary` is already a dependency.

### U4 The skill and the docs use the short form `[x]`

- Skill step 3: to resolve a chosen pack, use `--hub owner/pack@tag` instead of cloning the hub and
  copying pins. Searching still reads the hub's entries (the clone stays for search only, until the
  hub publishes `index.json` at a stable URL). The agent passes `-p` and `-y` itself: an agent never
  answers a question in the terminal.
- README: a "From pytemplate-hub" section leading with the short command; the fully pinned command
  as "Offline and in CI"; a line that `-h` is `--hub` and `--help` is help.
- CHANGELOG under 3.5.0, including the one visible change: `pytemplate create foo` in a terminal
  with no `-p` now asks for the profile instead of choosing `python`.

## 4. Tests

All offline. The hub is a local HTTP server or a `file://` `PYTEMPLATE_HUB_URL` over a fixture
entry that points at a local git pack fixture.

- `--hub` resolves the newest non-yanked version, an explicit tag, and refuses a yanked tag, an
  unknown tag, an unknown pack, format 2, and every mix with `--template*` flags.
- A tag that moved after listing is refused exactly as with the long command (same message).
- The stderr line, the `--json` fields, and `hub` in `.pytemplate.toml`.
- `-h` with no value prints help, on each command that has it; `--help` unchanged.
- The profile question: one profile, many profiles, `-y` with and without `python`, no terminal,
  cancel. `_stdin_is_tty` and `questionary` are replaced in tests, as for the component picker.
- A local folder (`--template ./pack`) gets the profile question too; pins and `--hub` stay refused
  with it.
- The skill test checks the new step 3 names only options the CLI has.

## 5. Outside this repository

- **Hub site** (pytemplate-hub): the copy button shows
  `uvx pytemplate-uv@latest create <name> -h owner/pack@tag`; the command builder adds `-p` and
  `-y` when the reader picks a profile; a "Fully pinned" tab keeps today's command. Ships after 3.5
  is on PyPI.
- **Hub rule** the lookup relies on: a listed tag's commit and digest never change. `verify`
  already fails a moved tag; the hub's docs should state that an entry's versions are append-only.

## 6. Decisions

- `[x]` D1 `-h` is the short form of `--hub` (the maintainer's call, 2026-11-25). Cost: `-h` is
  help in most tools; U2 covers `create -h` alone, and `--help` is unchanged.
- `[?]` D2 Release: 3.5.0 after 3.4.0 is tagged (recommended), or fold this into 3.4.0, which is
  prepared on `main` but not tagged.
- `[?]` D3 Trust: `--hub` trusts the hub's `main` branch over HTTPS for the pins. The long command
  remains for anyone who does not. Accept, or also require `--hub` to print the long command and
  ask for confirmation the first time (not recommended: one more prompt for every new user).

## 7. Phases

One pull request each; the maintainer merges.

| Phase | Scope |
| --- | --- |
| A | U1 and U2, with tests |
| B | U3, with tests |
| C | U4 (skill, README, CHANGELOG), version 3.5.0; tag after the maintainer's word |
