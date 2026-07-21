import { useEffect, useMemo, useState } from 'react';
import {
  BookOpen,
  Brain,
  Sparkles,
  Search,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import {
  fetchJourneyTimeline,
  fetchJourneyStats,
  queryJourney,
  JourneyTimelineEvent as JourneyEvent,
  JourneyStats,
} from '../lib/api';

interface JourneyTimelineResponse {
  events: JourneyEvent[];
  match_count: number;
  query: string;
}

export function JourneyPage() {
  const [timeline, setTimeline] = useState<JourneyTimelineResponse | null>(null);
  const [stats, setStats] = useState<JourneyStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [queryLoading, setQueryLoading] = useState(false);

  const refreshTimeline = async () => {
    try {
      setLoading(true);
      setError(null);
      const [timelineData, statsData] = await Promise.all([
        fetchJourneyTimeline(50),
        fetchJourneyStats(),
      ]);
      setTimeline(timelineData);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load journey data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshTimeline();
  }, []);

  const topSessions = useMemo(() => {
    if (!timeline?.events?.length) return [];
    const map = new Map<string, JourneyEvent & { count: number; totalScore: number }>();
    for (const event of timeline.events) {
      const existing = map.get(event.session_id);
      if (!existing) {
        map.set(event.session_id, { ...event, count: 1, totalScore: event.score });
      } else {
        existing.count += 1;
        existing.totalScore += event.score;
      }
    }
    return Array.from(map.values())
      .sort((a, b) => b.totalScore - a.totalScore)
      .slice(0, 8);
  }, [timeline]);

  const bundles = useMemo(() => {
    const map = new Map<string, JourneyEvent[]>();
    for (const event of timeline?.events ?? []) {
      const key = event.intent || 'Unlabelled thread';
      const existing = map.get(key);
      if (!existing) map.set(key, [event]);
      else existing.push(event);
    }
    return Array.from(map.entries())
      .map(([label, events]) => ({
        label,
        count: events.length,
        topScore: Math.max(...events.map((e) => e.score)),
        sessions: Array.from(new Set(events.map((e) => e.session_id))).slice(0, 5),
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [timeline]);

  const handleQuery = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = query.trim();
    if (!value || queryLoading) return;
    try {
      setQueryLoading(true);
      const data = await queryJourney(value);
      setTimeline((prev) => {
        const merged = {
          ...data,
          events: [...(prev?.events ?? []), ...data.events],
        };
        return merged;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Journey query failed');
    } finally {
      setQueryLoading(false);
    }
  };

  const formatTime = (ts: number) =>
    new Date(ts * 1000).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
                Journey Timeline
              </h1>
              <p className="text-sm mt-2 max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
                Replay and inspect learning emphasis trajectories across sessions, agents, and
                artifact bundles.
              </p>
            </div>
            <button
              onClick={refreshTimeline}
              className="px-3 py-1.5 text-xs rounded-lg border transition-colors cursor-pointer"
              style={{
                color: 'var(--color-text-secondary)',
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </header>

        {error && (
          <div
            className="mb-6 rounded-lg border px-4 py-3 text-sm"
            style={{
              color: 'var(--color-text)',
              borderColor: 'var(--color-border)',
              background: 'var(--color-bg-secondary)',
            }}
          >
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { label: 'Events', value: stats?.total_events ?? 0, icon: BookOpen },
            { label: 'Agent runs', value: stats?.agent_runs ?? 0, icon: Brain },
            { label: 'Knowledge gaps', value: stats?.knowledge_gaps ?? 0, icon: AlertTriangle },
            { label: 'Resolved gaps', value: stats?.resolved_gaps ?? 0, icon: CheckCircle2 },
            { label: 'Sessions', value: stats?.unique_sessions ?? 0, icon: TrendingUp },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border p-4"
              style={{
                color: 'var(--color-text)',
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              <div className="flex items-center gap-2">
                <item.icon size={14} style={{ color: 'var(--color-text-secondary)' }} />
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {item.label}
                </span>
              </div>
              <div className="text-xl font-semibold mt-1">{item.value}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <form
              onSubmit={handleQuery}
              className="flex items-center gap-2 mb-4"
            >
              <div
                className="flex flex-1 items-center gap-2 px-3 py-2 rounded-lg text-sm"
                style={{
                  background: 'var(--color-bg-secondary)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <Search size={14} style={{ color: 'var(--color-text-tertiary)' }} />
                <input
                  type="text"
                  placeholder="Search journey threads..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="flex-1 bg-transparent outline-none text-sm"
                  style={{ color: 'var(--color-text)' }}
                />
                <Sparkles size={14} style={{ color: 'var(--color-text-tertiary)' }} />
              </div>
              <button
                type="submit"
                disabled={queryLoading}
                className="px-3 py-2 text-xs rounded-lg border transition-colors cursor-pointer disabled:opacity-60"
                style={{
                  color: 'var(--color-text)',
                  borderColor: 'var(--color-border)',
                  background: 'var(--color-bg-secondary)',
                }}
              >
                {queryLoading ? 'Querying...' : 'Query'}
              </button>
            </form>

            <div
              className="rounded-lg border divide-y"
              style={{
                color: 'var(--color-text)',
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              {timeline?.events?.length ? (
                timeline.events.map((event, idx) => (
                  <div
                    key={`${event.session_id}-${idx}`}
                    className="px-4 py-3 flex flex-col gap-1"
                    style={{ borderColor: 'var(--color-border)' }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Brain size={14} style={{ color: 'var(--color-text-tertiary)' }} />
                        <span className="text-sm font-medium truncate">
                          {event.intent || event.session_id}
                        </span>
                      </div>
                      <span
                        className="text-xs font-mono"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {event.score.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      <span>Session: {event.session_id}</span>
                      <span>Cluster: {Array.isArray(event.cluster) ? event.cluster.slice(0, 3).join(', ') : '—'}</span>
                      <span>Surface: {event.surface}</span>
                      <span>{formatTime(event.occurred_at)}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="px-4 py-6 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  No journey events yet. Try a query above to bootstrap the timeline.
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <section
              className="rounded-lg border p-4"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              <h2
                className="text-sm font-semibold mb-3"
                style={{ color: 'var(--color-text)' }}
              >
                Top sessions
              </h2>
              <div className="space-y-2">
                {topSessions.length ? (
                  topSessions.map((item) => (
                    <div
                      key={item.session_id}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex min-w-0 flex-col">
                        <span
                          className="truncate"
                          style={{ color: 'var(--color-text)' }}
                        >
                          {item.intent || item.session_id}
                        </span>
                        <span style={{ color: 'var(--color-text-secondary)' }}>
                          {item.path}{' '}
                          {item.surface === 'shared' ? '· shared' : '· private'}
                        </span>
                      </div>
                      <span
                        className="font-mono shrink-0"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {item.totalScore.toFixed(1)}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    No sessions ranked yet.
                  </span>
                )}
              </div>
            </section>

            <section
              className="rounded-lg border p-4"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              <h2
                className="text-sm font-semibold mb-3"
                style={{ color: 'var(--color-text)' }}
              >
                Focus clusters
              </h2>
              <div className="space-y-2">
                {bundles.length ? (
                  bundles.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex min-w-0 flex-col">
                        <span
                          className="truncate"
                          style={{ color: 'var(--color-text)' }}
                        >
                          {item.label}
                        </span>
                        <span style={{ color: 'var(--color-text-secondary)' }}>
                          {item.count} event{item.count === 1 ? '' : 's'}
                        </span>
                      </div>
                      <span
                        className="font-mono shrink-0"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {item.topScore.toFixed(1)}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    Query the journey to surface clusters.
                  </span>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
