// The derive layer — turns a raw Topology into the rollups every Atlas lens reads (one catalog,
// many projections). Pure + client-side, so the UI works against TODAY's static snapshots before
// the introspector emits these fields itself; when the producer ships them, this prefers the
// producer's values. No layout here — that is layout.ts. "A view is data."
import type {
  ClusterRollup,
  Endpoint,
  NamespaceSummary,
  ResourceClass,
  Status,
  TopoNode,
  Topology,
} from './contract';
import { worstOf } from './status';

/** The fully-derived cluster — the shared catalog the lenses project. */
export interface ClusterModel {
  topo: Topology;
  byId: Map<string, TopoNode>;
  members: TopoNode[]; // every non-namespace node
  namespaces: NamespaceSummary[]; // ranked worst-first then size
  endpoints: Endpoint[]; // public entrypoint chains, worst-first
  rollup: ClusterRollup; // whole-cluster scorecard source
  publicIds: Set<string>; // ids reachable from a public ingress route
}

const WORKLOAD_KINDS = new Set([
  'deploy',
  'deployment',
  'sts',
  'statefulset',
  'ds',
  'daemonset',
  'cronjob',
  'rollout',
  'job',
]);

/** The robust resource CLASS — keyed off the authoritative k8s type (`meta.kind`) so a Deployment
 *  the producer mislabeled (e.g. cert-manager → secretstore) still counts as a workload. Falls
 *  back to the semantic NodeKind when meta.kind is absent. */
export function classOf(n: TopoNode): ResourceClass {
  const k = (n.meta.kind ?? '').toLowerCase();
  if (WORKLOAD_KINDS.has(k)) return 'workload';
  if (k === 'svc' || k === 'service') return 'service';
  if (k === 'ing' || k === 'ingress') return 'ingress';
  if (k === 'pvc' || k === 'pv' || k === 'volume') return 'volume';
  if (k === 'secret' || k === 'configmap' || k === 'config') return 'config';
  // fall back to the semantic kind
  switch (n.kind) {
    case 'service':
      return 'service';
    case 'ingress':
      return 'ingress';
    case 'pvc':
      return 'volume';
    case 'secretstore':
      return 'config';
    case 'deployment':
    case 'statefulset':
    case 'daemonset':
    case 'cronjob':
    case 'database':
    case 'cache':
    case 'queue':
      return 'workload';
    default:
      return 'other';
  }
}

/** The numeric readiness fraction, preferring the typed `health` over the stringly meta.replicas
 *  ("1/1"). Returns null when neither is present. */
export function readiness(n: TopoNode): { ready: number; desired: number } | null {
  if (n.health) return { ready: n.health.ready, desired: n.health.desired };
  const m = /^(\d+)\s*\/\s*(\d+)$/.exec(n.meta.replicas ?? '');
  if (m) return { ready: Number(m[1]), desired: Number(m[2]) };
  return null;
}

/** Split a comma/space-separated host list into clean hosts. */
function hostsOf(n: TopoNode): string[] {
  return (n.meta.hosts ?? '')
    .split(/[,\s]+/)
    .map((h) => h.trim())
    .filter(Boolean);
}

const blankByStatus = (): Record<Status, number> => ({
  ok: 0,
  warn: 0,
  down: 0,
  progressing: 0,
  unknown: 0,
});

