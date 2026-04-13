<script lang="ts">
  import { Loader2, Play } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import { api } from '$lib/api';
  import { apiFetch } from '$lib/api';
  import { formatTimeAgo } from '$lib/utils/formatting';
  import type { ApiResponse } from '$lib/types';
  import type { Fixture, TestPackage, AssetSet, ManufacturingSession } from '$lib/types/models';

  interface Props {
    open: boolean;
    productId: string;
    boardRevisionId?: string;
    onClose: () => void;
    onStarted: () => void;
  }

  let { open, productId, boardRevisionId, onClose, onStarted }: Props = $props();

  // Step 1: Fixtures
  let fixtures = $state<Fixture[]>([]);
  let loadingFixtures = $state(false);
  let selectedFixtureId = $state('');

  // Step 2: Test Apps
  let testApps = $state<TestPackage[]>([]);
  let loadingTestApps = $state(false);
  let selectedTestAppId = $state('');

  // Step 3: Asset Sets
  let assetSets = $state<AssetSet[]>([]);
  let loadingAssets = $state(false);
  let selectedAssetSetId = $state('');

  // Submission
  let submitting = $state(false);
  let error = $state<string | null>(null);

  const selectedFixture = $derived(fixtures.find(f => f.id === selectedFixtureId));
  const selectedTestApp = $derived(testApps.find(t => t.id === selectedTestAppId));
  const canStart = $derived(!!selectedFixtureId && !!selectedAssetSetId);

  async function fetchFixtures(): Promise<void> {
    loadingFixtures = true;
    try {
      let url = `/v2/fixtures?productId=${productId}&type=MANUFACTURING&limit=50`;
      if (boardRevisionId) url += `&boardRevisionId=${boardRevisionId}`;
      const res = await apiFetch<ApiResponse<{ data: Fixture[] }>>(url);
      const payload = res.data;
      fixtures = Array.isArray(payload) ? payload : (payload as any)?.data || [];
    } catch {
      fixtures = [];
    } finally {
      loadingFixtures = false;
    }
  }

  async function fetchTestApps(): Promise<void> {
    loadingTestApps = true;
    try {
      const res = await api.get<ApiResponse<{ data: TestPackage[] }>>(
        `/v2/products/${productId}/test-packages?type=MANUFACTURING&status=RELEASED&limit=20`
      );
      testApps = res.data?.data ?? (Array.isArray(res.data) ? res.data : []);
    } catch {
      testApps = [];
    } finally {
      loadingTestApps = false;
    }
  }

  async function fetchAssetSets(): Promise<void> {
    loadingAssets = true;
    try {
      let url = `/v2/products/${productId}/asset-sets?status=COMPLETE&limit=20`;
      if (boardRevisionId) url += `&boardRevisionId=${boardRevisionId}`;
      url += '&stageType=MANUFACTURING';
      const res = await api.get<ApiResponse<{ data: AssetSet[] }>>(url);
      assetSets = res.data?.data ?? (Array.isArray(res.data) ? res.data : []);
    } catch {
      assetSets = [];
    } finally {
      loadingAssets = false;
    }
  }

  // Fetch fixtures when dialog opens
  $effect(() => {
    if (open) {
      selectedFixtureId = '';
      selectedTestAppId = '';
      selectedAssetSetId = '';
      error = null;
      fetchFixtures();
    }
  });

  // Fetch test apps when fixture is selected
  $effect(() => {
    if (selectedFixtureId) {
      selectedTestAppId = '';
      selectedAssetSetId = '';
      fetchTestApps();
    }
  });

  // Fetch asset sets when test app is selected
  $effect(() => {
    if (selectedTestAppId) {
      selectedAssetSetId = '';
      fetchAssetSets();
    }
  });

  async function handleStart(): Promise<void> {
    if (!canStart) return;
    submitting = true;
    error = null;
    try {
      const body: Record<string, unknown> = {
        productId,
        fixtureId: selectedFixtureId,
      };
      if (selectedAssetSetId) body.assetSetId = selectedAssetSetId;
      await api.post<ApiResponse<ManufacturingSession>>(
        '/v2/manufacturing/sessions',
        body
      );
      onStarted();
      onClose();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create session';
    } finally {
      submitting = false;
    }
  }
