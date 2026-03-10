<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ArrowLeft,
    ArrowRight,
    Check,
    Cpu,
    Loader2,
    RefreshCw,
    AlertCircle,
    Wrench,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type {
    UnregisteredMtib,
    FixtureDesignSummary,
    Product,
  } from '$lib/types/models';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import { discoverMtibs, fetchDesigns, createBench } from '$lib/services/validation';

  const auth = getAuth();

  // Wizard steps
  type Step = 1 | 2 | 3 | 4;
  let currentStep = $state<Step>(1);
  let error = $state<string | null>(null);

  // Step 1: Select MTIB
  let mtibs = $state<UnregisteredMtib[]>([]);
  let loadingMtibs = $state(true);
  let selectedMtib = $state<UnregisteredMtib | null>(null);

  // Step 2: Select product & fixture design
  let products = $state<{ value: string; label: string }[]>([]);
  let designs = $state<FixtureDesignSummary[]>([]);
  let loadingProducts = $state(false);
  let selectedProductId = $state('');
  let selectedDesignId = $state('');
  let dutRevision = $state('');

  // Step 3: DUT Info
  let stationId = $state('');
  let benchName = $state('');
  let dutDeviceId = $state('');
  let dutSnr = $state('');
  let dutImei = $state('');
  let dutIccids = $state('');
  let jlinkAppSerial = $state('');
  let jlinkCommsSerial = $state('');
  let uartAppPath = $state('/dev/verdin-uart2');
  let uartCommsPath = $state('/dev/verdin-uart1');

  // Step 4: Review & Create
  let submitting = $state(false);

  // Computed values
  const selectedProduct = $derived(
    products.find((p) => p.value === selectedProductId)
  );
  const selectedDesign = $derived(
    designs.find((d) => d.id === selectedDesignId)
  );
  const filteredDesigns = $derived(
    selectedProductId
      ? designs.filter((d) => d.product.toLowerCase() === selectedProduct?.label.toLowerCase())
      : designs
  );

  async function loadMtibs(): Promise<void> {
    loadingMtibs = true;
    error = null;
    try {
      mtibs = await discoverMtibs();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to discover MTIBs';
    } finally {
      loadingMtibs = false;
    }
  }

  async function loadProductsAndDesigns(): Promise<void> {
    loadingProducts = true;
    try {
      const [prodRes, designRes] = await Promise.all([
        apiFetch<ApiResponse<{ data: Product[] }>>('/v2/catalog'),
        fetchDesigns({ limit: 100 }),
      ]);

      const prodList = Array.isArray(prodRes.data) ? prodRes.data : prodRes.data.data || [];
      products = prodList.map((p) => ({ value: p.id, label: p.name }));
      designs = designRes.data;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load products';
    } finally {
      loadingProducts = false;
    }
  }

  function selectMtib(mtib: UnregisteredMtib): void {
    selectedMtib = mtib;
    // Auto-fill station ID from hostname
    stationId = mtib.hostname.replace(/^mtib-/, 'station-');
    benchName = `${mtib.hostname} Test Bench`;
  }

  function nextStep(): void {
    error = null;
    if (currentStep === 1) {
      if (!selectedMtib) {
        error = 'Please select an MTIB';
        return;
      }
      loadProductsAndDesigns();
      currentStep = 2;
    } else if (currentStep === 2) {
      if (!selectedProductId) {
        error = 'Please select a product';
        return;
      }
      if (!dutRevision.trim()) {
        error = 'Please enter a DUT revision';
        return;
      }
      currentStep = 3;
    } else if (currentStep === 3) {
      if (!stationId.trim()) {
        error = 'Please enter a station ID';
        return;
      }
      if (!benchName.trim()) {
        error = 'Please enter a bench name';
        return;
      }
      currentStep = 4;
    }
  }

  function prevStep(): void {
    error = null;
    if (currentStep > 1) {
      currentStep = (currentStep - 1) as Step;
    }
  }

  async function handleSubmit(): Promise<void> {
    if (!selectedMtib || !selectedProductId) return;
    error = null;
    submitting = true;

    const iccids = dutIccids
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);

    const capabilities = selectedDesign?.capabilities || [];

    const data = {
      stationId: stationId.trim(),
      name: benchName.trim(),
      mtibAddress: selectedMtib.mtibAddress,
      mtibRevision: selectedMtib.hardwareRevision || undefined,
      capabilities,
      fixtureDesignId: selectedDesignId || undefined,
      dutProduct: selectedProduct?.label.toLowerCase() || '',
      dutRevision: dutRevision.trim(),
      dutDeviceId: dutDeviceId.trim() || undefined,
      dutSnr: dutSnr.trim() || undefined,
      dutImei: dutImei.trim() || undefined,
      dutIccids: iccids,
      jlinkAppSerial: jlinkAppSerial.trim() || undefined,
      jlinkCommsSerial: jlinkCommsSerial.trim() || undefined,
      uartAppPath: uartAppPath.trim() || undefined,
      uartCommsPath: uartCommsPath.trim() || undefined,
      status: 'AVAILABLE',
    };

    try {
      await createBench(data);
      goto('/validation/benches');
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to register bench';
    } finally {
      submitting = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Validation.Manage')) {
      goto('/');
      return;
    }
    loadMtibs();
  });
