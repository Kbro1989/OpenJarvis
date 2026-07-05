import { useEffect, useState } from 'react';

type Advisory = {
  hexagram?: string;
  emotionalTongue?: string;
  porosity?: number;
  coherence?: number;
  voiceWeight?: number;
  action?: string;
  category?: string;
  reactionFrame?: string;
};

export function KingwenAdvisoryPanel() {
  const [advisory, setAdvisory] = useState<Advisory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAdvisory() {
      try {
        const resp = await fetch('/v1/kingwen/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: 'Desktop advisor heartbeat', max_states: 1 }),
        });
        const text = await resp.text();
        if (!resp.ok) {
          throw new Error(`kingwen consult failed: ${resp.status} ${text}`);
        }
        const data = JSON.parse(text);
        if (cancelled) return;
        const payload = data.payload ?? data;
        setAdvisory({
          hexagram: payload.hexagram_unicode ?? payload.hexagram ?? null,
          emotionalTongue: payload.emotional_tongue ?? payload.save_string ?? null,
          porosity: payload.porosity ?? null,
          coherence: payload.emotional_deltas?.coherence ?? null,
          voiceWeight: payload.emotional_deltas?.voiceWeight ?? null,
          action: payload.action ?? null,
          category: payload.category ?? null,
          reactionFrame: payload.reaction_frame ?? null,
        });
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    }

    loadAdvisory();
    const interval = setInterval(loadAdvisory, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <h2 className="text-sm font-semibold text-white/90">King Wen Advisory</h2>
        <p className="mt-2 text-xs text-red-200/90">{error}</p>
      </div>
    );
  }

  if (!advisory) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <h2 className="text-sm font-semibold text-white/90">King Wen Advisory</h2>
        <p className="mt-2 text-xs text-white/70">Loading...</p>
      </div>
    );
  }

  const rows = [
    ['Hexagram', advisory.hexagram ?? '—'],
    ['Emotional tongue', advisory.emotionalTongue ?? '—'],
    ['Porosity', advisory.porosity != null ? String(advisory.porosity) : '—'],
    ['Coherence / voiceWeight', [advisory.coherence, advisory.voiceWeight].map(v => v != null ? String(v) : '—').join(' / ')],
    ['Action / category', [advisory.action, advisory.category].filter(Boolean).join(' · ') || '—'],
    ['Reaction frame', advisory.reactionFrame ?? '—'],
  ] as const;

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <h2 className="text-sm font-semibold text-white/90">King Wen Advisory</h2>
      <dl className="mt-3 space-y-2 text-xs text-white/80">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4">
            <dt className="text-white/60">{label}</dt>
            <dd className="text-right text-white/90">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
