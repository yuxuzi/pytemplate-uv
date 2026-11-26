"""The supported Python interface of pytemplate-uv.

Import from here rather than from internal modules, whose names may change between minor
releases::

    from pytemplate import api

    request = api.RenderRequest(profile_id="fastapi", project_name="svc", output_dir=Path("."))
    planned = api.plan(request)     # resolution and file list; writes nothing
    result = api.render(request)    # renders and publishes the project

``PACK_CATEGORIES`` is the fixed list a pack's ``categories`` may use. ``pack_digest(root)``
returns a pack's digest, the value ``--template-digest`` pins. Tools that record categories or
digests, such as pytemplate-hub, should use these rather than keep their own copies.

Errors: catch `RequestError` for an invalid request (nothing was written); it covers
`ConfigurationError`, `ManifestError`, `PackError`, and the profile and component errors, which are
also `ValueError` for compatibility. Any other `RenderError` means rendering or writing failed.
"""

from __future__ import annotations

from pytemplate.configuration import ConfigurationError
from pytemplate.configuration import load_render_request as load_request
from pytemplate.errors import PackError, RenderError, RequestError
from pytemplate.packs import (
    PACK_CATEGORIES,
    PackManifest,
    TemplateSource,
    open_catalog,
    pack_digest,
    read_pack_manifest,
)
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

__all__ = [
    "PACK_CATEGORIES",
    "SCHEMAS",
    "Catalog",
    "Component",
    "ComponentCompatibilityError",
    "ComponentNotFoundError",
    "ConfigurationError",
    "ManifestError",
    "PackError",
    "PackManifest",
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
    "bundled_catalog",
    "load_request",
    "open_catalog",
    "pack_digest",
    "read_pack_manifest",
    "plan",
    "render",
    "resolve",
    "validate",
]
