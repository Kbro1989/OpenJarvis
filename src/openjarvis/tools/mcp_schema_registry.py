"""Copyable MCP JSON schema registry and validator.

Reads schema JSONs from antigravity MCP directories and exposes a lightweight
validator so OpenJarvis can inspect tool surfaces without breaking existing
``mcp_adapter.py`` behaviour.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

_SCHEMA_ROOT = os.path.join("C:", os.sep, "Users", "krist", ".gemini", "antigravity", "mcp")
_JSON_TOOL_DIRS = ["datacloud_alloydb_remote", "datacloud_bigquery_remote"]


def _load_schema_files() -> Dict[str, Dict[str, Any]]:
    """Discover tool schemas from known antigravity MCP JSON directories."""
    schemas: Dict[str, Dict[str, Any]] = {}
    for directory in _JSON_TOOL_DIRS:
        tool_dir = os.path.join(_SCHEMA_ROOT, directory)
        if not os.path.isdir(tool_dir):
            continue
        for filename in os.listdir(tool_dir):
            if not filename.endswith(".json"):
                continue
            tool_path = os.path.join(tool_dir, filename)
            with open(tool_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            tool_name = data.get("name")
            if isinstance(tool_name, str) and tool_name:
                schemas[tool_name] = data
    return schemas


_SCHEMAS = _load_schema_files()


def load_schema(name: str) -> Dict[str, Any]:
    """Return the raw JSON schema dict for ``name``.

    Raises ``KeyError`` when ``name`` is not registered.
    """
    if name not in _SCHEMAS:
        raise KeyError(name)
    return dict(_SCHEMAS[name])


def list_tools() -> List[str]:
    """Return all registered MCP tool names in sorted order."""
    return sorted(_SCHEMAS.keys())


def validate_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Validate ``args`` against the JSON schema for ``name``.

    Returns ``{"valid": True}`` or ``{"valid": False, "error": str}``.
    """
    try:
        jsonschema = _jsonschema_module()
    except RuntimeError as exc:
        return {"valid": False, "error": str(exc)}

    try:
        schema = load_schema(name)
    except KeyError:
        return {"valid": False, "error": f"Unknown tool: {name}"}

    parameters = schema.get("parameters", {"type": "object"})
    try:
        jsonschema.validate(args, parameters)
    except jsonschema.ValidationError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True}


def _jsonschema_module() -> Any:
    try:
        import jsonschema as module
    except ImportError as exc:
        raise RuntimeError(
            "jsonschema is required to validate MCP tool calls."
        ) from exc
    return module


__all__ = ["load_schema", "list_tools", "validate_call"]
