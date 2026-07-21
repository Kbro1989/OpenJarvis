#!/usr/bin/env python3
"""Map King Wen top-K skill cards to POG2-equivalent scene manifests.

Output matches the exact POG2 pipeline manifest schema:
  PipelineManifest -> scenes[] -> SceneArtifact -> scene{} + image/voice paths
"""

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

POG2_STAGE_MAP = {
    1: {"pog2_function": "GutenbergLimb.enable()", "command": "digest_collect", "domain": "listen", "timeout_ms": 5000},
    2: {"pog2_function": "GutenbergLimb.ingestBook(...)", "command": "file_write", "domain": "integrate", "timeout_ms": 30000},
    3: {"pog2_function": "GutenbergLimb.analyzeStyle(bookId)", "command": "think", "domain": "debug", "timeout_ms": 10000},
    4: {"pog2_function": "getSequencedSegments(...)", "command": "shell_exec", "domain": "scaffold", "timeout_ms": 15000},
    5: {"pog2_function": "StoryboardLimbV2.generateScenes(...)", "command": "think", "domain": "design", "timeout_ms": 30000},
    6: {"pog2_function": "ChromanumberEngine.generateVisualSubstrate(...)", "command": "think", "domain": "creative", "timeout_ms": 60000},
    7: {"pog2_function": "VoiceLimb.narrate(...)", "command": "web_search", "domain": "api", "timeout_ms": 45000},
    8: {"pog2_function": "VideoAssemblerLimb.assemble(...)", "command": "shell_exec", "domain": "deploy", "timeout_ms": 120000},
    9: {"pog2_function": "YouTubeLimb.upload(...)", "command": "code_interpreter", "domain": "codegen", "timeout_ms": 60000},
}