</script>

<Modal {open} title="Start Manufacturing Session" onclose={onClose} size="md">
  <div class="space-y-4">
    {#if error}
      <div class="rounded-lg bg-error-muted px-3 py-2 text-sm text-error">{error}</div>
    {/if}

    <!-- Step 1: Fixture -->
    <div class="form-group">
      <label for="session-fixture" class="form-label">Fixture</label>
      {#if loadingFixtures}
        <div class="flex items-center gap-2 input input-md text-text-tertiary">
          <Loader2 size={14} class="animate-spin" />
          Loading fixtures...
        </div>
      {:else}
        <select id="session-fixture" bind:value={selectedFixtureId} class="input input-md">
          <option value="">Select a fixture...</option>
          {#each fixtures as f}
            <option value={f.id} disabled={!f.active}>
              {f.name}
              {#if f.design} -- {f.design.name} v{f.design.revision}{/if}
              ({f.slotCount ?? 0} slots)
              {#if !f.active} [INACTIVE]{/if}
            </option>
          {/each}
        </select>
        {#if fixtures.length === 0 && !loadingFixtures}
          <p class="form-hint text-warning">No manufacturing fixtures available. Create one first.</p>
        {/if}
      {/if}
    </div>

    <!-- Step 2: Test App (appears after fixture selected) -->
    {#if selectedFixtureId}
      <div class="form-group">
        <label for="session-test-app" class="form-label">Test App</label>
        {#if loadingTestApps}
          <div class="flex items-center gap-2 input input-md text-text-tertiary">
            <Loader2 size={14} class="animate-spin" />
            Loading test apps...
          </div>
        {:else}
          <select id="session-test-app" bind:value={selectedTestAppId} class="input input-md">
            <option value="">Select a released test app...</option>
            {#each testApps as pkg}
              <option value={pkg.id}>
                v{pkg.releasedVersion ?? pkg.version}
                -- {pkg.testCount} tests
                {#if pkg.releasedAt} -- released {formatTimeAgo(pkg.releasedAt)}{/if}
              </option>
            {/each}
          </select>
          {#if testApps.length === 0 && !loadingTestApps}
            <p class="form-hint text-warning">No released test apps. Release a test app first.</p>
          {/if}
        {/if}
      </div>
    {/if}

    <!-- Step 3: Asset Set (appears after test app selected) -->
    {#if selectedTestAppId}
      <div class="form-group">
        <label for="session-asset-set" class="form-label">Asset Set</label>
        {#if loadingAssets}
          <div class="flex items-center gap-2 input input-md text-text-tertiary">
            <Loader2 size={14} class="animate-spin" />
            Loading asset sets...
          </div>
        {:else}
          <select id="session-asset-set" bind:value={selectedAssetSetId} class="input input-md">
            <option value="">Select an asset set...</option>
            {#each assetSets as set}
              <option value={set.id}>
                {set.version} ({set.variant})
                {#if set.commitSha} -- {set.commitSha.slice(0, 7)}{/if}
                -- {formatTimeAgo(set.createdAt)}
              </option>
            {/each}
          </select>
          {#if assetSets.length === 0 && !loadingAssets}
            <p class="form-hint text-warning">No complete asset sets for this stage. Upload assets first.</p>
          {/if}
        {/if}
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <button onclick={onClose} disabled={submitting} class="btn btn-sm btn-ghost">Cancel</button>
    <button onclick={handleStart} disabled={submitting || !canStart} class="btn btn-sm btn-primary">
      {#if submitting}
        <Loader2 size={14} class="animate-spin" />
        Starting...
      {:else}
        <Play size={14} />
        Start Session
      {/if}
    </button>
  {/snippet}
</Modal>
