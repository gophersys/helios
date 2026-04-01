<script lang="ts">
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ProductStages from './product-stages.svelte';
  import FirmwareTab from './firmware-tab.svelte';
  import BuildConfigTab from './build-config-tab.svelte';
  import { Cpu, Pencil, Check, X, CircuitBoard, ExternalLink, Upload, Package, FlaskConical, Factory, Wrench } from 'lucide-svelte';
  import type { Product, BoardRevision, ProductTarget } from '$lib/types/models';
  import type { BuildArtifact } from '$lib/types/ci';
  import { api } from '$lib/api';
  import { createManualBuild, uploadBuildArtifact } from '$lib/services/ci';

  type Tab = 'firmware' | 'validation' | 'build' | 'manufacturing';

  interface Props {
    product: Product;
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
  }

  let { product, canManage, onBack, onRefresh }: Props = $props();

  let activeTab = $state<Tab>('firmware');
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
      await api.put(
        `/v2/products/${product.id}/boards/${ctx.boardId}/revisions/${editingRevisionId}`,
        { deviceType: editRevDeviceType, deviceVariant: editRevDeviceVariant }
      );

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
  let uploadedArtifacts = $state<BuildArtifact[]>([]);
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

  const tabs: { key: Tab; label: string; icon: typeof Package }[] = [
    { key: 'firmware', label: 'Firmware', icon: Package },
    { key: 'validation', label: 'Validation', icon: FlaskConical },
    { key: 'build', label: 'Build Config', icon: Wrench },
    { key: 'manufacturing', label: 'Manufacturing', icon: Factory },
  ];

  const boards = $derived(product.boards || []);

  const allRevisions = $derived(
    boards.flatMap((b) =>
      (b.revisions || []).map((r) => ({ ...r, boardId: b.id, boardName: b.name }))
    )
  );

  function sortedTargets(targets: ProductTarget[]): ProductTarget[] {
    return [...targets].sort((a, b) => (a.role === 'app' ? -1 : b.role === 'app' ? 1 : 0));
  }

  function bitbucketUrl(slug: string): string {
    return `https://bitbucket.org/corekinect/${slug}`;
  }
</script>

