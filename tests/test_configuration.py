"""Unit tests for render-request TOML files."""

from pathlib import Path

import pytest

from pytemplate.configuration import ConfigurationError, load_render_request


def test_load_render_request_resolves_relative_output_path(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "quant-service"\n'
        'profile = "fastapi"\n'
        'output_dir = "."\n'
        'components = ["api"]\n',
        encoding="utf-8",
    )

    request = load_render_request(config)

    assert request.project_name == "quant-service"
    assert request.profile_id == "fastapi"
    assert request.output_dir == tmp_path
    assert request.components == ("api",)
    assert request.no_input is True


def test_load_render_request_rejects_unknown_configuration_keys(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "quant-service"\nunknown = true\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unsupported configuration keys"):
        load_render_request(config)


def test_load_render_request_reads_template_data(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "quant-service"\n[data]\ndescription = "Risk analytics"\n',
        encoding="utf-8",
    )

    assert load_render_request(config).data == {"description": "Risk analytics"}


def test_load_render_request_rejects_non_string_template_data(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "quant-service"\n[data]\nyear = 2026\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="'data' must map"):
        load_render_request(config)
