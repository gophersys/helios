<script lang="ts">
  import { Wrench, Wifi, WifiOff, AlertTriangle } from 'lucide-svelte';
  import type { DashboardFixture } from '$lib/types/models';

  let { fixtures }: { fixtures: DashboardFixture[] } = $props();

  const totalFixtures = $derived(fixtures.length);
  const boardsOnline = $derived(fixtures.reduce((sum, f) => sum + f.nodesOnline, 0));
  const boardsOffline = $derived(fixtures.reduce((sum, f) => sum + f.nodesOffline, 0));
  const boardsError = $derived(fixtures.reduce((sum, f) => sum + f.nodesError, 0));
</script>

<div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
  <!-- Total Fixtures -->
  <div class="card card-sm flex items-center gap-3">
    <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-muted">
      <Wrench size={20} class="text-accent" />
    </div>
    <div>
      <p class="text-2xl font-semibold text-text-primary">{totalFixtures}</p>
      <p class="text-2xs text-text-tertiary">Total Fixtures</p>
    </div>
  </div>

  <!-- Boards Online -->
  <div class="card card-sm flex items-center gap-3">
    <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-success-muted">
      <Wifi size={20} class="text-success" />
    </div>
    <div>
      <p class="text-2xl font-semibold text-success">{boardsOnline}</p>
      <p class="text-2xs text-text-tertiary">Boards Online</p>
    </div>
  </div>

  <!-- Boards Offline -->
  {#if boardsOffline > 0}
    <div class="card card-sm flex items-center gap-3">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-warning-muted">
        <WifiOff size={20} class="text-warning" />
      </div>
      <div>
        <p class="text-2xl font-semibold text-warning">{boardsOffline}</p>
        <p class="text-2xs text-text-tertiary">Boards Offline</p>
      </div>
    </div>
  {/if}

  <!-- Errors -->
  {#if boardsError > 0}
    <div class="card card-sm flex items-center gap-3">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-error-muted">
        <AlertTriangle size={20} class="text-error" />
      </div>
      <div>
        <p class="text-2xl font-semibold text-error">{boardsError}</p>
        <p class="text-2xs text-text-tertiary">Errors</p>
      </div>
    </div>
  {/if}
</div>
