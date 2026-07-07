"""``jarvis chat`` — interactive multi-turn chat REPL."""

from __future__ import annotations

import sys
from typing import List, Optional

import click
from rich.console import Console
from rich.markdown import Markdown

from openjarvis.cli._tool_names import resolve_tool_names
from openjarvis.core.config import load_config
from openjarvis.core.events import EventBus
from openjarvis.core.types import Message, Role
from openjarvis.memory import publish_completed_exchange
from openjarvis.cli.ask import _append_kingwen_block


def _cmd_models(console: "Console", active_model: str, engine_name: str) -> None:
    """
    /models — ModelRolodex display.
    Shows:
      1. Live Ollama models + ternary router class (King Wen-conscious)
      2. Task chain (query-type → preferred model order)
      3. Cloudflare Worker endpoints from secrets store
    """
    from rich.table import Table
    from rich.panel import Panel
    from rich.rule import Rule

    try:
        from openjarvis.secrets.store import (
            CF_WORKERS, LOCAL_PORTS, MODEL_ROLODEX,
            task_model_chain, ternary_model_class,
        )
    except ImportError as exc:
        console.print(f"[red]Secrets store unavailable:[/red] {exc}")
        return

    # ── 1. Live Ollama models + ternary router class ───────────────────────
    live_models: list = []
    ollama_url = LOCAL_PORTS.get("ollama", {}).get("url", "http://localhost:11434")
    try:
        import urllib.request, json as _json
        req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = _json.loads(resp.read())
            live_models = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    # Current King Wen oracle state for ternary routing
    kw_hex_cat = "boundary"
    kw_hex_action = "WAIT"
    try:
        from openjarvis.emotion.kingwen import getHexagram
        import random, time
        hw = getHexagram("", session_id="models_cmd", emotional_input=int(time.time()) % 100)
        kw_hex_cat = hw.get("hexagram_category", "boundary")
        kw_hex_action = hw.get("hexagram_action", hw.get("action", "WAIT"))
    except Exception:
        pass

    ternary_class = ternary_model_class(kw_hex_cat, kw_hex_action)
    model_classes = MODEL_ROLODEX.get("model_classes", {})
    ternary_keywords = model_classes.get(ternary_class, [])

    # Build live model table
    mdl_table = Table(title="Live Ollama Models + Ternary Router", show_lines=False)
    mdl_table.add_column("Model", style="cyan", no_wrap=True)
    mdl_table.add_column("Class match", style="green")
    mdl_table.add_column("Active", justify="center")

    if live_models:
        for m in live_models:
            matched_class = "—"
            for cls_name, kws in model_classes.items():
                if any(kw in m.lower() for kw in kws):
                    matched_class = cls_name
                    break
            is_ternary_pick = any(kw in m.lower() for kw in ternary_keywords)
            is_active = "★" if m == active_model else ("◆" if is_ternary_pick else "")
            mdl_table.add_row(m, matched_class, is_active)
    else:
        mdl_table.add_row("[dim]Ollama offline or no models[/dim]", "—", "")

    console.print(mdl_table)
    console.print(
        f"[dim]Oracle: hex_cat=[cyan]{kw_hex_cat}[/cyan]  action=[cyan]{kw_hex_action}[/cyan]  "
        f"→ ternary class=[green]{ternary_class}[/green]  "
        f"keywords={ternary_keywords}[/dim]"
    )

    # ── 2. Task chain ──────────────────────────────────────────────────────
    console.print()
    tc_table = Table(title="Task Chain (query type → model priority)", show_lines=False)
    tc_table.add_column("Task", style="yellow", width=12)
    tc_table.add_column("Priority 1", style="cyan")
    tc_table.add_column("Priority 2", style="dim cyan")
    tc_table.add_column("Priority 3", style="dim")

    for task, chain in MODEL_ROLODEX.get("task_chain", {}).items():
        def _avail(m: str) -> str:
            return f"[green]{m}[/green]" if m in live_models else f"[dim]{m}[/dim]"
        tc_table.add_row(
            task,
            _avail(chain[0]) if len(chain) > 0 else "—",
            _avail(chain[1]) if len(chain) > 1 else "—",
            _avail(chain[2]) if len(chain) > 2 else "—",
        )

    console.print(tc_table)

    # ── 3. CF Worker endpoints (brief) ────────────────────────────────────
    console.print()
    cf_table = Table(title="Cloudflare Workers", show_lines=False)
    cf_table.add_column("Worker", style="magenta", width=22)
    cf_table.add_column("URL", style="blue")
    cf_table.add_column("Status", justify="center")

    status_style = {"live": "[green]live[/green]", "not_deployed": "[yellow]pending[/yellow]"}
    for name, w in CF_WORKERS.items():
        st = w.get("status", "unknown")
        cf_table.add_row(
            w.get("worker_name", name),
            w.get("base_url", ""),
            status_style.get(st, st),
        )

    console.print(cf_table)
    console.print(
        f"[dim]Active session: engine=[cyan]{engine_name}[/cyan]  "
        f"model=[cyan]{active_model}[/cyan]  "
        f"ollama={ollama_url}[/dim]"
    )


