"""Async delegation registry stub for OpenJarvis.

Maintains compatibility with Hermes' list_async_delegations interface.
"""
from __future__ import annotations

from typing import Any, Dict, List

def list_async_delegations() -> List[Dict[str, Any]]:
    """Return a list of active async delegations. Stub returning empty list."""
    return []
