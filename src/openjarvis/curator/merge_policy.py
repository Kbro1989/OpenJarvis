"""Capability-based merge policy for the OpenJarvis curator.

Adds semantic/capability-aware curation on top of the existing time-based
curator without mutating raw session text. On failure, the caller should
fall back to the existing time-based behavior unchanged.
"""
from __future__ import annotations

import dataclasses
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Shared artifact shape, aligned with Hermes ``session-artifact-ledger.jsonl``
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CuratorArtifact:
    session_id: str
    artifact_type: str
    surface: str
    intent: str
    cluster: List[str]
    synaptic_weight: float
    path: str
    tags: List[str] = field(default_factory=list)
    ts: Optional[str] = None


# ---------------------------------------------------------------------------
# Time-based policy: preserves the existing time-only curator behavior
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TimeBasedCuratorPolicy:
    stale_after_days: float = 30.0
    archive_after_days: float = 90.0
    prune_builtins: bool = True
    interval_hours: float = 168.0

    def is_stale(self, artifact: CuratorArtifact) -> bool:
        if not artifact.ts:
            return False
        try:
            age_days = (time.time() - time.mktime(time.strptime(artifact.ts[:19], "%Y-%m-%dT%H:%M:%S"))) / 86400.0
        except Exception:
            return False
        return age_days > self.stale_after_days

    def is_archived(self, artifact: CuratorArtifact) -> bool:
        if not artifact.ts:
            return False
        try:
            age_days = (time.time() - time.mktime(time.strptime(artifact.ts[:19], "%Y-%m-%dT%H:%M:%S"))) / 86400.0
        except Exception:
            return False
        return age_days > self.archive_after_days

    def filter(self, artifacts: Iterable[CuratorArtifact]) -> List[CuratorArtifact]:
        out: List[CuratorArtifact] = []
        for artifact in artifacts:
            if self.prune_builtins and artifact.surface in {"cli", "root"}:
                continue
            if self.is_archived(artifact):
                continue
            if self.is_stale(artifact):
                continue
            out.append(artifact)
        return out


