"""jarvis_save_string.py — Generalized save string protocol for OpenJarvis.

Ports the RSC save string pattern from openrsc-vinilla as a universal
state protocol for Jarvis domains: session, King Wen, agent, trace.

Canonical proof: C:/Users/krist/Desktop/openrsc-vinilla/player_save.json
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)

_SAVE_SCHEMA_PATH = Path(__file__).parent.parent / "data" / "jarvis_save_schema.json"
_DEFAULT_SAVE: Dict[str, Any] = {}


def _load_schema() -> Dict[str, Any]:
    if _SAVE_SCHEMA_PATH.exists():
        return json.loads(_SAVE_SCHEMA_PATH.read_text(encoding="utf-8"))
    return {}


def create_save_string(
    username: str = "",
    session_id: str = "",
    world: int = 0,
    plane: int = 0,
    x: int = 0,
    y: int = 0,
    kingwen_hexagram: int = 0,
    kingwen_phase: str = "",
    kingwen_porosity: float = 0.0,
    kingwen_vector: Optional[Dict[str, float]] = None,
    inventory: Optional[list] = None,
    bank: Optional[list] = None,
    skills: Optional[Dict[str, Dict[str, Any]]] = None,
    cache: Optional[Dict[str, Any]] = None,
    traces: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
    appearance: Optional[Dict[str, Any]] = None,
    social: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, str]] = None,
) -> str:
    """Serialize a Jarvis state save to compact string form.

    Mirrors RSC save string encoder: JSON payload → delimited string.
    Format verified against openrsc-vinilla player_save.json structure.
    """
    ts = int(time.time() * 1000)
    payload = {
        "u": user or {"username": username, "id": session_id},
        "p": {"x": x, "y": y, "world": world, "plane": plane},
        "f": 0,
        "cs": 0,
        "s": settings or {},
        "a": appearance or {},
        "so": social or {"friends": [], "ignores": []},
        "inv": inventory or [],
        "bnk": bank or [],
        "qp": 0,
        "qs": {},
        "sk": skills or {},
        "kw": {
            "h": kingwen_hexagram,
            "ph": kingwen_phase,
            "p": kingwen_porosity,
            "v": kingwen_vector or {},
            "c": {}
        },
        "tr": traces or {"session_count": 0, "total_turns": 0},
        "c": cache or {},
        "lid": session_id,
        "wid": 0,
        "id": hash(username) % 1000000,
        "ld": ts,
    }
    return json.dumps(payload, separators=(",", ":"))


def parse_save_string(save_str: str) -> Dict[str, Any]:
    """Deserialize a Jarvis save string back to JSON dict."""
    return json.loads(save_str)


def save_to_disk(save_str: str, path: Optional[Path] = None) -> Path:
    """Persist save string to disk. Atomic write."""
    target = path or (Path.home() / ".openjarvis" / "save_string.jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(save_str + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def load_last_save(path: Optional[Path] = None) -> Optional[str]:
    """Load the most recent save string from disk."""
    target = path or (Path.home() / ".openjarvis" / "save_string.jsonl")
    if not target.exists():
        return None
    lines = target.read_text(encoding="utf-8").splitlines()
    return lines[-1] if lines else None


def save_string_to_delimited(save_dict: Dict[str, Any]) -> str:
    """Encode save dict to compact delimited RSC-style string.

    Parsed from openrsc-vinilla player_save.json:
    [username];pos:(x,y);fat:(fatigue);int:(inv...);bnk:(bank...);
    skl:(skills...);kw:(kingwen...);tr:(traces...)
    """
    parts = []
    if "u" in save_dict:
        parts.append(str(save_dict["u"].get("username", "")))
    if "p" in save_dict:
        pos = save_dict["p"]
        parts.append(f"pos:({pos.get('x',0)},{pos.get('y',0)})")
    if "f" in save_dict:
        parts.append(f"fat:({save_dict['f']})")
    if "kw" in save_dict:
        kw = save_dict["kw"]
        parts.append(f"kw:({kw.get('h',0)},{kw.get('ph','')},{kw.get('p',0.0)})")
    if "inv" in save_dict:
        inv = save_dict["inv"]
        parts.append(f"inv:[{','.join(str(i) for i in inv[:10])}]")
    if "bnk" in save_dict:
        parts.append(f"bnk:[{','.join(str(b) for b in save_dict['bnk'][:10])}]")
    if "sk" in save_dict:
        parts.append(f"skl:[{len(save_dict['sk'])}]")
    if "tr" in save_dict:
        tr = save_dict["tr"]
        parts.append(f"tr:({tr.get('session_count',0)},{tr.get('total_turns',0)})")
    return ";".join(parts)


class JarvisSaveState:
    """Jarvis-native save state manager."""

    def __init__(self, save_path: Optional[Path] = None) -> None:
        self._save_path = save_path or (Path.home() / ".openjarvis" / "save_string.jsonl")
        self._current: Optional[str] = None
        self._current_dict: Dict[str, Any] = {}

    def create(self, **kwargs: Any) -> str:
        self._current = create_save_string(**kwargs)
        self._current_dict = parse_save_string(self._current)
        save_to_disk(self._current, self._save_path)
        return self._current

    def update(self, **kwargs: Any) -> str:
        if not self._current_dict:
            self._current_dict = _load_schema()
        self._current_dict.update(kwargs)
        self._current = json.dumps(self._current_dict, separators=(",", ":"))
        save_to_disk(self._current, self._save_path)
        return self._current

    def load(self) -> Optional[str]:
        self._current = load_last_save(self._save_path)
        if self._current:
            self._current_dict = parse_save_string(self._current)
        return self._current

    def to_delimited(self) -> str:
        if not self._current_dict:
            self._current_dict = _load_schema()
        return save_string_to_delimited(self._current_dict)
