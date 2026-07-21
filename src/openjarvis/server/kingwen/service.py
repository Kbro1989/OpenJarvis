"""King Wen Avatar Service — business logic + storage abstraction.

Implements the Jarvis adherence contract:
1. Read state before acting
2. Inject after acting
3. Advance tick
4. Query usage
5. Respect domain routing

All 64 hexagrams are represented simultaneously. Each hexagram has its own
save-string slot. Inject updates one slot; no collapse to a single dominant.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from .save_string import AvatarSaveString, BatchSaveString

logger = logging.getLogger(__name__)

_KING_WEN_COMPLETE_JSON = Path(
    r"C:/Users/krist/Desktop/KING-WEN-I-CHING-IMMUTABLE-TABLES/king_wen_64_verified.json"
)


class StorageBackend(Protocol):
    """Abstract storage — implement with KV, D1, or in-memory."""

    async def get(self, key: str) -> Optional[str]: ...
    async def put(self, key: str, value: str) -> None: ...
    async def list(self, prefix: str) -> List[str]: ...


class InMemoryStorage:
    """Fallback storage for testing."""

    def __init__(self) -> None:
        self._data: Dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    async def put(self, key: str, value: str) -> None:
        self._data[key] = value

    async def list(self, prefix: str) -> List[str]:
        return [k for k in self._data if k.startswith(prefix)]


class AvatarService:
    """King Wen avatar service — stateful session management."""

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage
        self._session_meta: Dict[str, dict] = {}
        self._registry_cache: Optional[Dict[str, Any]] = None

    def _key(self, session_id: str, suffix: str) -> str:
        return f"avatar:{session_id}:{suffix}"

    async def _get_complete_json(self) -> Dict[str, Any]:
        if self._registry_cache is not None:
            return self._registry_cache
        if not _KING_WEN_COMPLETE_JSON.exists():
            self._registry_cache = {}
            return self._registry_cache
        text = _KING_WEN_COMPLETE_JSON.read_text(encoding="utf-8")
        self._registry_cache = json.loads(text)
        return self._registry_cache

    async def _get_shotgun_expansion(self, request_text: str = "", emotional_input: int = 50) -> Dict[str, Any]:
        """Import shotgun expansion lazily to avoid circular imports."""
        try:
            from scripts.full_hexagram_shotgun import shotgun_expand
            return shotgun_expand(request_text, emotional_input)
        except Exception as exc:
            logger.error("Shotgun expansion failed: %s", exc)
            return {"expanded": [], "resolved": []}

    # ── State Management ──

    async def get_state(self, session_id: str) -> dict:
        """GET /state — full 64-hex expansion with live slot state merged."""
        complete = await self._get_complete_json()
        slots_json = await self.storage.get(self._key(session_id, "slots"))
        temporal_json = await self.storage.get(self._key(session_id, "temporal"))

        slots: Dict[int, dict] = {}
        if slots_json:
            try:
                slots = {item["hexagram_id"]: item for item in json.loads(slots_json) if "hexagram_id" in item}
            except Exception:
                slots = {}

        # Always return full 64 hexagrams from the complete registry
        hexagrams_list = complete.get("hexagrams", [])
        merged_hexagrams = []
        for canonical in hexagrams_list:
            hex_id = canonical.get("id")
            live = slots.get(int(hex_id)) if hex_id is not None else None
            merged = dict(canonical)
            if live:
                merged["live"] = live
            merged_hexagrams.append(merged)

        # Batch save string from current slots
        batch = self._slots_to_batch(slots)

        return {
            "saveString": batch.to_compact() if batch else "",
            "allHexagrams": merged_hexagrams,
            "temporalAnchor": json.loads(temporal_json or "{}"),
            "metadata": complete.get("metadata", {}),
            "stateSpaceAnalysis": complete.get("state_space_analysis", {}),
            "structuralProperties": complete.get("structural_properties", {}),
        }

    async def inject(
        self,
        session_id: str,
        hexagram_id: int,
        phase: str,
        domain: str,
        verb_cluster: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> dict:
        """POST /inject — update one hexagram slot, return transition."""
        old_state = await self.get_state(session_id)
        slots_json = await self.storage.get(self._key(session_id, "slots"))
        slots: Dict[int, dict] = {}
        if slots_json:
            try:
                slots = {item["hexagram_id"]: item for item in json.loads(slots_json) if "hexagram_id" in item}
            except Exception:
                slots = {}

        old_slot = slots.get(hexagram_id)
        old_save = AvatarSaveString.from_compact(old_slot["saveString"]) if old_slot and "saveString" in old_slot else AvatarSaveString.from_state(
            hex_id=hexagram_id, phase=phase,
            voice_weight=0.5, coherence=0.5, chaos=0.5,
            whimsy=0.5, dark_tone=0.5, porosity=0.5,
            domain=domain, action_clusters=[verb_cluster] if verb_cluster else [],
        )

        new_save = AvatarSaveString.from_state(
            hex_id=hexagram_id,
            phase=phase,
            voice_weight=old_save.voice_weight / 10,
            coherence=old_save.coherence / 10,
            chaos=old_save.chaos / 10,
            whimsy=old_save.whimsy / 10,
            dark_tone=old_save.dark_tone / 10,
            porosity=old_save.porosity / 100,
            domain=domain,
            action_clusters=[verb_cluster] if verb_cluster else [],
        )

        tone = old_save.transition_tone(new_save)
        actionable_paths = self._derive_actionable_paths(hexagram_id, domain, verb_cluster, tool)
        tool_call = new_save.tool_call

        # Update only this hexagram slot
        slots[hexagram_id] = {
            "hexagram_id": hexagram_id,
            "saveString": new_save.to_compact(),
            "domain": domain,
            "timestamp": new_save.timestamp,
            "tool_call": tool_call,
            "verb_cluster": verb_cluster or "",
            "tool": tool or "",
        }
        await self._persist_slots(session_id, slots)

        # Update usage
        usage_key = self._key(session_id, f"usage:{hexagram_id}:{domain}")
        usage_json = await self.storage.get(usage_key)
        usage = json.loads(usage_json or "{}")
        usage["count"] = usage.get("count", 0) + 1
        usage["lastUsed"] = new_save.timestamp
        usage["hexagramId"] = hexagram_id
        usage["domain"] = domain
        usage["injectSite"] = domain
        if verb_cluster:
            verbs = usage.get("verbClusters", [])
            if verb_cluster not in verbs:
                verbs.append(verb_cluster)
            usage["verbClusters"] = verbs
        if tool:
            skills = usage.get("skills", [])
            if tool not in skills:
                skills.append(tool)
            usage["skills"] = skills
        await self.storage.put(usage_key, json.dumps(usage))

        return {
            "newSaveString": new_save.to_compact(),
            "transitionTone": tone,
            "actionablePaths": actionable_paths,
            "toolCall": tool_call,
        }

    async def tick(self, session_id: str, tick_count: int, event: Optional[str] = None) -> dict:
        """POST /tick — advance clock, capture state for all 64 slots."""
        slots_json = await self.storage.get(self._key(session_id, "slots"))
        slots: Dict[int, dict] = {}
        if slots_json:
            try:
                slots = {item["hexagram_id"]: item for item in json.loads(slots_json) if "hexagram_id" in item}
            except Exception:
                slots = {}

        now = int(time.time() * 1000)
        updated_slots = {}
        for hex_id in range(1, 65):
            slot = slots.get(hex_id)
            if slot and "saveString" in slot:
                save = AvatarSaveString.from_compact(slot["saveString"])
                save = AvatarSaveString(
                    hex_id=save.hex_id,
                    phase=save.phase,
                    voice_weight=save.voice_weight,
                    coherence=save.coherence,
                    chaos=save.chaos,
                    whimsy=save.whimsy,
                    dark_tone=save.dark_tone,
                    porosity=save.porosity,
                    timestamp=now,
                    domain=save.domain,
                    trigrams=getattr(save, 'trigrams', None),
                    action_clusters=getattr(save, 'action_clusters', None) or [],
                )
            else:
                save = AvatarSaveString.from_state(
                    hex_id=hex_id, phase="present",
                    voice_weight=0.5, coherence=0.5, chaos=0.5,
                    whimsy=0.5, dark_tone=0.5, porosity=0.5,
                    domain="speech/vocabulary",
                )
            updated_slots[hex_id] = {
                "hexagram_id": hex_id,
                "saveString": save.to_compact(),
                "domain": save.domain,
                "timestamp": now,
                "tool_call": save.tool_call,
                "verb_cluster": "",
                "tool": "",
            }

        await self._persist_slots(session_id, updated_slots)

        marker = {
            "tick": tick_count,
            "timestamp": now,
            "event": event,
            "slotCount": len(updated_slots),
        }
        journey_key = self._key(session_id, "journey")
        journey_json = await self.storage.get(journey_key)
        journey = json.loads(journey_json or "[]")
        journey.append(marker)
        await self.storage.put(journey_key, json.dumps(journey[-1000:]))

        batch = self._slots_to_batch(updated_slots)
        return {
            "saveString": batch.to_compact() if batch else "",
            "journeyMarkers": journey[-10:],
        }

    async def get_usage(self, session_id: str, hexagram_id: int, domain: str) -> dict:
        """GET /usage — usage history for hexagram+domain."""
        usage_key = self._key(session_id, f"usage:{hexagram_id}:{domain}")
        usage_json = await self.storage.get(usage_key)
        usage = json.loads(usage_json or "{}")
        return {
            "count": usage.get("count", 0),
            "lastUsed": usage.get("lastUsed"),
            "verbClusters": usage.get("verbClusters", []),
            "skills": usage.get("skills", []),
        }

    async def get_time(self, session_id: str) -> dict:
        """GET /time — temporal anchor + tick history."""
        meta_json = await self.storage.get(self._key(session_id, "meta"))
        meta = json.loads(meta_json or "{}")
        journey_json = await self.storage.get(self._key(session_id, "journey"))
        journey = json.loads(journey_json or "[]")
        session_start = meta.get("sessionStart", int(time.time() * 1000))
        elapsed = int(time.time() * 1000) - session_start
        return {
            "sessionStart": session_start,
            "elapsedMs": elapsed,
            "tickCount": len(journey),
            "markers": journey[-20:],
        }

    async def get_domain(self, session_id: str, world: str) -> dict:
        """GET /domain/{world} — hexagrams mapped to game domain."""
        prefix = self._key(session_id, "usage:")
        keys = await self.storage.list(prefix)
        hexagrams = []
        skills = set()
        inject_sites = set()
        for key in keys:
            usage_json = await self.storage.get(key)
            if not usage_json:
                continue
            usage = json.loads(usage_json)
            if usage.get("domain") == world or world in usage.get("domain", ""):
                hexagrams.append({
                    "hexagramId": usage.get("hexagramId"),
                    "count": usage.get("count", 0),
                    "lastUsed": usage.get("lastUsed"),
                })
                skills.update(usage.get("skills", []))
                inject_sites.add(usage.get("injectSite", ""))
        return {
            "domain": world,
            "hexagrams": hexagrams,
            "skills": sorted(skills),
            "injectSites": sorted(filter(None, inject_sites)),
        }

    # ── Internal ──

    async def _persist_slots(self, session_id: str, slots: Dict[int, dict]) -> None:
        await self.storage.put(self._key(session_id, "slots"), json.dumps([dict(s) for s in slots.values()]))
        batch = self._slots_to_batch(slots)
        if batch:
            await self.storage.put(self._key(session_id, "save"), batch.to_compact())
        await self.storage.put(
            self._key(session_id, "meta"),
            json.dumps({"sessionStart": int(time.time() * 1000)}),
        )

    def _slots_to_batch(self, slots: Dict[int, dict]) -> Optional[BatchSaveString]:
        entries = []
        for hex_id in range(1, 65):
            slot = slots.get(hex_id)
            if slot and "saveString" in slot:
                try:
                    entries.append(AvatarSaveString.from_compact(slot["saveString"]))
                except Exception:
                    pass
        if len(entries) != 64:
            return None
        return BatchSaveString(entries)

    def _derive_actionable_paths(
        self,
        hexagram_id: int,
        domain: str,
        verb_cluster: Optional[str],
        tool: Optional[str],
    ) -> List[str]:
        """Derive actionable paths from hexagram + domain + verb + tool."""
        paths = []
        if "speech" in domain:
            paths.append("/oracle/speak")
            paths.append("/counsel/voice")
        if "memory" in domain:
            paths.append("/learn/recall")
            paths.append("/agents/history")
        if "tool" in domain:
            paths.append("/blueprint/run")
            paths.append("/agents/swarm")
        if tool:
            paths.append(f"/tool/{tool}")
        if hexagram_id in [1, 2, 3, 4]:
            paths.append("/build/initiate")
        if hexagram_id in [5, 6, 7, 8]:
            paths.append("/combat/engage")
        return list(dict.fromkeys(paths))
