#!/usr/bin/env python3
"""Top-K consensus router: King Wen expanded states → Jarvis executable commands."""

from __future__ import annotations

from typing import Any, Dict, List


SKILL_CARD_DOMAINS = {
    "1": ["generation", "initiation", "architecture", "deployment", "api-design", "creative"],
    "0": ["integration", "maintenance", "debugging", "refactoring", "stability", "receptive"],
}

TOOL_NATIVE_MAP = {
    "generation": "codegen",
    "initiation": "scaffold",
    "architecture": "design",
    "deployment": "deploy",
    "api-design": "api",
    "creative": "creative",
    "integration": "integrate",
    "maintenance": "maintain",
    "debugging": "debug",
    "refactoring": "refactor",
    "stability": "stabilize",
    "receptive": "listen",
}


def _hex_tau_score(hex_item: Dict[str, Any], vectors: Dict[str, float]) -> float:
    vec = {}
    for phase in hex_item.get("phases", []):
        for k, v in (phase.get("vectors") or {}).items():
            vec[k] = float(v or 0.0)
    if not vec:
        return 0.0
    dist = sum((vec.get(k, 0.0) - float(vectors.get(k, 0.0) or 0.0))**2 for k in ("chaos", "whimsy", "darkTone", "coherence", "voiceWeight"))**0.5
    return 1.0 / (1.0 + dist)


STAGE_COMMANDS = {
    1: "stabilize",
    2: "integrate",
    3: "debug",
    4: "scaffold",
    5: "design",
    6: "creative",
    7: "api",
    8: "deploy",
    9: "codegen",
}

FALLBACK_HEXAGRAMS = {
    8: {"hexagram_id": 63, "name": "After Completion", "reason": "completion/distribution"},
    9: {"hexagram_id": 1, "name": "The Creative", "reason": "generation/output"},
}


def _binary_domains(binary: str) -> List[str]:
    domains: List[str] = []
    for idx, bit in enumerate(binary):
        bucket = SKILL_CARD_DOMAINS.get(bit, ["unknown"])
        domain = bucket[idx % len(bucket)]
        if domain not in domains:
            domains.append(domain)
    return domains


def top_k_consensus(payload: Dict[str, Any], top_k: int = 5, required_stage_domains: Dict[int, str] | None = None) -> Dict[str, Any]:
    expanded = payload.get("expanded", [])
    consensus = payload.get("consensus", {})
    vectors = consensus.get("consensus_vector") or {}
    scored: List[Dict[str, Any]] = []

    for item in expanded:
        hid = int(item.get("hexagram_id") or 0)
        if hid <= 0:
            continue
        binary = (item.get("hexagram_symbols") or {}).get("binary", "")
        score = _hex_tau_score(item, vectors)
        cards = [
            {
                "slot": idx + 1,
                "bit": bit,
                "domain": SKILL_CARD_DOMAINS.get(bit, ["unknown"])[idx % len(SKILL_CARD_DOMAINS.get(bit, ["unknown"]))],
                "jarvis_tool": TOOL_NATIVE_MAP.get(SKILL_CARD_DOMAINS.get(bit, ["unknown"])[idx % len(SKILL_CARD_DOMAINS.get(bit, ["unknown"]))], "unknown"),
                "symbol": "{" if bit == "1" else "[",
            }
            for idx, bit in enumerate(binary)
        ]
        scored.append({
            "hexagram_id": hid,
            "name": (item.get("hexagram_symbols") or {}).get("name", ""),
            "unicode": (item.get("hexagram_symbols") or {}).get("unicode", ""),
            "binary": binary,
            "score": score,
            "weight": score,
            "skill_cards": cards,
            "jarvis_tools": list({c["jarvis_tool"] for c in cards if c["jarvis_tool"] != "unknown"}),
        })

    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)

    if required_stage_domains:
        covered_domains: set[str] = set()
        selected: List[Dict[str, Any]] = []
        for entry in ranked:
            if len(selected) >= top_k:
                break
            domains = set(_binary_domains(entry.get("binary", "")))
            new_coverage = domains - covered_domains
            if covered_domains and not new_coverage and len(selected) < top_k:
                entry = dict(entry)
                entry["weight"] = float(entry.get("weight", 0.0)) * 1.5
                entry["score"] = entry["weight"]
            selected.append(entry)
            covered_domains.update(domains)

        missing_boost = set(required_stage_domains.values()) - covered_domains
        if missing_boost and len(selected) < len(ranked):
            for missing_domain in missing_boost:
                for entry in ranked:
                    if entry in selected:
                        continue
                    if missing_domain in _binary_domains(entry.get("binary", "")):
                        boosted = dict(entry)
                        boosted["weight"] = float(boosted.get("weight", 0.0)) * 2.0
                        boosted["score"] = boosted["weight"]
                        selected.append(boosted)
                        covered_domains.add(missing_domain)
                        break
        top = selected[:top_k]
    else:
        top = ranked[:top_k]

    all_tools: List[str] = []
    for entry in top:
        all_tools.extend(entry.get("jarvis_tools", []))
    primary_tools = sorted(all_tools, key=all_tools.count, reverse=True)[:6]

    return {
        "source": payload.get("source", "collapse_full_128"),
        "top_k": top_k,
        "emotional_input": payload.get("emotional_input"),
        "hexagrams": top,
        "primary_tools": primary_tools,
        "parallel": True,
        "timeout_ms": 30000,
    }


def commands_from_top_k(top_k_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "kingwen-topk",
        "top_k": top_k_payload.get("top_k"),
        "hexagrams": [
            {
                "id": h.get("hexagram_id"),
                "name": h.get("name"),
                "weight": h.get("weight"),
                "skill_cards": h.get("skill_cards", []),
                "command": "execute_parallel",
            }
            for h in top_k_payload.get("hexagrams", [])
        ],
        "primary_tools": top_k_payload.get("primary_tools", []),
        "parallel": top_k_payload.get("parallel", True),
        "timeout_ms": top_k_payload.get("timeout_ms", 30000),
    }


__all__ = ["top_k_consensus", "commands_from_top_k"]