<div class="animate-fade-in">
  <BackButton label="Back to products" onclick={onBack} />

  <ErrorAlert message={error} />

  <div class="card card-md">
    <!-- ═══ HEADER ═══ -->
    {#if editingProduct}
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
      <div class="flex items-start gap-4">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-semibold text-text-primary">{product.name}</h2>
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

          <!-- Repo links -->
          <div class="mt-3 flex flex-wrap items-center gap-3 text-2xs">
            {#if product.fwRepoSlug}
              <a
                href={bitbucketUrl(product.fwRepoSlug)}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 font-mono text-text-secondary hover:text-accent transition-colors"
              >
                {product.fwRepoSlug}
                <Check size={10} class="text-success" />
                <ExternalLink size={10} class="opacity-60" />
              </a>
            {/if}
            {#if product.mfgFwRepoSlug}
              <a
                href={bitbucketUrl(product.mfgFwRepoSlug)}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 font-mono text-text-secondary hover:text-accent transition-colors"
              >
                {product.mfgFwRepoSlug}
                <Check size={10} class="text-success" />
                <ExternalLink size={10} class="opacity-60" />
              </a>
            {/if}
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

      <!-- ═══ HARDWARE REVISION CARDS ═══ -->
      {#if allRevisions.length > 0}
        <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {#each allRevisions as rev}
            <div class="rounded-lg border border-border bg-surface-0 p-3">
              {#if editingRevisionId === rev.id}
                <!-- Inline edit for revision -->
                <div class="space-y-3">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <CircuitBoard size={14} class="text-accent" />
                      <span class="text-xs font-semibold text-text-primary">
                        {rev.version.toUpperCase()}
                      </span>
                    </div>
                    <div class="flex items-center gap-1">
                      <button
                        onclick={cancelEditRevision}
                        class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                        title="Cancel"
                        aria-label="Cancel editing revision"
                      >
                        <X size={14} />
                      </button>
                      <button
                        onclick={saveRevision}
                        disabled={savingRevision}
                        class="rounded p-1 text-accent hover:bg-accent/10 disabled:opacity-50"
                        title="Save"
                        aria-label="Save revision"
                      >
                        <Check size={14} />
                      </button>
                    </div>
                  </div>
                  <div class="grid gap-2 grid-cols-2">
                    <label class="block">
                      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Type</span>
                      <input
                        type="number"
                        min="0"
                        bind:value={editRevDeviceType}
                        class="w-full rounded-lg border border-border bg-surface-1 px-2 py-1.5 text-xs font-mono text-text-primary focus:border-accent focus:outline-none"
                      />
                    </label>
                    <label class="block">
                      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Variant</span>
                      <input
                        type="number"
                        min="0"
                        bind:value={editRevDeviceVariant}
                        class="w-full rounded-lg border border-border bg-surface-1 px-2 py-1.5 text-xs font-mono text-text-primary focus:border-accent focus:outline-none"
                      />
                    </label>
                  </div>
                  {#each editRevTargets.sort((a, b) => a.role === 'app' ? -1 : b.role === 'app' ? 1 : 0) as target}
                    <div class="rounded border border-border-subtle bg-surface-1 p-2">
                      <div class="mb-1.5 flex items-center gap-1.5">
                        <Cpu size={12} class="text-accent" />
                        <span class="text-2xs font-semibold capitalize text-text-primary">{target.role}</span>
                        <span class="font-mono text-2xs text-text-tertiary">({target.soc})</span>
                      </div>
                      <label class="block">
                        <span class="mb-0.5 block text-2xs text-text-tertiary">AppID</span>
                        <input
                          type="number"
                          min="0"
                          bind:value={target.appId}
                          class="w-full rounded border border-border bg-surface-0 px-2 py-1 text-xs font-mono text-text-primary focus:border-accent focus:outline-none"
                        />
                      </label>
                    </div>
                  {/each}
                </div>
              {:else}
                <!-- Read-only revision card -->
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <CircuitBoard size={14} class="text-accent" />
                    <span class="text-xs font-semibold text-text-primary">
                      {rev.version.toUpperCase()}
                    </span>
                    <StatusBadge status={rev.status} />
                  </div>
                  {#if canManage}
                    <button
                      onclick={() => startEditRevision(rev)}
                      title="Edit revision config"
                      aria-label="Edit revision config"
                      class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                    >
                      <Pencil size={12} />
                    </button>
                  {/if}
                </div>
                {#if rev.ckBoardsName}
                  <div class="mt-1.5 font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</div>
                {/if}
                <div class="mt-1 font-mono text-2xs text-text-secondary">
                  DeviceType {rev.deviceType ?? '—'} / Variant {rev.deviceVariant ?? '—'}
                </div>
                {#if rev.targets && rev.targets.length > 0}
                  <div class="mt-2 space-y-1">
                    {#each sortedTargets(rev.targets) as target}
                      <div class="flex items-center justify-between rounded border border-border-subtle bg-surface-1 px-2 py-1.5">
                        <div class="flex items-center gap-1.5">
                          <Cpu size={12} class="text-accent" />
                          <span class="text-2xs font-medium capitalize text-text-primary">{target.role}</span>
                        </div>
                        <span class="font-mono text-2xs text-text-secondary">
                          {target.soc} &middot; {target.appId}
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

    <!-- ═══ TABS ═══ -->
    <div class="mt-5 flex gap-1 border-b border-border">
      {#each tabs as tab}
        {@const TabIcon = tab.icon}
        <button
          onclick={() => (activeTab = tab.key)}
          class={[
            'flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === tab.key
              ? 'border-b-2 border-accent text-accent'
              : 'text-text-tertiary hover:text-text-secondary'
          ].join(' ')}
        >
          <TabIcon size={14} />
          {tab.label}
        </button>
      {/each}
    </div>

    <!-- ═══ TAB CONTENT ═══ -->
    <div class="mt-5">
      {#if activeTab === 'firmware'}
        <FirmwareTab productId={product.id} {canManage} />
      {/if}

      {#if activeTab === 'validation'}
        <ProductStages productId={product.id} productName={product.name} revisions={product.boards?.[0]?.revisions ?? []} fwRepoSlug={product.fwRepoSlug ?? ''} />
      {/if}

      {#if activeTab === 'build'}
        <BuildConfigTab productId={product.id} productName={product.name} {canManage} />
      {/if}

      {#if activeTab === 'manufacturing'}
        <div class="py-8 text-center">
          <Factory size={32} class="mx-auto mb-3 text-text-tertiary opacity-40" />
          <p class="text-sm text-text-secondary">Manufacturing configuration coming soon.</p>
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
