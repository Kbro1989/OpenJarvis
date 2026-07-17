"""OpenJarvis multi-vendor TTS backend registry.

Ported from voicebox backend/backends/*.py capability surface.
Not a GUI frontend port. This is adapter-only: same synthesize()
shape reused by oracle speak, reward sidecar, and training exports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class BackendDescriptor:
    name: str
    module_path: str
    class_name: str
    requires_env: List[str] = field(default_factory=list)
    copyable: bool = True
    notes: str = ""


_REGISTRY: List[BackendDescriptor] = [
    BackendDescriptor(
        name="cloudflare_ai",
        module_path="openjarvis.speech.cloudflare_ai_tts",
        class_name="CloudflareAITTSBackend",
        requires_env=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
        notes="Local fallback if worker /tts unavailable",
    ),
    BackendDescriptor(
        name="cartesia",
        module_path="openjarvis.speech.cartesia_tts",
        class_name="CartesiaTTSBackend",
        requires_env=["CARTESIA_API_KEY"],
        notes="Primary prosthetic adapter path",
    ),
    BackendDescriptor(
        name="kingwen_worker",
        module_path="openjarvis.cli._oracle_speak",
        class_name="_tts_worker_with_vector",
        requires_env=[],
        notes="Remote worker vector path with compliance headers",
    ),
    BackendDescriptor(
        name="chatterbox",
        module_path="voicebox.backend.backends.chatterbox_backend",
        class_name="ChatterboxBackend",
        requires_env=[],
        notes="Local repo-backed; optional local backend",
    ),
    BackendDescriptor(
        name="kokoro",
        module_path="voicebox.backend.backends.kokoro_backend",
        class_name="KokoroBackend",
        requires_env=[],
        notes="Local repo-backed; optional local backend",
    ),
    BackendDescriptor(
        name="qwen_custom_voice",
        module_path="voicebox.backend.backends.qwen_custom_voice_backend",
        class_name="QwenCustomVoiceBackend",
        requires_env=[],
        notes="Local repo-backed; optional custom-voice backend",
    ),
]


def available_backends() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for desc in _REGISTRY:
        missing = [key for key in desc.requires_env if not __import__("os").environ.get(key)]
        out.append(
            {
                "name": desc.name,
                "module_path": desc.module_path,
                "class_name": desc.class_name,
                "copyable": desc.copyable,
                "available": len(missing) == 0,
                "missing_env": missing,
                "notes": desc.notes,
            }
        )
    return out
