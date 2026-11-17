"""Black-box tests for the public command-line interface."""

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from cli_runner import make_runner

import pytemplate.rendering as rendering
from pytemplate.main import app, create_project_app

runner = make_runner()


def test_no_cache_turns_off_the_pinned_pack_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[rendering.RenderRequest] = []
    real = rendering.render

    def capture(request: rendering.RenderRequest) -> rendering.RenderResult:
        requests.append(request)
        return real(request)

    monkeypatch.setattr("pytemplate.main.render", capture)
    for flags in ([], ["--no-cache"]):
        arguments = ["create", "demo", "-o", str(tmp_path), "-y", "--dry-run", *flags]
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0, result.output

    assert [request.use_cache for request in requests] == [True, False]


def test_help_describes_the_public_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "create" in result.output
    assert "list-profiles" in result.output
    assert "describe-profile" in result.output
    assert "list-components" in result.output
    assert "create-from-config" in result.output
    assert "validate" in result.output


def test_list_profiles_includes_the_bundled_profiles() -> None:
    result = runner.invoke(app, ["list-profiles"])

    assert result.exit_code == 0
    assert "python" in result.output
    assert "fastapi" in result.output
    assert "3.13" in result.output
    assert "3.14" in result.output
    assert "3.15" in result.output


def test_component_commands_describe_the_factory_contract() -> None:
    listed = runner.invoke(app, ["list-components"])
    described = runner.invoke(app, ["describe-component", "database"])

    assert listed.exit_code == 0, listed.output
    assert "database" in listed.output
    assert described.exit_code == 0, described.output
    assert "Requires: api" in described.output
    assert "DATABASE_URL" in described.output


def test_create_dry_run_does_not_write_a_project(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "-y", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "would create" in result.output
    assert not (tmp_path / "market-data-api").exists()


def test_create_renders_the_python_profile(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "-y"],
    )

    project = tmp_path / "market-data-api"
    assert result.exit_code == 0, result.output
    assert (project / "pyproject.toml").is_file()
    assert (project / "market_data_api" / "cli.py").is_file()
    manifest = (project / ".pytemplate.toml").read_text(encoding="utf-8")
    assert 'id = "python"' in manifest
    assert 'id = "cli"' in manifest


def test_create_renders_the_fastapi_profile_with_a_configured_database(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--profile",
            "fastapi",
            "--component",
            "database",
            "--output-dir",
            str(tmp_path),
            "-y",
        ],
    )

    project = tmp_path / "market-data-api"
    container = project / "market_data_api" / "bootstrap" / "container.py"
    environment_file = project / ".env.example"
    assert result.exit_code == 0, result.output
    assert "settings.DATABASE_URL.get_secret_value()" in container.read_text(encoding="utf-8")
    assert "MARKET_DATA_API_DATABASE_URL" in environment_file.read_text(encoding="utf-8")
    assert (project / "alembic.ini").is_file()
    assert not (project / ".env").exists()


def test_default_fastapi_project_has_no_database(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["create", "svc", "--profile", "fastapi", "-o", str(tmp_path), "-y"]
    )

    assert result.exit_code == 0, result.output
    assert not (tmp_path / "svc" / "alembic.ini").exists()
    assert "DATABASE_URL" not in (tmp_path / "svc" / ".env.example").read_text(encoding="utf-8")


def test_create_rejects_an_existing_output_without_force(tmp_path: Path) -> None:
    (tmp_path / "market-data-api").mkdir()

    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "-y"],
    )

    assert result.exit_code == 1
    assert "Output already exists" in result.output


def test_create_rejects_an_invalid_project_name(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "Market Data", "--output-dir", str(tmp_path), "-y"],
    )

    assert result.exit_code == 1
    assert "lowercase slug" in result.output


def test_create_rejects_a_component_not_supported_by_the_profile(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--component",
            "database",
            "--output-dir",
            str(tmp_path),
            "-y",
        ],
    )

    assert result.exit_code == 1
    assert "not available for profile 'python'" in result.output


