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
  type Step = 'stage' | 'upload' | 'complete';
  let currentStep = $state<Step>('stage');

  let selectedConfigId = $state<string | null>(null);
  let selectedFile = $state<File | null>(null);
  let validating = $state(false);
  let validationResult = $state<{
    valid: boolean;
    errors: string[];
    warnings: string[];
    labelsFound: string[];
    fileCount: number;
    parsedVersion: string | null;
    versionSource: string | null;
    modemLabelsRequired: string[];
    availableModemFirmwares: { id: string; version: string; filename: string; sizeBytes: number }[];
  } | null>(null);
  let uploading = $state(false);
  let uploadError = $state<string | null>(null);
  let uploadSuccess = $state(false);
  let uploadNotes = $state('');
  let uploadVersion = $state('');
  let selectedModemFirmwareId = $state<string | null>(null);

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

  const needsModemFirmware = $derived(
    (validationResult?.modemLabelsRequired?.length ?? 0) > 0
  );
  const hasModemFirmwareOptions = $derived(
    (validationResult?.availableModemFirmwares?.length ?? 0) > 0
  );
  const modemReady = $derived(
    !needsModemFirmware || !!selectedModemFirmwareId
  );

  const stepIndex = $derived(
    currentStep === 'stage' ? 0
    : currentStep === 'upload' ? 1
    : 2
  );

  const steps = ['Stage', 'Upload', 'Complete'] as const;

  // ── Handlers ───────────────────────────────────────────────

  function selectStage(configId: string) {
    selectedConfigId = configId;
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

  async function handleValidate() {
    if (!selectedFile || !selectedConfigId) return;
    validating = true;
    validationResult = null;
    uploadError = null;

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('stageConfigId', selectedConfigId);

      const result = await apiUpload<{ data: typeof validationResult }>(
        `/v2/products/${productId}/asset-sets/validate-zip`,
        formData
      );
      validationResult = result.data;
      if (validationResult?.parsedVersion) {
        uploadVersion = validationResult.parsedVersion;
      }
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Validation failed';
    } finally {
      validating = false;
    }
  }

  async function handleUpload() {
    if (!selectedFile || !selectedConfigId || !uploadVersion.trim()) return;

    uploading = true;
    uploadError = null;

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('stageConfigId', selectedConfigId);
      formData.append('version', uploadVersion.trim());
      formData.append('variant', 'debug');
      if (uploadNotes.trim()) {
        formData.append('notes', uploadNotes.trim());
      }
      if (selectedModemFirmwareId) {
        formData.append('modemFirmwareId', selectedModemFirmwareId);
      }

      await apiUpload(`/v2/products/${productId}/asset-sets/upload-zip`, formData);
      uploadSuccess = true;
      currentStep = 'complete';
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploading = false;
    }
  }

  function goBack() {
    if (currentStep === 'upload') {
      selectedFile = null;
      uploadError = null;
      validationResult = null;
      uploadVersion = '';
      uploadNotes = '';
      selectedModemFirmwareId = null;
      currentStep = 'stage';
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
    if (e.key === 'Escape' && !uploading && !validating) {
      onCancel();
    }
  }
</script>

<!-- Overlay -->
<div
  class="fixed inset-0 z-modal-backdrop bg-overlay animate-overlay-in"
  onclick={() => { if (!uploading && !validating) onCancel(); }}
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
        onclick={() => { if (!uploading && !validating) onCancel(); }}
        disabled={uploading || validating}
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

      <!-- Step 2: Upload & Validate -->
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
            </div>
          </div>

          <!-- Expected contents from build matrix -->
          {#if selectedConfig?.buildMatrix?.length && !validationResult}
            <div>
              <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Expected contents</h4>
              <div class="grid grid-cols-2 gap-1">
                {#each selectedConfig.buildMatrix as entry}
                  <div class="flex items-center gap-2 text-2xs text-text-secondary bg-surface-0 rounded px-2 py-1">
                    <span class="font-mono font-medium">{entry.label}/</span>
                    <span class="text-text-tertiary">
                      {entry.producesHex ? '.hex' : ''}{entry.producesCfw ? ' .cfw' : ''}{!entry.producesHex && !entry.producesCfw ? 'any' : ''}
                    </span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

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
                onclick={() => { selectedFile = null; validationResult = null; uploadVersion = ''; }}
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

          <!-- Validate button (before validation) -->
          {#if selectedFile && !validationResult}
            <button
              onclick={handleValidate}
              disabled={validating}
              class="flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {#if validating}
                <Loader2 size={14} class="animate-spin" />
                Validating...
              {:else}
                <Check size={14} />
                Validate
              {/if}
            </button>
          {/if}

          <!-- Validation results -->
          {#if validationResult}
            <div class="space-y-3">
              <!-- Labels checklist -->
              <div>
                <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Validation results</h4>
                <div class="space-y-1">
                  {#if selectedConfig?.buildMatrix}
                    {#each selectedConfig.buildMatrix as entry}
                      <div class="flex items-center gap-2 text-sm">
                        {#if validationResult.labelsFound.includes(entry.label)}
                          <Check class="text-success shrink-0" size={16} strokeWidth={2.5} />
                        {:else}
                          <X class="text-error shrink-0" size={16} strokeWidth={2.5} />
                        {/if}
                        <span class="font-mono text-2xs text-text-secondary">{entry.label}/</span>
                      </div>
                    {/each}
                  {/if}
                  {#if validationResult.warnings.length > 0}
                    {#each validationResult.warnings as warning}
                      <div class="flex items-center gap-2 text-2xs text-warning">
                        <AlertCircle size={14} class="shrink-0" />
                        <span>{warning}</span>
                      </div>
                    {/each}
                  {/if}
                  {#if validationResult.errors.length > 0}
                    {#each validationResult.errors as err}
                      <div class="flex items-center gap-2 text-2xs text-error">
                        <X size={14} class="shrink-0" />
                        <span>{err}</span>
                      </div>
                    {/each}
                  {/if}
                  <p class="text-2xs text-text-tertiary mt-1">{validationResult.fileCount} file{validationResult.fileCount === 1 ? '' : 's'} found</p>
                </div>
              </div>

              <!-- Version -->
              <div>
                {#if validationResult.parsedVersion}
                  <p class="text-2xs text-success mb-1">
                    Version detected: {validationResult.parsedVersion} (from {validationResult.versionSource})
                  </p>
                {:else}
                  <p class="text-2xs text-warning mb-1">Version could not be auto-detected</p>
                {/if}
                <label for="upload-version" class="block text-2xs font-medium text-text-secondary mb-1">
                  Version
                </label>
                <input
                  id="upload-version"
                  type="text"
                  bind:value={uploadVersion}
                  placeholder="e.g., 0.5.2"
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>

              <!-- Notes -->
              <div>
                <label for="upload-notes" class="block text-2xs font-medium text-text-secondary mb-1">
                  Notes <span class="text-text-tertiary font-normal">(optional)</span>
                </label>
                <textarea
                  id="upload-notes"
                  bind:value={uploadNotes}
                  placeholder="Notes about this firmware..."
                  rows="2"
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none resize-none"
                ></textarea>
              </div>

              <!-- Modem firmware selection -->
              {#if needsModemFirmware}
                <div>
                  <label for="modem-firmware-select" class="block text-2xs font-medium text-text-secondary mb-1">
                    Modem Firmware
                  </label>
                  {#if hasModemFirmwareOptions}
                    <select
                      id="modem-firmware-select"
                      bind:value={selectedModemFirmwareId}
                      class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
                    >
                      <option value={null}>Select modem firmware...</option>
                      {#each validationResult.availableModemFirmwares as fw}
                        <option value={fw.id}>v{fw.version} -- {fw.filename}</option>
                      {/each}
                    </select>
                  {:else}
                    <div class="rounded-lg bg-warning-muted px-3 py-2">
                      <p class="text-2xs text-warning">No modem firmware uploaded for this revision.</p>
                      <p class="text-2xs text-warning/70 mt-0.5">Upload modem firmware in the Assets tab first.</p>
                    </div>
                  {/if}
                </div>
              {/if}

              <!-- Upload button (only when valid + version filled + modem selected if needed) -->
              {#if validationResult.valid && uploadVersion.trim() && modemReady}
                <button
                  onclick={handleUpload}
                  disabled={uploading}
                  class="flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {#if uploading}
                    <Loader2 size={14} class="animate-spin" />
                    Uploading...
                  {:else}
                    <Upload size={14} />
                    Upload to Concord
                  {/if}
                </button>
              {/if}
            </div>
          {/if}

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

      <!-- Step 3: Complete -->
      {:else if currentStep === 'complete'}
        <div class="flex flex-col items-center justify-center py-8">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-success-muted mb-4">
            <Check size={24} class="text-success" strokeWidth={2.5} />
          </div>
          <p class="text-sm font-medium text-text-primary mb-1">Upload complete</p>
          <p class="text-2xs text-text-tertiary mb-1">
            Assets validated and stored for
            {selectedConfig ? stageName(selectedConfig.type as StageType, selectedConfig.stage) : ''}
          </p>
          {#if selectedFile}
            <p class="text-2xs text-text-tertiary">
              {selectedFile.name} ({formatSize(selectedFile.size)})
            </p>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between border-t border-border px-5 py-4">
      <div>
        {#if currentStep === 'upload'}
          <button
            onclick={goBack}
            disabled={uploading || validating}
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
        {#if currentStep === 'complete'}
          <button
            onclick={onComplete}
            class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Done
          </button>
        {:else}
          <button
            onclick={() => { if (!uploading && !validating) onCancel(); }}
            disabled={uploading || validating}
            class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50"
          >
            Cancel
          </button>

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
