"""The supported Python interface of pytemplate-uv.

Import from here rather than from internal modules, whose names may change between minor
releases::

    from pytemplate import api

    request = api.RenderRequest(profile_id="fastapi", project_name="svc", output_dir=Path("."))
    planned = api.plan(request)     # resolution and file list; writes nothing
    result = api.render(request)    # renders and publishes the project

Errors: `RequestError` and the profile/component errors mean the request is invalid and nothing
was written; any other `RenderError` means rendering or writing failed.
"""

from __future__ import annotations

from pytemplate.configuration import ConfigurationError
from pytemplate.configuration import load_render_request as load_request
from pytemplate.errors import PackError, RenderError, RequestError
from pytemplate.packs import TemplateSource, open_catalog
from pytemplate.profiles import (
    Catalog,
    Component,
    ComponentCompatibilityError,
    ComponentNotFoundError,
    ManifestError,
    Profile,
    ProfileNotFoundError,
    Setting,
    bundled_catalog,
)
from pytemplate.rendering import RenderPlan, RenderRequest, RenderResult, plan, render
from pytemplate.rendering import validate_request as validate
from pytemplate.resolution import Resolution, resolve
from pytemplate.schema import SCHEMAS
from pytemplate.updating import UpdateError, UpdateRequest, UpdateResult, update

__all__ = [
    "SCHEMAS",
    "Catalog",
    "Component",
    "ComponentCompatibilityError",
    "ComponentNotFoundError",
    "ConfigurationError",
    "ManifestError",
    "PackError",
    "Profile",
    "ProfileNotFoundError",
    "RenderError",
    "RenderPlan",
    "RenderRequest",
    "RenderResult",
    "RequestError",
    "Resolution",
    "Setting",
    "TemplateSource",
    "UpdateError",
    "UpdateRequest",
    "UpdateResult",
    "bundled_catalog",
    "load_request",
    "open_catalog",
    "plan",
    "render",
    "resolve",
    "update",
    "validate",
]
