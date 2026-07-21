"""Slash Command Registry — single source of truth for all / handlers.

Unifies CLI, HTTP API, and desktop bridge dispatch.
Every slash command is registered once and callable from any interface.

Usage:
    from openjarvis.slack.slash_registry import SlashCommandRegistry, SlashCommand

    registry = SlashCommandRegistry()
    registry.register(SlashCommand(
        name="/goal",
        handler=handle_goal,
        description="Set standing goal",
        category="planning",
        aliases=["/g"],
    ))

    # Dispatch from CLI:
    result = registry.dispatch("/goal", user_input, context)

    # Dispatch from HTTP:
    result = registry.dispatch("/goal", payload, context)
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class SlashCommand:
    """Definition of a slash command."""
    name: str                          # e.g. "/goal"
    handler: Callable                  # sync or async callable
    description: str = ""
    category: str = "general"          # planning, system, memory, automation, etc.
    aliases: List[str] = field(default_factory=list)
    requires_auth: bool = False
    hidden: bool = False               # Don't show in /help
    deprecated: bool = False

    def __post_init__(self):
        # Normalize name to start with /
        if not self.name.startswith("/"):
            self.name = "/" + self.name
        # Normalize aliases
        self.aliases = [a if a.startswith("/") else "/" + a for a in self.aliases]


@dataclass
class SlashContext:
    """Context passed to every slash handler."""
    session_id: str
    user_input: str                    # Full raw input
    query: str = ""                    # Extracted query/payload
    console: Any = None                # Rich console (CLI) or None (HTTP)
    request: Any = None                # FastAPI request (HTTP) or None (CLI)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SlashCommandRegistry:
    """Central registry for all slash commands."""

    def __init__(self) -> None:
        self._commands: Dict[str, SlashCommand] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(self, cmd: SlashCommand) -> None:
        """Register a slash command."""
        if cmd.name in self._commands:
            logger.warning("Overwriting slash command: %s", cmd.name)
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

        # Category index
        cat = cmd.category
        if cat not in self._categories:
            self._categories[cat] = []
        if cmd.name not in self._categories[cat]:
            self._categories[cat].append(cmd.name)

        logger.debug("Registered slash command: %s (%s)", cmd.name, cmd.category)

    def unregister(self, name: str) -> bool:
        """Remove a slash command."""
        name = name if name.startswith("/") else "/" + name
        if name not in self._commands:
            return False
        cmd = self._commands[name]
        # Remove all aliases too
        to_remove = [cmd.name] + cmd.aliases
        for key in to_remove:
            self._commands.pop(key, None)
        self._categories.get(cmd.category, []).remove(cmd.name)
        return True

    def get(self, name: str) -> Optional[SlashCommand]:
        """Lookup a command by name or alias."""
        name = name if name.startswith("/") else "/" + name
        return self._commands.get(name)

    def dispatch(self, name: str, ctx: SlashContext) -> Any:
        """Dispatch to a handler by name. Works for sync and async."""
        cmd = self.get(name)
        if not cmd:
            raise KeyError(f"Unknown slash command: {name}")
        if cmd.deprecated:
            logger.warning("Deprecated command used: %s", cmd.name)

        handler = cmd.handler
        sig = inspect.signature(handler)

        # Build kwargs based on handler signature
        kwargs = {}
        if "ctx" in sig.parameters:
            kwargs["ctx"] = ctx
        if "session_id" in sig.parameters:
            kwargs["session_id"] = ctx.session_id
        if "user_input" in sig.parameters:
            kwargs["user_input"] = ctx.user_input
        if "query" in sig.parameters:
            kwargs["query"] = ctx.query
        if "console" in sig.parameters:
            kwargs["console"] = ctx.console

        if asyncio.iscoroutinefunction(handler):
            return handler(**kwargs)
        return handler(**kwargs)

    async def dispatch_async(self, name: str, ctx: SlashContext) -> Any:
        """Async dispatch with automatic await."""
        result = self.dispatch(name, ctx)
        if asyncio.isfuture(result) or inspect.isawaitable(result):
            return await result
        return result

    def list_commands(self, category: Optional[str] = None, include_hidden: bool = False) -> List[SlashCommand]:
        """List registered commands."""
        seen = set()
        result = []
        for cmd in self._commands.values():
            if cmd.name in seen:
                continue
            if not include_hidden and cmd.hidden:
                continue
            if category and cmd.category != category:
                continue
            seen.add(cmd.name)
            result.append(cmd)
        return sorted(result, key=lambda c: c.name)

    def list_categories(self) -> List[str]:
        """List all categories."""
        return sorted(self._categories.keys())

    def build_help(self, category: Optional[str] = None) -> str:
        """Build /help text output."""
        lines = ["Available Commands:", "=" * 40]
        cats = [category] if category else self.list_categories()
        for cat in cats:
            cmds = self.list_commands(category=cat)
            if not cmds:
                continue
            lines.append(f"\n[{cat}]")
            for cmd in cmds:
                alias_str = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
                dep = " [DEPRECATED]" if cmd.deprecated else ""
                lines.append(f"  {cmd.name}{alias_str}{dep}")
                if cmd.description:
                    lines.append(f"    {cmd.description}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export registry as JSON-serializable dict."""
        return {
            "commands": [
                {
                    "name": cmd.name,
                    "description": cmd.description,
                    "category": cmd.category,
                    "aliases": cmd.aliases,
                    "requires_auth": cmd.requires_auth,
                    "hidden": cmd.hidden,
                    "deprecated": cmd.deprecated,
                }
                for cmd in self.list_commands(include_hidden=True)
            ],
            "categories": self.list_categories(),
        }
