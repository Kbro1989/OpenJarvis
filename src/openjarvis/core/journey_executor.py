"""JourneyExecutor — bridge from chat_cmd to journey_lookup.py / journey_weave.py.
Emits JOURNEY_ARRIVAL and LEARN_AUTO_INGEST via the existing event bus.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.events import EventType, get_event_bus


@dataclass(slots=True)
class JourneyMatch:
    session_id: str
    score: float
    synaptic_weight: float
    intent: str
    cluster: List[str]
    related_sessions: List[str]
    path: str
    artifact_type: str = "session_dump"
    surface: str = "shared"


class JourneyExecutor:
    def __init__(self, event_bus: Optional[Any] = None, cache_dir: Optional[Path] = None) -> None:
        self.bus = event_bus or get_event_bus()
        self.cache_dir = cache_dir or self._default_cache_dir()
        self.scripts_dir = self.cache_dir / "scripts"
        self.ledger_path = self.cache_dir / "session-artifact-ledger.jsonl"
        self.sessions_dir = Path.home() / "AppData" / "Local" / "hermes" / "sessions"

    @staticmethod
    def _default_cache_dir() -> Path:
        env = os.environ.get("HERMES_CACHE")
        if env:
            return Path(env)
        return Path.home() / "AppData" / "Local" / "hermes" / "cache"

    def consult(self, query: str, emotional_input: int = 50) -> Dict[str, Any]:
        """Run a King Wen consult for the current journey query."""
        from openjarvis.cli._oracle_speak import _consult_worker, get_emotional_input

        effective_input = get_emotional_input(default=emotional_input)
        consult_result = _consult_worker(query, session_id="journey", emotional_input=effective_input)
        payload = {
            "query": query,
            "emotional_input": effective_input,
            "consensus_hexagram_id": consult_result.get("consensus_hexagram_id"),
            "consensus_temporal": consult_result.get("consensus_temporal"),
            "consensus_yao": consult_result.get("consensus_yao"),
            "consensus_vector": consult_result.get("consensus_vector"),
            "consensus_intent": consult_result.get("consensus_intent"),
            "trajectory": consult_result.get("trajectory"),
            "mode": consult_result.get("mode"),
            "tool_hint": consult_result.get("tool_hint"),
            "rule": consult_result.get("rule"),
            "porosity": consult_result.get("porosity"),
            "scenes": consult_result.get("scenes"),
            "source": "journey-executor",
        }
        try:
            from openjarvis.core.session_clock_bridge import tag_payload

            payload = tag_payload(
                payload,
                session_id=getattr(self, "session_id", "journey"),
                phase="journey",
                event="consult",
            )
        except Exception:
            pass
        self.bus.publish(EventType.JOURNEY_ARRIVAL, payload)
        return payload

    def lookup(self, query: str, autotags: Optional[List[str]] = None) -> List[JourneyMatch]:
        raw = self._run_lookup_script(query, autotags)
        matches = self._parse_matches(raw)
        novel_edges = self._detect_novel_edges(matches)

        self.bus.publish(EventType.JOURNEY_ARRIVAL, {
            "query": query,
            "autotags": autotags or [],
            "match_count": len(matches),
            "top_session": matches[0].session_id if matches else None,
            "top_score": matches[0].score if matches else 0.0,
            "matches": [m.__dict__ for m in matches],
        })

        if novel_edges:
            self.bus.publish(EventType.LEARN_AUTO_INGEST, {
                "query": query,
                "novel_edge_count": len(novel_edges),
                "novel_edges": novel_edges,
                "source": "journey_lookup",
                "context_pools": self._extract_context_pools(matches),
                "emotional_vector": self._extract_emotion_vector(matches),
            })

        return matches

    def _run_lookup_script(self, query: str, autotags: Optional[List[str]]) -> Dict[str, Any]:
        script = self.scripts_dir / "journey_lookup.py"
        cmd = [os.sys.executable, str(script), query]
        if autotags:
            cmd += ["--autotag", ",".join(autotags)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.cache_dir),
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"journey_lookup.py failed (rc={result.returncode}):\n{result.stderr}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"journey_lookup.py returned non-JSON:\n{result.stdout[:500]}"
            ) from exc

    def _parse_matches(self, raw: Dict[str, Any]) -> List[JourneyMatch]:
        out: List[JourneyMatch] = []
        for m in raw.get("matches", []):
            out.append(JourneyMatch(
                session_id=m.get("session_id", ""),
                score=float(m.get("score", 0)),
                synaptic_weight=float(m.get("synaptic_weight", 1.0)),
                intent=m.get("intent", ""),
                cluster=m.get("cluster", []),
                related_sessions=m.get("related_sessions", []),
                path=m.get("path", ""),
                artifact_type=m.get("artifact_type", "session_dump"),
                surface=m.get("surface", "shared"),
            ))
        return out

    def _detect_novel_edges(self, matches: List[JourneyMatch]) -> List[Dict[str, Any]]:
        matched_ids = {m.session_id for m in matches}
        novel: List[Dict[str, Any]] = []
        for m in matches:
            for rel in m.related_sessions:
                if rel not in matched_ids:
                    novel.append({
                        "source": m.session_id,
                        "target": rel,
                        "weight": m.score * m.synaptic_weight,
                        "intent_snippet": m.intent[:120],
                        "cluster": m.cluster,
                    })
        return novel

    def _extract_context_pools(self, matches: List[JourneyMatch]) -> List[str]:
        pools: set = set()
        for m in matches:
            for word in m.cluster:
                if len(word) > 3:
                    pools.add(word.lower())
        return sorted(pools)[:32]

    def _extract_emotion_vector(self, matches: List[JourneyMatch]) -> Dict[str, float]:
        n = len(matches) or 1
        return {
            "valence": 0.5 + (matches[0].score / 10.0 if matches else 0),
            "arousal": min(1.0, n / 5.0),
            "dominance": 0.5,
        }

    def replay(self, session_id: str) -> Dict[str, Any]:
        dump_path = self._resolve_session_dump(session_id)
        if not dump_path.exists():
            raise FileNotFoundError(f"No session dump for {session_id}")

        with open(dump_path, "r", encoding="utf-8") as fh:
            dump = json.load(fh)

        self.bus.publish(EventType.JOURNEY_ARRIVAL, {
            "type": "replay",
            "session_id": session_id,
            "dump_path": str(dump_path),
            "intent": dump.get("intent", ""),
            "context": dump,
        })
        return dump

    def _resolve_session_dump(self, session_id: str) -> Path:
        pattern = f"request_dump_{session_id}_*.json"
        hits = list(self.sessions_dir.glob(pattern))
        if not hits:
            raise FileNotFoundError(f"Session dump not found: {session_id}")
        return sorted(hits, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    def weave(self, from_session: str, to_session: str) -> Dict[str, Any]:
        weave_script = self.scripts_dir / "journey_weave.py"
        if not weave_script.exists():
            raise FileNotFoundError(f"journey_weave.py not found at {weave_script}")

        cmd = [
            os.sys.executable,
            str(weave_script),
            "--from", from_session,
            "--to", to_session,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.cache_dir),
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"journey_weave.py failed (rc={result.returncode}):\n{result.stderr}"
            )

        try:
            path = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"journey_weave.py returned non-JSON:\n{result.stdout[:500]}"
            ) from exc

        self.bus.publish(EventType.JOURNEY_ARRIVAL, {
            "type": "weave",
            "from": from_session,
            "to": to_session,
            "path": path,
        })
        return path
