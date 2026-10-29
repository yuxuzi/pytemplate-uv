"""Command-line interface for the pytemplate project generator."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, NoReturn

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
from pytemplate.errors import RenderError, RequestError
from pytemplate.packs import open_catalog
from pytemplate.profiles import (
    Catalog,
    Component,
    ComponentCompatibilityError,
    ComponentNotFoundError,
    ManifestError,
    Profile,
    ProfileNotFoundError,
)
from pytemplate.rendering import (
    DEFAULT_TEMPLATE_SOURCE,
    RenderPlan,
    RenderRequest,
    generator_version,
    plan,
    render,
    validate_request,
)
from pytemplate.resolution import Resolution
from pytemplate.schema import SCHEMAS
from pytemplate.updating import UpdateError, UpdateRequest, update

app = typer.Typer(
    name="pytemplate",
    help="Generate deterministic Python projects from profiles, components, and template packs.",
    no_args_is_help=True,
)
console = Console()
skill_app = typer.Typer(help="Install or print the AI agent skill for creating projects.")
app.add_typer(skill_app, name="skill")

# Exit codes are part of the CLI contract: 1 for an invalid request (nothing was written),
# 2 for a valid request that failed while rendering or writing.
EXIT_INVALID = 1
EXIT_RENDER_FAILED = 2
_REQUEST_ERRORS = (
    ConfigurationError,
    RequestError,
    ProfileNotFoundError,
    ComponentNotFoundError,
    ComponentCompatibilityError,
    ManifestError,
)

JsonOption = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")]
TemplateOption = Annotated[
    str | None,
    typer.Option(
        "--template",
        "-t",
        help="External template pack: a directory or git source such as gh:org/repo",
    ),
]
TemplateRefOption = Annotated[
    str | None,
    typer.Option("--template-ref", help="Git tag or branch of the --template pack"),
]
ProfileOption = Annotated[str, typer.Option("--profile", "-p", help="Profile identifier")]
OutputOption = Annotated[Path, typer.Option("--output-dir", "-o", help="Existing parent directory")]
NoInputOption = Annotated[
    bool, typer.Option("--no-input", help="Accept template defaults without prompting")
]
ForceOption = Annotated[
    bool, typer.Option("--force", "-f", help="Allow overwriting an existing output")
]
ComponentOption = Annotated[
    list[str] | None,
    typer.Option(
        "--component",
        "-c",
        help="Add a compatible component (required components are added automatically); "
        "repeat for multiple components",
    ),
]
DataOption = Annotated[
    list[str] | None,
    typer.Option(
        "--data",
        "-d",
        help="Answer a template question as KEY=VALUE; repeat for multiple answers",
    ),
]
TemplateSourceOption = Annotated[
    str,
    typer.Option(
        "--template-source",
        help="Git source recorded for `pytemplate update` of bundled profiles (for forks)",
        show_default=True,
    ),
]
ConfigArgument = Annotated[
    Path | None,
    typer.Argument(help="TOML render-request file; when omitted, use the options below"),
]
NameOption = Annotated[
    str, typer.Option("--name", "-n", help="Project slug, when no request file is given")
]


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _fail(error: Exception, as_json: bool) -> NoReturn:
    """Report an error and exit with the code for its class."""
    code = EXIT_INVALID if isinstance(error, _REQUEST_ERRORS) else EXIT_RENDER_FAILED
    if as_json:
        _echo_json(
            {
                "ok": False,
                "exit_code": code,
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        )
    else:
        console.print(f"[red]Error:[/] {error}")
    raise typer.Exit(code=code) from error


def _profile_dict(profile: Profile) -> dict[str, object]:
    data = asdict(profile)
    del data["template_directory"]
    data["components"] = list(profile.components)
    return data


def _component_dict(component: Component) -> dict[str, object]:
    return asdict(component)


def _resolution_dict(resolution: Resolution) -> dict[str, object]:
    return {
        "profile": resolution.profile.identifier,
        "profile_version": resolution.profile.version,
        "components": [
            {"id": component.identifier, "version": component.version}
            for component in resolution.components
        ],
        "requested": list(resolution.requested),
        "added": list(resolution.added),
        "dependencies": list(resolution.dependencies),
        "dependency_groups": {
            group: list(specs) for group, specs in resolution.dependency_groups.items()
        },
        "settings": [asdict(setting) for setting in resolution.settings],
        "lifecycle_commands": list(resolution.lifecycle_commands),
        "security_notes": list(resolution.security_notes),
    }


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
    """Generate deterministic Python projects from profiles, components, and template packs."""


def _parse_data(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated KEY=VALUE options into template answers."""
    data: dict[str, str] = {}
    for pair in pairs or ():
        key, separator, value = pair.partition("=")
        if not separator or not key:
            raise ConfigurationError(f"Template data must be KEY=VALUE, got '{pair}'.")
        data[key] = value
    return data


