"""King Wen Avatar HTTP Client — Jarvis adherence contract implementation.

Implements the 5-rule adherence contract:
1. Read state before acting
2. Inject after acting
3. Advance tick
4. Query usage
5. Respect domain routing

Usage in chat_cmd.py handlers:
    from openjarvis.server.kingwen.client import KingwenClient

    client = KingwenClient(session_id="user-session-123")

    # Before /oracle or /counsel:
    save_string = await client.read_state()

    # After action completes:
    await client.inject(hexagram_id=7, phase="present", domain="speech/vocabulary")

    # Periodic tick:
    await client.tick(tick_count=tick_counter)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/v1/kingwen/avatar"


class KingwenClient:
    """Dual-mode client for King Wen avatar service endpoints.

    Async methods are for event-loop callers.
    Sync methods are for synchronous callers like REPLs.
    Both still require/return the King Wen response; sync just blocks.
    """

    def __init__(
        self,
        session_id: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 5.0,
    ) -> None:
        self.session_id = session_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._async_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

    # ── Async path ──

    async def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client

    async def close(self) -> None:
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
        if self._sync_client and not self._sync_client.is_closed:
            self._sync_client.close()

    # ── Sync path (for chat REPL) ──

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(timeout=self.timeout)
        return self._sync_client

    # ── Rule 1: Read state before acting ──

    async def read_state(self) -> Dict[str, Any]:
        return self.read_state_sync()

    def read_state_sync(self) -> Dict[str, Any]:
        """GET /state — read current save string + all hexagrams."""
        client = self._get_sync_client()
        url = f"{self.base_url}/{self.session_id}/state"
        try:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Kingwen state read: saveString=%s...", data.get("saveString", "")[:30])
            return data
        except httpx.HTTPError as exc:
            logger.warning("Failed to read Kingwen state: %s", exc)
            return {}

    async def read_save_string(self) -> str:
        return self.read_save_string_sync()

    def read_save_string_sync(self) -> str:
        state = self.read_state_sync()
        return state.get("saveString", "")

    # ── Rule 2: Inject after acting ──

    async def inject(
        self,
        hexagram_id: int,
        phase: str,
        domain: str,
        verb_cluster: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.inject_sync(hexagram_id, phase, domain, verb_cluster, tool)

    def inject_sync(
        self,
        hexagram_id: int,
        phase: str,
        domain: str,
        verb_cluster: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /inject — record action, return new save + transition tone."""
        client = self._get_sync_client()
        url = f"{self.base_url}/{self.session_id}/inject"
        payload = {
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
            data = resp.json()
            logger.debug(
                "Kingwen inject: hex=%d domain=%s newSave=%s...",
                hexagram_id, domain, data.get("newSaveString", "")[:30]
            )
            return data
        except httpx.HTTPError as exc:
            logger.warning("Failed to inject Kingwen state: %s", exc)
            return {}

    # ── Rule 3: Advance tick ──

    async def tick(self, tick_count: int, event: Optional[str] = None) -> Dict[str, Any]:
        return self.tick_sync(tick_count, event)

    def tick_sync(self, tick_count: int, event: Optional[str] = None) -> Dict[str, Any]:
        """POST /tick — advance clock, capture state."""
        client = self._get_sync_client()
        url = f"{self.base_url}/{self.session_id}/tick"
        payload = {"tickCount": tick_count}
        if event:
            payload["event"] = event

        try:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Failed to tick Kingwen state: %s", exc)
            return {}

    # ── Rule 4: Query usage ──

    async def query_usage(self, hexagram_id: int, domain: str) -> Dict[str, Any]:
        return self.query_usage_sync(hexagram_id, domain)

    def query_usage_sync(self, hexagram_id: int, domain: str) -> Dict[str, Any]:
        """GET /usage — query history for hexagram+domain."""
        client = self._get_sync_client()
        url = f"{self.base_url}/{self.session_id}/usage"
        params = {"hexagram_id": hexagram_id, "domain": domain}

        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Failed to query Kingwen usage: %s", exc)
            return {}

    # ── Rule 5: Respect domain routing ──

    async def get_domain(self, world: str) -> Dict[str, Any]:
        return self.get_domain_sync(world)

    def get_domain_sync(self, world: str) -> Dict[str, Any]:
        """GET /domain/{world} — get hexagrams mapped to game domain."""
        client = self._get_sync_client()
        url = f"{self.base_url}/{self.session_id}/domain/{world}"

        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Failed to get Kingwen domain: %s", exc)
            return {}

    async def get_time(self) -> Dict[str, Any]:
        return self.get_time_sync()

    def get_time_sync(self) -> Dict[str, Any]:
        """GET /time — temporal anchor + tick history."""
        client = self._get_sync_client()
        url = f"{self.base_url}/{self.session_id}/time"

        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Failed to get Kingwen time: %s", exc)
            return {}

    # ── Convenience: full adherence cycle ──

    async def adherence_cycle(
        self,
        hexagram_id: int,
        phase: str,
        domain: str,
        verb_cluster: Optional[str] = None,
        tool: Optional[str] = None,
        tick_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Full cycle: read → inject → optional tick → return transition."""
        before = await self.read_state()
        inject_result = await self.inject(hexagram_id, phase, domain, verb_cluster, tool)
        tick_result = {}
        if tick_count is not None:
            tick_result = await self.tick(tick_count)
        return {
            "before": before,
            "inject": inject_result,
            "tick": tick_result,
        }

    def adherence_cycle_sync(
        self,
        hexagram_id: int,
        phase: str,
        domain: str,
        verb_cluster: Optional[str] = None,
        tool: Optional[str] = None,
        tick_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sync full cycle for chat REPL."""
        before = self.read_state_sync()
        inject_result = self.inject_sync(hexagram_id, phase, domain, verb_cluster, tool)
        tick_result = {}
        if tick_count is not None:
            tick_result = self.tick_sync(tick_count)
        return {
            "before": before,
            "inject": inject_result,
            "tick": tick_result,
        }
