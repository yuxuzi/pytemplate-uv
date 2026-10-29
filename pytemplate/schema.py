"""JSON Schemas (draft 2020-12) for the factory contract, render requests, and manifests.

They let other tools validate inputs and read outputs without importing pytemplate-uv.
Tests keep each schema's properties in step with the loaders.
"""

from __future__ import annotations

from typing import Any

from pytemplate.profiles import (
    COMPONENT_STATUSES,
    CONTRACT_VERSION,
    PROFILE_KINDS,
    PROFILE_STATUSES,
    SETTING_TYPES,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_ID = "https://github.com/yuxuzi/pytemplate-uv/schemas/{name}-v{version}.json"

_TEXT: dict[str, Any] = {"type": "string", "minLength": 1}
_NAMES: dict[str, Any] = {"type": "array", "items": _TEXT, "uniqueItems": True}
_GROUPS: dict[str, Any] = {"type": "object", "additionalProperties": _NAMES}
_CONTRACT: dict[str, Any] = {"const": CONTRACT_VERSION}
_IDENTIFIER: dict[str, Any] = {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"}


def _object(properties: dict[str, Any], required: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
        **extra,
    }


def _document(name: str, title: str, body: dict[str, Any], version: int) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "$id": _ID.format(name=name, version=version),
        "title": title,
        **body,
    }


_SETTING = _object(
    {
        "name": _TEXT,
        "type": {"enum": list(SETTING_TYPES)},
        "description": _TEXT,
        "required_in_production": {"type": "boolean"},
        "secret": {"type": "boolean"},
    },
    ["name", "type", "description"],
)

PROFILE = _document(
    "profile",
    "pytemplate-uv profile manifest (profile.toml)",
    _object(
        {
            "contract": _CONTRACT,
            "id": _IDENTIFIER,
            "name": _TEXT,
            "description": _TEXT,
            "version": _TEXT,
            "kind": {"enum": list(PROFILE_KINDS)},
            "status": {"enum": list(PROFILE_STATUSES)},
            "aliases": _NAMES,
            "supported_python": {
                "type": "array",
                "items": {"enum": ["3.11", "3.12", "3.13", "3.14", "3.15"]},
                "uniqueItems": True,
            },
            "default_components": _NAMES,
            "optional_components": _NAMES,
            "legacy_components": _NAMES,
            "dependencies": _NAMES,
            "dependency_groups": _GROUPS,
            "questions": _NAMES,
            "lifecycle_commands": _NAMES,
            "security_posture": _TEXT,
        },
        ["contract", "id", "name", "description", "version", "kind", "status"],
    ),
    CONTRACT_VERSION,
)

COMPONENT = _document(
    "component",
    "pytemplate-uv component manifest (components/<id>.toml)",
    _object(
        {
            "contract": _CONTRACT,
            "id": _IDENTIFIER,
            "name": _TEXT,
            "description": _TEXT,
            "version": _TEXT,
            "status": {"enum": list(COMPONENT_STATUSES)},
            "compatible_profiles": _NAMES,
            "requires": _NAMES,
            "requires_any": _NAMES,
            "conflicts": _NAMES,
            "dependencies": _NAMES,
            "dependency_groups": _GROUPS,
            "paths": _NAMES,
            "settings": {"type": "array", "items": _SETTING},
            "questions": _NAMES,
            "lifecycle_commands": _NAMES,
            "security_notes": _NAMES,
        },
        ["contract", "id", "name", "description", "version", "status", "compatible_profiles"],
    ),
    CONTRACT_VERSION,
)

PACK = _document(
    "pack",
    "pytemplate-uv template pack manifest (pytemplate-pack.toml)",
    _object(
        {
            "contract": _CONTRACT,
            "id": _IDENTIFIER,
            "name": _TEXT,
            "description": _TEXT,
            "version": _TEXT,
        },
        ["contract", "id", "name", "description", "version"],
    ),
    CONTRACT_VERSION,
)

REQUEST = _document(
    "request",
    "pytemplate-uv render request (create-from-config, validate, plan --config)",
    _object(
        {
            "project_name": {"type": "string", "pattern": "^[a-z][a-z0-9]*(-[a-z0-9]+)*$"},
            "profile": _TEXT,
            "output_dir": _TEXT,
            "components": _NAMES,
            "no_input": {"type": "boolean"},
            "overwrite": {"type": "boolean"},
            "data": {"type": "object", "additionalProperties": {"type": "string"}},
            "template_source": _TEXT,
            "template": _TEXT,
            "template_ref": _TEXT,
        },
        ["project_name"],
    ),
    1,
)

MANIFEST = _document(
    "manifest",
    "pytemplate-uv generation manifest (.pytemplate.toml)",
    _object(
        {
            "schema": {"const": 2},
            "generator": _object({"name": _TEXT, "version": _TEXT}, ["name", "version"]),
            "template": _object(
                {
                    "kind": {"enum": ["bundled", "pack"]},
                    "source": {"type": "string"},
                    "ref": _TEXT,
                    "pack": _TEXT,
                    "pack_version": _TEXT,
                },
                ["kind", "source"],
            ),
            "profile": _object(
                {"id": _TEXT, "version": _TEXT, "supported_python": _NAMES},
                ["id", "version", "supported_python"],
            ),
            "components": {
                "type": "array",
                "items": _object(
                    {
                        "id": _TEXT,
                        "version": _TEXT,
                        "status": {"enum": list(COMPONENT_STATUSES)},
                        "reason": {"enum": ["default", "requested", "required"]},
                    },
                    ["id", "version", "status", "reason"],
                ),
            },
            "answers": {
                "type": "object",
                "additionalProperties": {
                    "anyOf": [{"type": "string"}, {"type": "boolean"}, _NAMES]
                },
            },
            "files": {
                "type": "array",
                "items": _object(
                    {
                        "path": _TEXT,
                        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "owner": _TEXT,
                    },
                    ["path", "sha256", "owner"],
                ),
            },
        },
        ["schema", "generator", "template", "profile", "answers"],
    ),
    2,
)

SCHEMAS: dict[str, dict[str, Any]] = {
    "profile": PROFILE,
    "component": COMPONENT,
    "pack": PACK,
    "request": REQUEST,
    "manifest": MANIFEST,
}