</script>

<svelte:head>
  <title>Register Test Bench - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Register Test Bench"
      description="Add a new MTIB to the validation system with DUT configuration."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Progress Steps -->
  <div class="mb-8 flex items-center justify-center gap-2">
    {#each [1, 2, 3, 4] as step}
      <div class="flex items-center">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors"
          class:bg-accent={currentStep >= step}
          class:text-white={currentStep >= step}
          class:bg-surface-2={currentStep < step}
          class:text-text-tertiary={currentStep < step}
        >
          {#if currentStep > step}
            <Check size={16} />
          {:else}
            {step}
          {/if}
        </div>
        {#if step < 4}
          <div
            class="mx-2 h-0.5 w-12 transition-colors"
            class:bg-accent={currentStep > step}
            class:bg-surface-2={currentStep <= step}
          ></div>
        {/if}
      </div>
    {/each}
  </div>

  <!-- Step labels -->
  <div class="mb-8 flex justify-center">
    <div class="grid grid-cols-4 gap-4 text-center text-2xs">
      <span class:text-accent={currentStep >= 1} class:text-text-tertiary={currentStep < 1}>
        Select MTIB
      </span>
      <span class:text-accent={currentStep >= 2} class:text-text-tertiary={currentStep < 2}>
        Product & Design
      </span>
      <span class:text-accent={currentStep >= 3} class:text-text-tertiary={currentStep < 3}>
        DUT Info
      </span>
      <span class:text-accent={currentStep >= 4} class:text-text-tertiary={currentStep < 4}>
        Review
      </span>
    </div>
  </div>

  <div class="mx-auto max-w-2xl">
    <!-- Step 1: Select MTIB -->
    {#if currentStep === 1}
      <div class="rounded-lg border border-border bg-surface-1 p-6">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-text-primary">Select Unregistered MTIB</h2>
          <button
            onclick={loadMtibs}
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-2"
            disabled={loadingMtibs}
          >
            <RefreshCw size={14} class={loadingMtibs ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {#if loadingMtibs}
          <LoadingState message="Discovering MTIBs in cluster..." />
        {:else if mtibs.length === 0}
          <EmptyState
            icon={Cpu}
            message="No unregistered MTIBs found in the cluster. Make sure the MTIB has joined the K8s cluster and is running the MTIB server."
          />
        {:else}
          <div class="space-y-2">
            {#each mtibs as mtib (mtib.hostname)}
              <button
                onclick={() => selectMtib(mtib)}
                class="w-full rounded-lg border p-4 text-left transition-colors"
                class:border-accent={selectedMtib?.hostname === mtib.hostname}
                class:bg-accent-muted={selectedMtib?.hostname === mtib.hostname}
                class:border-border={selectedMtib?.hostname !== mtib.hostname}
                class:hover:bg-surface-2={selectedMtib?.hostname !== mtib.hostname}
              >
                <div class="flex items-center justify-between">
                  <div>
                    <div class="font-medium text-text-primary">{mtib.hostname}</div>
                    <div class="text-sm text-text-secondary">{mtib.ip}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-sm text-text-secondary">{mtib.mtibAddress}</div>
                    {#if mtib.hardwareRevision}
                      <div class="text-2xs text-text-tertiary">{mtib.hardwareRevision}</div>
                    {/if}
                  </div>
                </div>
                {#if !mtib.ready}
                  <div class="mt-2 flex items-center gap-1 text-2xs text-warning">
                    <AlertCircle size={12} />
                    Node not ready
                  </div>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 2: Product & Fixture Design -->
    {#if currentStep === 2}
      <div class="rounded-lg border border-border bg-surface-1 p-6">
        <h2 class="mb-4 text-lg font-semibold text-text-primary">Product & Fixture Design</h2>

        {#if loadingProducts}
          <LoadingState message="Loading products..." />
        {:else}
          <div class="space-y-4">
            <Select
              bind:value={selectedProductId}
              label="Product"
              placeholder="Select product..."
              options={products}
              required
            />

            <TextInput
              bind:value={dutRevision}
              label="DUT Revision"
              placeholder="e.g. b0"
              required
            />

            <div>
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">
                Fixture Design (Optional)
              </span>
              {#if filteredDesigns.length === 0}
                <div class="rounded-lg border border-border bg-surface-0 p-4 text-center text-sm text-text-tertiary">
                  No fixture designs available for this product
                </div>
              {:else}
                <div class="space-y-2">
                  <button
                    onclick={() => (selectedDesignId = '')}
                    class="w-full rounded-lg border p-3 text-left transition-colors"
                    class:border-accent={!selectedDesignId}
                    class:bg-accent-muted={!selectedDesignId}
                    class:border-border={selectedDesignId}
                    class:hover:bg-surface-2={selectedDesignId}
                  >
                    <div class="text-sm text-text-secondary">No fixture design (manual config)</div>
                  </button>
                  {#each filteredDesigns as design (design.id)}
                    <button
                      onclick={() => (selectedDesignId = design.id)}
                      class="w-full rounded-lg border p-3 text-left transition-colors"
                      class:border-accent={selectedDesignId === design.id}
                      class:bg-accent-muted={selectedDesignId === design.id}
                      class:border-border={selectedDesignId !== design.id}
                      class:hover:bg-surface-2={selectedDesignId !== design.id}
                    >
                      <div class="flex items-center justify-between">
                        <div>
                          <div class="font-medium text-text-primary">{design.name}</div>
                          <div class="text-sm text-text-secondary">
                            {design.product} rev {design.revision}
                          </div>
                        </div>
                        <div class="flex gap-1">
                          {#each design.capabilities.slice(0, 2) as cap}
                            <span class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">
                              {cap}
                            </span>
                          {/each}
                          {#if design.capabilities.length > 2}
                            <span class="text-2xs text-text-tertiary">
                              +{design.capabilities.length - 2}
                            </span>
                          {/if}
                        </div>
                      </div>
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 3: DUT Info -->
    {#if currentStep === 3}
      <div class="rounded-lg border border-border bg-surface-1 p-6">
        <h2 class="mb-4 text-lg font-semibold text-text-primary">Station & DUT Information</h2>

        <div class="space-y-4">
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput
              bind:value={stationId}
              label="Station ID"
              placeholder="e.g. station-33"
              required
            />
            <TextInput
              bind:value={benchName}
              label="Bench Name"
              placeholder="e.g. Alpha B0 Bench 1"
              required
            />
          </div>

          <div class="border-t border-border pt-4">
            <span class="mb-3 block text-2xs font-medium uppercase text-text-tertiary">
              DUT Identification
            </span>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextInput
                bind:value={dutDeviceId}
                label="Device ID"
                placeholder="e.g. 70B3D584C01E1FCC"
              />
              <TextInput bind:value={dutSnr} label="SNR" placeholder="e.g. 0964" />
            </div>
            <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextInput bind:value={dutImei} label="IMEI" placeholder="e.g. 355025931735979" />
              <TextInput
                bind:value={dutIccids}
                label="ICCIDs"
                placeholder="ICCID1, ICCID2 (comma-separated)"
              />
            </div>
          </div>

          <div class="border-t border-border pt-4">
            <span class="mb-3 block text-2xs font-medium uppercase text-text-tertiary">
              Hardware Configuration
            </span>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextInput
                bind:value={jlinkAppSerial}
                label="J-Link App Serial"
                placeholder="e.g. 821009546"
              />
              <TextInput
                bind:value={jlinkCommsSerial}
                label="J-Link Comms Serial"
                placeholder="e.g. 821009537"
              />
            </div>
            <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <TextInput
                bind:value={uartAppPath}
                label="UART App Path"
                placeholder="/dev/verdin-uart2"
              />
              <TextInput
                bind:value={uartCommsPath}
                label="UART Comms Path"
                placeholder="/dev/verdin-uart1"
              />
            </div>
          </div>
        </div>
      </div>
    {/if}

    <!-- Step 4: Review -->
    {#if currentStep === 4}
      <div class="rounded-lg border border-border bg-surface-1 p-6">
        <h2 class="mb-4 text-lg font-semibold text-text-primary">Review & Confirm</h2>

        <div class="space-y-4">
          <div class="rounded-lg bg-surface-0 p-4">
            <div class="mb-2 flex items-center gap-2">
              <Cpu size={16} class="text-accent" />
              <span class="font-medium text-text-primary">MTIB</span>
            </div>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="text-text-tertiary">Hostname</div>
              <div class="text-text-secondary">{selectedMtib?.hostname}</div>
              <div class="text-text-tertiary">Address</div>
              <div class="text-text-secondary">{selectedMtib?.mtibAddress}</div>
              <div class="text-text-tertiary">Station ID</div>
              <div class="text-text-secondary">{stationId}</div>
              <div class="text-text-tertiary">Name</div>
              <div class="text-text-secondary">{benchName}</div>
            </div>
          </div>

          <div class="rounded-lg bg-surface-0 p-4">
            <div class="mb-2 flex items-center gap-2">
              <Wrench size={16} class="text-accent" />
              <span class="font-medium text-text-primary">Configuration</span>
            </div>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="text-text-tertiary">Product</div>
              <div class="text-text-secondary">{selectedProduct?.label || '-'}</div>
              <div class="text-text-tertiary">DUT Revision</div>
              <div class="text-text-secondary">{dutRevision}</div>
              <div class="text-text-tertiary">Fixture Design</div>
              <div class="text-text-secondary">{selectedDesign?.name || 'None'}</div>
            </div>
          </div>

          {#if dutDeviceId || dutSnr || dutImei}
            <div class="rounded-lg bg-surface-0 p-4">
              <div class="mb-2 font-medium text-text-primary">DUT Info</div>
              <div class="grid grid-cols-2 gap-2 text-sm">
                {#if dutDeviceId}
                  <div class="text-text-tertiary">Device ID</div>
                  <div class="font-mono text-text-secondary">{dutDeviceId}</div>
                {/if}
                {#if dutSnr}
                  <div class="text-text-tertiary">SNR</div>
                  <div class="font-mono text-text-secondary">{dutSnr}</div>
                {/if}
                {#if dutImei}
                  <div class="text-text-tertiary">IMEI</div>
                  <div class="font-mono text-text-secondary">{dutImei}</div>
                {/if}
              </div>
            </div>
          {/if}

          {#if jlinkAppSerial || jlinkCommsSerial}
            <div class="rounded-lg bg-surface-0 p-4">
              <div class="mb-2 font-medium text-text-primary">Hardware</div>
              <div class="grid grid-cols-2 gap-2 text-sm">
                {#if jlinkAppSerial}
                  <div class="text-text-tertiary">J-Link App</div>
                  <div class="font-mono text-text-secondary">{jlinkAppSerial}</div>
                {/if}
                {#if jlinkCommsSerial}
                  <div class="text-text-tertiary">J-Link Comms</div>
                  <div class="font-mono text-text-secondary">{jlinkCommsSerial}</div>
                {/if}
                {#if uartAppPath}
                  <div class="text-text-tertiary">UART App</div>
                  <div class="font-mono text-text-secondary">{uartAppPath}</div>
                {/if}
                {#if uartCommsPath}
                  <div class="text-text-tertiary">UART Comms</div>
                  <div class="font-mono text-text-secondary">{uartCommsPath}</div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Navigation buttons -->
    <div class="mt-6 flex items-center justify-between">
      <button
        onclick={() => (currentStep === 1 ? goto('/validation/benches') : prevStep())}
        class="btn btn-sm flex items-center gap-1.5"
      >
        <ArrowLeft size={14} />
        {currentStep === 1 ? 'Cancel' : 'Back'}
      </button>

      {#if currentStep < 4}
        <button onclick={nextStep} class="btn btn-sm btn-primary flex items-center gap-1.5">
          Next
          <ArrowRight size={14} />
        </button>
      {:else}
        <button
          onclick={handleSubmit}
          disabled={submitting}
          class="btn btn-sm btn-primary flex items-center gap-1.5"
        >
          {#if submitting}
            <Loader2 size={14} class="animate-spin" />
            Registering...
          {:else}
            <Check size={14} />
            Register Bench
          {/if}
        </button>
      {/if}
    </div>
  </div>
</div>