def _request(
    *,
    config: Path | None,
    project_name: str,
    profile: str,
    output_dir: Path,
    components: list[str] | None,
    data: list[str] | None,
    template: str | None,
    template_ref: str | None,
    template_source: str = DEFAULT_TEMPLATE_SOURCE,
    no_input: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
) -> RenderRequest:
    """Build a request from a TOML file or from command-line options."""
    if config is not None:
        return load_render_request(config, dry_run=dry_run)
    return RenderRequest(
        profile_id=profile,
        project_name=project_name,
        output_dir=output_dir,
        components=tuple(components or ()),
        no_input=no_input,
        overwrite=overwrite,
        dry_run=dry_run,
        data=_parse_data(data),
        template_source=template_source,
        template=template,
        template_ref=template_ref,
    )


def _render_and_report(build: Callable[[], RenderRequest], as_json: bool) -> None:
    """Render one request and display an actionable outcome."""
    try:
        result = render(build())
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    if as_json:
        _echo_json(
            {
                "ok": True,
                "dry_run": result.dry_run,
                "project_path": str(result.project_path),
                "manifest_path": str(result.manifest_path) if result.manifest_path else None,
                **_resolution_dict(result.resolution),
            }
        )
        return
    if result.dry_run:
        console.print(
            "[yellow]Dry run:[/] would create profile "
            f"'{result.profile.identifier}' at {result.project_path}"
        )
        return
    console.print(
        f"[green]Created[/] '{result.profile.identifier}' project at {result.project_path}"
    )
    console.print(f"Components: {', '.join(result.resolution.component_ids) or 'none'}")


@app.command("create")
def create(
    project_name: Annotated[
        str, typer.Argument(help="Lowercase project slug, for example: market-data-api")
    ],
    profile: ProfileOption = "python",
    output_dir: OutputOption = Path("."),
    no_input: NoInputOption = False,
    force: ForceOption = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Validate and show the target without writing files")
    ] = False,
    component: ComponentOption = None,
    data: DataOption = None,
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    template_source: TemplateSourceOption = DEFAULT_TEMPLATE_SOURCE,
    as_json: JsonOption = False,
) -> None:
    """Create a project from a bundled profile or a template pack."""
    _render_and_report(
        lambda: _request(
            config=None,
            project_name=project_name,
            profile=profile,
            output_dir=output_dir,
            components=component,
            data=data,
            template=template,
            template_ref=template_ref,
            template_source=template_source,
            no_input=no_input,
            overwrite=force,
            dry_run=dry_run,
        ),
        as_json,
    )


# Optional, fully equivalent spelling of `create` (same arguments and options).
app.command("create-project", help="Alias of `create`; accepts the same arguments and options.")(
    create
)

# Standalone `create-project` executable: `create-project NAME [OPTIONS]` runs `create` directly.
create_project_app = typer.Typer(
    name="create-project",
    help="Create a project from a bundled profile (same as `pytemplate create`).",
    add_completion=False,
)
create_project_app.command()(create)


@contextlib.contextmanager
def _catalog(template: str | None, template_ref: str | None, as_json: bool) -> Iterator[Catalog]:
    """Open the bundled catalog or a pack, reporting pack errors with the CLI exit codes."""
    try:
        with open_catalog(template, template_ref) as (catalog, _, _):
            yield catalog
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)


