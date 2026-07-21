"""Built-in slash handlers for Hermes-parity capabilities.

These are stub implementations that emit structured instruction payloads.
Each handler can be overridden by the user or connected to real backends.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from openjarvis.slash.slash_registry import SlashContext

logger = logging.getLogger(__name__)


def handle_goal(ctx: SlashContext) -> Dict[str, Any]:
    """Set or list standing goals."""
    query = ctx.query.strip()
    if not query:
        return {
            "type": "goal_list",
            "session_id": ctx.session_id,
            "goals": [],  # Fetch from store
            "message": "No standing goals set. Usage: /goal <description>",
        }
    return {
        "type": "goal_set",
        "session_id": ctx.session_id,
        "goal": query,
        "status": "active",
        "created_at": int(time.time()),
        "message": f"Goal set: {query}",
    }


def handle_snapshot(ctx: SlashContext) -> Dict[str, Any]:
    """Create a system snapshot."""
    snapshot_id = f"snap-{ctx.session_id}-{int(time.time())}"
    return {
        "type": "snapshot_create",
        "session_id": ctx.session_id,
        "snapshot_id": snapshot_id,
        "message": f"Snapshot created: {snapshot_id}",
    }


def handle_rollback(ctx: SlashContext) -> Dict[str, Any]:
    """Rollback to a previous snapshot."""
    snapshot_id = ctx.query.strip()
    if not snapshot_id:
        return {
            "type": "snapshot_rollback",
            "session_id": ctx.session_id,
            "snapshot_id": None,
            "message": "Usage: /rollback <snapshot_id>",
        }
    return {
        "type": "snapshot_rollback",
        "session_id": ctx.session_id,
        "snapshot_id": snapshot_id,
        "message": f"Rolled back to {snapshot_id}",
    }


def handle_queue(ctx: SlashContext) -> Dict[str, Any]:
    """Queue an action for next turn."""
    if not ctx.query.strip():
        return {
            "type": "queue_add",
            "session_id": ctx.session_id,
            "action": None,
            "position": "next",
            "message": "Usage: /queue <action>",
        }
    return {
        "type": "queue_add",
        "session_id": ctx.session_id,
        "action": ctx.query.strip(),
        "position": "next",
        "message": f"Queued: {ctx.query.strip()}",
    }


def handle_steer(ctx: SlashContext) -> Dict[str, Any]:
    """Inject instruction after next tool call."""
    instruction = ctx.query.strip()
    if not instruction:
        return {
            "type": "steer_inject",
            "session_id": ctx.session_id,
            "instruction": None,
            "trigger": "post_tool",
            "message": "Usage: /steer <instruction>",
        }
    return {
        "type": "steer_inject",
        "session_id": ctx.session_id,
        "instruction": instruction,
        "trigger": "post_tool",
        "message": f"Steer set: {instruction}",
    }


def handle_webhook(ctx: SlashContext) -> Dict[str, Any]:
    """Manage webhook subscriptions."""
    parts = ctx.query.split(maxsplit=2)
    subcmd = parts[0] if parts else "list"
    return {
        "type": f"webhook_{subcmd}",
        "session_id": ctx.session_id,
        "message": f"Webhook {subcmd} executed.",
    }


def handle_kanban(ctx: SlashContext) -> Dict[str, Any]:
    """Multi-profile kanban board."""
    return {
        "type": "kanban_show",
        "session_id": ctx.session_id,
        "profiles": [],  # Fetch from store
        "message": "Kanban board displayed.",
    }


def handle_curator(ctx: SlashContext) -> Dict[str, Any]:
    """Background skill maintenance."""
    return {
        "type": "curator_scan",
        "session_id": ctx.session_id,
        "skills_checked": 0,
        "message": "Skill maintenance scan complete.",
    }
