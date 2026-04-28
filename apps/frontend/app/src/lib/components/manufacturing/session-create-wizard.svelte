<script lang="ts">
  import { ChevronRight, ChevronLeft, Check, Loader2, Box, Wrench, Package, Play, X, Factory, FlaskConical } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product, Fixture, AssetSet } from '$lib/types/models';

  interface Props {
    open: boolean;
    onClose: () => void;
    onStarted: (sessionId: string) => void;
  }

  let { open, onClose, onStarted }: Props = $props();

  let step = $state(1);
  let error = $state<string | null>(null);
  let submitting = $state(false);

  // Step 1: Product
  let products = $state<Product[]>([]);
  let selectedProductId = $state('');
  const selectedProduct = $derived(products.find(p => p.id === selectedProductId));

  // Step 2: Fixture Instance
  let fixtures = $state<Fixture[]>([]);
  let selectedFixtureId = $state('');
  const selectedFixture = $derived(fixtures.find(f => f.id === selectedFixtureId));

  // Step 3: Test App
  let testPackages = $state<any[]>([]);
  let selectedTestPackageId = $state('');
  const selectedTestPackage = $derived(testPackages.find(t => t.id === selectedTestPackageId));

  // Step 4: Asset Set
  let assetSets = $state<AssetSet[]>([]);
  let selectedAssetSetId = $state('');
  const selectedAssetSet = $derived(assetSets.find(a => a.id === selectedAssetSetId));

  const stepLabels = ['Product', 'Fixture', 'Test App', 'Assets', 'Start'];
  const stepIcons = [Box, Wrench, FlaskConical, Package, Play];

  // Load products
  $effect(() => {
    if (open && products.length === 0) {
      apiFetch<ApiResponse<any>>('/v2/products').then(res => {
        const payload = res.data;
        products = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
      }).catch(() => { products = []; });
    }
  });

  // Load fixtures when product selected
  $effect(() => {
    if (selectedProductId) {
      apiFetch<ApiResponse<any>>(`/v2/fixtures?productId=${selectedProductId}&type=MANUFACTURING&limit=100`).then(res => {
        const payload = res.data;
        fixtures = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
      }).catch(() => { fixtures = []; });
    } else {
      fixtures = [];
    }
  });

  // Load test packages when fixture selected. DEV fixtures (sandbox rigs)
  // see both DEV and RELEASED candidates so an iteration loop doesn't need
  // a release first; RELEASE fixtures only see RELEASED packages.
  $effect(() => {
    if (selectedProductId && selectedFixtureId) {
      const isDevFixture = (selectedFixture as any)?.purpose === 'DEV';
      const released = apiFetch<ApiResponse<any>>(
        `/v2/products/${selectedProductId}/test-packages?type=MANUFACTURING&status=RELEASED&limit=50`
      );
      const dev = isDevFixture
        ? apiFetch<ApiResponse<any>>(
            `/v2/products/${selectedProductId}/test-packages?type=MANUFACTURING&status=DEVELOPMENT&limit=50`
          )
        : Promise.resolve({ data: { data: [] } } as any);

      Promise.all([released, dev]).then(([rRes, dRes]) => {
        const rPayload = (rRes as any).data;
        const dPayload = (dRes as any).data;
        const rList = Array.isArray(rPayload) ? rPayload : (rPayload as any)?.data ?? [];
        const dList = Array.isArray(dPayload) ? dPayload : (dPayload as any)?.data ?? [];
        testPackages = [...rList, ...dList];
      }).catch(() => { testPackages = []; });
    } else {
      testPackages = [];
    }
  });

  // Load asset sets when test app selected
  $effect(() => {
    if (selectedProductId && selectedFixture?.boardRevisionId && selectedTestPackageId) {
      apiFetch<ApiResponse<any>>(
        `/v2/products/${selectedProductId}/asset-sets?boardRevisionId=${selectedFixture.boardRevisionId}&stageType=MANUFACTURING&status=COMPLETE&limit=50`
      ).then(res => {
        const payload = res.data;
        const items = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
        assetSets = items;
      }).catch(() => { assetSets = []; });
    } else {
      assetSets = [];
    }
  });

  function selectProduct(id: string) {
    selectedProductId = id;
    selectedFixtureId = '';
    selectedAssetSetId = '';
    step = 2;
  }

  function selectFixture(id: string) {
    selectedFixtureId = id;
    selectedTestPackageId = '';
    selectedAssetSetId = '';
    step = 3;
  }

  function selectTestPackage(id: string) {
    selectedTestPackageId = id;
    selectedAssetSetId = '';
    step = 4;
  }

  function selectAssetSet(id: string) {
    selectedAssetSetId = id;
    step = 5;
  }

  function goToStep(s: number) {
    if (s < step) step = s;
  }

  async function handleStart() {
    if (!selectedProductId || !selectedFixtureId) return;
    submitting = true;
    error = null;
    try {
      const body: any = {
        productId: selectedProductId,
        fixtureId: selectedFixtureId,
      };
      if (selectedTestPackageId) body.testPackageId = selectedTestPackageId;
      if (selectedAssetSetId) body.assetSetId = selectedAssetSetId;

      const res = await api.post('/v2/manufacturing/sessions', body);
      const session = (res as any).data;
      onStarted(session.id);
      resetAndClose();
    } catch (e: any) {
      error = e?.data?.errors?.[0]?.message || (e instanceof Error ? e.message : 'Failed to start session');
    } finally {
      submitting = false;
    }
  }

  function resetAndClose() {
    step = 1;
    selectedProductId = '';
    selectedFixtureId = '';
    selectedTestPackageId = '';
    selectedAssetSetId = '';
    error = null;
    onClose();
  }
