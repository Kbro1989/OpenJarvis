/**
 * JARVIS Cloudflare Native Router
 * ================================
 * Single entry-point Worker that routes all JARVIS interactions
 * across the POG2 ecosystem. Every path is intentional.
 *
 * Routes:
 *   GET  /health                   — liveness probe
 *   POST /oracle/consult           → ichingoracle Worker (King Wen consult)
 *   WS   /oracle/ws                → ichingoracle WebSocket (real-time persona stream)
 *   POST /jarvis/wake              → wake sequence trigger (fires jarvis_wake.py result)
 *   POST /jarvis/intent            → intent decoder (oracle state → tool slots)
 *   POST /jarvis/delegate          → Hermes delegation webhook
 *   WS   /globe/ws                 → openjarvis-globe-worker (King Wen consensus fan-out)
 *   POST /training/export          → queue a trace to pog2-collapse-events
 *   GET  /training/status          → check training queue depth
 *   GET  /secrets/endpoints        → list registered Worker endpoints (internal, auth-gated)
 *
 * Bound services (configure in wrangler.toml JARVIS_ROUTER section):
 *   ORACLE_WORKER  — Service binding to ichingoracle
 *   GLOBE_WORKER   — Service binding to openjarvis-kingwen-globe
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import { bearerAuth } from "hono/bearer-auth";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Env {
  // Service bindings
  ORACLE_WORKER: Fetcher;
  GLOBE_WORKER: Fetcher;

  // Queue bindings
  POG2_COLLAPSE_QUEUE: Queue;

  // KV
  POG2_SOVEREIGN: KVNamespace;

  // Secrets (set via wrangler secret put)
  JARVIS_ROUTER_TOKEN: string;    // Bearer token for auth-gated routes
  CF_ACCOUNT_ID: string;
}

// ─── App ──────────────────────────────────────────────────────────────────────

const app = new Hono<{ Bindings: Env }>();

// Global CORS — allow JARVIS desktop client + Hermes localhost
app.use(
  "/*",
  cors({
    origin: ["http://localhost:7891", "http://localhost:8000", "http://localhost:3000"],
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  })
);

// ─── Health ───────────────────────────────────────────────────────────────────

app.get("/health", (c) => {
  return c.json({
    status: "ok",
    service: "jarvis-router",
    timestamp: Date.now(),
    routes: [
      "POST /oracle/consult",
      "WS   /oracle/ws",
      "POST /jarvis/wake",
      "POST /jarvis/intent",
      "POST /jarvis/delegate",
      "WS   /globe/ws",
      "POST /training/export",
      "GET  /training/status",
      "GET  /secrets/endpoints",
    ],
  });
});

// ─── Oracle Proxy ─────────────────────────────────────────────────────────────

/**
 * POST /oracle/consult
 * Proxies to the ichingoracle Worker's /oracle/consult endpoint.
 * Adds JARVIS session metadata to the request.
 */
app.post("/oracle/consult", async (c) => {
  const body = await c.req.json().catch(() => ({}));

  // Inject JARVIS router metadata
  const enriched = {
    ...body,
    _source: "jarvis-router",
    _timestamp: Date.now(),
  };

  const response = await c.env.ORACLE_WORKER.fetch(
    new Request("https://ichingoracle.kristain33rs.workers.dev/oracle/consult", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(enriched),
    })
  );

  const data = await response.json();
  return c.json(data, response.status as any);
});

/**
 * GET /oracle/ws  (WebSocket upgrade)
 * Tunnels the WebSocket connection through to ichingoracle's /ws endpoint.
 */
app.get("/oracle/ws", async (c) => {
  const upgradeHeader = c.req.header("Upgrade");
  if (!upgradeHeader || upgradeHeader !== "websocket") {
    return c.text("Expected WebSocket upgrade", 426);
  }

  // Forward the WebSocket upgrade to the Oracle worker
  return c.env.ORACLE_WORKER.fetch(
    new Request("https://ichingoracle.kristain33rs.workers.dev/ws", c.req.raw)
  );
});

