// Kubernetes resource parsing and formatting utilities

export function parseCpuMillis(val: string): number {
  if (!val) return 0;
  if (val.endsWith('m')) {
    return parseInt(val.slice(0, -1), 10);
  }
  return Math.round(parseFloat(val) * 1000);
}

export function parseMemoryMi(val: string): number {
  if (!val) return 0;
  const num = parseFloat(val);
  if (val.endsWith('Ki')) {
    return num / 1024;
  }
  if (val.endsWith('Mi')) {
    return num;
  }
  if (val.endsWith('Gi')) {
    return num * 1024;
  }
  if (val.endsWith('Ti')) {
    return num * 1024 * 1024;
  }
  // Assume bytes
  return num / (1024 * 1024);
}

export function formatCpu(millis: number): string {
  if (millis >= 1000) {
    return `${(millis / 1000).toFixed(1)} cores`;
  }
  return `${millis}m`;
}

export function formatMem(mi: number): string {
  if (mi >= 1024) {
    return `${(mi / 1024).toFixed(1)} Gi`;
  }
  return `${mi.toFixed(0)} Mi`;
}

export function formatAge(timestamp: string | null): string {
  if (!timestamp) return '-';
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return '<1m';
  if (diffMins < 60) return `${diffMins}m`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d`;
}
