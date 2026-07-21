#!/usr/bin/env python3
"""Blueprint registry — canonical definitions for all Jarvis automation blueprints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class BlueprintDefinition:
    key: str
    title: str
    description: str
    actionable: bool = True
    default_schedule: str = "0 8 * * *"
    default_agent: str = "simple"
    default_tools: str = "web_search,file_write"
    required_inputs: List[str] = field(default_factory=list)
    output_artifact: str = "brief"
    execution_prompt: str = ""


_BUILTINS: List[BlueprintDefinition] = [
    BlueprintDefinition(
        key="morning-brief",
        title="Morning briefing",
        description="A short daily briefing: today's calendar, weather, and anything urgent waiting on you.",
        default_schedule="0 8 * * *",
        default_tools="web_search,file_read",
        output_artifact="brief",
        execution_prompt=(
            "Produce a concise morning brief with three sections: "
            "1) Today's calendar highlights from any local calendar files or web sources. "
            "2) Weather summary for the user's location. "
            "3) Urgent items flagged from recent communications or task stores. "
            "Write the brief to a markdown file and quote it."
        ),
    ),
    BlueprintDefinition(
        key="important-mail",
        title="Important-mail monitor",
        description="Check your inbox periodically and ping you ONLY about mail that actually needs attention.",
        default_schedule="0 10 * * *",
        default_tools="web_search,web_request",
        output_artifact="alert",
        execution_prompt=(
            "Check inbox via available mail connectors or web sources. "
            "Classify each message as needs_attention / informational / spam. "
            "Report ONLY needs_attention items with sender, subject, and reason. "
            "If none, report 'No urgent mail.'"
        ),
    ),
    BlueprintDefinition(
        key="weekly-review",
        title="Weekly review",
        description="A weekly recap: what got done, what's still open, and what's coming up.",
        default_schedule="0 18 * * 5",
        default_tools="file_read,file_write,web_search",
        output_artifact="report",
        execution_prompt=(
            "Compile a weekly review with three sections: "
            "1) Completed: items from task store marked done this week. "
            "2) Open: active tasks and blockers. "
            "3) Upcoming: next week's calendar and commitments. "
            "Write to a markdown file and quote it."
        ),
    ),
    BlueprintDefinition(
        key="workday-start",
        title="Workday start reminder",
        description="A weekday nudge with your agenda and top priorities.",
        default_schedule="0 9 * * 1-5",
        default_tools="file_read,web_search",
        output_artifact="nudge",
        execution_prompt=(
            "Produce a weekday start nudge: agenda from calendar sources, "
            "top 3 priorities from task store, and one-sentence encouragement. "
            "Keep it under 150 words."
        ),
    ),
    BlueprintDefinition(
        key="custom-reminder",
        title="Custom reminder",
        description="A recurring reminder in your own words, on your schedule.",
        default_schedule="0 12 * * *",
        default_tools="",
        output_artifact="reminder",
        execution_prompt="",
    ),
    BlueprintDefinition(
        key="evening-winddown",
        title="Evening wind-down",
        description="An end-of-day check-in: tomorrow's calendar at a glance and anything you should prep tonight.",
        default_schedule="0 21 * * *",
        default_tools="file_read,web_search",
        output_artifact="brief",
        execution_prompt=(
            "Produce an evening wind-down brief: tomorrow's calendar preview, "
            "any items to prep tonight, and a one-line reminder to disconnect. "
            "Write to markdown and quote it."
        ),
    ),
    BlueprintDefinition(
        key="news-digest",
        title="Topic news digest",
        description="A recurring digest on a topic you care about — deduped against what was already sent, so only genuinely new items land.",
        default_schedule="0 7 * * *",
        default_tools="web_search,file_read,file_write",
        output_artifact="digest",
        execution_prompt=(
            "Fetch recent web sources for the configured topic. "
            "Dedup against previously sent digests in the artifact store. "
            "Return 3-5 new items with source, title, summary, and relevance. "
            "Write the digest to a markdown file."
        ),
    ),
    BlueprintDefinition(
        key="bill-renewal-watch",
        title="Bills & renewals reminder",
        description="A heads-up before a recurring payment, subscription renewal, or due date — so nothing auto-charges by surprise.",
        default_schedule="0 10 * * 1",
        default_tools="file_read,file_write",
        output_artifact="alert",
        execution_prompt=(
            "Check local records for upcoming bills, subscriptions, and renewals. "
            "Report items due in the next 14 days with amount, date, and action needed. "
            "If no records exist, advise creating a billing ledger file."
        ),
    ),
    BlueprintDefinition(
        key="habit-checkin",
        title="Habit check-in",
        description="A recurring nudge to keep a habit on track and reflect on whether you did it.",
        default_schedule="0 20 * * *",
        default_tools="file_read,file_write",
        output_artifact="checkin",
        execution_prompt=(
            "Load the user's habit tracker file if it exists. "
            "Prompt reflection on today's habits: completed, missed, and reason. "
            "Update the tracker file with today's entries. "
            "Deliver a brief reflection summary."
        ),
    ),
    BlueprintDefinition(
        key="hydration-move",
        title="Hydration & movement nudge",
        description="A periodic nudge during the day to drink water, stand up, and stretch.",
        default_schedule="0 10,13,16 * * 1-5",
        default_tools="",
        output_artifact="nudge",
        execution_prompt="Deliver a short hydration/movement nudge: drink water, stand, stretch, breathe.",
    ),
    BlueprintDefinition(
        key="meal-plan",
        title="Weekly meal plan",
        description="A weekly meal plan plus a consolidated grocery list, tuned to your diet and how much time you have to cook.",
        default_schedule="0 18 * * 0",
        default_tools="web_search,file_write",
        output_artifact="plan",
        execution_prompt=(
            "Produce a weekly meal plan with dinner slots. "
            "Include a consolidated grocery list. "
            "Respect any dietary constraints from user config. "
            "Write to a markdown file and quote it."
        ),
    ),
    BlueprintDefinition(
        key="learn-daily",
        title="Daily learning drip",
        description="One bite-sized lesson a day on a topic you want to learn, building progressively over time.",
        default_schedule="0 7 * * *",
        default_tools="knowledge_search,file_write",
        output_artifact="lesson",
        execution_prompt=(
            "Produce one bite-sized lesson on the configured topic. "
            "Build on previous lessons if a learning log exists. "
            "Keep it under 200 words with one practice exercise. "
            "Append to the learning log file."
        ),
    ),
    BlueprintDefinition(
        key="gratitude-journal",
        title="Gratitude & reflection prompt",
        description="A gentle evening prompt to reflect on the day and note what went well.",
        default_schedule="0 21 * * *",
        default_tools="file_write",
        output_artifact="prompt",
        execution_prompt=(
            "Deliver a gentle evening gratitude prompt with three reflection questions. "
            "Append the prompt to a gratitude journal file if one exists."
        ),
    ),
    BlueprintDefinition(
        key="kingwen-state-of-being",
        title="King Wen state of being",
        description="Capture the full King Wen 64-hexagram expansion, record all 64 save-string slots, select dominant state from 512 resolved states, and inject back into the appropriate slot. Trigger import/inject tooling with trigram symbols and emotional consulting.",
        default_schedule="0 7,19 * * *",
        default_tools="",
        output_artifact="kingwen-state",
        execution_prompt=(
            "Run the King Wen full-expansion wire: "
            "1) Read current 64-slot save state. "
            "2) Call collapse_full_128() to get all 512 resolved states. "
            "3) Record the full expansion. "
            "4) Select dominant state from 512, not 3→1. "
            "5) Inject result back into the save-string slot. "
            "6) Report hexagram id, phase, domain, vectors, and transition tone. "
            "Include trigram symbols ☰☱☲☳☴☵☶☷ in the artifact."
        ),
    ),
    BlueprintDefinition(
        key="on-this-day",
        title="On-this-day discovery",
        description="A daily dose of curiosity: a notable historical event, fact, or word for the day.",
        default_schedule="0 8 * * *",
        default_tools="web_search,file_write",
        output_artifact="discovery",
        execution_prompt=(
            "Find one notable historical event or interesting fact for today's date. "
            "Keep it concise and surprising. "
            "Append to the discovery log file and deliver the item."
        ),
    ),
]


class BlueprintRegistry:
    """Canonical registry of all Jarvis automation blueprints."""

    def __init__(self) -> None:
        self._by_key: Dict[str, BlueprintDefinition] = {b.key: b for b in _BUILTINS}
        self._by_title: Dict[str, BlueprintDefinition] = {b.title.lower(): b for b in _BUILTINS}

    def get(self, key: str) -> Optional[BlueprintDefinition]:
        return self._by_key.get(key) or self._by_title.get(key.lower())

    def match(self, query: str) -> Optional[BlueprintDefinition]:
        q = (query or "").strip().lower()
        if not q:
            return None
        exact = self._by_key.get(q) or self._by_title.get(q.lower())
        if exact:
            return exact
        prefix = next((b for b in _BUILTINS if b.key.startswith(q) or b.title.lower().startswith(q)), None)
        if prefix:
            return prefix
        substr = next((b for b in _BUILTINS if q in b.key.lower() or q in b.title.lower()), None)
        return substr

    def all(self) -> List[BlueprintDefinition]:
        return list(_BUILTINS)

    def _match_blueprint_on_query(self, query: str) -> tuple[Optional[Dict[str, str]], list[Dict[str, str]]]:
        q = (query or "").strip().lower()
        if not q:
            return None, []

        exact = next((b for b in _BUILTINS if b.key == q or b.title.lower() == q), None)
        if exact:
            return {
                "key": exact.key,
                "title": exact.title,
                "description": exact.description,
                "default_schedule": exact.default_schedule,
                "default_agent": exact.default_agent,
                "default_tools": exact.default_tools,
                "output_artifact": exact.output_artifact,
                "execution_prompt": exact.execution_prompt,
            }, []

        prefix = [b for b in _BUILTINS if b.key.startswith(q) or b.title.lower().startswith(q)]
        if len(prefix) == 1:
            b = prefix[0]
            return {
                "key": b.key,
                "title": b.title,
                "description": b.description,
                "default_schedule": b.default_schedule,
                "default_agent": b.default_agent,
                "default_tools": b.default_tools,
                "output_artifact": b.output_artifact,
                "execution_prompt": b.execution_prompt,
            }, []
        if len(prefix) > 1:
            return None, [{"key": b.key, "title": b.title} for b in prefix]

        substr = [b for b in _BUILTINS if q in b.key.lower() or q in b.title.lower() or q in b.description.lower()]
        if len(substr) == 1:
            b = substr[0]
            return {
                "key": b.key,
                "title": b.title,
                "description": b.description,
                "default_schedule": b.default_schedule,
                "default_agent": b.default_agent,
                "default_tools": b.default_tools,
                "output_artifact": b.output_artifact,
                "execution_prompt": b.execution_prompt,
            }, []
        if len(substr) > 1:
            return None, [{"key": b.key, "title": b.title} for b in substr]

        return None, []


__all__ = ["BlueprintDefinition", "BlueprintRegistry", "_BUILTINS"]
