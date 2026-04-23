<script lang="ts">
  import { Package, Clock, Upload, Check } from 'lucide-svelte';

  interface Props {
    value: string;
    onchange: (value: string) => void;
  }

  let { value, onchange }: Props = $props();

  const options = [
    {
      key: 'latest_build',
      label: 'Latest Build',
      description: 'Automatically uses the most recent validated firmware build',
      icon: Clock,
    },
    {
      key: 'specific_version',
      label: 'Specific Version',
      description: 'Pin to a specific firmware version from the build system',
      icon: Package,
    },
    {
      key: 'manual_upload',
      label: 'Manual Upload',
      description: 'Upload firmware binaries manually for each manufacturing run',
      icon: Upload,
    },
  ];
</script>

<div class="space-y-2">
  {#each options as option}
    {@const Icon = option.icon}
    <button
      type="button"
      onclick={() => onchange(option.key)}
      class="flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors {value === option.key ? 'border-accent bg-accent/5' : 'border-border bg-surface-0 hover:bg-surface-2'}"
    >
      <div class="flex h-8 w-8 items-center justify-center rounded-lg {value === option.key ? 'bg-accent/10 text-accent' : 'bg-surface-2 text-text-tertiary'}">
        <Icon size={16} />
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium text-text-primary">{option.label}</div>
        <div class="text-2xs text-text-tertiary">{option.description}</div>
      </div>
      {#if value === option.key}
        <Check size={16} class="text-accent" />
      {/if}
    </button>
  {/each}
</div>
