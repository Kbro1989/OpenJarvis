"""Tests for :mod:`openjarvis.engine.hermes_runtime`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.engine.hermes_runtime import HermesRuntimeEngine


@pytest.fixture()
def hermestmp(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    (root / "evals" / "backends" / "external" / "_runners").mkdir(parents=True)
    (root / "evals" / "backends" / "external" / "_runners" / "hermes_runner.py").write_text(
        "raise SystemExit(0)", encoding="utf-8"
    )
    monkeypatch.setenv("HERMES_AGENT_PATH", str(root))
    return root


def test_health_true_when_path_and_runner_and_python_exist(hermestmp):
    engine = HermesRuntimeEngine(
        python_executable=Path(sys.executable),
        timeout_seconds=30.0,
    )

    assert engine.health() is True


def test_health_false_when_runner_missing(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    monkeypatch.setenv("HERMES_AGENT_PATH", str(root))
    engine = HermesRuntimeEngine(
        python_executable=Path(sys.executable),
        timeout_seconds=30.0,
    )

    assert engine.health() is False


def test_health_false_when_python_missing(hermestmp):
    engine = HermesRuntimeEngine(
        python_executable=os.devnull,
        timeout_seconds=30.0,
    )

    assert engine.health() is False


def test_generate_full_returns_error_when_runner_missing(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    monkeypatch.setenv("HERMES_AGENT_PATH", str(root))
    engine = HermesRuntimeEngine(
        python_executable=Path(sys.executable),
        timeout_seconds=30.0,
    )
    engine._runner_script = lambda: root / "missing-runner.py"

    result = engine.generate_full(
        [{"role": "user", "content": "ping"}],
        model="hermes-test",
    )

    assert result.get("finish_reason") == "error"
    assert "Hermes runner produced no output JSON" in (result.get("error") or "")


def test_generate_full_passes_expected_environment(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    root.mkdir()
    monkeypatch.setenv("HERMES_AGENT_PATH", str(root))
    captured: dict[str, object] = {}

    def fake_run(cmd, env, stdout, stderr, text, timeout, check):  # pragma: no cover - monkeypatched in test only
        captured["cmd"] = [str(part) for part in cmd]
        captured["env"] = dict(env)
        return type("Proc", (), {"stderr": "", "returncode": 0})()

    monkeypatch.setenv("HERMES_AGENT_PYTHON", "")
    engine = HermesRuntimeEngine(
        python_executable=Path(sys.executable),
        api_mode="chat_completions",
        max_iterations=42,
        timeout_seconds=30.0,
    )
    engine._runner_script = lambda: root / "hermes_runner.py"
    import openjarvis.engine.hermes_runtime as runtime_mod

    monkeypatch.setattr(runtime_mod.subprocess, "run", fake_run)

    engine.generate_full(
        [{"role": "user", "content": "ping"}],
        model="custom-model",
    )

    assert captured["cmd"][0] == str(sys.executable)
    assert captured["env"]["HERMES_AGENT_PATH"] == str(root)
    assert captured["env"]["HERMES_AGENT_PYTHON"] == str(sys.executable)
    assert "--max-iterations" in captured["cmd"]
    assert "42" in captured["cmd"]


def test_engine_registration():
    from openjarvis.core.registry import EngineRegistry
    from openjarvis.engine._discovery import _make_engine
    from openjarvis.engine import hermes_runtime  # noqa: F401 - ensure decorator applied

    EngineRegistry.clear()
    EngineRegistry.register(HermesRuntimeEngine)

    cfg = JarvisConfig()
    cfg.engine.hermes.path = ""
    cfg.engine.hermes.python_executable = str(sys.executable)

    engine = _make_engine("hermes", cfg)

    assert isinstance(engine, HermesRuntimeEngine)
    assert engine.engine_id == "hermes"