def test_validate_and_create_from_toml_config(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text(
        'project_name = "configured-api"\nprofile = "fastapi"\ncomponents = ["api", "database"]\n',
        encoding="utf-8",
    )

    validated = runner.invoke(app, ["validate", str(config)])
    created = runner.invoke(app, ["create-from-config", str(config)])

    assert validated.exit_code == 0, validated.output
    assert "Valid" in validated.output
    assert created.exit_code == 0, created.output
    assert (tmp_path / "configured-api" / ".pytemplate.toml").is_file()


def test_create_accepts_template_data_and_describes_inputs(tmp_path: Path) -> None:
    described = runner.invoke(app, ["describe-profile", "python"])
    created = runner.invoke(
        app,
        [
            "create",
            "market-data-api",
            "--output-dir",
            str(tmp_path),
            "-y",
            "--data",
            "description=Factor research toolkit",
        ],
    )

    assert described.exit_code == 0, described.output
    assert "Template inputs: project_name, package_name, description" in described.output
    assert created.exit_code == 0, created.output
    readme = (tmp_path / "market-data-api" / "README.md").read_text(encoding="utf-8")
    assert "Factor research toolkit" in readme


def test_create_rejects_malformed_template_data(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create", "market-data-api", "--output-dir", str(tmp_path), "--data", "novalue"],
    )

    assert result.exit_code == 1
    assert "KEY=VALUE" in result.output


def test_version_option_prints_the_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.startswith("pytemplate-uv ")


def test_create_project_is_a_full_alias_of_create(tmp_path: Path) -> None:
    listed = runner.invoke(app, ["--help"])
    created = runner.invoke(
        app,
        [
            "create-project",
            "market-data-api",
            "--profile",
            "fastapi",
            "--output-dir",
            str(tmp_path),
            "-y",
            "--data",
            "description=Alias check",
        ],
    )

    assert "create-project" in listed.output
    assert created.exit_code == 0, created.output
    readme = (tmp_path / "market-data-api" / "README.md").read_text(encoding="utf-8")
    assert "Alias check" in readme


def test_create_project_executable_runs_create_directly(tmp_path: Path) -> None:
    result = runner.invoke(
        create_project_app,
        ["market-data-api", "-p", "fastapi", "-o", str(tmp_path), "-y"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "market-data-api" / "AGENTS.md").is_file()


def test_validate_reports_components_added_by_requirements(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "svc"\nprofile = "fastapi"\ncomponents = ["database"]\n')

    result = runner.invoke(app, ["validate", str(config)])

    assert result.exit_code == 0, result.output
    assert "Components: api, database" in result.output


def test_validate_rejects_auth_without_a_mode_with_guidance(tmp_path: Path) -> None:
    config = tmp_path / "request.toml"
    config.write_text('project_name = "svc"\nprofile = "fastapi"\ncomponents = ["auth"]\n')

    result = runner.invoke(app, ["validate", str(config), "--json"])

    assert result.exit_code == 1
    assert "add --component auth-api-key" in json.loads(result.output)["error"]["message"]


def test_plan_json_lists_files_and_writes_nothing(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            "--name",
            "svc",
            "--profile",
            "fastapi",
            "-c",
            "container",
            "-o",
            str(tmp_path),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert list(tmp_path.iterdir()) == []
    assert payload["ok"] is True
    assert [item["id"] for item in payload["components"]] == ["api", "container"]
    assert "Dockerfile" in payload["files"]
    assert "pyproject.toml" in payload["files"]
    assert payload["target_exists"] is False
    assert "fastapi>=0.115" in payload["dependencies"]


def test_plan_reports_an_existing_target_without_failing(tmp_path: Path) -> None:
    (tmp_path / "svc").mkdir()

    result = runner.invoke(app, ["plan", "--name", "svc", "-o", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "target exists" in result.output


def test_validate_with_options_rejects_an_incompatible_component() -> None:
    result = runner.invoke(
        app, ["validate", "--profile", "python", "--component", "database", "--json"]
    )

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["ok"] is False
    assert payload["exit_code"] == 1
    assert payload["error"]["type"] == "ComponentCompatibilityError"
    assert "Components for 'python': cli, container" in payload["error"]["message"]


def test_validate_catches_answers_the_template_rejects() -> None:
    result = runner.invoke(app, ["validate", "--data", "python_version=3.9"])

    assert result.exit_code == 1
    assert "Copier rejected the answers" in result.output


def test_create_json_reports_the_result(tmp_path: Path) -> None:
    result = runner.invoke(app, ["create", "svc", "-o", str(tmp_path), "-y", "--json"])

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert payload["project_path"] == str(tmp_path.resolve() / "svc")
    assert payload["manifest_path"].endswith(".pytemplate.toml")
    assert payload["requested"] == []


def test_render_failure_exits_with_code_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rendering, "run_copy", fail)

    result = runner.invoke(app, ["create", "svc", "-o", str(tmp_path), "-y", "--json"])

    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["message"].endswith("disk full")


def test_bad_data_option_is_an_invalid_request() -> None:
    result = runner.invoke(app, ["validate", "--data", "novalue"])

    assert result.exit_code == 1
    assert "KEY=VALUE" in result.output


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_yes_and_the_deprecated_no_input_render_identical_projects(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()

    short = runner.invoke(app, ["create", "demo", "-o", str(tmp_path / "a"), "-y"])
    long = runner.invoke(app, ["create", "demo", "-o", str(tmp_path / "b"), "--yes"])
    old = runner.invoke(app, ["create", "demo", "-o", str(tmp_path / "c"), "--no-input"])

    assert short.exit_code == long.exit_code == old.exit_code == 0
    assert _tree(tmp_path / "a" / "demo") == _tree(tmp_path / "b" / "demo")
    assert _tree(tmp_path / "a" / "demo") == _tree(tmp_path / "c" / "demo")
    assert "--no-input is deprecated" in old.stderr
    assert "-y" in old.stderr
    assert old.stderr.count("deprecated") == 1
    assert "deprecated" not in short.stderr


def test_no_input_is_hidden_from_help() -> None:
    result = runner.invoke(app, ["create", "--help"])

    assert "--yes" in result.output
    assert "--no-input" not in result.output


def test_create_without_a_terminal_or_yes_exits_before_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pytemplate.main._stdin_is_tty", lambda: False)

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path)])

    assert result.exit_code == 1
    assert "-y" in result.output
    assert "--data KEY=VALUE" in result.output
    assert not (tmp_path / "demo").exists()


def test_json_implies_yes_and_never_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pytemplate.main._stdin_is_tty", lambda: False)

    result = runner.invoke(app, ["create", "demo", "-o", str(tmp_path), "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["ok"] is True
    assert (tmp_path / "demo" / "pyproject.toml").is_file()


def test_errors_go_to_stderr_and_json_stays_on_stdout(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    args = ["create", "demo", "-o", str(tmp_path), "-y"]

    human = runner.invoke(app, args)
    machine = runner.invoke(app, [*args, "--json"])
    schema = runner.invoke(app, ["schema", "nope"])

    assert human.exit_code == 1
    assert human.stdout == ""
    assert "Output already exists" in human.stderr
    assert machine.exit_code == 1
    assert json.loads(machine.stdout)["error"]["type"] == "RequestError"
    assert machine.stderr == ""
    assert schema.exit_code == 1
    assert schema.stdout == ""
    assert "Unknown schema" in schema.stderr


def test_unknown_identifiers_get_suggestions(tmp_path: Path) -> None:
    component = runner.invoke(
        app, ["plan", "-p", "fastapi", "-c", "datbase", "-o", str(tmp_path), "--name", "x"]
    )
    profile = runner.invoke(app, ["plan", "-p", "fastap", "-o", str(tmp_path), "--name", "x"])
    described = runner.invoke(app, ["describe-component", "datbase"])
    schema = runner.invoke(app, ["schema", "manifst"])
    data = runner.invoke(app, ["plan", "-o", str(tmp_path), "--name", "x", "-d", "packge_name=y"])

    assert "Did you mean 'database'?" in component.stderr
    assert "Available components:" in component.stderr
    assert "Did you mean 'fastapi'?" in profile.stderr
    assert "Available profiles:" in profile.stderr
    assert "Did you mean 'database'?" in described.stderr
    assert "Did you mean 'manifest'?" in schema.stderr
    assert "Did you mean 'package_name' instead of 'packge_name'?" in data.stderr


def test_nothing_close_gives_no_suggestion(tmp_path: Path) -> None:
    result = runner.invoke(app, ["plan", "-p", "zzzzzz", "-o", str(tmp_path), "--name", "x"])

    assert "Did you mean" not in result.stderr
    assert "Available profiles:" in result.stderr


def test_create_prints_next_steps_with_the_package_substituted(tmp_path: Path) -> None:
    result = runner.invoke(app, ["create", "market-data-api", "-o", str(tmp_path), "-y"])

    assert result.exit_code == 0, result.output
    assert "Next steps:" in result.stdout
    assert "  cd " in result.stdout
    assert "uv run mypy market_data_api" in result.stdout
    assert "{package}" not in result.stdout


def test_next_steps_are_human_output_only(tmp_path: Path) -> None:
    machine = runner.invoke(app, ["create", "demo", "-o", str(tmp_path), "--json"])
    dry = runner.invoke(app, ["create", "demo2", "-o", str(tmp_path), "-y", "--dry-run"])

    assert "Next steps" not in machine.stdout
    assert "lifecycle_commands" in json.loads(machine.stdout)
    assert "Next steps" not in dry.stdout


def test_completion_offers_bundled_profile_and_component_ids() -> None:
    from pytemplate.cli_options import complete_components, complete_profiles

    class Context:
        params: dict[str, object] = {}

    profiles = [name for name, _ in complete_profiles(Context(), "fast")]  # type: ignore[arg-type]
    components = [name for name, _ in complete_components(Context(), "data")]  # type: ignore[arg-type]
    assert profiles == ["fastapi"]
    assert components == ["database"]


def test_completion_is_empty_for_a_template_pack() -> None:
    from pytemplate.cli_options import complete_profiles

    class Context:
        params: dict[str, object] = {"template": "gh:org/pack"}

    assert complete_profiles(Context(), "") == []  # type: ignore[arg-type]


def test_shell_completion_runs_through_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("_PYTEMPLATE_COMPLETE", "complete_bash")
    monkeypatch.setenv("COMP_WORDS", "pytemplate create demo --profile fast")
    monkeypatch.setenv("COMP_CWORD", "4")

    result = runner.invoke(app, [])

    assert "fastapi" in result.output


def test_validate_opens_the_catalog_once_and_refuses_an_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[int] = []
    real = rendering.open_catalog

    def counting(*args: object, **kwargs: object) -> object:
        opened.append(1)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(rendering, "open_catalog", counting)
    ok = runner.invoke(app, ["validate", "--name", "demo", "-o", str(tmp_path), "--json"])
    (tmp_path / "demo").mkdir()
    exists = runner.invoke(app, ["validate", "--name", "demo", "-o", str(tmp_path)])

    assert ok.exit_code == 0, ok.output
    assert "files" not in json.loads(ok.stdout)
    assert exists.exit_code == 1
    assert "Output already exists" in exists.stderr
    assert len(opened) == 2


class _FakeCheckbox:
    def __init__(self, answer: list[str] | None) -> None:
        self.answer = answer

    def ask(self) -> list[str] | None:
        return self.answer


def _interactive(
    monkeypatch: pytest.MonkeyPatch, answer: list[str] | None
) -> tuple[list[Any], list[rendering.RenderRequest]]:
    import questionary

    seen: list[object] = []
    monkeypatch.setattr("pytemplate.main._stdin_is_tty", lambda: True)

    def checkbox(message: str, choices: list[object], **_: object) -> _FakeCheckbox:
        seen.extend(choices)
        return _FakeCheckbox(answer)

    monkeypatch.setattr(questionary, "checkbox", checkbox)
    requests: list[rendering.RenderRequest] = []
    real = rendering.render

    def capture(request: rendering.RenderRequest) -> rendering.RenderResult:
        requests.append(request)
        # A dry run renders through Copier, which would prompt; the picker is under test here.
        return real(dataclasses.replace(request, no_input=True))

    monkeypatch.setattr("pytemplate.main.render", capture)
    return seen, requests


def test_picker_offers_optional_components_and_passes_the_choice_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen, requests = _interactive(monkeypatch, ["database"])

    result = runner.invoke(
        app, ["create", "demo", "-p", "fastapi", "-o", str(tmp_path), "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert {choice.value for choice in seen} >= {"database", "worker"}
    assert requests[0].components == ("database",)


def test_picker_is_skipped_with_explicit_components_or_nothing_optional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen, _ = _interactive(monkeypatch, [])

    explicit = runner.invoke(
        app, ["create", "demo", "-p", "fastapi", "-c", "worker", "-o", str(tmp_path), "--dry-run"]
    )

    assert explicit.exit_code == 0, explicit.output
    assert seen == []  # the picker never ran


def test_cancelling_the_picker_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interactive(monkeypatch, None)

    result = runner.invoke(app, ["create", "demo", "-p", "fastapi", "-o", str(tmp_path)])

    assert result.exit_code == 1
    assert "Cancelled" in result.stderr
    assert not (tmp_path / "demo").exists()
