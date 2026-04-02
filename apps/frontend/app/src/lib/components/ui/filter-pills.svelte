<script lang="ts">
  const STATUS_COLORS: Record<string, { active: string; inactive: string }> = {
    SUCCESS: { active: 'bg-success-muted text-success', inactive: 'bg-surface-2 text-text-tertiary' },
    PASSED: { active: 'bg-success-muted text-success', inactive: 'bg-surface-2 text-text-tertiary' },
    COMPLETED: { active: 'bg-info-muted text-info', inactive: 'bg-surface-2 text-text-tertiary' },
    FAILED: { active: 'bg-error-muted text-error', inactive: 'bg-surface-2 text-text-tertiary' },
    BUILD_FAILED: { active: 'bg-error-muted text-error', inactive: 'bg-surface-2 text-text-tertiary' },
    ERROR: { active: 'bg-error-muted text-error', inactive: 'bg-surface-2 text-text-tertiary' },
    BUILDING: { active: 'bg-accent-muted text-accent', inactive: 'bg-surface-2 text-text-tertiary' },
    RUNNING: { active: 'bg-success-muted text-success', inactive: 'bg-surface-2 text-text-tertiary' },
    PENDING: { active: 'bg-warning-muted text-warning', inactive: 'bg-surface-2 text-text-tertiary' },
    QUEUED: { active: 'bg-surface-3 text-text-secondary', inactive: 'bg-surface-2 text-text-tertiary' },
    SKIPPED: { active: 'bg-surface-3 text-text-secondary', inactive: 'bg-surface-2 text-text-tertiary' },
    CANCELLED: { active: 'bg-surface-3 text-text-secondary', inactive: 'bg-surface-2 text-text-tertiary' },
    VALIDATING: { active: 'bg-info-muted text-info', inactive: 'bg-surface-2 text-text-tertiary' },
  };

  const DEFAULT_COLORS = { active: 'bg-accent-muted text-accent', inactive: 'bg-surface-2 text-text-tertiary' };

  let {
    options,
    selected,
    onchange,
  }: {
    options: { value: string; label: string; color?: string }[];
    selected: Set<string>;
    onchange: (selected: Set<string>) => void;
  } = $props();

  function toggle(value: string) {
    const next = new Set(selected);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    onchange(next);
  }

  function getColors(opt: { value: string; color?: string }) {
    if (opt.color) {
      return { active: opt.color, inactive: 'bg-surface-2 text-text-tertiary' };
    }
    return STATUS_COLORS[opt.value] ?? DEFAULT_COLORS;
  }
</script>

<div class="flex flex-wrap items-center gap-1.5">
  {#each options as opt}
    {@const colors = getColors(opt)}
    {@const isActive = selected.has(opt.value)}
    <button
      type="button"
      onclick={() => toggle(opt.value)}
      class="inline-flex items-center rounded-full px-2.5 py-0.5 text-2xs font-medium transition-colors cursor-pointer {isActive ? colors.active : colors.inactive}"
    >
      {opt.label}
    </button>
  {/each}
</div>
