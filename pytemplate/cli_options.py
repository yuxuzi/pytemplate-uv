"""Shared command-line options: the request options of `create`, `validate`, and `plan`."""

from __future__ import annotations

import functools
import inspect
import typing
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from pytemplate.configuration import ConfigurationError
from pytemplate.profiles import bundled_catalog
from pytemplate.rendering import RenderRequest

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
TemplateCommitOption = Annotated[
    str | None,
    typer.Option(
        "--template-commit",
        help="Refuse the git pack unless --template-ref resolves to this full commit hash",
    ),
]
TemplateDigestOption = Annotated[
    str | None,
    typer.Option(
        "--template-digest",
        help="Refuse the git pack unless its files match this SHA-256 digest",
    ),
]
NoCacheOption = Annotated[
    bool,
    typer.Option(
        "--no-cache",
        help="Fetch a pinned git pack again instead of using the local cache",
    ),
]


def _bundled_choices(ctx: typer.Context, kind: str, incomplete: str) -> list[tuple[str, str]]:
    """Complete identifiers from the bundled catalog; never fail, and skip a --template pack."""
    if ctx.params.get("template"):
        return []
    try:
        catalog = bundled_catalog()
        items = (
            [(p.identifier, p.description) for p in catalog.profiles]
            if kind == "profile"
            else [(c.identifier, c.description) for c in catalog.components]
        )
    except Exception:  # completion must never print a traceback into the user's shell
        return []
    return [(name, text) for name, text in items if name.startswith(incomplete)]


def complete_profiles(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
    """Shell completion of bundled profile identifiers."""
    return _bundled_choices(ctx, "profile", incomplete)


def complete_components(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
    """Shell completion of bundled component identifiers."""
    return _bundled_choices(ctx, "component", incomplete)


ProfileOption = Annotated[
    str,
    typer.Option("--profile", "-p", help="Profile identifier", autocompletion=complete_profiles),
]
OutputOption = Annotated[Path, typer.Option("--output-dir", "-o", help="Existing parent directory")]
YesOption = Annotated[
    bool, typer.Option("--yes", "-y", help="Accept template defaults without prompting")
]
# Deprecated spelling of --yes: hidden from help, warns once, removed in 4.0.
NoInputOption = Annotated[
    bool, typer.Option("--no-input", hidden=True, help="Deprecated: use -y/--yes")
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
        autocompletion=complete_components,
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
ConfigArgument = Annotated[
    Path | None,
    typer.Argument(help="TOML render-request file; when omitted, use the options below"),
]
NameOption = Annotated[
    str, typer.Option("--name", "-n", help="Project slug, when no request file is given")
]


@dataclass(frozen=True)
class RequestOptions:
    """The request options shared by `create`, `validate`, and `plan`, read once per command."""

    profile: str
    output_dir: Path
    component: list[str] | None
    data: list[str] | None
    template: str | None
    template_ref: str | None
    template_commit: str | None
    template_digest: str | None
    no_cache: bool = False

    def build(
        self,
        project_name: str,
        *,
        no_input: bool = True,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> RenderRequest:
        """Build a request from these options and the per-command flags."""
        return RenderRequest(
            profile_id=self.profile,
            project_name=project_name,
            output_dir=self.output_dir,
            components=tuple(self.component or ()),
            no_input=no_input,
            overwrite=overwrite,
            dry_run=dry_run,
            data=parse_data(self.data),
            template=self.template,
            template_ref=self.template_ref,
            template_commit=self.template_commit,
            template_digest=self.template_digest,
            use_cache=not self.no_cache,
        )


# Parameter name -> (annotation, default). The decorator below appends these to a command so the
# three request commands declare their twelve shared options once.
_SHARED_PARAMETERS: dict[str, tuple[object, object]] = {
    "profile": (ProfileOption, "python"),
    "output_dir": (OutputOption, Path(".")),
    "component": (ComponentOption, None),
    "data": (DataOption, None),
    "template": (TemplateOption, None),
    "template_ref": (TemplateRefOption, None),
    "template_commit": (TemplateCommitOption, None),
    "template_digest": (TemplateDigestOption, None),
    "no_cache": (NoCacheOption, False),
    "as_json": (JsonOption, False),
}


def request_options(command: Callable[..., None]) -> Callable[..., None]:
    """Give a command the shared request options as `opts` and `as_json` keyword arguments."""
    signature = inspect.signature(command)
    hints = typing.get_type_hints(command, include_extras=True)
    own = [
        p.replace(annotation=hints[name])
        for name, p in signature.parameters.items()
        if name not in ("opts", "as_json")
    ]
    shared = [
        inspect.Parameter(
            name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default, annotation=annotation
        )
        for name, (annotation, default) in _SHARED_PARAMETERS.items()
    ]

    @functools.wraps(command)
    def wrapper(**kwargs: object) -> None:
        as_json = bool(kwargs.pop("as_json"))
        opts = RequestOptions(**{k: kwargs.pop(k) for k in _SHARED_PARAMETERS if k != "as_json"})  # type: ignore[arg-type]
        command(opts=opts, as_json=as_json, **kwargs)

    wrapper.__signature__ = signature.replace(parameters=[*own, *shared])  # type: ignore[attr-defined]
    wrapper.__annotations__ = {
        **{k: v for k, v in hints.items() if k not in ("opts", "as_json")},
        **{name: annotation for name, (annotation, _) in _SHARED_PARAMETERS.items()},
    }
    return wrapper


def parse_data(pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated KEY=VALUE options into template answers."""
    data: dict[str, str] = {}
    for pair in pairs or ():
        key, separator, value = pair.partition("=")
        if not separator or not key:
            raise ConfigurationError(f"Template data must be KEY=VALUE, got '{pair}'.")
        data[key] = value
    return data
