"""Causality ledger for OpenJarvis King Wen integration.
Records why a synapse/artifact fired, not just that it fired.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


LEDGER_PATH = None  # set by writer if persistence is enabled


@dataclass
class CausalityLedgerRecord:
    ts: str
    session_id: str
    surface: str
    artifact_type: str
    artifact_id: str
    path: str
    consumer: str
    parent_artifact_id: Optional[str]
    reason: Optional[str]
    model: Optional[str]
    intent: str
    intent_source: str
    cluster: List[str]
    synaptic_weight: float
    tags: List[str]
    kingwen: Dict[str, Any] = field(default_factory=dict)
    mhd: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def append(record: CausalityLedgerRecord) -> None:
    global LEDGER_PATH
    if not LEDGER_PATH:
        return
    try:
        with open(LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(json_dumps(record.to_dict()) + "\n")
    except Exception:
        pass


def json_dumps(obj: Dict[str, Any]) -> str:
    try:
        import json
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def record_from_session_artifact(
    session_id: str,
    surface: str,
    artifact_type: str,
    artifact_id: str,
    path: str,
    intent: str,
    intent_source: str,
    cluster: List[str],
    synaptic_weight: float,
    tags: List[str],
    reason: Optional[str] = None,
    model: Optional[str] = None,
    parent_artifact_id: Optional[str] = None,
    consumer: str = "all",
    kingwen: Optional[Dict[str, Any]] = None,
    mhd: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> CausalityLedgerRecord:
    return CausalityLedgerRecord(
        ts=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        surface=surface,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        path=path,
        consumer=consumer,
        parent_artifact_id=parent_artifact_id,
        reason=reason,
        model=model,
        intent=intent,
        intent_source=intent_source,
        cluster=cluster,
        synaptic_weight=synaptic_weight,
        tags=tags,
        kingwen=kingwen or {},
        mhd=mhd or {},
        provenance=provenance or {},
    )
