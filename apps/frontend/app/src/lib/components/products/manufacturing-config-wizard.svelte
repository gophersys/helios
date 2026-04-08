<script lang="ts">
  import Modal from '$lib/components/ui/modal.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FirmwareSourcePicker from './firmware-source-picker.svelte';
  import ManufacturingStageConfigComponent from './manufacturing-stage-config.svelte';
  import {
    ChevronRight, ChevronLeft, Check, CircuitBoard,
    Zap, Cpu, ShieldCheck, Package, Loader2,
    CheckCircle2, XCircle,
  } from 'lucide-svelte';
  import type { BoardRevision, ManufacturingConfig, ManufacturingStageConfig } from '$lib/types/models';
  import { api } from '$lib/api';
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    productId: string;
    revisions: BoardRevision[];
    existingConfig: ManufacturingConfig | null;
    onClose: () => void;
    onSaved: () => void;
  }

  let { open, productId, revisions, existingConfig, onClose, onSaved }: Props = $props();

  // ── Wizard state ───────────────────────────────────────
  let currentStep = $state(1);
  let saving = $state(false);
  let error = $state<string | null>(null);

  const totalSteps = 4;

  // Step 1: Base configuration
  let formRevisionId = $state('');
  let formEnabled = $state(true);

  // Step 2: Stage configuration
  let stages = $state<ManufacturingStageConfig[]>([
    { name: 'electrical', enabled: true, config: { ch0Voltage: 4.5, ch1Voltage: 0, minCurrentMa: 5, maxCurrentMa: 100, i2cAddresses: '0x38,0x50' } },
    { name: 'flash', enabled: true, config: { flashApp: true, flashComms: true, jlinkSpeed: 4000 } },
    { name: 'post', enabled: true, config: { boot: true, chipId: true, bms: true, charger: true, gps: true, modem: true, imei: true, flashRW: true, personalize: true, ipcRekey: true } },
  ]);

  // Step 2: Firmware source
  let firmwareSource = $state('latest_build');

  // Step 3: Pass criteria
  let allStagesMustPass = $state(true);
  let maxRetriesPerUnit = $state(3);
  let electricalTimeLimit = $state(30);
  let flashTimeLimit = $state(120);
  let postTimeLimit = $state(300);

  // Step 3: Personalization
  let coreOpsUrl = $state('https://10.4.45.3:443');
  let deviceType = $state(2);
  let deviceVariant = $state(3);
  let defaultCarrier = $state('Onomondo');

  // ── Derived ────────────────────────────────────────────
  const selectableRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE' || r.status === 'DRAFT'));
  const selectedRevision = $derived(revisions.find((r) => r.id === formRevisionId));
  const step1Valid = $derived(!!formRevisionId);
  const step2Valid = $derived(stages.some((s) => s.enabled));
  const step3Valid = $derived(maxRetriesPerUnit >= 0);

  const isUpdate = $derived(!!existingConfig);

  // ── Initialize on open ─────────────────────────────────
  $effect(() => {
    if (open) {
      currentStep = 1;
      error = null;

      if (existingConfig) {
        formRevisionId = existingConfig.boardRevisionId;
        formEnabled = existingConfig.enabled;
        firmwareSource = existingConfig.firmwareSource;

        // Restore stages
        if (existingConfig.stages?.length) {
          stages = existingConfig.stages.map((s) => ({ ...s, config: { ...s.config } }));
        }

        // Restore pass criteria
        if (existingConfig.passCriteria) {
          allStagesMustPass = existingConfig.passCriteria.allStagesMustPass ?? true;
          maxRetriesPerUnit = existingConfig.passCriteria.maxRetriesPerUnit ?? 3;
          const tl = existingConfig.passCriteria.timingLimits ?? {};
          electricalTimeLimit = (tl.electrical as number) ?? 30;
          flashTimeLimit = (tl.flash as number) ?? 120;
          postTimeLimit = (tl.post as number) ?? 300;
        }

        // Restore personalization
        if (existingConfig.personalizationConfig) {
          coreOpsUrl = existingConfig.personalizationConfig.coreOpsUrl;
          deviceType = existingConfig.personalizationConfig.deviceType;
          deviceVariant = existingConfig.personalizationConfig.deviceVariant;
          defaultCarrier = existingConfig.personalizationConfig.defaultCarrier;
        }
      } else {
        // Defaults for new config
        formRevisionId = selectableRevisions.length === 1 ? selectableRevisions[0].id : '';
        formEnabled = true;
        firmwareSource = 'latest_build';
        stages = [
          { name: 'electrical', enabled: true, config: { ch0Voltage: 4.5, ch1Voltage: 0, minCurrentMa: 5, maxCurrentMa: 100, i2cAddresses: '0x38,0x50' } },
          { name: 'flash', enabled: true, config: { flashApp: true, flashComms: true, jlinkSpeed: 4000 } },
          { name: 'post', enabled: true, config: { boot: true, chipId: true, bms: true, charger: true, gps: true, modem: true, imei: true, flashRW: true, personalize: true, ipcRekey: true } },
        ];
        allStagesMustPass = true;
        maxRetriesPerUnit = 3;
        electricalTimeLimit = 30;
        flashTimeLimit = 120;
        postTimeLimit = 300;
        coreOpsUrl = 'https://10.4.45.3:443';
        deviceType = 2;
        deviceVariant = 3;
        defaultCarrier = 'Onomondo';
      }
    }
  });

  // ── Navigation ─────────────────────────────────────────
  function nextStep() {
    if (currentStep < totalSteps) currentStep++;
  }

  function prevStep() {
    if (currentStep > 1) currentStep--;
  }

  function canAdvance(): boolean {
    switch (currentStep) {
      case 1: return step1Valid;
      case 2: return step2Valid;
      case 3: return step3Valid;
      default: return true;
    }
  }

  function updateStage(index: number, updated: ManufacturingStageConfig) {
    stages = stages.map((s, i) => (i === index ? updated : s));
  }

  // ── Save ───────────────────────────────────────────────
  async function save() {
    saving = true;
    error = null;

    const payload = {
      boardRevisionId: formRevisionId,
      enabled: formEnabled,
      stages,
      firmwareSource,
      firmwareSetId: null,
      personalizationConfig: stages.find((s) => s.name === 'post' && s.enabled)
        ? { coreOpsUrl, deviceType, deviceVariant, defaultCarrier }
        : null,
      passCriteria: {
        allStagesMustPass,
        maxRetriesPerUnit,
        timingLimits: {
          electrical: electricalTimeLimit,
          flash: flashTimeLimit,
          post: postTimeLimit,
        },
      },
    };

    try {
      if (isUpdate) {
        await api.put(`/v2/products/${productId}/manufacturing`, payload);
      } else {
        await api.post(`/v2/products/${productId}/manufacturing`, payload);
      }
      onSaved();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save manufacturing config';
    } finally {
      saving = false;
    }
  }

  const stepLabels = ['Base Config', 'Stages', 'Pass Criteria', 'Review & Save'];