</script>

<Modal {open} onclose={resetAndClose} size="full" title="" noPadding showCloseButton={false}>
  <div class="flex flex-col h-[90vh]">
    <!-- Header -->
    <div class="flex items-center gap-3 px-6 py-3 border-b border-border shrink-0">
      <div class="flex items-center justify-center w-9 h-9 rounded-lg bg-accent/10">
        <Factory size={18} class="text-accent" />
      </div>
      <div class="flex-1 min-w-0">
        <h2 class="text-sm font-semibold text-text-primary">New Manufacturing Session</h2>
        <p class="text-2xs text-text-tertiary truncate">
          {#if selectedProduct}
            {selectedProduct.name}
            {#if selectedFixture} · {selectedFixture.name}{/if}
          {:else}
            Select a product and fixture to begin
          {/if}
        </p>
      </div>

      {#if selectedFixture}
        <div class="flex items-center gap-2 rounded-lg border border-accent/30 bg-accent-muted px-3 py-2">
          <Wrench size={14} class="text-accent" />
          <span class="text-sm font-semibold text-text-primary">{selectedFixture.name}</span>
          <span class="text-2xs text-text-tertiary">{selectedFixture.panelRows}×{selectedFixture.panelCols}</span>
        </div>
      {/if}

      <button onclick={resetAndClose} class="rounded-lg p-2 text-text-tertiary hover:bg-surface-2 hover:text-text-primary transition-colors">
        <X size={18} />
      </button>
    </div>

    <!-- Step indicator -->
    <div class="flex items-center gap-2 px-6 py-2.5 border-b border-border-subtle bg-surface-0/50 shrink-0">
      {#each stepLabels as label, i}
        {@const stepNum = i + 1}
        {@const isComplete = step > stepNum}
        {@const isCurrent = step === stepNum}
        <button
          onclick={() => goToStep(stepNum)}
          disabled={stepNum > step}
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
            {isCurrent ? 'bg-accent text-white shadow-sm' :
             isComplete ? 'bg-success-muted text-success' :
             'bg-surface-2 text-text-tertiary'}"
        >
          {#if isComplete}
            <Check size={14} />
          {:else}
            {@const Icon = stepIcons[i]}
            <Icon size={14} />
          {/if}
          {label}
        </button>
        {#if i < stepLabels.length - 1}
          <div class="h-px flex-1 bg-border-subtle max-w-8"></div>
        {/if}
      {/each}
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto px-6 py-4">

      <!-- Step 1: Product -->
      {#if step === 1}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Which product are you manufacturing?</p>
          <div class="grid gap-3">
            {#each products.filter(p => p.status === 'ACTIVE') as product}
              <button
                onclick={() => selectProduct(product.id)}
                class="card card-md text-left transition-all
                  {selectedProductId === product.id ? 'border-accent bg-accent-muted' : 'hover:border-text-tertiary'}"
              >
                <div class="flex items-center gap-4">
                  <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-tertiary shrink-0">
                    <Box size={20} />
                  </div>
                  <div class="flex-1 min-w-0">
                    <span class="text-sm font-semibold text-text-primary">{product.name}</span>
                    {#if product.slug}
                      <p class="text-2xs text-text-tertiary">{product.slug}</p>
                    {/if}
                  </div>
                  <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                </div>
              </button>
            {/each}
          </div>
        </div>

      <!-- Step 2: Fixture Instance -->
      {:else if step === 2}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Select a manufacturing fixture.</p>
          {#if fixtures.length === 0}
            <div class="text-center py-8 rounded-xl border-2 border-dashed border-border">
              <Wrench size={32} class="mx-auto mb-3 text-text-tertiary" />
              <p class="text-sm text-text-secondary">No manufacturing fixtures found.</p>
              <p class="text-2xs text-text-tertiary mt-1">Create a fixture in the Fixtures page first.</p>
            </div>
          {:else}
            <div class="grid gap-3">
              {#each fixtures as fixture}
                {@const isAvailable = fixture.assignable === true}
                <button
                  onclick={() => { if (isAvailable) selectFixture(fixture.id); }}
                  disabled={!isAvailable}
                  class="card card-md text-left transition-all
                    {selectedFixtureId === fixture.id ? 'border-accent bg-accent-muted' :
                     !isAvailable ? 'opacity-50 cursor-not-allowed' :
                     'hover:border-text-tertiary'}"
                >
                  <div class="flex items-center gap-4">
                    <div class="flex h-10 w-10 items-center justify-center rounded-lg {isAvailable ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'} shrink-0">
                      <Wrench size={20} />
                    </div>
                    <div class="flex-1 min-w-0">
                      <span class="text-sm font-semibold text-text-primary">{fixture.name}</span>
                      <div class="flex items-center gap-2 mt-0.5">
                        <span class="text-2xs text-text-tertiary">{fixture.panelRows}×{fixture.panelCols} slots</span>
                        {#if fixture.design}
                          <span class="text-2xs text-text-tertiary">· {fixture.design.name}</span>
                        {/if}
                      </div>
                    </div>
                    {#if !isAvailable}
                      <span class="rounded bg-warning-muted px-2 py-0.5 text-2xs font-medium text-warning">In Use</span>
                    {:else}
                      <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                    {/if}
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 3: Test App -->
      {:else if step === 3}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Select which test app version to run.</p>
          {#if testPackages.length === 0}
            <div class="text-center py-8 rounded-xl border-2 border-dashed border-border">
              <FlaskConical size={32} class="mx-auto mb-3 text-text-tertiary" />
              {#if (selectedFixture as any)?.purpose === 'DEV'}
                <p class="text-sm text-text-secondary">No test apps uploaded for this product yet.</p>
                <p class="text-2xs text-text-tertiary mt-1">Upload one with <code>corectl upload</code> — both dev and released candidates show here for dev rigs.</p>
              {:else}
                <p class="text-sm text-text-secondary">No released test apps found.</p>
                <p class="text-2xs text-text-tertiary mt-1">Release a manufacturing test app first, or use a dev fixture to run unreleased builds.</p>
              {/if}
            </div>
          {:else}
            <div class="grid gap-3">
              {#each testPackages as tp}
                <button
                  onclick={() => selectTestPackage(tp.id)}
                  class="card card-md text-left transition-all
                    {selectedTestPackageId === tp.id ? 'border-accent bg-accent-muted' : 'hover:border-text-tertiary'}"
                >
                  <div class="flex items-center gap-4">
                    <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-tertiary shrink-0">
                      <FlaskConical size={20} />
                    </div>
                    <div class="flex-1 min-w-0">
                      <span class="text-sm font-semibold text-text-primary">v{tp.releasedVersion || tp.version}</span>
                      <div class="flex items-center gap-2 mt-0.5">
                        {#if tp.status === 'DEVELOPMENT'}
                          <span class="rounded bg-warning-muted px-1.5 py-0.5 text-2xs font-medium text-warning">DEV</span>
                        {:else}
                          <span class="rounded bg-success-muted px-1.5 py-0.5 text-2xs font-medium text-success">RELEASED</span>
                        {/if}
                        <span class="text-2xs text-text-tertiary">{tp.testCount} tests</span>
                        {#if tp.releasedAt}
                          <span class="text-2xs text-text-tertiary">· {new Date(tp.releasedAt).toLocaleDateString()}</span>
                        {:else if tp.createdAt}
                          <span class="text-2xs text-text-tertiary">· {new Date(tp.createdAt).toLocaleDateString()}</span>
                        {/if}
                      </div>
                    </div>
                    <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 4: Asset Set -->
      {:else if step === 4}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Select firmware assets for this session.</p>
          {#if assetSets.length === 0}
            <div class="text-center py-8 rounded-xl border-2 border-dashed border-border">
              <Package size={32} class="mx-auto mb-3 text-text-tertiary" />
              <p class="text-sm text-text-secondary">No completed asset sets found.</p>
              <p class="text-2xs text-text-tertiary mt-1">Upload assets for the manufacturing stage first.</p>
            </div>
          {:else}
            <div class="grid gap-3">
              {#each assetSets as asset}
                <button
                  onclick={() => selectAssetSet(asset.id)}
                  class="card card-md text-left transition-all
                    {selectedAssetSetId === asset.id ? 'border-accent bg-accent-muted' : 'hover:border-text-tertiary'}"
                >
                  <div class="flex items-center gap-4">
                    <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-tertiary shrink-0">
                      <Package size={20} />
                    </div>
                    <div class="flex-1 min-w-0">
                      <span class="text-sm font-semibold text-text-primary">v{asset.version}</span>
                      <div class="flex items-center gap-2 mt-0.5">
                        <span class="text-2xs text-text-tertiary">{asset.variant}</span>
                        <span class="text-2xs text-text-tertiary">· {asset.source}</span>
                        <span class="text-2xs text-text-tertiary">· {new Date(asset.createdAt).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 5: Review & Start -->
      {:else if step === 5}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Review and start the manufacturing session.</p>

          <div class="card card-md">
            <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">Session Summary</h4>
            <div class="grid grid-cols-2 gap-y-2 gap-x-8 text-sm">
              <div class="text-text-tertiary">Product</div>
              <div class="text-text-primary font-medium">{selectedProduct?.name}</div>
              <div class="text-text-tertiary">Fixture</div>
              <div class="text-text-primary font-medium">{selectedFixture?.name}
                <span class="text-text-tertiary font-normal">{selectedFixture?.panelRows}×{selectedFixture?.panelCols} slots</span>
              </div>
              <div class="text-text-tertiary">Test App</div>
              <div class="text-text-primary font-medium">v{selectedTestPackage?.releasedVersion || selectedTestPackage?.version}
                <span class="text-text-tertiary font-normal">{selectedTestPackage?.testCount} tests</span>
              </div>
              <div class="text-text-tertiary">Assets</div>
              <div class="text-text-primary font-medium">
                {#if selectedAssetSet}
                  v{selectedAssetSet.version} ({selectedAssetSet.variant})
                {:else}
                  <span class="text-text-tertiary">None selected — will use latest</span>
                {/if}
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-accent/30 bg-accent-muted/30 px-4 py-3">
            <p class="text-sm text-text-primary">Starting this session will <strong>lock the fixture</strong> and make it unavailable for other sessions until this one ends.</p>
          </div>

          {#if error}
            <div class="rounded-lg border border-error/30 bg-error-muted px-4 py-3 text-sm text-error">{error}</div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between px-6 py-3 border-t border-border bg-surface-0/50 shrink-0">
      <button
        onclick={step === 1 ? resetAndClose : () => step--}
        class="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-2 transition-colors"
      >
        <ChevronLeft size={16} />
        {step === 1 ? 'Cancel' : 'Back'}
      </button>

      <div class="flex items-center gap-3">
        <span class="text-2xs text-text-tertiary">Step {step} of {stepLabels.length}</span>
        {#if step === 5}
          <button
            onclick={handleStart}
            disabled={submitting || !selectedFixtureId}
            class="flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
          >
            {#if submitting}<Loader2 size={14} class="animate-spin" />{/if}
            {submitting ? 'Starting...' : 'Start Session'}
          </button>
        {/if}
      </div>
    </div>
  </div>
</Modal>
