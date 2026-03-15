# Phase 5 — Frontend: Cluster Overview Dashboard

## Objective

Build the main overview page that displays cluster health at a glance: metric cards, resource summary, and a mini events feed.

---

## 1. Create `src/app/pages/system/overview.tsx`

Replace the placeholder from Phase 4 with the full implementation.

```tsx
import { useCallback, useEffect, useState } from 'react';
import { Server, Box, Layers, Briefcase } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { MetricCard } from '../../components/system/metric-card';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';

interface ClusterInfo {
  kubernetesVersion: string;
  platform: string;
  nodeCount: number;
  namespaceCount: number;
  resources: {
    pods: { running: number; pending: number; failed: number; succeeded: number; total: number };
    deployments: { available: number; progressing: number; total: number };
    services: { total: number };
    jobs: { active: number; succeeded: number; failed: number; total: number };
  };
}

interface K8sEvent {
  type: string;
  reason: string;
  message: string;
  object: string;
  namespace: string;
  count: number;
  firstSeen: string | null;
  lastSeen: string | null;
  source: string;
}

const POLL_INTERVAL = 15000; // 15 seconds

export function SystemOverview() {
  const [cluster, setCluster] = useState<ClusterInfo | null>(null);
  const [events, setEvents] = useState<K8sEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [clusterRes, eventsRes] = await Promise.all([
        api<ApiResponse<ClusterInfo>>('/v2/system/cluster'),
        api<ApiResponse<K8sEvent[]>>('/v2/system/events?limit=20'),
      ]);
      setCluster(clusterRes.data);
      setEvents(eventsRes.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load cluster info');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) return <LoadingState message="Loading cluster info..." />;

  return (
    <div>
      <ErrorAlert message={error} />

      {cluster && (
        <>
          {/* Version banner */}
          <div className="mb-4 flex items-center gap-3 text-xs text-text-tertiary">
            <span>Kubernetes {cluster.kubernetesVersion}</span>
            <span className="text-border">|</span>
            <span>{cluster.platform}</span>
            <span className="text-border">|</span>
            <span>{cluster.namespaceCount} namespaces</span>
          </div>

          {/* Metric cards */}
          <div className="mb-6 grid grid-cols-4 gap-3">
            <MetricCard
              label="Nodes"
              value={cluster.nodeCount}
              icon={Server}
              status="neutral"
            />
            <MetricCard
              label="Pods"
              value={cluster.resources.pods.running}
              icon={Box}
              subtitle={`${cluster.resources.pods.total} total, ${cluster.resources.pods.pending} pending, ${cluster.resources.pods.failed} failed`}
              status={cluster.resources.pods.failed > 0 ? 'error' : 'success'}
            />
            <MetricCard
              label="Deployments"
              value={`${cluster.resources.deployments.available}/${cluster.resources.deployments.total}`}
              icon={Layers}
              subtitle="available"
              status={cluster.resources.deployments.progressing > 0 ? 'warning' : 'success'}
            />
            <MetricCard
              label="Jobs"
              value={cluster.resources.jobs.active}
              icon={Briefcase}
              subtitle={`${cluster.resources.jobs.succeeded} succeeded, ${cluster.resources.jobs.failed} failed`}
              status={cluster.resources.jobs.failed > 0 ? 'warning' : 'neutral'}
            />
          </div>
        </>
      )}

      {/* Recent events */}
      <div>
        <h2 className="mb-3 text-sm font-medium text-text-primary">Recent Events</h2>
        {events.length === 0 ? (
          <div className="py-8 text-center text-sm text-text-tertiary">No events</div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Type</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Reason</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Object</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Message</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {events.slice(0, 15).map((event, idx) => (
                  <tr key={`${event.object}-${event.reason}-${idx}`} className="bg-surface-1">
                    <td className="px-3 py-2">
                      <StatusIndicator status={event.type} />
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{event.reason}</td>
                    <td className="px-3 py-2 font-mono text-xs text-text-secondary">{event.object}</td>
                    <td className="max-w-xs truncate px-3 py-2 text-xs text-text-tertiary">{event.message}</td>
                    <td className="px-3 py-2"><ResourceAge timestamp={event.lastSeen} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

## Verification

1. Navigate to `/system` — metric cards display with live cluster data
2. Events table shows recent K8s events with type badges
3. Data auto-refreshes every 15 seconds
4. Error states display correctly if the backend is unreachable
5. Light/dark mode both look correct

---

## Overview Update

```
- [x] Phase 5 — Frontend: cluster overview dashboard
```
