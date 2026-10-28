"""Command-line interface for the pytemplate project generator."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pytemplate.agent_skill import (
    SkillInstallError,
    default_skills_dir,
    install_skill,
    skill_text,
)
from pytemplate.configuration import ConfigurationError, load_render_request
from pytemplate.profiles import (
    Component,
    ComponentCompatibilityError,
    ComponentNotFoundError,
    Profile,
    ProfileNotFoundError,
    get_component,
    get_profile,
    list_components,
    list_profiles,
    question_details,
)
from pytemplate.rendering import (
    DEFAULT_TEMPLATE_SOURCE,
    RenderError,
    RenderRequest,
    generator_version,
    render,
    validate_request,
)
from pytemplate.updating import UpdateError, UpdateRequest, update

app = typer.Typer(
    name="pytemplate",
    help="Generate deterministic Python project foundations from bundled profiles.",
    no_args_is_help=True,
)
console = Console()
skill_app = typer.Typer(help="Install or print the AI agent skill for creating projects.")
app.add_typer(skill_app, name="skill")

JsonOption = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")]


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _profile_dict(profile: Profile) -> dict[str, object]:
    data = asdict(profile)
    del data["template_directory"]
    return data


def _component_dict(component: Component) -> dict[str, object]:
    return asdict(component)


def _show_version(value: bool) -> None:
    if value:
        console.print(f"pytemplate-uv {generator_version()}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the installed version and exit.",
            callback=_show_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Generate deterministic Python project foundations from bundled profiles."""


