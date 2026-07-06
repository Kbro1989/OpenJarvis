"""Oracle dashboard — minimal interceptive renderer for the existing chat avatar.

Displays the live worker payload in terminal context:
  - hexagram, temporal, dominant axis
  - full voice vector with porosity
  - unified weave / text spoken
  - audio artifact path
  - backend metadata

No separate UI process. Just formatted output the existing REPL can print.
"""

from __future__ import annotations

from typing import Any, Dict


def _color(text: str, code: str) -> str:
    return f"[{code}]{text}[/{code}]"


def _format_vector(vector: Dict[str, float]) -> str:
    if not vector:
        return _color("none", "dim red")
    parts = []
    for k in ("voiceWeight", "coherence", "chaos", "whimsy", "darkTone"):
        v = vector.get(k, 0.0)
        bar = "\u2588" * int(round(v * 12))
        parts.append(f"  {k:<10} {v:.3f} {bar}")
    return "\n".join(parts)


def render(result: Dict[str, Any]) -> str:
    hexagram_id = result.get("hexagram_id") or 0
    hexagram_name = result.get("hexagram_name", "?")
    phase = result.get("phase_temporal", "")
    dominant = result.get("dominant_axis", "")
    agree = result.get("agree_temporal", "")
    trajectory = result.get("trajectory", "")
    text = result.get("text_spoken", "")
    backend = result.get("backend", "")
    audio_path = result.get("audio_path", "")
    error = result.get("error")
    voice_vector = result.get("voice_vector") or {}
    porosity = result.get("porosity")

    if error:
        return _color("Oracle voice failed: ", "red") + str(error)

    lines = [
        "",
        _color("\u2728 Oracle voice rendered", "bold cyan"),
        _color("hexagram", "dim") + f"  {hexagram_id} {hexagram_name}",
        _color("temporal", "dim") + f"  phase={phase}  agree={agree}",
        _color("trajectory", "dim") + f"  {trajectory}",
        _color("voice", "dim") + f"  backend={backend}",
        _color("dominant", "dim") + f"  {dominant}",
        _color("porosity", "dim") + f"  {porosity}",
        _color("vector", "dim") + "\n" + _format_vector(voice_vector),
        _color("audio", "dim") + f"  {audio_path}" if audio_path else "",
        _color("text", "dim") + f"  {text[:220]}",
        "",
    ]

    return "\n".join(line for line in lines if line is not None)


__all__ = ["render"]
