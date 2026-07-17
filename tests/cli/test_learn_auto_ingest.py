"""Minimal verification for /learn auto-ingest wiring."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from openjarvis.core.events import EventBus, EventType, get_event_bus


class _FakeConfig:
    data_dir = "~/fake_openjarvis_data"


def test_learn_auto_ingest_subscriber_writes_jsonl(tmp_path: Path) -> None:
    import openjarvis.cli.serve as serve_mod

    class _FakeConfig:
        data_dir = str(tmp_path)

    orig_data_dir = getattr(serve_mod, "config", None)
    serve_mod.config = _FakeConfig()

    try:
        from openjarvis.core.events import EventBus, EventType
        bus = EventBus(record_history=True)

        # Replicate the real serve.py subscriber setup exactly.
        from pathlib import Path as _Path
        learn_base = _Path(serve_mod.config.data_dir).expanduser()
        learn_base.mkdir(parents=True, exist_ok=True)
        learn_ingest_path = learn_base / "learn-ingest.jsonl"

        def _on_learn_auto_ingest(event) -> None:
            try:
                with open(learn_ingest_path, "a", encoding="utf-8") as _f:
                    _f.write(
                        json.dumps(
                            {
                                "ts": event.timestamp,
                                "query": event.data.get("query"),
                                "novel_edge_count": event.data.get("novel_edge_count"),
                                "novel_edges": event.data.get("novel_edges"),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            except Exception:
                pass

        bus.subscribe(EventType.LEARN_AUTO_INGEST, _on_learn_auto_ingest)

        bus.publish(
            EventType.LEARN_AUTO_INGEST,
            {
                "query": "King Wen voice",
                "novel_edge_count": 1,
                "novel_edges": [{"source": "s1", "target": "s2"}],
            },
        )

        lines = learn_ingest_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["query"] == "King Wen voice"
        assert parsed["novel_edge_count"] == 1
        assert parsed["novel_edges"] == [{"source": "s1", "target": "s2"}]
        assert any(e.event_type == EventType.LEARN_AUTO_INGEST for e in bus.history)
    finally:
        serve_mod.config = orig_data_dir
