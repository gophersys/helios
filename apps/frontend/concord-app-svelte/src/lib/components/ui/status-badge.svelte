<script lang="ts">
  const COLORS: Record<string, string> = {
    // Existing
    ACTIVE: 'bg-success-muted text-success',
    DEPRECATED: 'bg-warning-muted text-warning',
    EOL: 'bg-error-muted text-error',
    DRAFT: 'bg-accent-muted text-accent',
    RELEASED: 'bg-success-muted text-success',
    UPLOAD: 'bg-accent-muted text-accent',
    EXTERNAL: 'bg-surface-2 text-text-secondary',
    // Node statuses
    ONLINE: 'bg-success-muted text-success',
    OFFLINE: 'bg-surface-2 text-text-tertiary',
    MAINTENANCE: 'bg-warning-muted text-warning',
    ERROR: 'bg-error-muted text-error',
    // Deployment statuses
    PENDING: 'bg-warning-muted text-warning',
    RUNNING: 'bg-success-muted text-success',
    STOPPED: 'bg-surface-2 text-text-secondary',
    FAILED: 'bg-error-muted text-error',
    CANCELLED: 'bg-surface-2 text-text-tertiary',
    COMPLETED: 'bg-info-muted text-info',
    // Execution statuses
    QUEUED: 'bg-surface-2 text-text-secondary',
    PASSED: 'bg-success-muted text-success',
    // Type badges
    MANUFACTURING: 'bg-accent-muted text-accent',
    VALIDATION: 'bg-info-muted text-info',
    // Lifecycle states
    REGISTERED: 'bg-info-muted text-info',
    ASSIGNED: 'bg-success-muted text-success',
    // Health statuses
    HEALTHY: 'bg-success-muted text-success',
    DEGRADED: 'bg-warning-muted text-warning',
    UNASSIGNED: 'bg-surface-2 text-text-tertiary',
    EMPTY: 'bg-surface-2 text-text-tertiary',
    UNKNOWN: 'bg-surface-2 text-text-tertiary',
  };

  let { status }: { status: string } = $props();

  const colorClass = $derived(COLORS[status] || 'bg-surface-2 text-text-secondary');
</script>

<span class="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium {colorClass}">
  {status}
</span>
