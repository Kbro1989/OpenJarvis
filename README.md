# OpenJarvis

> Personal AI infrastructure — Python · Local-first · King Wen cognitive layer

OpenJarvis is a local-first personal AI runtime built for deep multi-agent
orchestration, distributed inference, and emotional state–guided generation.
It extends the open-jarvis framework with a fully integrated
[King Wen I-Ching immutable table](https://github.com/krist/.../KING-WEN-I-CHING-IMMUTABLE-TABLES)
layer that acts as the cognitive synaptic core across all output pipelines.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│ OpenJarvis Runtime                                         │
│                                                            │
│  CLI (chat / ask / serve / oracle / script / journey)      │
│       │                                                    │
│  ┌────▼──────────────────────────────────────────────┐     │
│  │ King Wen Cognitive Layer                          │     │
│  │  emotion/kingwen_engine_adapter.py                │     │
│  │  → collapse_full_128 → oracle consensus           │     │
│  │  → voice weight vector (chaos · whimsy ·          │     │
│  │    darkTone · coherence · voiceWeight)            │     │
│  │  → script pipeline / narrative dispatch           │     │
│  └───────────────────────────────────────────────────┘     │
│       │                                                    │
│  ┌────▼──────────────────────────────────────────────┐     │
│  │ Agent Layer                          Trace Layer  │     │
│  │  managed agents · channel agents     TraceStore   │     │
│  │  morning digest · orchestrator       telemetry    │     │
│  └───────────────────────────────────────────────────┘     │
│       │                                                    │
│  ┌────▼──────────────────────────────────────────────┐     │
│  │ Tool Registry (40+ tools)                         │     │
│  │  kingwen_oracle_consult  · script_pipeline        │     │
│  │  kingwen_narrative_dispatch · actionable_bridge   │     │
│  │  kingwen_vhdl_router · voice_tools · learning     │     │
│  │  code_interpreter · file_write · channel_send     │     │
│  └───────────────────────────────────────────────────┘     │
│       │                                                    │
│  ┌────▼──────────────────────────────────────────────┐     │
│  │ Inference Backends                                │     │
│  │  Ollama (local) · Cloudflare Workers AI           │     │
│  │  OpenAI-compatible · TernaryRouter                │     │
│  └───────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────┘
```

---

## King Wen Cognitive Layer

The King Wen I-Ching immutable tables (64 hexagrams × 512 collapse states)
act as the emotional and intentional governor across all generation pipelines.
Every inference session is anchored to a hexagram oracle state that provides:

| Axis | Role |
|---|---|
| `voiceWeight` | Speaker confidence / assertiveness |
| `coherence` | Structural clarity of output |
| `chaos` | Tension / disruption index |
| `whimsy` | Lateral / unexpected response density |
| `darkTone` | Shadow / depth register |

The quantum expansion loop (`collapse_full_128`) runs multi-pass superposition
capture with coherence-biased gap filling to collapse intent into a hexagram
state before any generation happens.

---

## Universal Script Pipeline

`/script` drives any creative or technical output through the hexagram
cognitive state machine:

```
/script <type> <intent> [--hex N] [--passes N] [--emotional 0-100]
```

**Types:**

| Type | Output |
|---|---|
| `prose` | Literary narrative with past/present/future arc |
| `screenplay` | INT./EXT. slug + action + dialogue |
| `dialogue` | Two-character exchange driven by voice weights |
| `lyrics` | Verse/chorus/bridge with axis-driven rhyme & meter |
| `image_prompt` | Stable Diffusion weighted prompt |
| `code` | Code completion via narrative dispatch |
| `essay` | Thesis → development → counter → synthesis |
| `training_record` | Megatron multi-domain JSONL for downstream ingestion |
| `gutenberg` | POG2-compatible corpus passage match |

All pipeline runs are appended to `~/.openjarvis/script_pipeline_ledger.jsonl`
as training signal for Megatron multi-domain ingestion.

---

## CLI Commands

```
jarvis chat                  # Interactive REPL
jarvis ask <query>           # Single-shot query
jarvis serve                 # Start API server
jarvis daemon                # Background daemon

# In chat REPL:
/oracle <query>              # King Wen oracle consult + voice synthesis
/counsel <query>             # Oracle with past/present/future framing
/script <type> <intent>      # Universal script cognitive pipeline
/journey <sub>               # TraceStore graph replay/consult
/agents                      # Active processes and agent state
/blueprint <name>            # Hermes automation catalog
/cron list|pause|enable      # Hermes cron job management
/tools list|enable|disable   # Session tool registry control
/memory list|queue|approve   # Memory write approval gate
/models                      # ModelRolodex: Ollama + ternary + CF workers
/learn status|run            # Skill ingestion
/rules                       # Rules skill enforcement scan
/help                        # Full command reference
```

---

## Source Layout

```
src/openjarvis/
  agents/          Managed, channel, morning-digest, orchestration agents
  cli/             All CLI commands and REPL (chat_cmd.py is the REPL core)
  core/            Config, types, registry, paths
  emotion/         King Wen engine adapter, completion injection, voice weights
  tools/           Tool registry: 10+ King Wen tools + general tools
  server/          FastAPI server, WebSocket bridge, agent routes
  prompt/          Prompt builder with King Wen emotional_state injection
  learning/        Skill ingestion + knowledge graph
  traces/          TraceStore SQLite collector + graph renderer
  memory/          Memory approval gate + store
  security/        Audit log (hash-chained SQLite)
  speech/          TTS synthesis (voice preset from King Wen)
  scheduler/       Task scheduling system
  mcp/             MCP (Model Context Protocol) layer
  sovereign/       SovereignRuntime: neurological map, immunology, pulse monitor
  openjarvis/      Runtime package: core, slash, sovereign, emotion
src/openjarvis/
  core/            NeurologicalMap, JarvisNeurologicalMap, NodeTester health audit
  emotion/         King Wen completion injection, expanded consensus batch save strings
  sovereign/       CognitiveImmunologyEmergency, SovereignCircuitBreaker, BiologicalPulseMonitor
  slash/           Slash command registry, handlers, integration
scripts/
  validate_sovereign_subsystem.py  Neurology/immunology/pulse verification
  verify_kingwen_expansion.py      Expansion frontier verification
  validate_kingwen_research.py     Voice-pool/inject-site research fidelity check
emergency/
  LOCKDOWN_<ts>.json               Sovereign immunology lockdown artifacts
```

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) for local inference
- King Wen immutable tables repo at `KING_WEN_IMMUTABLE_TABLES` env path
  (defaults to `C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES`)

```bash
pip install -e .
jarvis init
jarvis chat
```

---

## Key Constraints

- **No cross-calling Hermes ↔ Jarvis** — any shared dependency is ported into Jarvis locally
- **No mock / stub / placeholder data** in production ship-set
- **No undefined deletions** — every removal is intentional and documented
- King Wen tables are **immutable** — runtime reads only, no writes to the table source