@app.command("list-profiles")
def list_profiles_command(
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    as_json: JsonOption = False,
) -> None:
    """List the profiles of the bundled catalog or a template pack."""
    with _catalog(template, template_ref, as_json) as catalog:
        profiles = catalog.profiles
    if as_json:
        _echo_json([_profile_dict(profile) for profile in profiles])
        return
    table = Table(title="Project profiles")
    table.add_column("ID", style="cyan")
    table.add_column("Kind")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Python")
    table.add_column("Components")
    table.add_column("Description")
    for profile in profiles:
        table.add_row(
            profile.identifier,
            profile.kind,
            profile.version,
            profile.status,
            ", ".join(profile.supported_python),
            ", ".join(profile.default_components) or "none",
            profile.description,
        )
    console.print(table)


@app.command("describe-profile")
def describe_profile(
    profile_id: Annotated[str, typer.Argument(help="Profile identifier")],
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    as_json: JsonOption = False,
) -> None:
    """Show metadata and template inputs for a profile."""
    with _catalog(template, template_ref, as_json) as catalog:
        try:
            profile = catalog.profile(profile_id)
        except ProfileNotFoundError as error:
            _fail(error, as_json)
        details = [
            question
            for question in catalog.question_details()
            if question["name"] in profile.questions
        ]
    if as_json:
        _echo_json({**_profile_dict(profile), "question_details": details})
        return
    console.print(
        f"[bold]{profile.name}[/] ({profile.identifier}, v{profile.version}, "
        f"{profile.kind}, {profile.status})"
    )
    console.print(profile.description)
    if profile.aliases:
        console.print(f"Compatibility aliases: {', '.join(profile.aliases)}")
    console.print(f"Supported Python: {', '.join(profile.supported_python)}")
    console.print(f"Default components: {', '.join(profile.default_components) or 'none'}")
    console.print(f"Optional components: {', '.join(profile.optional_components) or 'none'}")
    console.print(f"Template inputs: {', '.join(profile.questions) or 'none'}")
    console.print(f"Security posture: {profile.security_posture}")


@app.command("list-components")
def list_components_command(
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    as_json: JsonOption = False,
) -> None:
    """List the components of the bundled catalog or a template pack."""
    with _catalog(template, template_ref, as_json) as catalog:
        components = catalog.components
    if as_json:
        _echo_json([_component_dict(component) for component in components])
        return
    table = Table(title="Application components")
    table.add_column("ID", style="cyan")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Profiles")
    table.add_column("Requires")
    table.add_column("Description")
    for component in components:
        table.add_row(
            component.identifier,
            component.version,
            component.status,
            ", ".join(component.compatible_profiles),
            ", ".join(component.requires) or "-",
            component.description,
        )
    console.print(table)


@app.command("describe-component")
def describe_component(
    component_id: Annotated[str, typer.Argument(help="Component identifier")],
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    as_json: JsonOption = False,
) -> None:
    """Show metadata for a component."""
    with _catalog(template, template_ref, as_json) as catalog:
        try:
            component = catalog.component(component_id)
        except ComponentNotFoundError as error:
            _fail(error, as_json)
    if as_json:
        _echo_json(_component_dict(component))
        return
    console.print(
        f"[bold]{component.name}[/] ({component.identifier}, v{component.version}, "
        f"{component.status})"
    )
    console.print(component.description)
    console.print(f"Compatible profiles: {', '.join(component.compatible_profiles)}")
    console.print(f"Requires: {', '.join(component.requires) or 'none'}")
    console.print(f"Conflicts with: {', '.join(component.conflicts) or 'none'}")
    console.print(f"Dependencies: {', '.join(component.dependencies) or 'none'}")
    for group, specs in component.dependency_groups.items():
        console.print(f"Dependency group '{group}': {', '.join(specs)}")
    console.print(f"Owned paths: {', '.join(component.paths) or 'none'}")
    if component.questions:
        console.print(f"Template inputs: {', '.join(component.questions)}")
    for setting in component.settings:
        flags = [
            label
            for label, enabled in (
                ("required in production", setting.required_in_production),
                ("secret", setting.secret),
            )
            if enabled
        ]
        suffix = f" ({', '.join(flags)})" if flags else ""
        console.print(f"Setting {setting.name}: {setting.type}{suffix}. {setting.description}")
    for note in component.security_notes:
        console.print(f"Security: {note}")


