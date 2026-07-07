"""King Wen dashboard — debug probe, tool mediation, and state monitor.

Exposes the standalone debug tools as a dashboard panel:
- kingwen-probe.js data health check
- tmp_kingwen_tail_probe.py mediation/monitoring flow
- tmp_kingwen_debug_console.py turn-start tail
- verify_oracle_worker.py worker verification status

Usage:
    from openjarvis.cli.kingwen_dashboard import render_kingwen_dashboard
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _color(text: str, code: str) -> str:
    return f"[{code}]{text}[/{code}]"


def _bar(value: float, width: int = 10) -> str:
    filled = int(round(min(1.0, max(0.0, value)) * width))
    return "\u2588" * filled + "\u2591" * (width - filled)


def render_kingwen_dashboard(
    provider: Optional[Any] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Render King Wen dashboard cards.

    Args:
        provider: KingWenEmotionProvider instance, or None for offline mode.
        tool_calls: list of tool call dicts with 'name' key.
        tool_results: list of tool result dicts with 'tool_name' and 'success'.

    Returns:
        Formatted dashboard string for terminal output.
    """
    lines: List[str] = [
        "",
        _color("=== King Wen Debug Dashboard ===", "bold magenta"),
        "",
    ]

    # ── 1. Provider / workspace probe ───────────────────────────────────────
    probe: Dict[str, Any] = {
        "registry": False,
        "weights": False,
        "reflections": False,
        "kingwen_endpoint": False,
        "builder_endpoint": False,
        "operative_endpoint": False,
        "monitor_endpoint": False,
        "morning_endpoint": False,
        "config_endpoint": False,
    }
    counts: Optional[Dict[str, int]] = None
    samples: Dict[str, Any] = {}

    if provider is not None:
        try:
            probe["kingwen_endpoint"] = True
            counts = {
                "registry": len(getattr(provider, "_registry", {})),
                "weights": len(getattr(provider, "_weights", {})),
                "reflections": len(getattr(provider, "_reflections", {})),
            }
            probe["registry"] = counts["registry"] > 0
            probe["weights"] = counts["weights"] > 0
            probe["reflections"] = counts["reflections"] > 0
            samples = {
                "3": (provider._registry or {}).get("3"),
                "6": (provider._registry or {}).get("6"),
                "37": (provider._registry or {}).get("37"),
            }
        except Exception:
            pass

    status_style = lambda ok: "green" if ok else "red"
    lines.append(_color("Workspace Probe", "underline"))
    for key, ok in probe.items():
        lines.append(f"  {key}: [{status_style(ok)}]{ok}[/{status_style(ok)}]")
    if counts:
        lines.append(
            f"  counts: registry={counts['registry']}  "
            f"weights={counts['weights']}  reflections={counts['reflections']}"
        )
    if samples:
        lines.append(f"  sample hex 3: {samples.get('3')}")
        lines.append(f"  sample hex 6: {samples.get('6')}")
        lines.append(f"  sample hex 37: {samples.get('37')}")

    # ── 2. Turn-start tail ───────────────────────────────────────────────────
    if provider is not None and hasattr(provider, "consult"):
        try:
            payload = provider.consult(
                text="dashboard-probe",
                session_id="kingwen-dashboard",
                emotional_input=50,
            )
            hex_id = payload.get("hexagram_id")
            hex_name = payload.get("hexagram_name", "?")
            phase = payload.get("phase_temporal", "")
            tongue = payload.get("emotional_tongue") or {}
            deltas = payload.get("emotional_deltas") or {}
            vec = deltas or tongue.get("training_weight_vectors") or {}
            porosity = deltas.get("porosity") or tongue.get("porosity")
            action = payload.get("action", "")
            category = payload.get("category", "")
            reaction = (payload.get("reaction_frame") or "")[:160]

            lines.append("")
            lines.append(_color("Turn-start Tail", "underline"))
            lines.append(
                f"  hexagram: {hex_id} {hex_name}  phase={phase}  "
                f"action={action}  category={category}"
            )
            lines.append(f"  reaction: {reaction or '(none)'}")
            lines.append(f"  porosity: {porosity}")
            for axis in ("voiceWeight", "coherence", "chaos", "whimsy", "darkTone"):
                val = float(vec.get(axis, 0.0) or 0.0)
                lines.append(f"  {axis:<10} {val:.3f} {_bar(val)}")
        except Exception as exc:
            lines.append(f"  consult failed: {exc}")

    # ── 3. Tool mediation / monitoring ──────────────────────────────────────
    if tool_calls or tool_results:
        lines.append("")
        lines.append(_color("Tool Mediation / Monitoring", "underline"))

        if tool_calls:
            names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]
            lines.append(f"  proposed: {' -> '.join(names) or '(none)'}")

        if tool_results:
            successes = sum(1 for tr in tool_results if tr.get("success"))
            failures = len(tool_results) - successes
            lines.append(f"  outcomes : {successes} success, {failures} failure")
            for tr in tool_results:
                mark = "ok" if tr.get("success") else "fail"
                lines.append(
                    f"    {tr.get('tool_name', '?'):<16} [{mark}] "
                    f"{(tr.get('content') or '')[:80]}"
                )

    # ── 4. Worker verification ──────────────────────────────────────────────
    lines.append("")
    lines.append(_color("Worker Verification", "underline"))
    worker_url = "https://kingwen-oracle.kristain33rs.workers.dev"
    lines.append(f"  kingwen-oracle: {worker_url}")
    lines.append("  NOTE: verify_oracle_worker.py is standalone; run it for live /consult + /tts verification")

    return "\n".join(lines)


__all__ = ["render_kingwen_dashboard"]
