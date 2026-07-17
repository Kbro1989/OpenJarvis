"""kingwen_learning_tools.py — Megatron/learning pipeline tools registered in Jarvis.

Tools registered here:
  - kingwen_pseudopod_ingest    : Ingest Jarvis traces into King Wen training-shaped JSONL rows
  - kingwen_corpus_validate     : Validate King Wen corpus integrity (schema drift, missing fields)
  - kingwen_training_export     : Export Voicebox training vectors + profile payloads from all 512 states
  - kingwen_megatron_slice      : Slice and format training corpus for Megatron-LM ingestion
  - kingwen_fan_out_digest      : Run the full fan-out learn batch on wiki-math pages

Ports Megatron-LM training scaffolding from:
  - openjarvis/learning/kingwen_pseudopod_ingest.py
  - KING-WEN-I-CHING-IMMUTABLE-TABLES/scripts/export_voicebox_training.py
  - KING-WEN-I-CHING-IMMUTABLE-TABLES/learn/scripts/fan_out_learn.py

No mocks. All file paths are real on this machine.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

def _ok(tool_id: str, output: str, metadata: dict = None) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=output, success=True, metadata=metadata or {})


def _err(tool_id: str, msg: str) -> ToolResult:
    return ToolResult(tool_name=tool_id, content=f"ERROR: {msg}", success=False)


LOGGER = logging.getLogger(__name__)

KING_WEN_ROOT = Path(r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES")
OPENJARVIS_LEARNING_DIR = Path.home() / ".openjarvis" / "learning"


# ── Tool: Pseudopod Ingest ────────────────────────────────────────────────────

@ToolRegistry.register("kingwen_pseudopod_ingest")
class KingWenPseudopodIngestTool(BaseTool):
    """Ingest live Jarvis traces into King Wen pseudopod JSONL training rows."""

    tool_id = "kingwen_pseudopod_ingest"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_pseudopod_ingest",
            description=(
                "Reads live Jarvis trace_store records and agent messages and transforms them "
                "into King Wen pseudopod JSONL training rows with domain labels, session IDs, "
                "porosity weights, hexagram IDs, and voice vectors. Writes to "
                "~/.openjarvis/learning/kingwen_pseudopod_ingest.jsonl."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of traces to ingest per pass.",
                        "default": 200,
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory to write JSONL output. Defaults to ~/.openjarvis/learning.",
                        "default": "",
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        limit = int(params.get("limit", 200))
        output_dir_str = str(params.get("output_dir", ""))
        output_dir = Path(output_dir_str) if output_dir_str else OPENJARVIS_LEARNING_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from openjarvis.traces.store import TraceStore
            from openjarvis.learning.kingwen_pseudopod_ingest import KingWenPseudopodIngestor

            trace_store = TraceStore(str(Path.home() / ".openjarvis" / "traces.db"))
            ingestor = KingWenPseudopodIngestor(trace_store=trace_store, output_dir=output_dir)
            out_path = ingestor.ingest_traces(limit=limit)

            return _ok(self.tool_id, f'Ingested {ingestor.rows_written} rows → {out_path}', {'rows_written': ingestor.rows_written, 'output_path': str(out_path), 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_pseudopod_ingest failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Corpus Integrity Validator ─────────────────────────────────────────

@ToolRegistry.register("kingwen_corpus_validate")
class KingWenCorpusValidateTool(BaseTool):
    """Validate King Wen corpus JSONL files for schema drift and missing fields."""

    tool_id = "kingwen_corpus_validate"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_corpus_validate",
            description=(
                "Scans King Wen corpus JSONL files in the learning directory for schema drift, "
                "missing required fields, and JSON decode errors. Returns per-file counts and "
                "a list of all detected issues."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "base_dir": {
                        "type": "string",
                        "description": "Directory containing corpus JSONL files. Defaults to ~/.openjarvis/learning.",
                        "default": "",
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        base_dir_str = str(params.get("base_dir", ""))
        base_dir = Path(base_dir_str) if base_dir_str else OPENJARVIS_LEARNING_DIR

        try:
            from openjarvis.learning.kingwen_pseudopod_ingest import CorpusIntegrityValidator

            validator = CorpusIntegrityValidator(base_dir=base_dir)
            results = validator.validate_all()

            issue_count = results.get("issue_count", 0)
            summary = f"Validated {len(results.get('files', {}))} corpus files — {issue_count} issue(s) found"

            return _ok(self.tool_id, summary, {**results, 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_corpus_validate failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Voicebox Training Export ───────────────────────────────────────────

@ToolRegistry.register("kingwen_training_export")
class KingWenTrainingExportTool(BaseTool):
    """Export Voicebox training vectors and profile payloads from all 512 oracle states."""

    tool_id = "kingwen_training_export"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_training_export",
            description=(
                "Runs the King Wen → Voicebox training exporter over all 512 oracle states "
                "using the specified emotional input. Writes voicebox_training_vector.json and "
                "voicebox_profile_payload.json to the King Wen DATASETS/ directory."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "emotional_input": {
                        "type": "integer",
                        "description": "Emotional input seed [0–100]. Default 50 = neutral.",
                        "default": 50,
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Output directory. Defaults to KING-WEN-IMMUTABLE-TABLES/DATASETS.",
                        "default": "",
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        emotional_input = int(params.get("emotional_input", 50))
        output_dir_str = str(params.get("output_dir", ""))
        output_dir = Path(output_dir_str) if output_dir_str else (KING_WEN_ROOT / "DATASETS")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from openjarvis.emotion.kingwen_engine_adapter import collapse_full_128, HEXAGRAM_BASE, PHASE_INFO

            collapse = collapse_full_128(emotional_input=emotional_input)
            resolved: List[Dict[str, Any]] = collapse.get("resolved") or []
            expanded: List[Dict[str, Any]] = collapse.get("expanded") or []

            # Build per-hexagram vector mean
            by_hex: Dict[int, List[Dict[str, Any]]] = {}
            for item in resolved:
                hid = int(item.get("hexagram_id") or 0)
                by_hex.setdefault(hid, []).append(item)

            def _vec_mean(rows: List[Dict[str, Any]]) -> Dict[str, float]:
                keys = ["chaos", "whimsy", "darkTone", "coherence", "voiceWeight"]
                acc = {k: 0.0 for k in keys}
                for row in rows:
                    rv = row.get("resolved_vector") or {}
                    for k in keys:
                        acc[k] += float(rv.get(k, 0.0))
                n = float(len(rows)) or 1.0
                return {k: round(v / n, 6) for k, v in acc.items()}

            vector_rows = []
            profile_payloads = []
            for item in expanded:
                hid = int(item.get("hexagram_id") or 0)
                inject = item.get("inject_site") or {}
                hex_resolved = by_hex.get(hid, [])
                vec_mean = _vec_mean(hex_resolved)
                phase_bits = int(item.get("phase_bits") or 0)
                temporal = (PHASE_INFO.get(phase_bits) or {}).get("temporal", "present")
                hex_info = HEXAGRAM_BASE.get(hid, {})

                vector_rows.append({
                    "hexagram_id": hid,
                    "hexagram_name": hex_info.get("name", ""),
                    "phase_bits": phase_bits,
                    "temporal": temporal,
                    "emotional_input": emotional_input,
                    "inject_site": inject,
                    "vector_mean": vec_mean,
                })

                profile_payloads.append({
                    "profile_id": f"kingwen_{hid}_{temporal}",
                    "hexagram_id": hid,
                    "hexagram_name": hex_info.get("name", ""),
                    "temporal_phase": temporal,
                    "action": hex_info.get("action", ""),
                    "category": hex_info.get("category", ""),
                    "pitch_modulator": round(1.0 + (vec_mean.get("whimsy", 0.5) - 0.5) * 0.4, 4),
                    "speed_rate": round(1.0 - (vec_mean.get("darkTone", 0.5) - 0.5) * 0.3, 4),
                    "amplitude_gain": round(0.5 + vec_mean.get("voiceWeight", 0.5) * 0.5, 4),
                    "spectral_tilt": round((vec_mean.get("chaos", 0.5) - 0.5) * 0.2, 4),
                })

            vec_path = output_dir / "voicebox_training_vector.json"
            prof_path = output_dir / "voicebox_profile_payload.json"
            vec_path.write_text(json.dumps(vector_rows, indent=2, ensure_ascii=False), encoding="utf-8")
            prof_path.write_text(json.dumps(profile_payloads, indent=2, ensure_ascii=False), encoding="utf-8")

            return _ok(self.tool_id, f'Exported {len(vector_rows)} training rows → {output_dir}', {'vector_path': str(vec_path), 'profile_path': str(prof_path), 'row_count': len(vector_rows), 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_training_export failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Megatron Corpus Slicer ─────────────────────────────────────────────

@ToolRegistry.register("kingwen_megatron_slice")
class KingWenMegatronSliceTool(BaseTool):
    """Slice and format King Wen wiki-math corpus for Megatron-LM ingestion."""

    tool_id = "kingwen_megatron_slice"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_megatron_slice",
            description=(
                "Reads the King Wen fan-out learned corpus and slices it into "
                "Megatron-LM compatible text rows (one JSON per line, 'text' field). "
                "Filters by minimum formula count and exports to kingwen_train_data/."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "min_formulas": {
                        "type": "integer",
                        "description": "Minimum number of formulas a page must have to be included.",
                        "default": 1,
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Maximum rows to export. 0 = no limit.",
                        "default": 0,
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "Output JSONL filename inside kingwen_train_data/.",
                        "default": "wiki_math_corpus.jsonl",
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        min_formulas = int(params.get("min_formulas", 1))
        max_rows = int(params.get("max_rows", 0))
        output_filename = str(params.get("output_filename", "wiki_math_corpus.jsonl"))

        learned_path = KING_WEN_ROOT / "learn" / "exports" / "fan_out_learned.json"
        output_path = KING_WEN_ROOT / "kingwen_train_data" / output_filename

        try:
            if not learned_path.exists():
                return _err(self.tool_id, f'fan_out_learned.json not found at {learned_path}. Run kingwen_fan_out_digest first.')

            learned = json.loads(learned_path.read_text(encoding="utf-8"))
            items: List[Dict[str, Any]] = learned.get("items", [])

            output_path.parent.mkdir(parents=True, exist_ok=True)
            rows_written = 0

            with output_path.open("w", encoding="utf-8") as fh:
                for item in items:
                    formulas = item.get("formulas") or []
                    if len(formulas) < min_formulas:
                        continue
                    title = item.get("title", "")
                    formula_texts = [f.get("latex_like", "") for f in formulas if f.get("latex_like")]
                    text = f"{title}\n" + "\n".join(formula_texts)
                    fh.write(json.dumps({"text": text, "title": title, "formula_count": len(formulas)}, ensure_ascii=False) + "\n")
                    rows_written += 1
                    if max_rows and rows_written >= max_rows:
                        break

            return _ok(self.tool_id, f'Sliced {rows_written} Megatron rows → {output_path}', {'output_path': str(output_path), 'rows_written': rows_written, 'min_formulas_filter': min_formulas, 'timestamp': time.time()})
        except Exception as exc:
            LOGGER.exception("kingwen_megatron_slice failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Fan-Out Learn Digest ───────────────────────────────────────────────

@ToolRegistry.register("kingwen_fan_out_digest")
class KingWenFanOutDigestTool(BaseTool):
    """Run the full King Wen fan-out wiki-math learn batch and persist output."""

    tool_id = "kingwen_fan_out_digest"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_fan_out_digest",
            description=(
                "Runs the King Wen fan-out learn batch over the wiki-math manifest, "
                "extracts LaTeX/MathML nodes, classifies formulas into King Wen domains, "
                "and writes fan_out_learned.json with oracle telemetry per page. "
                "Requires fan_out_manifest.jsonl to be populated first."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "delay": {
                        "type": "number",
                        "description": "Throttle delay between wiki-page parses (seconds).",
                        "default": 0.35,
                    },
                    "max_errors": {
                        "type": "integer",
                        "description": "Stop after this many consecutive parse errors.",
                        "default": 5,
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    def execute(self, **params: Any) -> ToolResult:
        delay = float(params.get("delay", 0.35))
        max_errors = int(params.get("max_errors", 5))

        manifest_path = KING_WEN_ROOT / "learn" / "exports" / "fan_out_manifest.jsonl"
        out_path = KING_WEN_ROOT / "learn" / "exports" / "fan_out_learned.json"

        try:
            if not manifest_path.exists():
                return _err(self.tool_id, f'fan_out_manifest.jsonl not found at {manifest_path}')

            import sys
            sys.path.insert(0, str(KING_WEN_ROOT / "learn" / "scripts"))
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "fan_out_learn",
                str(KING_WEN_ROOT / "learn" / "scripts" / "fan_out_learn.py"),
            )
            if spec is None or spec.loader is None:
                return _err(self.tool_id, "Could not load fan_out_learn.py")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            items = [
                json.loads(line)
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            result = module.learn_batch(items, delay=delay, max_errors=max_errors)
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

            return _ok(
                self.tool_id,
                f"Fan-out digest: {result['learned_count']}/{result['batch_count']} pages → {out_path}",
                {
                    'learned_count': result['learned_count'],
                    'batch_count': result['batch_count'],
                    'output_path': str(out_path),
                    'timestamp': time.time(),
                },
            )
        except Exception as exc:
            LOGGER.exception("kingwen_fan_out_digest failed")
            return _err(self.tool_id, str(exc))


# ── Tool: Multi-Domain JSONL Rebuild ─────────────────────────────────────────

@ToolRegistry.register("kingwen_multi_domain_rebuild")
class KingWenMultiDomainRebuildTool(BaseTool):
    """Rebuild megatron_multi_domain.jsonl from learned_sequential_64.json.

    Fixes the null-field data quality issue in the existing file.
    Iterates the dict-keyed source (keys "1"–"64"), joins with HEXAGRAM_BASE,
    computes trigram domain routing, ternary yao tension (qutrit |psi>),
    Gaussian emotional pull sigma, and Hamiltonian sequence energy H -- injecting
    full math-enriched rows compatible with Megatron-LM multi-domain ingestion.

    Inject-site tagging convention (per pipeline enrichment contract)::

      [§INJECT:domain-{name}|temporal-{phase}|trigram-{u}-{l}]
      H_seq  = 0.5 * omega^2 * (hex_id / 64)^2  (harmonic oscillator proxy)
      G_pull = exp(-0.5 * ((ew_chaos - mu) / sigma)^2)  (Gaussian emotional pull)
      psi_norm = sqrt(sum ternary^2)             (qutrit norm)
    """

    tool_id = "kingwen_multi_domain_rebuild"
    is_local = True

    _DOMAIN_TABLE = [
        "voice", "motion", "structure", "logic",
        "memory", "perception", "generation", "resolution",
    ]
    _EMO_MU: float = 0.5
    _EMO_SIG: float = 0.25

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="kingwen_multi_domain_rebuild",
            description=(
                "Rebuilds kingwen_train_data/megatron_multi_domain.jsonl from "
                "learned_sequential_64.json, joining with HEXAGRAM_BASE and injecting "
                "ternary yao tension, Gaussian emotional pull, Hamiltonian sequence energy, "
                "and trigram domain tags. Overwrites the previous null-field file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "output_filename": {
                        "type": "string",
                        "description": "Output JSONL filename inside kingwen_train_data/.",
                        "default": "megatron_multi_domain.jsonl",
                    },
                    "allowed_bridges": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Bridge tags written to every row.",
                        "default": ["kingwen_core_to_megatron"],
                    },
                },
                "required": [],
            },
            category="knowledge",
        )

    @staticmethod
    def _trigram_domain(upper_idx: int, lower_idx: int, domain_table: List[str]) -> str:
        idx = (upper_idx * 8 + lower_idx) % len(domain_table)
        return domain_table[idx]

    @staticmethod
    def _hamiltonian_energy(hexagram_id: int, stability: float, coherence: float) -> float:
        import math
        omega = 2 * math.pi / 64
        x = hexagram_id / 64.0
        kinetic = 0.5 * (omega ** 2) * (x ** 2)
        binding = 0.3 * stability * coherence
        return round(kinetic + binding, 8)

    @staticmethod
    def _gaussian_pull(chaos: float, mu: float, sigma: float) -> float:
        import math
        if sigma <= 0:
            return 1.0
        z = (chaos - mu) / sigma
        return round(math.exp(-0.5 * z * z), 8)

    @staticmethod
    def _ternary_qutrit_norm(pattern_shape: Dict[str, Any]) -> float:
        import math
        yang = float(pattern_shape.get("yang_count") or 0)
        yin = float(pattern_shape.get("yin_count") or 0)
        norm = math.sqrt(yang ** 2 + yin ** 2) or 1.0
        return round(norm, 6)

    @staticmethod
    def _inject_site_tag(domain: str, temporal: str, upper_idx: int, lower_idx: int) -> str:
        return (
            f"[\u00a7INJECT:domain-{domain}|temporal-{temporal}"
            f"|trigram-{upper_idx}-{lower_idx}]"
        )

    def execute(self, **params: Any) -> ToolResult:
        import importlib.util as _iutil

        output_filename = str(params.get("output_filename", "megatron_multi_domain.jsonl"))
        allowed_bridges: List[str] = list(
            params.get("allowed_bridges", ["kingwen_core_to_megatron"])
        )

        seq64_path = KING_WEN_ROOT / "learn" / "exports" / "learned_sequential_64.json"
        output_path = KING_WEN_ROOT / "kingwen_train_data" / output_filename

        try:
            if not seq64_path.exists():
                return _err(self.tool_id, f"learned_sequential_64.json not found at {seq64_path}")

            ee_path = KING_WEN_ROOT / "emotional_engine.py"
            if not ee_path.exists():
                return _err(self.tool_id, f"emotional_engine.py not found at {ee_path}")
            ee_spec = _iutil.spec_from_file_location("emotional_engine_rebuild", str(ee_path))
            ee_mod = _iutil.module_from_spec(ee_spec)
            ee_spec.loader.exec_module(ee_mod)  # type: ignore[union-attr]
            hexagram_base: Dict[int, Dict[str, Any]] = getattr(ee_mod, "HEXAGRAM_BASE", {})

            raw: Dict[str, Any] = json.loads(seq64_path.read_text(encoding="utf-8"))

            output_path.parent.mkdir(parents=True, exist_ok=True)
            rows_written = 0

            with output_path.open("w", encoding="utf-8") as fh:
                for str_id, entry in raw.items():
                    try:
                        hex_id = int(str_id)
                    except (ValueError, TypeError):
                        continue

                    base = hexagram_base.get(hex_id, {})
                    name = entry.get("name") or base.get("name") or f"Hex-{hex_id}"
                    category = entry.get("category") or base.get("category") or "unknown"
                    action = entry.get("action") or base.get("action") or "NONE"
                    ps: Dict[str, Any] = entry.get("pattern_shape") or {}
                    binary = ps.get("binary") or base.get("binary_top_to_bottom") or ""
                    trigs = entry.get("trigrams") or {}
                    upper_idx = int(trigs.get("upper_idx") or base.get("upper_idx") or 0)
                    lower_idx = int(trigs.get("lower_idx") or base.get("lower_idx") or 0)
                    ew: Dict[str, float] = entry.get("emotional_weights") or {
                        "chaos": 0.5, "whimsy": 0.5, "darkTone": 0.0,
                        "coherence": 0.5, "voiceWeight": 0.5,
                    }
                    stability = float(ps.get("stability") or 0.5)
                    inject_pools: List[str] = list(ps.get("inject_pools") or [])
                    temporal = "present"

                    domain = self._trigram_domain(upper_idx, lower_idx, self._DOMAIN_TABLE)
                    H_seq = self._hamiltonian_energy(hex_id, stability, float(ew.get("coherence", 0.5)))
                    G_pull = self._gaussian_pull(float(ew.get("chaos", 0.5)), self._EMO_MU, self._EMO_SIG)
                    psi_norm = self._ternary_qutrit_norm(ps)
                    inject_tag = self._inject_site_tag(domain, temporal, upper_idx, lower_idx)

                    row: Dict[str, Any] = {
                        "domain": "kingwen_core",
                        "source": "learn/exports/learned_sequential_64.json",
                        "hexagram_id": hex_id,
                        "name": name,
                        "category": category,
                        "action": action,
                        "binary": binary,
                        "construct": f"hexagram::{name}::{category}",
                        "math": (
                            f"{name}: {action} dominant={binary}={category}"
                            f" porosity={round(float(ps.get('porosity_norm', 0.0)), 4)}"
                            f" H={H_seq} G={G_pull} psi={psi_norm}"
                        ),
                        "emotional_weights": {
                            "chaos": ew.get("chaos"),
                            "whimsy": ew.get("whimsy"),
                            "darkTone": ew.get("darkTone"),
                            "coherence": ew.get("coherence"),
                            "voiceWeight": ew.get("voiceWeight"),
                        },
                        "pattern_shape": ps,
                        "inject_site": {
                            "tag": inject_tag,
                            "domain": domain,
                            "temporal": temporal,
                            "upper_idx": upper_idx,
                            "lower_idx": lower_idx,
                            "inject_pools": inject_pools,
                        },
                        "math_enrichment": {
                            "H_hamiltonian": H_seq,
                            "G_gaussian_pull": G_pull,
                            "psi_qutrit_norm": psi_norm,
                            "trigram_domain": domain,
                            "stability": stability,
                        },
                        "allowed_bridges": allowed_bridges,
                        "source_domain": "kingwen_core",
                        "training_notes": entry.get("training_notes") or "",
                        "unique_pattern_summary": entry.get("unique_pattern_summary") or "",
                    }
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    rows_written += 1

            return _ok(
                self.tool_id,
                f"Rebuilt {rows_written} Megatron multi-domain rows \u2192 {output_path}",
                {
                    "output_path": str(output_path),
                    "rows_written": rows_written,
                    "timestamp": time.time(),
                },
            )
        except Exception as exc:
            LOGGER.exception("kingwen_multi_domain_rebuild failed")
            return _err(self.tool_id, str(exc))
