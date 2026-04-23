<script lang="ts">
  import { Shield, UserPlus, X, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api';
  import type { Product } from '$lib/types/models';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import { formatTimeAgo } from '$lib/utils/formatting';

  interface Props {
    product: Product;
    canManage: boolean;
    onRefresh: () => void;
  }

  let { product, canManage, onRefresh }: Props = $props();

  // ── Types ────────────────────────────────────────────────

  interface AccessEntry {
    id: string;
    userId: string;
    productId: string;
    level: string;
    userName: string;
    userEmail: string;
    userRole: string;
    createdAt: string;
    updatedAt: string;
  }

  interface UserRecord {
    id: string;
    name: string;
    email: string;
    role: string;
  }

  // ── State ────────────────────────────────────────────────

  let entries = $state<AccessEntry[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let showGrantForm = $state(false);
  let grantUserId = $state('');
  let grantLevel = $state('view');
  let granting = $state(false);
  let grantError = $state<string | null>(null);

  let allUsers = $state<UserRecord[]>([]);
  let loadingUsers = $state(false);

  // ── Derived ──────────────────────────────────────────────

  const existingUserIds = $derived(new Set(entries.map((e) => e.userId)));

  const selectableUsers = $derived(
    allUsers.filter(
      (u) =>
        !existingUserIds.has(u.id) &&
        u.role !== 'ADMIN' &&
        u.role !== 'MAINTAINER'
    )
  );

  const userOptions = $derived(
    selectableUsers.map((u) => ({
      value: u.id,
      label: `${u.name} (${u.email})`,
    }))
  );

  const levelOptions = [
    { value: 'view', label: 'View' },
    { value: 'operate', label: 'Operate' },
    { value: 'develop', label: 'Develop' },
    { value: 'admin', label: 'Admin' },
  ];

  // ── Data fetching ────────────────────────────────────────

  async function fetchAccess() {
    loading = true;
    error = null;
    try {
      const res = await api.get<{ data: AccessEntry[] }>(
        `/v2/products/${product.id}/access`
      );
      entries = res.data || [];
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load access entries';
    } finally {
      loading = false;
    }
  }

  async function fetchUsers() {
    if (allUsers.length > 0) return;
    loadingUsers = true;
    try {
      const res = await api.get<{ data: { data: UserRecord[] } }>('/v2/users');
      allUsers = res.data?.data || [];
    } catch {
      // Non-critical — the user dropdown will just be empty
    } finally {
      loadingUsers = false;
    }
  }

  $effect(() => {
    if (product?.id) fetchAccess();
  });

  // ── Mutations ────────────────────────────────────────────

  async function grantAccess() {
    if (!grantUserId || !grantLevel) return;
    granting = true;
    grantError = null;
    try {
      await api.post(`/v2/products/${product.id}/access`, {
        userId: grantUserId,
        level: grantLevel,
      });
      showGrantForm = false;
      grantUserId = '';
      grantLevel = 'view';
      await fetchAccess();
      onRefresh();
    } catch (err) {
      grantError = err instanceof Error ? err.message : 'Failed to grant access';
    } finally {
      granting = false;
    }
  }

  async function handleLevelChange(entry: AccessEntry) {
    // entry.level is already updated by the Select binding
    const newLevel = entry.level;
    try {
      await api.put(`/v2/products/${product.id}/access/${entry.id}`, {
        level: newLevel,
      });
      await fetchAccess();
      onRefresh();
    } catch (err) {
      // Refetch to restore correct state
      await fetchAccess();
      error = err instanceof Error ? err.message : 'Failed to update access level';
    }
  }

  async function revokeAccess(entry: AccessEntry) {
    if (!confirm(`Revoke access for ${entry.userName}?`)) return;
    try {
      await api.delete(`/v2/products/${product.id}/access/${entry.id}`);
      await fetchAccess();
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to revoke access';
    }
  }

  function openGrantForm() {
    showGrantForm = true;
    grantError = null;
    grantUserId = '';
    grantLevel = 'view';
    fetchUsers();
  }

  function closeGrantForm() {
    showGrantForm = false;
    grantError = null;
  }

  // ── Helpers ──────────────────────────────────────────────

  function levelBadgeClass(level: string): string {
    switch (level) {
      case 'view': return 'badge badge-info';
      case 'operate': return 'badge';
      case 'develop': return 'badge badge-warning';
      case 'admin': return 'badge badge-accent';
      default: return 'badge';
    }
  }
</script>

<!-- Header -->
<div class="mb-4 flex items-center justify-between">
  <h3 class="text-sm font-semibold text-text-primary">Product Access</h3>
  {#if canManage}
    <button class="btn btn-sm btn-primary" onclick={openGrantForm}>
      <UserPlus size={14} class="mr-1" />
      Grant Access
    </button>
  {/if}
</div>

<ErrorAlert message={error} />

<!-- Grant access form -->
{#if showGrantForm}
  <div class="card card-sm mb-4">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm font-medium text-text-primary">Grant Access</span>
      <button class="btn btn-sm btn-ghost" onclick={closeGrantForm}>
        <X size={14} />
      </button>
    </div>

    <ErrorAlert message={grantError} />

    <div class="flex flex-wrap items-end gap-3">
      <div class="min-w-[240px] flex-1">
        <Select
          bind:value={grantUserId}
          options={userOptions}
          placeholder={loadingUsers ? 'Loading users...' : 'Select user'}
          label="User"
          disabled={loadingUsers}
        />
      </div>
      <div class="min-w-[140px]">
        <Select
          bind:value={grantLevel}
          options={levelOptions}
          label="Level"
        />
      </div>
      <button
        class="btn btn-sm btn-primary"
        disabled={!grantUserId || granting}
        onclick={grantAccess}
      >
        {granting ? 'Granting...' : 'Grant'}
      </button>
    </div>
  </div>
{/if}

<!-- Loading state -->
{#if loading}
  <div class="rounded-lg border border-border bg-surface-0 p-6 text-center">
    <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
  </div>

<!-- Empty state -->
{:else if entries.length === 0}
  <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
    <Shield size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
    <p class="text-sm text-text-secondary">No users have been granted access to this product.</p>
    <p class="text-2xs text-text-tertiary mt-1">Administrators and Maintainers can access all products by default.</p>
  </div>

<!-- Access table -->
{:else}
  <div class="rounded-lg border border-border overflow-x-auto">
    <table class="w-full text-sm border-collapse">
      <thead>
        <tr class="bg-surface-2">
          <th class="text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">User</th>
          <th class="text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Role</th>
          <th class="text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Access Level</th>
          <th class="text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Granted</th>
          {#if canManage}
            <th class="text-right px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary">Actions</th>
          {/if}
        </tr>
      </thead>
      <tbody>
        {#each entries as entry (entry.id)}
          <tr class="border-t border-border-subtle">
            <td class="px-4 py-2.5">
              <div class="text-sm text-text-primary">{entry.userName}</div>
              <div class="text-2xs text-text-tertiary">{entry.userEmail}</div>
            </td>
            <td class="px-4 py-2.5">
              <span class="text-sm text-text-secondary">{entry.userRole}</span>
            </td>
            <td class="px-4 py-2.5">
              {#if canManage}
                <Select
                  compact
                  bind:value={entry.level}
                  options={levelOptions}
                  onchange={() => handleLevelChange(entry)}
                />
              {:else}
                <span class={levelBadgeClass(entry.level)}>{entry.level}</span>
              {/if}
            </td>
            <td class="px-4 py-2.5">
              <span class="text-2xs text-text-tertiary">{formatTimeAgo(entry.createdAt)}</span>
            </td>
            {#if canManage}
              <td class="px-4 py-2.5 text-right">
                <button
                  class="btn btn-sm btn-danger"
                  onclick={() => revokeAccess(entry)}
                  title="Revoke access"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