/** Derive the whole catalog from a raw Topology. */
export function deriveCluster(topo: Topology): ClusterModel {
  const byId = new Map(topo.nodes.map((n) => [n.id, n]));
  const members = topo.nodes.filter((n) => n.kind !== 'namespace');

  // ── exposure: anything reachable from an ingress `routes` edge is public ──────────────────────
  const publicIds = new Set<string>();
  const routes = topo.edges.filter((e) => e.kind === 'routes');
  const selects = topo.edges.filter((e) => e.kind === 'selects');
  for (const r of routes) {
    publicIds.add(r.source); // the ingress
    publicIds.add(r.target); // the service
  }
  for (const s of selects) {
    if (publicIds.has(s.source)) publicIds.add(s.target); // workloads behind a public service
  }

  // ── endpoints: ingress host -> service:port -> workload, worst-of the chain ───────────────────
  const endpoints: Endpoint[] = [];
  for (const ing of topo.nodes.filter((n) => n.kind === 'ingress')) {
    const routed = routes.filter((r) => r.source === ing.id);
    const hosts = hostsOf(ing);
    const labels = hosts.length ? hosts : [ing.name];
    labels.forEach((host, hi) => {
      const r = routed[Math.min(hi, routed.length - 1)] as (typeof routed)[number] | undefined;
      const service = r ? byId.get(r.target) : undefined;
      const workload = service
        ? byId.get(selects.find((s) => s.source === service.id)?.target ?? '')
        : undefined;
      const port = r?.meta?.port ?? service?.meta.ports?.split(',')[0]?.trim();
      endpoints.push({
        id: `${ing.id}#${host}`,
        host,
        namespace: ing.namespace ?? '—',
        ingress: ing,
        service,
        workload,
        port,
        path: r?.meta?.path,
        status: worstOf([ing.status, service?.status, workload?.status]),
      });
    });
  }
  endpoints.sort((a, b) => severity(b.status) - severity(a.status) || a.host.localeCompare(b.host));

  // ── per-namespace summaries ───────────────────────────────────────────────────────────────────
  const byNs = new Map<string, TopoNode[]>();
  for (const m of members) {
    const ns = m.namespace ?? '—';
    const list = byNs.get(ns) ?? [];
    list.push(m);
    byNs.set(ns, list);
  }
  const namespaces: NamespaceSummary[] = [...byNs.entries()].map(([name, mem]) => {
    const byClass: Record<ResourceClass, number> = {
      workload: 0,
      service: 0,
      ingress: 0,
      volume: 0,
      config: 0,
      other: 0,
    };
    const byStatus = blankByStatus();
    const hosts: string[] = [];
    const volumes: TopoNode[] = [];
    for (const m of mem) {
      byClass[classOf(m)] += 1;
      byStatus[m.status ?? 'unknown'] += 1;
      if (m.kind === 'ingress') hosts.push(...hostsOf(m));
      if (classOf(m) === 'volume') volumes.push(m);
    }
    return {
      id: `ns/${name}`,
      name,
      rollup: worstOf(mem.map((m) => m.status)),
      total: mem.length,
      byClass,
      byStatus,
      hosts,
      storage: volumes.length
        ? { count: volumes.length, capacity: volumes[0].meta.capacity }
        : undefined,
      members: [...mem].sort(
        (a, b) => severity(b.status) - severity(a.status) || a.name.localeCompare(b.name),
      ),
    } satisfies NamespaceSummary;
  });
  namespaces.sort(
    (a, b) =>
      severity(b.rollup) - severity(a.rollup) || b.total - a.total || a.name.localeCompare(b.name),
  );

  // ── whole-cluster rollup ──────────────────────────────────────────────────────────────────────
  const byStatus = blankByStatus();
  const totals = {
    workloads: 0,
    services: 0,
    ingresses: 0,
    namespaces: byNs.size,
    hosts: endpoints.length,
    volumes: 0,
  };
  for (const m of members) {
    byStatus[m.status ?? 'unknown'] += 1;
    const c = classOf(m);
    if (c === 'workload') totals.workloads += 1;
    else if (c === 'service') totals.services += 1;
    else if (c === 'ingress') totals.ingresses += 1;
    else if (c === 'volume') totals.volumes += 1;
  }
  const rollup: ClusterRollup = { status: worstOf(members.map((m) => m.status)), byStatus, totals };

  return { topo, byId, members, namespaces, endpoints, rollup, publicIds };
}

function severity(s: Status | undefined): number {
  return s === 'down' ? 4 : s === 'warn' ? 3 : s === 'progressing' ? 2 : s === 'ok' ? 1 : 0;
}
