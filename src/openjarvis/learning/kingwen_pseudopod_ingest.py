"""King Wen pseudopod + live usage ingestion/validation for OpenJarvis.

Ports copyable surfaces from Megatron-LM-review kingwen_train_data:
- runtime/kingwen_dataset.py domain-aware SampleMeta concepts
- build_usage_labels.py live trace ingestion
- integrity_check.py corpus validation

Strict no-mock. Uses real TraceStore and filesystem artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class SampleMeta:
    session_id: str
    agent_id: Optional[str]
    domain: str
    text: str
    trace_id: Optional[str] = None
    hexagram_id: Optional[int] = None
    porosity: Optional[float] = None
    voice_vector: Optional[Dict[str, float]] = None
    source_path: Optional[str] = None


class KingWenPseudopodIngestor:
    """Ingest OpenJarvis traces into King Wen training-shaped rows."""

    POROSITY_WEIGHT = {0: 1.0, 1: 1.05, 2: 1.15, 3: 1.35, 4: 1.5}
    DOMAIN_PREFIXES = {
        "traces.db:trace_steps": "OPENJARVIS",
        "agents.db:agent_messages": "OPENJARVIS",
        "agents.db:agent_learning_log": "OPENJARVIS",
        "kingwen_worker:/consult": "KING_WEN_ORACLE",
        "sovereign_pipeline:scene": "SOVEREIGN_PIPELINE_SCENE",
        "ternary_interaction": "TERNARY_INTERACTION",
        "slider_capture": "SLIDER_CAPTURE",
    }

    def __init__(self, trace_store: Any, output_dir: Optional[Path] = None) -> None:
        self.trace_store = trace_store
        self.output_dir = output_dir or Path.home() / ".openjarvis" / "learning"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rows_written = 0

    def _trace_store_path(self) -> Optional[Path]:
        for attr in ("db_path", "path", "_db_path"):
            candidate = getattr(self.trace_store, attr, None)
            if isinstance(candidate, (str, Path)):
                return Path(candidate)
        return None

    def _domain_for(self, source: str) -> str:
        for key, prefix in self.DOMAIN_PREFIXES.items():
            if key in source:
                return prefix
        return "OPENJARVIS"

    def _row_from_trace(self, trace: Any, source_path: str) -> SampleMeta:
        session_id = getattr(trace, "session_id", "") or ""
        agent_id = getattr(trace, "agent_id", None)
        domain = self._domain_for(source_path)
        text = getattr(trace, "content", "") or getattr(trace, "prompt", "") or ""
        trace_id = getattr(trace, "id", None) or getattr(trace, "trace_id", None)
        porosity = getattr(trace, "kingwen_porosity", None)
        voice_vector = getattr(trace, "kingwen_voice_vector", None)
        hexagram_id = getattr(trace, "kingwen_hexagram_id", None)
        if isinstance(hexagram_id, str):
            try:
                hexagram_id = int(hexagram_id)
            except ValueError:
                hexagram_id = None
        return SampleMeta(
            session_id=session_id,
            agent_id=agent_id,
            domain=domain,
            text=text,
            trace_id=trace_id,
            hexagram_id=hexagram_id,
            porosity=float(porosity) if porosity is not None else None,
            voice_vector=voice_vector if isinstance(voice_vector, dict) else None,
            source_path=source_path,
        )

    def _serialize_row(self, row: SampleMeta) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "session_id": row.session_id,
            "agent_id": row.agent_id,
            "domain": row.domain,
            "text": row.text,
            "source": row.source_path,
        }
        if row.trace_id is not None:
            payload["trace_id"] = row.trace_id
        if row.hexagram_id is not None:
            payload["hexagram_id"] = row.hexagram_id
        if row.porosity is not None:
            payload["porosity"] = row.porosity
            payload["sample_weight"] = self.POROSITY_WEIGHT.get(
                min(4, max(0, int(row.porosity))), 1.0
            )
        if row.voice_vector is not None:
            payload["voice_vector"] = row.voice_vector
        return payload

    def ingest_traces(self, limit: int = 200) -> Path:
        rows: List[SampleMeta] = []
        try:
            traces = self.trace_store.list_traces(limit=limit)
            for idx, trace in enumerate(traces):
                source = f"traces.db:trace_steps:{idx}"
                rows.append(self._row_from_trace(trace, source))
        except Exception:
            rows = []

        try:
            agent_size = getattr(getattr(self.trace_store, "agents_db", None), "size", lambda: 0)()
            for idx in range(min(agent_size, limit)):
                raw = getattr(self.trace_store, "agents_db", None)
                msg = getattr(raw, "get_message_by_index", lambda i: None)(idx) if raw else None
                if msg is None:
                    continue
                rows.append(self._row_from_trace(msg, "agents.db:agent_messages"))
        except Exception:
            pass

        out_path = self.output_dir / "kingwen_pseudopod_ingest.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(self._serialize_row(row), ensure_ascii=False) + "\n")
            self.rows_written = len(rows)
        return out_path


class CorpusIntegrityValidator:
    """Validate King Wen corpus files for schema drift and missing fields."""

    REQUIRED_KEYS = {
        "kingwen_pretrain.jsonl": ["text"],
        "kingwen_pseudopod_ingest.jsonl": ["session_id", "domain", "text", "source"],
        "combined_pretrain_train.jsonl": ["text"],
        "learn-ingest.jsonl": ["query", "novel_edge_count", "novel_edges"],
    }

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path.home() / ".openjarvis" / "learning"
        self.issues: List[Dict[str, Any]] = []

    def validate_all(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {"files": {}, "issue_count": 0}
        for filename, required in self.REQUIRED_KEYS.items():
            path = self.base_dir / filename
            if not path.exists():
                results["files"][filename] = {"exists": False, "issue": "missing"}
                self.issues.append({"file": filename, "issue": "missing"})
                continue
            line_count = 0
            bad = 0
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    line_count += 1
                    try:
                        obj = json.loads(line)
                        missing = [k for k in required if k not in obj]
                        if missing:
                            bad += 1
                            self.issues.append({"file": filename, "line": line_count, "missing": missing})
                    except json.JSONDecodeError:
                        bad += 1
                        self.issues.append({"file": filename, "line": line_count, "issue": "json_decode_error"})
            results["files"][filename] = {
                "exists": True,
                "line_count": line_count,
                "bad_lines": bad,
                "required_keys": required,
            }
        results["issue_count"] = len(self.issues)
        return results
