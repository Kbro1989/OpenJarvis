import { EnergyDashboard } from '../components/Dashboard/EnergyDashboard';
import { CostComparison } from '../components/Dashboard/CostComparison';
import { TraceDebugger } from '../components/Dashboard/TraceDebugger';
import { KingwenAdvisoryPanel } from '../components/Dashboard/KingwenAdvisoryPanel';
import { KingwenAvatar3D } from '../components/Dashboard/KingwenAvatar3D';
import { fetchAvatar } from '../lib/kingwenDashboard';
import type { AvatarPayload } from '../lib/avatarProtocol';
import { useAppStore } from '../lib/store';
import { motion } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import {
  fetchManagedAgents,
  fetchBlueprints,
  fetchBlueprintArtifacts,
  fetchJourneyTimeline,
  fetchJourneyStats,
  queryJourney,
  fetchArtifacts,
  type BlueprintRecord,
  type BlueprintArtifactLog,
  type JourneyTimelineEvent,
  type JourneyStats,
  type ManagedAgent,
  type ArtifactRecord,
} from '../lib/api';

export function DashboardPage() {
  const now = new Date();
  const stamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              System Overview
            </h1>
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {stamp}
            </div>
          </div>
          <p
            className="text-sm mt-2 max-w-2xl"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Live telemetry and operational views for your on-device inference stack,
            agent fleet, learning journey, and generated artifacts.
          </p>
        </header>

        <DashboardTabs />
      </div>
    </div>
  );
}

type DashboardTabId = 'overview' | 'blueprints' | 'agents' | 'journey' | 'artifacts' | 'kingwen';

const TABS: { id: DashboardTabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'blueprints', label: 'Blueprints' },
  { id: 'agents', label: 'Agents' },
  { id: 'journey', label: 'Journey' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'kingwen', label: 'King Wen' },
];

