<script lang="ts">
  const COLORS: Record<string, string> = {
    // Existing
    ACTIVE: 'bg-accent-muted text-accent',
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
    DEVELOPMENT: 'bg-warning-muted text-warning',
    COMPLETED: 'bg-info-muted text-info',
    // Execution statuses
    QUEUED: 'bg-surface-2 text-text-secondary',
    PASSED: 'bg-success-muted text-success',
    SKIPPED: 'bg-surface-2 text-text-tertiary',
    // Build / CI statuses
    BUILDING: 'bg-accent-muted text-accent',
    BLOCKED: 'bg-surface-2 text-text-tertiary',
    SUCCESS: 'bg-success-muted text-success',
    BUILD_FAILED: 'bg-error-muted text-error',
    VALIDATING: 'bg-info-muted text-info',
    // Type badges
    MANUFACTURING: 'bg-accent-muted text-accent',
    VALIDATION: 'bg-info-muted text-info',
    // Lifecycle states
    REGISTERED: 'bg-info-muted text-info',
    ASSIGNED: 'bg-success-muted text-success',
    // Test bench statuses
    AVAILABLE: 'bg-success-muted text-success',
    LOCKED: 'bg-warning-muted text-warning',
    // Health statuses
    HEALTHY: 'bg-success-muted text-success',
    DEGRADED: 'bg-warning-muted text-warning',
    UNASSIGNED: 'bg-surface-2 text-text-tertiary',
    EMPTY: 'bg-surface-2 text-text-tertiary',
    UNKNOWN: 'bg-surface-2 text-text-tertiary',
    // Recipe version statuses
    PUBLISHED: 'bg-success-muted text-success',
    // Asset set statuses
    COMPLETE: 'bg-success-muted text-success',
    VALIDATED: 'bg-info-muted text-info',
    // Asset set source badges
    BUILD_SERVICE: 'bg-accent-muted text-accent',
    MANUAL_UPLOAD: 'bg-warning-muted text-warning',
    EXTERNAL_CI: 'bg-surface-2 text-text-secondary',
    // Product lifecycle
    ARCHIVED: 'bg-surface-2 text-text-tertiary',
    INACTIVE: 'bg-surface-2 text-text-tertiary',
    // Error report statuses
    OPEN: 'bg-error-muted text-error',
    ACKNOWLEDGED: 'bg-warning-muted text-warning',
    RESOLVED: 'bg-success-muted text-success',
    DISMISSED: 'bg-surface-2 text-text-tertiary',
  };

  // Human-readable labels for ugly enum values
  const LABELS: Record<string, string> = {
    BUILD_SERVICE: 'Build',
    MANUAL_UPLOAD: 'Manual',
    EXTERNAL_CI: 'External',
    BUILD_FAILED: 'Build Failed',
    EOL: 'End of Life',
  };

  let { status }: { status: string } = $props();

  const colorClass = $derived(COLORS[status] || 'bg-surface-2 text-text-secondary');
  const label = $derived(LABELS[status] || status);
</script>

<span class="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium {colorClass}">
  {label}
</span>
