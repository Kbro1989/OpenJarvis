"""King Wen sync client + full-expansion wire for chat_cmd.py.

Sync client:
- Uses httpx.Client, no asyncio/await.
- Hits the 7 kingwen avatar endpoints.
- collapse_full_128() is an external local call from the immutable tables,
  not from the oracle program.

Full-expansion wire:
- On each message: read current 64-slot state
- Call collapse_full_128() to get 512 resolved states
- Record the full expansion
- Select the dominant state from the 512, not 3→1 oracle collapse
- Inject the result back into the appropriate slot
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ── King Wen immutable tables root ────────────────────────────────────────
KINGWEN_ROOT = os.environ.get(
    "KINGWEN_ROOT",
    r"C:/Users/krist/Desktop/KING-WEN-I-CHING-IMMUTABLE-TABLES",
)
if KINGWEN_ROOT not in sys.path:
    sys.path.insert(0, KINGWEN_ROOT)

DEFAULT_BASE_URL = os.environ.get(
    "KINGWEN_AVATAR_URL",
    "http://localhost:8000/v1/kingwen/avatar",
)


# ── Sync client ────────────────────────────────────────────────────────────

class KingwenClientSync:
    """Synchronous HTTP client for King Wen avatar service endpoints."""

    def __init__(self, session_id: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 5.0) -> None:
        self.session_id = session_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    # ── State ──────────────────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        """GET /state — current save string + all 64 hexagrams."""
        client = self._get_client()
        url = f"{self.base_url}/{self.session_id}/state"
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Kingwen get_state failed: %s", exc)
            return {}

    def read_save_string(self) -> str:
        state = self.get_state()
        return state.get("saveString", "")

    # ── Inject ─────────────────────────────────────────────────────────────

    def inject(
        self,
        hexagram_id: int,
        phase: str,
        domain: str,
        verb_cluster: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /inject — update one hexagram slot, return transition."""
        client = self._get_client()
        url = f"{self.base_url}/{self.session_id}/inject"
        payload: Dict[str, Any] = {
            "hexagram_id": hexagram_id,
            "phase": phase,
            "domain": domain,
        }
        if verb_cluster:
            payload["verb_cluster"] = verb_cluster
        if tool:
            payload["tool"] = tool
        try:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Kingwen inject failed: %s", exc)
            return {}

    # ── Tick ───────────────────────────────────────────────────────────────

    def tick(self, tick_count: int, event: Optional[str] = None) -> Dict[str, Any]:
        """POST /tick — advance clock, refresh all 64 slots."""
        client = self._get_client()
        url = f"{self.base_url}/{self.session_id}/tick"
        payload: Dict[str, Any] = {"tickCount": tick_count}
        if event:
            payload["event"] = event
        try:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Kingwen tick failed: %s", exc)
            return {}

    # ── Usage / domain / time ───────────────────────────────────────────────

    def query_usage(self, hexagram_id: int, domain: str) -> Dict[str, Any]:
        client = self._get_client()
        url = f"{self.base_url}/{self.session_id}/usage"
        params = {"hexagram_id": hexagram_id, "domain": domain}
        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Kingwen query_usage failed: %s", exc)
            return {}

    def get_domain(self, world: str) -> Dict[str, Any]:
        client = self._get_client()
        url = f"{self.base_url}/{self.session_id}/domain/{world}"
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Kingwen get_domain failed: %s", exc)
            return {}

    def get_time(self) -> Dict[str, Any]:
        client = self._get_client()
        url = f"{self.base_url}/{self.session_id}/time"
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Kingwen get_time failed: %s", exc)
            return {}


# ── Full-expansion selectors ───────────────────────────────────────────────

def load_collapse_full_128():
    """Import collapse_full_128 from the immutable tables.

    This is an external local call, not from the oracle program.
    """
    try:
        from emotional_engine import collapse_full_128  # type: ignore
        return collapse_full_128
    except Exception as exc:
        logger.warning("Failed to import collapse_full_128: %s", exc)
        return None


def dominant_from_expansion(expansion: Dict[str, Any]) -> Dict[str, Any]:
    """Select dominant state from full 512-state expansion.

    Selection rule:
    - Prefer resolved vector with highest voiceWeight/coherence sum
    - Fallback to first resolved entry
    - Never collapse to 3 then pick 1
    """
    resolved = expansion.get("resolved") or []
    if not resolved:
        return {}

    def score(entry: Dict[str, Any]) -> float:
        vec = entry.get("resolved_vector") or {}
        voice_weight = float(vec.get("voiceWeight", 0.0) or 0.0)
        coherence = float(vec.get("coherence", 0.0) or 0.0)
        return voice_weight + coherence

    ranked = sorted(resolved, key=score, reverse=True)
    return ranked[0]


def record_full_expansion(
    expansion: Dict[str, Any],
    storage: Any,
    session_id: str,
    tick: int,
) -> str:
    """Persist full expansion payload for this session/tick."""
    path = f"kingwen:expansion:{session_id}:{tick}"
    try:
        storage.put(path, json.dumps(expansion))
    except Exception as exc:
        logger.warning("Failed to record full expansion: %s", exc)
    return path


# ── Full-expansion wire pattern ─────────────────────────────────────────────

class FullExpansionWire:
    """King Wen full-expansion wire for chat handlers.

    Pattern:
    1. Read current 64-slot state
    2. Call collapse_full_128() to get 512 expanded states
    3. Record the full expansion
    4. Select dominant from 512, not 3→1
    5. Inject result back into appropriate slot
    """

    def __init__(self, session_id: str, client: KingwenClientSync, storage: Any) -> None:
        self.session_id = session_id
        self.client = client
        self.storage = storage
        self.collapse_full_128 = load_collapse_full_128()
        self._tick = 0

    def process(self, user_text: str, domain: str, tool: str) -> Dict[str, Any]:
        """Run the full-expansion cycle for one user message."""
        self._tick += 1

        # 1. Read current 64-slot state
        state = self.client.get_state()
        save_string = state.get("saveString", "")
        all_hexagrams = state.get("allHexagrams", [])

        # 2. Call collapse_full_128() to get 512 resolved states
        expansion: Dict[str, Any] = {}
        if self.collapse_full_128 is not None:
            try:
                expansion = self.collapse_full_128(user_text)
            except Exception as exc:
                logger.warning("collapse_full_128 failed: %s", exc)

        if not expansion:
            expansion = {"source": "fallback", "resolved": [], "expanded": []}

        # 3. Record the full expansion
        record_full_expansion(expansion, self.storage, self.session_id, self._tick)

        # 4. Select dominant from 512, not 3→1
        dominant = dominant_from_expansion(expansion)
        hexagram_id = int(dominant.get("hexagram_id") or 1)
        phase = "present"
        if dominant.get("phase_temporal") in ("past", "present", "future"):
            phase = str(dominant["phase_temporal"])

        # 5. Inject back into appropriate slot
        inject_result = self.client.inject(
            hexagram_id=hexagram_id,
            phase=phase,
            domain=domain,
            verb_cluster="consult",
            tool=tool,
        )

        return {
            "tick": self._tick,
            "saveStringBefore": save_string,
            "expansionSource": expansion.get("source", "unknown"),
            "expandedCount": len(expansion.get("expanded", [])),
            "resolvedCount": len(expansion.get("resolved", [])),
            "dominant": dominant,
            "hexagramId": hexagram_id,
            "phase": phase,
            "inject": inject_result,
        }