// ─── JARVIS Endpoints ─────────────────────────────────────────────────────────

/**
 * POST /jarvis/wake
 * Stores the wake result in KV and broadcasts to Globe WebSocket observers.
 */
app.post("/jarvis/wake", async (c) => {
  const body = await c.req.json().catch(() => ({}));

  const wakeRecord = {
    ...body,
    received_at: Date.now(),
  };

  // Persist latest wake state to KV
  await c.env.POG2_SOVEREIGN.put(
    "jarvis:last_wake",
    JSON.stringify(wakeRecord),
    { expirationTtl: 86400 }
  );

  // Fan out to Globe if hexagram data present
  if (body.hexagram_id) {
    const globeMsg = {
      type: "KINGWEN_CONSENSUS_UPDATE",
      source: "jarvis_wake",
      timestamp: Date.now(),
      hexagram_id: body.hexagram_id,
      hexagram_name: body.hexagram_name,
      porosity: body.porosity_ratio,
      voiceWeight: body.expanded_vector?.voiceWeight,
      coherence: body.expanded_vector?.coherence,
      phase_temporal: body.temporal,
      trajectory: body.tone,
    };

    // Non-blocking broadcast to Globe (fire and forget)
    c.env.GLOBE_WORKER.fetch(
      new Request("https://openjarvis-kingwen-globe.kristain33rs.workers.dev/parties/globe/jarvis-wake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(globeMsg),
      })
    ).catch(() => {});
  }

  return c.json({ status: "wake_received", stored: true });
});

/**
 * POST /jarvis/intent
 * Accepts a raw user message + optional oracle state, returns ranked tool slots.
 * This is the pure HTTP bridge for the intent decoder.
 */
app.post("/jarvis/intent", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const { user_text = "", oracle_state = null } = body;

  // If no oracle_state provided, fetch one from ichingoracle first
  let oracleResult = oracle_state;
  if (!oracleResult) {
    try {
      const oracleResp = await c.env.ORACLE_WORKER.fetch(
        new Request("https://ichingoracle.kristain33rs.workers.dev/oracle/consult", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: user_text, source: "jarvis-intent" }),
        })
      );
      oracleResult = await oracleResp.json();
    } catch {
      oracleResult = null;
    }
  }

  return c.json({
    user_text,
    oracle_state: oracleResult,
    note: "Route to jarvis_wake.py intent_slots for tool selection. Oracle state is Jiminy Cricket's input.",
    intent_endpoint: "python src/openjarvis/intent/decoder.py",
  });
});

/**
 * POST /jarvis/delegate
 * Receives delegation events from JARVIS or Hermes and stores in KV queue.
 */
app.post("/jarvis/delegate", async (c) => {
  const body = await c.req.json().catch(() => ({}));

  const record = {
    ...body,
    queued_at: Date.now(),
  };

  // Push to collapse queue for training data capture
  if (body.task_type === "model_train" || body.event_type === "trace_complete") {
    await c.env.POG2_COLLAPSE_QUEUE.send({
      type: "delegation",
      payload: record,
    });
  }

  // Store in KV log
  const key = `jarvis:delegate:${Date.now()}`;
  await c.env.POG2_SOVEREIGN.put(key, JSON.stringify(record), {
    expirationTtl: 604800, // 7 days
  });

  return c.json({ status: "delegated", key });
});

// ─── Globe WebSocket Proxy ─────────────────────────────────────────────────────

/**
 * GET /globe/ws  (WebSocket upgrade)
 * Tunnels to the PartyKit Globe Durable Object.
 */
app.get("/globe/ws", async (c) => {
  return c.env.GLOBE_WORKER.fetch(
    new Request(
      "https://openjarvis-kingwen-globe.kristain33rs.workers.dev/parties/globe/main",
      c.req.raw
    )
  );
});

// ─── Training Queue ───────────────────────────────────────────────────────────

