"""A CliRunner with Click 8.2 result semantics on every supported Typer and Click version.

Click 8.2+ captures stderr separately and also includes it in ``output``. Click 8.1 does one or
the other (``mix_stderr``), so on 8.1 the runner keeps stderr separate and adds it to ``output``.
Newer Typer releases do not depend on Click, so this module never imports it.
"""

from __future__ import annotations

import inspect
from typing import Any

from typer.testing import CliRunner

_CLICK_81 = "mix_stderr" in inspect.signature(CliRunner.__init__).parameters


class _Runner81(CliRunner):
    def __init__(self) -> None:
        super().__init__(mix_stderr=False)  # type: ignore[call-arg]

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        result = super().invoke(*args, **kwargs)
        combined = property(lambda self: self.stdout + self.stderr)
        result.__class__ = type("Result", (type(result),), {"output": combined})
        return result


def make_runner() -> CliRunner:
    """Return a runner whose results expose ``stderr`` and a combined ``output``."""
    return _Runner81() if _CLICK_81 else CliRunner()
