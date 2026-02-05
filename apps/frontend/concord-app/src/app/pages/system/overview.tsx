import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Server,
  Box,
  Layers,
  Briefcase,
  Network,
  Bell,
  ArrowRight,
  ChevronRight,
} from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { ProgressRing } from '../../components/system/progress-ring';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';
import { ClusterInfo, K8sEvent, NodeSummary } from '../../types/models';

const POLL_INTERVAL = 10000;

export function SystemOverview() {
  const navigate = useNavigate();
  const [cluster, setCluster] = useState<ClusterInfo | null>(null);
  const [nodes, setNodes] = useState<NodeSummary[]>([]);
  const [events, setEvents] = useState<K8sEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [clusterRes, nodesRes, eventsRes] = await Promise.all([
        api<ApiResponse<ClusterInfo>>('/v2/system/cluster'),
        api<ApiResponse<NodeSummary[]>>('/v2/system/nodes'),
        api<ApiResponse<K8sEvent[]>>('/v2/system/events?limit=20'),
      ]);
      setCluster(clusterRes.data);
      setNodes(nodesRes.data);
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

  const readyNodes = nodes.filter((n) => n.status === 'Ready').length;
  const pods = cluster?.resources.pods;
  const deps = cluster?.resources.deployments;
  const jobs = cluster?.resources.jobs;

  return (
    <div>
      <ErrorAlert message={error} />

      {cluster && (
        <>
          {/* Cluster version banner */}
          <div className="mb-5 flex items-center gap-2 rounded-lg border border-border bg-surface-1 px-4 py-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent-muted">
              <Network size={14} className="text-accent" />
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="font-medium text-text-primary">Kubernetes {cluster.kubernetesVersion}</span>
              <span className="text-border">|</span>
              <span className="text-text-tertiary">{cluster.platforms.join(', ')}</span>
              <span className="text-border">|</span>
              <span className="text-text-tertiary">{cluster.namespaceCount} namespaces</span>
            </div>
          </div>

          {/* Resource ring cards — clickable */}
          <div className="mb-6 grid grid-cols-4 gap-3">
            {/* Nodes */}
            <button
              onClick={() => navigate('/system/nodes')}
              className="group flex flex-col items-center gap-3 rounded-xl border border-border bg-surface-1 p-5 transition-all hover:border-accent/30 hover:shadow-card"
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center gap-2">
                  <Server size={14} className="text-text-tertiary" />
                  <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Nodes</span>
                </div>
                <ChevronRight size={14} className="text-text-tertiary opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <ProgressRing
                value={readyNodes}
                max={cluster.nodeCount}
                color="success"
                centerText={`${readyNodes}/${cluster.nodeCount}`}
                sublabel="ready"
              />
            </button>

            {/* Pods */}
            <div className="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface-1 p-5">
              <div className="flex w-full items-center gap-2">
                <Box size={14} className="text-text-tertiary" />
                <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Pods</span>
              </div>
              <ProgressRing
                value={pods?.running || 0}
                max={pods?.total || 0}
                color="success"
                sublabel="running"
              />
              <div className="flex w-full justify-center gap-3 text-2xs">
                {(pods?.pending || 0) > 0 && (
                  <span className="text-warning">{pods?.pending} pending</span>
                )}
                {(pods?.failed || 0) > 0 && (
                  <span className="text-error">{pods?.failed} failed</span>
                )}
                {(pods?.pending || 0) === 0 && (pods?.failed || 0) === 0 && (
                  <span className="text-success">all healthy</span>
                )}
              </div>
            </div>

            {/* Deployments */}
            <div className="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface-1 p-5">
              <div className="flex w-full items-center gap-2">
                <Layers size={14} className="text-text-tertiary" />
                <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Deployments</span>
              </div>
              <ProgressRing
                value={deps?.available || 0}
                max={deps?.total || 0}
                color="success"
                sublabel="available"
              />
              {(deps?.progressing || 0) > 0 && (
                <span className="text-2xs text-warning">{deps?.progressing} progressing</span>
              )}
            </div>

            {/* Jobs */}
            <div className="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface-1 p-5">
              <div className="flex w-full items-center gap-2">
                <Briefcase size={14} className="text-text-tertiary" />
                <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Jobs</span>
              </div>
              <ProgressRing
                value={jobs?.succeeded || 0}
                max={jobs?.total || 0}
                color="info"
                sublabel="succeeded"
              />
              <div className="flex w-full justify-center gap-3 text-2xs">
                {(jobs?.active || 0) > 0 && (
                  <span className="text-info">{jobs?.active} active</span>
                )}
                {(jobs?.failed || 0) > 0 && (
                  <span className="text-error">{jobs?.failed} failed</span>
                )}
              </div>
            </div>
          </div>

          {/* Services + Namespaces mini stats */}
          <div className="mb-6 grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
              <span className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Services</span>
              <div className="mt-1 text-xl font-bold text-text-primary">{cluster.resources.services.total}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
              <span className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Namespaces</span>
              <div className="mt-1 text-xl font-bold text-text-primary">{cluster.namespaceCount}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
              <span className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Total Pods</span>
              <div className="mt-1 text-xl font-bold text-text-primary">{pods?.total || 0}</div>
              <div className="mt-0.5 text-2xs text-text-tertiary">
                {pods?.succeeded || 0} succeeded
              </div>
            </div>
          </div>
        </>
      )}

      {/* Node quick-look cards */}
      {nodes.length > 0 && (
        <div className="mb-6">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-text-primary">Nodes</h2>
            <button
              onClick={() => navigate('/system/nodes')}
              className="flex items-center gap-1 text-xs text-accent transition-colors hover:text-accent-hover"
            >
              View all <ArrowRight size={12} />
            </button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {nodes.slice(0, 6).map((node) => (
              <button
                key={node.name}
                onClick={() => navigate(`/system/nodes/${node.name}`)}
                className="group flex items-center gap-3 rounded-lg border border-border bg-surface-1 p-3 text-left transition-all hover:border-accent/30 hover:shadow-card"
              >
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                    node.status === 'Ready'
                      ? 'bg-success-muted text-success'
                      : 'bg-error-muted text-error'
                  }`}
                >
                  <Server size={16} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-text-primary">{node.name}</span>
                    <ChevronRight size={12} className="shrink-0 text-text-tertiary opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <div className="flex items-center gap-2 text-2xs text-text-tertiary">
                    <StatusIndicator status={node.status} />
                    <span>{node.roles.join(', ')}</span>
                    <span className="text-border">|</span>
                    <span>{node.allocated.podCount} pods</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Recent events */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell size={14} className="text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">Recent Events</h2>
          </div>
          <button
            onClick={() => navigate('/system/events')}
            className="flex items-center gap-1 text-xs text-accent transition-colors hover:text-accent-hover"
          >
            View all <ArrowRight size={12} />
          </button>
        </div>
        {events.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface-1 py-8 text-center text-sm text-text-tertiary">
            No events
          </div>
        ) : (
          <div className="space-y-1">
            {events.slice(0, 8).map((event) => (
              <div
                key={`${event.object}-${event.reason}-${event.type}-${event.lastSeen}-${event.message}`}
                className="flex items-center gap-3 rounded-lg border border-border bg-surface-1 px-3 py-2 transition-colors hover:bg-surface-2"
              >
                <StatusIndicator status={event.type} />
                <span className="shrink-0 text-xs font-medium text-text-secondary">{event.reason}</span>
                <span className="shrink-0 font-mono text-2xs text-text-tertiary">{event.object}</span>
                <span className="min-w-0 flex-1 truncate text-2xs text-text-tertiary">{event.message}</span>
                <span className="shrink-0 text-2xs text-text-tertiary">
                  <ResourceAge timestamp={event.lastSeen} />
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
