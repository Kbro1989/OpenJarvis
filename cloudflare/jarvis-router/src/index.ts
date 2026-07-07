/**
 * JARVIS Cloudflare Native Router
 * ================================
 * Single entry-point Worker for JARVIS + King Wen only.
 *
 * Separation rules:
 *   - Jarvis does NOT talk to ichingoracle
 *   - King Wen does NOT talk to ichingoracle
 *   - King Wen influences Jarvis decisions between user intent and actionable tooling tasks
 *
 * Routes:
 *   GET  /health                   — liveness probe
 *   POST /kingwen/consult          → kingwen-oracle Worker (King Wen consult, immutable tables)
 *   WS   /kingwen/ws               → kingwen-oracle WebSocket
 *   POST /jarvis/wake              → wake sequence trigger
 *   POST /jarvis/intent            → intent decoder bridge, King Wen oracle state → tool slots
 *   POST /jarvis/delegate          → Hermes delegation webhook
 *   WS   /globe/ws                 → openjarvis-kingwen-globe (consensus fan-out)
 *   POST /training/export          → queue a trace to pog2-collapse-events
 *   GET  /training/status          → check training queue depth
 *   GET  /secrets/endpoints        → list registered Worker endpoints (auth-gated)
 */

export interface Env {
  KINGWEN_WORKER: Fetcher;
  GLOBE_WORKER: Fetcher;
  POG2_COLLAPSE_QUEUE: Queue;
  POG2_SOVEREIGN: KVNamespace;
  JARVIS_ROUTER_TOKEN: string;
  CF_ACCOUNT_ID: string;
}

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": [
    "http://localhost:7891",
    "http://localhost:8000",
    "http://localhost:3000",
  ].join(","),
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization",
};

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    ...init,
  });
}

async function parseJson(req: Request, fallback: unknown = {}): Promise<unknown> {
  try {
    return await req.json();
  } catch {
    return fallback;
  }
}

async function handleCors(req: Request): Promise<Response | null> {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }
  return null;
}

async function proxyJson(
  fetcher: Fetcher,
  url: string,
  req: Request,
  prefix?: Record<string, unknown>,
): Promise<Response> {
  const incoming = (await parseJson(req, {})) as Record<string, unknown>;
  const payload = prefix ? { ...prefix, ...incoming } : incoming;
  const response = await fetcher.fetch(
    new Request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  const data = await response.json().catch(() => ({}));
  return jsonResponse(data, { status: response.status });
}

async function wsPassthrough(fetcher: Fetcher, url: string, req: Request): Promise<Response> {
  return fetcher.fetch(new Request(url, req));
}

// ─── Health ───────────────────────────────────────────────────────────────────

function healthResponse(): Response {
  return jsonResponse({
    status: "ok",
    service: "jarvis-router",
    timestamp: Date.now(),
    separation: {
      jarvis_to_ichingoracle: false,
      kingwen_to_ichingoracle: false,
      kingwen_influences_jarvis_intent: true,
    },
    routes: [
      "POST /kingwen/consult",
      "WS   /kingwen/ws",
      "POST /jarvis/wake",
      "POST /jarvis/intent",
      "POST /jarvis/delegate",
      "WS   /globe/ws",
      "POST /training/export",
      "GET  /training/status",
      "GET  /secrets/endpoints",
    ],
  });
}

// ─── King Wen Backend ─────────────────────────────────────────────────────────

async function kingwenConsult(env: Env, req: Request): Promise<Response> {
  return proxyJson(
    env.KINGWEN_WORKER,
    "https://kingwen-oracle.kristain33rs.workers.dev/consult",
    req,
    { _source: "jarvis-router", _backend: "kingwen-oracle" },
  );
}

async function kingwenWs(env: Env, req: Request): Promise<Response> {
  return wsPassthrough(env.KINGWEN_WORKER, "https://kingwen-oracle.kristain33rs.workers.dev/ws", req);
}

// ─── JARVIS Endpoints ─────────────────────────────────────────────────────────

async function jarvisWake(env: Env, req: Request): Promise<Response> {
  const body = (await parseJson(req, {})) as Record<string, unknown>;
  const wakeRecord = { ...body, received_at: Date.now() };
  await env.POG2_SOVEREIGN.put("jarvis:last_wake", JSON.stringify(wakeRecord), { expirationTtl: 86400 });

  const hexagramId = body.hexagram_id;
  if (typeof hexagramId === "string" && hexagramId) {
    const globeMsg = {
      type: "KINGWEN_CONSENSUS_UPDATE",
      source: "jarvis_wake",
      timestamp: Date.now(),
      hexagram_id: hexagramId,
      hexagram_name: body.hexagram_name,
      porosity: body.porosity_ratio,
      voiceWeight: (body.expanded_vector as Record<string, unknown> | undefined)?.voiceWeight,
      coherence: (body.expanded_vector as Record<string, unknown> | undefined)?.coherence,
      phase_temporal: body.temporal,
      trajectory: body.tone,
    };
    env.GLOBE_WORKER.fetch(
      new Request("https://openjarvis-kingwen-globe.kristain33rs.workers.dev/parties/globe/jarvis-wake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(globeMsg),
      }),
    ).catch(() => {});
  }

  return jsonResponse({ status: "wake_received", stored: true });
}

