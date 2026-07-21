import { compressStateSignature, type AvatarPayload, type HexagramNode } from './avatarProtocol';

const HEXAGRAM_COUNT = 64;
const GGWOW_PATTERNS: Record<string, { frequency: number; duration_ms: number; pattern: string }> = {
  transition: { frequency: 1800, duration_ms: 120, pattern: 'up' },
  action: { frequency: 2200, duration_ms: 80, pattern: 'burst' },
  hold: { frequency: 1200, duration_ms: 200, pattern: 'sustain' },
  agent_mode: { frequency: 1600, duration_ms: 160, pattern: 'double' },
};

export function buildAvatarPayload(workerPayload: Record<string, unknown>): AvatarPayload {
  const source = String(workerPayload['source'] ?? '');
  const mode = source.includes('agent') || source.includes('worker') ? 'agent' : 'human';
  const emotionalDeltas = (workerPayload['emotional_deltas'] || {}) as Record<string, number>;

  const nodes = buildHexagramNodes(workerPayload);
  const dominant = nodes.reduce((best, node) => (node.voiceWeight > best.voiceWeight ? node : best), nodes[0]);

  const transition_tone = mode === 'agent' ? GGWOW_PATTERNS.transition : null;

  const prevSig = (workerPayload as any)['prev_state_signature'];
  const nextSig = compressStateSignature(workerPayload);

  return {
    session_id: String(workerPayload['session_id'] || 'openjarvis'),
    mode,
    state_signature: nextSig,
    nodes,
    dominant,
    transition_tone,
    timestamp: Date.now(),
  };
}

export function buildHexagramNodes(workerPayload: Record<string, unknown>): HexagramNode[] {
  const allHexagrams = Array.isArray(workerPayload['all_hexagrams'])
    ? (workerPayload['all_hexagrams'] as Array<Record<string, unknown>>)
    : [];
  const consensus = (workerPayload['consensus_vector'] || {}) as Record<string, number>;
  const porosity = Number(workerPayload['porosity_mean'] ?? 0.5);

  if (allHexagrams.length === 0) {
    const fallback = buildFallbackNode(workerPayload, porosity);
    return [fallback];
  }

  return allHexagrams.map((hex, idx) => {
    const binary = String(hex['binary'] || '000000');
    const coords = binaryToSphereCoords(binary, idx, allHexagrams.length);
    const vectors = (hex['vectors'] || consensus) as Record<string, number>;

    return {
      id: Number(hex['hexagram_id'] ?? idx + 1),
      name: String(hex['name'] || ''),
      unicode: String(hex['unicode'] || ''),
      binary,
      x: coords.x,
      y: coords.y,
      z: coords.z,
      radius: 0.6 + Number(vectors['voiceWeight'] ?? 0.5) * 0.6,
      color: vectorToColor(vectors),
      opacity: 0.35 + porosity * 0.6,
      phase: String(hex['phase_temporal'] || 'present'),
      voiceWeight: Number(vectors['voiceWeight'] ?? 0.5),
      coherence: Number(vectors['coherence'] ?? 0.5),
      chaos: Number(vectors['chaos'] ?? 0.5),
      whimsy: Number(vectors['whimsy'] ?? 0.5),
      darkTone: Number(vectors['darkTone'] ?? 0.5),
      porosity,
    } satisfies HexagramNode;
  });
}

function buildFallbackNode(payload: Record<string, unknown>, porosity: number): HexagramNode {
  const vec = (payload['emotional_deltas'] || {}) as Record<string, number>;
  return {
    id: Number(payload['hexagram_id'] ?? 1),
    name: String(payload['hexagram_name'] || ''),
    unicode: String(payload['hexagram_unicode'] || ''),
    binary: String(payload['binary'] || '000000'),
    x: 0,
    y: 0,
    z: 0,
    radius: 0.8,
    color: '#38bdf8',
    opacity: 0.7,
    phase: String(payload['phase_temporal'] || 'present'),
    voiceWeight: Number(vec['voiceWeight'] ?? 0.5),
    coherence: Number(vec['coherence'] ?? 0.5),
    chaos: Number(vec['chaos'] ?? 0.5),
    whimsy: Number(vec['whimsy'] ?? 0.5),
    darkTone: Number(vec['darkTone'] ?? 0.5),
    porosity,
  } satisfies HexagramNode;
}

export function binaryToSphereCoords(binary: string, index: number, total: number) {
  const phi = Math.acos(1 - ((index + 0.5) / Math.max(total, 1)) * 2);
  const theta = Math.PI * (1 + Math.sqrt(5)) * index;

  const liveBits = binary.split('').filter((bit) => bit === '1').length;
  const radius = 1.2 + (liveBits / 6) * 1.4;

  return {
    x: Math.cos(theta) * Math.sin(phi) * radius,
    y: Math.cos(phi) * radius,
    z: Math.sin(theta) * Math.sin(phi) * radius,
  };
}

export function vectorToColor(vec: Record<string, number>): string {
  const r = Math.round((vec['chaos'] ?? 0) * 255);
  const g = Math.round((vec['coherence'] ?? 0.5) * 255);
  const b = Math.round((vec['darkTone'] ?? 0) * 255);
  return `rgb(${r},${g},${b})`;
}

export function nextTransitionTone(payload: AvatarPayload) {
  if (payload.transition_tone) return payload.transition_tone;
  if (payload.dominant?.phase === 'future') return GGWOW_PATTERNS.action;
  return GGWOW_PATTERNS.hold;
}
