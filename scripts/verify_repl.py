"""verify_repl.py

Runs the live ``openjarvis.cli`` REPL through subprocess stdin pipe,
exercises the slash registry matrix, asserts expected outputs, and
returns exit code 0/1 for CI integration.

Usage:
    PYTHONPATH=src python scripts/verify_repl.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap


PYTHON = sys.executable
CMD = [PYTHON, "-m", "openjarvis.cli"]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    # src layout, not installed editable
    env.setdefault("PYTHONPATH", "src")
    return env


def _script(commands: list[str]) -> str:
    lines = ["/help", "/history"]
    lines.extend(commands)
    lines.append("/quit")
    return textwrap.dedent("\n".join(lines + [""]))


def run_case(
    name: str,
    commands: list[str],
    assertions: list[tuple[str, str]],
) -> bool:
    script = _script(commands)
    proc = subprocess.run(
        CMD,
        input=script,
        env=_env(),
        text=True,
        capture_output=True,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
    )
    ok = proc.returncode == 0
    computed = {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    print(f"[REPL] {name}: rc={proc.returncode}")

    for needle, label in assertions:
        present = needle in proc.stdout or needle in proc.stderr
        status = "ok" if present else "MISSING"
        print(f"  {status}: {label} => {needle!r}")
        if not present:
            ok = False
    return ok


def main() -> int:
    cases = [
        (
            "slash_registry",
            ["/goal", "/snapshot", "/rollback", "/queue", "/steer", "/webhook", "/kanban", "/curator"],
            [
                ("/quit", "help lists /quit"),
                ("Goal set: /goal", "/goal handler fired"),
                ("Snapshot created:", "/snapshot handler fired"),
                ("Rolled back to /rollback", "/rollback handler fired"),
                ("Queued: /queue", "/queue handler fired"),
                ("Steer set: /steer", "/steer handler fired"),
                ("Webhook /webhook executed.", "/webhook handler fired"),
                ("Kanban board displayed.", "/kanban handler fired"),
                ("Skill maintenance scan complete.", "/curator handler fired"),
            ],
        ),
        (
            "builtin_handlers",
            ["/clear", "/history", "/models"],
            [
                ("History cleared.", "/clear handler fired"),
                ("/history", "/history still present"),
                ("ModelRolodex", "/models still present"),
            ],
        ),
    ]

    all_ok = True
    for name, commands, assertions in cases:
        all_ok &= run_case(name, commands, assertions)

    if all_ok:
        print("[REPL] PASS")
    else:
        print("[REPL] FAIL")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
