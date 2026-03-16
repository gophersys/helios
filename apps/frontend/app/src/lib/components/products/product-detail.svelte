<script lang="ts">
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import BoardList from './board-list.svelte';
  import FirmwareBuildManager from './firmware-app-list.svelte';
  import type { Product, Chipset } from '$lib/types/models';

  type Tab = 'boards' | 'firmware' | 'usage';

  interface Props {
    product: Product;
    chipsets: Chipset[];
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
  }

  let { product, chipsets, canManage, onBack, onRefresh }: Props = $props();

  let activeTab = $state<Tab>('boards');
  let error = $state<string | null>(null);

  const tabs: { key: Tab; label: string }[] = [
    { key: 'boards', label: 'Boards' },
    { key: 'firmware', label: 'Firmware' },
    { key: 'usage', label: 'Usage' },
  ];

  const boards = $derived(product.boards || []);
  const firmwareBuilds = $derived(product.firmwareBuilds || []);
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

        <div class="mt-3 flex gap-4 text-2xs text-text-tertiary">
          <span>
            <strong class="text-text-secondary">{boards.length}</strong> board{boards.length !== 1 ? 's' : ''}
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
      {#if activeTab === 'boards'}
        <BoardList
          productId={product.id}
          {boards}
          builds={firmwareBuilds}
          {chipsets}
          {canManage}
          {onRefresh}
        />
      {/if}

      {#if activeTab === 'firmware'}
        <FirmwareBuildManager
          productId={product.id}
          builds={firmwareBuilds}
          {chipsets}
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
