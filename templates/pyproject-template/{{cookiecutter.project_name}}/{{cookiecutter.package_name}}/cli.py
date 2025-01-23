"""Command-line interface for {{cookiecutter.project_name}}."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="{{cookiecutter.package_name}}",
    help="CLI for {{cookiecutter.project_name}}",
    rich_help_panel=True,
    no_args_is_help=True,
)
console = Console()

@app.command()
def hello(
    name: Optional[str] = typer.Option(None, help="Name to greet"),
    formal: bool = typer.Option(False, "--formal", "-f", help="Use formal greeting")
):
    """
    Greet a person with an optional formal greeting.

    Args:
        name: The name of the person to greet. If not provided, greets the world.
        formal: Whether to use a formal greeting style.
    """
    if name is None:
        name = "World"
    
    if formal:
        greeting = f"Greetings, esteemed {name}."
    else:
        greeting = f"Hello, {name}!"
    
    console.print(greeting, style="bold green")

@app.command()
def info():
    """
    Display project information in a rich table.
    """
    table = Table(title="Project Information")
    
    table.add_column("Attribute", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Name", "{{cookiecutter.project_name}}")
    table.add_row("Package", "{{cookiecutter.package_name}}")
    table.add_row("Description", "{{cookiecutter.description}}")
    table.add_row("Author", "{{cookiecutter.author}}")
    
    console.print(table)

def main():
    """Entry point for the CLI application."""
    app()

if __name__ == "__main__":
    main()