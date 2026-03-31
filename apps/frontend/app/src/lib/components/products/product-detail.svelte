<script lang="ts">
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import BoardList from './board-list.svelte';
  import FirmwareBuildManager from './firmware-app-list.svelte';
  import ProductStages from './product-stages.svelte';
  import BuildConfigCard from './build-config-card.svelte';
  import { Cpu, Layers, Upload, Pencil, Check, X, CircuitBoard } from 'lucide-svelte';
  import type { Product, BoardRevision, ProductTarget } from '$lib/types/models';
  import type { BuildJobArtifact } from '$lib/types/ci';
  import { api } from '$lib/api';
  import { createManualBuild, uploadBuildArtifact } from '$lib/services/ci';

  type Tab = 'stages' | 'boards' | 'firmware' | 'build-config' | 'usage';

  interface Props {
    product: Product;
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
  }

  let { product, canManage, onBack, onRefresh }: Props = $props();

  let activeTab = $state<Tab>('stages');
  let error = $state<string | null>(null);

  // ── Product info editing ────────────────────────────────
  let editingProduct = $state(false);
  let editName = $state('');
  let editSlug = $state('');
  let editDescription = $state('');
  let editFwRepoSlug = $state('');
  let editMfgFwRepoSlug = $state('');
  let savingProduct = $state(false);

  function startEditProduct(): void {
    editName = product.name;
    editSlug = product.slug || '';
    editDescription = product.description || '';
    editFwRepoSlug = product.fwRepoSlug || '';
    editMfgFwRepoSlug = product.mfgFwRepoSlug || '';
    editingProduct = true;
  }

  function cancelEditProduct(): void {
    editingProduct = false;
    error = null;
  }

  async function saveProduct(): Promise<void> {
    savingProduct = true;
    error = null;
    try {
      await api.put(`/v2/products/${product.id}`, {
        name: editName.trim(),
        slug: editSlug.trim() || null,
        description: editDescription.trim() || null,
        fwRepoSlug: editFwRepoSlug.trim() || null,
        mfgFwRepoSlug: editMfgFwRepoSlug.trim() || null,
      });
      editingProduct = false;
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update product';
    } finally {
      savingProduct = false;
    }
  }

  // ── Revision config editing ─────────────────────────────
  let editingRevisionId = $state<string | null>(null);
  let editRevDeviceType = $state<number>(0);
  let editRevDeviceVariant = $state<number>(0);
  let editRevTargets = $state<{ id: string; role: string; soc: string; appId: number }[]>([]);
  let savingRevision = $state(false);

  function startEditRevision(rev: BoardRevision): void {
    editingRevisionId = rev.id;
    editRevDeviceType = rev.deviceType ?? 0;
    editRevDeviceVariant = rev.deviceVariant ?? 0;
    editRevTargets = (rev.targets || []).map((t) => ({ ...t }));
    error = null;
  }

  function cancelEditRevision(): void {
    editingRevisionId = null;
    error = null;
  }

  function findBoardForRevision(revisionId: string): { boardId: string } | null {
    for (const board of (product.boards || [])) {
      for (const rev of (board.revisions || [])) {
        if (rev.id === revisionId) return { boardId: board.id };
      }
    }
    return null;
  }

  async function saveRevision(): Promise<void> {
    if (!editingRevisionId) return;
    savingRevision = true;
    error = null;

    const ctx = findBoardForRevision(editingRevisionId);
    if (!ctx) {
      error = 'Could not find board for revision';
      savingRevision = false;
      return;
    }

    try {
      // Update revision fields (deviceType, deviceVariant)
      await api.put(
        `/v2/products/${product.id}/boards/${ctx.boardId}/revisions/${editingRevisionId}`,
        { deviceType: editRevDeviceType, deviceVariant: editRevDeviceVariant }
      );

      // Update each target individually
      for (const target of editRevTargets) {
        await api.put(
          `/v2/products/${product.id}/boards/${ctx.boardId}/revisions/${editingRevisionId}/targets/${target.id}`,
          { role: target.role, soc: target.soc, appId: target.appId }
        );
      }

      editingRevisionId = null;
      onRefresh();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update revision config';
    } finally {
      savingRevision = false;
    }
  }

  // ── Upload modal state ──────────────────────────────────
  let showUploadModal = $state(false);
  let uploadStep = $state<'details' | 'artifacts'>('details');
  let uploadBoard = $state('');
  let uploadTarget = $state('');
  let uploadVariant = $state('');
  let uploadVersion = $state('');
  let uploadBranch = $state('');
  let uploadNotes = $state('');
  let uploadSubmitting = $state(false);
  let uploadBuildId = $state<string | null>(null);
  let uploadingFile = $state(false);
  let uploadedArtifacts = $state<BuildJobArtifact[]>([]);
  let artifactRole = $state('');
  let artifactProcessor = $state('');

  function openUploadModal(): void {
    uploadStep = 'details';
    uploadBoard = '';
    uploadTarget = '';
    uploadVariant = '';
    uploadVersion = '';
    uploadBranch = '';
    uploadNotes = '';
    uploadBuildId = null;
    uploadedArtifacts = [];
    artifactRole = '';
    artifactProcessor = '';
    showUploadModal = true;
  }

  function closeUploadModal(): void {
    showUploadModal = false;
  }

  async function handleUploadCreate(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    uploadSubmitting = true;
    try {
      const build = await createManualBuild({
        product: product.name,
        board: uploadBoard,
        target: uploadTarget,
        variant: uploadVariant,
        branch: uploadBranch,
        versionString: uploadVersion || undefined,
        notes: uploadNotes || undefined,
        productId: product.id,
      });
      uploadBuildId = build.id;
      uploadStep = 'artifacts';
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create build';
    } finally {
      uploadSubmitting = false;
    }
  }

  async function handleArtifactUpload(file: File): Promise<void> {
    if (!uploadBuildId) return;
    uploadingFile = true;
    try {
      const artifactType = file.name.endsWith('.hex') ? 'plaintextHex'
        : file.name.endsWith('.cfw') ? 'encryptedCfw'
        : file.name.endsWith('.json') ? 'manifest'
        : undefined;

      const artifact = await uploadBuildArtifact(uploadBuildId, file, {
        role: artifactRole || undefined,
        processor: artifactProcessor || undefined,
        artifactType,
      });
      uploadedArtifacts = [...uploadedArtifacts, artifact];
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to upload artifact';
    } finally {
      uploadingFile = false;
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'stages', label: 'Build & Test Stages' },
    { key: 'boards', label: 'Boards' },
    { key: 'firmware', label: 'Firmware' },
    { key: 'build-config', label: 'Build Config' },
    { key: 'usage', label: 'Usage' },
  ];

  const boards = $derived(product.boards || []);
  const firmwareBuilds = $derived(product.firmwareBuilds || []);

  // Collect all revisions across boards for the revision config section
  const allRevisions = $derived(
    boards.flatMap((b) =>
      (b.revisions || []).map((r) => ({ ...r, boardId: b.id, boardName: b.name }))
    )
  );

  function sortedTargets(targets: ProductTarget[]): ProductTarget[] {
    return [...targets].sort((a, b) => (a.role === 'app' ? -1 : b.role === 'app' ? 1 : 0));
  }
