<script lang="ts">
  import type { Component } from 'svelte';

  type StatusType = 'success' | 'warning' | 'error' | 'info' | 'neutral';

  interface Props {
    label: string;
    value: string | number;
    icon?: Component;
    subtitle?: string;
    status?: StatusType;
  }

  let { label, value, icon, subtitle, status = 'neutral' }: Props = $props();

  const valueColor = $derived.by(() => {
    switch (status) {
      case 'success': return 'text-success';
      case 'warning': return 'text-warning';
      case 'error': return 'text-error';
      case 'info': return 'text-info';
      default: return 'text-text-primary';
    }
  });
</script>

<div class="card card-sm">
  <div class="flex items-center gap-2 mb-1">
    {#if icon}{@const Icon = icon}<Icon class="w-4 h-4 text-text-tertiary" />{/if}
    <span class="text-2xs font-medium uppercase tracking-wide text-text-secondary">{label}</span>
  </div>
  <div class="text-2xl font-bold {valueColor}">{value}</div>
  {#if subtitle}
    <div class="text-xs text-text-tertiary mt-0.5">{subtitle}</div>
  {/if}
</div>
