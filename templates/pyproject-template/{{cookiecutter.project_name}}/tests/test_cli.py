"""Tests for the CLI module."""

from typer.testing import CliRunner

from {{cookiecutter.package_name}}.cli import app

runner = CliRunner()

def test_hello_default():
    """Test default hello command."""
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.output

def test_hello_with_name():
    """Test hello command with a name."""
    result = runner.invoke(app, ["hello", "--name", "Alice"])
    assert result.exit_code == 0
    assert "Hello, Alice!" in result.output

def test_hello_formal():
    """Test formal greeting."""
    result = runner.invoke(app, ["hello", "--name", "Bob", "--formal"])
    assert result.exit_code == 0
    assert "Greetings, esteemed Bob." in result.output

def test_info():
    """Test info command."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Project Information" in result.output
    assert "{{cookiecutter.project_name}}" in result.output
    assert "{{cookiecutter.package_name}}" in result.output
