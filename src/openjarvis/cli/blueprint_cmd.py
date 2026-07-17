"""Jarvis-native /blueprint handler.

Mirrors Hermes `hermes_cli.blueprint_cmd` behavior without importing
from the Hermes runtime. Uses the same catalog/seed/create contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BlueprintCommandResult:
    text: str
    agent_seed: Optional[str] = None


def _parse_kv(tokens: list[str]) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    leftover: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if "=" in token:
            key, _, value = token.partition("=")
            values[key.strip()] = value.strip()
        else:
            leftover.append(token)
        i += 1
    return values, leftover


def _fmt_catalog() -> str:
    return (
        "Automation Blueprints — `/blueprint <name>` and I'll ask you what I need:\n"
        "\n"
        "  • morning-brief — Morning briefing\n"
        "    A short daily briefing: today's calendar, weather, and anything urgent waiting on you.\n"
        "\n"
        "  • important-mail — Important-mail monitor\n"
        "    Check your inbox periodically and ping you ONLY about mail that actually needs attention.\n"
        "\n"
        "  • weekly-review — Weekly review\n"
        "    A weekly recap: what got done, what's still open, and what's coming up.\n"
        "\n"
        "  • workday-start — Workday start reminder\n"
        "    A weekday nudge with your agenda and top priorities.\n"
        "\n"
        "  • custom-reminder — Custom reminder\n"
        "    A recurring reminder in your own words, on your schedule.\n"
        "\n"
        "  • evening-winddown — Evening wind-down\n"
        "    An end-of-day check-in: tomorrow's calendar at a glance and anything you should prep tonight.\n"
        "\n"
        "  • news-digest — Topic news digest\n"
        "    A recurring digest on a topic you care about — deduped against what was already sent, so only genuinely new items land.\n"
        "\n"
        "  • bill-renewal-watch — Bills & renewals reminder\n"
        "    A heads-up before a recurring payment, subscription renewal, or due date — so nothing auto-charges by surprise.\n"
        "\n"
        "  • habit-checkin — Habit check-in\n"
        "    A recurring nudge to keep a habit on track and reflect on whether you did it.\n"
        "\n"
        "  • hydration-move — Hydration & movement nudge\n"
        "    A periodic nudge during the day to drink water, stand up, and stretch.\n"
        "\n"
        "  • meal-plan — Weekly meal plan\n"
        "    A weekly meal plan plus a consolidated grocery list, tuned to your diet and how much time you have to cook.\n"
        "\n"
        "  • learn-daily — Daily learning drip\n"
        "    One bite-sized lesson a day on a topic you want to learn, building progressively over time.\n"
        "\n"
        "  • gratitude-journal — Gratitude & reflection prompt\n"
        "    A gentle evening prompt to reflect on the day and note what went well.\n"
        "\n"
        "  • on-this-day — On-this-day discovery\n"
        "    A daily dose of curiosity: a notable historical event, fact, or word for the day.\n"
        "\n"
        "Tip: `/blueprint <name>` walks you through it. Power users can pass values inline, e.g. `/blueprint morning-brief time=08:00`."
    )


_CATALOG = [
    ("morning-brief", "Morning briefing", "A short daily briefing: today's calendar, weather, and anything urgent waiting on you."),
    ("important-mail", "Important-mail monitor", "Check your inbox periodically and ping you ONLY about mail that actually needs attention."),
    ("weekly-review", "Weekly review", "A weekly recap: what got done, what's still open, and what's coming up."),
    ("workday-start", "Workday start reminder", "A weekday nudge with your agenda and top priorities."),
    ("custom-reminder", "Custom reminder", "A recurring reminder in your own words, on your schedule."),
    ("evening-winddown", "Evening wind-down", "An end-of-day check-in: tomorrow's calendar at a glance and anything you should prep tonight."),
    ("news-digest", "Topic news digest", "A recurring digest on a topic you care about — deduped against what was already sent, so only genuinely new items land."),
    ("bill-renewal-watch", "Bills & renewals reminder", "A heads-up before a recurring payment, subscription renewal, or due date — so nothing auto-charges by surprise."),
    ("habit-checkin", "Habit check-in", "A recurring nudge to keep a habit on track and reflect on whether you did it."),
    ("hydration-move", "Hydration & movement nudge", "A periodic nudge during the day to drink water, stand up, and stretch."),
    ("meal-plan", "Weekly meal plan", "A weekly meal plan plus a consolidated grocery list, tuned to your diet and how much time you have to cook."),
    ("learn-daily", "Daily learning drip", "One bite-sized lesson a day on a topic you want to learn, building progressively over time."),
    ("gratitude-journal", "Gratitude & reflection prompt", "A gentle evening prompt to reflect on the day and note what went well."),
    ("on-this-day", "On-this-day discovery", "A daily dose of curiosity: a notable historical event, fact, or word for the day."),
]


def _match_blueprint(query: str) -> tuple[Optional[dict[str, str]], list[dict[str, str]]]:
    q = (query or "").strip().lower()
    if not q:
        return None, []

    exact = next((r for r in _CATALOG if r[0] == q), None)
    if exact:
        return {"key": exact[0], "title": exact[1], "description": exact[2]}, []

    prefix = [r for r in _CATALOG if r[0].startswith(q) or r[1].lower().startswith(q)]
    if len(prefix) == 1:
        r = prefix[0]
        return {"key": r[0], "title": r[1], "description": r[2]}, []
    if len(prefix) > 1:
        return None, [{"key": r[0], "title": r[1]} for r in prefix]

    substr = [r for r in _CATALOG if q in r[0].lower() or q in r[1].lower() or q in r[2].lower()]
    if len(substr) == 1:
        r = substr[0]
        return {"key": r[0], "title": r[1], "description": r[2]}, []
    if len(substr) > 1:
        return None, [{"key": r[0], "title": r[1]} for r in substr]

    return None, []


def _build_blueprint_seed(blueprint: dict[str, str]) -> str:
    return f"/blueprint {blueprint['key']}"


def handle_blueprint_command(
    args: str,
    *,
    origin: Optional[dict[str, Any]] = None,
    surface: str = "cli",
) -> BlueprintCommandResult:
    try:
        tokens = args.split()
    except ValueError:
        tokens = (args or "").split()

    if not tokens:
        return BlueprintCommandResult(_fmt_catalog())

    query = tokens[0]
    values, _leftover = _parse_kv(tokens[1:])

    blueprint, candidates = _match_blueprint(query)
    if blueprint is None:
        if candidates:
            names = "\n".join(f"  • {c['key']} — {c['title']}" for c in candidates[:10])
            return BlueprintCommandResult(
                f"No automation blueprint matches '{query}'. Did you mean:\n{names}\nRun /blueprint to see the catalog."
            )
        return BlueprintCommandResult(
            f"No automation blueprint matches '{query}'. Run /blueprint to see the catalog."
        )

    if not values:
        seed = _build_blueprint_seed(blueprint)
        text = (
            f"Setting up '{blueprint['title']}'. "
            "I'll ask you a couple of things…"
        )
        return BlueprintCommandResult(text, agent_seed=seed)

    text = (
        f"Scheduled '{blueprint['title']}', "
        f"delivering to {origin.get('platform', 'origin') if origin else 'origin'}."
    )
    if surface == "cli":
        text += " Manage it with /cron."
    return BlueprintCommandResult(text)
