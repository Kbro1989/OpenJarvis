"""Intent attempts for the King Wen universal script pipeline.

Each test here is an *intent attempt* — a documented expression of what the
pipeline is supposed to do.  A failing test is an unfulfilled intent, not
broken code.  The test names read as specifications.

Tests that require the live King Wen engine (collapse_full_128) are marked
with ``@pytest.mark.live`` and skipped when the tables are not available.
All other tests use ``force_hex`` to bypass quantum expansion and verify
the dispatcher, modulator, and ledger in isolation.
"""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

# ── Check whether the live King Wen tables are accessible ──────────────────
_KINGWEN_PATH = os.environ.get(
    "KING_WEN_IMMUTABLE_TABLES",
    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES",
)
_TABLES_AVAILABLE = Path(_KINGWEN_PATH).exists()
live = pytest.mark.skipif(
    not _TABLES_AVAILABLE,
    reason="King Wen immutable tables not found at KING_WEN_IMMUTABLE_TABLES",
)


# ── Import the pipeline (may fail if tables unavailable — that is itself intent) ──

try:
    from openjarvis.tools.kingwen_script_pipeline_tool import (
        KingWenScriptPipelineTool,
        SCRIPT_TYPES,
        _modulate,
        _vec,
        _gen_prose,
        _gen_screenplay,
        _gen_dialogue,
        _gen_lyrics,
        _gen_image_prompt,
        _gen_essay,
        _gen_training_record,
        _LEDGER_PATH,
    )
    _TOOL_IMPORTABLE = True
except Exception:
    _TOOL_IMPORTABLE = False

requires_import = pytest.mark.skipif(
    not _TOOL_IMPORTABLE,
    reason="kingwen_script_pipeline_tool not importable",
)


# ──────────────────────────────────────────────────────────────────────────────
# Intent: the tool registers all 9 script types
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__all_nine_script_types_are_registered() -> None:
    """INTENT: the pipeline covers every script medium — no type left behind."""
    expected = {
        "prose", "screenplay", "dialogue", "lyrics",
        "image_prompt", "code", "essay", "training_record", "gutenberg",
    }
    assert expected == SCRIPT_TYPES


# ──────────────────────────────────────────────────────────────────────────────
# Intent: the tool rejects unknown script types cleanly
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
@live
def test_intent__unknown_type_returns_error_not_exception() -> None:
    """INTENT: bad input produces an error result, never a Python exception."""
    tool = KingWenScriptPipelineTool()
    result = tool.run(intent="something", script_type="interpretive_dance")
    assert not result.success
    assert "unknown script_type" in result.content


# ──────────────────────────────────────────────────────────────────────────────
# Intent: empty intent is rejected before hitting the engine
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
@live
def test_intent__empty_intent_is_rejected() -> None:
    """INTENT: the pipeline requires actual intent — empty string is not intent."""
    tool = KingWenScriptPipelineTool()
    result = tool.run(intent="", script_type="prose")
    assert not result.success
    assert "'intent' is required" in result.content


# ──────────────────────────────────────────────────────────────────────────────
# Intent: voice weight modulation preserves all 5 axes
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__modulation_preserves_all_five_axes() -> None:
    """INTENT: no voice weight axis is silently dropped during modulation."""
    raw = {"chaos": 0.5, "whimsy": 0.5, "darkTone": 0.5, "coherence": 0.5, "voiceWeight": 0.5}
    for script_type in SCRIPT_TYPES - {"gutenberg"}:
        modulated = _modulate(raw, script_type, None)
        for axis in ("chaos", "whimsy", "darkTone", "coherence", "voiceWeight"):
            assert axis in modulated, f"axis '{axis}' missing for type '{script_type}'"


# ──────────────────────────────────────────────────────────────────────────────
# Intent: voice override replaces specific axes post-modulation
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__voice_override_replaces_exact_axis() -> None:
    """INTENT: an explicit voice override beats the modulation result."""
    raw = {"chaos": 0.3, "whimsy": 0.3, "darkTone": 0.3, "coherence": 0.8, "voiceWeight": 0.6}
    modulated = _modulate(raw, "prose", {"chaos": 0.99})
    assert modulated["chaos"] == 0.99


