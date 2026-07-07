"""
JARVIS Secrets Store
====================
Single source of truth for all API keys, endpoints, and Worker bindings
used across the JARVIS ecosystem.

Structure:
  SECTION 1 — LLM / AI provider keys (Ollama, OpenRouter, Anthropic, Google, etc.)
  SECTION 2 — Cloudflare Worker endpoints (all verified from INTEGRATION-SPEC.md §11)
  SECTION 3 — POG2 binding IDs (KV, D1, R2, DO, Queue names)
  SECTION 4 — Local service ports (Ollama, JARVIS serve, Hermes webhook, expand_server)

Usage:
    from openjarvis.secrets.store import get_secret, CF_WORKERS, LOCAL_PORTS

Rules (from INTEGRATION-SPEC.md §8):
  - No mock/stub/placeholder.  Every value here must be a real, deployed resource.
  - No fabricated bindings.  Values come from wrangler.toml / wrangler.json on disk.
  - Read-only after import.  Do not mutate at runtime.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — LLM / AI Provider Keys
# Populated from environment variables. Never hardcode keys here.
# ─────────────────────────────────────────────────────────────────────────────

LLM_KEYS: Dict[str, str] = {
    # Local Ollama — no key needed, but host is configurable
    "ollama_host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),

    # OpenRouter (cloud fallback for Ollama)
    "openrouter_api_key":  os.environ.get("OPENROUTER_API_KEY", ""),
    "openrouter_base_url": "https://openrouter.ai/api/v1",

    # Anthropic Claude
    "anthropic_api_key":   os.environ.get("ANTHROPIC_API_KEY", ""),

    # Google Gemini
    "google_api_key":      os.environ.get("GOOGLE_API_KEY", ""),

    # OpenAI
    "openai_api_key":      os.environ.get("OPENAI_API_KEY", ""),

    # Cartesia TTS (used by oracle_speak.py)
    "cartesia_api_key":    os.environ.get("CARTESIA_API_KEY", ""),

    # JARVIS Router Bearer token (auth-gated /secrets/endpoints)
    "jarvis_router_token": os.environ.get("JARVIS_ROUTER_TOKEN", ""),
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — Cloudflare Worker Endpoints
# Source: INTEGRATION-SPEC.md §11 (verified from wrangler configs on disk)
# Account: kristain33rs  |  Account ID: 6872653edcee9c791787c1b783173793
# ─────────────────────────────────────────────────────────────────────────────

CF_ACCOUNT = {
    "account_id":        "6872653edcee9c791787c1b783173793",
    "account_subdomain": "kristain33rs",
    "dashboard":         "https://dash.cloudflare.com/6872653edcee9c791787c1b783173793",
}

CF_WORKERS: Dict[str, Dict[str, Any]] = {

    # ── 1. King Wen Oracle Worker ────────────────────────────────────────────
    # Config: Desktop/kingwen-oracle-worker/kingwen-oracle/wrangler.toml
    "kingwen_oracle": {
        "worker_name": "kingwen-oracle",
        "base_url":    "https://kingwen-oracle.kristain33rs.workers.dev",
        "local_dev":   "http://localhost:8787",    # wrangler dev default
        "endpoints": {
            "health":  "GET  /health",
            "consult": "POST /consult",
            "tts":     "POST /tts",
            "random":  "GET  /random",
            "message": "GET  /message",
            # WS /ws — 404 in current production; fix wrangler.toml name before use
        },
        "response_headers": [
            "X-Kingwen-Compliance",   # "compliant" | "reject"
            "X-Kingwen-Vector",       # voiceWeight|coherence|chaos|whimsy|darkTone (6dp each)
            "X-Kingwen-Violations",   # comma-separated axis names
            "X-Kingwen-Porosity",     # float
            "X-Kingwen-Trajectory",   # still|converging|diverging|cycling
            "X-Kingwen-Temporal",     # past|present|future
            "X-Kingwen-Session",      # session id string
        ],
        "tts_model": "@cf/deepgram/aura-2-en",
        "bindings":  {"ai": "AI"},
        "compat":    ["nodejs_compat"],
        "config_path": r"C:\Users\krist\Desktop\kingwen-oracle-worker\kingwen-oracle\wrangler.toml",
        "deploy_cmd":  "npm run deploy",
        "deploy_cwd":  r"C:\Users\krist\Desktop\kingwen-oracle-worker\kingwen-oracle",
        "status":      "live",
    },

    # ── 2. IChing Oracle (POG2 Sovereign Router) ─────────────────────────────
    # Config: Desktop/oracle/wrangler.toml
    "ichingoracle": {
        "worker_name": "ichingoracle",
        "base_url":    "https://ichingoracle.kristain33rs.workers.dev",
        "local_dev":   "http://localhost:8788",
        "endpoints": {
            "consult":   "POST /oracle/consult",
            "websocket": "WS   /ws",
            "health":    "GET  /health",
            "assets":    "GET  /  (SPA fallback)",
        },
        "bindings": {
            "durable_objects": ["POG2OrchestratorDO", "POG2WebSocketDO"],
            "kv":    ["POG2_SOVEREIGN", "POG2_DISSIPATOR"],
            "d1":    ["POG2_BOUNDARY"],
            "r2":    ["POG2_TRANSFORMER"],
            "ai":    "AI",
            "queues_producer": [
                "pog2-collapse-events",
                "pog2-drift-events",
                "pog2-continuity-events",
                "pog2-crisis-broadcast",
                "pog2-persona-outputs",
            ],
        },
        "env_vars": {
            "BEAT_INTERVAL_MS":       "640",
            "ATTRACTOR_PERSISTENCE":  "5",
            "VOID_REENTRY_DEPTH":     "5",
            "MAX_COMPUTE_MS":         "50",
            "BASE_ENTROPY_FIRST_TICK": "0.999",
        },
        "config_path": r"C:\Users\krist\Desktop\oracle\wrangler.toml",
        "deploy_cmd":  "wrangler deploy",
        "deploy_cwd":  r"C:\Users\krist\Desktop\oracle",
        "status":      "live",
    },

    # ── 3. Globe Worker (King Wen Consensus Broadcast) ───────────────────────
    # Config: Desktop/openjarvis-globe-worker/wrangler.json
    "globe": {
        "worker_name": "openjarvis-kingwen-globe",
        "base_url":    "https://openjarvis-kingwen-globe.kristain33rs.workers.dev",
        "local_dev":   "http://localhost:8789",
        "endpoints": {
            "websocket": "WS   /parties/globe/:room_id",
            "broadcast": "POST /parties/globe/:room_id",
            "default_room": "default",
        },
        "ws_message_type": "KINGWEN_CONSENSUS_UPDATE",
        "bindings": {
            "durable_objects": ["Globe (SQLite, PartyKit)"],
        },
        "config_path": r"C:\Users\krist\Desktop\openjarvis-globe-worker\wrangler.json",
        "deploy_cmd":  "wrangler deploy",
        "deploy_cwd":  r"C:\Users\krist\Desktop\openjarvis-globe-worker",
        "status":      "live",
    },

    # ── 4. JARVIS Router (Cloudflare native router — new) ────────────────────
    # Config: OpenJarvis/cloudflare/jarvis-router/wrangler.toml  [to be deployed]
    "jarvis_router": {
        "worker_name": "jarvis-router",
        "base_url":    "https://jarvis-router.kristain33rs.workers.dev",
        "local_dev":   "http://localhost:8790",
        "endpoints": {
            "health":          "GET  /health",
            "oracle_consult":  "POST /oracle/consult",
            "oracle_ws":       "WS   /oracle/ws",
            "jarvis_wake":     "POST /jarvis/wake",
            "jarvis_intent":   "POST /jarvis/intent",
            "jarvis_delegate": "POST /jarvis/delegate",
            "globe_ws":        "WS   /globe/ws",
            "training_export": "POST /training/export",
            "training_status": "GET  /training/status",
            "endpoints_list":  "GET  /secrets/endpoints  [Bearer: JARVIS_ROUTER_TOKEN]",
        },
        "service_bindings": {
            "ORACLE_WORKER": "ichingoracle",
            "GLOBE_WORKER":  "openjarvis-kingwen-globe",
        },
        "queue_bindings": {
            "POG2_COLLAPSE_QUEUE": "pog2-collapse-events",
        },
        "kv_bindings": {
            "POG2_SOVEREIGN": "06bb2cad53044973b59cdc9c97551402",
        },
        "config_path": r"C:\Users\krist\Desktop\OpenJarvis\cloudflare\jarvis-router\wrangler.toml",
        "deploy_cmd":  "wrangler deploy",
        "deploy_cwd":  r"C:\Users\krist\Desktop\OpenJarvis\cloudflare\jarvis-router",
        "status":      "not_deployed",   # wrangler.toml not yet written — scaffold pending
    },

    # ── 5. Ollama Cloudflare Worker (local Ollama backchannel) ───────────────
    # Config: C:\Users\krist\ollama-cloudflare-worker\wrangler.toml
    "ollama_cf_worker": {
        "worker_name": "ollama-cloudflare-worker",
        "base_url":    "https://ollama-cloudflare-worker.kristain33rs.workers.dev",
        "local_dev":   "http://localhost:11434",   # pass-through to local Ollama
        "endpoints": {
            "api":       "HTTP /api/*",
            "websocket": "WS   /",
        },
        "bindings": {
            "durable_objects": ["OllamaDurableObject (OLLAMA_DO)"],
            "kv": ["MODEL_CONFIG → 317b95fb8ab149b3b68fdf5088a0c60a"],
        },
        "required_secret": "OLLAMA_LOCAL_URL",
        "config_path": r"C:\Users\krist\ollama-cloudflare-worker\wrangler.toml",
        "deploy_cmd":  "wrangler deploy",
        "deploy_cwd":  r"C:\Users\krist\ollama-cloudflare-worker",
        "status":      "live",
    },

    # ── 6. Alt1 Helper Bridge (RS Wiki / Grand Exchange backend) ─────────────
    # Config: Desktop/alt1-ai/alt1-worker/wrangler.jsonc
    "alt1_helper_bridge": {
        "worker_name": "alt-1-helper-bridge",
        "base_url":    "https://alt-1-helper-bridge.kristain33rs.workers.dev",
        "local_dev":   "http://localhost:8791",
        "endpoints": {
            "root": "GET  /  (RS Wiki / GE frontend root)",
        },
        "bindings": {
            "kv": ["ITEMS_LIST → 86eec6acf2404e0fbe088cace94294bd"],
            "ai": "AI",
        },
        "compat": ["global_fetch_strictly_public"],
        "config_path": r"C:\Users\krist\Desktop\alt1-ai\alt1-worker\wrangler.jsonc",
        "deploy_cmd":  "wrangler deploy",
        "deploy_cwd":  r"C:\Users\krist\Desktop\alt1-ai\alt1-worker",
        "status":      "live",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — POG2 Binding IDs
# Exact resource IDs from wrangler configs — used in wrangler.toml authoring
# and for programmatic access via CF REST API.
# ─────────────────────────────────────────────────────────────────────────────

CF_BINDINGS: Dict[str, Any] = {
    "kv": {
        "POG2_SOVEREIGN":  "06bb2cad53044973b59cdc9c97551402",
        "POG2_DISSIPATOR": "3b5cd3111d3747829460ed0cb55eb492",
        "ITEMS_LIST":      "86eec6acf2404e0fbe088cace94294bd",
        "MODEL_CONFIG":    "317b95fb8ab149b3b68fdf5088a0c60a",
    },
    "d1": {
        "POG2_BOUNDARY": "2f9edde9-8271-4ae2-a24d-cc48c62cfdf4",
    },
    "r2": {
        "POG2_TRANSFORMER": "pog2-transformer",   # bucket name
    },
    "queues": {
        "producers": [
            "pog2-collapse-events",
            "pog2-drift-events",
            "pog2-continuity-events",
            "pog2-crisis-broadcast",
            "pog2-persona-outputs",
        ],
        "consumers": [
            "pog2-collapse-events",
            "pog2-drift-events",
            "pog2-continuity-events",
            "pog2-crisis-broadcast",
            "pog2-persona-outputs",
        ],
    },
    "durable_objects": {
        "POG2OrchestratorDO":  "ichingoracle",
        "POG2WebSocketDO":     "ichingoracle",
        "Globe":               "openjarvis-kingwen-globe",
        "OllamaDurableObject": "ollama-cloudflare-worker",
    },
    "d1_tables": [
        "identity_threads",
        "boundary_states",
        "entropy_curves",
        "persistence_state",
        "thread_field",
        "persona_vocabulary",
        "persona_syntax",
        "thread_registry",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — Local Service Ports
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_PORTS: Dict[str, Any] = {
    # Ollama local LLM server
    "ollama":         {"host": "localhost", "port": 11434, "url": "http://localhost:11434"},

    # OpenJarvis serve
    "jarvis_serve":   {"host": "localhost", "port": 8000,  "url": "http://localhost:8000"},

    # Hermes webhook receiver (from pog2-jarvis-bridge)
    "hermes_webhook": {"host": "localhost", "port": 7891,  "url": "http://localhost:7891"},

    # King Wen expand_server.py (local ternary router / expansion endpoint)
    "expand_server":  {"host": "localhost", "port": 8765,  "url": "http://localhost:8765",
                       "endpoints": {
                           "expand":  "GET  /expand   → 512 resolved states",
                           "consult": "POST /consult  → single hexagram expansion",
                           "health":  "GET  /health",
                       }},

    # Wrangler dev ports (by worker)
    "wrangler_dev": {
        "kingwen_oracle":  8787,
        "ichingoracle":    8788,
        "globe":           8789,
        "jarvis_router":   8790,
        "alt1_bridge":     8791,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — ModelRolodex (ternary-conscious model router)
# Ported from Desktop/POG2_ModelRolodex_Workflow/run_router.js and run_query.js
# King Wen hexagram category + action → Ollama model selection chain
# ─────────────────────────────────────────────────────────────────────────────

MODEL_ROLODEX: Dict[str, Any] = {
    # ── Providers ─────────────────────────────────────────────────────────────
    # All providers with a key in LLM_KEYS + cloud entries from model_catalog.py
    # engine: "ollama" = local inference | "cloud" = API call | "openrouter" = proxy
    "providers": {
        "ollama": {
            "engine":   "ollama",
            "api_key_env": None,
            "base_url": "http://localhost:11434",
            "key_in_store": "ollama_host",
            "requires_key": False,
            "notes": "Local Ollama — no key needed",
        },
        "openai": {
            "engine":   "cloud",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "key_in_store": "openai_api_key",
            "requires_key": True,
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-5-mini", "gpt-5-mini-2025-08-07"],
        },
        "openai-codex": {
            "engine":   "cloud",
            "api_key_env": "OPENAI_CODEX_API_KEY",
            "base_url": "https://api.openai.com/v1",
            "key_in_store": "openai_api_key",   # shares OpenAI key
            "requires_key": True,
            "notes": "ChatGPT Plus/Pro subscription models",
            "models": ["codex/gpt-4o", "codex/gpt-4o-mini", "codex/o3-mini",
                       "codex/gpt-5-mini", "codex/gpt-5-mini-2025-08-07"],
        },
        "anthropic": {
            "engine":   "cloud",
            "api_key_env": "ANTHROPIC_API_KEY",
            "base_url": "https://api.anthropic.com",
            "key_in_store": "anthropic_api_key",
            "requires_key": True,
            "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514",
                       "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
        },
        "google": {
            "engine":   "cloud",
            "api_key_env": "GOOGLE_API_KEY",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "key_in_store": "google_api_key",
            "requires_key": True,
            "models": ["gemini-2.5-pro", "gemini-2.5-flash",
                       "gemini-3-pro", "gemini-3-flash"],
        },
        "openrouter": {
            "engine":   "openrouter",
            "api_key_env": "OPENROUTER_API_KEY",
            "base_url": "https://openrouter.ai/api/v1",
            "key_in_store": "openrouter_api_key",
            "requires_key": True,
            "notes": "Cloud proxy — routes to any provider; use provider/model-id format",
            "models": [
                # OpenRouter IDs mirror provider model IDs
                "openai/gpt-4o", "openai/gpt-4o-mini",
                "anthropic/claude-sonnet-4-20250514", "anthropic/claude-opus-4-20250514",
                "google/gemini-2.5-pro", "google/gemini-2.5-flash",
                "mistralai/mistral-7b-instruct", "deepseek/deepseek-coder-v2",
                "qwen/qwen3-32b", "minimax/minimax-m2.7",
            ],
        },
        "minimax": {
            "engine":   "cloud",
            "api_key_env": "MINIMAX_API_KEY",
            "base_url": "https://api.minimax.io/v1",
            "key_in_store": "minimax_api_key",
            "requires_key": True,
            "models": ["MiniMax-M2.7", "MiniMax-M2.7-highspeed",
                       "MiniMax-M2.5", "MiniMax-M2.5-highspeed"],
        },
        "deepseek": {
            "engine":   "ollama",           # local via Ollama
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "key_in_store": "deepseek_api_key",
            "requires_key": False,          # local variant requires no key
            "models": ["deepseek-coder-v2:16b"],
        },
        "mistral": {
            "engine":   "ollama",
            "api_key_env": "MISTRAL_API_KEY",
            "base_url": "https://api.mistral.ai/v1",
            "key_in_store": "mistral_api_key",
            "requires_key": False,
            "models": ["mistral:7b"],
        },
        "ibm": {
            "engine":   "ollama",
            "api_key_env": None,
            "base_url": "https://www.ibm.com/granite",
            "key_in_store": None,
            "requires_key": False,
            "models": ["granite3.3:8b", "granite4.0-micro", "granite4.0-h-small"],
        },
        "cartesia": {
            "engine":   "tts",
            "api_key_env": "CARTESIA_API_KEY",
            "base_url": "https://api.cartesia.ai",
            "key_in_store": "cartesia_api_key",
            "requires_key": True,
            "notes": "TTS only — used by oracle_speak.py, not a chat provider",
            "models": [],
        },
        "meta": {
            "engine":   "ollama",
            "api_key_env": None,
            "base_url": None,
            "key_in_store": None,
            "requires_key": False,
            "models": ["llama3.3:70b", "llama3.2:3b"],
        },
        "alibaba": {
            "engine":   "ollama",
            "api_key_env": None,
            "base_url": None,
            "key_in_store": None,
            "requires_key": False,
            "notes": "Qwen family — local via Ollama",
            "models": [
                "qwen3:0.6b", "qwen3:1.7b", "qwen3:4b", "qwen3:8b",
                "qwen3:14b", "qwen3:30b", "qwen3:32b",
                "qwen3.5:0.8b", "qwen3.5:2b", "qwen3.5:4b", "qwen3.5:9b",
                "qwen3.5:27b", "qwen3.5:35b", "qwen3.5:122b", "qwen3.5:397b",
            ],
        },
    },

    # ── Task chains: ollama-local first, cloud fallback ────────────────────
    # Each task has a local chain (Ollama) and a cloud chain (API providers).
    # /models shows local chain; intent decoder can fall through to cloud.
    "task_chain": {
        # local
        "chat":     ["qwen2.5-coder:7b-instruct-q4_K_M", "qwen3.6:27b", "gemma4:latest"],
        "research": ["gemma4:latest", "qwen3.6:27b", "qwen2.5-coder:7b-instruct-q4_K_M"],
        "code":     ["qwen2.5-coder:7b-instruct-q4_K_M", "qwen3.6:27b", "gemma4:latest"],
        "embed":    ["nomic-embed-text", "qwen3.6:27b", "gemma4:latest"],
        "vision":   ["gemma4:latest", "qwen3.6:27b", "qwen2.5-coder:7b-instruct-q4_K_M"],
        "kingwen":  ["gemma4:latest", "qwen3.6:27b", "qwen2.5-coder:7b-instruct-q4_K_M"],
        "default":  ["qwen3.6:27b", "gemma4:latest", "qwen2.5-coder:7b-instruct-q4_K_M"],
    },
    # Cloud fallback chains keyed by provider — used when Ollama offline
    "task_chain_cloud": {
        "chat":     ["gpt-4o-mini", "claude-haiku-4-5", "gemini-2.5-flash"],
        "research": ["gemini-2.5-pro", "claude-opus-4-20250514", "gpt-4o"],
        "code":     ["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.5-pro"],
        "embed":    ["openai/text-embedding-3-small"],   # openrouter passthrough
        "vision":   ["gemini-2.5-pro", "gpt-4o", "claude-opus-4-20250514"],
        "kingwen":  ["claude-opus-4-20250514", "gemini-2.5-pro", "gpt-4o"],
        "default":  ["gpt-4o-mini", "gemini-2.5-flash", "claude-haiku-4-5"],
    },
    # OpenRouter fallback chains (single provider, any model)
    "task_chain_openrouter": {
        "chat":     ["openai/gpt-4o-mini", "google/gemini-2.5-flash", "anthropic/claude-haiku-4-5"],
        "research": ["google/gemini-2.5-pro", "anthropic/claude-opus-4-20250514", "openai/gpt-4o"],
        "code":     ["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514", "google/gemini-2.5-pro"],
        "vision":   ["google/gemini-2.5-pro", "openai/gpt-4o", "anthropic/claude-opus-4-20250514"],
        "kingwen":  ["anthropic/claude-opus-4-20250514", "google/gemini-2.5-pro", "openai/gpt-4o"],
        "default":  ["openai/gpt-4o-mini", "google/gemini-2.5-flash", "anthropic/claude-haiku-4-5"],
    },

    # ── Ternary router: hexagram → model class (local + cloud) ─────────────
    "ternary_router": {
        # Local (Ollama)
        "sovereign_assert":   "large_model",
        "transformer_yield":  "small_model",
        "dissipator_adapt":   "qwen_mistral",
        "boundary_wait":      "default",
        # Cloud — triggered when porosity > 0.7 or Ollama offline
        "sovereign_assert_cloud":  "anthropic_opus",   # deep authority
        "transformer_yield_cloud": "google_flash",     # fast receptive
        "dissipator_adapt_cloud":  "openrouter_any",   # flexible routing
        "boundary_wait_cloud":     "openai_mini",      # lightweight hold
    },
    # Model class definitions (matched against model ID strings)
    "model_classes": {
        # Local Ollama classes
        "large_model":      ["27b", "32b", "70b", "120b"],
        "small_model":      ["7b", "8b", "q4"],
        "qwen_mistral":     ["qwen", "mistral"],
        "embed_model":      ["embed", "nomic"],
        "vision_model":     ["vision", "llava", "gemma4"],
        # Cloud provider classes
        "anthropic_opus":   ["claude-opus", "claude-sonnet-4-20250514", "claude-sonnet-4-6"],
        "anthropic_haiku":  ["claude-haiku"],
        "openai_full":      ["gpt-4o", "gpt-5-mini"],
        "openai_mini":      ["gpt-4o-mini", "gpt-5-mini"],
        "google_pro":       ["gemini-2.5-pro", "gemini-3-pro"],
        "google_flash":     ["gemini-2.5-flash", "gemini-3-flash"],
        "openrouter_any":   ["openai/", "anthropic/", "google/", "mistralai/"],
        "minimax_any":      ["minimax", "MiniMax"],
    },

    # ── Task keyword → task type ────────────────────────────────────────────
    "task_keywords": {
        "kingwen":  ["king-wen", "kingwen", "hexagram", "oracle", "consult", "emotion", "reflection"],
        "code":     ["code", "function", "typescript", "python", "sql", "rust", "regex", "refactor", "debug"],
        "research": ["research", "paper", "arxiv", "search", "compare", "analysis", "evidence"],
        "vision":   ["image", "vision", "ocr", "diagram", "screenshot", "picture"],
        "embed":    ["embed", "retrieval", "rag", "vector"],
    },

    # ── King Wen data paths (read-only) ─────────────────────────────────────
    "data_paths": {
        "hexagram_registry":    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\data\hexagram-registry.json",
        "temporal_reflections": r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\data\temporal-reflections.json",
        "collapse_output":      r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\collapse_full_128_output.json",
        "emotional_weights":    r"C:\Users\krist\Desktop\KING-WEN-I-CHING-IMMUTABLE-TABLES\data\emotional-weights.json",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Accessor helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_secret(key: str) -> str:
    """Retrieve a key from LLM_KEYS. Returns empty string if not set."""
    return LLM_KEYS.get(key, "")


def get_worker(name: str) -> Optional[Dict[str, Any]]:
    """Look up a Cloudflare Worker config by short name."""
    return CF_WORKERS.get(name)


def worker_url(name: str, env: str = "production") -> str:
    """Return the base URL for a worker (production or local_dev)."""
    w = CF_WORKERS.get(name, {})
    if env == "local":
        return w.get("local_dev", "")
    return w.get("base_url", "")


def task_model_chain(task: str) -> list:
    """Return the preferred model chain for a given task."""
    return MODEL_ROLODEX["task_chain"].get(task, MODEL_ROLODEX["task_chain"]["default"])


def ternary_model_class(hexagram_category: str, hexagram_action: str) -> str:
    """
    Map hexagram category + action to a model class preference.
    Mirrors the King Wen-conscious router from run_router.js.
    """
    key = f"{hexagram_category.lower()}_{hexagram_action.lower()}"
    return MODEL_ROLODEX["ternary_router"].get(key, "default")


def task_fit_for(query: str) -> str:
    """Classify a query string into a task type for model selection."""
    q = query.lower()
    for task, keywords in MODEL_ROLODEX["task_keywords"].items():
        if any(k in q for k in keywords):
            return task
    return "chat"
