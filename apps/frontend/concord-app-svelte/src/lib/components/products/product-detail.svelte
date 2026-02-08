<script lang="ts">
  import { Cpu } from 'lucide-svelte';
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import { useChipsetConfig } from '$lib/hooks/use-chipset-config.svelte';
  import BoardRevisionList from './board-revision-list.svelte';
  import FirmwareAppList from './firmware-app-list.svelte';
  import type { Product } from '$lib/types/models';

  type Tab = 'overview' | 'firmware' | 'usage';

  interface Props {
    product: Product;
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
  }

  let { product, canManage, onBack, onRefresh }: Props = $props();

  let activeTab = $state<Tab>('overview');
  let error = $state<string | null>(null);
  const chipsetState = useChipsetConfig();

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'firmware', label: 'Firmware' },
    { key: 'usage', label: 'Usage' },
  ];

  const boardRevisions = $derived(product.boardRevisions || []);
  const firmwareApps = $derived(product.firmwareApplications || []);
  const firmwareBuilds = $derived(product.firmwareBuilds || []);
  const chipsets = $derived(
    product.chipsets ||
    [...new Set(firmwareApps.map((a) => a.chipset).filter(Boolean) as string[])].sort()
  );
</script>

<div class="animate-fade-in">
  <BackButton label="Back to products" onclick={onBack} />

  <ErrorAlert message={error} />

  <div class="card card-md">
    <!-- Header -->
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
        </div>
        {#if product.description}
          <p class="mt-1 text-sm text-text-secondary">{product.description}</p>
        {/if}

        <!-- Chipset badges -->
        {#if chipsets.length > 0}
          <div class="mt-2 flex flex-wrap gap-1.5">
            {#each chipsets as c}
              <span class="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent">
                <Cpu size={16} />
                {c}
              </span>
            {/each}
          </div>
        {/if}

        <div class="mt-3 flex gap-4 text-2xs text-text-tertiary">
          <span>
            <strong class="text-text-secondary">{boardRevisions.length}</strong> board revision{boardRevisions.length !== 1 ? 's' : ''}
          </span>
          <span>
            <strong class="text-text-secondary">{firmwareApps.length}</strong> firmware app{firmwareApps.length !== 1 ? 's' : ''}
          </span>
          <span>
            <strong class="text-text-secondary">{firmwareBuilds.length}</strong> firmware build{firmwareBuilds.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </div>

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
      {#if activeTab === 'overview'}
        <BoardRevisionList
          productId={product.id}
          revisions={boardRevisions}
          supportedSocs={chipsetState.data?.supportedSocs || []}
          {canManage}
          {onRefresh}
        />
      {/if}

      {#if activeTab === 'firmware'}
        <FirmwareAppList
          productId={product.id}
          apps={firmwareApps}
          builds={firmwareBuilds}
          {boardRevisions}
          chipsetConfig={chipsetState.data}
          {canManage}
          {onRefresh}
        />
      {/if}

      {#if activeTab === 'usage'}
        <div class="py-8 text-center text-sm text-text-tertiary">
          Session and test usage statistics coming soon.
        </div>
      {/if}
    </div>
  </div>
</div>