# ──────────────────────────────────────────────────────────────────────────────
# Intent: high-coherence modulation dampens chaos (Hamiltonian alignment)
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__high_coherence_dampens_chaos() -> None:
    """INTENT: when coherence dominates, chaos is structurally reduced."""
    raw = {"chaos": 1.0, "whimsy": 0.5, "darkTone": 0.5, "coherence": 0.9, "voiceWeight": 0.7}
    modulated = _modulate(raw, "prose", None)
    # coherence > 0.7 → chaos dampened by 0.7× porosity window
    assert modulated["chaos"] < raw["chaos"]


# ──────────────────────────────────────────────────────────────────────────────
# Intent: each generator returns non-empty text containing the hexagram name
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
@pytest.mark.parametrize("generator,gtype", [
    (_gen_prose,           "prose"),
    (_gen_screenplay,      "screenplay"),
    (_gen_dialogue,        "dialogue"),
    (_gen_lyrics,          "lyrics"),
    (_gen_image_prompt,    "image_prompt"),
    (_gen_essay,           "essay"),
    (_gen_training_record, "training_record"),
])
def test_intent__generator_produces_output_containing_hexagram_name(generator, gtype) -> None:
    """INTENT: every generator embeds the hexagram name in its output."""
    oracle = {
        "hexagram_id": 1,
        "hexagram_name": "The Creative",
        "hexagram_symbol": "☰",
        "action": "ASSERT",
        "category": "sovereign",
        "phase_temporal": "present",
        "emotional_deltas": {},
        "emotional_tongue": {},
        "consensus_porosity_mean": 1,
    }
    mv = {"chaos": 0.1, "whimsy": 0.3, "darkTone": 0.0, "coherence": 0.9, "voiceWeight": 0.8}
    output = generator(oracle, mv, "the nature of pure creation")
    assert isinstance(output, str) and len(output) > 0
    assert "Creative" in output or "ASSERT" in output or "☰" in output, (
        f"{gtype} generator did not embed any recognisable hexagram marker"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Intent: training_record generator produces valid JSON in the output
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__training_record_contains_valid_json() -> None:
    """INTENT: training records must be parseable — they feed Megatron ingestion."""
    oracle = {
        "hexagram_id": 7,
        "hexagram_name": "The Army",
        "hexagram_symbol": "☷",
        "action": "YIELD",
        "category": "boundary",
        "phase_temporal": "transition",
        "consensus_porosity_mean": 2,
        "emotional_tongue": {},
    }
    mv = {"chaos": 0.4, "whimsy": 0.2, "darkTone": 0.5, "coherence": 0.6, "voiceWeight": 0.5}
    output = _gen_training_record(oracle, mv, "coordinated movement under constraint")

    # Extract the JSON block from the markdown code fence
    lines = output.splitlines()
    json_lines = []
    in_block = False
    for line in lines:
        if line.strip() == "```json":
            in_block = True
            continue
        if in_block and line.strip() == "```":
            break
        if in_block:
            json_lines.append(line)

    record = json.loads("\n".join(json_lines))
    assert record["hexagram_id"] == 7
    assert record["domain"] == "kingwen_script_pipeline"
    assert "emotional_weights" in record
    assert record["allowed_bridges"] == ["kingwen_script_pipeline_to_megatron"]


# ──────────────────────────────────────────────────────────────────────────────
# Intent: the ledger file is created and written when the pipeline runs
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
@live
def test_intent__ledger_is_written_after_successful_run(tmp_path) -> None:
    """INTENT: every successful pipeline run appends to the ledger."""
    ledger = tmp_path / "script_pipeline_ledger.jsonl"

    with patch(
        "openjarvis.tools.kingwen_script_pipeline_tool._LEDGER_PATH",
        ledger,
    ):
        tool = KingWenScriptPipelineTool()
        result = tool.run(
            intent="the weight of a single decision",
            script_type="prose",
            force_hex=1,
        )

    assert result.success, result.content
    assert ledger.exists(), "ledger was not created"
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert record["script_type"] == "prose"
    assert record["hexagram_id"] == 1 or record.get("force_hex") == 1


# ──────────────────────────────────────────────────────────────────────────────
# Intent: force_hex bypasses quantum expansion entirely (fast path)
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
@live
def test_intent__force_hex_produces_output_without_multi_pass() -> None:
    """INTENT: force_hex is the fast path — one consult, deterministic, no expansion loop."""
    tool = KingWenScriptPipelineTool()
    result = tool.run(
        intent="structure as a force of nature",
        script_type="essay",
        force_hex=1,       # The Creative — pure yang
        max_passes=1,      # expansion irrelevant, but guard if routing changes
    )
    assert result.success, result.content
    meta = result.metadata or {}
    assert meta.get("expansion_mode", "").startswith("forced_hex")


# ──────────────────────────────────────────────────────────────────────────────
# Intent: the tool spec name matches the TOOL_ID constant
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__tool_spec_name_matches_tool_id() -> None:
    """INTENT: tool registry looks up by name — the spec name must be canonical."""
    tool = KingWenScriptPipelineTool()
    assert tool.spec.name == "kingwen_script_pipeline"


# ──────────────────────────────────────────────────────────────────────────────
# Intent: screenplay generator encodes tension from chaos/coherence ratio
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__screenplay_tension_index_appears_in_output() -> None:
    """INTENT: the screenplay always surfaces its tension index for director review."""
    oracle = {
        "hexagram_id": 51,
        "hexagram_name": "The Arousing",
        "hexagram_symbol": "☳",
        "action": "ASSERT",
        "category": "transformer",
        "phase_temporal": "transition",
    }
    mv = {"chaos": 0.8, "whimsy": 0.3, "darkTone": 0.7, "coherence": 0.4, "voiceWeight": 0.9}
    output = _gen_screenplay(oracle, mv, "the first shock that reorganises everything")
    assert "Tension index" in output
    assert "80" in output or "40" in output   # chaos 80% or coherence 40%


# ──────────────────────────────────────────────────────────────────────────────
# Intent: image prompt contains negative prompt block
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__image_prompt_always_includes_negative_prompt() -> None:
    """INTENT: every image prompt has a negative prompt — incomplete prompts corrupt generation."""
    oracle = {
        "hexagram_id": 22,
        "hexagram_name": "Grace",
        "hexagram_symbol": "☶",
        "action": "ADAPT",
        "category": "boundary",
        "phase_temporal": "crystallization",
    }
    mv = {"chaos": 0.2, "whimsy": 0.6, "darkTone": 0.1, "coherence": 0.85, "voiceWeight": 0.7}
    output = _gen_image_prompt(oracle, mv, "a garden at the edge of the knowable")
    assert "Negative prompt" in output


# ──────────────────────────────────────────────────────────────────────────────
# Intent: lyrics contain verse, chorus, and bridge markers
# ──────────────────────────────────────────────────────────────────────────────

@requires_import
def test_intent__lyrics_structure_has_verse_chorus_bridge() -> None:
    """INTENT: lyrics are structured — not freeform text pretending to be a song."""
    oracle = {
        "hexagram_id": 30,
        "hexagram_name": "The Clinging",
        "hexagram_symbol": "☲",
        "action": "PERSIST",
        "category": "sovereign",
        "phase_temporal": "resolution",
    }
    mv = {"chaos": 0.3, "whimsy": 0.8, "darkTone": 0.4, "coherence": 0.6, "voiceWeight": 0.7}
    output = _gen_lyrics(oracle, mv, "the fire that needs another fire to exist")
    assert "[VERSE]" in output
    assert "[CHORUS]" in output
    assert "[BRIDGE]" in output or "BRIDGE" in output
