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
    /models — ModelRolodex display (card-style, matching POG2_ModelRolodex_Workflow).
    Shows:
      1. Oracle state card + ternary router class
      2. Live Ollama model cards with task-fit / ternary match markers
      3. Task-chain cards (local + cloud), mirroring run_query.js/run_router.js
      4. Cloudflare Worker endpoint cards
    """
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.text import Text

    try:
        from openjarvis.secrets.store import (
            CF_WORKERS,
            LOCAL_PORTS,
            MODEL_ROLODEX,
            task_model_chain,
            ternary_model_class,
            task_fit_for,
        )
    except ImportError as exc:
        console.print(f"[red]Secrets store unavailable:[/red] {exc}")
        return

    # Current King Wen oracle state for ternary routing
    kw_hex_cat = "boundary"
    kw_hex_action = "WAIT"
    try:
        from openjarvis.emotion.kingwen import KingWenEmotionProvider
        import random, time
        provider = KingWenEmotionProvider(
            registry_path=MODEL_ROLODEX["data_paths"]["hexagram_registry"],
            weights_path=MODEL_ROLODEX["data_paths"]["emotional_weights"],
            reflections_path=MODEL_ROLODEX["data_paths"]["temporal_reflections"],
        )
        hw = provider.getHexagram("/models", session_id="models_cmd", emotional_input=int(time.time()) % 100)
        kw_hex_cat = hw.get("hexagram_category", "boundary")
        kw_hex_action = hw.get("hexagram_action", hw.get("action", "WAIT"))
    except Exception:
        pass

    ternary_class = ternary_model_class(kw_hex_cat, kw_hex_action)
    model_classes = MODEL_ROLODEX.get("model_classes", {})
    ternary_keywords = model_classes.get(ternary_class, [])

    oracle_text = Text()
    oracle_text.append("Hexagram category: ", style="dim")
    oracle_text.append(kw_hex_cat, style="cyan")
    oracle_text.append("  Action: ", style="dim")
    oracle_text.append(kw_hex_action, style="cyan")
    oracle_text.append("  Ternary class: ", style="dim")
    oracle_text.append(ternary_class, style="green")
    oracle_text.append("  Keywords: ", style="dim")
    oracle_text.append(", ".join(ternary_keywords), style="green")
    console.print(Panel(oracle_text, title="[bold]Oracle + Ternary Router[/bold]", expand=False))

    # ── 2. Live Ollama models as cards ─────────────────────────────────────
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

    if live_models:
        for m in live_models:
            matched_class = "—"
            matched_task = "—"
            for cls_name, kws in model_classes.items():
                if any(kw in m.lower() for kw in kws):
                    matched_class = cls_name
                    break
            sample_query = f"Run a {ternary_class.lower()} King Wen task."
            inferred_task = task_fit_for(sample_query)
            task_chain = task_model_chain(inferred_task)
            if m in task_chain:
                idx = task_chain.index(m)
                matched_task = f"P{idx + 1}"
            is_ternary_pick = any(kw in m.lower() for kw in ternary_keywords)
            is_active = "★" if m == active_model else ("◆" if is_ternary_pick else "")
            model_text = Text()
            model_text.append(m, style="cyan")
            if is_active:
                model_text.append(f"  {is_active}", style="yellow")
            model_text.append("\nClass: ", style="dim")
            model_text.append(matched_class, style="green")
            model_text.append("  Task rank: ", style="dim")
            model_text.append(matched_task, style="yellow")
            console.print(Panel(model_text, expand=False))
    else:
        console.print(Panel("[dim]Ollama offline or no models[/dim]", title="[bold]Local Models[/bold]", expand=False))

    # ── 3. Task-chain cards (local + cloud) ─────────────────────────────────
    console.print(Rule("Task Chains"))

    for title, chain_key in [("Local Ollama", "task_chain"), ("Cloud", "task_chain_openrouter")]:
        chains = MODEL_ROLODEX.get(chain_key, {})
        for task, chain in chains.items():
            if not isinstance(chain, list):
                continue
            entries = []
            for idx, m in enumerate(chain[:3], 1):
                style = "green" if m in live_models else "dim"
                entries.append(f"P{idx}: [{style}]{m}[/{style}]")
            task_text = Text()
            task_text.append(f"{task}: ", style="yellow")
            task_text.append("  ".join(entries))
            console.print(Panel(task_text, title=f"[bold]{title}[/bold]  ·  {task}", expand=False))

    # ── 4. CF Worker endpoint cards ─────────────────────────────────────────
    console.print(Rule("Cloudflare Workers"))
    for name, w in CF_WORKERS.items():
        worker_text = Text()
        worker_text.append("URL: ", style="dim")
        worker_text.append(w.get("base_url", ""), style="blue")
        worker_text.append("\nStatus: ", style="dim")
        st = w.get("status", "unknown")
        worker_text.append(st, style="green" if st == "live" else "yellow")
        endpoints = w.get("endpoints", {})
        if endpoints:
            worker_text.append("\nEndpoints:\n", style="dim")
            for ep, val in endpoints.items():
                worker_text.append(f"  {ep}: ", style="dim")
                worker_text.append(val + "\n", style="cyan")
        console.print(Panel(worker_text, title=f"[bold]{w.get('worker_name', name)}[/bold]", expand=False))

    console.print(
        f"[dim]Active session: engine=[cyan]{engine_name}[/cyan]  "
        f"model=[cyan]{active_model}[/cyan]  ollama={ollama_url}[/dim]"
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
                director = result.get("director_payload") or {}
                scene = (director.get("scene") or {}) if isinstance(director, dict) else {}
                if scene.get("description"):
                    console.print(scene["description"])
                if scene.get("visualPrompt"):
                    console.print(f"[dim]{scene['visualPrompt'][:260]}[/dim]")
                if scene.get("styleInfluence"):
                    console.print(f"[dim]style={scene['styleInfluence'][:160]}[/dim]")
                if director.get("playback_instructions"):
                    pi = director["playback_instructions"]
                    console.print(f"[dim]playback={pi.get('level')} | route={pi.get('route')} | action={pi.get('action')}[/dim]")
                if scene.get("prosody"):
                    prosody = scene["prosody"]
                    console.print(
                        f"[dim]chaos={prosody.get('chaos',0):.2f} whimsy={prosody.get('whimsy',0):.2f} darkTone={prosody.get('darkTone',0):.2f} coherence={prosody.get('coherence',0):.2f} voiceWeight={prosody.get('voiceWeight',0):.2f}[/dim]"
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
                director = result.get("director_payload") or {}
                scene = (director.get("scene") or {}) if isinstance(director, dict) else {}
                if scene.get("description"):
                    console.print(scene["description"])
                if scene.get("visualPrompt"):
                    console.print(f"[dim]{scene['visualPrompt'][:260]}[/dim]")
                if scene.get("styleInfluence"):
                    console.print(f"[dim]style={scene['styleInfluence'][:160]}[/dim]")
                if director.get("playback_instructions"):
                    pi = director["playback_instructions"]
                    console.print(f"[dim]playback={pi.get('level')} | route={pi.get('route')} | action={pi.get('action')}[/dim]")
                if scene.get("prosody"):
                    prosody = scene["prosody"]
                    console.print(
                        f"[dim]chaos={prosody.get('chaos',0):.2f} whimsy={prosody.get('whimsy',0):.2f} darkTone={prosody.get('darkTone',0):.2f} coherence={prosody.get('coherence',0):.2f} voiceWeight={prosody.get('voiceWeight',0):.2f}[/dim]"
                    )
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
        elif cmd.startswith("/blueprint "):
            from openjarvis.cli._oracle_speak import _consult_worker, _ensure_voice_router, get_emotional_input
            from openjarvis.cli.blueprint_schema import build_agentic_instruction, action_from_router, constraints_for_action

            blueprint_query = user_input[len("/blueprint "):].strip()
            if not blueprint_query:
                console.print("[yellow]Usage: /blueprint <query|path>|train|voice|persona|learn|scene <query>[/yellow]")
                continue

            vision_data = None
            try:
                from openjarvis.vision import BlueprintEyes
                eyes = BlueprintEyes()
                candidate = Path(blueprint_query)
                if candidate.exists() and candidate.is_file():
                    raw = candidate.read_bytes()
                    width = height = 0
                    try:
                        from PIL import Image
                        import io
                        with Image.open(io.BytesIO(raw)) as img:
                            width, height = img.size
                            if img.mode != "RGBA":
                                img = img.convert("RGBA")
                            raw = img.tobytes()
                    except Exception:
                        width = height = 0
                    base64_image = __import__("base64").b64encode(raw).decode()
                    if width and height:
                        vision_data = eyes.parse(raw, width, height, base64_image)
            except Exception as exc:
                console.print(f"[dim]Blueprint vision skipped: {exc}[/dim]")

            try:
                consult = _consult_worker(
                    blueprint_query,
                    session_id="blueprint",
                    emotional_input=get_emotional_input(),
                    vision_data=vision_data,
                )
            except Exception as exc:
                console.print(f"[red]Blueprint consult failed: {exc}[/red]")
                continue

            if "error" in consult:
                console.print(f"[red]Blueprint consult error: {consult['error']}[/red]")
                continue

            router = _ensure_voice_router()
            router_eval = router.evaluate_advice(
                consult,
                user_direct_input=True,
                safety_ok=True,
                sensor_variance=abs(float(consult.get("consensus_vector", {}).get("voiceWeight", 0.5) or 0.5) - 0.5),
            ) if router else {
                "advice_hexagram": int(consult.get("consensus_hexagram_id") or 0),
                "voice_mode": "idle",
                "priority": 1,
                "hold_in_state": False,
                "deliberation": False,
                "fault_vector": 0,
                "crit_countdown": None,
                "reasoning": "router unavailable",
            }

            action_type = action_from_router(router_eval)
            constraints = constraints_for_action(action_type, router_eval)
            instruction = build_agentic_instruction(
                source_ingestion=f"cli://blueprint/{blueprint_query[:64]}",
                oracle_consensus={
                    "consensus_hexagram_id": consult.get("consensus_hexagram_id"),
                    "consensus_yao": consult.get("consensus_yao"),
                    "consensus_temporal": consult.get("consensus_temporal"),
                    "consensus_vector": consult.get("consensus_vector"),
                    "emotional_input": consult.get("emotional_input"),
                    "temporal_distribution": consult.get("temporal_distribution"),
                    "porosity_mean": consult.get("porosity_mean"),
                    "porosity_median": consult.get("porosity_median"),
                    "porosity_mode": consult.get("porosity_mode"),
                    "vectors_mean": consult.get("vectors_mean"),
                    "vectors_median": consult.get("vectors_median"),
                    "vectors_mode": consult.get("vectors_mode"),
                    "primary_pool_mode": consult.get("primary_pool_mode"),
                    "secondary_pool_mode": consult.get("secondary_pool_mode"),
                    "direction_mode": consult.get("direction_mode"),
                    "yao_label_mode": consult.get("yao_label_mode"),
                    "past_mode": consult.get("past_mode"),
                    "present_mode": consult.get("present_mode"),
                    "future_mode": consult.get("future_mode"),
                    "reasons": consult.get("reasons"),
                },
                router_evaluation=router_eval,
                agentic_action={
                    "type": action_type,
                    "tool": "kingwen_oracle_worker",
                    "parameters": {
                        "query": blueprint_query,
                        "rag_context": True,
                        "voice_output": False,
                    },
                    "constraints": constraints,
                },
                scene_generation=vision_data.get("scene_facts") if vision_data else None,
            )
        elif cmd.startswith("/blueprint wiki-math-parser "):
            from pathlib import Path
            import sys as _sys
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            target = user_input[len("/blueprint wiki-math-parser "):].strip()
            if not target:
                console.print("[yellow]Usage: /blueprint wiki-math-parser <source_or_wikitext_path>[/yellow]")
                continue

            source_text = ""
            source_kind = "text"
            candidate = Path(target)
            if candidate.exists() and candidate.is_file():
                source_text = candidate.read_text(encoding="utf-8", errors="ignore")
                source_kind = f"file:{candidate}"
            else:
                source_text = target
                source_kind = "text"

            mw_available = False
            math_nodes: list[str] = []
            headings: list[str] = []
            links: list[str] = []
            comments: list[str] = []
            try:
                mw_path = r"C:\Users\krist\Desktop\mwparserfromhell_local"
                if mw_path not in _sys.path:
                    _sys.path.insert(0, mw_path)
                from mwparserfromhell import parse as mw_parse
                mw_available = True
                code = mw_parse(source_text)
                headings = [str(n).strip() for n in code.ifilter_headings(recursive=True)][:20]
                links = [str(n).strip() for n in code.ifilter_external_links(recursive=True)][:20]
                comments = [str(n).strip() for n in code.ifilter_comments(recursive=True)][:20]
                math_nodes = [
                    str(n)
                    for n in code.ifilter(
                        matches=lambda n: hasattr(n, "tag") and str(getattr(n, "tag", "")).lower() in {"math", "ce", "chem", "sub", "sup"}
                    )
                ][:20]
            except Exception as exc:
                console.print(f"[dim]wiki-math parser unavailable: {exc}[/dim]")

            instruction = build_agentic_instruction(
                source_ingestion=f"wiki-math://{source_kind}",
                oracle_consensus={},
                router_evaluation={
                    "advice_hexagram": 0,
                    "voice_mode": "idle",
                    "priority": 1,
                    "hold_in_state": False,
                    "deliberation": False,
                    "fault_vector": 0,
                    "crit_countdown": None,
                    "reasoning": "wiki-math parse artifact",
                },
                agentic_action={
                    "type": "consult_and_respond",
                    "tool": "wiki_math_parser",
                    "parameters": {
                        "source_kind": source_kind,
                        "parser_backend": "mwparserfromhell" if mw_available else "unavailable",
                    },
                    "constraints": {"fabrication_policy": "PROHIBITED", "allow_tool_use": False},
                },
                scene_generation=None,
            )
            payload = {
                **instruction,
                "wiki_math": {
                    "headings": headings,
                    "links": links,
                    "comments": comments,
                    "math_nodes": math_nodes,
                    "math_node_count": len(math_nodes),
                    "source_chars": len(source_text),
                },
            }
            console.print_json(payload)
            continue
        elif cmd.startswith("/blueprint train "):
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            train_query = user_input[len("/blueprint train "):].strip() or "collapse_full_128 emotional sweep"
            kingwen_root = Path(r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES")
            megatron_root = Path(r"C:\Users\krist\Desktop\Megatron-LM-review\kingwen_train_data")

            discovered = []
            for rel in [
                "collapse_full_128_output.json",
                "learn/exports/capture_detailed.json",
                "kingwen_pretrain.jsonl",
                "combined_pretrain_train.jsonl",
                "domain_smoke/kingwen_smoke.jsonl",
                "model/jarvis-native-kingwen-life/manifest.json",
            ]:
                p = kingwen_root / rel
                if not p.exists():
                    p = megatron_root / rel
                if p.exists():
                    discovered.append(str(p))

            instruction = build_agentic_instruction(
                source_ingestion=f"megatron://train/{train_query[:64]}",
                oracle_consensus={},
                router_evaluation={
                    "advice_hexagram": 0,
                    "voice_mode": "idle",
                    "priority": 1,
                    "hold_in_state": False,
                    "deliberation": False,
                    "fault_vector": 0,
                    "crit_countdown": None,
                    "reasoning": "megatron training artifact route",
                },
                agentic_action={
                    "type": "consult_and_respond",
                    "tool": "megatron_training_surface",
                    "parameters": {
                        "query": train_query,
                        "kingwen_root": str(kingwen_root),
                        "megatron_root": str(megatron_root),
                    },
                    "constraints": {"fabrication_policy": "PROHIBITED", "allow_tool_use": False},
                },
                scene_generation=None,
            )
            console.print_json({**instruction, "training_artifacts": discovered})
            continue
        elif cmd.startswith("/blueprint voice "):
            from openjarvis.cli._oracle_speak import _tts_worker_with_vector, _dominant_axis, _extract_vector
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            payload = user_input[len("/blueprint voice "):].strip()
            if not payload:
                console.print("[yellow]Usage: /blueprint voice <text>|<emotional_input> <text>[/yellow]")
                continue

            emotional_input = 50
            text = payload
            try:
                maybe_n, rest = payload.split(" ", 1)
                emotional_input = max(0, min(100, int(maybe_n)))
                text = rest
            except ValueError:
                text = payload

            vector = {
                "voiceWeight": 0.6,
                "coherence": 0.7,
                "chaos": 0.2,
                "whimsy": 0.25,
                "darkTone": 0.05,
            }
            try:
                consult = __import__("openjarvis.cli._oracle_speak", fromlist=["_consult_worker"])._consult_worker(
                    text, session_id="blueprint-voice", emotional_input=emotional_input
                )
                vector = _extract_vector(consult) or vector
            except Exception:
                pass

            try:
                audio, headers = _tts_worker_with_vector(
                    text,
                    vector,
                    porosity=float(vector.get("coherence", 0.7)),
                    trajectory="still",
                    agree_temporal="present",
                    session_id="blueprint-voice",
                )
                instruction = build_agentic_instruction(
                    source_ingestion="voice://blueprint-voice",
                    oracle_consensus={},
                    router_evaluation={
                        "advice_hexagram": 0,
                        "voice_mode": "idle",
                        "priority": 1,
                        "hold_in_state": False,
                        "deliberation": False,
                        "fault_vector": 0,
                        "crit_countdown": None,
                        "reasoning": "kingwen-emotion-voice synthesis",
                    },
                    agentic_action={
                        "type": "consult_and_respond",
                        "tool": "kingwen_worker_tts",
                        "parameters": {"text": text, "emotional_input": emotional_input},
                        "constraints": {"fabrication_policy": "PROHIBITED", "allow_tool_use": False},
                    },
                    scene_generation=None,
                )
                console.print_json({**instruction, "backend": "kingwen-worker-tts", "bytes": len(audio), "headers": headers})
            except Exception as exc:
                console.print(f"[red]blueprint voice failed: {exc}[/red]")
            continue
        elif cmd.startswith("/blueprint persona"):
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            soul = Path.home() / ".openjarvis" / "SOUL.md"
            memory = Path.home() / ".openjarvis" / "MEMORY.md"
            user = Path.home() / ".openjarvis" / "USER.md"
            persona = {
                "soul_path": str(soul),
                "soul_exists": soul.exists(),
                "memory_path": str(memory),
                "memory_exists": memory.exists(),
                "user_path": str(user),
                "user_exists": user.exists(),
            }
            if soul.exists():
                persona["soul_preview"] = soul.read_text(encoding="utf-8", errors="ignore")[:900]
            instruction = build_agentic_instruction(
                source_ingestion="persona://openjarvis",
                oracle_consensus={},
                router_evaluation={
                    "advice_hexagram": 0,
                    "voice_mode": "idle",
                    "priority": 1,
                    "hold_in_state": False,
                    "deliberation": False,
                    "fault_vector": 0,
                    "crit_countdown": None,
                    "reasoning": "openjarvis-persona-harness audit",
                },
                agentic_action={
                    "type": "consult_and_respond",
                    "tool": "openjarvis_persona_harness",
                    "parameters": persona,
                    "constraints": {"fabrication_policy": "PROHIBITED", "allow_tool_use": False},
                },
                scene_generation=None,
            )
            console.print_json(instruction)
            continue
        elif cmd.startswith("/blueprint integration"):
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            root = Path(r"C:\Users\krist\Desktop\OpenJarvis")
            kingwen_root = Path(r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES")
            candidate_paths = [
                root / "src/openjarvis/emotion/kingwen.py",
                root / "src/openjarvis/cli/_oracle_speak.py",
                root / "src/openjarvis/cli/audio_dsp.py",
                root / "src/openjarvis/bridge_servers/desktop_execution.py",
                root / "src/openjarvis/cli/chat_cmd.py",
                root / "src/openjarvis/prompt/builder.py",
                root / "king_wen_codebasemap.md",
                kingwen_root / "emotional_engine.py",
                kingwen_root / "expand_server.py",
            ]
            surfaces = []
            for p in candidate_paths:
                surfaces.append({"path": str(p), "exists": p.exists(), "size": p.stat().st_size if p.exists() else 0})

            instruction = build_agentic_instruction(
                source_ingestion="integration://openjarvis-kingwen",
                oracle_consensus={},
                router_evaluation={
                    "advice_hexagram": 0,
                    "voice_mode": "idle",
                    "priority": 1,
                    "hold_in_state": False,
                    "deliberation": False,
                    "fault_vector": 0,
                    "crit_countdown": None,
                    "reasoning": "openjarvis-kingwen-integration audit",
                },
                agentic_action={
                    "type": "consult_and_respond",
                    "tool": "openjarvis_kingwen_integration_audit",
                    "parameters": {"surfaces": surfaces},
                    "constraints": {"fabrication_policy": "PROHIBITED", "allow_tool_use": False},
                },
                scene_generation=None,
            )
            console.print_json(instruction)
            continue
        elif cmd.startswith("/blueprint learn"):
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            ledgers = [
                r"C:\Users\krist\AppData\Local\hermes\cache\session-artifact-ledger.jsonl",
                r"C:\Users\krist\AppData\Local\hermes\cache\session-cluster-seeds.jsonl",
                r"C:\Users\krist\AppData\Local\hermes\cache\learn-extracts.jsonl",
            ]
            stats = []
            for p in ledgers:
                path = Path(p)
                stats.append({"path": p, "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0})

            instruction = build_agentic_instruction(
                source_ingestion="learn://hermes/ledger",
                oracle_consensus={},
                router_evaluation={
                    "advice_hexagram": 0,
                    "voice_mode": "idle",
                    "priority": 1,
                    "hold_in_state": False,
                    "deliberation": False,
                    "fault_vector": 0,
                    "crit_countdown": None,
                    "reasoning": "hermes-learn artifact summary",
                },
                agentic_action={
                    "type": "consult_and_respond",
                    "tool": "hermes_learn_ledger",
                    "parameters": {"ledger_paths": ledgers},
                    "constraints": {"fabrication_policy": "PROHIBITED", "allow_tool_use": False},
                },
                scene_generation=None,
            )
            console.print_json({**instruction, "ledger_stats": stats})
            continue
        elif cmd.startswith("/learn"):
            from openjarvis.cli.blueprint_schema import build_agentic_instruction

            argv = user_input.split(" ")[1:]
            sub = argv[0].lower() if argv else "status"

            cache_dir = Path.home() / "AppData" / "Local" / "hermes" / "cache"
            learn_base = Path.home() / ".openjarvis" / "learning"
            ledgers = {
                "ledger": cache_dir / "session-artifact-ledger.jsonl",
                "seeds": cache_dir / "session-cluster-seeds.jsonl",
                "extracts": cache_dir / "learn-extracts.jsonl",
                "learn_ingest": learn_base / "learn-ingest.jsonl",
            }
            stats = {k: {"exists": p.exists(), "size": p.stat().st_size if p.exists() else 0} for k, p in ledgers.items()}

            if sub == "status":
                console.print_json({
                    "command": "/learn status",
                    "artifacts": stats,
                    "cache_dir": str(cache_dir),
                    "learn_base": str(learn_base),
                })
                continue

            if sub == "run":
                agent_id = argv[1] if len(argv) > 1 else None
                try:
                    from openjarvis.learning.learning_orchestrator import LearningOrchestrator
                    from openjarvis.analytics.trace_store import TraceStore

                    trace_store = TraceStore()
                    orchestrator = LearningOrchestrator(
                        trace_store=trace_store,
                        config_dir=Path.home() / ".openjarvis" / "learning",
                    )
                    result = orchestrator.run(agent_id=agent_id)
                    pseudopod_ingest = ""
                    try:
                        from openjarvis.learning.kingwen_pseudopod_ingest import KingWenPseudopodIngestor
                        pseudopod_ingest = str(
                            KingWenPseudopodIngestor(trace_store).ingest_traces(limit=200)
                        )
                    except Exception:
                        pass
                    console.print_json({
                        "command": "/learn run",
                        "agent_id": agent_id,
                        "result": result,
                        "learn_artifacts": stats,
                        "pseudopod_ingest": pseudopod_ingest,
                    })
                except Exception as exc:
                    console.print(f"[red]learn run failed: {exc}[/red]")
                continue

            if sub == "ingests":
                ingest_path = ledgers["learn_ingest"]
                items = []
                if ingest_path.exists():
                    for line in ingest_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            items.append(json.loads(line))
                        except Exception:
                            pass
                console.print_json({
                    "command": "/learn ingests",
                    "path": str(ingest_path),
                    "count": len(items),
                    "items": items,
                })
                continue

            console.print("[yellow]/learn status|run [agent_id]|ingests|ingest[/yellow]")
            continue
        elif cmd.startswith("/learn ingest"):
            from openjarvis.learning.kingwen_pseudopod_ingest import KingWenPseudopodIngestor
            from openjarvis.traces.store import TraceStore

            try:
                store = TraceStore()
                ing = KingWenPseudopodIngestor(store)
                path = ing.ingest_traces(limit=200)
                payload = {
                    "command": "/learn ingest",
                    "path": str(path),
                    "rows": ing.rows_written,
                }
                try:
                    from openjarvis.core.session_clock_bridge import tag_payload

                    payload = tag_payload(
                        payload,
                        session_id=getattr(store, "session_id", "learn"),
                        phase="learn",
                        event="ingest",
                    )
                except Exception:
                    pass
                console.print_json(payload)
            except Exception as exc:
                console.print(f"[red]/learn ingest failed: {exc}[/red]")
            continue
        elif cmd.startswith("/blueprint"):
            import shlex

            try:
                tokens = shlex.split(user_input)[1:] if user_input else []
            except ValueError:
                tokens = (user_input or "").split()[1:]
            args = " ".join(shlex.quote(t) for t in tokens)
            try:
                from openjarvis.cli.blueprint_cmd import handle_blueprint_command

                result = handle_blueprint_command(args)
            except Exception as exc:
                console.print(f"[red]blueprint failed: {exc}[/red]")
                continue
            console.print(result.text)
            seed = getattr(result, "agent_seed", None)
            if seed:
                console.print_json({"agent_seed": seed})
            continue
        elif cmd == "/agents":
            try:
                from openjarvis.tools.process_registry import process_registry, format_uptime_short

                processes = process_registry.list_sessions()
                running = [p for p in processes if p.get("status") == "running"]
                finished = [p for p in processes if p.get("status") != "running"]

                console.print(f"[bold]Running processes:[/bold] {len(running)}")
                for p in running:
                    cmd_text = p.get("command", "")[:80]
                    up = format_uptime_short(p.get("uptime_seconds", 0))
                    console.print(f"    {p.get('session_id', '?')} · {up} · {cmd_text}")

                if finished:
                    console.print(f"[bold]Recently finished:[/bold] {len(finished)}")

                try:
                    from openjarvis.tools.async_delegation import list_async_delegations

                    delegations = list_async_delegations()
                    running_d = [d for d in delegations if d.get("status") == "running"]
                    if delegations:
                        console.print(
                            f"[bold]Background delegations:[/bold] {len(running_d)} running"
                        )
                        for d in delegations:
                            goal = (d.get("goal") or "")[:60]
                            console.print(
                                f"    {d.get('delegation_id', '?')} · "
                                f"{d.get('status', '?')} · {goal}"
                            )
                except Exception:
                    pass

                agent_running = getattr(agent, "_agent_running", False)
                console.print(
                    f"[bold]Agent:[/bold] {'running' if agent_running else 'idle'}"
                )
            except Exception as exc:
                console.print(f"[red]agents lookup failed: {exc}[/red]")
            continue
        elif cmd.startswith("/journey"):
            from openjarvis.core.journey_executor import JourneyExecutor

            exe = JourneyExecutor()
            argv = user_input.split(" ")[1:]
            if not argv:
                console.print(
                    "[dim]Usage: /journey lookup <query> [--autotag t1,t2] | replay <session_id> | weave --from <id> --to <id> | consult <query> | leaderboard[/dim]"
                )
                continue

            sub = argv[0].lower()
            if sub == "lookup":
                query_parts: list[str] = []
                autotags: list[str] | None = None
                i = 1
                while i < len(argv):
                    if argv[i] == "--autotag":
                        autotags = argv[i + 1].split(",") if i + 1 < len(argv) else []
                        i += 2
                    else:
                        query_parts.append(argv[i])
                        i += 1
                query = " ".join(query_parts).strip("\"'")
                if not query:
                    console.print("[yellow]Usage: /journey lookup <query> [--autotag t1,t2][/yellow]")
                    continue
                try:
                    matches = exe.lookup(query, autotags)
                except Exception as exc:
                    console.print(f"[red]Journey lookup failed: {exc}[/red]")
                    continue
                console.print(f"[bold magenta]Journey Lookup[/bold magenta]: `{query}`")
                console.print(f"Matches: {len(matches)}  |  Autotags: {autotags or 'none'}")
                for idx, m in enumerate(matches[:6], 1):
                    console.print(
                        f"{idx}. `[{m.session_id}]` score={m.score:.2f} weight={m.synaptic_weight:.2f}"
                    )
                    console.print(f"    intent: {m.intent[:90]}...")
                    console.print(f"    cluster: {', '.join(m.cluster[:6])}")
                if len(matches) > 0 and any(m.related_sessions for m in matches):
                    console.print(
                        f"[dim]*Novel edges queued for `/learn` ingest: {sum(len(m.related_sessions) for m in matches)}*[/dim]"
                    )
                continue

            if sub == "replay":
                if len(argv) < 2:
                    console.print("[yellow]Usage: /journey replay <session_id>[/yellow]")
                    continue
                try:
                    dump = exe.replay(argv[1])
                except Exception as exc:
                    console.print(f"[red]Journey replay failed: {exc}[/red]")
                    continue
                intent = str(dump.get("intent", "N/A"))[:100]
                console.print(f"[bold magenta]Replay hydrated[/bold magenta]: `{argv[1]}`")
                console.print(f"Intent: {intent}...")
                continue

            if sub == "weave":
                from_id = None
                to_id = None
                i = 1
                while i < len(argv):
                    if argv[i] == "--from" and i + 1 < len(argv):
                        from_id = argv[i + 1]
                        i += 2
                    elif argv[i] == "--to" and i + 1 < len(argv):
                        to_id = argv[i + 1]
                        i += 2
                    else:
                        i += 1
                if not from_id or not to_id:
                    console.print("[yellow]Usage: /journey weave --from <id> --to <id>[/yellow]")
                    continue
                try:
                    path = exe.weave(from_id, to_id)
                except Exception as exc:
                    console.print(f"[red]Journey weave failed: {exc}[/red]")
                    continue
                nodes = path.get("nodes", []) if isinstance(path, dict) else []
                console.print(f"[bold magenta]Weave Path[/bold magenta]: `{from_id}` → `{to_id}`")
                console.print(f"Nodes: {len(nodes)}")
                for n in nodes[:10]:
                    console.print(f"  → {n}")
                continue

            if sub == "consult":
                query_parts = []
                i = 1
                while i < len(argv):
                    if argv[i] == "--emotional-input" and i + 1 < len(argv):
                        try:
                            emotional_input = int(argv[i + 1])
                        except (TypeError, ValueError):
                            emotional_input = 50
                        i += 2
                        continue
                    query_parts.append(argv[i])
                    i += 1
                query = " ".join(query_parts).strip("\"'")
                if not query:
                    console.print("[yellow]Usage: /journey consult <query> [--emotional-input 0..100][/yellow]")
                    continue
                try:
                    payload = exe.consult(query, emotional_input=emotional_input)
                except Exception as exc:
                    console.print(f"[red]Journey consult failed: {exc}[/red]")
                    continue
                console.print_json(payload)
                continue

            if sub == "leaderboard":
                try:
                    tables_root = Path.home() / "Desktop" / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
                    out_path = tables_root / "collapse_full_128_output.json"
                    if not out_path.exists():
                        console.print("[yellow]collapse_full_128_output.json not found.[/yellow]")
                        continue
                    payload = json.loads(out_path.read_text(encoding="utf-8"))
                    resolved = payload.get("resolved") or []
                    consensus = payload.get("consensus") or {}
                    by_hex: Dict[int, List[Dict[str, Any]]] = {}
                    for item in resolved:
                        h_id = int(item.get("hexagram_id") or 0)
                        if not h_id:
                            continue
                        by_hex.setdefault(h_id, []).append(item)
                    rows = []
                    for h_id, items in by_hex.items():
                        vectors = []
                        for item in items:
                            rv = item.get("resolved_vector") or {}
                            vectors.append([float(rv.get(k, 0.0) or 0.0) for k in ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]])
                        mean = [sum(v[i] for v in vectors) / max(1, len(vectors)) for i in range(5)]
                        rows.append({
                            "hexagram_id": h_id,
                            "count": len(items),
                            "mean_vector": {
                                "chaos": mean[0],
                                "whimsy": mean[1],
                                "darkTone": mean[2],
                                "coherence": mean[3],
                                "voiceWeight": mean[4],
                            },
                        })
                    rows.sort(key=lambda r: (-r["count"], -(r["mean_vector"].get("voiceWeight") or 0.0), r["hexagram_id"]))
                    console.print_json({
                        "command": "/journey leaderboard",
                        "source": str(out_path),
                        "emotional_input": payload.get("emotional_input"),
                        "total_resolved": payload.get("total_resolved"),
                        "consensus": consensus,
                        "leaderboard": rows[:12],
                    })
                except Exception as exc:
                    console.print(f"[red]/journey leaderboard failed: {exc}[/red]")
                continue

            console.print(f"[yellow]Unknown journey subcommand: `{sub}`[/yellow]")
            continue
        elif cmd.startswith("/journey leaderboard"):
            try:
                from pathlib import Path
                import json

                tables_root = Path.home() / "Desktop" / "KING-WEN-I-CHING-IMMUTABLE-TABLES"
                out_path = tables_root / "collapse_full_128_output.json"
                if not out_path.exists():
                    console.print("[yellow]collapse_full_128_output.json not found.[/yellow]")
                    continue
                payload = json.loads(out_path.read_text(encoding="utf-8"))
                resolved = payload.get("resolved") or []
                consensus = payload.get("consensus") or {}
                by_hex = {}
                for item in resolved:
                    h_id = int(item.get("hexagram_id") or 0)
                    if not h_id:
                        continue
                    by_hex.setdefault(h_id, []).append(item)
                rows = []
                for h_id, items in by_hex.items():
                    vectors = []
                    for item in items:
                        rv = item.get("resolved_vector") or {}
                        vectors.append([float(rv.get(k, 0.0) or 0.0) for k in ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]])
                    mean = [sum(v[i] for v in vectors) / max(1, len(vectors)) for i in range(5)]
                    rows.append({
                        "hexagram_id": h_id,
                        "count": len(items),
                        "mean_vector": {
                            "chaos": mean[0],
                            "whimsy": mean[1],
                            "darkTone": mean[2],
                            "coherence": mean[3],
                            "voiceWeight": mean[4],
                        },
                    })
                rows.sort(key=lambda r: (-r["count"], -(r["mean_vector"].get("voiceWeight") or 0.0), r["hexagram_id"]))
                console.print_json({
                    "command": "/journey leaderboard",
                    "source": str(out_path),
                    "emotional_input": payload.get("emotional_input"),
                    "total_resolved": payload.get("total_resolved"),
                    "consensus": consensus,
                    "leaderboard": rows[:12],
                })
            except Exception as exc:
                console.print(f"[red]/journey leaderboard failed: {exc}[/red]")
            continue
        elif cmd.startswith("/cron"):
            # /cron list | /cron pause <id> | /cron enable <id> | /cron disable <id> | /cron status <id>
            import json as _json
            from pathlib import Path as _Path
            _cron_jobs_path = _Path.home() / "AppData" / "Local" / "hermes" / "cron" / "jobs.json"
            _cron_argv = user_input.split()[1:]
            _cron_sub = _cron_argv[0].lower() if _cron_argv else "list"

            def _load_cron_jobs():
                if not _cron_jobs_path.exists():
                    return None, f"jobs.json not found: {_cron_jobs_path}"
                try:
                    data = _json.loads(_cron_jobs_path.read_text(encoding="utf-8"))
                    return data.get("jobs", []), None
                except Exception as exc:
                    return None, str(exc)

            def _save_cron_jobs(jobs):
                try:
                    _cron_jobs_path.write_text(
                        _json.dumps({"jobs": jobs}, indent=2, default=str),
                        encoding="utf-8",
                    )
                    return None
                except Exception as exc:
                    return str(exc)

            if _cron_sub == "list":
                jobs, err = _load_cron_jobs()
                if err:
                    console.print(f"[red]/cron: {err}[/red]")
                else:
                    console.print(f"[bold]Cron Jobs[/bold] ({len(jobs)} total, from {_cron_jobs_path.name})")
                    for j in jobs:
                        state_color = "green" if j.get("enabled") else "red"
                        sched = j.get("schedule_display") or j.get("schedule", {}).get("display", "?")
                        last_ok = j.get("last_status", "?") == "ok"
                        status_icon = "✓" if last_ok else "✗"
                        console.print(
                            f"  [{state_color}]{j['id'][:12]}[/{state_color}] "
                            f"[bold]{j.get('name', 'unnamed')[:40]}[/bold] "
                            f"sched=[cyan]{sched}[/cyan] "
                            f"state=[dim]{j.get('state','?')}[/dim] "
                            f"{status_icon}last={j.get('last_run_at', 'never')[:19]}"
                        )
            elif _cron_sub in ("status",) and len(_cron_argv) >= 2:
                _cron_id = _cron_argv[1]
                jobs, err = _load_cron_jobs()
                if err:
                    console.print(f"[red]/cron: {err}[/red]")
                else:
                    matched = [j for j in jobs if j["id"].startswith(_cron_id) or j.get("name", "").lower() == _cron_id.lower()]
                    if not matched:
                        console.print(f"[yellow]/cron: no job matching '{_cron_id}'[/yellow]")
                    else:
                        for j in matched:
                            console.print_json({
                                "id": j["id"],
                                "name": j.get("name"),
                                "enabled": j.get("enabled"),
                                "state": j.get("state"),
                                "schedule": j.get("schedule"),
                                "last_run_at": j.get("last_run_at"),
                                "next_run_at": j.get("next_run_at"),
                                "last_status": j.get("last_status"),
                                "last_error": j.get("last_error"),
                                "repeat": j.get("repeat"),
                                "enabled_toolsets": j.get("enabled_toolsets"),
                                "model_snapshot": j.get("model_snapshot"),
                            })
            elif _cron_sub in ("pause", "enable", "disable") and len(_cron_argv) >= 2:
                _cron_id = _cron_argv[1]
                jobs, err = _load_cron_jobs()
                if err:
                    console.print(f"[red]/cron: {err}[/red]")
                else:
                    matched_count = 0
                    for j in jobs:
                        if j["id"].startswith(_cron_id) or j.get("name", "").lower() == _cron_id.lower():
                            matched_count += 1
                            if _cron_sub == "pause":
                                import datetime as _dt
                                j["enabled"] = False
                                j["state"] = "paused"
                                j["paused_at"] = _dt.datetime.now().isoformat()
                                j["paused_reason"] = "jarvis /cron pause"
                            elif _cron_sub == "enable":
                                j["enabled"] = True
                                j["state"] = "scheduled"
                                j["paused_at"] = None
                                j["paused_reason"] = None
                            elif _cron_sub == "disable":
                                j["enabled"] = False
                                j["state"] = "disabled"
                    if matched_count == 0:
                        console.print(f"[yellow]/cron: no job matching '{_cron_id}'[/yellow]")
                    else:
                        save_err = _save_cron_jobs(jobs)
                        if save_err:
                            console.print(f"[red]/cron: failed to save: {save_err}[/red]")
                        else:
                            console.print(f"[green]/cron {_cron_sub}[/green]: updated {matched_count} job(s) matching '{_cron_id}'")
            else:
                console.print(
                    "[dim]Usage:\n"
                    "  /cron list               — list all jobs with state\n"
                    "  /cron status <id|name>   — full status for one job\n"
                    "  /cron pause <id|name>    — pause job (sets enabled=false, state=paused)\n"
                    "  /cron enable <id|name>   — re-enable paused/disabled job\n"
                    "  /cron disable <id|name>  — disable job permanently until re-enabled\n"
                    "[/dim]"
                )
            continue
        elif cmd.startswith("/tools"):
            # /tools list | /tools enable <name> | /tools disable <name> | /tools reset
            from openjarvis.core.registry import ToolRegistry
            _tools_argv = user_input.split()[1:]
            _tools_sub = _tools_argv[0].lower() if _tools_argv else "list"

            # Session-level disabled set lives on the registry instance
            if not hasattr(ToolRegistry, "_session_disabled"):
                ToolRegistry._session_disabled = set()

            if _tools_sub == "list":
                all_tools = list(ToolRegistry._registry.keys()) if hasattr(ToolRegistry, "_registry") else []
                if not all_tools:
                    console.print("[dim]No tools registered (registry empty).[/dim]")
                else:
                    console.print(f"[bold]Registered Tools[/bold] ({len(all_tools)})")
                    for name in sorted(all_tools):
                        disabled = name in ToolRegistry._session_disabled
                        tag = "[red]disabled[/red]" if disabled else "[green]enabled[/green]"
                        console.print(f"  {tag} {name}")
            elif _tools_sub == "disable" and len(_tools_argv) >= 2:
                _tool_name = _tools_argv[1]
                ToolRegistry._session_disabled.add(_tool_name)
                console.print(f"[yellow]Tool disabled for this session:[/yellow] {_tool_name}")
            elif _tools_sub == "enable" and len(_tools_argv) >= 2:
                _tool_name = _tools_argv[1]
                ToolRegistry._session_disabled.discard(_tool_name)
                console.print(f"[green]Tool re-enabled:[/green] {_tool_name}")
            elif _tools_sub == "reset":
                cleared = list(ToolRegistry._session_disabled)
                ToolRegistry._session_disabled.clear()
                console.print(f"[green]/tools reset:[/green] cleared {len(cleared)} session override(s): {cleared or 'none'}")
            else:
                console.print(
                    "[dim]Usage:\n"
                    "  /tools list            — show all registered tools with enabled/disabled state\n"
                    "  /tools enable <name>   — re-enable a tool disabled this session\n"
                    "  /tools disable <name>  — disable a tool for this session\n"
                    "  /tools reset           — clear all session-level tool overrides\n"
                    "[/dim]"
                )
            continue
        elif cmd.startswith("/memory"):
            # /memory list | /memory approve <id> | /memory reject <id> | /memory flush
            import json as _json
            from pathlib import Path as _Path
            _mem_argv = user_input.split()[1:]
            _mem_sub = _mem_argv[0].lower() if _mem_argv else "list"

            # Pending memory approval queue — stored in ~/.openjarvis/memory_approvals.jsonl
            _mem_queue_path = _Path.home() / ".openjarvis" / "memory_approvals.jsonl"

            def _load_pending_memories():
                if not _mem_queue_path.exists():
                    return []
                entries = []
                for line in _mem_queue_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(_json.loads(line))
                    except Exception:
                        pass
                return entries

            def _save_pending_memories(entries):
                _mem_queue_path.parent.mkdir(parents=True, exist_ok=True)
                _mem_queue_path.write_text(
                    "\n".join(_json.dumps(e, default=str) for e in entries),
                    encoding="utf-8",
                )

            def _commit_memory(entry):
                """Write an approved memory entry to the openjarvis memory store."""
                try:
                    from openjarvis.tools.memory_manage import MemoryManageTool
                    tool = MemoryManageTool()
                    result = tool.execute({
                        "action": "add",
                        "content": entry.get("content", ""),
                        "tags": entry.get("tags", []),
                        "source": entry.get("source", "memory_approval"),
                    })
                    return result.success, getattr(result, "content", str(result))
                except Exception as exc:
                    return False, str(exc)

            if _mem_sub == "list":
                pending = _load_pending_memories()
                if not pending:
                    console.print("[dim]No pending memory approvals.[/dim]")
                else:
                    console.print(f"[bold]Pending Memory Approvals[/bold] ({len(pending)})")
                    for i, entry in enumerate(pending):
                        m_id = entry.get("id", str(i))
                        tags = ", ".join(entry.get("tags", []))
                        content_preview = entry.get("content", "")[:120]
                        console.print(
                            f"  [cyan]{m_id}[/cyan] tags=[dim]{tags}[/dim]\n"
                            f"    {content_preview}"
                        )
            elif _mem_sub == "approve" and len(_mem_argv) >= 2:
                _mem_id = _mem_argv[1]
                pending = _load_pending_memories()
                to_commit = [e for e in pending if e.get("id", "").startswith(_mem_id)]
                remaining = [e for e in pending if not e.get("id", "").startswith(_mem_id)]
                if not to_commit:
                    console.print(f"[yellow]/memory: no pending entry matching '{_mem_id}'[/yellow]")
                else:
                    for entry in to_commit:
                        ok, msg = _commit_memory(entry)
                        if ok:
                            console.print(f"[green]Approved + committed:[/green] {entry.get('id')} — {msg[:80]}")
                        else:
                            console.print(f"[red]Commit failed:[/red] {entry.get('id')} — {msg}")
                    _save_pending_memories(remaining)
            elif _mem_sub == "reject" and len(_mem_argv) >= 2:
                _mem_id = _mem_argv[1]
                pending = _load_pending_memories()
                rejected = [e for e in pending if e.get("id", "").startswith(_mem_id)]
                remaining = [e for e in pending if not e.get("id", "").startswith(_mem_id)]
                if not rejected:
                    console.print(f"[yellow]/memory: no pending entry matching '{_mem_id}'[/yellow]")
                else:
                    _save_pending_memories(remaining)
                    console.print(f"[red]Rejected:[/red] {len(rejected)} entry(s) matching '{_mem_id}' — removed from queue")
            elif _mem_sub == "flush":
                pending = _load_pending_memories()
                _save_pending_memories([])
                console.print(f"[yellow]/memory flush:[/yellow] cleared {len(pending)} pending approval(s) without committing")
            elif _mem_sub == "queue":
                # Queue a new memory for approval: /memory queue <content...>
                content = " ".join(_mem_argv[1:]).strip()
                if not content:
                    console.print("[yellow]Usage: /memory queue <content>[/yellow]")
                else:
                    import uuid as _uuid, datetime as _dt
                    entry = {
                        "id": _uuid.uuid4().hex[:12],
                        "content": content,
                        "tags": [],
                        "source": "jarvis_cli",
                        "queued_at": _dt.datetime.now().isoformat(),
                        "status": "pending",
                    }
                    pending = _load_pending_memories()
                    pending.append(entry)
                    _save_pending_memories(pending)
                    console.print(f"[green]Queued for approval:[/green] {entry['id']} — use `/memory approve {entry['id']}` to commit")
            else:
                console.print(
                    "[dim]Usage:\n"
                    "  /memory list           — show pending approval queue\n"
                    "  /memory queue <text>   — add a memory entry pending approval\n"
                    "  /memory approve <id>   — approve + commit an entry to memory store\n"
                    "  /memory reject <id>    — reject + discard from queue\n"
                    "  /memory flush          — clear entire pending queue without committing\n"
                    "[/dim]"
                )
            continue
        elif cmd.startswith("/script"):
            # /script <type> <intent...> [--hex <1-64>] [--passes <n>] [--emotional <0-100>]
            _script_args = cmd[len("/script"):].strip()
            _script_tokens = _script_args.split()
            _script_type = _script_tokens[0] if _script_tokens else ""
            _valid_types = {
                "prose", "screenplay", "dialogue", "lyrics",
                "image_prompt", "code", "essay", "training_record", "gutenberg",
            }
            if not _script_type or _script_type not in _valid_types:
                console.print(
                    "[yellow]/script usage:[/yellow]\n"
                    "  /script <type> <intent...>\n"
                    "  types: prose screenplay dialogue lyrics image_prompt "
                    "code essay training_record gutenberg\n"
                    "  --hex <1-64>       force a specific hexagram\n"
                    "  --passes <n>       quantum expansion passes (default 3)\n"
                    "  --emotional <0-100>  emotional input seed\n"
                )
                continue
            # Parse optional flags
            _script_force_hex: int | None = None
            _script_passes: int = 3
            _script_emotional: int = 50
            _intent_tokens: list[str] = []
            _skip_next = False
            for _i, _tok in enumerate(_script_tokens[1:], start=1):
                if _skip_next:
                    _skip_next = False
                    continue
                if _tok == "--hex" and _i + 1 < len(_script_tokens):
                    try:
                        _script_force_hex = int(_script_tokens[_i + 1])
                    except ValueError:
                        pass
                    _skip_next = True
                elif _tok == "--passes" and _i + 1 < len(_script_tokens):
                    try:
                        _script_passes = max(1, int(_script_tokens[_i + 1]))
                    except ValueError:
                        pass
                    _skip_next = True
                elif _tok == "--emotional" and _i + 1 < len(_script_tokens):
                    try:
                        _script_emotional = max(0, min(100, int(_script_tokens[_i + 1])))
                    except ValueError:
                        pass
                    _skip_next = True
                else:
                    _intent_tokens.append(_tok)
            _script_intent = " ".join(_intent_tokens).strip()
            if not _script_intent:
                console.print("[yellow]/script: intent text is required after the type[/yellow]")
                continue
            try:
                from openjarvis.tools.kingwen_script_pipeline_tool import KingWenScriptPipelineTool

                _pipeline = KingWenScriptPipelineTool()
                with console.status(
                    f"[bold cyan]{_script_type}[/bold cyan] pipeline "
                    f"{'(hex ' + str(_script_force_hex) + ')' if _script_force_hex else '(quantum)'}…"
                ):
                    _script_result = _pipeline.run(
                        intent=_script_intent,
                        script_type=_script_type,
                        emotional_input=_script_emotional,
                        force_hex=_script_force_hex,
                        max_passes=_script_passes,
                    )
                if _script_result.success:
                    _smeta = _script_result.metadata or {}
                    console.print(
                        f"[bold]{_smeta.get('hexagram_symbol','')} "
                        f"{_smeta.get('hexagram_name','')}[/bold]  "
                        f"[dim]{_smeta.get('action','')}  ·  "
                        f"{_smeta.get('phase_temporal','')}  ·  "
                        f"{_script_type}  ·  {_smeta.get('elapsed_s','')}s[/dim]"
                    )
                    console.print(_script_result.content)
                else:
                    console.print(f"[red]{_script_result.content}[/red]")
            except Exception as _script_exc:
                console.print(f"[red]/script error: {_script_exc}[/red]")
            continue
        elif cmd.startswith("/background"):
            # /background <command...>
            _bg_cmd = cmd[len("/background"):].strip()
            if not _bg_cmd:
                console.print("[yellow]/background usage:[/yellow] /background <command...>")
                continue
            try:
                import random
                import subprocess
                import threading
                import os
                from openjarvis.tools.process_registry import process_registry
                from openjarvis.core.events import EventType

                # Generate a unique background task ID
                _bg_id = f"bg_{random.randint(1000, 9999)}"
                
                # Start process in background
                _proc = subprocess.Popen(
                    _bg_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=os.getcwd(),
                    text=True
                )
                
                # Register in shared process registry so /agents displays it
                process_registry.register_process(_bg_id, _bg_cmd, _proc.pid, os.getcwd())
                
                console.print(f"[green]Spawned background task:[/green] [bold]{_bg_id}[/bold] (PID {_proc.pid})")
                
                # Publish task start event
                bus.publish(
                    EventType.SCHEDULER_TASK_START,
                    {
                        "session_id": _bg_id,
                        "command": _bg_cmd,
                        "pid": _proc.pid,
                    }
                )

                def _wait_for_bg_task(p, bid, bcmd):
                    stdout, stderr = p.communicate()
                    process_registry.deregister_process(bid)
                    bus.publish(
                        EventType.SCHEDULER_TASK_END,
                        {
                            "session_id": bid,
                            "command": bcmd,
                            "exit_code": p.returncode,
                            "stdout": stdout[:1000] if stdout else "",
                            "stderr": stderr[:1000] if stderr else "",
                        }
                    )
                    console.log(f"\n[bold green]Background task {bid} finished[/bold green] (exit code {p.returncode}).")

                threading.Thread(
                    target=_wait_for_bg_task,
                    args=(_proc, _bg_id, _bg_cmd),
                    daemon=True
                ).start()

            except Exception as _bg_exc:
                console.print(f"[red]/background error: {_bg_exc}[/red]")
            continue
        elif cmd == "/rules":
            try:
                from pathlib import Path

                skills_dir = Path.home() / "AppData" / "Local" / "hermes" / "skills"
                scan_path = skills_dir / "rules" / "rules-skill-scan.txt"
                pattern = (
                    "(placeholder|stub|todo|mock|fake|invalid|minimal content|"
                    "wip|work-in-progress|no-op|pass-through|dummy)"
                )
                hits = []
                for skill_md in skills_dir.rglob("SKILL.md"):
                    try:
                        text = skill_md.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        continue
                    for lineno, line in enumerate(text.splitlines(), 1):
                        import re

                        if re.search(pattern, line, re.IGNORECASE):
                            hits.append({
                                "path": str(skill_md),
                                "line": lineno,
                                "match": line.strip(),
                            })
                payload = {
                    "command": "/rules",
                    "skill": "rules",
                    "scan_path": str(scan_path),
                    "skills_dir": str(skills_dir),
                    "violations_found": len(hits),
                    "violations": hits[:50],
                }
                console.print_json(payload)
            except Exception as exc:
                console.print(f"[red]/rules failed: {exc}[/red]")
            continue
        elif cmd.startswith("/task"):
            _task_raw = cmd[len("/task"):].strip()
            if not _task_raw:
                console.print(
                    "[yellow]/task usage:[/yellow]\n"
                    "  /task <goal> [key=value ...]\n"
                    "  Example: /task verify kingwen oracle and voice profile script_type=prose"
                )
                continue
            _task_tokens = _task_raw.split()
            _task_goal_parts: list[str] = []
            _task_context: dict[str, str] = {}
            _skip = False
            for _i, _tok in enumerate(_task_tokens):
                if _skip:
                    _skip = False
                    continue
                if "=" in _tok and _task_goal_parts:
                    _k, _, _v = _tok.partition("=")
                    _task_context[_k.strip()] = _v.strip()
                else:
                    _task_goal_parts.append(_tok)
            _task_goal = " ".join(_task_goal_parts).strip()
            if not _task_goal:
                console.print("[yellow]/task: goal text is required[/yellow]")
                continue
            try:
                from openjarvis.tools.task_engine import TaskEngineTool
                _engine = TaskEngineTool()
                with console.status(f"[bold cyan]Task Engine[/bold cyan] decomposing: {_task_goal[:60]}…"):
                    _task_result = _engine.run(goal=_task_goal, context=_task_context or None)
                if _task_result.success:
                    console.print(_task_result.content)
                else:
                    console.print(f"[red]{_task_result.content}[/red]")
            except Exception as _task_exc:
                console.print(f"[red]/task error: {_task_exc}[/red]")
            continue
        elif cmd == "/help":
            console.print(
                "[bold]Commands:[/bold]\n"
                "  /quit, /exit  — end session\n"
                "  /clear        — clear conversation\n"
                "  /model        — show active model\n"
                "  /models       — ModelRolodex: live Ollama + ternary router + CF workers\n"
                "  /history      — show conversation\n"
                "  /agents       — active processes, delegations, agent state\n"
                "  /blueprint <name> [slot=val] — Hermes automation catalog/seed/create\n"
                "  /oracle <q>   — consult King Wen, synthesize voice to file\n"
                "  /counsel <q>  — same as /oracle with PPF framing\n"
                "  /journey <sub> — lookup/replay/weave/consult/leaderboard\n"
                "  /learn status|run|ingests|ingest — learn/skill ingestion\n"
                "  /cron list|status|pause|enable|disable <id> — Hermes cron job management\n"
                "  /tools list|enable|disable|reset <name> — session tool registry control\n"
                "  /memory list|queue|approve|reject|flush — memory write approval gate\n"
                "  /script <type> <intent> [--hex N] [--passes N] [--emotional N]\n"
                "          types: prose screenplay dialogue lyrics image_prompt\n"
                "                 code essay training_record gutenberg\n"
                "  /background <command> — spawn a background task with event-bus completion\n"
                "  /rules        — load and enforce rules skill\n"
                "  /help         — this message\n"
                "\n"
                "[dim]Skills (load via Hermes skill system):[/dim]\n"
                "  wiki-math-parser | kingwen-jarvis-megatron-learn | kingwen-emotion-voice\n"
                "  learn | openjarvis-persona-harness | openjarvis-kingwen-integration"
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
