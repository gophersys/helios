// Topology contract — the single shape the visibility canvas renders, regardless of producer.
// Producers (live k8s introspection today; deploy/servicespec or codeinsight later) all emit this;
// the canvas only ever consumes it. Mirrors the codeinsight Report pattern: a view is *data*
// (which nodes/edges to show + how), so adding a view never touches the renderer.

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

/** What an edge represents (the relationship semantics). */
export type EdgeKind =
  | 'routes' //   ingress  -> service
  | 'selects' //  service  -> workload
  | 'mounts' //   workload -> pvc
  | 'contains' // namespace -> member (grouping)
  | 'depends'; //  workload -> workload/infra (declared or inferred)

export interface TopoNode {
  id: string; // stable, unique within the topology (e.g. "deploy/observability/grafana")
  kind: NodeKind;
  name: string; // display label
  namespace?: string;
  /** Small, human-facing facts shown in the node card + detail panel (replicas, image, ports…). */
  meta: Record<string, string>;
  /** Health signal if known: green/amber/red/unknown -> node accent. */
  status?: 'ok' | 'warn' | 'down' | 'unknown';
  /** Optional explicit group (usually the namespace id) for layout clustering. */
  group?: string;
}

export interface TopoEdge {
  id: string;
  source: string; // TopoNode.id
  target: string; // TopoNode.id
  kind: EdgeKind;
  label?: string;
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

/** The lightweight index the cluster picker renders. */
export interface ClusterSummary {
  id: string;
  name: string;
  generatedAt: string;
  nodeCount: number;
  namespaces: number;
}
