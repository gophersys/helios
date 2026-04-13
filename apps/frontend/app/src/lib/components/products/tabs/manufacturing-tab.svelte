<script lang="ts">
  import { Factory, Play } from 'lucide-svelte';
  import ProductStages from '../product-stages.svelte';
  import TestAppStatusCard from '../test-app-status-card.svelte';
  import TestPackageList from '../test-package-list.svelte';
  import FixtureDesignsSection from '../fixture-designs-section.svelte';
  import FixtureInstances from '../fixture-instances.svelte';
  import SessionStartDialog from '$lib/components/manufacturing/session-start-dialog.svelte';
  import type { Product } from '$lib/types/models';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
    selectedRevisionId?: string | null;
  }

  let { product, canManage, onRefresh, selectedRevisionId }: Props = $props();

  const revisions = $derived(
    (product.boards || [])
      .flatMap((b) => b.revisions || [])
      .filter((r) => r.status === 'ACTIVE')
  );

  const selectedRevision = $derived(
    revisions.find((r) => r.id === selectedRevisionId) ?? revisions[0] ?? null
  );

  // Session readiness checks
  const mfgStatus = $derived(product.testAppStatus?.manufacturing ?? null);
  const hasReleasedApp = $derived(mfgStatus?.status === 'RELEASED');
  const hasStage = $derived(revisions.length > 0);

  let showSessionDialog = $state(false);

  function handleSessionStarted(): void {
    onRefresh();
  }
</script>

{#if revisions.length === 0}
  <div class="text-center py-8">
    <Factory size={32} class="mx-auto text-text-tertiary mb-3 opacity-50" />
    <p class="text-sm text-text-secondary">No active board revisions.</p>
    <p class="text-2xs text-text-tertiary mt-1">Add a board revision in the Hardware tab first.</p>
  </div>
{:else}
  <div class="space-y-6">
    <!-- Section 1: Manufacturing Stage -->
    {#if selectedRevision}
      <ProductStages
        productId={product.id}
        productSlug={product.slug ?? ''}
        productName={product.name}
        {revisions}
        fwRepoSlug={product.mfgFwRepoSlug ?? product.fwRepoSlug ?? ''}
        stageType="MANUFACTURING"
        boardRevisionId={selectedRevision.id}
        {canManage}
        {onRefresh}
      />
    {/if}

    <!-- Section 2: Test App -->
    <div class="card card-md">
      <h3 class="text-sm font-semibold text-text-primary mb-3">Test App</h3>
      <TestAppStatusCard status={mfgStatus} type="MANUFACTURING" />
      <TestPackageList productId={product.id} packageType="MANUFACTURING" {onRefresh} />
    </div>

    <!-- Section 3: Fixture Designs -->
    <div class="card card-md">
      <FixtureDesignsSection type="MANUFACTURING" boardRevisionId={selectedRevision?.id} />
    </div>

    <!-- Section 4: Fixture Instances -->
    <div class="card card-md">
      <FixtureInstances
        productId={product.id}
        boardRevisionId={selectedRevision?.id}
        {canManage}
      />
    </div>

    <!-- Section 5: Start Session -->
    <div class="card card-md">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-text-primary">Manufacturing Session</h3>
          <p class="text-2xs text-text-tertiary mt-1">
            {#if !hasStage}
              Enable a manufacturing stage to get started.
            {:else if !hasReleasedApp}
              Release a test app to unlock session creation.
            {:else}
              Start a session to begin manufacturing units.
            {/if}
          </p>
        </div>
        <button
          onclick={() => showSessionDialog = true}
          disabled={!hasStage || !hasReleasedApp}
          class="btn btn-md btn-primary"
        >
          <Play size={16} />
          Start Manufacturing Session
        </button>
      </div>
    </div>
  </div>

  <SessionStartDialog
    open={showSessionDialog}
    productId={product.id}
    boardRevisionId={selectedRevision?.id}
    onClose={() => showSessionDialog = false}
    onStarted={handleSessionStarted}
  />
{/if}