# ---------------------------------------------------------------------------
# Capability-based policy: merge skill-weight vectors, discard raw text
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CapabilityBasedCuratorPolicy:
    capability_ledger_path: Path = field(
        default_factory=lambda: Path("C:/Users/krist/AppData/Local/hermes/cache/skill-activation-rankings.jsonl")
    )
    capabilities_path: Path = field(
        default_factory=lambda: Path("C:/Users/krist/AppData/Local/hermes/cache/capability-pulse.jsonl")
    )
    skill_baseline_path: Path = field(
        default_factory=lambda: Path("C:/Users/krist/AppData/Local/hermes/cache/skills-baseline.json")
    )
    min_activation: float = 0.05
    vector_decay: float = 0.85
    top_k_capabilities: int = 64

    def _load_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        out: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _latest_skill_graph(self) -> Dict[str, float]:
        rows = self._load_jsonl(self.capability_ledger_path)
        if not rows:
            rows = self._load_jsonl(self.capabilities_path)
        latest = rows[-1] if rows else {}
        skill_graph = latest.get("skill_graph") or latest.get("skills", {}).get("skill_graph") or []
        out: Dict[str, float] = {}
        for entry in skill_graph:
            sid = entry.get("skill_id") or entry.get("id") or entry.get("name")
            activation = entry.get("activation")
            voltage = entry.get("voltage", 0.0)
            if sid is None or activation is None:
                continue
            try:
                activation = float(activation)
            except Exception:
                continue
            if activation < self.min_activation:
                continue
            score = max(0.0, activation) + max(0.0, float(voltage)) * 0.1
            out[str(sid)] = max(out.get(str(sid), 0.0), score)
        return out

    def _baseline_skills(self) -> set:
        data = self._load_json(self.skill_baseline_path)
        skills = data.get("skills") if isinstance(data, dict) else None
        out: set = set()
        if isinstance(skills, list):
            for entry in skills:
                if not isinstance(entry, dict):
                    continue
                sid = entry.get("path") or entry.get("skill_id") or entry.get("name")
                if sid:
                    out.add(str(sid))
        return out

    def build_capability_vector(self, artifacts: Iterable[CuratorArtifact]) -> Dict[str, float]:
        skill_graph = self._latest_skill_graph()
        baseline = self._baseline_skills()
        cluster_accum: Dict[str, float] = {}
        for artifact in artifacts:
            if artifact.artifact_type != "session_dump":
                continue
            for concept in artifact.cluster:
                concept = concept.strip().lower()
                if not concept or len(concept) < 3:
                    continue
                weight = float(artifact.synaptic_weight)
                if baseline:
                    weight *= 0.75
                cluster_accum[concept] = cluster_accum.get(concept, 0.0) + weight
                for sid, activation in skill_graph.items():
                    if concept in sid.lower():
                        cluster_accum[concept] += activation * 0.25
        capability_vector = dict(cluster_accum)
        for concept, value in capability_vector.items():
            capability_vector[concept] = math.pow(value, self.vector_decay)
        return dict(
            sorted(capability_vector.items(), key=lambda kv: kv[1], reverse=True)[: self.top_k_capabilities]
        )

    def semantic_merge_key(self, artifact: CuratorArtifact) -> Tuple[str, ...]:
        normalized_cluster = sorted({c.strip().lower() for c in artifact.cluster if c and len(c) > 2})
        return tuple(normalized_cluster[:8])

    def merge(self, artifacts: Iterable[CuratorArtifact]) -> List[CuratorArtifact]:
        merged: Dict[Any, CuratorArtifact] = {}
        for artifact in artifacts:
            if artifact.artifact_type != "session_dump":
                continue
            key = self.semantic_merge_key(artifact)
            existing = merged.get(key)
            if existing is None:
                merged[key] = CuratorArtifact(
                    session_id=artifact.session_id,
                    artifact_type="capability_ring",
                    surface=artifact.surface,
                    intent="",
                    cluster=list(key),
                    synaptic_weight=artifact.synaptic_weight,
                    path="capability-ring://merged/" + artifact.session_id,
                    tags=list(artifact.tags),
                    ts=artifact.ts,
                )
            else:
                existing.synaptic_weight = max(existing.synaptic_weight, artifact.synaptic_weight)
                existing.tags = list({*existing.tags, *artifact.tags})
        merged_artifacts = list(merged.values())
        merged_artifacts.sort(key=lambda a: a.synaptic_weight, reverse=True)
        return merged_artifacts

    def curate(
        self,
        artifacts: Iterable[CuratorArtifact],
        time_policy: Optional[TimeBasedCuratorPolicy] = None,
    ) -> Dict[str, Any]:
        time_policy = time_policy or TimeBasedCuratorPolicy()
        filtered = time_policy.filter(artifacts)
        merged = self.merge(filtered)
        capability_vector = self.build_capability_vector(filtered)
        top_capabilities = sorted(capability_vector.items(), key=lambda kv: kv[1], reverse=True)[:32]
        return {
            "type": "capability_curation",
            "capabilities_checked": len(top_capabilities),
            "capabilities_retained": len(top_capabilities),
            "time_filtered_count": len(filtered),
            "capability_vector": top_capabilities,
            "retained": [dataclasses.asdict(a) for a in merged[:128]],
            "discarded_raw_text": True,
        }


# ---------------------------------------------------------------------------
# Composed curator: capability-first, time-based fallback
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CapabilityMergedCurator:
    capability_policy: CapabilityBasedCuratorPolicy = field(default_factory=CapabilityBasedCuratorPolicy)
    time_policy: TimeBasedCuratorPolicy = field(default_factory=TimeBasedCuratorPolicy)

    def curate(self, artifacts: Iterable[CuratorArtifact]) -> Dict[str, Any]:
        try:
            return self.capability_policy.curate(artifacts, time_policy=self.time_policy)
        except Exception as exc:
            return self._fallback(artifacts, exc)

    def _fallback(self, artifacts: Iterable[CuratorArtifact], exc: Exception) -> Dict[str, Any]:
        try:
            filtered = self.time_policy.filter(artifacts)
            return {
                "type": "time_curation",
                "capabilities_checked": 0,
                "capabilities_retained": 0,
                "time_filtered_count": len(filtered),
                "capability_vector": [],
                "retained": [dataclasses.asdict(a) for a in filtered[:128]],
                "discarded_raw_text": False,
                "fallback_reason": f"{exc.__class__.__name__}: {exc}",
            }
        except Exception:
            return {
                "type": "curator_scan",
                "capabilities_checked": 0,
                "message": "Skill maintenance scan complete.",
            }
