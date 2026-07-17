"""Agentic instruction schema — unified contract between ingestion and execution.

Maps King Wen consensus + router evaluation to executable agentic actions.
Scene generation is optional; agentic execution is primary.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


def build_agentic_instruction(
    *,
    instruction_id: Optional[str] = None,
    source_ingestion: str = "",
    oracle_consensus: Dict[str, Any],
    router_evaluation: Dict[str, Any],
    agentic_action: Dict[str, Any],
    scene_generation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build canonical agentic instruction payload.

    Args:
        instruction_id: UUID, generated if omitted.
        source_ingestion: Source handle, e.g. ``gutenberg://5/constitution``.
        oracle_consensus: Full consensus payload from ``collapse_full_128()`` or worker ``/blueprint``.
        router_evaluation: Router output from ``kingwen_voice_router.py`` or worker ``/blueprint``.
        agentic_action: Executable action block.
        scene_generation: Optional creative output block.

    Returns:
        Canonical agentic instruction dict.
    """
    return {
        "instruction_id": instruction_id or str(uuid.uuid4()),
        "source_ingestion": source_ingestion,
        "oracle_consensus": {
            "hexagram": oracle_consensus.get("consensus_hexagram_id"),
            "hexagram_id_mode": oracle_consensus.get("consensus_hexagram_id"),
            "yao_lines": oracle_consensus.get("consensus_yao"),
            "phase_temporal": oracle_consensus.get("consensus_temporal"),
            "phase_temporal_mode": oracle_consensus.get("consensus_temporal"),
            "consensus_vector": oracle_consensus.get("consensus_vector"),
            "emotional_input": oracle_consensus.get("emotional_input"),
            "temporal_distribution": oracle_consensus.get("temporal_distribution"),
            "porosity_mean": oracle_consensus.get("porosity_mean"),
            "porosity_median": oracle_consensus.get("porosity_median"),
            "porosity_mode": oracle_consensus.get("porosity_mode"),
            "vectors_mean": oracle_consensus.get("vectors_mean"),
            "vectors_median": oracle_consensus.get("vectors_median"),
            "vectors_mode": oracle_consensus.get("vectors_mode"),
            "primary_pool_mode": oracle_consensus.get("primary_pool_mode"),
            "secondary_pool_mode": oracle_consensus.get("secondary_pool_mode"),
            "direction_mode": oracle_consensus.get("direction_mode"),
            "yao_label_mode": oracle_consensus.get("yao_label_mode"),
            "past_mode": oracle_consensus.get("past_mode"),
            "present_mode": oracle_consensus.get("present_mode"),
            "future_mode": oracle_consensus.get("future_mode"),
            "reasons": oracle_consensus.get("reasons"),
        },
        "router_evaluation": {
            "advice_hexagram": router_evaluation.get("advice_hexagram"),
            "voice_mode": router_evaluation.get("voice_mode"),
            "priority": router_evaluation.get("priority"),
            "hold_in_state": router_evaluation.get("hold_in_state"),
            "deliberation": router_evaluation.get("deliberation"),
            "fault_vector": int(router_evaluation.get("fault_vector", 0) or 0),
            "crit_countdown": router_evaluation.get("crit_countdown"),
            "reasoning": router_evaluation.get("reasoning"),
        },
        "agentic_action": agentic_action,
        "scene_generation": scene_generation,
    }


def action_from_router(router_evaluation: Dict[str, Any]) -> str:
    """Derive agentic action type from router evaluation.

    Priority 1 / direct user input → consult_and_respond.
    Deliberation / hold → deliberate_and_hold.
    CRIT countdown active → escalate_crit.
    Fault vector nonzero → assess_fault.
    Default → consult_and_respond.
    """
    if router_evaluation.get("deliberation"):
        return "deliberate_and_hold"
    if router_evaluation.get("crit_countdown") is not None and int(router_evaluation.get("crit_countdown", 0) or 0) > 0:
        return "escalate_crit"
    faults = int(router_evaluation.get("fault_vector", 0) or 0)
    if faults != 0:
        return "assess_fault"
    if router_evaluation.get("priority") == 1:
        return "consult_and_respond"
    return "consult_and_respond"


def constraints_for_action(action_type: str, router_evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Derive execution constraints from action type."""
    if action_type == "deliberate_and_hold":
        return {
            "max_tokens": 1024,
            "temperature": 0.1,
            "fabrication_policy": "PROHIBITED",
            "allow_tool_use": False,
            "hold_reason": router_evaluation.get("reasoning"),
        }
    if action_type == "escalate_crit":
        return {
            "max_tokens": 512,
            "temperature": 0.0,
            "fabrication_policy": "PROHIBITED",
            "allow_tool_use": False,
            "crit_countdown": router_evaluation.get("crit_countdown"),
        }
    if action_type == "assess_fault":
        return {
            "max_tokens": 512,
            "temperature": 0.0,
            "fabrication_policy": "PROHIBITED",
            "allow_tool_use": False,
            "fault_vector": int(router_evaluation.get("fault_vector", 0) or 0),
        }
    return {
        "max_tokens": 2048,
        "temperature": 0.3,
        "fabrication_policy": "PROHIBITED",
        "allow_tool_use": True,
    }
