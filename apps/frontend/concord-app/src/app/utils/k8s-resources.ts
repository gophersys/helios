export function parseCpuMillis(val: string): number {
  if (!val) return 0;
  if (val.endsWith('m')) return parseInt(val, 10) || 0;
  return (parseFloat(val) || 0) * 1000;
}

export function parseMemoryMi(val: string): number {
  if (!val) return 0;
  if (val.endsWith('Gi')) return (parseFloat(val) || 0) * 1024;
  if (val.endsWith('Mi')) return parseFloat(val) || 0;
  if (val.endsWith('Ki')) return (parseFloat(val) || 0) / 1024;
  return (parseInt(val, 10) || 0) / (1024 * 1024);
}

export function formatCpu(millis: number): string {
  if (millis >= 1000) return `${(millis / 1000).toFixed(1)} cores`;
  return `${millis}m`;
}

export function formatMem(mi: number): string {
  if (mi >= 1024) return `${(mi / 1024).toFixed(1)} Gi`;
  return `${Math.round(mi)} Mi`;
}
