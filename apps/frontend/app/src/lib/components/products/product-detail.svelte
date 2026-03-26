<script lang="ts">
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import BoardList from './board-list.svelte';
  import FirmwareBuildManager from './firmware-app-list.svelte';
  import ProductStages from './product-stages.svelte';
  import BuildConfigCard from './build-config-card.svelte';
  import { GitBranch, Cpu, Layers, Wrench } from 'lucide-svelte';
  import type { Product, Chipset } from '$lib/types/models';

  type Tab = 'stages' | 'boards' | 'firmware' | 'build-config' | 'usage';

  interface Props {
    product: Product;
    chipsets: Chipset[];
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
  }

  let { product, chipsets, canManage, onBack, onRefresh }: Props = $props();

  let activeTab = $state<Tab>('stages');
  let error = $state<string | null>(null);

  const tabs: { key: Tab; label: string }[] = [
    { key: 'stages', label: 'Build & Test Stages' },
    { key: 'boards', label: 'Boards' },
    { key: 'firmware', label: 'Firmware' },
    { key: 'build-config', label: 'Build Config' },
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

        <!-- Metadata row -->
        <div class="mt-3 flex flex-wrap gap-4 text-2xs text-text-tertiary">
          {#if product.slug}
            <span class="font-mono bg-surface-2 px-2 py-0.5 rounded">{product.slug}</span>
          {/if}
          {#if product.repoSlug}
            <span class="flex items-center gap-1">
              <GitBranch size={12} />
              <span class="font-mono">{product.repoSlug}</span>
              {#if product.repoBranch}
                <span class="text-text-tertiary/50">:</span>
                <span class="font-mono">{product.repoBranch}</span>
              {/if}
            </span>
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
      {#if activeTab === 'stages'}
        <ProductStages productId={product.id} productName={product.name} />
      {/if}

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
