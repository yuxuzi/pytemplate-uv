"""Command-line interface for the pytemplate project generator."""

from __future__ import annotations

import contextlib
import json
import shlex
import sys
from collections.abc import Callable, Iterator
from dataclasses import asdict, replace
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from pytemplate.agent_skill import (
    SkillInstallError,
    default_skills_dir,
    install_skill,
    skill_text,
)
from pytemplate.cli_options import (
    ConfigArgument,
    ForceOption,
    HubHelpCommand,
    HubOption,
    JsonOption,
    NameOption,
    NoCacheOption,
    NoInputOption,
    RequestOptions,
    TemplateCommitOption,
    TemplateDigestOption,
    TemplateOption,
    TemplateRefOption,
    YesOption,
    request_options,
)
from pytemplate.configuration import ConfigurationError, load_render_request
from pytemplate.errors import RenderError, RequestError
from pytemplate.hub import HubPin, pin_for
from pytemplate.packs import open_catalog
from pytemplate.picker import choose_components, choose_profile
from pytemplate.post_create import run_post_steps
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
    RenderPlan,
    RenderRequest,
    generator_version,
    plan,
    render,
)
from pytemplate.resolution import Resolution
from pytemplate.schema import SCHEMAS
from pytemplate.status import project_status
from pytemplate.suggestions import did_you_mean