async function jarvisIntent(env: Env, req: Request): Promise<Response> {
  const body = (await parseJson(req, {})) as { user_text?: string; oracle_state?: unknown };
  const userText = typeof body.user_text === "string" ? body.user_text : "";

  let oracleResult = body.oracle_state ?? null;
  if (oracleResult === null) {
    try {
      const oracleResp = await env.KINGWEN_WORKER.fetch(
        new Request("https://kingwen-oracle.kristain33rs.workers.dev/consult", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: userText, source: "jarvis-intent" }),
        }),
      );
      oracleResult = await oracleResp.json();
    } catch {
      oracleResult = null;
    }
  }

  return jsonResponse({
    user_text: userText,
    oracle_state: oracleResult,
    note: "King Wen oracle state feeds Jarvis intent decoding. Tool selection is decided locally from this state.",
    intent_endpoint: "python src/openjarvis/intent/decoder.py",
  });
}

async function jarvisDelegate(env: Env, req: Request): Promise<Response> {
  const body = (await parseJson(req, {})) as Record<string, unknown>;
  const record = { ...body, queued_at: Date.now() };
  const taskType = body.task_type;
  const eventType = body.event_type;
  if (taskType === "model_train" || eventType === "trace_complete") {
    await env.POG2_COLLAPSE_QUEUE.send({
      type: "delegation",
      payload: record,
    });
  }
  const key = `jarvis:delegate:${Date.now()}`;
  await env.POG2_SOVEREIGN.put(key, JSON.stringify(record), { expirationTtl: 604800 });
  return jsonResponse({ status: "delegated", key });
}

async function globeWs(env: Env, req: Request): Promise<Response> {
  return wsPassthrough(
    env.GLOBE_WORKER,
    "https://openjarvis-kingwen-globe.kristain33rs.workers.dev/parties/globe/main",
    req,
  );
}

async function trainingExport(env: Env, req: Request): Promise<Response> {
  const body = (await parseJson(req, {})) as Record<string, unknown>;
  await env.POG2_COLLAPSE_QUEUE.send({
    type: "kingwen_trace",
    trace_id: (typeof body.trace_id === "string" && body.trace_id) || `tr_${Date.now()}`,
    hexagram_id: body.hexagram_id,
    porosity_ratio: body.porosity_ratio,
    quantum_collapse_delta: body.quantum_collapse_delta,
    text: body.text,
    weight: body.weight,
    timestamp: Date.now(),
  });
  return jsonResponse({ status: "queued", queue: "pog2-collapse-events" });
}