def _read_input(prompt: str = "You> ") -> Optional[str]:
    """Read user input with graceful EOF handling."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None


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
def chat(
    engine_key: str | None,
    model_name: str | None,
    agent_name: str | None,
    tools: str | None,
    system_prompt: str | None,
    persona_name: str | None,
) -> None:
    """Start an interactive multi-turn chat session.

    Commands during chat:
      /quit, /exit  — end session
      /clear        — clear conversation history
      /model        — show current model
      /help         — show available commands
      /history      — show conversation history
    """
    console = Console(stderr=True)

    config = load_config()
    bus = EventBus(record_history=False)

    import dataclasses as _dc

    effective_mf = (
        _dc.replace(config.memory_files, persona_name=persona_name)
        if persona_name is not None
        else config.memory_files
    )

    # Resolve engine
    from openjarvis.engine import get_engine
    from openjarvis.intelligence import register_builtin_models

    register_builtin_models()

    resolved = get_engine(config, engine_key)
    if resolved is None:
        console.print("[red]No inference engine available.[/red]")
        sys.exit(1)

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
            sys.exit(1)

    # Resolve agent (optional)
    agent = None
    agent_key = agent_name or config.agent.default_agent
    if agent_key and agent_key != "none":
        try:
            import openjarvis.agents  # noqa: F401 — trigger registration
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
                        import openjarvis.tools  # noqa: F401 — trigger registration
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

                    def _confirm(prompt: str) -> bool:
                        console.print(
                            f"[yellow]Confirm:[/yellow] {prompt} [y/N] ",
                            end="",
                        )
                        ans = input().strip().lower()
                        return ans in ("y", "yes")

                    kwargs["interactive"] = True
                    kwargs["confirm_callback"] = _confirm

                import inspect as _inspect

                if (
                    "prompt_builder"
                    in _inspect.signature(agent_cls.__init__).parameters
                ):
                    from openjarvis.prompt.builder import SystemPromptBuilder

                    kwargs["prompt_builder"] = SystemPromptBuilder(
                        agent_template=config.agent.default_system_prompt or "",
                        memory_files_config=effective_mf,
                        system_prompt_config=config.system_prompt,
                    )

                agent = agent_cls(engine, model, **kwargs)
        except Exception as exc:
            console.print(f"[yellow]Agent '{agent_key}' failed: {exc}[/yellow]")

    # Print banner
    console.print(
        f"[green bold]OpenJarvis Chat[/green bold]\n"
        f"  Engine: [cyan]{engine_name}[/cyan]  Model: [cyan]{model}[/cyan]"
        f"  Agent: [cyan]{agent_key or 'direct'}[/cyan]\n"
        f"  Type /help for commands, /quit to exit.\n"
    )

    # Background-work status banner (disappears after first user message)
    from openjarvis.cli._bg_state import get_status
    from openjarvis.cli._chat_banner import render_startup_banner

    _banner = render_startup_banner(get_status())
    if _banner:
        console.print(f"[dim cyan]{_banner}[/dim cyan]")

    # Completion-notification dispatcher (fires once per task per session)
    from openjarvis.cli._chat_notifications import NotificationDispatcher

    _notifications = NotificationDispatcher(get_status())

    # Automatic long-term memory — extracts durable facts in the background.
    memory_service = None
    try:
        from openjarvis.memory import build_memory_service

        memory_service = build_memory_service(config, engine, model, event_bus=bus)
        if memory_service is not None:
            memory_service.start()
            console.print("[dim]  Memory: active[/dim]")
    except Exception as exc:
        console.print(f"[yellow]Memory service unavailable: {exc}[/yellow]")
        memory_service = None

    # Conversation state
    if not system_prompt:
        from openjarvis.prompt.builder import SystemPromptBuilder

        builder = SystemPromptBuilder(
            agent_template=config.agent.default_system_prompt or "",
            memory_files_config=effective_mf,
            system_prompt_config=config.system_prompt,
        )
        system_prompt = builder.build()

    history: List[Message] = []
    if system_prompt:
        history.append(Message(role=Role.SYSTEM, content=system_prompt))

    # REPL loop
    while True:
        for note in _notifications.diff(get_status()):
            console.print(f"[dim cyan]{note}[/dim cyan]")

        user_input = _read_input()
        if user_input is None:
            console.print("\n[dim]Goodbye![/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # Handle slash commands
        cmd = user_input.lower()
        if cmd in ("/quit", "/exit", "/q"):
            from openjarvis.cli._oracle_speak import shutdown as _oracle_shutdown
            from openjarvis.cli._oracle_dashboard import render as _oracle_render

            _oracle_shutdown()
            console.print("[dim]Goodbye![/dim]")
            break
        elif cmd == "/clear":
            history = []
            if system_prompt:
                history.append(Message(role=Role.SYSTEM, content=system_prompt))
            console.print("[dim]History cleared.[/dim]")
            continue
        elif cmd.startswith("/oracle "):
            query = user_input[len("/oracle "):].strip()
            if not query:
                console.print("[yellow]Usage: /oracle <your question>[/yellow]")
                continue
            from openjarvis.cli._oracle_speak import oracle_speak_async, get_emotional_input

            def _done(fut):
                try:
                    result = fut.result()
                except Exception as exc:
                    console.print(f"\n[red]Oracle voice failed: {exc}[/red]\n")
                    return
                mode = result.get("mode", "chat")
                console.print(f"\n[bold magenta]Oracle[/bold magenta] [{mode}]")
                console.print(result.get("text_spoken", ""))
                scenes = result.get("scenes") or []
                if scenes:
                    scene = scenes[0]
                    prosody = scene.get("prosody") or {}
                    console.print(
                        f"[dim]porosity={result.get('porosity')} trajectory={result.get('trajectory')} dominant={result.get('dominant_axis')} rule={result.get('rule')} "
                        f"chaos={prosody.get('chaos',0):.2f} whimsy={prosody.get('whimsy',0):.2f} darkTone={prosody.get('darkTone',0):.2f} coherence={prosody.get('coherence',0):.2f}[/dim]"
                    )
                if result.get("audio_path"):
                    played = "yes" if result.get("played") else "no"
                    console.print(f"[dim]audio={result.get('audio_path')} played={played} backend={result.get('backend')}[/dim]")
                if mode == "do" and result.get("tool_hint"):
                    console.print(f"[bold yellow]Do[/bold yellow]: {result.get('tool_hint')} | rule={result.get('rule')}")

            future = oracle_speak_async(query, emotional_input=get_emotional_input(), on_done=_done)
            console.print("[dim]Oracle is consulting... voice will appear when ready.[/dim]")
            continue
        elif cmd.startswith("/counsel "):
            query = user_input[len("/counsel "):].strip()
            if not query:
                console.print("[yellow]Usage: /counsel <your question>[/yellow]")
                continue
            from openjarvis.cli._oracle_speak import oracle_speak_async, get_emotional_input

            counsel_prefix = "Counsel me through past, present, and future truth: "

            def _done(fut):
                try:
                    result = fut.result()
                except Exception as exc:
                    console.print(f"\n[red]Oracle counsel failed: {exc}[/red]\n")
                    return
                console.print(_oracle_render(result))

            future = oracle_speak_async(counsel_prefix + query, emotional_input=get_emotional_input(), on_done=_done)
            console.print("[dim]Oracle is counseling... voice will appear when ready.[/dim]")
            continue
        elif cmd == "/model":
            console.print(
                f"Model: [cyan]{model}[/cyan]  Engine: [cyan]{engine_name}[/cyan]"
            )
            continue
        elif cmd == "/models":
            _cmd_models(console, model, engine_name)
            continue
        elif cmd == "/help":
            console.print(
                "[bold]Commands:[/bold]\n"
                "  /quit, /exit  — end session\n"
                "  /clear        — clear conversation\n"
                "  /model        — show active model\n"
                "  /models       — ModelRolodex: live Ollama + ternary router + CF workers\n"
                "  /history      — show conversation\n"
                "  /oracle <q>   — consult King Wen, synthesize voice to file\n"
                "  /counsel <q>  — same as /oracle with PPF framing\n"
                "  /help         — this message"
            )
            continue
        elif cmd == "/history":
            if not history:
                console.print("[dim]No history yet.[/dim]")
            else:
                for msg in history:
                    role_str = msg.role if isinstance(msg.role, str) else msg.role.value
                    role = role_str.upper()
                    console.print(f"[bold]{role}:[/bold] {msg.content[:200]}")
            continue

        # Add user message
        history.append(Message(role=Role.USER, content=user_input))

        # Generate response
        try:
            if agent is not None:
                response = agent.run(user_input)
                _append_kingwen_block(agent, response, user_input=user_input)
                content = (
                    response.content if hasattr(response, "content") else str(response)
                )
            else:
                result = engine.generate(history, model=model)
                content = (
                    result.get("content", "")
                    if isinstance(result, dict)
                    else str(result)
                )

            history.append(Message(role=Role.ASSISTANT, content=content))
            console.print()
            console.print(Markdown(content))
            console.print()

            publish_completed_exchange(
                bus,
                user_input,
                content,
                source="cli.chat",
            )
        except KeyboardInterrupt:
            console.print("\n[dim]Generation interrupted.[/dim]")
        except Exception as exc:
            console.print(f"\n[red]Error: {exc}[/red]\n")

    if memory_service is not None:
        memory_service.stop()


__all__ = ["chat"]