app = typer.Typer(
    name="pytemplate",
    help="Generate deterministic Python projects from profiles, components, and template packs.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True, soft_wrap=True)
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


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _stdin_is_tty() -> bool:
    """Report whether prompts can be answered; tests replace this."""
    return sys.stdin.isatty()


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
        err_console.print(f"[red]Error:[/] {escape(str(error))}")
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


def _request(
    config: Path | None, project_name: str, opts: RequestOptions, **flags: bool
) -> RenderRequest:
    """Build a request from a TOML file or from command-line options."""
    if config is not None:
        if opts.hub is not None:
            raise RequestError(
                '--hub cannot be combined with a request file; set hub = "owner/pack@tag" in '
                "the file instead."
            )
        return load_render_request(config, dry_run=flags.get("dry_run", False), notify=_announce)
    return opts.build(project_name, **flags)


def _print_next_steps(project_path: Path, resolution: Resolution, request: RenderRequest) -> None:
    """Tell the user how to enter the new project and run the profile's lifecycle commands."""
    package = request.data.get("package_name", request.project_name.replace("-", "_"))
    console.print("\nNext steps:")
    console.print(f"  cd {shlex.quote(str(project_path))}", markup=False)
    for command in resolution.lifecycle_commands:
        console.print(f"  {command.replace('{package}', package)}", markup=False)


def _with_picked_components(opts: RequestOptions, as_json: bool) -> RequestOptions:
    """Offer the profile's optional components in a terminal and return the chosen options."""
    try:
        with open_catalog(
            opts.template,
            opts.template_ref,
            commit=opts.template_commit,
            digest=opts.template_digest,
            use_cache=not opts.no_cache,
        ) as (catalog, _, _):
            if opts.profile is None:
                raise RequestError("--profile must be chosen before its components are offered.")
            chosen = choose_components(catalog.profile(opts.profile), catalog.component_map())
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    return replace(opts, component=chosen or None)


def _resolved(opts: RequestOptions, as_json: bool) -> tuple[RequestOptions, HubPin | None]:
    """Resolve `--hub` to its pins, announce the pin on stderr, and return the pinned options."""
    try:
        resolved, pin = opts.resolved()
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    if pin is not None:
        err_console.print(pin.notice, markup=False)
    return resolved, pin


def _with_profile(
    opts: RequestOptions, pin: HubPin | None, as_json: bool, *, ask: bool
) -> RequestOptions:
    """Fill in the profile when `-p` is missing.

    A catalog with one profile uses it. Otherwise, when ``ask`` (a terminal without -y), the
    user chooses; when not, ``python`` is used, or the usual unknown-profile error lists them.
    """
    if opts.profile is not None:
        return opts
    try:
        with open_catalog(
            opts.template,
            opts.template_ref,
            commit=opts.template_commit,
            digest=opts.template_digest,
            use_cache=not opts.no_cache,
        ) as (catalog, _, _):
            profiles = catalog.profiles
            if len(profiles) == 1:
                identifier = profiles[0].identifier
            elif ask and profiles:
                checks = pin.profile_lifecycles if pin is not None else None
                identifier = choose_profile(profiles, checks)
            else:
                identifier = catalog.profile("python").identifier
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    return replace(opts, profile=identifier)


def _render_and_report(
    build: Callable[[], RenderRequest],
    as_json: bool,
    after: Callable[[Path], list[str]] | None = None,
) -> None:
    """Render one request and display an actionable outcome."""
    try:
        request = build()
        result = render(request)
        steps = after(result.project_path) if after and not result.dry_run else []
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    if as_json:
        _echo_json(
            {
                "ok": True,
                "dry_run": result.dry_run,
                "project_path": str(result.project_path),
                "manifest_path": str(result.manifest_path) if result.manifest_path else None,
                "template": asdict(result.source),
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
    for step in steps:
        console.print(f"[green]Also[/] {step}")
    _print_next_steps(result.project_path, result.resolution, request)


@app.command("create", cls=HubHelpCommand)
@request_options
def create(
    project_name: Annotated[
        str, typer.Argument(help="Lowercase project slug, for example: market-data-api")
    ],
    opts: RequestOptions,
    as_json: bool,
    yes: YesOption = False,
    no_input: NoInputOption = False,
    force: ForceOption = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Validate and show the target without writing files")
    ] = False,
    git: Annotated[
        bool, typer.Option("--git", help="Run git init and make the first commit afterwards")
    ] = False,
    lock: Annotated[
        bool, typer.Option("--lock", help="Run `uv lock` in the new project afterwards")
    ] = False,
) -> None:
    """Create a project from a bundled profile or a template pack."""
    if no_input:
        err_console.print(
            "[yellow]Warning:[/] --no-input is deprecated; use -y/--yes. It will be removed in 4.0."
        )
    # Machine output never prompts, so --json implies --yes.
    unattended = yes or no_input or as_json
    if not unattended and not _stdin_is_tty():
        _fail(
            RequestError(
                "Cannot prompt for answers: standard input is not a terminal. Pass -y/--yes to "
                "accept the template defaults, and --data KEY=VALUE to set individual answers."
            ),
            as_json,
        )
    opts, pin = _resolved(opts, as_json)
    opts = _with_profile(opts, pin, as_json, ask=not unattended)
    if not unattended and not opts.component:
        opts = _with_picked_components(opts, as_json)
    _render_and_report(
        lambda: opts.build(project_name, no_input=unattended, overwrite=force, dry_run=dry_run),
        as_json,
        after=(lambda path: run_post_steps(path, git=git, lock=lock)) if git or lock else None,
    )


# Optional, fully equivalent spelling of `create` (same arguments and options).
app.command(
    "create-project",
    help="Alias of `create`; accepts the same arguments and options.",
    cls=HubHelpCommand,
)(create)

# Standalone `create-project` executable: `create-project NAME [OPTIONS]` runs `create` directly.
create_project_app = typer.Typer(
    name="create-project",
    help="Create a project from a bundled profile (same as `pytemplate create`).",
    add_completion=False,
)
create_project_app.command(cls=HubHelpCommand)(create)


@contextlib.contextmanager
def _catalog(
    template: str | None,
    template_ref: str | None,
    as_json: bool,
    *,
    commit: str | None = None,
    digest: str | None = None,
    no_cache: bool = False,
    hub: str | None = None,
) -> Iterator[Catalog]:
    """Open the bundled catalog or a pack, reporting pack errors with the CLI exit codes."""
    try:
        if hub is not None:
            pin = pin_for(
                hub,
                template=template,
                template_ref=template_ref,
                template_commit=commit,
                template_digest=digest,
            )
            err_console.print(pin.notice, markup=False)
            template, template_ref = pin.location, pin.tag
            commit, digest = pin.commit, pin.digest
        with open_catalog(
            template, template_ref, commit=commit, digest=digest, use_cache=not no_cache
        ) as (catalog, _, _):
            yield catalog
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)


@app.command("list-profiles", cls=HubHelpCommand)
def list_profiles_command(
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    template_commit: TemplateCommitOption = None,
    template_digest: TemplateDigestOption = None,
    no_cache: NoCacheOption = False,
    as_json: JsonOption = False,
    hub: HubOption = None,
) -> None:
    """List the profiles of the bundled catalog or a template pack."""
    with _catalog(
        template,
        template_ref,
        as_json,
        commit=template_commit,
        digest=template_digest,
        no_cache=no_cache,
        hub=hub,
    ) as catalog:
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


@app.command("describe-profile", cls=HubHelpCommand)
def describe_profile(
    profile_id: Annotated[str, typer.Argument(help="Profile identifier")],
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    template_commit: TemplateCommitOption = None,
    template_digest: TemplateDigestOption = None,
    no_cache: NoCacheOption = False,
    as_json: JsonOption = False,
    hub: HubOption = None,
) -> None:
    """Show metadata and template inputs for a profile."""
    with _catalog(
        template,
        template_ref,
        as_json,
        commit=template_commit,
        digest=template_digest,
        no_cache=no_cache,
        hub=hub,
    ) as catalog:
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


@app.command("list-components", cls=HubHelpCommand)
def list_components_command(
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    template_commit: TemplateCommitOption = None,
    template_digest: TemplateDigestOption = None,
    no_cache: NoCacheOption = False,
    as_json: JsonOption = False,
    hub: HubOption = None,
) -> None:
    """List the components of the bundled catalog or a template pack."""
    with _catalog(
        template,
        template_ref,
        as_json,
        commit=template_commit,
        digest=template_digest,
        no_cache=no_cache,
        hub=hub,
    ) as catalog:
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


@app.command("describe-component", cls=HubHelpCommand)
def describe_component(
    component_id: Annotated[str, typer.Argument(help="Component identifier")],
    template: TemplateOption = None,
    template_ref: TemplateRefOption = None,
    template_commit: TemplateCommitOption = None,
    template_digest: TemplateDigestOption = None,
    no_cache: NoCacheOption = False,
    as_json: JsonOption = False,
    hub: HubOption = None,
) -> None:
    """Show metadata for a component."""
    with _catalog(
        template,
        template_ref,
        as_json,
        commit=template_commit,
        digest=template_digest,
        no_cache=no_cache,
        hub=hub,
    ) as catalog:
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
    _render_and_report(
        lambda: load_render_request(config, dry_run=dry_run, notify=_announce), as_json
    )


def _announce(line: str) -> None:
    """Print one line on stderr, the way `--hub` announces the pin it resolved."""
    err_console.print(line, markup=False)


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


@app.command("validate", cls=HubHelpCommand)
@request_options
def validate_config(
    opts: RequestOptions,
    as_json: bool,
    config: ConfigArgument = None,
    project_name: NameOption = "my-project",
) -> None:
    """Validate a render request, including template answers, without writing the project."""
    if config is None:
        opts, pin = _resolved(opts, as_json)
        opts = _with_profile(opts, pin, as_json, ask=False)
    try:
        request = _request(config, project_name, opts, dry_run=True)
        planned = plan(request)
        if planned.target_exists and not request.overwrite:
            raise RequestError(
                f"Output already exists: {planned.project_path}. Re-run with --force only if "
                "overwriting is intended."
            )
    except (*_REQUEST_ERRORS, RenderError) as error:
        _fail(error, as_json)
    if as_json:
        payload = _plan_dict(planned)
        del payload["files"]
        _echo_json(payload)
        return
    resolution = planned.resolution
    console.print(f"[green]Valid[/] {resolution.profile.identifier} -> {planned.project_path}")
    console.print(f"Components: {', '.join(resolution.component_ids) or 'none'}")
    if resolution.added:
        console.print(f"Added by requirements: {', '.join(resolution.added)}")


@app.command("plan", cls=HubHelpCommand)
@request_options
def plan_command(
    opts: RequestOptions,
    as_json: bool,
    config: ConfigArgument = None,
    project_name: NameOption = "my-project",
) -> None:
    """Show the resolved components, dependencies, and exact files, without writing anything."""
    if config is None:
        opts, pin = _resolved(opts, as_json)
        opts = _with_profile(opts, pin, as_json, ask=False)
    try:
        result = plan(_request(config, project_name, opts))
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


@app.command("status")
def status_command(
    path: Annotated[
        Path, typer.Argument(help="Generated project to inspect (default: current directory)")
    ] = Path("."),
    as_json: JsonOption = False,
) -> None:
    """List files changed, deleted, or added since the project was generated (read-only)."""
    try:
        report = project_status(path)
    except _REQUEST_ERRORS as error:
        _fail(error, as_json)
    if as_json:
        _echo_json(report.as_dict())
        return
    if report.clean:
        console.print(f"[green]No changes[/] since generation in {report.project_path}")
        return
    console.print(f"Changes since generation in {report.project_path}:")
    for label, names in (
        ("Changed", report.changed),
        ("Deleted", report.deleted),
        ("Added", report.added),
    ):
        if names:
            console.print(f"{label} ({len(names)}):")
            for name in names:
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
        err_console.print(
            f"[red]Error:[/] Unknown schema '{name}'.{did_you_mean(name, SCHEMAS)} "
            f"Available: {', '.join(SCHEMAS)}."
        )
        raise typer.Exit(code=EXIT_INVALID)
    _echo_json(SCHEMAS[name])


@skill_app.command("show")
def skill_show() -> None:
    """Print the skill (SKILL.md) for use with any AI tool."""
    typer.echo(skill_text(), nl=False)


@skill_app.command("install")
def skill_install(
    project: Annotated[
        bool,
        typer.Option("--project", help="Install into this directory instead of the home directory"),
    ] = False,
    agent: Annotated[
        str,
        typer.Option(
            "--agent",
            help="'claude' for .claude/skills (Claude Code), or 'agents' for .agents/skills "
            "(Codex and other Agent Skills clients)",
        ),
    ] = "claude",
    dest: Annotated[
        Path | None, typer.Option("--dest", help="Install into this skills directory instead")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing skill")] = False,
) -> None:
    """Install the skill so an AI coding agent can create projects with pytemplate."""
    try:
        skills_dir = dest if dest is not None else default_skills_dir(project=project, agent=agent)
        target = install_skill(skills_dir, force=force)
    except SkillInstallError as error:
        err_console.print(f"[red]Error:[/] {escape(str(error))}")
        raise typer.Exit(code=1) from error
    console.print(f"[green]Installed[/] skill at {target}")


if __name__ == "__main__":
    app()