JARVIS_TOOL_REGISTRY = {
    "codegen": "code_interpreter",
    "scaffold": "shell_exec",
    "design": "think",
    "deploy": "shell_exec",
    "api": "web_search",
    "creative": "think",
    "integrate": "file_write",
    "maintain": "file_read",
    "debug": "think",
    "refactor": "code_interpreter",
    "stabilize": "digest_collect",
    "listen": "file_read",
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


def _binary_domains(binary: str) -> List[str]:
    domains: List[str] = []
    for idx, bit in enumerate(binary):
        bucket = SKILL_CARD_DOMAINS.get(bit, ["unknown"])
        domain = bucket[idx % len(bucket)]
        if domain not in domains:
            domains.append(domain)
    return domains


def _build_skill_cards(binary: str) -> List[Dict[str, str]]:
    cards = []
    for idx, bit in enumerate(binary):
        bucket = SKILL_CARD_DOMAINS.get(bit, ["unknown"])
        domain = bucket[idx % len(bucket)]
        cards.append({
            "slot": idx + 1,
            "bit": bit,
            "domain": domain,
            "jarvis_tool": TOOL_NATIVE_MAP.get(domain, "unknown"),
            "symbol": "{" if bit == "1" else "[",
        })
    return cards


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
        cards = _build_skill_cards(binary)
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


def map_skill_cards_to_commands(skill_cards: List[Dict[str, str]]) -> Dict[str, Any]:
    commands: List[Dict[str, Any]] = []
    guidance: List[str] = []
    seen_tools = set()
    for card in skill_cards:
        domain = card.get("domain", "")
        jarvis_tool = card.get("jarvis_tool")
        if not jarvis_tool or jarvis_tool == "unknown":
            continue
        executable = JARVIS_TOOL_REGISTRY.get(jarvis_tool)
        if executable and executable not in seen_tools:
            commands.append({
                "slot": card.get("slot"),
                "bit": card.get("bit"),
                "domain": domain,
                "jarvis_tool": jarvis_tool,
                "command": executable,
                "symbol": card.get("symbol"),
            })
            seen_tools.add(executable)
        guidance.append(f"{domain}:{jarvis_tool}")

    return {
        "commands": commands,
        "guidance": guidance,
        "executable_tools": sorted(seen_tools),
    }


def _stage_seed_commands(commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    present = {c["command"] for c in commands}
    seeded = []
    for stage_num, meta in POG2_STAGE_MAP.items():
        if meta["command"] not in present:
            seeded.append({
                "stage": stage_num,
                "pog2_function": meta["pog2_function"],
                "command": meta["command"],
                "domain": meta["domain"],
                "timeout_ms": meta["timeout_ms"],
                "source": "stage-seed",
            })
    return seeded


def top_k_executable_plan(top_k_payload: Dict[str, Any]) -> Dict[str, Any]:
    hexagrams = top_k_payload.get("hexagrams", [])
    planned: List[Dict[str, Any]] = []
    global_commands: List[Dict[str, Any]] = []
    global_guidance: List[str] = []
    seen_global = set()
    for hex_item in hexagrams:
        skill_cards = hex_item.get("skill_cards", [])
        mapped = map_skill_cards_to_commands(skill_cards)
        plan_entry = {
            "hexagram_id": hex_item.get("hexagram_id"),
            "name": hex_item.get("name"),
            "binary": hex_item.get("binary"),
            "score": hex_item.get("score"),
            "commands": mapped["commands"],
            "guidance": mapped["guidance"],
        }
        planned.append(plan_entry)
        for cmd in mapped["commands"]:
            key = cmd["command"]
            if key not in seen_global:
                global_commands.append(cmd)
                seen_global.add(key)
        global_guidance.extend(mapped["guidance"])

    seeded = _stage_seed_commands(global_commands)
    all_commands = list(global_commands) + seeded

    return {
        "source": "kingwen-receptive-map",
        "top_k": top_k_payload.get("top_k"),
        "emotional_input": top_k_payload.get("emotional_input"),
        "hexagram_plans": planned,
        "executable_tools": sorted({c["command"] for c in all_commands}),
        "commands": all_commands,
        "guidance": global_guidance,
        "seeded_stages": seeded,
        "pipeline_stage_map": POG2_STAGE_MAP,
        "parallel": top_k_payload.get("parallel", True),
        "timeout_ms": sum(meta["timeout_ms"] for meta in POG2_STAGE_MAP.values()),
    }


def _to_pog2_scene(index: int, hex_item: Dict[str, Any], emotion: Dict[str, float], stage: int = 1) -> Dict[str, Any]:
    binary = hex_item.get("binary", "") or ""
    cards = _build_skill_cards(binary)
    domain = cards[0]["domain"] if cards else "unknown"
    jarvis_tool = cards[0]["jarvis_tool"] if cards else "unknown"

    description = f"Scene {index}: {hex_item.get('name', 'Hexagram')} emotional state"
    visual_prompt = (
        f"Scene {index} visual prompt from King Wen hexagram {hex_item.get('hexagram_id')} "
        f"({hex_item.get('name')}) with domain {domain}, "
        f"visualPrompt placeholder for image generation"
    )
    style_influence = (
        f"King Wen style influence for hexagram {hex_item.get('hexagram_id')}: "
        f"dominant domain {domain}, jarvis_tool {jarvis_tool}"
    )
    prosody = {
        "chaos": float(emotion.get("chaos", 0.0) or 0.0),
        "whimsy": float(emotion.get("whimsy", 0.0) or 0.0),
        "darkTone": float(emotion.get("darkTone", 0.0) or 0.0),
        "coherence": float(emotion.get("coherence", 0.0) or 0.0),
        "voiceWeight": float(emotion.get("voiceWeight", 0.0) or 0.0),
    }

    return {
        "index": index,
        "scene": {
            "index": index,
            "description": description,
            "visualPrompt": visual_prompt,
            "styleInfluence": style_influence,
            "prosody": prosody,
        },
        "imagePath": None,
        "imageStatus": "pending",
        "voicePath": None,
        "voiceStatus": "pending",
        "soundtrackStatus": "pending",
        "soundtrackPath": None,
        "hexagram_id": hex_item.get("hexagram_id"),
        "binary": binary,
        "stage": stage,
        "pog2_function": POG2_STAGE_MAP.get(stage, {}).get("pog2_function", ""),
        "jarvis_command": POG2_STAGE_MAP.get(stage, {}).get("command", jarvis_tool),
        "domain": domain,
        "timeout_ms": POG2_STAGE_MAP.get(stage, {}).get("timeout_ms", 30000),
    }


def build_pipeline_manifest(top_k_payload: Dict[str, Any], book_id: int = 0, book_title: str = "") -> Dict[str, Any]:
    hexagrams = top_k_payload.get("hexagrams", [])
    consensus = top_k_payload.get("consensus", {}) or {}
    emotion = consensus.get("consensus_vector") or {}

    scenes: List[Dict[str, Any]] = []
    for idx, hex_item in enumerate(hexagrams, 1):
        stage = ((idx - 1) % 9) + 1
        scenes.append(_to_pog2_scene(idx, hex_item, emotion, stage=stage))

    total_timeout = sum(POG2_STAGE_MAP.get(((idx - 1) % 9) + 1, {}).get("timeout_ms", 30000) for idx in range(1, len(scenes) + 1))

    return {
        "bookId": book_id,
        "bookTitle": book_title or f"King Wen Pipeline {book_id}",
        "createdAt": __import__("time").time() * 1000,
        "pipelinePath": "",
        "totalScenes": len(scenes),
        "successfulImages": 0,
        "successfulVoice": 0,
        "scenes": scenes,
        "status": "partial",
        "videoPath": None,
        "characterMap": {},
        "source": "kingwen-receptive-map",
        "top_k": top_k_payload.get("top_k"),
        "emotional_input": top_k_payload.get("emotional_input"),
        "primary_tools": top_k_payload.get("primary_tools", []),
        "parallel": top_k_payload.get("parallel", True),
        "total_stage_timeout_ms": total_timeout,
        "stage_count": 9,
        "pipeline_assembly": "stitch_full_movie_at_end",
    }


__all__ = [
    "top_k_consensus",
    "commands_from_top_k",
    "map_skill_cards_to_commands",
    "_stage_seed_commands",
    "top_k_executable_plan",
    "_to_pog2_scene",
    "build_pipeline_manifest",
    "POG2_STAGE_MAP",
    "JARVIS_TOOL_REGISTRY",
]
