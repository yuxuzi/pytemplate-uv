"""Assemble the documentation site's sources from the repository's Markdown files.

The README, CONTRIBUTING, CHANGELOG, and docs/ stay where they are; this copies them into
``site-src/`` (ignored by version control) and rewrites links between them. Run from anywhere:
``python .github/docs/prepare.py``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site-src"
REPO = "https://github.com/yuxuzi/pytemplate-uv/blob/main"

PAGES = {
    "README.md": "index.md",
    "docs/compatibility.md": "compatibility.md",
    "CONTRIBUTING.md": "contributing.md",
    "CHANGELOG.md": "changelog.md",
}
LINKS = {
    "(docs/compatibility.md": "(compatibility.md",
    "(CONTRIBUTING.md": "(contributing.md",
    "(CHANGELOG.md": "(changelog.md",
    "(AGENTS.md": f"({REPO}/AGENTS.md",
    "(LICENSE": f"({REPO}/LICENSE",
    "(PLAN.md": f"({REPO}/PLAN.md",
}


def main() -> None:
    """Write the site sources."""
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()
    for source, target in PAGES.items():
        text = (ROOT / source).read_text(encoding="utf-8")
        for old, new in LINKS.items():
            text = text.replace(old, new)
        (OUT / target).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
