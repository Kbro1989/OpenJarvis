"""Slash Registry Integration — wires all handlers into the central registry.

Import this module once at startup to register all built-in commands.
"""
from __future__ import annotations

from openjarvis.slash.slash_registry import SlashCommandRegistry, SlashCommand
from openjarvis.slash.handlers import (
    handle_goal, handle_snapshot, handle_rollback,
    handle_queue, handle_steer, handle_webhook,
    handle_kanban, handle_curator,
)


def register_all(registry: SlashCommandRegistry) -> None:
    """Register all built-in slash commands."""

    # Planning
    registry.register(SlashCommand(
        name="/goal", handler=handle_goal,
        description="Set or list standing goals",
        category="planning", aliases=["/g"],
    ))

    # System
    registry.register(SlashCommand(
        name="/snapshot", handler=handle_snapshot,
        description="Create a system snapshot",
        category="system",
    ))
    registry.register(SlashCommand(
        name="/rollback", handler=handle_rollback,
        description="Rollback to a previous snapshot",
        category="system",
    ))

    # REPL
    registry.register(SlashCommand(
        name="/queue", handler=handle_queue,
        description="Queue an action for next turn",
        category="repl",
    ))
    registry.register(SlashCommand(
        name="/steer", handler=handle_steer,
        description="Inject instruction after next tool call",
        category="repl",
    ))

    # Integration
    registry.register(SlashCommand(
        name="/webhook", handler=handle_webhook,
        description="Manage webhook subscriptions",
        category="integration",
    ))

    # Organization
    registry.register(SlashCommand(
        name="/kanban", handler=handle_kanban,
        description="Multi-profile kanban board",
        category="organization",
    ))

    # Maintenance
    registry.register(SlashCommand(
        name="/curator", handler=handle_curator,
        description="Background skill maintenance",
        category="maintenance",
    ))