async function trainingStatus(env: Env): Promise<Response> {
  const last = await env.POG2_SOVEREIGN.get("jarvis:last_wake");
  return jsonResponse({
    queue: "pog2-collapse-events",
    last_wake: last ? JSON.parse(last) : null,
    note: "Use Cloudflare dashboard for queue depth metrics.",
  });
}

async function secretsEndpoints(): Response {
  return jsonResponse(WORKER_ENDPOINTS);
}

// ─── Main Fetch Handler ───────────────────────────────────────────────────────

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const cors = await handleCors(req);
    if (cors) return cors;

    const url = new URL(req.url);
    const path = url.pathname;

    if (path === "/health" && req.method === "GET") {
      return healthResponse();
    }

    if (path === "/kingwen/consult" && req.method === "POST") {
      return kingwenConsult(env, req);
    }
    if (path === "/kingwen/ws") {
      return kingwenWs(env, req);
    }

    if (path === "/jarvis/wake" && req.method === "POST") {
      return jarvisWake(env, req);
    }
    if (path === "/jarvis/intent" && req.method === "POST") {
      return jarvisIntent(env, req);
    }
    if (path === "/jarvis/delegate" && req.method === "POST") {
      return jarvisDelegate(env, req);
    }
    if (path === "/globe/ws") {
      return globeWs(env, req);
    }
    if (path === "/training/export" && req.method === "POST") {
      return trainingExport(env, req);
    }
    if (path === "/training/status" && req.method === "GET") {
      return trainingStatus(env);
    }
    if (path === "/secrets/endpoints" && req.method === "GET") {
      const auth = req.headers.get("Authorization") || "";
      const token = auth.replace("Bearer ", "").trim();
      if (!token || token !== env.JARVIS_ROUTER_TOKEN) {
        return jsonResponse({ error: "unauthorized" }, { status: 401 });
      }
      return secretsEndpoints();
    }

    return jsonResponse({ error: "not_found", path }, { status: 404 });
  },
};

// ─── Worker Endpoints Manifest ────────────────────────────────────────────────

export const WORKER_ENDPOINTS = {
  _meta: {
    account_id: "6872653edcee9c791787c1b783173793",
    account_subdomain: "kristain33rs",
    updated: "2026-07-07",
    separation: {
      jarvis_to_ichingoracle: false,
      kingwen_to_ichingoracle: false,
      kingwen_influences_jarvis_intent: true,
    },
  },
  kingwen: {
    name: "kingwen-oracle",
    base_url: "https://kingwen-oracle.kristain33rs.workers.dev",
    backend: "kingwen_immutable_tables",
    endpoints: {
      consult: "POST /consult",
      health: "GET /health",
      tts: "POST /tts",
      random: "GET /random",
      message: "GET /message",
    },
    bindings: {
      ai: "AI",
    },
  },
  globe: {
    name: "openjarvis-kingwen-globe",
    base_url: "https://openjarvis-kingwen-globe.kristain33rs.workers.dev",
    endpoints: {
      websocket: "WS /parties/globe/:room_id",
      broadcast: "POST /parties/globe/:room_id",
    },
    bindings: {
      durable_objects: ["Globe (SQLite)"],
    },
  },
  router: {
    name: "jarvis-router",
    base_url: "https://jarvis-router.kristain33rs.workers.dev",
    endpoints: {
      health: "GET /health",
      kingwen_consult: "POST /kingwen/consult",
      kingwen_ws: "WS /kingwen/ws",
      jarvis_wake: "POST /jarvis/wake",
      jarvis_intent: "POST /jarvis/intent",
      jarvis_delegate: "POST /jarvis/delegate",
      globe_ws: "WS /globe/ws",
      training_export: "POST /training/export",
      training_status: "GET /training/status",
      endpoints: "GET /secrets/endpoints [Bearer auth]",
    },
  },
};
