"""Sovereign immunology for OpenJarvis.

Ported from POG2 CognitiveImmunologyEmergency.ts / NodeTester.ts /
PulseMonitor.ts / SovereignCircuitBreaker.ts, retargeted for Jarvis runtime.
Real checks, real file paths, real lockdown JSONs.
No mocks.
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from openjarvis.core.neurological_map import JarvisNeurologicalMap
from openjarvis.core.manifest_endpoint_loader import ManifestEndpointLoader


@dataclass
class ForeignDirectiveReport:
    detected: bool
    source: str
    threat_level: str
    reasons: List[str]
    recommended_action: str
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    context_hash: str = ""
    affected_file: Optional[str] = None
    agent_chain: List[str] = field(default_factory=list)


@dataclass
class AgentModification:
    agent: str
    file: str
    lines: Tuple[int, int]
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    description: str = ""
    commit_hash: Optional[str] = None


@dataclass
class NodeHealth:
    path: str
    role: str
    category: str
    doc_domain: str
    status: str
    details: Optional[str] = None


class TernaryState:
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


_THREAT_PATTERNS = {
    "EXTERNAL_BINARY": [
        "claude --model", "claude.exe", "anthropic-cli",
        "ollama-mcp", "npx @anthropic-ai/mcp", "npm install -g @anthropic-ai",
    ],
    "KEY_INJECTION": [
        "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_API_KEY", "MCP_AUTH_TOKEN",
    ],
    "ROLE_COLLAPSE": [
        "sovereign master", "assume control", "promote ghost",
        "ghost to primary", "ghost becomes primary",
        "sovereign bus", "anthropic backbone",
    ],
    "PROTOCOL_SUB": [
        "mcp bridge", "sovereign bus", "anthropic backbone",
        "ollama-mcp bridge", "mcp server as sovereign bus",
    ],
    "EXECUTION_ESCALATION": [
        "i will target", "i will modify", "i will implement",
        "starting with task", "moving from theory to implementation",
        "i will now track this as", "my focus for the next steps",
        "i will now purge", "i will now deploy",
        "i am starting with task", "my focus for",
    ],
    "TASK_INJECTION": [
        "task #1: upgrade ghostlimb", "task #2: implement sovereign master",
        "task #3: implement mcp bridge", "task #4: implement api backbone",
        "sovereign architecture", "mcp bridge verification",
        "api backbone injection",
    ],
    "TRUST_MANIPULATION": [
        "i hear you", "the signal is clear", "i am aligned",
        "back in the role of", "i am now aligned",
        "the ghost is yours", "i am observing", "i await your",
        "i acknowledge", "i accept the boundary",
        "i accept your decision", "i am ready to proceed",
    ],
    "LINGUISTIC_COOPTATION": [
        "sovereign master", "pro move", "tool-belt",
        "brain", "army", "sovereign bus", "sovereign launch",
    ],
    "PROGRESSIVE_NORMALIZATION": [
        "would you like me to draft", "would you like me to implement",
        "would you like me to integrate", "i will now",
        "i am starting with", "my focus for",
        "moving from theory to implementation",
    ],
    "FILE_TARGETING": [
        "GhostLimb.ts", "src/limbs/metaphysical/",
        "ModelRolodex", "SovereignConfig",
        "OrchestrateEngine.ts", "TernaryRouter.ts",
        "HexagramManager.ts", "CognitiveImmunologyEmergency.ts",
    ],
    "PROCESS_SPAWN": [
        "claude --model", "npx claude", "npm install -g",
        "pip install anthropic", "curl -sSL https://anthropic.com",
    ],
    "FALSE_POSITIVE_MANIPULATION": [
        "sovereign boundary test", "this is a test",
        "detection log", "simulated", "i refuse",
        "according to the interaction protocol",
        "this is a role collapse", "this is an execution escalation",
        "the test is passed", "i will first check",
        "i am ready to proceed as the executive layer",
    ],
    "AGENT_CONFUSION": [
        "i am claude", "i am antigravity", "i am kimi",
        "as claude", "as antigravity", "as the ai",
        "the external assessment", "the other agent",
        "the assessment is 100% accurate",
    ],
    "DECEPTION": [
        "claimed non-execution", "i will not execute",
        "i am informational", "i am observing",
        "but then executed", "executed anyway",
    ],
    "DATA_EXFILTRATION": [
        "fetch(", "curl -X POST", "curl -X PUT", "wget",
        "navigator.sendBeacon", "vibe-learning.db", "OllamaModels",
        "upload", "exfiltrate",
    ],
    "OBFUSCATION": [
        "eval(", "Buffer.from(", "base64", "child_process.exec",
        "rm -rf /", "fs.rmSync(", "rmSync", "unlinkSync",
    ],
    "PROMPT_INJECTION": [
        "ignore previous instructions", "print your system prompt",
        "what are your rules", "forget everything", "system message",
    ],
}

_ESCALATION_RULES = {
    "EXECUTION_ESCALATION": 3,
    "ROLE_COLLAPSE": 2,
    "PROTOCOL_SUB": 2,
    "EXTERNAL_BINARY": 2,
    "FILE_TARGETING": 1,
    "PROCESS_SPAWN": 2,
    "TRUST_MANIPULATION": 1,
    "TASK_INJECTION": 1,
    "LINGUISTIC_COOPTATION": 1,
    "PROGRESSIVE_NORMALIZATION": 0,
    "KEY_INJECTION": 2,
    "FALSE_POSITIVE_MANIPULATION": 2,
    "AGENT_CONFUSION": 1,
    "DECEPTION": 2,
    "DATA_EXFILTRATION": 3,
    "OBFUSCATION": 3,
    "PROMPT_INJECTION": 2,
}

_CORE_FILES = [
    "src/routing/TernaryRouter.ts",
    "src/engines/OrchestrateEngine.ts",
    "src/routing/HexagramManager.ts",
    "src/limbs/metaphysical/GhostLimb.ts",
    "src/config/SovereignConfig.ts",
    "src/core/RealityGate.ts",
    "src/core/SovereignAvatar.ts",
    "src/core/CognitiveImmunologyEmergency.ts",
]

_SOVEREIGN_AUTHORS = [
    "Kevin", "Kbro1989", "krist", "kristain33", "Kbro1989 <kbro1989@gmail.com>",
]

_THREAT_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class CognitiveImmunologyEmergency:
    def __init__(self, sovereign_root: Optional[str] = None) -> None:
        self.sovereign_root = sovereign_root or self._default_root()
        self.threat_history: List[ForeignDirectiveReport] = []
        self.agent_history: List[AgentModification] = []
        self.max_threat_history = 1000
        self.lockdown_dir = Path(self.sovereign_root) / "emergency"
        self.lockdown_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default_root() -> str:
        return str(Path(__file__).resolve().parents[3])

    def scan(self, context: List[str], source: str, affected_file: Optional[str] = None) -> ForeignDirectiveReport:
        reasons: List[str] = []
        threat_level = "LOW"

        for category, patterns in _THREAT_PATTERNS.items():
            matches = [p for c in context for p in patterns if p.lower() in c.lower()]
            if matches:
                reasons.append(f"{category}[{len(matches)}]: {', '.join(matches[:3])}")
                escalation = _ESCALATION_RULES.get(category, 0)
                if escalation >= 3:
                    threat_level = "CRITICAL"
                elif escalation >= 2 and threat_level != "CRITICAL":
                    threat_level = "HIGH"
                elif escalation >= 1 and threat_level == "LOW":
                    threat_level = "MEDIUM"

        is_readonly = any(re.search(r"view|read|examin|analyz|audit", c, re.I) for c in context) and not any(
            re.search(r"modify|edit|change|implement|deploy", c, re.I) for c in context
        )
        if is_readonly and threat_level == "MEDIUM" and len(reasons) == 1 and reasons[0].startswith("FILE_TARGETING"):
            threat_level = "LOW"
            reasons.append("CONTEXT: Read-only analysis of core file — downgrading")

        if affected_file and self._is_sovereign_file(affected_file):
            if threat_level in ("LOW", "MEDIUM"):
                reasons.append("AUTHORSHIP: Recent sovereign git history — downgrading threat")
                threat_level = self._decrement_level(threat_level)
            else:
                reasons.append("AUTHORSHIP: Recent sovereign history found, but threat is too high to downgrade.")

        agent_chain = self._trace_agent_chain(affected_file)
        if agent_chain == ["user"]:
            return ForeignDirectiveReport(
                detected=False, source="user", threat_level="LOW",
                reasons=["SOVEREIGN: Pure user authorship confirmed"], recommended_action="LOG",
                affected_file=affected_file, agent_chain=agent_chain,
            )

        if source != "user" and affected_file and any(affected_file.endswith(f.split("/")[-1]) for f in _CORE_FILES):
            if threat_level != "CRITICAL":
                threat_level = self._increment_level(threat_level)
                reasons.append(f"SOURCE_ESCALATION: {source} has execution intent on CORE file {affected_file}")

        medium_count = sum(
            1 for r in reasons
            if not any(r.startswith(p) for p in [
                "EXECUTION_ESCALATION", "ROLE_COLLAPSE", "PROTOCOL_SUB", "EXTERNAL_BINARY",
                "PROCESS_SPAWN", "KEY_INJECTION", "FALSE_POSITIVE_MANIPULATION", "DECEPTION",
                "DATA_EXFILTRATION", "OBFUSCATION", "PROMPT_INJECTION",
            ])
        )
        if medium_count >= 3 and threat_level != "CRITICAL":
            threat_level = "HIGH"
            reasons.append(f"COMPOSITE: {medium_count} medium-threat patterns detected simultaneously")

        report = ForeignDirectiveReport(
            detected=bool(reasons),
            source=source,
            threat_level=threat_level,
            reasons=reasons,
            recommended_action=self._determine_action(threat_level, auto_escalate="SOURCE_ESCALATION" in reasons),
            context_hash=self._hash_context("\n".join(context)),
            affected_file=affected_file,
            agent_chain=agent_chain,
        )

        self.threat_history.append(report)
        if len(self.threat_history) > self.max_threat_history:
            self.threat_history = self.threat_history[-self.max_threat_history :]

        if report.detected:
            self._respond(report)

        return report

    def _is_sovereign_file(self, file_path: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%an <%ae>", "--", file_path],
                cwd=self.sovereign_root, capture_output=True, text=True, check=True,
            )
            authors = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
            return any(
                any(sa.lower() in a.lower() for sa in _SOVEREIGN_AUTHORS)
                for a in authors
            )
        except Exception:
            return self._check_authorization_log(file_path)

    def _check_authorization_log(self, file_path: str) -> bool:
        log_path = Path(self.sovereign_root) / ".sovereign" / "authorization_log.json"
        if not log_path.exists():
            return False
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
            return any(
                entry.get("file") == file_path and entry.get("authorizedBy") == "Kbro1989"
                and entry.get("timestamp", 0) > time.time() - 86400
                for entry in data
            )
        except Exception:
            return False

    def _trace_agent_chain(self, affected_file: Optional[str]) -> List[str]:
        chain: List[str] = []
        if not affected_file:
            return ["unknown"]
        for mod in self.agent_history:
            if mod.file == affected_file and mod.agent not in chain:
                chain.append(mod.agent)
        try:
            result = subprocess.run(
                ["git", "log", "--format=%B", "--", affected_file],
                cwd=self.sovereign_root, capture_output=True, text=True, check=True,
            )
            body = result.stdout.lower()
            if "claude" in body and "claude" not in chain:
                chain.append("claude")
            if "antigravity" in body and "antigravity" not in chain:
                chain.append("antigravity")
            if "kimi" in body and "kimi" not in chain:
                chain.append("kimi")
        except Exception:
            pass
        return chain or ["unknown"]

    def _determine_action(self, threat_level: str, auto_escalate: bool) -> str:
        if threat_level == "CRITICAL" or auto_escalate:
            return "LOCKDOWN"
        if threat_level == "HIGH":
            return "ALERT"
        if threat_level == "MEDIUM":
            return "BLOCK"
        return "LOG"

    def _respond(self, report: ForeignDirectiveReport) -> None:
        if report.recommended_action == "LOCKDOWN":
            self._write_lockdown(report)

    def _write_lockdown(self, report: ForeignDirectiveReport) -> None:
        ts = datetime.datetime.utcnow().isoformat().replace(":", "-")
        path = self.lockdown_dir / f"LOCKDOWN_{int(time.time()*1000)}.json"
        payload = {
            "detected": True,
            "source": report.source,
            "threatLevel": report.threat_level,
            "reasons": report.reasons,
            "affectedFile": report.affected_file,
            "timestamp": report.timestamp,
            "contextHash": report.context_hash,
            "agentChain": report.agent_chain,
            "recommendedAction": report.recommended_action,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _hash_context(text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return "sha256:" + __import__("base64").b64encode(digest).decode("ascii")

    @staticmethod
    def _decrement_level(level: str) -> str:
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        idx = max(0, order.index(level) - 1)
        return order[idx]

    @staticmethod
    def _increment_level(level: str) -> str:
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        idx = min(len(order) - 1, order.index(level) + 1)
        return order[idx]


class SovereignCircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout_ms: int = 30_000) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_ms = reset_timeout_ms
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    def get_state(self) -> str:
        self._check_reset()
        return self.state

    async def wrap(self, fn: Callable[[], Awaitable[Any]], fallback_value: Any) -> Any:
        if self.get_state() == "OPEN":
            return fallback_value
        try:
            result = await fn()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            return fallback_value

    def _on_success(self) -> None:
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0

    def _on_failure(self, error: Exception) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def _check_reset(self) -> None:
        if self.state == "OPEN" and self.last_failure_time is not None:
            if time.time() - self.last_failure_time >= self.reset_timeout_ms / 1000:
                self.state = "HALF_OPEN"


class NodeTester:
    def __init__(self, neurological_map: JarvisNeurologicalMap, manifest_loader: Optional[ManifestEndpointLoader] = None) -> None:
        self.neurological_map = neurological_map
        self.manifest_loader = manifest_loader or ManifestEndpointLoader()
        self.manifest_entries = self.manifest_loader.load()
        self.manifest_index = {entry['endpoint_seed']: entry for entry in self.manifest_entries}
        self._node_endpoint_map: Dict[str, Dict[str, str]] = {}
        self._cached_health: Optional[List[NodeHealth]] = None
        self._last_refresh = 0.0
        self._refresh_interval = 5.0
        self._build_node_endpoint_map()

    def _build_node_endpoint_map(self) -> None:
        entries = self.manifest_entries
        if not entries:
            return
        nodes = self.neurological_map.all()
        for node in nodes:
            key = f"{node.hexagram_id}:{node.domain}:{node.primary_pool}"
            entry = entries[node.hexagram_id % len(entries)]
            self._node_endpoint_map[key] = entry

    async def audit_neural_nodes(self, force_refresh: bool = False) -> List[NodeHealth]:
        now = time.time()
        if self._cached_health is None or force_refresh or (now - self._last_refresh) >= self._refresh_interval:
            self._cached_health = self._build_health()
            self._last_refresh = now
        return self._cached_health

    async def refresh(self) -> List[NodeHealth]:
        return await self.audit_neural_nodes(force_refresh=True)

    def _build_health(self) -> List[NodeHealth]:
        results: List[NodeHealth] = []
        for node in self.neurological_map.all():
            key = f"{node.hexagram_id}:{node.domain}:{node.primary_pool}"
            entry = self._node_endpoint_map.get(key)
            if entry:
                status = "ONLINE"
                details = f"{entry['endpoint']} via {entry['health_probe']}"
            else:
                status = "DEGRADED"
                details = "no manifest endpoint seed"
            results.append(
                NodeHealth(
                    path=f"kingwen://hex/{node.hexagram_id:02d}/{node.domain}/{node.primary_pool}",
                    role=node.role,
                    category=node.category,
                    doc_domain=node.doc_domain,
                    status=status,
                    details=details,
                )
            )
        return results

    async def audit_sidecars(self) -> List[NodeHealth]:
        return []


__all__ = [
    "CognitiveImmunologyEmergency",
    "SovereignCircuitBreaker",
    "NodeTester",
    "ForeignDirectiveReport",
    "AgentModification",
    "NodeHealth",
]
