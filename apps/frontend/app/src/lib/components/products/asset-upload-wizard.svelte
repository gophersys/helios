<script lang="ts">
  import { X, Loader2, Upload, ChevronLeft, Check, AlertCircle, FileArchive, File as FileIcon } from 'lucide-svelte';
  import { apiFetch, apiUpload } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { ProductStageConfig, StageType } from '$lib/types/stages';
  import { stageName } from '$lib/types/stages';
  import { canonicalFilename } from '$lib/utils/assets';

  interface Revision {
    id: string;
    version: string;
    ckBoardsName: string | null;
  }

  interface Props {
    productId: string;
    productSlug: string;
    revision: Revision;
    stageConfigs: ProductStageConfig[];
    onComplete: () => void;
    onCancel: () => void;
  }

  let { productId, productSlug, revision, stageConfigs, onComplete, onCancel }: Props = $props();

  // ── Wizard state ────────────────────────────────────────────
  type Step = 'stage' | 'upload' | 'complete';
  type UploadMode = 'files' | 'zip';
  let currentStep = $state<Step>('stage');
  let uploadMode = $state<UploadMode>('zip');

  let selectedConfigId = $state<string | null>(null);

  // ── Files mode state ────────────────────────────────────────
  interface AnalyzedFile {
    filename: string;
    size: number;
    file: File;
    detectedType: string;
    detectedProcessor: string | null;
    detectedVariant: string | null;
    suggestedLabel: string | null;
    confidence: string | null;
    matchReason: string | null;
    assignedLabel: string;
  }

  let selectedFiles = $state<File[]>([]);
  let analyzedFiles = $state<AnalyzedFile[]>([]);
  let analyzing = $state(false);

  // ── Zip mode state ──────────────────────────────────────────
  let selectedZipFile = $state<File | null>(null);
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

  // ── Shared state ────────────────────────────────────────────
  let uploading = $state(false);
  let uploadError = $state<string | null>(null);
  let uploadSuccess = $state(false);
  let uploadNotes = $state('');
  let uploadVersion = $state('');
  let selectedModemFirmwareId = $state<string | null>(null);
  let uploadSummary = $state<{ fileCount: number; labels: string[]; version: string } | null>(null);

  // Analyze-files response modem data
  let analyzeModemLabelsRequired = $state<string[]>([]);
  let analyzeAvailableModemFirmwares = $state<{ id: string; version: string; filename: string; sizeBytes: number }[]>([]);

  // ── Derived ────────────────────────────────────────────────
  const enabledConfigs = $derived(stageConfigs.filter(c => c.enabled));
  const validationConfigs = $derived(
    enabledConfigs.filter(c => c.type === 'VALIDATION').sort((a, b) => a.stage - b.stage)
  );
  const manufacturingConfigs = $derived(
    enabledConfigs.filter(c => c.type === 'MANUFACTURING').sort((a, b) => a.stage - b.stage)
  );
  const hasConfigs = $derived(enabledConfigs.length > 0);

  const selectedConfig = $derived(
    enabledConfigs.find(c => c.id === selectedConfigId) ?? null
  );

  // Files mode derived
  const requiredLabels = $derived(
    selectedConfig?.buildMatrix?.filter((e: any) => e.fwType !== 'modem').map((e: any) => e.label) ?? []
  );

  const assignedLabels = $derived(
    new Set(analyzedFiles.map(f => f.assignedLabel).filter(Boolean))
  );

  const unassignedLabels = $derived(
    requiredLabels.filter((l: string) => !assignedLabels.has(l))
  );

  const allLabelsAssigned = $derived(
    requiredLabels.length > 0 && requiredLabels.every((l: string) => assignedLabels.has(l))
  );

  const filesNeedsModem = $derived(analyzeModemLabelsRequired.length > 0);
  const filesHasModemOptions = $derived(analyzeAvailableModemFirmwares.length > 0);
  const filesModemReady = $derived(!filesNeedsModem || !!selectedModemFirmwareId);

  // Zip mode derived
  const zipNeedsModem = $derived((validationResult?.modemLabelsRequired?.length ?? 0) > 0);
  const zipHasModemOptions = $derived((validationResult?.availableModemFirmwares?.length ?? 0) > 0);
  const zipModemReady = $derived(!zipNeedsModem || !!selectedModemFirmwareId);

  const stepIndex = $derived(
    currentStep === 'stage' ? 0
    : currentStep === 'upload' ? 1
    : 2
  );

  const steps = ['Stage', 'Upload', 'Complete'] as const;

  // ── Handlers ───────────────────────────────────────────────

  let modemFirmwares = $state<{ id: string; version: string; filename: string }[]>([]);
  let modemLoaded = $state(false);

  // Preload modem firmware on mount — one fetch, always available
  $effect(() => {
    if (productId && revision.id && !modemLoaded) {
      modemLoaded = true;
      apiFetch<ApiResponse<any[]>>(
        `/v2/products/${productId}/revisions/${revision.id}/modem-firmware`
      ).then(res => {
        modemFirmwares = Array.isArray(res.data) ? res.data : [];
      }).catch(() => {
        modemFirmwares = [];
      });
    }
  });

  // Does the selected stage require modem firmware?
  const stageNeedsModem = $derived(
    selectedConfig?.buildMatrix?.some((e: any) => e.fwType === 'modem') ?? false
  );
  const modemAvailable = $derived(modemFirmwares.length > 0);
  const modemBlocked = $derived(stageNeedsModem && !modemAvailable);

  function selectStage(configId: string) {
    selectedConfigId = configId;
    if (!modemBlocked) {
      currentStep = 'upload';
    }
  }

  // --- Files mode handlers ---

  function handleFilesSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    const files = input.files;
    if (files && files.length > 0) {
      addFiles(Array.from(files));
    }
    // Reset input so re-selecting same files works
    input.value = '';
  }

  function handleFilesDrop(e: DragEvent) {
    e.preventDefault();
    const dt = e.dataTransfer;
    if (!dt?.files) return;

    const valid = Array.from(dt.files).filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase();
      return ext === 'hex' || ext === 'cfw' || ext === 'json';
    });

    if (valid.length > 0) {
      addFiles(valid);
    }
  }

  function addFiles(files: File[]) {
    selectedFiles = [...selectedFiles, ...files];
    uploadError = null;
    // Reset analysis when files change
    analyzedFiles = [];
  }

  function removeFile(index: number) {
    selectedFiles = selectedFiles.filter((_, i) => i !== index);
    analyzedFiles = [];
    uploadError = null;
  }

  async function handleAnalyze() {
    if (selectedFiles.length === 0 || !selectedConfigId) return;
    analyzing = true;
    uploadError = null;
    analyzedFiles = [];

    try {
      const formData = new FormData();
      formData.append('stageConfigId', selectedConfigId);
      for (const f of selectedFiles) {
        formData.append('files', f);
      }

      const result = await apiUpload<{ data: {
        files: {
          filename: string;
          size: number;
          detectedType: string;
          detectedProcessor: string | null;
          detectedVariant: string | null;
          suggestedLabel: string | null;
          confidence: string | null;
          matchReason: string | null;
        }[];
        unmatchedLabels: string[];
        allMatched: boolean;
        modemLabelsRequired: string[];
        availableModemFirmwares: { id: string; version: string; filename: string; sizeBytes: number }[];
      } }>(
        `/v2/products/${productId}/asset-sets/analyze-files`,
        formData
      );

      const data = result.data;
      analyzeModemLabelsRequired = data.modemLabelsRequired;
      analyzeAvailableModemFirmwares = data.availableModemFirmwares;

      analyzedFiles = data.files.map((f, i) => ({
        ...f,
        file: selectedFiles[i],
        assignedLabel: f.confidence === 'high' || f.confidence === 'medium'
          ? f.suggestedLabel ?? ''
          : '',
      }));
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Analysis failed';
    } finally {
      analyzing = false;
    }
  }

  function setFileLabel(index: number, label: string) {
    analyzedFiles = analyzedFiles.map((f, i) =>
      i === index ? { ...f, assignedLabel: label } : f
    );
  }

  async function handleFilesUpload() {
    if (!selectedConfigId || !uploadVersion.trim() || !allLabelsAssigned || !filesModemReady) return;

    uploading = true;
    uploadError = null;

    try {
      const formData = new FormData();
      formData.append('stageConfigId', selectedConfigId);
      formData.append('version', uploadVersion.trim());
      if (uploadNotes.trim()) {
        formData.append('notes', uploadNotes.trim());
      }
      if (selectedModemFirmwareId) {
        formData.append('modemFirmwareId', selectedModemFirmwareId);
      }

      for (const af of analyzedFiles) {
        formData.append('files', af.file);
        formData.append('labels', af.assignedLabel);
      }

      await apiUpload(`/v2/products/${productId}/asset-sets/upload-files`, formData);
      uploadSummary = {
        fileCount: analyzedFiles.length,
        labels: analyzedFiles.map(f => f.assignedLabel),
        version: uploadVersion.trim(),
      };
      uploadSuccess = true;
      currentStep = 'complete';
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploading = false;
    }
  }

  // --- Zip mode handlers ---

  function handleZipSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      selectedZipFile = file;
      uploadError = null;
    }
  }

  function handleZipDrop(e: DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file && file.name.endsWith('.zip')) {
      selectedZipFile = file;
      uploadError = null;
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
  }

  async function handleValidateZip() {
    if (!selectedZipFile || !selectedConfigId) return;
    validating = true;
    validationResult = null;
    uploadError = null;

    try {
      const formData = new FormData();
      formData.append('file', selectedZipFile);
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

  async function handleZipUpload() {
    if (!selectedZipFile || !selectedConfigId || !uploadVersion.trim()) return;

    uploading = true;
    uploadError = null;

    try {
      const formData = new FormData();
      formData.append('file', selectedZipFile);
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
      uploadSummary = {
        fileCount: validationResult?.fileCount ?? 0,
        labels: validationResult?.labelsFound ?? [],
        version: uploadVersion.trim(),
      };
      uploadSuccess = true;
      currentStep = 'complete';
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploading = false;
    }
  }

  // --- Navigation ---

  function goBack() {
    if (currentStep === 'upload') {
      resetUploadState();
      currentStep = 'stage';
    }
  }

  function resetUploadState() {
    selectedFiles = [];
    analyzedFiles = [];
    selectedZipFile = null;
    uploadError = null;
    validationResult = null;
    uploadVersion = '';
    uploadNotes = '';
    selectedModemFirmwareId = null;
    analyzeModemLabelsRequired = [];
    analyzeAvailableModemFirmwares = [];
  }

  function switchMode(mode: UploadMode) {
    uploadMode = mode;
    resetUploadState();
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function labelCount(config: ProductStageConfig): number {
    return config.buildMatrix?.length ?? 0;
  }

  function fileTypeLabel(type: string): string {
    switch (type) {
      case 'plaintextHex': return 'HEX';
      case 'encryptedCfw': return 'CFW';
      case 'manifest': return 'JSON';
      default: return type;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !uploading && !validating && !analyzing) {
      onCancel();
    }
  }

  const busy = $derived(uploading || validating || analyzing);
</script>

<!-- Overlay -->
<div
  class="fixed inset-0 z-modal-backdrop bg-overlay animate-overlay-in"
  onclick={() => { if (!busy) onCancel(); }}
  onkeydown={handleKeydown}
  role="presentation"
  tabindex="-1"
></div>

<!-- Dialog -->
<div class="fixed inset-0 z-modal flex items-center justify-center p-4">
  <div
    class="w-full max-w-2xl animate-modal-in rounded-lg border border-border bg-surface-1 shadow-modal max-h-[90vh] flex flex-col"
    role="dialog"
    aria-modal="true"
    aria-labelledby="upload-wizard-title"
  >
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-border px-6 py-4 shrink-0">
      <div class="flex items-center gap-3">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-muted">
          <Upload size={20} class="text-accent" strokeWidth={1.75} />
        </div>
        <div>
          <h2 id="upload-wizard-title" class="text-sm font-semibold text-text-primary">
            Upload Assets
          </h2>
          <p class="text-2xs text-text-tertiary">
            {revision.version}{revision.ckBoardsName ? ` (${revision.ckBoardsName})` : ''}
          </p>
        </div>
      </div>
      <button
        onclick={() => { if (!busy) onCancel(); }}
        disabled={busy}
        class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary disabled:opacity-50"
        title="Cancel"
        aria-label="Cancel upload"
      >
        <X size={20} strokeWidth={1.75} />
      </button>
    </div>

    <!-- Step indicator -->
    <div class="flex items-center gap-1 px-6 py-3 border-b border-border-subtle shrink-0">
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
    <div class="p-6 min-h-[200px] overflow-y-auto">

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

          {#if modemBlocked}
            <div class="mt-3 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3 text-sm text-warning">
              This stage requires modem firmware. Upload modem firmware first.
            </div>
          {/if}
        </div>

      <!-- Step 2: Upload & Match -->
      {:else if currentStep === 'upload'}
        <div class="space-y-4">
          <!-- Stage summary -->
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

          <!-- Mode toggle -->
          <!-- Zip upload only -->

          <!-- ============ FILES MODE (hidden — zip only) ============ -->
          {#if false}

            <!-- Expected labels (before analysis) -->
            {#if selectedConfig?.buildMatrix?.length && analyzedFiles.length === 0}
              <div>
                <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Expected contents</h4>
                <div class="grid grid-cols-2 gap-1">
                  {#each selectedConfig.buildMatrix.filter((e: any) => e.fwType !== 'modem') as entry}
                    <div class="flex items-center gap-2 text-2xs text-text-secondary bg-surface-0 rounded px-2 py-1">
                      <span class="font-mono font-medium">{entry.label}</span>
                      <span class="text-text-tertiary">
                        {entry.producesHex ? '.hex' : ''}{entry.producesCfw ? ' .cfw' : ''}{!entry.producesHex && !entry.producesCfw ? 'any' : ''}
                      </span>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Drop zone for loose files -->
            <div
              ondrop={handleFilesDrop}
              ondragover={handleDragOver}
              class="flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-6 transition-colors
                {selectedFiles.length > 0 ? 'border-accent/40 bg-accent-muted/20' : 'border-border hover:border-accent/50'}"
            >
              {#if selectedFiles.length === 0}
                <FileIcon size={28} class="mb-2 text-text-tertiary" />
                <p class="text-sm text-text-secondary mb-1">Drop .hex / .cfw files here</p>
                <p class="text-2xs text-text-tertiary mb-3">or</p>
                <label class="cursor-pointer rounded-lg border border-accent/30 bg-accent-muted px-3 py-1.5 text-2xs font-medium text-accent hover:bg-accent/15 transition-colors">
                  Browse files
                  <input type="file" multiple accept=".hex,.cfw,.json" class="hidden" onchange={handleFilesSelect} />
                </label>
              {:else}
                <!-- File list -->
                <div class="w-full space-y-1">
                  {#each selectedFiles as file, i}
                    <div class="flex items-center gap-2 rounded bg-surface-0 px-3 py-1.5 text-2xs">
                      <FileIcon size={12} class="text-text-tertiary shrink-0" />
                      <span class="font-mono text-text-primary truncate flex-1">{file.name}</span>
                      <span class="text-text-tertiary shrink-0">{formatSize(file.size)}</span>
                      <button
                        onclick={() => removeFile(i)}
                        class="text-text-tertiary hover:text-error shrink-0"
                        title="Remove"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  {/each}
                </div>
                <label class="mt-2 cursor-pointer text-2xs text-accent hover:underline">
                  Add more files
                  <input type="file" multiple accept=".hex,.cfw,.json" class="hidden" onchange={handleFilesSelect} />
                </label>
              {/if}
            </div>

            <!-- Analyze button -->
            {#if selectedFiles.length > 0 && analyzedFiles.length === 0}
              <button
                onclick={handleAnalyze}
                disabled={analyzing}
                class="btn btn-primary w-full"
              >
                {#if analyzing}
                  <Loader2 size={14} class="animate-spin" />
                  Analyzing...
                {:else}
                  <Check size={14} />
                  Analyze files
                {/if}
              </button>
            {/if}

            <!-- Mapping table (after analysis) -->
            {#if analyzedFiles.length > 0}
              <div>
                <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">File mapping</h4>
                <div class="rounded-lg border border-border overflow-hidden">
                  <table class="w-full text-2xs">
                    <thead>
                      <tr class="bg-surface-2 text-text-tertiary">
                        <th class="text-left px-3 py-2 font-medium">File</th>
                        <th class="text-left px-3 py-2 font-medium w-16">Size</th>
                        <th class="text-left px-3 py-2 font-medium w-12">Type</th>
                        <th class="text-left px-3 py-2 font-medium w-44">Label</th>
                        <th class="text-center px-3 py-2 font-medium w-8"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each analyzedFiles as file, i}
                        <tr class="border-t border-border-subtle">
                          <td class="px-3 py-2">
                            <span class="font-mono text-text-primary">{file.filename}</span>
                          </td>
                          <td class="px-3 py-2 text-text-tertiary">{formatSize(file.size)}</td>
                          <td class="px-3 py-2 text-text-tertiary">{fileTypeLabel(file.detectedType)}</td>
                          <td class="px-3 py-2">
                            {#if file.confidence === 'high'}
                              <span class="inline-flex items-center gap-1 text-success font-medium">
                                {file.assignedLabel}
                              </span>
                            {:else}
                              <select
                                value={file.assignedLabel}
                                onchange={(e) => setFileLabel(i, (e.target as HTMLSelectElement).value)}
                                class="w-full rounded border border-border bg-surface-0 px-2 py-1 text-2xs text-text-primary focus:border-accent focus:outline-hidden"
                              >
                                <option value="">Select label...</option>
                                {#if file.suggestedLabel && file.confidence === 'medium'}
                                  <option value={file.suggestedLabel}>{file.suggestedLabel} (suggested)</option>
                                {/if}
                                {#each requiredLabels.filter((l: string) => !assignedLabels.has(l) || l === file.assignedLabel) as label}
                                  {#if label !== file.suggestedLabel || file.confidence !== 'medium'}
                                    <option value={label}>{label}</option>
                                  {/if}
                                {/each}
                              </select>
                            {/if}
                          </td>
                          <td class="px-3 py-2 text-center">
                            {#if file.assignedLabel && file.confidence === 'high'}
                              <span class="text-success" title="Auto-matched">&#10003;</span>
                            {:else if file.assignedLabel}
                              <span class="text-warning" title={file.matchReason ?? 'Manually assigned'}>&#9888;</span>
                            {:else}
                              <span class="text-error" title="Needs assignment">&#10005;</span>
                            {/if}
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>

                <!-- Missing labels warning -->
                {#if unassignedLabels.length > 0}
                  <div class="mt-2 flex items-start gap-2 text-2xs text-warning">
                    <AlertCircle size={14} class="shrink-0 mt-0.5" />
                    <span>Missing: {unassignedLabels.join(', ')}</span>
                  </div>
                {/if}
              </div>

              <!-- Version -->
              <div>
                <label for="files-version" class="block text-2xs font-medium text-text-secondary mb-1">
                  Version
                </label>
                <input
                  id="files-version"
                  type="text"
                  bind:value={uploadVersion}
                  placeholder="e.g., 0.5.2"
                  class="input w-full"
                />
              </div>

              <!-- Modem firmware selection -->
              {#if filesNeedsModem}
                <div>
                  <label for="files-modem-select" class="block text-2xs font-medium text-text-secondary mb-1">
                    Modem Firmware
                  </label>
                  {#if filesHasModemOptions}
                    <select
                      id="files-modem-select"
                      bind:value={selectedModemFirmwareId}
                      class="input w-full"
                    >
                      <option value={null}>Select modem firmware...</option>
                      {#each analyzeAvailableModemFirmwares as fw}
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

              <!-- Notes -->
              <div>
                <label for="files-notes" class="block text-2xs font-medium text-text-secondary mb-1">
                  Notes <span class="text-text-tertiary font-normal">(optional)</span>
                </label>
                <textarea
                  id="files-notes"
                  bind:value={uploadNotes}
                  placeholder="Notes about this firmware..."
                  rows="2"
                  class="input w-full resize-none"
                ></textarea>
              </div>

              <!-- Upload button -->
              <button
                onclick={handleFilesUpload}
                disabled={!allLabelsAssigned || !uploadVersion.trim() || !filesModemReady || uploading}
                class="btn btn-primary w-full"
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

          <!-- ============ ZIP MODE ============ -->
          {:else}

            <!-- Expected zip structure from build matrix -->
            {#if selectedConfig?.buildMatrix?.length && !validationResult}
              <div class="rounded-lg border border-border bg-surface-0 p-3">
                <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Expected zip structure</h4>
                <div class="font-mono text-2xs text-text-secondary space-y-0.5">
                  {#each selectedConfig.buildMatrix.filter((e: any) => e.fwType !== 'modem') as entry}
                    <div>
                      <span class="text-accent">{entry.label}/</span>
                    </div>
                    {#if entry.producesHex}
                      <div class="ml-4 text-text-tertiary">
                        {canonicalFilename(productSlug, entry.fwType, entry.processor, revision.version, entry.variant, 'hex')}
                      </div>
                    {/if}
                    {#if entry.producesCfw}
                      <div class="ml-4 text-text-tertiary">
                        {canonicalFilename(productSlug, entry.fwType, entry.processor, revision.version, entry.variant, 'cfw')}
                      </div>
                    {/if}
                  {/each}
                </div>
                {#if selectedConfig.buildMatrix.some((e: any) => e.fwType === 'modem')}
                  <p class="text-2xs text-text-tertiary mt-2 italic">Modem firmware is selected separately below.</p>
                {/if}
              </div>
            {/if}

            <!-- Drop zone (zip) -->
            <div
              ondrop={handleZipDrop}
              ondragover={handleDragOver}
              class="flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition-colors
                {selectedZipFile ? 'border-accent bg-accent-muted/30' : 'border-border hover:border-accent/50'}"
            >
              {#if selectedZipFile}
                <FileArchive size={28} class="mb-2 text-accent" />
                <p class="text-sm font-medium text-text-primary">{selectedZipFile.name}</p>
                <p class="text-2xs text-text-tertiary mt-0.5">{formatSize(selectedZipFile.size)}</p>
                <button
                  onclick={() => { selectedZipFile = null; validationResult = null; uploadVersion = ''; }}
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
                  <input type="file" accept=".zip" class="hidden" onchange={handleZipSelect} />
                </label>
              {/if}
            </div>

            <!-- Validate button (before validation) -->
            {#if selectedZipFile && !validationResult}
              <button
                onclick={handleValidateZip}
                disabled={validating}
                class="btn btn-primary w-full"
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
                      {#each selectedConfig.buildMatrix.filter((e: any) => e.fwType !== 'modem') as entry}
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
                  <label for="zip-version" class="block text-2xs font-medium text-text-secondary mb-1">
                    Version
                  </label>
                  <input
                    id="zip-version"
                    type="text"
                    bind:value={uploadVersion}
                    placeholder="e.g., 0.5.2"
                    class="input input-sm w-full"
                  />
                </div>

                <!-- Notes -->
                <div>
                  <label for="zip-notes" class="block text-2xs font-medium text-text-secondary mb-1">
                    Notes <span class="text-text-tertiary font-normal">(optional)</span>
                  </label>
                  <textarea
                    id="zip-notes"
                    bind:value={uploadNotes}
                    placeholder="Notes about this firmware..."
                    rows="2"
                    class="input input-sm w-full resize-none"
                  ></textarea>
                </div>

                <!-- Modem firmware selection -->
                {#if zipNeedsModem}
                  <div>
                    <label for="zip-modem-select" class="block text-2xs font-medium text-text-secondary mb-1">
                      Modem Firmware
                    </label>
                    {#if zipHasModemOptions}
                      <select
                        id="zip-modem-select"
                        bind:value={selectedModemFirmwareId}
                        class="input input-sm w-full"
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
                {#if validationResult.valid && uploadVersion.trim() && zipModemReady}
                  <button
                    onclick={handleZipUpload}
                    disabled={uploading}
                    class="btn btn-primary w-full"
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
          {/if}

          <!-- Shared error display -->
          {#if uploadError}
            <div class="flex items-start gap-2 rounded-lg bg-error-muted px-4 py-3">
              <AlertCircle size={14} class="text-error mt-0.5 shrink-0" />
              <div>
                <p class="text-sm text-error">{uploadError}</p>
                {#if uploadMode === 'zip'}
                  <p class="text-2xs text-error/70 mt-0.5">Check that the zip contains the expected label directories and firmware files.</p>
                {:else}
                  <p class="text-2xs text-error/70 mt-0.5">Check that the files match the expected build matrix labels.</p>
                {/if}
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
          {#if uploadSummary}
            <p class="text-2xs text-text-tertiary">
              {uploadSummary.fileCount} file{uploadSummary.fileCount === 1 ? '' : 's'}
              &middot; v{uploadSummary.version}
            </p>
            <div class="mt-2 flex flex-wrap gap-1 justify-center">
              {#each uploadSummary.labels as label}
                <span class="inline-block rounded bg-surface-2 px-2 py-0.5 text-2xs font-mono text-text-secondary">{label}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between border-t border-border px-6 py-4 shrink-0">
      <div>
        {#if currentStep === 'upload'}
          <button
            onclick={goBack}
            disabled={busy}
            class="btn btn-sm btn-ghost"
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
            class="btn btn-sm btn-primary"
          >
            Done
          </button>
        {:else}
          <button
            onclick={() => { if (!busy) onCancel(); }}
            disabled={busy}
            class="btn btn-sm btn-secondary"
          >
            Cancel
          </button>

          {#if !hasConfigs}
            <button
              onclick={onCancel}
              class="btn btn-sm btn-primary"
            >
              Close
            </button>
          {/if}
        {/if}
      </div>
    </div>
  </div>
</div>
