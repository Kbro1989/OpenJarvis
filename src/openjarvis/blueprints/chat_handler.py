"""Chat handler for /blueprint commands in OpenJarvis interactive mode.

Usage in chat_cmd.py:
    from openjarvis.blueprints.chat_handler import handle_blueprint_command
    elif cmd.startswith("/blueprint"):
        handle_blueprint_command(user_input, console)
        continue

This keeps blueprint logic out of chat_cmd.py and makes it independently testable.
"""
from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console

from openjarvis.blueprints.registry import BlueprintRegistry
from openjarvis.blueprints.store import BlueprintStore
from openjarvis.blueprints.executor import BlueprintExecutor
from openjarvis.blueprints.scheduler_bridge import TaskSchedulerBridge

logger = logging.getLogger(__name__)

DEFAULT_DB = Path.home() / ".openjarvis" / "blueprints.db"
DEFAULT_ARTIFACTS = Path.home() / ".openjarvis" / "artifacts" / "blueprints"


def _ensure_dirs() -> None:
    DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _get_components():
    _ensure_dirs()
    store = BlueprintStore(DEFAULT_DB)
    executor = BlueprintExecutor(store, artifacts_root=str(DEFAULT_ARTIFACTS))
    bridge = TaskSchedulerBridge(store, executor)
    registry = BlueprintRegistry()
    return store, executor, bridge, registry


def handle_blueprint_command(user_input: str, console: Console) -> None:
    """Handle /blueprint <subcmd> [arg] from the chat interface."""
    parts = user_input.strip().split(maxsplit=2)
    if len(parts) == 1:
        console.print(
            "[yellow]Usage:[/yellow] /blueprint <catalog|list|create|run|pause|resume|delete> [name]"
        )
        return
    subcmd = parts[1].lower()
    arg = parts[2] if len(parts) > 2 else ""
    _, executor, bridge, registry = _get_components()

    if subcmd == "catalog":
        console.print("[bold]Available Blueprints:[/bold]")
        for bp in registry.all():
            status = "[green]OK[/green]" if bp.actionable else "[dim]--[/dim]"
            console.print(f"  {status} [cyan]{bp.key}[/cyan] -- {bp.title}")
            console.print(f"    [dim]{bp.description}[/dim]")

    elif subcmd == "list":
        jobs = bridge.list_jobs()
        if not jobs:
            console.print("[dim]No blueprint jobs configured.[/dim]")
        else:
            console.print(
                f"[bold]{'Key':20s} {'Status':10s} {'Schedule':20s} {'Last Run'}[/bold]"
            )
            for job in jobs:
                last = job.get("last_run") or "Never"
                console.print(
                    f"{job['key']:20s} {job['status']:10s} "
                    f"{job['schedule']:20s} {last}"
                )

    elif subcmd == "create" and arg:
        definition = registry.match(arg)
        if not definition:
            console.print(f"[red]Unknown blueprint: {arg}[/red]")
            return
        result = bridge.create_blueprint_job(key=definition.key)
        console.print(f"[green]Created:[/green] {result['key']} @ {result['schedule']}")

    elif subcmd == "run" and arg:
        definition = registry.match(arg)
        if not definition:
            console.print(f"[red]Unknown blueprint: {arg}[/red]")
            return
        result = executor.run(definition)
        console.print(f"[green]Executed:[/green] {result.status}")
        if result.artifact_path:
            console.print(f"  Artifact: [cyan]{result.artifact_path}[/cyan]")
        if result.summary:
            console.print(f"  Summary: {result.summary[:200]}")
        if result.error:
            console.print(f"  [red]Error:[/red] {result.error}")

    elif subcmd == "pause" and arg:
        bridge.pause_job(arg)
        console.print(f"[yellow]Paused:[/yellow] {arg}")

    elif subcmd == "resume" and arg:
        if bridge.resume_job(arg):
            console.print(f"[green]Resumed:[/green] {arg}")
        else:
            console.print(f"[red]Failed to resume:[/red] {arg}")

    elif subcmd == "delete" and arg:
        bridge.delete_job(arg)
        console.print(f"[red]Deleted:[/red] {arg}")

    else:
        console.print(
            f"[dim]Unknown subcommand '{subcmd}'. "
            f"Try: catalog, list, create, run, pause, resume, delete[/dim]"
        )