@app.command("create-from-config")
def create_from_config(
    config: Annotated[Path, typer.Argument(help="TOML render-request file")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Validate and show the target without writing files")
    ] = False,
    as_json: JsonOption = False,
) -> None:
    """Create a project from a deterministic TOML render request."""
    _render_and_report(lambda: load_render_request(config, dry_run=dry_run), as_json)


def _plan_dict(result: RenderPlan) -> dict[str, object]:
    return {
        "ok": True,
        "project_path": str(result.project_path),
        "target_exists": result.target_exists,
        "package_name": result.package_name,
        "template": asdict(result.source),
        **_resolution_dict(result.resolution),
        "files": list(result.files),
    }


@app.command("validate")
def validate_config(
    config: ConfigArgument = None,
    project_name: NameOption = "my-project",
    profile: ProfileOption = "python",
    output_dir: OutputOption = Path("."),
    component: ComponentOption = None,
    data: DataOption = None,
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    as_json: JsonOption = False,
) -> None:
    """Validate a render request, including template answers, without writing the project."""
    try:
        request = _request(
            config=config,
            project_name=project_name,
            profile=profile,
            output_dir=output_dir,
            components=component,
            data=data,
            template=template,
            template_ref=template_ref,
            dry_run=True,
        )
        resolution, project_path = validate_request(request)
        planned = plan(request)
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    if as_json:
        payload = _plan_dict(planned)
        del payload["files"]
        _echo_json(payload)
        return
    console.print(f"[green]Valid[/] {resolution.profile.identifier} -> {project_path}")
    console.print(f"Components: {', '.join(resolution.component_ids) or 'none'}")
    if resolution.added:
        console.print(f"Added by requirements: {', '.join(resolution.added)}")


@app.command("plan")
def plan_command(
    config: ConfigArgument = None,
    project_name: NameOption = "my-project",
    profile: ProfileOption = "python",
    output_dir: OutputOption = Path("."),
    component: ComponentOption = None,
    data: DataOption = None,
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    as_json: JsonOption = False,
) -> None:
    """Show the resolved components, dependencies, and exact files, without writing anything."""
    try:
        result = plan(
            _request(
                config=config,
                project_name=project_name,
                profile=profile,
                output_dir=output_dir,
                components=component,
                data=data,
                template=template,
                template_ref=template_ref,
            )
        )
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    if as_json:
        _echo_json(_plan_dict(result))
        return
    resolution = result.resolution
    console.print(
        f"[bold]Plan[/] for '{resolution.profile.identifier}' at {result.project_path}"
        + (" [yellow](target exists; create needs --force)[/]" if result.target_exists else "")
    )
    console.print(f"Components: {', '.join(resolution.component_ids) or 'none'}")
    if resolution.added:
        console.print(f"Added by requirements: {', '.join(resolution.added)}")
    console.print(f"Dependencies: {', '.join(resolution.dependencies) or 'none'}")
    for group, specs in resolution.dependency_groups.items():
        console.print(f"Dependency group '{group}': {', '.join(specs)}")
    for setting in resolution.settings:
        console.print(f"Setting {result.package_name.upper()}_{setting.name} ({setting.type})")
    console.print(f"Files ({len(result.files)}):")
    for name in result.files:
        console.print(f"  {name}", markup=False)


@app.command("schema")
def schema_command(
    name: Annotated[
        str,
        typer.Argument(help=f"Schema to print: {', '.join(SCHEMAS)}"),
    ],
) -> None:
    """Print a JSON Schema for a manifest, request, or generated-project file."""
    if name not in SCHEMAS:
        console.print(f"[red]Error:[/] Unknown schema '{name}'. Available: {', '.join(SCHEMAS)}.")
        raise typer.Exit(code=EXIT_INVALID)
    _echo_json(SCHEMAS[name])


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
