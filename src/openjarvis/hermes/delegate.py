"""
JARVIS → Hermes Delegate
=========================
JARVIS calls this to hand off tasks to the Hermes agent stack.
Posts a task payload to the Hermes webhook on localhost:7891.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Dict


HERMES_WEBHOOK = "http://localhost:7891/jarvis/event"


def delegate(task_type: str, payload: Dict[str, Any], priority: str = "normal") -> dict:
    event = {
        "event_type": "delegate_to_hermes",
        "timestamp": time.time(),
        "payload": {
            "task_type": task_type,
            "data": payload,
            "priority": priority,
        },
    }
    body = json.dumps(event).encode("utf-8")
    try:
        req = urllib.request.Request(
            HERMES_WEBHOOK,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return {"status": "delegated", "http_code": resp.status}
    except urllib.error.URLError as e:
        return {"status": "hermes_offline", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: delegate.py <task_type> [json_payload]"}))
        sys.exit(1)
    task_type = sys.argv[1]
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = delegate(task_type, payload)
    print(json.dumps(result, indent=2))
