#!/usr/bin/env python3
"""OpenJarvis skill-card expansion route for King Wen consult.

Wires full 64-hex expansion into /oracle and /counsel rendering."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence


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

HEXAGRAM_SYMBOLS = {
    "1": "䷀", "2": "䷁", "3": "䷂", "4": "䷃", "5": "䷄", "6": "䷅", "7": "䷆", "8": "䷇",
    "9": "䷈", "10": "䷉", "11": "䷊", "12": "䷋", "13": "䷌", "14": "䷍", "15": "䷎", "16": "䷏",
    "17": "䷐", "18": "䷑", "19": "䷒", "20": "䷓", "21": "䷔", "22": "䷕", "23": "䷖", "24": "䷗",
    "25": "䷘", "26": "䷙", "27": "䷚", "28": "䷛", "29": "䷜", "30": "䷝", "31": "䷞", "32": "䷟",
    "33": "䷠", "34": "䷡", "35": "䷢", "36": "䷣", "37": "䷤", "38": "䷥", "39": "䷦", "40": "䷧",
    "41": "䷨", "42": "䷩", "43": "䷪", "44": "䷫", "45": "䷬", "46": "䷭", "47": "䷮", "48": "䷯",
    "49": "䷰", "50": "䷱", "51": "䷲", "52": "䷳", "53": "䷴", "54": "䷵", "55": "䷶", "56": "䷷",
    "57": "䷸", "58": "䷹", "59": "䷺", "60": "䷻", "61": "䷼", "62": "䷽", "63": "䷾", "64": "䷿",
}


def build_skill_cards(binary: str) -> List[Dict[str, str]]:
    cards = []
    for idx, bit in enumerate(binary):
        domain = SKILL_CARD_DOMAINS.get(bit, ["unknown"])[idx % len(SKILL_CARD_DOMAINS.get(bit, ["unknown"]))]
        tool = TOOL_NATIVE_MAP.get(domain, "unknown")
        cards.append({
            "slot": idx + 1,
            "bit": bit,
            "domain": domain,
            "jarvis_tool": tool,
            "symbol": "{" if bit == "1" else "[",
        })
    return cards


def render_full_expansion_payload(payload: Dict[str, Any], top_k: int = 12) -> Dict[str, Any]:
    expanded = payload.get("expanded", [])
    consensus = payload.get("consensus", {})
    winner = payload.get("winner") or {}
    weights_by_hex: Dict[int, float] = {}
    vectors = consensus.get("consensus_vector") or {}

    for hex_item in expanded:
        vec = {}
        for phase in hex_item.get("phases", []):
            for k, v in (phase.get("vectors") or {}).items():
                vec[k] = float(v or 0.0)
        dist = sum((vec.get(k, 0.0) - float(vectors.get(k, 0.0) or 0.0))**2 for k in ("chaos", "whimsy", "darkTone", "coherence", "voiceWeight"))**0.5
        weights_by_hex[int(hex_item.get("hexagram_id") or 0)] = 1.0 / (1.0 + dist)

    ranked = sorted(
        [
            {
                "hexagram_id": int(h.get("hexagram_id") or 0),
                "name": (h.get("hexagram_symbols") or {}).get("name", ""),
                "unicode": HEXAGRAM_SYMBOLS.get(str(int(h.get("hexagram_id") or 0)), ""),
                "binary": (h.get("hexagram_symbols") or {}).get("binary", ""),
                "category": (h.get("hexagram_symbols") or {}).get("category", ""),
                "action": (h.get("hexagram_symbols") or {}).get("action", ""),
                "score": weights_by_hex.get(int(h.get("hexagram_id") or 0), 0.0),
                "skill_cards": build_skill_cards((h.get("hexagram_symbols") or {}).get("binary", "")),
            }
            for h in expanded
            if int(h.get("hexagram_id") or 0) > 0
        ],
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "winner": winner,
        "source": payload.get("source", "collapse_full_128"),
        "all_hexagrams_count": len(expanded),
        "all_resolved_count": payload.get("all_resolved_count", len(expanded) * 8),
        "consensus_vector": vectors,
        "top_k": ranked[:top_k],
        "ranked": ranked,
        "team": [
            {
                "hexagram_id": int(h.get("hexagram_id") or 0),
                "name": (h.get("hexagram_symbols") or {}).get("name", ""),
                "unicode": HEXAGRAM_SYMBOLS.get(str(int(h.get("hexagram_id") or 0)), ""),
                "binary": (h.get("hexagram_symbols") or {}).get("binary", ""),
                "skill_cards": build_skill_cards((h.get("hexagram_symbols") or {}).get("binary", "")),
                "phases": h.get("phases", []),
            }
            for h in expanded
            if int(h.get("hexagram_id") or 0) > 0
        ],
    }


def render_pretty_print(payload: Dict[str, Any]) -> str:
    rendered = render_full_expansion_payload(payload)
    lines = []
    lines.append("═══ KING WEN FULL EXPANSION ═══")
    lines.append(f"source={rendered['source']}")
    lines.append(f"winner={rendered['winner']}")
    lines.append(f"consensus_vector={rendered['consensus_vector']}")
    lines.append(f"all_hexagrams_count={rendered['all_hexagrams_count']}")
    lines.append(f"all_resolved_count={rendered['all_resolved_count']}")
    lines.append("")
    lines.append("── TOP K ──")
    for item in rendered["top_k"]:
        cards = " ".join(f"{c['symbol']}{c['jarvis_tool']}" for c in item["skill_cards"])
        lines.append(f"#{item['hexagram_id']:02d} {item['unicode']} {item['name']:<22} score={item['score']:.4f} | {cards}")
    lines.append("")
    lines.append("── FULL TEAM /skill cards ──")
    for item in rendered["team"]:
        cards = []
        for c in item["skill_cards"]:
            cards.append(f"{c['slot']}:{c['symbol']}{c['jarvis_tool']}")
        lines.append(f"#{item['hexagram_id']:02d} {item['unicode']} {item['name']:<22} {' | '.join(cards)}")
    return "\n".join(lines)
