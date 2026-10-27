"""Command-line interface for the pytemplate project generator."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pytemplate.profiles import ProfileNotFoundError, get_profile, list_profiles
from pytemplate.rendering import RenderError, RenderRequest, render

app = typer.Typer(
    name="pytemplate",
    help="Generate deterministic Python project foundations from bundled profiles.",
    no_args_is_help=True,
)
console = Console()


def _create(
    project_name: str,
    profile: str,
    output_dir: Path,
    no_input: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Render one profile and display an actionable outcome."""
    try:
        result = render(
            RenderRequest(
                profile_id=profile,
                project_name=project_name,
                output_dir=output_dir,
                no_input=no_input,
                overwrite=force,
                dry_run=dry_run,
            )
        )
    except (RenderError, ProfileNotFoundError) as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error

    if result.dry_run:
        console.print(
            f"[yellow]Dry run:[/] would create profile '{result.profile.identifier}' at {result.project_path}"
        )
        return
    console.print(f"[green]Created[/] '{result.profile.identifier}' project at {result.project_path}")


@app.command("create")
def create(
    project_name: Annotated[str, typer.Argument(help="Lowercase project slug, for example: market-data-api")],
    profile: Annotated[str, typer.Option("--profile", "-p", help="Profile identifier")] = "python",
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Existing parent directory")] = Path("."),
    no_input: Annotated[bool, typer.Option("--no-input", help="Do not show Cookiecutter prompts")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Allow overwriting an existing output")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Validate and show the target without writing files")] = False,
) -> None:
    """Create a project from a bundled profile."""
    _create(project_name, profile, output_dir, no_input, force, dry_run)


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
    _create(project_name, profile, output_dir, no_input, force, dry_run)


@app.command("list-profiles")
def list_profiles_command() -> None:
    """List bundled profiles and their descriptions."""
    table = Table(title="Bundled project profiles")
    table.add_column("ID", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    for profile in list_profiles():
        table.add_row(profile.identifier, profile.version, profile.description)
    console.print(table)


@app.command("describe-profile")
def describe_profile(profile_id: Annotated[str, typer.Argument(help="Profile identifier")]) -> None:
    """Show metadata for a bundled profile."""
    try:
        profile = get_profile(profile_id)
    except ProfileNotFoundError as error:
        console.print(f"[red]Error:[/] {error}")
        raise typer.Exit(code=1) from error
    console.print(f"[bold]{profile.name}[/] ({profile.identifier}, v{profile.version})")
    console.print(profile.description)
    if profile.aliases:
        console.print(f"Compatibility aliases: {', '.join(profile.aliases)}")


if __name__ == "__main__":
    app()
