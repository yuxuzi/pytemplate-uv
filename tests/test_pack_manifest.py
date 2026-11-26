"""Optional ``categories`` and ``keywords`` in ``pytemplate-pack.toml``."""

from pathlib import Path

import pytest
from conftest import write_pack

from pytemplate.errors import PackError
from pytemplate.packs import PACK_FILE, open_catalog, read_pack_manifest


def _with_keys(root: Path, extra: str) -> Path:
    manifest = root / PACK_FILE
    manifest.write_text(manifest.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return root


def test_valid_categories_and_keywords_load(tmp_path: Path) -> None:
    root = _with_keys(
        write_pack(tmp_path / "pack"),
        'categories = ["data", "quant"]\nkeywords = ["backtest", "factor"]\n',
    )

    manifest = read_pack_manifest(root)

    assert manifest.categories == ("data", "quant")
    assert manifest.keywords == ("backtest", "factor")
    assert manifest.id == "demo-pack"
    assert manifest.name == "Demo pack"
    assert manifest.description == "A pack used by the tests."
    assert manifest.version


def test_boundary_values_are_accepted(tmp_path: Path) -> None:
    twelve = ", ".join(f'"k{index}"' for index in range(12))
    root = _with_keys(
        write_pack(tmp_path / "pack"),
        f'keywords = [{twelve}, "{"a" * 30}"]\n',
    )

    with pytest.raises(PackError, match="has 13 entries"):
        read_pack_manifest(root)

    root = _with_keys(write_pack(tmp_path / "other"), f"keywords = [{twelve}]\n")
    assert len(read_pack_manifest(root).keywords) == 12


def test_manifest_without_the_keys_still_loads(tmp_path: Path) -> None:
    manifest = read_pack_manifest(write_pack(tmp_path / "pack"))

    assert manifest.categories == ()
    assert manifest.keywords == ()


def test_pack_with_the_keys_still_opens_as_a_catalog(tmp_path: Path) -> None:
    root = _with_keys(write_pack(tmp_path / "pack"), 'keywords = ["factor"]\n')

    with open_catalog(str(root)) as (catalog, source, _):
        assert source.pack_id == "demo-pack"
        assert [profile.identifier for profile in catalog.profiles] == ["tool"]


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (
            'categories = "data"',
            r"'categories' must be a list of category ids \(cli, .*\), got 'data'",
        ),
        ("categories = [3]", r"'categories' must be a list of category ids \(cli, .*\), got \[3\]"),
        ('categories = ["Data"]', r"unknown category 'Data'; use one of: cli, library, web"),
        ('categories = ["risk-tools"]', r"unknown category 'risk-tools'; use one of"),
        ('categories = ["webs"]', r"unknown category 'webs'.* Did you mean 'web'\?"),
        ('categories = ["web", "web"]', r"each category may be listed only once"),
        ('keywords = "factor"', r"'keywords' must be a list of strings, got 'factor'"),
        ("keywords = [1]", r"'keywords' must be a list of strings, got \[1\]"),
        (
            "keywords = [" + ", ".join(f'"k{i}"' for i in range(13)) + "]",
            r"'keywords' has 13 entries; at most 12 are allowed",
        ),
        ('keywords = ["Factor"]', r"keyword 'Factor' must be lowercase"),
        ('keywords = [" factor"]', r"keyword ' factor' must be lowercase"),
        ('keywords = [""]', r"keyword '' must be lowercase"),
        (
            'keywords = ["' + "a" * 31 + '"]',
            r"keyword '" + "a" * 31 + r"' is 31 characters; at most 30 are allowed",
        ),
    ],
)
def test_invalid_shapes_name_the_file_and_key(tmp_path: Path, extra: str, message: str) -> None:
    root = _with_keys(write_pack(tmp_path / "pack"), extra + "\n")

    with pytest.raises(PackError, match=PACK_FILE + ": " + message):
        read_pack_manifest(root)


def test_the_category_list_is_fixed_and_exported() -> None:
    from pytemplate import api
    from pytemplate.schema import SCHEMAS

    assert api.PACK_CATEGORIES == ("cli", "library", "web", "worker", "data", "ai", "quant")
    items = SCHEMAS["pack"]["properties"]["categories"]["items"]
    assert items == {"enum": list(api.PACK_CATEGORIES)}