</script>

<div class="animate-fade-in">
  <BackButton label="Back to products" onclick={onBack} />

  <ErrorAlert message={error} />

  <div class="card card-md">
    <!-- Header -->
    {#if editingProduct}
      <!-- Inline edit mode for product info -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-text-primary">Edit Product</h3>
          <div class="flex items-center gap-2">
            <button
              onclick={cancelEditProduct}
              class="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
            >
              <X size={14} />
              Cancel
            </button>
            <button
              onclick={saveProduct}
              disabled={savingProduct || !editName.trim()}
              class="flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Check size={14} />
              {savingProduct ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Product Name *</span>
            <input
              type="text"
              bind:value={editName}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Slug</span>
            <input
              type="text"
              bind:value={editSlug}
              placeholder="URL-safe identifier"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>
        </div>
        <label class="block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
          <input
            type="text"
            bind:value={editDescription}
            placeholder="Optional description"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Firmware Repo Slug</span>
            <input
              type="text"
              bind:value={editFwRepoSlug}
              placeholder="e.g. alpha_fw"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Mfg Firmware Repo Slug</span>
            <input
              type="text"
              bind:value={editMfgFwRepoSlug}
              placeholder="e.g. alpha_mfg_fw"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>
        </div>
      </div>
    {:else}
      <!-- Read-only header -->
      <div class="flex items-start gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-semibold text-text-primary">
              {product.name}
            </h2>
            <span
              class={[
                'inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium',
                product.active
                  ? 'bg-success-muted text-success'
                  : 'bg-surface-2 text-text-tertiary'
              ].join(' ')}
            >
              {product.active ? 'Active' : 'Inactive'}
            </span>
            {#if canManage}
              <button
                onclick={startEditProduct}
                title="Edit product"
                aria-label="Edit product"
                class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
              >
                <Pencil size={14} />
              </button>
            {/if}
          </div>
          {#if product.description}
            <p class="mt-1 text-sm text-text-secondary">{product.description}</p>
          {/if}

          <!-- Metadata row -->
          <div class="mt-3 flex flex-wrap gap-4 text-2xs text-text-tertiary">
            {#if product.slug}
              <span class="font-mono bg-surface-2 px-2 py-0.5 rounded">{product.slug}</span>
            {/if}
            {#if product.fwRepoSlug}
              <span class="font-mono bg-surface-2 px-2 py-0.5 rounded" title="Firmware repo">fw: {product.fwRepoSlug}</span>
            {/if}
            {#if product.mfgFwRepoSlug}
              <span class="font-mono bg-surface-2 px-2 py-0.5 rounded" title="Mfg firmware repo">mfg: {product.mfgFwRepoSlug}</span>
            {/if}
            {#if product.targets && product.targets.length > 0}
              {#each product.targets as target}
                <span class="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-2xs font-mono text-accent">
                  <Cpu size={10} />
                  {target.soc}
                  <span class="text-accent/60">#{target.appId}</span>
                </span>
              {/each}
            {/if}
            <span class="flex items-center gap-1">
              <Layers size={12} />
              <strong class="text-text-secondary">{boards.length}</strong> board{boards.length !== 1 ? 's' : ''}
            </span>
            <span class="flex items-center gap-1">
              <Cpu size={12} />
              <strong class="text-text-secondary">{firmwareBuilds.length}</strong> build{firmwareBuilds.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
        {#if canManage}
          <div class="flex-shrink-0">
            <button
              onclick={openUploadModal}
              class="btn btn-sm flex items-center gap-1.5"
            >
              <Upload size={14} />
              Upload Build
            </button>
          </div>
        {/if}
      </div>

      <!-- Revision config cards (always visible below header when revisions exist) -->
      {#if allRevisions.length > 0}
        <div class="mt-4 space-y-3">
          {#each allRevisions as rev}
            <div class="rounded-lg border border-border bg-surface-0 p-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <CircuitBoard size={14} class="text-accent" />
                  <span class="text-xs font-semibold text-text-primary">
                    Revision {rev.version.toUpperCase()}
                  </span>
                  {#if rev.ckBoardsName}
                    <span class="font-mono text-2xs text-text-tertiary">({rev.ckBoardsName})</span>
                  {/if}
                  <span class="font-mono text-2xs text-text-secondary">
                    Type {rev.deviceType ?? '—'} &middot; Variant {rev.deviceVariant ?? '—'}
                  </span>
                </div>
                {#if canManage && editingRevisionId !== rev.id}
                  <button
                    onclick={() => startEditRevision(rev)}
                    title="Edit revision config"
                    aria-label="Edit revision config"
                    class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                  >
                    <Pencil size={14} />
                  </button>
                {/if}
              </div>

              {#if editingRevisionId === rev.id}
                <!-- Inline edit for revision -->
                <div class="mt-3 space-y-3">
                  <div class="grid gap-3 sm:grid-cols-2">
                    <label class="block">
                      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Type</span>
                      <input
                        type="number"
                        min="0"
                        bind:value={editRevDeviceType}
                        class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
                      />
                    </label>
                    <label class="block">
                      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Variant</span>
                      <input
                        type="number"
                        min="0"
                        bind:value={editRevDeviceVariant}
                        class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
                      />
                    </label>
                  </div>

                  <div class="grid gap-3 sm:grid-cols-2">
                    {#each editRevTargets.sort((a, b) => a.role === 'app' ? -1 : b.role === 'app' ? 1 : 0) as target}
                      <div class="rounded-lg border border-border-subtle bg-surface-1 p-3">
                        <div class="mb-2 flex items-center gap-2">
                          <Cpu size={14} class="text-accent" />
                          <span class="text-xs font-semibold capitalize text-text-primary">{target.role}</span>
                          <span class="font-mono text-2xs text-text-tertiary">({target.soc})</span>
                        </div>
                        <label class="block">
                          <span class="mb-1 block text-2xs text-text-tertiary">AppID</span>
                          <input
                            type="number"
                            min="0"
                            bind:value={target.appId}
                            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-1.5 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
                          />
                        </label>
                      </div>
                    {/each}
                  </div>

                  <div class="flex items-center justify-end gap-2">
                    <button
                      onclick={cancelEditRevision}
                      class="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
                    >
                      <X size={14} />
                      Cancel
                    </button>
                    <button
                      onclick={saveRevision}
                      disabled={savingRevision}
                      class="flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                    >
                      <Check size={14} />
                      {savingRevision ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </div>
              {:else}
                <!-- Read-only targets -->
                {#if rev.targets && rev.targets.length > 0}
                  <div class="mt-2 grid gap-2 sm:grid-cols-2">
                    {#each sortedTargets(rev.targets) as target}
                      <div class="flex items-center justify-between rounded border border-border-subtle bg-surface-1 px-3 py-2">
                        <span class="text-xs font-medium capitalize text-text-primary">{target.role}</span>
                        <span class="font-mono text-2xs text-text-secondary">
                          {target.soc} &middot; AppID {target.appId}
                        </span>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <p class="mt-2 text-2xs text-text-tertiary">No targets configured.</p>
                {/if}
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {/if}

    <!-- Tabs -->
    <div class="mt-5 flex gap-1 border-b border-border">
      {#each tabs as tab}
        <button
          onclick={() => (activeTab = tab.key)}
          class={[
            'px-4 py-2 text-sm font-medium transition-colors',
            activeTab === tab.key
              ? 'border-b-2 border-accent text-accent'
              : 'text-text-tertiary hover:text-text-secondary'
          ].join(' ')}
        >
          {tab.label}
        </button>
      {/each}
    </div>

    <!-- Tab content -->
    <div class="mt-5">
      {#if activeTab === 'stages'}
        <ProductStages productId={product.id} productName={product.name} />
      {/if}

      {#if activeTab === 'boards'}
        <BoardList
          productId={product.id}
          {boards}
          {canManage}
          {onRefresh}
        />
      {/if}

      {#if activeTab === 'firmware'}
        <FirmwareBuildManager
          productId={product.id}
          builds={firmwareBuilds}
          targets={product.targets || []}
          {canManage}
          {onRefresh}
        />
      {/if}

      {#if activeTab === 'build-config'}
        {#if product.buildConfig}
          <BuildConfigCard config={product.buildConfig} />
        {:else}
          <div class="py-8 text-center text-sm text-text-tertiary">
            No build configuration set. Use the product creation wizard to auto-populate from ck_boards.
          </div>
        {/if}
      {/if}

      {#if activeTab === 'usage'}
        <div class="py-8 text-center text-sm text-text-tertiary">
          Session and test usage statistics coming soon.
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- Upload Build Modal -->
<Modal open={showUploadModal} title={uploadStep === 'details' ? 'Upload Build' : 'Upload Artifacts'} onclose={closeUploadModal} size="lg">
  {#if uploadStep === 'details'}
    <form onsubmit={handleUploadCreate} class="space-y-3">
      <div class="rounded-lg border border-border bg-surface-0 px-3 py-2">
        <div class="text-2xs text-text-tertiary">Product</div>
        <div class="text-sm font-medium text-text-primary">{product.name}</div>
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextInput bind:value={uploadBoard} label="Board" placeholder="e.g. alpha_b0" required />
        <Select
          bind:value={uploadTarget}
          label="Target"
          placeholder="Select target"
          options={[
            { value: 'app', label: 'App' },
            { value: 'mfg', label: 'Manufacturing' },
          ]}
          required
        />
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select
          bind:value={uploadVariant}
          label="Variant"
          placeholder="Select variant"
          options={[
            { value: 'debug', label: 'Debug' },
            { value: 'release', label: 'Release' },
          ]}
          required
        />
        <TextInput bind:value={uploadVersion} label="Version" placeholder="e.g. 0.8.3" />
      </div>
      <TextInput bind:value={uploadBranch} label="Branch" placeholder="e.g. main" required />
      <div>
        <label for="product-upload-notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
        <textarea
          id="product-upload-notes"
          bind:value={uploadNotes}
          placeholder="Optional notes about this build..."
          rows="2"
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
        ></textarea>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button type="button" onclick={closeUploadModal} class="btn btn-sm">Cancel</button>
        <button type="submit" disabled={uploadSubmitting} class="btn btn-sm btn-primary">
          {uploadSubmitting ? 'Creating...' : 'Create Build'}
        </button>
      </div>
    </form>
  {:else}
    <div class="space-y-4">
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="text-2xs text-text-tertiary mb-1">Build created</div>
        <div class="text-sm font-mono text-text-primary">{uploadBuildId?.slice(0, 12)}</div>
      </div>

      {#if uploadedArtifacts.length > 0}
        <div>
          <div class="text-2xs font-medium text-text-tertiary mb-2">Uploaded ({uploadedArtifacts.length})</div>
          <div class="space-y-1">
            {#each uploadedArtifacts as artifact}
              <div class="flex items-center gap-2 rounded border border-border bg-surface-0 px-3 py-1.5 text-sm">
                <span class="flex-1 font-mono text-text-primary truncate">{artifact.name}</span>
                <span class="text-2xs text-success">Uploaded</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="rounded-lg border-2 border-dashed border-border bg-surface-0 p-4">
        <div class="text-sm font-medium text-text-primary mb-3">Add Artifact</div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-3">
          <Select
            bind:value={artifactRole}
            label="Role"
            placeholder="Select role"
            options={[
              { value: 'app', label: 'App' },
              { value: 'comms', label: 'Comms' },
              { value: 'modem', label: 'Modem' },
            ]}
          />
          <Select
            bind:value={artifactProcessor}
            label="Processor"
            placeholder="Select processor"
            options={[
              { value: 'nrf52840', label: 'nRF52840' },
              { value: 'nrf9151', label: 'nRF9151' },
            ]}
          />
        </div>
        <label
          for="product-artifact-file"
          class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border p-4 transition-colors hover:border-text-tertiary hover:bg-surface-1"
        >
          <Upload size={20} class="text-text-tertiary" />
          <span class="text-2xs text-text-tertiary">
            {uploadingFile ? 'Uploading...' : 'Click to select .hex or .cfw file'}
          </span>
          <input
            id="product-artifact-file"
            type="file"
            accept=".hex,.cfw,.bin,.json"
            class="hidden"
            disabled={uploadingFile}
            onchange={(e) => {
              const input = e.target as HTMLInputElement;
              const file = input.files?.[0];
              if (file) handleArtifactUpload(file);
              input.value = '';
            }}
          />
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <button onclick={closeUploadModal} class="btn btn-sm btn-primary">
          Done
        </button>
      </div>
    </div>
  {/if}
</Modal>
