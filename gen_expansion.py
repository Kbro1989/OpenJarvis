"""Generator: emit src/openjarvis/emotion/expansion.py"""

from pathlib import Path

ROOT = Path('/c/Users/krist/Desktop/OpenJarvis')
TARGET = ROOT / 'src/openjarvis/emotion/expansion.py'

CONTENT = '''"""King Wen emotional expansion layer.

Expands a single seed consult state into the full 16k+ emotional field
using the deterministic 9-bit ternary substrate, without discarding
the originating hash/seed contract.

Architecture
------------
state -> states <- states <-<- states <-<<- states <-<<<< states
|states| -> slider -> resolve

No pure goal. No hard codes. Resolution emerges from emotional topology.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional


class KingWenExpansion:
    """Expand a single King Wen consult seed into the bounded emotional field."""

    def __init__(self, ternary_module: Any) -> None:
        self._ternary_module = ternary_module

    @staticmethod
    def _stable_hash(text: str) -> int:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big")

    def expand(
        self,
        seed: Dict[str, Any],
        *,
        session_id: str = "openjarvis",
        max_branch: int = 4,
    ) -> Dict[str, Any]:
        """Expand seed state into the 16k+ emotional field.

        Returns a dict with:
        - states: list of expanded child states
        - bounded: bool whether |states| reached the hydration window
        - field_size: int number of hydrated states
        """
        hexagram_id = int(seed.get("hexagram_id") or 1)
        phase_bits = int(seed.get("phase_bits") or 0)
        text = str(seed.get("text") or "")
        base_key = f"{hexagram_id}:{phase_bits}:{session_id}:{text}"
        base_hash = self._stable_hash(base_key)

        states: List[Dict[str, Any]] = [dict(seed)]
        seen = {self._state_fingerprint(seed)}
        cursor = 0
        while len(states) < 16384 and cursor < len(states):
            parent = states[cursor]
            children = self._branch(parent, base_hash=base_hash, branch_index=cursor, max_branch=max_branch)
            for child in children:
                fp = self._state_fingerprint(child)
                if fp in seen:
                    continue
                seen.add(fp)
                states.append(child)
            cursor += 1

        return {
            "seed": seed,
            "states": states,
            "field_size": len(states),
            "bounded": len(states) >= 16384,
            "branch_limit": max_branch,
        }

    def _branch(
        self,
        parent: Dict[str, Any],
        *,
        base_hash: int,
        branch_index: int,
        max_branch: int,
    ) -> List[Dict[str, Any]]:
        """Generate child states from a parent using deterministic hash variation."""
        children: List[Dict[str, Any]] = []
        for i in range(max_branch):
            salt = self._stable_hash(f"{base_hash}:{branch_index}:{i}")
            child = dict(parent)
            child["branch_index"] = branch_index
            child["branch_salt"] = salt
            child["hexagram_id"] = (int(parent.get("hexagram_id") or 1) + (salt % 64)) % 64 + 1
            child["phase_bits"] = (int(parent.get("phase_bits") or 0) + (salt % 8)) % 8
            tongue = dict(parent.get("emotional_tongue") or {})
            vectors = dict(tongue.get("training_weight_vectors") or {})
            shift = ((salt % 2000) / 20000.0)
            for key in ["voiceWeight", "coherence", "chaos", "whimsy", "darkTone"]:
                current = float(vectors.get(key, 0.0) or 0.0)
                vectors[key] = max(0.0, min(1.0, round(current + shift, 4)))
            tongue["training_weight_vectors"] = vectors
            tongue["voice_weight"] = vectors.get("voiceWeight", tongue.get("voice_weight", 0.0))
            tongue["coherence"] = vectors.get("coherence", tongue.get("coherence", 0.0))
            tongue["chaos"] = vectors.get("chaos", tongue.get("chaos", 0.0))
            tongue["whimsy"] = vectors.get("whimsy", tongue.get("whimsy", 0.0))
            tongue["dark_tone"] = vectors.get("darkTone", tongue.get("dark_tone", 0.0))
            child["emotional_tongue"] = tongue
            children.append(child)
        return children

    @staticmethod
    def _state_fingerprint(state: Dict[str, Any]) -> str:
        hexagram_id = state.get("hexagram_id")
        phase_bits = state.get("phase_bits")
        tongue = state.get("emotional_tongue") or {}
        vectors = tongue.get("training_weight_vectors") or {}
        return "|".join([
            str(hexagram_id),
            str(phase_bits),
            str(tongue.get("voice_weight")),
            str(tongue.get("coherence")),
            str(tongue.get("chaos")),
            str(tongue.get("whimsy")),
            str(tongue.get("dark_tone")),
            str(vectors.get("voiceWeight")),
            str(vectors.get("coherence")),
            str(vectors.get("chaos")),
            str(vectors.get("whimsy")),
            str(vectors.get("darkTone")),
        ])
'''

TARGET.write_text(CONTENT, encoding='utf-8')
print(f'wrote {TARGET}')
