"""Jarvis neurological map — research-grade 64-node voice/domain registry.

Mirrors POG2 NeurologicalMap.ts concepts for Jarvis:
- 64 hexagram nodes with distinct roles, domains, voice pools
- Self-referential state: activation counts, timestamps, queries by hex/domain/pool
- Runtime endpoint health test seed inject sites
- Real data from King Wen immutable tables
- No mocks, no placeholders
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.environ.get(
    "KING_WEN_IMMUTABLE_TABLES",
    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES",
)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from kingwen_ternary_tables_complete import (
    HEXAGRAM_BASE,
    HEXAGRAM_INJECTION_SITE,
    VOICEBOX_VOICE_POOL,
    EMOTIONAL_WEIGHTS,
)


class NeurologicalNode:
    __slots__ = (
        "hexagram_id",
        "name",
        "unicode",
        "category",
        "action",
        "domain",
        "primary_pool",
        "secondary_pool",
        "porosity",
        "voice_weight",
        "coherence",
        "chaos",
        "whimsy",
        "dark_tone",
        "doc_domain",
        "role",
        "training_notes",
        "vector",
        "activation_count",
        "last_activated_ts",
        "endpoint_seed",
        "last_health_status",
        "last_health_ts",
        "health_details",
    )

    def __init__(
        self,
        hexagram_id: int,
        name: str,
        unicode: str,
        category: str,
        action: str,
        domain: str,
        primary_pool: str,
        secondary_pool: str,
        porosity: float,
        voice_weight: float,
        coherence: float,
        chaos: float,
        whimsy: float,
        dark_tone: float,
        doc_domain: str = "META",
        role: str = "",
        training_notes: str = "",
        vector: Optional[Dict[str, float]] = None,
        activation_count: int = 0,
        last_activated_ts: int = 0,
        endpoint_seed: str = "",
        last_health_status: str = "UNKNOWN",
        last_health_ts: int = 0,
        health_details: str = "",
    ) -> None:
        self.hexagram_id = hexagram_id
        self.name = name
        self.unicode = unicode
        self.category = category
        self.action = action
        self.domain = domain
        self.primary_pool = primary_pool
        self.secondary_pool = secondary_pool
        self.porosity = porosity
        self.voice_weight = voice_weight
        self.coherence = coherence
        self.chaos = chaos
        self.whimsy = whimsy
        self.dark_tone = dark_tone
        self.doc_domain = doc_domain
        self.role = role
        self.training_notes = training_notes
        self.vector = vector or {
            "voiceWeight": voice_weight,
            "coherence": coherence,
            "chaos": chaos,
            "whimsy": whimsy,
            "darkTone": dark_tone,
        }
        self.activation_count = activation_count
        self.last_activated_ts = last_activated_ts
        self.endpoint_seed = endpoint_seed or self._default_seed(hexagram_id, domain, primary_pool)
        self.last_health_status = last_health_status
        self.last_health_ts = last_health_ts
        self.health_details = health_details

    @staticmethod
    def _default_seed(hexagram_id: int, domain: str, primary_pool: str) -> str:
        raw = f"{hexagram_id}:{domain}:{primary_pool}".encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hexagram_id": self.hexagram_id,
            "name": self.name,
            "unicode": self.unicode,
            "category": self.category,
            "action": self.action,
            "domain": self.domain,
            "primary_pool": self.primary_pool,
            "secondary_pool": self.secondary_pool,
            "porosity": self.porosity,
            "voice_weight": self.voice_weight,
            "coherence": self.coherence,
            "chaos": self.chaos,
            "whimsy": self.whimsy,
            "dark_tone": self.dark_tone,
            "doc_domain": self.doc_domain,
            "role": self.role,
            "training_notes": self.training_notes,
            "vector": self.vector,
            "activation_count": self.activation_count,
            "last_activated_ts": self.last_activated_ts,
            "endpoint_seed": self.endpoint_seed,
            "last_health_status": self.last_health_status,
            "last_health_ts": self.last_health_ts,
            "health_details": self.health_details,
        }


class JarvisNeurologicalMap:
    """64-node neurological map for OpenJarvis.

    Self-referential: query by hex/domain/pool/voice, update activation state,
    inject/recover runtime endpoint health test seeds.
    All 64 hexagrams have distinct voice/domain assignments.
    """

    def __init__(self) -> None:
        self._nodes: Dict[int, NeurologicalNode] = {}
        self._by_domain: Dict[str, List[NeurologicalNode]] = {}
        self._by_pool: Dict[str, List[NeurologicalNode]] = {}
        self._by_seed: Dict[str, NeurologicalNode] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        self._nodes.clear()
        self._by_domain.clear()
        self._by_pool.clear()
        self._by_seed.clear()
        for hex_id in range(1, 65):
            record = HEXAGRAM_BASE.get(hex_id, {})
            inject = HEXAGRAM_INJECTION_SITE.get(hex_id, {})
            weights = EMOTIONAL_WEIGHTS.get(str(hex_id), {})
            category = str(inject.get("category") or record.get("category") or "").strip()
            action = str(inject.get("action") or record.get("action") or "").strip()
            domain = f"kingwen/{category.lower()}" if category else f"kingwen/hex-{hex_id:02d}"
            primary_pool = str(inject.get("primary_pool") or "").strip()
            secondary_pool = str(inject.get("secondary_pool") or "").strip()
            porosity = float(inject.get("porosity") or 0.0)
            vector = {
                "voiceWeight": float(weights.get("voiceWeight", 0.0) or 0.0),
                "coherence": float(weights.get("coherence", 0.0) or 0.0),
                "chaos": float(weights.get("chaos", 0.0) or 0.0),
                "whimsy": float(weights.get("whimsy", 0.0) or 0.0),
                "darkTone": float(weights.get("darkTone", 0.0) or 0.0),
            }
            doc_domain = self._doc_domain_for(category, action)
            role = self._role_for(hex_id, record, inject)
            node = NeurologicalNode(
                hexagram_id=hex_id,
                name=str(record.get("name") or ""),
                unicode=str(record.get("unicode") or ""),
                category=category,
                action=action,
                domain=domain,
                primary_pool=primary_pool,
                secondary_pool=secondary_pool,
                porosity=porosity,
                voice_weight=vector["voiceWeight"],
                coherence=vector["coherence"],
                chaos=vector["chaos"],
                whimsy=vector["whimsy"],
                dark_tone=vector["darkTone"],
                doc_domain=doc_domain,
                role=role,
                training_notes=str(weights.get("trainingNotes") or inject.get("reason") or ""),
                vector=vector,
            )
            self._nodes[hex_id] = node
            self._by_domain.setdefault(domain, []).append(node)
            if primary_pool:
                self._by_pool.setdefault(primary_pool, []).append(node)
            if secondary_pool:
                self._by_pool.setdefault(secondary_pool, []).append(node)
            self._by_seed[node.endpoint_seed] = node

    @staticmethod
    def _doc_domain_for(category: str, action: str) -> str:
        c = (category or "").lower()
        a = (action or "").lower()
        if any(k in c for k in ["speech", "voice", "vocabulary"]):
            return "CREATIVE"
        if any(k in c for k in ["memory", "recall", "learn"]):
            return "MEMORY"
        if any(k in c for k in ["tool", "use", "inspect"]):
            return "CODE"
        if any(k in a for k in ["read", "write", "build", "repair"]):
            return "CODE"
        return "META"

    @staticmethod
    def _role_for(hex_id: int, record: Dict[str, Any], inject: Dict[str, Any]) -> str:
        action = str(inject.get("action") or record.get("action") or "").strip()
        category = str(inject.get("category") or record.get("category") or "").strip()
        if action:
            return action
        if category:
            return category
        return f"hex-{hex_id:02d}"

    def get(self, hex_id: int) -> NeurologicalNode:
        return self._nodes[hex_id]

    def all(self) -> List[NeurologicalNode]:
        return list(self._nodes.values())

    def by_domain(self, domain: str) -> List[NeurologicalNode]:
        return list(self._by_domain.get(domain, []))

    def by_pool(self, pool: str) -> List[NeurologicalNode]:
        return list(self._by_pool.get(pool, []))

    def by_seed(self, seed: str) -> Optional[NeurologicalNode]:
        return self._by_seed.get(seed)

    def dominant_voice(self) -> NeurologicalNode:
        return max(self._nodes.values(), key=lambda n: n.voice_weight + n.coherence)

    def dominant_domain(self) -> str:
        counts: Dict[str, int] = {}
        for node in self._nodes.values():
            counts[node.domain] = counts.get(node.domain, 0) + 1
        return max(counts, key=counts.__getitem__)

    def activate(self, hex_id: int, ts: int = 0) -> NeurologicalNode:
        node = self._nodes[hex_id]
        node.activation_count += 1
        node.last_activated_ts = ts
        return node

    def inject_health_seed(self, hex_id: int, seed: str, status: str = "ONLINE", details: str = "") -> NeurologicalNode:
        node = self._nodes[hex_id]
        node.endpoint_seed = seed
        node.last_health_status = status
        node.last_health_ts = int(time.time() * 1000)
        node.health_details = details
        self._by_seed[seed] = node
        return node

    def recover_by_seed(self, seed: str) -> Optional[NeurologicalNode]:
        node = self._by_seed.get(seed)
        if node is None:
            return None
        node.last_health_ts = int(time.time() * 1000)
        return node

    def summary(self) -> Dict[str, Any]:
        return {
            "node_count": len(self._nodes),
            "domain_count": len(self._by_domain),
            "pool_count": len(self._by_pool),
            "dominant_domain": self.dominant_domain(),
            "dominant_voice": {
                "hexagram_id": self.dominant_voice().hexagram_id,
                "name": self.dominant_voice().name,
                "domain": self.dominant_voice().domain,
                "primary_pool": self.dominant_voice().primary_pool,
                "vector": self.dominant_voice().vector,
            },
        }


__all__ = ["JarvisNeurologicalMap", "NeurologicalNode"]
