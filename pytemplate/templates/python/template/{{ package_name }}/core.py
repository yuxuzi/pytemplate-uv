"""Core logic, kept independent of the command-line interface."""


def greet(name: str, *, formal: bool = False) -> str:
    """Return a greeting for ``name``."""
    if formal:
        return f"Greetings, esteemed {name}."
    return f"Hello, {name}!"
