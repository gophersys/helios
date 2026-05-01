<script lang="ts">
  import { Factory, Play, Loader2, Check, X, QrCode } from 'lucide-svelte';
  import ProductStages from '../product-stages.svelte';
  import TestAppStatusCard from '../test-app-status-card.svelte';
  import TestPackageList from '../test-package-list.svelte';
  import FixtureDesignsSection from '../fixture-designs-section.svelte';
  import FixtureInstances from '../fixture-instances.svelte';
  import SessionStartDialog from '$lib/components/manufacturing/session-start-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import { api } from '$lib/api';
  import type { Product, BoardRevision, Board } from '$lib/types/models';

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

  // Resolve which board owns the selected revision so we can build the
  // board-revisions API URL.
  const selectedBoard = $derived<Board | null>(
    selectedRevision
      ? (product.boards || []).find((b) => (b.revisions || []).some((r) => r.id === selectedRevision.id)) ?? null
      : null
  );

  // Session readiness checks
  const mfgStatus = $derived(product.testAppStatus?.manufacturing ?? null);
  const hasReleasedApp = $derived(mfgStatus?.status === 'RELEASED');
  const hasStage = $derived(revisions.length > 0);

  let showSessionDialog = $state(false);

  function handleSessionStarted(): void {
    onRefresh();
  }

  // ── SNR length config ────────────────────────────────────────────────
  // Per-revision setting that locks the manufacturing scan UI to an exact
  // serial number length. Null = no enforcement (default).
  let snrLengthInput = $state<string>('');
  let snrSaving = $state(false);
  let snrError = $state<string | null>(null);
  let snrSavedAt = $state<number | null>(null);

  // Sync input when the selected revision changes.
  $effect(() => {
    snrLengthInput =
      selectedRevision?.snrLength != null ? String(selectedRevision.snrLength) : '';
    snrError = null;
    snrSavedAt = null;
  });

  const snrInputDirty = $derived(
    selectedRevision != null
      && snrLengthInput.trim() !== (selectedRevision.snrLength != null ? String(selectedRevision.snrLength) : '')
  );

  async function saveSnrLength(): Promise<void> {
    if (!selectedRevision || !selectedBoard) return;
    snrError = null;
    snrSaving = true;
    try {
      const trimmed = snrLengthInput.trim();
      let payloadValue: number | null;
      if (trimmed === '') {
        payloadValue = null;
      } else {
        const parsed = Number(trimmed);
        if (!Number.isInteger(parsed) || parsed <= 0) {
          snrError = 'SNR length must be a positive integer.';
          return;
        }
        payloadValue = parsed;
      }
      await api.put(
        `/v2/products/${product.id}/boards/${selectedBoard.id}/revisions/${selectedRevision.id}`,
        { snrLength: payloadValue }
      );
      snrSavedAt = Date.now();
      onRefresh();
    } catch (err: unknown) {
      snrError = err instanceof Error ? err.message : 'Failed to save SNR length';
    } finally {
      snrSaving = false;
    }
  }

  function clearSnrLength(): void {
    snrLengthInput = '';
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

    <!-- Section 2: Scan settings -->
    {#if selectedRevision}
      <div class="card card-md">
        <div class="flex items-center gap-2 mb-3">
          <QrCode size={14} class="text-accent" />
          <h3 class="text-sm font-semibold text-text-primary">Scan Settings</h3>
          <span class="text-2xs text-text-tertiary ml-auto">
            Revision <span class="font-mono text-text-secondary">{selectedRevision.version}</span>
          </span>
        </div>

        <p class="text-2xs text-text-tertiary mb-3">
          Set the expected serial number length for this revision. The manufacturing scan
          dialog refuses to verify panels until the operator types exactly this many
          characters. Leave blank to skip length enforcement.
        </p>

        <ErrorAlert message={snrError} />

        <div class="flex items-end gap-2">
          <label class="block flex-1 max-w-xs">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Serial Number Length</span>
            <input
              type="number"
              min="1"
              step="1"
              bind:value={snrLengthInput}
              placeholder="No enforcement"
              disabled={!canManage || snrSaving}
              class="input input-md font-mono w-full"
              data-testid="snr-length-input"
            />
          </label>
          {#if snrLengthInput && canManage}
            <button
              onclick={clearSnrLength}
              disabled={snrSaving}
              class="btn btn-sm btn-icon btn-ghost"
              title="Clear (disable enforcement)"
              aria-label="Clear SNR length"
            >
              <X size={14} />
            </button>
          {/if}
          {#if canManage}
            <button
              onclick={saveSnrLength}
              disabled={snrSaving || !snrInputDirty}
              class="btn btn-sm btn-primary"
              data-testid="snr-length-save"
            >
              {#if snrSaving}
                <Loader2 size={12} class="animate-spin" />
                Saving...
              {:else if snrSavedAt && !snrInputDirty}
                <Check size={12} />
                Saved
              {:else}
                Save
              {/if}
            </button>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Section 3: Test App -->
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

  </div>
{/if}
