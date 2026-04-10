<script lang="ts">
  import { X, Loader2, Upload, ChevronLeft, Check, AlertCircle, FileArchive } from 'lucide-svelte';
  import { apiUpload } from '$lib/api';
  import type { ProductStageConfig, StageType } from '$lib/types/stages';
  import { stageName } from '$lib/types/stages';

  interface Revision {
    id: string;
    version: string;
    ckBoardsName: string | null;
  }

  interface Props {
    productId: string;
    revision: Revision;
    stageConfigs: ProductStageConfig[];
    onComplete: () => void;
    onCancel: () => void;
  }

  let { productId, revision, stageConfigs, onComplete, onCancel }: Props = $props();

  // ── Wizard state ────────────────────────────────────────────
  type Step = 'stage' | 'variant' | 'upload' | 'uploading';
  let currentStep = $state<Step>('stage');

  let selectedConfigId = $state<string | null>(null);
  let selectedVariant = $state<'debug' | 'release' | 'mfg'>('debug');
  let selectedFile = $state<File | null>(null);
  let uploading = $state(false);
  let uploadError = $state<string | null>(null);
  let uploadSuccess = $state(false);

  // ── Derived ────────────────────────────────────────────────
  const validationConfigs = $derived(
    stageConfigs.filter(c => c.type === 'VALIDATION').sort((a, b) => a.stage - b.stage)
  );
  const manufacturingConfigs = $derived(
    stageConfigs.filter(c => c.type === 'MANUFACTURING').sort((a, b) => a.stage - b.stage)
  );
  const hasConfigs = $derived(stageConfigs.length > 0);

  const selectedConfig = $derived(
    stageConfigs.find(c => c.id === selectedConfigId) ?? null
  );

  const stepIndex = $derived(
    currentStep === 'stage' ? 0
    : currentStep === 'variant' ? 1
    : currentStep === 'upload' ? 2
    : 3
  );

  const steps = ['Stage', 'Variant', 'Upload', 'Complete'] as const;

  // ── Handlers ───────────────────────────────────────────────

  function selectStage(configId: string) {
    selectedConfigId = configId;
    const config = stageConfigs.find(c => c.id === configId);
    if (config?.type === 'MANUFACTURING') {
      selectedVariant = 'mfg';
    } else {
      selectedVariant = 'debug';
    }
    currentStep = 'variant';
  }

  function confirmVariant() {
    currentStep = 'upload';
  }

  function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      selectedFile = file;
      uploadError = null;
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file && file.name.endsWith('.zip')) {
      selectedFile = file;
      uploadError = null;
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function handleUpload() {
    if (!selectedFile || !selectedConfigId) return;

    uploading = true;
    uploadError = null;
    currentStep = 'uploading';

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('stageConfigId', selectedConfigId);
      formData.append('version', 'auto');
      formData.append('variant', selectedVariant);

      await apiUpload(`/v2/products/${productId}/asset-sets/upload-zip`, formData);
      uploadSuccess = true;
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
      currentStep = 'upload';
    } finally {
      uploading = false;
    }
  }

  function goBack() {
    if (currentStep === 'variant') {
      currentStep = 'stage';
    } else if (currentStep === 'upload') {
      selectedFile = null;
      uploadError = null;
      currentStep = 'variant';
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function labelCount(config: ProductStageConfig): number {
    return config.buildMatrix?.length ?? 0;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !uploading) {
      onCancel();
    }
  }
</script>

<!-- Overlay -->
<div
  class="fixed inset-0 z-modal-backdrop bg-overlay animate-overlay-in"
  onclick={() => { if (!uploading) onCancel(); }}
  onkeydown={handleKeydown}
  role="presentation"
  tabindex="-1"
></div>

<!-- Dialog -->
<div class="fixed inset-0 z-modal flex items-center justify-center p-4">
  <div
    class="w-full max-w-lg animate-modal-in rounded-xl border border-border bg-surface-1 shadow-xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby="upload-wizard-title"
  >
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-border px-5 py-4">
      <div class="flex items-center gap-3">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-muted">
          <Upload size={20} class="text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <h2 id="upload-wizard-title" class="text-sm font-semibold text-text-primary">
            Upload Firmware Assets
          </h2>
          <p class="text-2xs text-text-tertiary">
            {revision.version}{revision.ckBoardsName ? ` (${revision.ckBoardsName})` : ''}
          </p>
        </div>
      </div>
      <button
        onclick={() => { if (!uploading) onCancel(); }}
        disabled={uploading}
        class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary disabled:opacity-50"
        title="Cancel"
        aria-label="Cancel upload"
      >
        <X size={20} strokeWidth={1.75} />
      </button>
    </div>

    <!-- Step indicator -->
    <div class="flex items-center gap-1 px-5 py-3 border-b border-border-subtle">
      {#each steps as label, i}
        {@const active = i === stepIndex}
        {@const done = i < stepIndex}
        <div class="flex items-center gap-1">
          <div class="flex h-5 w-5 items-center justify-center rounded-full text-2xs font-bold
            {done ? 'bg-accent text-white' : active ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
            {#if done}
              <Check size={10} strokeWidth={3} />
            {:else}
              {i + 1}
            {/if}
          </div>
          <span class="text-2xs {active ? 'text-text-primary font-medium' : 'text-text-tertiary'}">
            {label}
          </span>
        </div>
        {#if i < steps.length - 1}
          <div class="flex-1 h-px bg-border-subtle mx-1"></div>
        {/if}
      {/each}
    </div>

    <!-- Body -->
    <div class="p-5 min-h-[200px]">

      <!-- No stages configured -->
      {#if !hasConfigs}
        <div class="text-center py-8">
          <AlertCircle size={32} class="mx-auto mb-3 text-text-tertiary" />
          <p class="text-sm text-text-secondary mb-1">No stages configured for this revision</p>
          <p class="text-2xs text-text-tertiary">
            Configure stages in the Validation or Manufacturing tab first.
          </p>
        </div>

      <!-- Step 1: Select Stage -->
      {:else if currentStep === 'stage'}
        <div class="space-y-4">
          {#if validationConfigs.length > 0}
            <div>
              <h3 class="text-2xs font-medium text-text-tertiary uppercase tracking-wider mb-2">Validation Stages</h3>
              <div class="space-y-1.5">
                {#each validationConfigs as config}
                  <button
                    onclick={() => selectStage(config.id)}
                    class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                      {selectedConfigId === config.id
                        ? 'border-accent bg-accent-muted'
                        : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
                  >
                    <div class="flex h-7 w-7 items-center justify-center rounded text-2xs font-bold shrink-0
                      {config.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
                      {config.stage}
                    </div>
                    <div class="flex-1 min-w-0">
                      <span class="text-sm font-medium text-text-primary">
                        {stageName(config.type as StageType, config.stage)}
                      </span>
                      {#if config.name && config.name !== stageName(config.type as StageType, config.stage)}
                        <span class="text-2xs text-text-tertiary ml-1">({config.name})</span>
                      {/if}
                    </div>
                    <span class="text-2xs text-text-tertiary shrink-0">
                      {labelCount(config)} label{labelCount(config) === 1 ? '' : 's'}
                    </span>
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          {#if manufacturingConfigs.length > 0}
            <div>
              <h3 class="text-2xs font-medium text-text-tertiary uppercase tracking-wider mb-2">Manufacturing Stages</h3>
              <div class="space-y-1.5">
                {#each manufacturingConfigs as config}
                  <button
                    onclick={() => selectStage(config.id)}
                    class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                      {selectedConfigId === config.id
                        ? 'border-accent bg-accent-muted'
                        : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
                  >
                    <div class="flex h-7 w-7 items-center justify-center rounded text-2xs font-bold shrink-0
                      {config.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
                      M
                    </div>
                    <div class="flex-1 min-w-0">
                      <span class="text-sm font-medium text-text-primary">
                        {stageName(config.type as StageType, config.stage)}
                      </span>
                    </div>
                    <span class="text-2xs text-text-tertiary shrink-0">
                      {labelCount(config)} label{labelCount(config) === 1 ? '' : 's'}
                    </span>
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>

      <!-- Step 2: Select Variant -->
      {:else if currentStep === 'variant'}
        <div class="space-y-3">
          <p class="text-2xs text-text-tertiary mb-3">
            Select the firmware variant for
            <span class="font-medium text-text-secondary">
              {selectedConfig ? stageName(selectedConfig.type as StageType, selectedConfig.stage) : ''}
            </span>
          </p>
          {#each [
            { value: 'debug', label: 'Debug', desc: 'Debug symbols enabled, verbose logging' },
            { value: 'release', label: 'Release', desc: 'Optimized build, production-ready' },
            { value: 'mfg', label: 'Manufacturing', desc: 'Manufacturing test firmware' },
          ] as opt}
            <button
              onclick={() => { selectedVariant = opt.value as 'debug' | 'release' | 'mfg'; }}
              class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                {selectedVariant === opt.value
                  ? 'border-accent bg-accent-muted'
                  : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
            >
              <div class="flex h-5 w-5 items-center justify-center rounded-full border-2 shrink-0
                {selectedVariant === opt.value ? 'border-accent' : 'border-border'}">
                {#if selectedVariant === opt.value}
                  <div class="h-2.5 w-2.5 rounded-full bg-accent"></div>
                {/if}
              </div>
              <div>
                <span class="text-sm font-medium text-text-primary">{opt.label}</span>
                <p class="text-2xs text-text-tertiary">{opt.desc}</p>
              </div>
            </button>
          {/each}
        </div>

      <!-- Step 3: Upload -->
      {:else if currentStep === 'upload'}
        <div class="space-y-4">
          <!-- Summary -->
          <div class="rounded-lg border border-border-subtle bg-surface-0/50 px-4 py-3">
            <div class="flex items-center gap-4 text-2xs">
              <div>
                <span class="text-text-tertiary">Stage:</span>
                <span class="font-medium text-text-primary ml-1">
                  {selectedConfig ? stageName(selectedConfig.type as StageType, selectedConfig.stage) : ''}
                </span>
              </div>
              <div>
                <span class="text-text-tertiary">Variant:</span>
                <span class="font-medium text-text-primary ml-1 capitalize">{selectedVariant}</span>
              </div>
              <div>
                <span class="text-text-tertiary">Version:</span>
                <span class="font-medium text-text-primary ml-1">Auto</span>
              </div>
            </div>
          </div>

          <!-- Drop zone -->
          <div
            ondrop={handleDrop}
            ondragover={handleDragOver}
            class="flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition-colors
              {selectedFile ? 'border-accent bg-accent-muted/30' : 'border-border hover:border-accent/50'}"
          >
            {#if selectedFile}
              <FileArchive size={28} class="mb-2 text-accent" />
              <p class="text-sm font-medium text-text-primary">{selectedFile.name}</p>
              <p class="text-2xs text-text-tertiary mt-0.5">{formatSize(selectedFile.size)}</p>
              <button
                onclick={() => { selectedFile = null; }}
                class="mt-2 text-2xs text-accent hover:underline"
              >
                Remove
              </button>
            {:else}
              <FileArchive size={28} class="mb-2 text-text-tertiary" />
              <p class="text-sm text-text-secondary mb-1">Drop a .zip file here</p>
              <p class="text-2xs text-text-tertiary mb-3">or</p>
              <label class="cursor-pointer rounded-lg border border-accent/30 bg-accent-muted px-3 py-1.5 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors">
                Browse files
                <input type="file" accept=".zip" class="hidden" onchange={handleFileSelect} />
              </label>
            {/if}
          </div>

          {#if uploadError}
            <div class="flex items-start gap-2 rounded-lg bg-error-muted px-4 py-3">
              <AlertCircle size={14} class="text-error mt-0.5 shrink-0" />
              <div>
                <p class="text-sm text-error">{uploadError}</p>
                <p class="text-2xs text-error/70 mt-0.5">Check that the zip contains the expected label directories and firmware files.</p>
              </div>
            </div>
          {/if}
        </div>

      <!-- Step 4: Uploading / Success -->
      {:else if currentStep === 'uploading'}
        <div class="flex flex-col items-center justify-center py-8">
          {#if uploadSuccess}
            <div class="flex h-12 w-12 items-center justify-center rounded-full bg-success-muted mb-4">
              <Check size={24} class="text-success" strokeWidth={2.5} />
            </div>
            <p class="text-sm font-medium text-text-primary mb-1">Upload complete</p>
            <p class="text-2xs text-text-tertiary">
              Assets validated and stored for
              {selectedConfig ? stageName(selectedConfig.type as StageType, selectedConfig.stage) : ''}
              ({selectedVariant})
            </p>
          {:else}
            <Loader2 size={32} class="animate-spin text-accent mb-4" />
            <p class="text-sm font-medium text-text-primary mb-1">Uploading and validating...</p>
            <p class="text-2xs text-text-tertiary">
              The server is checking firmware files against the build matrix.
            </p>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between border-t border-border px-5 py-4">
      <div>
        {#if currentStep === 'variant' || currentStep === 'upload'}
          <button
            onclick={goBack}
            disabled={uploading}
            class="flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50"
          >
            <ChevronLeft size={14} />
            Back
          </button>
        {:else}
          <div></div>
        {/if}
      </div>

      <div class="flex items-center gap-2">
        {#if uploadSuccess}
          <button
            onclick={onComplete}
            class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Done
          </button>
        {:else if currentStep === 'uploading'}
          <!-- No actions while uploading -->
        {:else}
          <button
            onclick={() => { if (!uploading) onCancel(); }}
            disabled={uploading}
            class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50"
          >
            Cancel
          </button>

          {#if currentStep === 'variant'}
            <button
              onclick={confirmVariant}
              class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Next
            </button>
          {:else if currentStep === 'upload'}
            <button
              onclick={handleUpload}
              disabled={!selectedFile || uploading}
              class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Upload size={14} />
              Upload
            </button>
          {/if}

          {#if !hasConfigs}
            <button
              onclick={onCancel}
              class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Close
            </button>
          {/if}
        {/if}
      </div>
    </div>
  </div>
</div>