function DashboardTabs() {
  const [tab, setTab] = useState<DashboardTabId>('overview');

  return (
    <>
      <div
        className="flex gap-1 mb-6"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        {TABS.map((item) => {
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className="relative px-4 py-2.5 text-sm transition-colors cursor-pointer"
              style={{
                color: active ? 'var(--color-text)' : 'var(--color-text-secondary)',
                fontWeight: active ? 600 : 400,
              }}
            >
              {item.label}
              {active && (
                <motion.span
                  layoutId="dashboard-tab-indicator"
                  className="absolute left-0 right-0 -bottom-px h-[2px]"
                  style={{ background: 'var(--color-accent)' }}
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </div>

      <motion.div
        key={tab}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18 }}
      >
        {tab === 'overview' && <OverviewContent />}
        {tab === 'blueprints' && <BlueprintsTab />}
        {tab === 'agents' && <AgentsTab />}
        {tab === 'journey' && <JourneyTab />}
        {tab === 'artifacts' && <ArtifactsTab />}
        {tab === 'kingwen' && <KingwenTab />}
      </motion.div>
    </>
  );
}

function OverviewContent() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <EnergyDashboard />
      <CostComparison />
    </div>
  );
}

function AgentsTab() {
  const [agents, setAgents] = useState<ManagedAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchManagedAgents();
      setAgents(data);
    } catch (e: any) {
      setError(e?.message || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const statusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'var(--color-accent)';
      case 'needs_attention':
      case 'budget_exceeded':
      case 'stalled':
        return 'var(--color-warning)';
      case 'error':
        return 'var(--color-error)';
      case 'paused':
        return 'var(--color-text-tertiary)';
      default:
        return 'var(--color-success)';
    }
  };

  if (error) {
    return (
      <div
        className="hud-panel p-6"
        style={{ color: 'var(--color-error)' }}
      >
        {error}
      </div>
    );
  }

  return (
    <div className="hud-panel p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="hud-label flex items-center gap-2">
          Managed Agents
        </h3>
        <button
          onClick={refresh}
          className="text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer"
          style={{
            background: 'var(--color-bg-secondary)',
            color: 'var(--color-text-secondary)',
            border: '1px solid var(--color-border)',
          }}
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          Loading agents...
        </div>
      ) : agents.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          No agents yet. Use the Agents page to create your first managed agent.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th className="py-2 pr-4 text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>Agent</th>
                <th className="py-2 pr-4 text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>Type</th>
                <th className="py-2 pr-4 text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>Status</th>
                <th className="py-2 pr-4 text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>Runs</th>
                <th className="py-2 pr-4 text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>Tokens</th>
                <th className="py-2 pr-4 text-xs font-medium" style={{ color: 'var(--color-text-tertiary)' }}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td className="py-2 pr-4" style={{ color: 'var(--color-text)' }}>
                    {agent.name || agent.id}
                  </td>
                  <td className="py-2 pr-4 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {agent.agent_type}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{ color: statusColor(agent.status) }}
                    >
                      <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: statusColor(agent.status) }} />
                      {agent.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {agent.total_runs ?? '—'}
                  </td>
                  <td className="py-2 pr-4 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {agent.total_tokens != null ? agent.total_tokens.toLocaleString() : '—'}
                  </td>
                  <td className="py-2 pr-4 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {agent.total_cost != null ? `$${agent.total_cost.toFixed(4)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function BlueprintsTab() {
  const [blueprints, setBlueprints] = useState<BlueprintRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<Record<string, BlueprintArtifactLog[]>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBlueprints();
      setBlueprints(data);
    } catch (e: any) {
      setError(e?.message || 'Failed to load blueprints');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const loadArtifacts = useCallback(async (key: string) => {
    try {
      const data = await fetchBlueprintArtifacts(key);
      setArtifacts((prev) => ({ ...prev, [key]: data }));
    } catch {
      setArtifacts((prev) => ({ ...prev, [key]: [] }));
    }
  }, []);

  const toggleExpand = (key: string) => {
    setExpandedKey((prev) => {
      const next = prev === key ? null : key;
      if (next && !artifacts[next]) {
        loadArtifacts(next);
      }
      return next;
    });
  };

  if (error) {
    return (
      <div
        className="hud-panel p-6"
        style={{ color: 'var(--color-error)' }}
      >
        {error}
      </div>
    );
  }

  return (
    <div className="hud-panel p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="hud-label flex items-center gap-2">Blueprints</h3>
        <button
          onClick={refresh}
          className="text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer"
          style={{
            background: 'var(--color-bg-secondary)',
            color: 'var(--color-text-secondary)',
            border: '1px solid var(--color-border)',
          }}
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          Loading blueprints...
        </div>
      ) : blueprints.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          No blueprints registered yet.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {blueprints.map((bp) => {
            const expanded = expandedKey === bp.key;
            const rows = artifacts[bp.key];
            return (
              <div
                key={bp.key}
                className="rounded-lg overflow-hidden"
                style={{ border: '1px solid var(--color-border)' }}
              >
                <button
                  onClick={() => toggleExpand(bp.key)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors cursor-pointer"
                  style={{ background: 'var(--color-bg-secondary)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-tertiary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-secondary)')}
                >
                  <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>
                    {bp.title || bp.key}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {bp.status}
                  </span>
                  <span className="flex-1" />
                  <span className="text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                    {expanded ? 'hide' : 'artifacts'}
                  </span>
                </button>
                {expanded && (
                  <div className="px-4 py-3" style={{ borderTop: '1px solid var(--color-border)' }}>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      <div>
                        <span style={{ color: 'var(--color-text-tertiary)' }}>Key</span>
                        <div className="mt-1 font-mono break-all">{bp.key}</div>
                      </div>
                      <div>
                        <span style={{ color: 'var(--color-text-tertiary)' }}>Agent</span>
                        <div className="mt-1">{bp.agent || '—'}</div>
                      </div>
                      <div>
                        <span style={{ color: 'var(--color-text-tertiary)' }}>Schedule</span>
                        <div className="mt-1">{bp.schedule || '—'}</div>
                      </div>
                      <div>
                        <span style={{ color: 'var(--color-text-tertiary)' }}>Artifact</span>
                        <div className="mt-1">{bp.output_artifact || '—'}</div>
                      </div>
                      <div className="md:col-span-2">
                        <span style={{ color: 'var(--color-text-tertiary)' }}>Description</span>
                        <div className="mt-1">{bp.description || '—'}</div>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="text-xs font-medium mb-2" style={{ color: 'var(--color-text-tertiary)' }}>
                        Recent artifact log
                      </div>
                      {!rows || rows.length === 0 ? (
                        <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                          No artifacts yet.
                        </div>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {rows.slice(0, 8).map((row) => (
                            <div
                              key={row.id}
                              className="flex items-center gap-2 rounded px-2 py-1.5"
                              style={{ background: 'var(--color-bg)' }}
                            >
                              <span className="text-[10px] font-mono" style={{ color: 'var(--color-text-tertiary)' }}>
                                {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                              </span>
                              <span className="text-[10px]" style={{ color: 'var(--color-accent)' }}>
                                {row.status}
                              </span>
                              <span className="flex-1 truncate text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                                {row.path || row.summary || '—'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function JourneyTab() {
  const [timeline, setTimeline] = useState<{ events: JourneyTimelineEvent[]; match_count: number; query: string }>({
    events: [],
    match_count: 0,
    query: '',
  });
  const [stats, setStats] = useState<JourneyStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [queryLoading, setQueryLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tl, st] = await Promise.allSettled([fetchJourneyTimeline(), fetchJourneyStats()]);
      if (tl.status === 'fulfilled') setTimeline(tl.value);
      if (st.status === 'fulfilled') setStats(st.value);
    } catch (e: any) {
      setError(e?.message || 'Failed to load journey');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onSearch = useCallback(async () => {
    const term = query.trim();
    if (!term || queryLoading) return;
    setQueryLoading(true);
    try {
      const result = await queryJourney(term);
      setTimeline((prev) => ({
        events: result.events,
        match_count: result.match_count,
        query: result.query,
      }));
    } catch (e: any) {
      setError(e?.message || 'Journey query failed');
    } finally {
      setQueryLoading(false);
    }
  }, [query, queryLoading]);

  const statItems = stats
    ? [
        { label: 'Events', value: String(stats.total_events ?? 0) },
        { label: 'Agent runs', value: String(stats.agent_runs ?? 0) },
        { label: 'Gaps', value: String(stats.knowledge_gaps ?? 0) },
        { label: 'Resolved', value: String(stats.resolved_gaps ?? 0) },
        { label: 'Sessions', value: String(stats.unique_sessions ?? 0) },
      ]
    : [];

  return (
    <div className="space-y-4">
      <div className="hud-panel p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="hud-label flex items-center gap-2">Learning Journey</h3>
          <button
            onClick={load}
            className="text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer"
            style={{
              background: 'var(--color-bg-secondary)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
          >
            Refresh
          </button>
        </div>
        {loading ? (
          <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            Loading journey...
          </div>
        ) : error ? (
          <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-error)' }}>
            {error}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {statItems.map((item) => (
              <div key={item.label} className="rounded-lg p-3" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
                <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                  {item.label}
                </div>
                <div className="text-lg font-semibold mt-1 truncate" style={{ color: 'var(--color-text)' }}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="hud-panel p-6">
        <h3 className="hud-label flex items-center gap-2 mb-3">Timeline</h3>
        <div className="flex gap-2 mb-4">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
            className="flex-1 rounded-md px-3 py-1.5 text-sm outline-none"
            style={{
              background: 'var(--color-bg-secondary)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
            }}
            placeholder="Run a journey query..."
          />
          <button
            onClick={onSearch}
            disabled={queryLoading}
            className="text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer"
            style={{
              background: 'var(--color-accent)',
              color: 'var(--color-bg)',
            }}
          >
            {queryLoading ? 'Querying…' : 'Query'}
          </button>
        </div>
        {timeline.events.length === 0 ? (
          <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            No journey events yet.
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto flex flex-col gap-1.5">
            {timeline.events.slice(0, 50).map((event, idx) => (
              <div
                key={`${event.session_id}-${idx}`}
                className="flex items-start gap-3 rounded px-3 py-2"
                style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}
              >
                <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--color-text-tertiary)', minWidth: 64 }}>
                  {new Date(event.occurred_at * 1000).toLocaleString()}
                </div>
                <div className="flex-1">
                  <div className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                    {event.session_id || 'Journey'}
                  </div>
                  <div className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                    <span className="font-mono">{event.cluster || event.intent || '—'}</span>
                    <span className="mx-1.5" style={{ color: 'var(--color-text-tertiary)' }}>·</span>
                    score {typeof event.score === 'number' ? event.score.toFixed(2) : '—'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ArtifactsTab() {
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ArtifactRecord | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchArtifacts();
      setArtifacts(data);
    } catch (e: any) {
      setError(e?.message || 'Failed to load artifacts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (error) {
    return (
      <div className="hud-panel p-6" style={{ color: 'var(--color-error)' }}>
        {error}
      </div>
    );
  }

  return (
    <div className="hud-panel p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="hud-label flex items-center gap-2">Artifacts</h3>
        <button
          onClick={refresh}
          className="text-xs px-3 py-1.5 rounded-md transition-colors cursor-pointer"
          style={{
            background: 'var(--color-bg-secondary)',
            color: 'var(--color-text-secondary)',
            border: '1px solid var(--color-border)',
          }}
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          Loading artifacts...
        </div>
      ) : artifacts.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
          No artifacts available. Execute a blueprint to generate one.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-1 overflow-y-auto flex flex-col gap-1" style={{ maxHeight: 420 }}>
            {artifacts.map((artifact) => (
              <button
                key={artifact.id}
                onClick={() => setSelected(artifact)}
                className="w-full text-left px-3 py-2 rounded-md transition-colors cursor-pointer"
                style={{
                  background: selected?.id === artifact.id ? 'var(--color-bg-tertiary)' : 'transparent',
                  border: `1px solid ${selected?.id === artifact.id ? 'var(--color-border)' : 'transparent'}`,
                }}
                onMouseEnter={(e) => {
                  if (selected?.id !== artifact.id) e.currentTarget.style.background = 'var(--color-bg-secondary)';
                }}
                onMouseLeave={(e) => {
                  if (selected?.id !== artifact.id) e.currentTarget.style.background = 'transparent';
                }}
              >
                <div className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                  {artifact.summary || artifact.id}
                </div>
                <div className="flex items-center gap-2 text-[10px] mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
                  <span className="capitalize">{artifact.status || 'unknown'}</span>
                  <span>·</span>
                  <span>{artifact.blueprint_key || artifact.kind || artifact.id}</span>
                </div>
              </button>
            ))}
          </div>
          <div className="md:col-span-2 rounded-lg p-4" style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)' }}>
            {selected ? (
              <div className="space-y-3">
                <div>
                  <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                    Status
                  </div>
                  <div className="text-sm mt-1" style={{ color: 'var(--color-text)' }}>
                    {selected.status}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                    Path
                  </div>
                  <div className="text-xs mt-1 font-mono break-all" style={{ color: 'var(--color-text-secondary)' }}>
                    {selected.path || '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                    Summary
                  </div>
                  <div className="text-sm mt-1 whitespace-pre-wrap" style={{ color: 'var(--color-text-secondary)' }}>
                    {selected.summary || '—'}
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                Select an artifact to inspect it.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function KingwenTab() {
  const [sessionId] = useState(() => 'dashboard-session');

  return (
    <div className="flex flex-col gap-4">
      <div className="hud-panel p-6">
        <h3 className="hud-label flex items-center gap-2 mb-3">Live Advisory</h3>
        <KingwenAdvisoryPanel />
      </div>
      <div className="hud-panel p-6">
        <h3 className="hud-label flex items-center gap-2 mb-3">Avatar</h3>
        <KingwenAvatar sessionId={sessionId} />
      </div>
    </div>
  );
}

function KingwenAvatar({ sessionId }: { sessionId: string }) {
  const [avatar, setAvatar] = useState<AvatarPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAvatar() {
      try {
        const data = await fetchAvatar(sessionId);
        if (!cancelled) {
          setAvatar(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    }

    loadAvatar();
    const id = setInterval(loadAvatar, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sessionId]);

  if (error) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <h2 className="text-sm font-semibold text-white/90">King Wen Avatar</h2>
        <p className="mt-2 text-xs text-red-200/90">{error}</p>
      </div>
    );
  }

  if (!avatar) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <h2 className="text-sm font-semibold text-white/90">King Wen Avatar</h2>
        <p className="mt-2 text-xs text-white/70">Loading...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 overflow-hidden">
      <KingwenAvatar3D payload={avatar} />
    </div>
  );
}
