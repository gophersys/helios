<script lang="ts">
  import type { FlowNodeData, ValidationStepStatus } from './types';
  import { NODE_TYPE_ICONS } from './types';

  let {
    node,
    selected = false,
    onclick = () => {},
  }: {
    node: FlowNodeData;
    selected?: boolean;
    onclick?: () => void;
  } = $props();

  const statusStyles: Record<ValidationStepStatus, string> = {
    PENDING: 'border-surface-2 bg-surface-1 text-text-tertiary',
    BLOCKED: 'border-surface-2 bg-surface-1 text-text-tertiary opacity-60',
    RUNNING: 'border-accent bg-accent/10 text-accent ring-2 ring-accent/30 animate-pulse-subtle',
    PASSED: 'border-success bg-success/10 text-success',
    FAILED: 'border-error bg-error/10 text-error',
    SKIPPED: 'border-warning bg-warning/10 text-warning',
  };

  const statusIcons: Record<ValidationStepStatus, string> = {
    PENDING: '○',
    BLOCKED: '⏸',
    RUNNING: '◐',
    PASSED: '✓',
    FAILED: '✗',
    SKIPPED: '⊘',
  };
</script>

<button
  type="button"
  class="group relative flex h-20 w-40 cursor-pointer flex-col items-center justify-center rounded-lg border-2 transition-all hover:shadow-md {statusStyles[
    node.status
  ]} {selected ? 'ring-2 ring-accent ring-offset-2 ring-offset-surface-0' : ''}"
  onclick={onclick}
>
  <!-- Type icon -->
  <div class="absolute -top-2 left-2 rounded bg-surface-0 px-1 text-xs">
    {NODE_TYPE_ICONS[node.type]}
  </div>

  <!-- Status indicator -->
  <div
    class="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold {node.status ===
    'RUNNING'
      ? 'bg-accent text-white'
      : node.status === 'PASSED'
        ? 'bg-success text-white'
        : node.status === 'FAILED'
          ? 'bg-error text-white'
          : 'bg-surface-2 text-text-secondary'}"
  >
    {statusIcons[node.status]}
  </div>

  <!-- Label -->
  <span class="text-sm font-medium">{node.label}</span>

  <!-- Summary or progress -->
  {#if node.status === 'RUNNING' && node.progress !== undefined}
    <div class="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-surface-2">
      <div
        class="h-full bg-accent transition-all"
        style="width: {node.progress}%"
      ></div>
    </div>
    <span class="mt-0.5 text-xs opacity-80">{node.progress}%</span>
  {:else if node.summary}
    <span class="mt-1 text-xs opacity-80">{node.summary}</span>
  {/if}
</button>

<style>
  @keyframes pulse-subtle {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.85;
    }
  }

  .animate-pulse-subtle {
    animation: pulse-subtle 2s ease-in-out infinite;
  }
</style>