def _parse_data(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated KEY=VALUE options into template answers."""
    data: dict[str, str] = {}
    for pair in pairs or ():
        key, separator, value = pair.partition("=")
        if not separator or not key:
            console.print(f"[red]Error:[/] Template data must be KEY=VALUE, got '{pair}'.")
            raise typer.Exit(code=1)
        data[key] = value
    return data


def _render_and_report(request: RenderRequest) -> None:
    """Render one request and display an actionable outcome."""
    try:
        result = render(request)
    except (
        RenderError,
        ProfileNotFoundError,
        ComponentNotFoundError,
        ComponentCompatibilityError,
    ) as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    if result.dry_run:
        console.print(
            "[yellow]Dry run:[/] would create profile "
            f"'{result.profile.identifier}' at {result.project_path}"
        )
        return
    console.print(
        f"[green]Created[/] '{result.profile.identifier}' project at {result.project_path}"
    )


@app.command("create")
def create(
    project_name: Annotated[
        str, typer.Argument(help="Lowercase project slug, for example: market-data-api")
    ],
    profile: Annotated[str, typer.Option("--profile", "-p", help="Profile identifier")] = "python",
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Existing parent directory")
    ] = Path("."),
    no_input: Annotated[
        bool, typer.Option("--no-input", help="Accept template defaults without prompting")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Allow overwriting an existing output")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Validate and show the target without writing files")
    ] = False,
    component: Annotated[
        list[str] | None,
        typer.Option(
            "--component",
            "-c",
            help="Select a compatible component; repeat for multiple components",
        ),
    ] = None,
    data: Annotated[
        list[str] | None,
        typer.Option(
            "--data",
            "-d",
            help="Answer a template question as KEY=VALUE; repeat for multiple answers",
        ),
    ] = None,
    template_source: Annotated[
        str,
        typer.Option(
            "--template-source",
            help="Git source recorded for `pytemplate update` (for forks)",
            show_default=True,
        ),
    ] = DEFAULT_TEMPLATE_SOURCE,
) -> None:
    """Create a project from a bundled profile."""
    _render_and_report(
        RenderRequest(
            profile_id=profile,
            project_name=project_name,
            output_dir=output_dir,
            components=tuple(component or ()),
            no_input=no_input,
            overwrite=force,
            dry_run=dry_run,
            data=_parse_data(data),
            template_source=template_source,
        )
    )


@app.command("create-project", hidden=True)
def create_project_compat(
    project_name: Annotated[str, typer.Argument(help="Lowercase project slug")],
    profile: Annotated[str, typer.Option("--profile", "-p")] = "python",
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("."),
    no_input: Annotated[bool, typer.Option("--no-input")] = False,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Compatibility alias for the former command name."""
    _render_and_report(
        RenderRequest(
            profile_id=profile,
            project_name=project_name,
            output_dir=output_dir,
            no_input=no_input,
            overwrite=force,
            dry_run=dry_run,
        )
    )


@app.command("list-profiles")
def list_profiles_command(as_json: JsonOption = False) -> None:
    """List bundled profiles and their descriptions."""
    if as_json:
        _echo_json([_profile_dict(profile) for profile in list_profiles()])
        return
    table = Table(title="Bundled project profiles")
    table.add_column("ID", style="cyan")
    table.add_column("Version")
    table.add_column("Python")
    table.add_column("Components")
    table.add_column("Description")
    for profile in list_profiles():
        table.add_row(
            profile.identifier,
            profile.version,
            ", ".join(profile.supported_python),
            ", ".join(profile.default_components) or "none",
            profile.description,
        )
    console.print(table)


@app.command("describe-profile")
def describe_profile(
    profile_id: Annotated[str, typer.Argument(help="Profile identifier")],
    as_json: JsonOption = False,
) -> None:
    """Show metadata and template inputs for a bundled profile."""
    try:
        profile = get_profile(profile_id)
    except ProfileNotFoundError as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    if as_json:
        _echo_json({**_profile_dict(profile), "question_details": question_details()})
        return
    console.print(f"[bold]{profile.name}[/] ({profile.identifier}, v{profile.version})")
    console.print(profile.description)
    if profile.aliases:
        console.print(f"Compatibility aliases: {', '.join(profile.aliases)}")
    console.print(f"Supported Python: {', '.join(profile.supported_python)}")
    console.print(f"Available components: {', '.join(profile.components) or 'none'}")
    console.print(f"Default components: {', '.join(profile.default_components) or 'none'}")
    console.print(f"Template inputs: {', '.join(profile.questions) or 'none'}")
    console.print(f"Security posture: {profile.security_posture}")


@app.command("list-components")
def list_components_command(as_json: JsonOption = False) -> None:
    """List bundled application-factory components."""
    if as_json:
        _echo_json([_component_dict(component) for component in list_components()])
        return
    table = Table(title="Bundled application components")
    table.add_column("ID", style="cyan")
    table.add_column("Version")
    table.add_column("Profiles")
    table.add_column("Description")
    for component in list_components():
        table.add_row(
            component.identifier,
            component.version,
            ", ".join(component.compatible_profiles),
            component.description,
        )
    console.print(table)


@app.command("describe-component")
def describe_component(
    component_id: Annotated[str, typer.Argument(help="Component identifier")],
    as_json: JsonOption = False,
) -> None:
    """Show metadata for a bundled application-factory component."""
    try:
        component = get_component(component_id)
    except ComponentNotFoundError as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    if as_json:
        _echo_json(_component_dict(component))
        return
    console.print(f"[bold]{component.name}[/] ({component.identifier}, v{component.version})")
    console.print(component.description)
    console.print(f"Compatible profiles: {', '.join(component.compatible_profiles)}")
    console.print(f"Dependency groups: {', '.join(component.dependency_groups) or 'none'}")
    console.print(f"Template fragments: {', '.join(component.template_fragments) or 'none'}")
    if component.configuration_schema:
        console.print(f"Configuration: {component.configuration_schema}")


@app.command("create-from-config")
def create_from_config(
    config: Annotated[Path, typer.Argument(help="TOML render-request file")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Validate and show the target without writing files")
    ] = False,
) -> None:
    """Create a project from a deterministic TOML render request."""
    try:
        request = load_render_request(config, dry_run=dry_run)
    except ConfigurationError as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    _render_and_report(request)


@app.command("validate")
def validate_config(
    config: Annotated[Path, typer.Argument(help="TOML render-request file")],
) -> None:
    """Validate a TOML render request without rendering files."""
    try:
        request = load_render_request(config, dry_run=True)
        profile, components, project_path = validate_request(request)
    except (
        ConfigurationError,
        RenderError,
        ProfileNotFoundError,
        ComponentNotFoundError,
        ComponentCompatibilityError,
    ) as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Valid[/] {profile.identifier} -> {project_path}")
    console.print(
        f"Components: {', '.join(component.identifier for component in components) or 'none'}"
    )


@app.command("update")
def update_command(
    project_dir: Annotated[
        Path, typer.Argument(help="Generated project directory (a clean git repository)")
    ] = Path("."),
    to: Annotated[
        str | None,
        typer.Option("--to", help="Template tag to update to; defaults to this version's tag"),
    ] = None,
    apply: Annotated[
        bool, typer.Option("--apply", help="Write the changes; without it this is a dry run")
    ] = False,
) -> None:
    """Merge a newer template version into a generated project with `copier update`."""
    try:
        result = update(UpdateRequest(project_dir=project_dir, to_ref=to, apply=apply))
    except UpdateError as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    source = result.from_ref or "an unrecorded version"
    if not result.applied:
        console.print(
            f"[yellow]Dry run:[/] would update {result.project_path} from {source} to "
            f"{result.to_ref}. Re-run with --apply to write the changes."
        )
        return
    console.print(
        f"[green]Updated[/] {result.project_path} from {source} to {result.to_ref}. "
        "Review `git diff` and resolve any conflict markers before committing."
    )


@skill_app.command("show")
def skill_show() -> None:
    """Print the skill (SKILL.md) for use with any AI tool."""
    typer.echo(skill_text(), nl=False)


@skill_app.command("install")
def skill_install(
    project: Annotated[
        bool,
        typer.Option("--project", help="Install into ./.claude/skills instead of ~/.claude/skills"),
    ] = False,
    dest: Annotated[
        Path | None, typer.Option("--dest", help="Install into this skills directory instead")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing skill")] = False,
) -> None:
    """Install the skill so Claude Code can create projects with pytemplate."""
    skills_dir = dest if dest is not None else default_skills_dir(project=project)
    try:
        target = install_skill(skills_dir, force=force)
    except SkillInstallError as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Installed[/] skill at {target}")


if __name__ == "__main__":
    app()
