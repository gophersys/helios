<script lang="ts">
  import { Cpu, Settings, Layers, Wrench, FileCode, Cog } from 'lucide-svelte';
  import type { BuildConfig } from '$lib/types/models';

  interface Props {
    config: BuildConfig;
  }

  let { config }: Props = $props();

  const targetEntries = $derived(Object.entries(config.targets));
  const overlayEntries = $derived(
    Object.entries(config.overlays).filter(([, files]) => files.length > 0)
  );
  const confFileEntries = $derived(
    Object.entries(config.confFiles).filter(([, files]) => files.length > 0)
  );
</script>

<div class="space-y-4">
  <!-- Build Targets -->
  <section class="rounded-lg border border-border bg-surface-1 p-4">
    <div class="mb-3 flex items-center gap-2 text-text-primary">
      <Cpu size={16} />
      <h4 class="text-sm font-semibold">Build Targets</h4>
    </div>
    <div class="grid gap-3 sm:grid-cols-2">
      {#each targetEntries as [role, target]}
        <div class="rounded-lg border border-border-subtle bg-surface-0 p-3">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-xs font-medium text-text-primary capitalize">{role}</span>
            <span class="rounded-full bg-accent/10 px-2 py-0.5 text-2xs font-mono text-accent">
              AppID {target.appId}
            </span>
          </div>
          <dl class="space-y-1 text-2xs">
            <div class="flex justify-between">
              <dt class="text-text-tertiary">SoC</dt>
              <dd class="font-mono text-text-secondary">{target.soc}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-text-tertiary">Role</dt>
              <dd class="text-text-secondary">{target.role}</dd>
            </div>
          </dl>
        </div>
      {/each}
    </div>
  </section>

  <!-- General Config -->
  <section class="rounded-lg border border-border bg-surface-1 p-4">
    <div class="mb-3 flex items-center gap-2 text-text-primary">
      <Settings size={16} />
      <h4 class="text-sm font-semibold">General</h4>
    </div>
    <dl class="space-y-2 text-sm">
      {#each [
        ['Board', config.board],
        ['NCS Version', config.ncsVersion],
        ['Board Root', config.boardRoot],
      ] as [label, value]}
        <div class="flex items-baseline justify-between border-b border-border-subtle py-1 last:border-0">
          <dt class="text-xs text-text-tertiary">{label}</dt>
          <dd class="font-mono text-xs text-text-primary">{value}</dd>
        </div>
      {/each}
      <div class="flex items-baseline justify-between border-b border-border-subtle py-1">
        <dt class="text-xs text-text-tertiary">VSM Merge</dt>
        <dd>
          <span class={config.hasVsmMerge ? 'text-success text-xs' : 'text-text-tertiary text-xs'}>
            {config.hasVsmMerge ? 'Enabled' : 'Disabled'}
          </span>
        </dd>
      </div>
      <div class="flex items-baseline justify-between py-1">
        <dt class="text-xs text-text-tertiary">FIPS</dt>
        <dd>
          <span class={config.hasFips ? 'text-success text-xs' : 'text-text-tertiary text-xs'}>
            {config.hasFips ? 'Enabled' : 'Disabled'}
          </span>
        </dd>
      </div>
    </dl>
  </section>

  <!-- CFW Config -->
  <section class="rounded-lg border border-border bg-surface-1 p-4">
    <div class="mb-3 flex items-center gap-2 text-text-primary">
      <Layers size={16} />
      <h4 class="text-sm font-semibold">CFW Configuration</h4>
    </div>
    <dl class="space-y-2 text-sm">
      <div class="flex items-baseline justify-between border-b border-border-subtle py-1">
        <dt class="text-xs text-text-tertiary">Device Type</dt>
        <dd class="font-mono text-xs text-text-primary">{config.cfw.deviceType}</dd>
      </div>
      <div class="flex items-baseline justify-between py-1">
        <dt class="text-xs text-text-tertiary">Device Variant</dt>
        <dd class="font-mono text-xs text-text-primary">{config.cfw.deviceVariant}</dd>
      </div>
    </dl>
  </section>

  <!-- Conf Files -->
  {#if confFileEntries.length > 0}
    <section class="rounded-lg border border-border bg-surface-1 p-4">
      <div class="mb-3 flex items-center gap-2 text-text-primary">
        <FileCode size={16} />
        <h4 class="text-sm font-semibold">Configuration Files</h4>
      </div>
      {#each confFileEntries as [target, files]}
        <div class="mb-2 last:mb-0">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary uppercase">{target}</span>
          <div class="space-y-1">
            {#each files as file}
              <div class="rounded border border-border-subtle bg-surface-0 px-2.5 py-1 font-mono text-2xs text-text-secondary">
                {file}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </section>
  {/if}

  <!-- Overlays -->
  {#if overlayEntries.length > 0}
    <section class="rounded-lg border border-border bg-surface-1 p-4">
      <div class="mb-3 flex items-center gap-2 text-text-primary">
        <Cog size={16} />
        <h4 class="text-sm font-semibold">DTS Overlays</h4>
      </div>
      {#each overlayEntries as [target, files]}
        <div class="mb-2 last:mb-0">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary uppercase">{target}</span>
          <div class="space-y-1">
            {#each files as file}
              <div class="rounded border border-border-subtle bg-surface-0 px-2.5 py-1 font-mono text-2xs text-text-secondary">
                {file}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </section>
  {/if}

  <!-- Post-Build Steps -->
  {#if config.postBuild.length > 0}
    <section class="rounded-lg border border-border bg-surface-1 p-4">
      <div class="mb-3 flex items-center gap-2 text-text-primary">
        <Wrench size={16} />
        <h4 class="text-sm font-semibold">Post-Build Steps</h4>
      </div>
      <ol class="space-y-1.5">
        {#each config.postBuild as step, i}
          <li class="flex items-center gap-2">
            <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-2 text-2xs font-medium text-text-tertiary">
              {i + 1}
            </span>
            <span class="font-mono text-xs text-text-secondary">{step}</span>
          </li>
        {/each}
      </ol>
    </section>
  {/if}
</div>