/**
 * POST /training/export
 * Accepts a JARVIS trace record and queues it to pog2-collapse-events
 * for the Megatron-LM KingWen dataset pipeline.
 */
app.post("/training/export", async (c) => {
  const body = await c.req.json().catch(() => ({}));

  await c.env.POG2_COLLAPSE_QUEUE.send({
    type: "kingwen_trace",
    trace_id: body.trace_id || `tr_${Date.now()}`,
    hexagram_id: body.hexagram_id,
    porosity_ratio: body.porosity_ratio,
    quantum_collapse_delta: body.quantum_collapse_delta,
    text: body.text,
    weight: body.weight,
    timestamp: Date.now(),
  });

  return c.json({ status: "queued", queue: "pog2-collapse-events" });
});

app.get("/training/status", async (c) => {
  const last = await c.env.POG2_SOVEREIGN.get("jarvis:last_wake");
  return c.json({
    queue: "pog2-collapse-events",
    last_wake: last ? JSON.parse(last) : null,
    note: "Use Cloudflare dashboard for queue depth metrics.",
  });
});

// ─── Secrets / Endpoints Registry (auth-gated) ───────────────────────────────

app.get(
  "/secrets/endpoints",
  bearerAuth({ token: (c) => c.env.JARVIS_ROUTER_TOKEN }),
  (c) => {
    return c.json(WORKER_ENDPOINTS);
  }
);

// ─── 404 ──────────────────────────────────────────────────────────────────────

app.notFound((c) => c.json({ error: "not_found", path: c.req.path }, 404));
app.onError((err, c) => c.json({ error: err.message }, 500));

// ─── Export ───────────────────────────────────────────────────────────────────

export default app;

// ─── Worker Endpoints Manifest (also served by secrets store) ─────────────────
// This is the canonical registry — imported by the Python secrets store.

export const WORKER_ENDPOINTS = {
  _meta: {
    account_id: "6872653edcee9c791787c1b783173793",
    account_subdomain: "kristain33rs",
    updated: "2026-07-07",
  },
  oracle: {
    name: "ichingoracle",
    base_url: "https://ichingoracle.kristain33rs.workers.dev",
    endpoints: {
      consult:    "POST /oracle/consult",
      websocket:  "WS   /ws",
      health:     "GET  /health",
    },
    bindings: {
      durable_objects: ["POG2OrchestratorDO", "POG2WebSocketDO"],
      kv:  ["POG2_SOVEREIGN", "POG2_DISSIPATOR"],
      d1:  ["POG2_BOUNDARY (pog2-boundary)"],
      r2:  ["POG2_TRANSFORMER (pog2-transformer)"],
      queues: [
        "pog2-collapse-events",
        "pog2-drift-events",
        "pog2-continuity-events",
        "pog2-crisis-broadcast",
        "pog2-persona-outputs",
      ],
      ai: "Workers AI binding (AI)",
    },
  },
  globe: {
    name: "openjarvis-kingwen-globe",
    base_url: "https://openjarvis-kingwen-globe.kristain33rs.workers.dev",
    endpoints: {
      websocket:   "WS   /parties/globe/:room_id",
      broadcast:   "POST /parties/globe/:room_id",
    },
    bindings: {
      durable_objects: ["Globe (SQLite)"],
    },
  },
  router: {
    name: "jarvis-router",
    base_url: "https://jarvis-router.kristain33rs.workers.dev",
    endpoints: {
      health:           "GET  /health",
      oracle_consult:   "POST /oracle/consult",
      oracle_ws:        "WS   /oracle/ws",
      jarvis_wake:      "POST /jarvis/wake",
      jarvis_intent:    "POST /jarvis/intent",
      jarvis_delegate:  "POST /jarvis/delegate",
      globe_ws:         "WS   /globe/ws",
      training_export:  "POST /training/export",
      training_status:  "GET  /training/status",
      endpoints:        "GET  /secrets/endpoints  [Bearer auth]",
    },
  },
};
