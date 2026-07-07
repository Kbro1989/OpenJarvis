import json
from pathlib import Path
from typing import Any, Dict, List
from openjarvis.core.types import Trace

def export_to_megatron_jsonl(
    traces: List[Trace], 
    output_path: Path, 
    user_specs_context: str = ""
) -> None:
    """
    Exports a batch of Traces into Megatron-LM compatible JSONL format.
    
    Megatron typically expects text datasets for causal language modeling to look like:
    {"text": "the full sequence context"}
    
    For our emotionally weighted / porous setup, we format the document to explicitly
    state the porosity, the hexagram state, the user spec (compressed binary memory), 
    and the final action sequence, allowing the model to learn the quantum-collapse 
    transition from ambiguous user intent to strict execution.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "a", encoding="utf-8") as f:
        for trace in traces:
            # Gather state from the trace
            collapse_delta = 0.0
            porosity = 0.0
            hexagram = "UNKNOWN"
            
            # Find the step where the collapse occurred (usually a KINGWEN_VOICE or respond step)
            for step in trace.steps:
                if getattr(step, "quantum_collapse_delta", None) is not None:
                    collapse_delta = step.quantum_collapse_delta
                if getattr(step, "porosity_ratio", None) is not None:
                    porosity = step.porosity_ratio
                if getattr(step, "hexagram_name", None) is not None:
                    hexagram = step.hexagram_name
                elif getattr(step, "hexagram_id", None) is not None:
                    hexagram = f"HEX_{step.hexagram_id}"
            
            # We treat the text as a structured block the model learns to predict
            # It starts with context (the user specs), the user query, the internal state, 
            # and ends with the collapsed response.
            
            structured_text = (
                f"<|system|>\nUser Specification Context:\n{user_specs_context}\n"
                f"<|user|>\n{trace.query}\n"
                f"<|oracle_state|>\n"
                f"Porosity Ratio: {porosity:.4f}\n"
                f"Quantum Collapse Delta: {collapse_delta:.4f}\n"
                f"Resolved Hexagram: {hexagram}\n"
                f"<|assistant|>\n{trace.result}\n<|endoftext|>"
            )
            
            # Additional metadata can be passed for custom Megatron dataloaders 
            # (e.g. for PPO reward mapping if we choose to use RLHF).
            record: Dict[str, Any] = {
                "text": structured_text,
                "weight": collapse_delta,  # Higher collapse delta -> stronger learning signal
                "porosity": porosity,
                "hexagram": hexagram,
                "trace_id": trace.trace_id,
                "metadata": trace.metadata
            }
            
            f.write(json.dumps(record) + "\n")
