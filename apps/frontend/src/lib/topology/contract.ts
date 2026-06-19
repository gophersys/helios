// Topology contract — the single shape the visibility canvas renders, regardless of producer.
// Producers (live k8s introspection today; deploy/servicespec or codeinsight later) all emit this;
// the canvas only ever consumes it. Mirrors the codeinsight Report pattern: a view is *data*
// (which nodes/edges to show + how), so adding a view never touches the renderer. The Atlas
// redesign adds derived rollups (also data: computed once in the producer or the client-side
// `model.ts`, never re-aggregated per render) so every lens is a projection of one catalog.

/** What a node represents. Drives the icon + accent. */
export type NodeKind =
  | 'namespace'
  | 'deployment'
  | 'statefulset'
  | 'daemonset'
  | 'cronjob'
  | 'service'
  | 'ingress'
  | 'pvc'
  | 'database'
  | 'cache'
  | 'queue'
  | 'secretstore'
  | 'external';

/** Health signal. `progressing` is a rollout in flight (0 < ready < desired); color-blue/diamond.
 *  Severity order (worst→best): down > warn > progressing > ok > unknown. */
export type Status = 'ok' | 'warn' | 'down' | 'progressing' | 'unknown';

/** The coarse resource CLASS used for counts/inventory grouping. Derived from the authoritative
 *  k8s resource type (`meta.kind`) — robust against the producer's semantic NodeKind guesses
 *  (e.g. a cert-manager Deployment mislabeled `secretstore` is still classed `workload`). */
export type ResourceClass = 'workload' | 'service' | 'ingress' | 'volume' | 'config' | 'other';

/** What an edge represents (the relationship semantics). */
export type EdgeKind =
  | 'routes' //   ingress  -> service
  | 'selects' //  service  -> workload
  | 'mounts' //   workload -> pvc
  | 'contains' // namespace -> member (grouping; never drawn)
  | 'depends'; //  workload -> workload/infra (declared or inferred)

export interface TopoNode {
  id: string; // stable, unique within the topology (e.g. "deploy/observability/grafana")
  kind: NodeKind;
  name: string; // display label
  namespace?: string;
  /** Small, human-facing facts shown in the node card + detail panel (replicas, image, ports…). */
  meta: Record<string, string>;
  /** Health signal if known: green/amber/red/blue/grey -> node accent. */
  status?: Status;
  /** Numeric readiness rollup source (preferred over the stringly meta.replicas). */
  health?: { ready: number; desired: number; restarts?: number; reason?: string };
  /** Reachable from a public ingress route? Drives the Endpoints lens + the Overview globe badge. */
  exposure?: 'public' | 'internal';
  /** Optional explicit group (usually the namespace id) for layout clustering. */
  group?: string;
}

export interface TopoEdge {
  id: string;
  source: string; // TopoNode.id
  target: string; // TopoNode.id
  kind: EdgeKind;
  label?: string;
  /** Route facts co-located on the edge (ingress host/path/port) for the Endpoints chain. */
  meta?: { host?: string; path?: string; port?: string; protocol?: string };
}

/** A named lens over the same node/edge set — architecture, data-flow, etc. */
export interface TopoView {
  id: string;
  title: string;
  description?: string;
  /** Node/edge ids to include; empty `nodes` means "all nodes". */
  nodes: string[];
  edges: string[];
}

export interface Topology {
  clusterId: string; // "home" | "oracle" | …
  clusterName: string; // "Home (k3s)" …
  generatedAt: string; // ISO timestamp of the snapshot
  source: 'live-introspection' | 'servicespec' | 'codeinsight';
  nodes: TopoNode[];
  edges: TopoEdge[];
  views: TopoView[];
}

// ── Derived rollups (data, not layout) ───────────────────────────────────────────────────────────
// Computed by `model.ts` from a Topology so every lens reads numbers, never re-parses strings.

/** A worst-of health rollup for one namespace + its size breakdown. */
export interface NamespaceSummary {
  id: string; // "ns/<name>"
  name: string;
  rollup: Status; // worst-of its members
  total: number; // member count (non-namespace)
  byClass: Record<ResourceClass, number>;
  byStatus: Partial<Record<Status, number>>;
  hosts: string[]; // public ingress hosts the namespace owns
  storage?: { count: number; capacity?: string };
  members: TopoNode[]; // sorted worst-first then name
}

/** One public entrypoint chain: host -> service:port -> workload, health = the chain's worst. */
export interface Endpoint {
  id: string;
  host: string;
  namespace: string;
  ingress: TopoNode;
  service?: TopoNode;
  workload?: TopoNode;
  port?: string;
  path?: string;
  status: Status; // worst-of the chain
}

/** The whole-cluster rollup that powers the Scorecard banner. */
export interface ClusterRollup {
  status: Status; // worst-of all members
  byStatus: Record<Status, number>;
  totals: {
    workloads: number;
    services: number;
    ingresses: number;
    namespaces: number;
    hosts: number;
    volumes: number;
  };
}

/** The lightweight index the cluster switcher renders (with its worst-of health dot). */
export interface ClusterSummary {
  id: string;
  name: string;
  generatedAt: string;
  status: Status;
  namespaces: number;
}
