"""The old documentation site's addresses redirect to the pytemplate website."""

import re
from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parent.parent / ".github" / "pages"
SITE = "https://yuxuzi.github.io/pytemplate-hub/"
REPOSITORY = "https://github.com/yuxuzi/pytemplate-uv/blob/main/"
# Each address the old site served, and where it now leads.
EXPECTED = {
    "index.html": f"{SITE}learn/guide/",
    "compatibility/index.html": f"{SITE}learn/compatibility/",
    "contributing/index.html": f"{REPOSITORY}CONTRIBUTING.md",
    "changelog/index.html": f"{REPOSITORY}CHANGELOG.md",
    "404.html": f"{SITE}learn/",
}


def test_every_page_is_expected() -> None:
    found = {path.relative_to(PAGES).as_posix() for path in PAGES.rglob("*") if path.is_file()}

    assert found == set(EXPECTED)


@pytest.mark.parametrize(("page", "target"), EXPECTED.items())
def test_page_redirects_to_its_new_address(page: str, target: str) -> None:
    html = (PAGES / page).read_text(encoding="utf-8")

    assert f'<meta http-equiv="refresh" content="0; url={target}">' in html
    assert f'<link rel="canonical" href="{target}">' in html
    assert f'<a href="{target}">' in html
    assert '<meta name="robots" content="noindex">' in html
    assert re.search(r"<title>Moved: [^<]+</title>", html)


def test_the_readme_links_the_website() -> None:
    readme = (PAGES.parent.parent / "README.md").read_text(encoding="utf-8")

    for path in ("learn/", "learn/tutorial/", "learn/guide/", "learn/packs/", "publish/"):
        assert f"{SITE}{path}" in readme, path
    assert f"{SITE}learn/compatibility/" in readme