</script>

<Modal
  {open}
  title="{isUpdate ? 'Edit' : 'Configure'} Manufacturing"
  onclose={onClose}
  size="xl"
>
  <!-- Step indicator -->
  <div class="mb-5 flex items-center gap-1">
    {#each stepLabels as label, i}
      {@const stepNum = i + 1}
      <div class="flex items-center gap-1 {i > 0 ? 'flex-1' : ''}">
        {#if i > 0}
          <div class="h-px flex-1 {currentStep > i ? 'bg-accent' : 'bg-border'}"></div>
        {/if}
        <button
          type="button"
          onclick={() => { if (stepNum <= currentStep) currentStep = stepNum; }}
          class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-2xs font-medium transition-colors {currentStep === stepNum ? 'bg-accent text-white' : currentStep > stepNum ? 'bg-accent/10 text-accent' : 'bg-surface-2 text-text-tertiary'}"
        >
          {#if currentStep > stepNum}
            <Check size={10} />
          {:else}
            {stepNum}
          {/if}
          <span class="hidden sm:inline">{label}</span>
        </button>
      </div>
    {/each}
  </div>

  <ErrorAlert message={error} />

  <!-- Step 1: Base Configuration -->
  {#if currentStep === 1}
    <div class="space-y-4">
      <div>
        <h3 class="text-sm font-semibold text-text-primary">Base Configuration</h3>
        <p class="mt-1 text-2xs text-text-tertiary">Select the board revision and enable manufacturing.</p>
      </div>

      <label class="block">
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Board Revision *</span>
        <select
          bind:value={formRevisionId}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        >
          <option value="">Select a revision...</option>
          {#each selectableRevisions as rev}
            <option value={rev.id}>{rev.version} {rev.ckBoardsName ? `(${rev.ckBoardsName})` : ''}</option>
          {/each}
        </select>
      </label>

      <label class="flex items-center gap-3">
        <div class="relative inline-flex cursor-pointer items-center">
          <input type="checkbox" bind:checked={formEnabled} class="peer sr-only" />
          <div class="peer h-5 w-9 rounded-full bg-surface-2 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:bg-accent peer-checked:after:translate-x-full"></div>
        </div>
        <div>
          <span class="text-sm font-medium text-text-primary">Enable manufacturing</span>
          <p class="text-2xs text-text-tertiary">When enabled, manufacturing sessions can be started for this configuration.</p>
        </div>
      </label>
    </div>

  <!-- Step 2: Stage Configuration -->
  {:else if currentStep === 2}
    <div class="space-y-4">
      <div>
        <h3 class="text-sm font-semibold text-text-primary">Stage Configuration</h3>
        <p class="mt-1 text-2xs text-text-tertiary">Configure each manufacturing stage. At least one stage must be enabled.</p>
      </div>

      <div class="space-y-3">
        {#each stages as stage, i}
          <ManufacturingStageConfigComponent
            {stage}
            onupdate={(updated) => updateStage(i, updated)}
          />
        {/each}
      </div>

      <div class="border-t border-border pt-4">
        <h4 class="mb-2 text-xs font-semibold text-text-tertiary">Firmware Source</h4>
        <FirmwareSourcePicker value={firmwareSource} onchange={(v) => (firmwareSource = v)} />
      </div>
    </div>

  <!-- Step 3: Pass Criteria -->
  {:else if currentStep === 3}
    <div class="space-y-4">
      <div>
        <h3 class="text-sm font-semibold text-text-primary">Pass Criteria & Personalization</h3>
        <p class="mt-1 text-2xs text-text-tertiary">Define pass/fail thresholds and personalization settings.</p>
      </div>

      <!-- Pass criteria -->
      <div class="rounded-xl border border-border bg-surface-0 p-4 space-y-3">
        <h4 class="text-xs font-semibold text-text-tertiary">Pass Criteria</h4>

        <label class="flex items-center gap-3">
          <input type="checkbox" bind:checked={allStagesMustPass} class="rounded border-border" />
          <span class="text-sm text-text-primary">All stages must pass for unit to pass</span>
        </label>

        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Max Retries Per Unit</span>
          <input
            type="number"
            min="0"
            max="10"
            bind:value={maxRetriesPerUnit}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          />
        </label>

        <div class="grid gap-3 sm:grid-cols-3">
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Electrical Timeout (s)</span>
            <input type="number" bind:value={electricalTimeLimit} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Flash Timeout (s)</span>
            <input type="number" bind:value={flashTimeLimit} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">POST Timeout (s)</span>
            <input type="number" bind:value={postTimeLimit} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
          </label>
        </div>
      </div>

      <!-- Personalization config (only shown if POST stage is enabled) -->
      {#if stages.find((s) => s.name === 'post' && s.enabled)}
        <div class="rounded-xl border border-border bg-surface-0 p-4 space-y-3">
          <h4 class="text-xs font-semibold text-text-tertiary">Personalization</h4>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">CoreOps Server URL</span>
            <input
              type="text"
              bind:value={coreOpsUrl}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <div class="grid gap-3 sm:grid-cols-3">
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Type</span>
              <input type="number" bind:value={deviceType} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
            </label>
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Variant</span>
              <input type="number" bind:value={deviceVariant} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
            </label>
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Default Carrier</span>
              <input type="text" bind:value={defaultCarrier} class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none" />
            </label>
          </div>
        </div>
      {/if}
    </div>

  <!-- Step 4: Review & Save -->
  {:else if currentStep === 4}
    <div class="space-y-4">
      <div>
        <h3 class="text-sm font-semibold text-text-primary">Review Configuration</h3>
        <p class="mt-1 text-2xs text-text-tertiary">Review your manufacturing configuration before saving.</p>
      </div>

      <!-- Base config summary -->
      <div class="rounded-xl border border-border bg-surface-0 p-4 space-y-2">
        <h4 class="text-xs font-semibold text-text-tertiary">Base Configuration</h4>
        <div class="grid gap-2 text-sm">
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">Board Revision</span>
            <span class="text-text-primary">{selectedRevision?.version ?? 'Unknown'}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">Manufacturing</span>
            <span class="text-text-primary">{formEnabled ? 'Enabled' : 'Disabled'}</span>
          </div>
        </div>
      </div>

      <!-- Stages summary -->
      <div class="rounded-xl border border-border bg-surface-0 p-4 space-y-2">
        <h4 class="text-xs font-semibold text-text-tertiary">Stages</h4>
        <div class="space-y-1">
          {#each stages as stage}
            <div class="flex items-center gap-2 text-sm">
              {#if stage.enabled}
                <CheckCircle2 size={14} class="text-success" />
              {:else}
                <XCircle size={14} class="text-text-tertiary" />
              {/if}
              <span class="capitalize text-text-primary">{stage.name}</span>
              <span class="text-text-tertiary">{stage.enabled ? 'Enabled' : 'Disabled'}</span>
            </div>
          {/each}
        </div>
      </div>

      <!-- Firmware source summary -->
      <div class="rounded-xl border border-border bg-surface-0 p-4 space-y-2">
        <h4 class="text-xs font-semibold text-text-tertiary">Firmware Source</h4>
        <span class="text-sm text-text-primary capitalize">{firmwareSource.replace(/_/g, ' ')}</span>
      </div>

      <!-- Pass criteria summary -->
      <div class="rounded-xl border border-border bg-surface-0 p-4 space-y-2">
        <h4 class="text-xs font-semibold text-text-tertiary">Pass Criteria</h4>
        <div class="grid gap-1 text-sm">
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">All stages must pass</span>
            <span class="text-text-primary">{allStagesMustPass ? 'Yes' : 'No'}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-text-secondary">Max retries</span>
            <span class="text-text-primary">{maxRetriesPerUnit}</span>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Footer navigation -->
  {#snippet footer()}
    <div class="flex w-full items-center justify-between">
      <button
        type="button"
        onclick={currentStep === 1 ? onClose : prevStep}
        class="flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
      >
        {#if currentStep > 1}
          <ChevronLeft size={14} />
          Back
        {:else}
          Cancel
        {/if}
      </button>

      {#if currentStep < totalSteps}
        <button
          type="button"
          onclick={nextStep}
          disabled={!canAdvance()}
          class="flex items-center gap-1 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Next
          <ChevronRight size={14} />
        </button>
      {:else}
        <button
          type="button"
          onclick={save}
          disabled={saving}
          class="flex items-center gap-1 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {#if saving}
            <Loader2 size={14} class="animate-spin" />
            Saving...
          {:else}
            <Check size={14} />
            {isUpdate ? 'Update' : 'Create'} Configuration
          {/if}
        </button>
      {/if}
    </div>
  {/snippet}
</Modal>
