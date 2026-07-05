"""``jarvis inject`` — send a native runtime request through the full Jarvis stack."""

from __future__ import annotations

import logging
from typing import List, Optional

import click
from rich.console import Console
from rich.markdown import Markdown

from openjarvis.cli._banner import print_banner
from openjarvis.cli._tool_names import resolve_tool_names
from openjarvis.core.config import load_config
from openjarvis.core.events import EventBus
from openjarvis.core.types import Message, Role
from openjarvis.engine import get_engine
from openjarvis.intelligence import register_builtin_models
from openjarvis.prompt.builder import SystemPromptBuilder
from openjarvis.sdk import JarvisSystem

logger = logging.getLogger(__name__)


@click.command()
@click.option("-e", "--engine", "engine_key", default=None, help="Engine backend.")
@click.option("-m", "--model", "model_name", default=None, help="Model to use.")
@click.option("-a", "--agent", "agent_name", default=None, help="Agent type.")
@click.option("--tools", default=None, help="Comma-separated tool names.")
@click.option("--system", "system_prompt", default=None, help="Custom system prompt.")
@click.option(
    "--persona",
    "persona_name",
    default=None,
    help=(
        "Named persona dir under ~/.openjarvis/personas/<name>/ "
        "(overrides config). Pass 'none' to disable all persona files."
    ),
)
@click.argument("prompt", required=False)
def inject(
    engine_key: Optional[str],
    model_name: Optional[str],
    agent_name: Optional[str],
    tools: Optional[str],
    system_prompt: Optional[str],
    persona_name: Optional[str],
    prompt: Optional[str],
) -> None:
    """Run a native Jarvis request through the full runtime stack."""

    console = Console(stderr=True)
    config = load_config()
    bus = EventBus(record_history=False)

    import dataclasses as _dc

    effective_mf = (
        _dc.replace(config.memory_files, persona_name=persona_name)
        if persona_name is not None
        else config.memory_files
    )

    register_builtin_models()
    resolved = get_engine(config, engine_key)
    if resolved is None:
        console.print("[red]No inference engine available.[/red]")
        raise click.ClickException("No inference engine available.")

    engine_name, engine = resolved
    model = model_name or config.intelligence.default_model
    if not model:
        from openjarvis.engine import discover_engines, discover_models

        all_engines = discover_engines(config)
        all_models = discover_models(all_engines)
        engine_models = all_models.get(engine_name, [])
        if engine_models:
            model = engine_models[0]
        else:
            console.print("[red]No model available.[/red]")
            raise click.ClickException("No model available.")

    if not prompt:
        prompt = click.prompt("Prompt")

    agent = None
    agent_key = agent_name or config.agent.default_agent
    if agent_key and agent_key != "none":
        try:
            import openjarvis.agents  # noqa: F401
            from openjarvis.core.registry import AgentRegistry

            if AgentRegistry.contains(agent_key):
                agent_cls = AgentRegistry.get(agent_key)
                kwargs: dict = {"bus": bus}

                if getattr(agent_cls, "accepts_tools", False):
                    tool_names_list = resolve_tool_names(
                        tools,
                        getattr(config.tools, "enabled", None),
                        getattr(config.agent, "tools", None),
                    )
                    if tool_names_list:
                        import openjarvis.tools  # noqa: F401
                        from openjarvis.core.registry import ToolRegistry
                        from openjarvis.tools._stubs import BaseTool

                        tool_instances = []
                        for tname in tool_names_list:
                            if ToolRegistry.contains(tname):
                                tcls = ToolRegistry.get(tname)
                                if isinstance(tcls, type) and issubclass(
                                    tcls, BaseTool
                                ):
                                    tool_instances.append(tcls())
                                elif isinstance(tcls, BaseTool):
                                    tool_instances.append(tcls)
                        if tool_instances:
                            kwargs["tools"] = tool_instances
                    kwargs["max_turns"] = config.agent.max_turns
                    kwargs["interactive"] = True
                    kwargs["confirm_callback"] = lambda prompt: True

                import inspect as _inspect

                if (
                    "prompt_builder"
                    in _inspect.signature(agent_cls.__init__).parameters
                ):
                    kwargs["prompt_builder"] = SystemPromptBuilder(
                        agent_template=config.agent.default_system_prompt or "",
                        memory_files_config=effective_mf,
                        system_prompt_config=config.system_prompt,
                    )

                agent = agent_cls(engine, model, **kwargs)
        except Exception as exc:
            console.print(f"[yellow]Agent '{agent_key}' failed: {exc}[/yellow]")

    console.print(
        f"[green bold]Jarvis Inject[/green bold]\n"
        f"  Engine: [cyan]{engine_name}[/cyan]  Model: [cyan]{model}[/cyan]"
        f"  Agent: [cyan]{agent_key or 'direct'}[/cyan]\n"
        f"  Prompt: [cyan]{prompt}[/cyan]\n"
    )

    try:
        if agent is not None:
            response = agent.run(prompt)
            from openjarvis.cli.ask import _append_kingwen_block

            _append_kingwen_block(agent, response, user_input=prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
        else:
            messages: List[Message] = []
            if system_prompt:
                messages.append(Message(role=Role.SYSTEM, content=system_prompt))
            else:
                builder = SystemPromptBuilder(
                    agent_template=config.agent.default_system_prompt or "",
                    memory_files_config=effective_mf,
                    system_prompt_config=config.system_prompt,
                )
                built = builder.build()
                if built:
                    messages.append(Message(role=Role.SYSTEM, content=built))
            messages.append(Message(role=Role.USER, content=prompt))
            result = engine.generate(messages, model=model)
            content = result.get("content", "") if isinstance(result, dict) else str(result)

        console.print()
        console.print(Markdown(content))
        console.print()
    except KeyboardInterrupt:
        console.print("\n[dim]Generation interrupted.[/dim]")
    except Exception as exc:
        console.print(f"\n[red]Error: {exc}[/red]\n")
        raise click.ClickException(str(exc))


__all__ = ["inject"]
