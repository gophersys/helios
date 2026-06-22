// k9s launch — the visibility canvas opens a live k9s TUI for a focused resource. A single ttyd
// (port K9S_PORT) serves `k9s` against a MERGED kubeconfig whose context names ARE the cluster ids
// (home, oracle); ttyd appends `?arg=` query values to the command, so we pass k9s flags that land
// the session on this exact resource: --context <cluster> -n <namespace> -c <resource view>.
// Pure + side-effect-free so it is unit-/e2e-assertable; the DOM open() is the caller's job.
import type { TopoNode } from './contract';

export const K9S_PORT = '7682';

// Authoritative k8s kind (meta.kind) → k9s resource alias the `-c` view opens on.
const K9S_VIEW: Record<string, string> = {
  deploy: 'deploy',
  deployment: 'deploy',
  sts: 'statefulset',
  statefulset: 'statefulset',
  ds: 'daemonset',
  daemonset: 'daemonset',
  svc: 'service',
  service: 'service',
  ing: 'ingress',
  ingress: 'ingress',
  pvc: 'pvc',
};

export function k9sView(node: TopoNode): string {
  return K9S_VIEW[node.meta.kind ?? ''] ?? K9S_VIEW[node.kind] ?? 'pods';
}

export function buildK9sUrl(opts: {
  hostname: string;
  clusterId: string;
  node: TopoNode;
  port?: string;
}): string {
  const args = ['--context', opts.clusterId];
  if (opts.node.namespace) args.push('-n', opts.node.namespace);
  args.push('-c', k9sView(opts.node));
  const qs = args.map((a) => `arg=${encodeURIComponent(a)}`).join('&');
  return `http://${opts.hostname}:${opts.port ?? K9S_PORT}/?${qs}`;
}
