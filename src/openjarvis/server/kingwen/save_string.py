"""King Wen Avatar Save String — compact state serialization.

Formats:
- Single:  hex_id:phase:vw:ch:cc:wh:dt:porosity:timestamp:domain
- Batch:   hex_id1,hex_id2,...|phase1,phase2,...|vw1,ch1,...|timestamp|domain
- Trigram: ☰☱☲☳☴☵☶☷ mapped to upper/lower trigram pairs
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


# ── Trigram symbols and mappings ──

TRIGRAM_SYMBOLS = {
    "111": "☰",  # Qian / Creative
    "011": "☱",  # Dui / Joyous
    "101": "☲",  # Li / Clinging
    "001": "☳",  # Zhen / Arousing
    "010": "☴",  # Xun / Gentle
    "000": "☵",  # Kan / Abysmal
    "110": "☶",  # Gen / Keeping Still
    "100": "☷",  # Kun / Receptive
}

TRIGRAM_NAMES = {
    "111": "Heaven",
    "011": "Lake",
    "101": "Fire",
    "001": "Thunder",
    "010": "Wind",
    "000": "Water",
    "110": "Mountain",
    "100": "Earth",
}

# Reverse lookup: symbol -> binary
TRIGRAM_BINARY = {v: k for k, v in TRIGRAM_SYMBOLS.items()}


def binary_to_trigram_symbol(binary_3: str) -> str:
    return TRIGRAM_SYMBOLS.get(binary_3, "?")


def hexagram_to_trigram_pair(hex_binary: str) -> tuple[str, str]:
    upper = hex_binary[:3]
    lower = hex_binary[3:]
    return (
        binary_to_trigram_symbol(upper),
        binary_to_trigram_symbol(lower),
    )


# ── Action parser: verb cluster → tool endpoint ──

ACTION_CLUSTER_TOOL_MAP = {
    "Talk to": "/counsel/voice",
    "Listen to": "/counsel/voice",
    "Read": "/learn/recall",
    "Information": "/learn/query",
    "Inspect": "/tool/inspect",
    "Look at": "/tool/inspect",
    "Use": "/tool/use",
    "Activate": "/tool/activate",
    "Rub": "/tool/rub",
    "Enter": "/tool/enter",
    "Open": "/tool/open",
    "Interact": "/tool/interact",
    "Build": "/blueprint/run",
    "Craft": "/blueprint/run",
    "Repair": "/tool/repair",
    "Collect": "/tool/collect",
    "Destroy": "/tool/destroy",
    "Attack": "/combat/engage",
    "Break": "/tool/destroy",
    "Hit": "/combat/engage",
    "Write": "/learn/record",
    "Weave": "/agents/swarm",
}

DEFAULT_TOOL_FOR_DOMAIN = {
    "speech/vocabulary": "/oracle/speak",
    "memory/recall": "/learn/recall",
    "tool/routing": "/tool/use",
}


def resolve_tool_call(verb_cluster: List[str], domain: str) -> Optional[str]:
    for verb in verb_cluster:
        if verb in ACTION_CLUSTER_TOOL_MAP:
            return ACTION_CLUSTER_TOOL_MAP[verb]
    return DEFAULT_TOOL_FOR_DOMAIN.get(domain, "/tool/use")


# ── Save string dataclass ──


PHASE_MAP = {'past': 'a', 'present': 'p', 'future': 'f'}
PHASE_FULL_MAP = {'a': 'past', 'p': 'present', 'f': 'future'}


@dataclass(frozen=True)
class AvatarSaveString:
    hex_id: int           # 1-64 canonical, 0-511 expanded
    phase: str            # 'a' | 'p' | 'f'
    voice_weight: int     # 0-9
    coherence: int        # 0-9
    chaos: int            # 0-9
    whimsy: int           # 0-9
    dark_tone: int        # 0-9
    porosity: int         # 0-99
    timestamp: int        # Unix epoch ms
    domain: str           # e.g. 'speech/vocabulary', 'lumbridge'
    trigrams: Optional[str] = field(default=None)  # e.g. '☰☷'
    action_clusters: Optional[List[str]] = field(default=None)
    schema_version: str = field(default="jarvis-save-v2")
    category: Optional[str] = field(default=None)
    action: Optional[str] = field(default=None)
    runtime_tier: Optional[str] = field(default=None)
    health: Optional[str] = field(default=None)
    tool: Optional[str] = field(default=None)
    predicate: Optional[str] = field(default=None)
    pass_type: Optional[str] = field(default=None)
    confidence: Optional[float] = field(default=None)
    emotional_input: Optional[float] = field(default=None)
    turn_id: Optional[str] = field(default=None)

    @property
    def phase_full(self) -> str:
        return PHASE_FULL_MAP.get(self.phase, 'present')

    @property
    def iso_timestamp(self) -> str:
        return datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc).isoformat()

    @property
    def tool_call(self) -> Optional[str]:
        if self.action_clusters:
            return resolve_tool_call(self.action_clusters, self.domain)
        return DEFAULT_TOOL_FOR_DOMAIN.get(self.domain, "/tool/use")

    def to_compact(self) -> str:
        """Serialize to compact save string."""
        if (
            self.category
            or self.action
            or self.runtime_tier
            or self.health
            or self.tool
            or self.predicate
            or self.pass_type
            or self.confidence is not None
            or self.emotional_input is not None
            or self.turn_id
        ):
            extra = ":".join(
                [
                    self.schema_version or "",
                    self.category or "",
                    self.action or "",
                    self.runtime_tier or "",
                    self.health or "",
                    self.tool or "",
                    self.predicate or "",
                    self.pass_type or "",
                    (f"{self.confidence:.4f}" if self.confidence is not None else ""),
                    (f"{self.emotional_input:.4f}" if self.emotional_input is not None else ""),
                    self.turn_id or "",
                ]
            )
            return (
                f"{self.schema_version or 'jarvis-save-v2'}|{self.hex_id:02d}:{self.phase}:"
                f"{self.voice_weight}:{self.coherence}:{self.chaos}:"
                f"{self.whimsy}:{self.dark_tone}:{self.porosity:02d}:"
                f"{self.timestamp}:{self.domain};{extra}"
            )
        return (
            f"{self.hex_id:02d}:{self.phase}:"
            f"{self.voice_weight}:{self.coherence}:{self.chaos}:"
            f"{self.whimsy}:{self.dark_tone}:{self.porosity:02d}:"
            f"{self.timestamp}:{self.domain}"
        )

    @classmethod
    def from_compact(cls, s: str) -> "AvatarSaveString":
        """Parse from compact save string."""
        if ";" in s:
            payload, extra = s.split(";", 1)
            version = ""
            if "|" in payload:
                version, payload = payload.split("|", 1)
            parts = payload.split(":")
            if len(parts) != 10:
                raise ValueError(f"Invalid save string format: expected 10 segments, got {len(parts)}")
            extra_parts = extra.split(":")
            def _extra(idx, default=""):
                return extra_parts[idx].strip() if idx < len(extra_parts) and extra_parts[idx].strip() else default
            return cls(
                hex_id=int(parts[0]),
                phase=parts[1],
                voice_weight=int(parts[2]),
                coherence=int(parts[3]),
                chaos=int(parts[4]),
                whimsy=int(parts[5]),
                dark_tone=int(parts[6]),
                porosity=int(parts[7]),
                timestamp=int(parts[8]),
                domain=parts[9],
                trigrams=None,
                action_clusters=[],
                schema_version=version or _extra(0) or "jarvis-save-v2",
                category=_extra(1) or None,
                action=_extra(2) or None,
                runtime_tier=_extra(3) or None,
                health=_extra(4) or None,
                tool=_extra(5) or None,
                predicate=_extra(6) or None,
                pass_type=_extra(7) or None,
                confidence=float(_extra(8)) if _extra(8) else None,
                emotional_input=float(_extra(9)) if _extra(9) else None,
                turn_id=_extra(10) or None,
            )
        parts = s.split(":")
        if len(parts) != 10:
            raise ValueError(f"Invalid save string format: expected 10 segments, got {len(parts)}")
        return cls(
            hex_id=int(parts[0]),
            phase=parts[1],
            voice_weight=int(parts[2]),
            coherence=int(parts[3]),
            chaos=int(parts[4]),
            whimsy=int(parts[5]),
            dark_tone=int(parts[6]),
            porosity=int(parts[7]),
            timestamp=int(parts[8]),
            domain=parts[9],
        )

    @classmethod
    def from_state(
        cls,
        hex_id: int,
        phase: str,
        voice_weight: float,
        coherence: float,
        chaos: float,
        whimsy: float,
        dark_tone: float,
        porosity: float,
        domain: str,
        action_clusters: Optional[List[str]] = None,
    ) -> "AvatarSaveString":
        """Build from raw float values (scales internally)."""
        mapped_phase = PHASE_MAP.get(phase.lower(), 'p')
        upper_bin = f"{hex_id:06b}"[:3]
        lower_bin = f"{hex_id:06b}"[3:]
        trigrams = f"{binary_to_trigram_symbol(upper_bin)}{binary_to_trigram_symbol(lower_bin)}"
        return cls(
            hex_id=hex_id,
            phase=mapped_phase,
            voice_weight=min(9, max(0, int(voice_weight * 10))),
            coherence=min(9, max(0, int(coherence * 10))),
            chaos=min(9, max(0, int(chaos * 10))),
            whimsy=min(9, max(0, int(whimsy * 10))),
            dark_tone=min(9, max(0, int(dark_tone * 10))),
            porosity=min(99, max(0, int(porosity * 100))),
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            domain=domain,
            trigrams=trigrams,
            action_clusters=action_clusters or [],
        )

    def transition_tone(self, other: "AvatarSaveString") -> dict:
        """Compute emotional transition tone between two save strings."""
        return {
            "voice_shift": other.voice_weight - self.voice_weight,
            "coherence_shift": other.coherence - self.coherence,
            "chaos_shift": other.chaos - self.chaos,
            "porosity_shift": other.porosity - self.porosity,
            "phase_changed": self.phase != other.phase,
            "domain_changed": self.domain != other.domain,
            "elapsed_ms": other.timestamp - self.timestamp,
        }


# ── Batch save strings for full 64-hex expansion ──


class BatchSaveString:
    """Compactly encode all 64 hexagram save strings for storage/transmission."""

    def __init__(self, entries: List[AvatarSaveString]) -> None:
        if len(entries) != 64:
            raise ValueError(f"BatchSaveString requires exactly 64 entries, got {len(entries)}")
        self.entries = sorted(entries, key=lambda e: e.hex_id)

    def to_compact(self) -> str:
        """Encode as compact batch with extended metadata."""
        hex_ids = ",".join(f"{e.hex_id:02d}" for e in self.entries)
        phases = ",".join(e.phase for e in self.entries)
        vectors = ",".join(
            f"{e.voice_weight}:{e.coherence}:{e.chaos}:{e.whimsy}:{e.dark_tone}:{e.porosity:02d}"
            for e in self.entries
        )
        timestamps = ",".join(str(e.timestamp) for e in self.entries)
        domains = "~".join(e.domain.replace(",", " ").replace("~", " ") for e in self.entries)
        trigrams = "~".join(e.trigrams or "??" for e in self.entries)
        actions = "~".join("|".join(e.action_clusters or []) for e in self.entries)
        meta_entries = []
        for e in self.entries:
            meta_entries.append(
                ":".join(
                    [
                        e.schema_version or "",
                        e.category or "",
                        e.action or "",
                        e.runtime_tier or "",
                        e.health or "",
                        e.tool or "",
                        e.predicate or "",
                        e.pass_type or "",
                        (f"{e.confidence:.4f}" if e.confidence is not None else ""),
                        (f"{e.emotional_input:.4f}" if e.emotional_input is not None else ""),
                        e.turn_id or "",
                    ]
                )
            )
        meta = "~".join(meta_entries)
        return "|".join([hex_ids, phases, vectors, timestamps, domains, trigrams, actions, meta])

    @classmethod
    def from_compact(cls, s: str) -> "BatchSaveString":
        """Parse compact batch into 64 entries."""
        parts = s.split("|")
        if len(parts) != 8:
            raise ValueError(f"Invalid batch format: expected 8 sections, got {len(parts)}")
        hex_ids = parts[0].split(",")
        phases = parts[1].split(",")
        vectors = parts[2].split(",")
        timestamps = parts[3].split(",")
        domains = parts[4].split("~")
        trigrams = parts[5].split("~")
        actions = parts[6].split("~")
        meta = parts[7].split("~")
        if len(hex_ids) != 64:
            raise ValueError(f"Expected 64 hexagrams, got {len(hex_ids)}")
        entries: List[AvatarSaveString] = []
        for idx in range(64):
            v = vectors[idx].split(":")
            mp = meta[idx].split(":") if idx < len(meta) else []
            def _m(i, default=""):
                return mp[i].strip() if i < len(mp) and mp[i].strip() else default
            entries.append(
                AvatarSaveString(
                    hex_id=int(hex_ids[idx]),
                    phase=phases[idx],
                    voice_weight=int(v[0]),
                    coherence=int(v[1]),
                    chaos=int(v[2]),
                    whimsy=int(v[3]),
                    dark_tone=int(v[4]),
                    porosity=int(v[5]),
                    timestamp=int(timestamps[idx]),
                    domain=domains[idx] if idx < len(domains) else "unknown",
                    trigrams=trigrams[idx] if idx < len(trigrams) else None,
                    action_clusters=actions[idx].split("|") if idx < len(actions) else [],
                    schema_version=_m(0) or "jarvis-save-v2",
                    category=_m(1) or None,
                    action=_m(2) or None,
                    runtime_tier=_m(3) or None,
                    health=_m(4) or None,
                    tool=_m(5) or None,
                    predicate=_m(6) or None,
                    pass_type=_m(7) or None,
                    confidence=float(_m(8)) if _m(8) else None,
                    emotional_input=float(_m(9)) if _m(9) else None,
                    turn_id=_m(10) or None,
                )
            )
        return cls(entries)

    def get_slot(self, hex_id: int) -> AvatarSaveString:
        for e in self.entries:
            if e.hex_id == hex_id:
                return e
        raise KeyError(f"Hexagram {hex_id} not found in batch")

    def dominant(self) -> AvatarSaveString:
        return max(self.entries, key=lambda e: e.voice_weight)


# ── Validation ──


SINGLE_RE_LEGACY = re.compile(
    r"^(\d{2}):([aprf]):([0-9]):([0-9]):([0-9]):([0-9]):([0-9]):(\d{2}):(\d{13}):(.+)$"
)
SINGLE_RE_EXTENDED = re.compile(
    r"^([^|:]+)\|(\d{2}):([aprf]):([0-9]):([0-9]):([0-9]):([0-9]):([0-9]):(\d{2}):(\d{13}):(.+);(.+)$"
)
BATCH_RE = re.compile(
    r"^(\d{2}(?:,\d{2}){63})\|([aprf](?:,[aprf]){63})\|"
    r"([0-9]:[0-9]:[0-9]:[0-9]:[0-9]:\d{2}(?:,[0-9]:[0-9]:[0-9]:[0-9]:[0-9]:\d{2}){63})\|"
    r"(\d{13}(?:,\d{13}){63})\|(.+)\|(.+)\|(.+)\|(.+)$"
)


def validate_save_string(s: str) -> bool:
    if ";" in s:
        payload, extra = s.split(";", 1)
        version = ""
        if "|" in payload:
            version, payload = payload.split("|", 1)
        payload_parts = payload.split(":")
        if len(payload_parts) == 10:
            return len(extra.split(":")) >= 1
        return False
    if "|" in s:
        parts = s.split("|")
        return len(parts) == 8 and len(parts[0].split(",")) == 64
    return bool(SINGLE_RE_LEGACY.match(s))


def parse_save_string(s: str) -> AvatarSaveString | BatchSaveString:
    if "|" in s:
        return BatchSaveString.from_compact(s)
    return AvatarSaveString.from_compact(s)
