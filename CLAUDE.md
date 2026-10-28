@AGENTS.md

## Claude Code notes

- To try the bundled project-creation skill locally, run `uv run pytemplate skill install --project`
  (it writes `./.claude/skills/pytemplate/SKILL.md`; do not commit that copy). Then ask Claude to
  create a project.
- Edit the skill only in `pytemplate/skills/pytemplate/SKILL.md`; `tests/test_skill.py` checks that
  every command it references exists.
