export interface AvatarMode {
  mode: 'human' | 'agent';
  stateSignature: string;
  lastTransition: number;
}

export interface HexagramNode {
  id: number;
  name: string;
  unicode: string;
  binary: string;
  x: number;
  y: number;
  z: number;
  radius: number;
  color: string;
  opacity: number;
  phase: string;
  voiceWeight: number;
  coherence: number;
  chaos: number;
  whimsy: number;
  darkTone: number;
  porosity: number;
}

export interface AvatarPayload {
  session_id: string;
  mode: AvatarMode['mode'];
  state_signature: string;
  nodes: HexagramNode[];
  dominant: HexagramNode | null;
  transition_tone: {
    frequency: number;
    duration_ms: number;
    pattern: string;
  } | null;
  timestamp: number;
}

export function compressStateSignature(payload: Record<string, unknown>): string {
  const hex = String(payload['hexagram_id'] ?? 0).padStart(2, '0');
  const phase = String(payload['phase_temporal'] ?? 'present').slice(0, 1);
  const vec = (payload['emotional_deltas'] || {}) as Record<string, number>;
  const vw = Math.round((vec['voiceWeight'] ?? 0.5) * 10);
  const ch = Math.round((vec['coherence'] ?? 0.5) * 10);
  const cc = Math.round((vec['chaos'] ?? 0.5) * 10);
  const wh = Math.round((vec['whimsy'] ?? 0.5) * 10);
  const dt = Math.round((vec['darkTone'] ?? 0.5) * 10);
  return `${hex}:${phase}:${vw}:${ch}:${cc}:${wh}:${dt}`;
}

export function modeFromSource(source?: string): AvatarMode['mode'] {
  if (!source) return 'human';
  return source.includes('agent') || source.includes('worker') ? 'agent' : 'human';
}
