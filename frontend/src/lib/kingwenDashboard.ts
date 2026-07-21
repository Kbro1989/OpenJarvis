import { getBase, getApiKey } from './api';
import type { AvatarPayload } from './avatarProtocol';

export interface AdvisoryPayload {
  hexagram?: string;
  emotionalTongue?: string;
  porosity?: number;
  coherence?: number;
  voiceWeight?: number;
  action?: string;
  category?: string;
  reactionFrame?: string;
  chaos?: number;
  whimsy?: number;
  darkTone?: number;
  dominantHexagramId?: number;
  dominantDomain?: string;
  onlineNodes?: number;
  degradedNodes?: number;
  offlineNodes?: number;
}

export interface KingwenState {
  advisory: AdvisoryPayload | null;
  avatar: AvatarPayload | null;
  loading: boolean;
  error: string | null;
  lastUpdated: number | null;
}

export function createDefaultState(): KingwenState {
  return {
    advisory: null,
    avatar: null,
    loading: false,
    error: null,
    lastUpdated: null,
  };
}

const DEFAULT_ADVISORY_POLL = 30000;
const DEFAULT_AVATAR_POLL = 30000;
const DEV_BACKEND_FALLBACK = 'http://127.0.0.1:8000';

function resolveBase(): string {
  const base = getBase();
  if (base) return base.replace(/\/+$/, '');
  return DEV_BACKEND_FALLBACK;
}

function buildReadonlyHeaders(): HeadersInit {
  const key = getApiKey();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (key) headers['Authorization'] = `Bearer ${key}`;
  return headers;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${resolveBase()}${path}`, {
    method: 'POST',
    headers: buildReadonlyHeaders(),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`kingwen ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${resolveBase()}${path}`, { headers: buildReadonlyHeaders() });
  if (!res.ok) throw new Error(`kingwen ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function fetchAdvisory(): Promise<AdvisoryPayload> {
  return postJson<AdvisoryPayload>('/v1/kingwen/consult', { prompt: 'Desktop advisor heartbeat', max_states: 1 });
}

export async function fetchAvatar(sessionId: string): Promise<AvatarPayload> {
  return getJson<AvatarPayload>(`/v1/kingwen/avatar/${encodeURIComponent(sessionId)}`);
}

export function startAdvisoryPoll(
  setAdvisory: (payload: AdvisoryPayload | null) => void,
  setError: (error: string | null) => void,
  intervalMs = DEFAULT_ADVISORY_POLL,
) {
  let cancelled = false;

  async function tick() {
    try {
      const advisory = await fetchAdvisory();
      if (!cancelled) {
        setAdvisory(advisory);
        setError(null);
      }
    } catch (err) {
      if (!cancelled) setError(err instanceof Error ? err.message : String(err));
    }
  }

  tick();
  const id = setInterval(tick, intervalMs);
  return () => {
    cancelled = true;
    clearInterval(id);
  };
}

export function startAvatarPoll(
  sessionId: string,
  setAvatar: (payload: AvatarPayload | null) => void,
  setError: (error: string | null) => void,
  intervalMs = DEFAULT_AVATAR_POLL,
) {
  let cancelled = false;

  async function tick() {
    try {
      const avatar = await fetchAvatar(sessionId);
      if (!cancelled) {
        setAvatar(avatar);
        setError(null);
      }
    } catch (err) {
      if (!cancelled) setError(err instanceof Error ? err.message : String(err));
    }
  }

  tick();
  const id = setInterval(tick, intervalMs);
  return () => {
    cancelled = true;
    clearInterval(id);
  };
}
