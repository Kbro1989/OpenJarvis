#!/usr/bin/env python3
"""Quick verification for Avalokiteshvara avatar endpoint logic."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("C:/Users/krist/Desktop/OpenJarvis/src")))

from openjarvis.server.api_routes import _load_avalokiteshvara_arm  # noqa: E402


def main() -> int:
    arm = _load_avalokiteshvara_arm(1)
    assert arm, "hexagram 1 arm missing"
    assert arm.get("mantra"), "missing mantra"
    assert arm.get("mudra"), "missing mudra"
    print("arm_hex1=" + repr(arm))

    empty = _load_avalokiteshvara_arm(9999)
    assert empty == {}, "unexpected arm for invalid hex"
    print("arm_invalid=empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
