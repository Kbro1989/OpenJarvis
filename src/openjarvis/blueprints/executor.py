from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from openjarvis.blueprints.registry import BlueprintDefinition
from openjarvis.server.kingwen.kingwen_client_sync import KingwenClientSync


class BlueprintRunResult:
    def __init__(self, blueprint_key: str, status: str, path: str, summary: str) -> None:
        self.blueprint_key = blueprint_key
        self.status = status
        self.path = path
        self.summary = summary


class BlueprintExecutor:
    def __init__(self, store: Any) -> None:
        self.store = store

    def _header(self, definition: BlueprintDefinition) -> str:
        return (
            f"# Blueprint: {definition.title}\n\n"
            f"- Key: {definition.key}\n"
            f"- Kind: {definition.kind}\n"
            f"- Status: {definition.status.value}\n\n"
        )

    def _artifact_path(self, definition: BlueprintDefinition) -> Path:
        base = Path("artifacts") / definition.key
        base.parent.mkdir(parents=True, exist_ok=True)
        return base.with_suffix(".md")

    def execute(self, definition: BlueprintDefinition, values: Dict[str, Any]) -> BlueprintRunResult:
        values = values or {}
        artifact_path = self._artifact_path(definition)
        try:
            text = self._execute(definition, values, artifact_path)
            self.store.log_artifact(definition.key, status="success", path=str(artifact_path), summary=text[:240])
            return BlueprintRunResult(
                blueprint_key=definition.key,
                status="success",
                path=str(artifact_path),
                summary=text[:240],
            )
        except Exception as exc:
            self.store.log_artifact(definition.key, status="error", path=str(artifact_path), summary=str(exc))
            raise

    def _execute(
        self,
        definition: BlueprintDefinition,
        values: Dict[str, str],
        artifact_path: Path,
    ) -> str:
        key = definition.key
        if key == "daily-brief":
            return self._daily_brief(definition, values, artifact_path)
        if key == "on-this-day":
            return self._on_this_day(definition, values, artifact_path)
        if key == "kingwen-state-of-being":
            return self._kingwen_state_of_being(definition, values, artifact_path)

        return self._header(definition) + "## Unhandled blueprint\n\nNo executor wired for this key.\n"

    def _daily_brief(
        self,
        definition: BlueprintDefinition,
        values: Dict[str, str],
        artifact_path: Path,
    ) -> str:
        return self._header(definition) + "## Daily Brief\n\n- Notable item not yet wired to web source.\n- Discovery log will populate once web connector is configured.\n"

    def _on_this_day(
        self,
        definition: BlueprintDefinition,
        values: Dict[str, str],
        artifact_path: Path,
    ) -> str:
        return self._header(definition) + "## On this day\n\n- Notable item not yet wired to web source.\n- Discovery log will populate once web connector is configured.\n"

    def _kingwen_state_of_being(
        self,
        definition: BlueprintDefinition,
        values: Dict[str, str],
        artifact_path: Path,
    ) -> str:
        import json as _json
        from pathlib import Path as _Path
        from openjarvis.server.kingwen.kingwen_client_sync import KingwenClientSync

        session_id = values.get("session_id", "blueprint-kingwen-state")
        text = values.get("text") or values.get("query") or definition.title
        domain = values.get("domain") or "blueprint/state-of-being"
        tool = values.get("tool") or "/blueprint/kingwen-state-of-being"

        tables_root = _Path("C:/Users/krist/Desktop/KING-WEN-I-CHING-IMMUTABLE-TABLES")
        hexagrams = []
        expansion = {"source": "local-immutable-tables", "expanded": [], "resolved": []}
        try:
            registry = _json.loads(
                (tables_root / "king_wen_64_verified.json").read_text(encoding="utf-8")
            )
            hexagrams = registry.get("hexagrams", [])
            collapse_payload = _json.loads(
                (tables_root / "collapse_full_128_output.json").read_text(encoding="utf-8")
            )
            expansion["expanded"] = collapse_payload.get("expanded", [])
            expansion["resolved"] = collapse_payload.get("resolved", [])
        except Exception as exc:
            expansion = {"source": "error", "error": str(exc), "expanded": [], "resolved": []}

        resolved = expansion.get("resolved") or []
        expanded = expansion.get("expanded") or []

        selected = None
        if resolved:
            def _score(entry: Dict[str, Any]) -> float:
                vec = entry.get("resolved_vector") or entry.get("expanded_vector") or {}
                return float(vec.get("voiceWeight", 0.0) or 0.0) + float(vec.get("coherence", 0.0) or 0.0)

            selected = sorted(resolved, key=_score, reverse=True)[0]

        inject: Dict[str, Any] = {}
        state_before: Dict[str, Any] = {}
        try:
            client = KingwenClientSync(session_id=session_id)
            state_before = client.get_state()
            inject = client.inject(
                hexagram_id=int(selected.get("hexagram_id") or 1),
                phase=str(selected.get("phase_temporal") or "present"),
                domain=domain,
                verb_cluster="blueprint",
                tool=tool,
            )
            client.close()
        except Exception as exc:
            inject = {"error": str(exc)}

        hexagram_id = int(selected.get("hexagram_id") or 0)
        phase = str(selected.get("phase_temporal") or "")
        vectors = (selected.get("resolved_vector") or selected.get("expanded_vector") or {}) if selected else {}
        porosity = selected.get("inject_site", {}).get("porosity") if selected else None
        try:
            porosity = float(porosity) if porosity is not None else None
        except (TypeError, ValueError):
            porosity = None

        save_slots: List[str] = []
        hex_entries: List[Dict[str, Any]] = []
        for h in hexagrams:
            hid = int(h.get("id") or 0)
            entry: Dict[str, Any] = {
                "hexagram_id": hid,
                "name": h.get("name"),
                "unicode": h.get("unicode"),
                "category": h.get("category"),
                "action": h.get("action"),
                "upper_trigram": h.get("upper_trigram"),
                "lower_trigram": h.get("lower_trigram"),
                "phases": [],
            }
            for phase_bits in range(8):
                matched = [
                    r
                    for r in resolved
                    if int(r.get("hexagram_id") or -1) == hid
                    and int(r.get("phase_bits") or -1) == phase_bits
                ]
                slot = matched[0] if matched else {}
                vecs = slot.get("resolved_vector") or slot.get("expanded_vector") or {}
                p = slot.get("inject_site", {}).get("porosity")
                try:
                    p = float(p) if p is not None else None
                except (TypeError, ValueError):
                    p = None
                entry["phases"].append(
                    {
                        "phase_bits": phase_bits,
                        "phase_temporal": slot.get("phase_temporal"),
                        "phase_polarity": slot.get("phase_polarity"),
                        "phase_description": slot.get("phase_description"),
                        "porosity": p,
                        "voiceWeight": float(vecs.get("voiceWeight") or 0),
                        "coherence": float(vecs.get("coherence") or 0),
                        "chaos": float(vecs.get("chaos") or 0),
                        "whimsy": float(vecs.get("whimsy") or 0),
                        "darkTone": float(vecs.get("darkTone") or 0),
                        "changing_lines": slot.get("line_states"),
                    }
                )
                save_slots.append(
                    f"{hid}:{slot.get('phase_temporal','present')}:{float(vecs.get('voiceWeight') or 0):.3f}:{float(vecs.get('coherence') or 0):.3f}:{float(vecs.get('chaos') or 0):.3f}:{float(vecs.get('whimsy') or 0):.3f}:{float(vecs.get('darkTone') or 0):.3f}:{(p if p is not None else 0):.3f}:{time.time():.0f}:{domain}"
                )
            hex_entries.append(entry)

        save_string = ",".join(save_slots[:64])

        lines = [
            self._header(definition),
            "## King Wen State of Being\n\n",
            f"- Session: {session_id}\n",
            f"- Source text: {text}\n",
            f"- Domain: {domain}\n",
            f"- Tool: {tool}\n",
            f"- Expansion source: {expansion.get('source') or 'unknown'}\n",
            f"- Expanded count: {len(expanded)}\n",
            f"- Resolved count: {len(resolved)}\n",
            "\n## Dominant State\n\n",
            f"- Hexagram: {hexagram_id or '—'}\n",
            f"- Phase: {phase or 'present'}\n",
            f"- Porosity: {porosity if porosity is not None else '—'}\n",
            "\n### Vectors\n\n",
            f"- voiceWeight: {float(vectors.get('voiceWeight') or 0):.3f}\n",
            f"- coherence: {float(vectors.get('coherence') or 0):.3f}\n",
            f"- chaos: {float(vectors.get('chaos') or 0):.3f}\n",
            f"- whimsy: {float(vectors.get('whimsy') or 0):.3f}\n",
            f"- darkTone: {float(vectors.get('darkTone') or 0):.3f}\n",
            "\n## Trigrams\n\n",
            "- ☰ Qian (Heaven)\n",
            "- ☱ Dui (Lake)\n",
            "- ☲ Li (Fire)\n",
            "- ☳ Zhen (Thunder)\n",
            "- ☴ Xun (Wind)\n",
            "- ☵ Kan (Water)\n",
            "- ☶ Gen (Mountain)\n",
            "- ☷ Kun (Earth)\n",
            "\n## 64 Save-State Slots\n\n",
            "```\n",
            save_string + "\n",
            "```\n",
            "\n## First 10 Hexagrams\n\n",
            "| # | Name | Category | Upper | Lower | Phase | Temporal | VoiceWeight | Coherence | Porosity |\n",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n",
        ]
        for entry in hex_entries[:10]:
            first = entry["phases"][0] if entry["phases"] else {}
            lines.append(
                f"| {entry['hexagram_id']} | {entry['name'] or ''} | {entry['category'] or ''} | {entry['upper_trigram'] or ''} | {entry['lower_trigram'] or ''} | {first.get('phase_bits')} | {first.get('phase_temporal') or ''} | {first.get('voiceWeight', 0):.3f} | {first.get('coherence', 0):.3f} | {first.get('porosity') if first.get('porosity') is not None else '—'} |\n"
            )

        lines.extend(
            [
                "\n## Injection Result\n\n",
                f"```json\n{json.dumps(inject, indent=2)}\n```\n",
                "\n## Save State Before\n\n",
                f"```\n{state_before.get('saveString', '')}\n```\n",
            ]
        )

        content = "".join(lines)
        artifact_path.write_text(content, encoding="utf-8")
        return content


__all__ = ["BlueprintRunResult", "BlueprintExecutor"]
