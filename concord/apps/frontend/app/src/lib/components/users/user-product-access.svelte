<script lang="ts">
  import { Shield, Plus, Trash2, X } from 'lucide-svelte';
  import { api } from '$lib/api';
  import Select from '$lib/components/ui/select.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import { formatTimeAgo } from '$lib/utils/formatting';

  interface Props {
    userId: string;
    userName: string;
    userRole: string;
    canManage: boolean;
    onClose: () => void;
  }

  let { userId, userName, userRole, canManage, onClose }: Props = $props();

  interface AccessEntry {
    id: string;
    userId: string;
    productId: string;
    level: string;
    productName?: string;
    productSlug?: string;
    createdAt: string;
    updatedAt: string;
  }

  interface ProductRecord {
    id: string;
    name: string;
  }

  let entries = $state<AccessEntry[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let showAddForm = $state(false);
  let products = $state<ProductRecord[]>([]);
  let loadingProducts = $state(false);
  let addProductId = $state('');
  let addLevel = $state('view');
  let adding = $state(false);
  let addError = $state<string | null>(null);

  const isBypassRole = $derived(userRole === 'ADMIN' || userRole === 'MAINTAINER');

  const existingProductIds = $derived(new Set(entries.map((e) => e.productId)));

  const productOptions = $derived(
    products
      .filter((p) => !existingProductIds.has(p.id))
      .map((p) => ({ value: p.id, label: p.name }))
  );

  const levelOptions = [
    { value: 'view', label: 'View' },
    { value: 'operate', label: 'Operate' },
    { value: 'develop', label: 'Develop' },
    { value: 'admin', label: 'Admin' },
  ];

  async function fetchAccess() {
    loading = true;
    error = null;
    try {
      const res = await api.get<{ data: AccessEntry[] }>(
        `/v2/users/${userId}/product-access`
      );
      entries = res.data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load product access';
    } finally {
      loading = false;
    }
  }

  async function fetchProducts() {
    if (products.length > 0) return;
    loadingProducts = true;
    try {
      const res = await api.get<{ data: { data: ProductRecord[] } }>('/v2/products');
      products = res.data?.data || [];
    } catch {
      // Non-critical
    } finally {
      loadingProducts = false;
    }
  }

  $effect(() => {
    if (userId) fetchAccess();
  });

  async function addAccess() {
    if (!addProductId || !addLevel) return;
    adding = true;
    addError = null;
    try {
      await api.put(`/v2/users/${userId}/product-access`, {
        access: [
          ...entries.map((e) => ({ productId: e.productId, level: e.level })),
          { productId: addProductId, level: addLevel },
        ],
      });
      showAddForm = false;
      addProductId = '';
      addLevel = 'view';
      await fetchAccess();
    } catch (err) {
      addError = err instanceof Error ? err.message : 'Failed to add access';
    } finally {
      adding = false;
    }
  }

  async function updateLevel(entry: AccessEntry) {
    try {
      await api.put(`/v2/users/${userId}/product-access`, {
        access: entries.map((e) => ({ productId: e.productId, level: e.level })),
      });
      await fetchAccess();
    } catch {
      await fetchAccess();
    }
  }

  async function removeAccess(entry: AccessEntry) {
    if (!confirm(`Remove ${entry.productName || 'this product'} access for ${userName}?`)) return;
    try {
      await api.put(`/v2/users/${userId}/product-access`, {
        access: entries
          .filter((e) => e.id !== entry.id)
          .map((e) => ({ productId: e.productId, level: e.level })),
      });
      await fetchAccess();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to remove access';
    }
  }

  function openAddForm() {
    showAddForm = true;
    addError = null;
    addProductId = '';
    addLevel = 'view';
    fetchProducts();
  }
</script>

<tr>
  <td colspan="5" class="px-0 py-0">
    <div class="border-t border-accent/20 bg-surface-0 px-6 py-4">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <Shield size={14} class="text-accent" />
          <span class="text-sm font-medium text-text-primary">
            Product Access — {userName}
          </span>
        </div>
        <div class="flex items-center gap-2">
          {#if canManage && !isBypassRole}
            <button class="btn btn-sm btn-ghost text-accent" onclick={openAddForm}>
              <Plus size={14} class="mr-1" />
              Add
            </button>
          {/if}
          <button class="btn btn-sm btn-ghost" onclick={onClose}>
            <X size={14} />
          </button>
        </div>
      </div>

      {#if isBypassRole}
        <div class="rounded-lg border border-dashed border-border bg-surface-1 p-3 text-center">
          <p class="text-sm text-text-secondary">{userRole}s can access all products by default.</p>
          <p class="text-2xs text-text-tertiary mt-1">Product access entries are not needed for this role.</p>
        </div>
      {:else}
        <ErrorAlert message={error} />

        {#if showAddForm && canManage}
          <div class="mb-3 rounded-lg border border-border bg-surface-1 p-3">
            <ErrorAlert message={addError} />
            <div class="flex flex-wrap items-end gap-3">
              <div class="min-w-[200px] flex-1">
                <Select
                  bind:value={addProductId}
                  options={productOptions}
                  placeholder={loadingProducts ? 'Loading...' : 'Select product'}
                  label="Product"
                  disabled={loadingProducts}
                />
              </div>
              <div class="min-w-[120px]">
                <Select
                  bind:value={addLevel}
                  options={levelOptions}
                  label="Level"
                />
              </div>
              <button
                class="btn btn-sm btn-primary"
                disabled={!addProductId || adding}
                onclick={addAccess}
              >
                {adding ? '...' : 'Add'}
              </button>
              <button class="btn btn-sm btn-ghost" onclick={() => (showAddForm = false)}>
                Cancel
              </button>
            </div>
          </div>
        {/if}

        {#if loading}
          <div class="text-center py-3">
            <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
          </div>
        {:else if entries.length === 0}
          <div class="rounded-lg border border-dashed border-border bg-surface-1 p-3 text-center">
            <p class="text-sm text-text-secondary">No product access granted</p>
            <p class="text-2xs text-text-tertiary mt-1">This user cannot see any products.</p>
          </div>
        {:else}
          <div class="rounded-lg border border-border overflow-x-auto">
            <table class="w-full text-sm border-collapse">
              <thead>
                <tr class="bg-surface-2">
                  <th class="text-left px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Product</th>
                  <th class="text-left px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Level</th>
                  <th class="text-left px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Since</th>
                  {#if canManage}
                    <th class="text-right px-3 py-1.5 text-2xs font-semibold uppercase tracking-wider text-text-tertiary"></th>
                  {/if}
                </tr>
              </thead>
              <tbody>
                {#each entries as entry (entry.id)}
                  <tr class="border-t border-border-subtle">
                    <td class="px-3 py-2 text-sm text-text-primary">{entry.productName || entry.productId}</td>
                    <td class="px-3 py-2">
                      {#if canManage}
                        <Select
                          compact
                          bind:value={entry.level}
                          options={levelOptions}
                          onchange={() => updateLevel(entry)}
                        />
                      {:else}
                        <span class="text-sm text-text-secondary capitalize">{entry.level}</span>
                      {/if}
                    </td>
                    <td class="px-3 py-2 text-2xs text-text-tertiary">{formatTimeAgo(entry.createdAt)}</td>
                    {#if canManage}
                      <td class="px-3 py-2 text-right">
                        <button
                          class="btn btn-sm btn-ghost text-error"
                          onclick={() => removeAccess(entry)}
                          title="Remove access"
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    {/if}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      {/if}
    </div>
  </td>
</tr>
