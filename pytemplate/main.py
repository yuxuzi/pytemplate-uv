"""Command-line interface for creating Python projects from templates."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="pytemplate-uv",
    help="Create Python projects from templates using uv package manager",
    add_completion=True,
    rich_help_panel=True,
)
console = Console()


def _validate_template(template: str) -> Path:
    """Validate and return the path to the specified template.

    Args:
        template (str): Name of the project template.

    Returns:
        Path: Path to the template directory.

    Raises:
        typer.BadParameter: If template is not found.

    """
    templates_dir = Path(__file__).parent.parent / "templates"
    template_path = templates_dir / f"{template}-template"

    console.print(f"[yellow]Checking template path: {template_path}[/]")

    if not template_path.exists():
        available_templates = [
            d.name.replace("-template", "") for d in templates_dir.glob("*-template") if d.is_dir()
        ]

        error_text = Text("Template not found!", style="bold red")
        suggestion_text = Text(
            f"\nAvailable templates: {', '.join(available_templates)}", style="yellow"
        )

        console.print(Panel(Text.assemble(error_text, suggestion_text), border_style="red"))
        raise typer.BadParameter(f"Template '{template}' not found")

    console.print(f"[green]Using template path: {template_path}[/]")
    return template_path


def _get_context() -> dict[str, str]:
    """Retrieve context variables for project template.

    Returns:
        A dictionary of context variables.

    """
    return {
        "author": os.environ.get("USER", "your name"),
        "email": os.environ.get("USER_EMAIL", "your@email.com"),
        "github_username": os.environ.get("GITHUB_USERNAME", "your_username"),
    }


def _build_cookiecutter_command(
    template_path: Path, context: dict, no_input: bool = False, force: bool = False
) -> list[str]:
    """Build the cookiecutter command with appropriate options.
    Args:
        template_path: Path to the project template
        context: Context variables for the template
        no_input: Whether to skip interactive prompts
        force: Whether to overwrite existing project directory
    Returns:
        A list of command arguments.

    """  # noqa: D205, D411
    cookiecutter_cmd = [
        "cookiecutter",
        str(template_path),
        *[f"{k}={v}" for k, v in context.items()],
    ]

    if no_input:
        cookiecutter_cmd.append("--no-input")

    if force:
        cookiecutter_cmd.append("--overwrite-if-exists")

    return cookiecutter_cmd


@app.command()
def create_project(
    project_name: str = typer.Argument(None, help="Name of the project"),
    template: str = typer.Option(
        "pyproject", "--template", "-t", help="Template to use for project creation"
    ),
    no_input: bool = typer.Option(
        False, "--no-input", "-y", help="Skip prompts and use default values"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing project directory"),
):
    """Create a new project from a specified template."""
    template_path = _validate_template(template)
    context = _get_context()
    if project_name:
        context["project_name"] = project_name

    cookiecutter_cmd = _build_cookiecutter_command(template_path, context, no_input, force)

    try:
        result = subprocess.run(cookiecutter_cmd, text=True, check=True)
        console.print("[green]Project created successfully![/]")

        if result.stdout:
            console.print(f"[green]{result.stdout.strip()}[/]")

    except subprocess.CalledProcessError as e:
        console.print("[red]Project creation failed:[/]")
        console.print(f"Command: {' '.join(e.cmd)}")

        if e.stdout:
            console.print("[yellow]Standard Output:[/]")
            console.print(e.stdout)

        if e.stderr:
            console.print("[red]Error Output:[/]")
            console.print(e.stderr)

        raise typer.Exit(code=1)  # noqa: B904


if __name__ == "__main__":
    app()
