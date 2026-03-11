<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { UserPlus, X, Check } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { FullUser, PermissionSet } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import { formatDate } from '$lib/utils/formatting';
  import PermissionSetsTab from '$lib/components/users/permission-sets-tab.svelte';

  const auth = getAuth();

  type Tab = 'users' | 'permission-sets';
  let activeTab = $state<Tab>('users');

  let users = $state<FullUser[]>([]);
  let permissionSets = $state<PermissionSet[]>([]);
  let loading = $state(true);
  let showCreate = $state(false);
  let error = $state<string | null>(null);

  let formEmail = $state('');
  let formName = $state('');
  let formPermissionSetId = $state('');
  let submitting = $state(false);

  const canManage = $derived(auth.hasPermission('Concord.Admin.Users.Manage'));

  const tabs: { key: Tab; label: string }[] = [
    { key: 'users', label: 'Users' },
    { key: 'permission-sets', label: 'Permission Sets' },
  ];

  async function fetchUsers(): Promise<void> {
    try {
      const data = await apiFetch<ApiResponse<FullUser[]>>('/v2/users');
      users = data.data;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load users';
    } finally {
      loading = false;
    }
  }

  async function fetchPermissionSets(): Promise<void> {
    try {
      const data = await apiFetch<ApiResponse<PermissionSet[]>>('/v2/permissions');
      permissionSets = data.data;
      // Set default selection
      if (data.data.length > 0 && !formPermissionSetId) {
        const viewerSet = data.data.find((s) => s.name === 'Viewer');
        formPermissionSetId = viewerSet?.id || data.data[0].id;
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load permission sets';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Users.View')) {
      goto('/');
      return;
    }
    fetchUsers();
    fetchPermissionSets();
  });

  async function handleCreate(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;
    try {
      await api.post('/v2/users', {
        email: formEmail,
        name: formName,
        permissionSetId: formPermissionSetId || null,
      });
      formEmail = '';
      formName = '';
      const viewerSet = permissionSets.find((s) => s.name === 'Viewer');
      formPermissionSetId = viewerSet?.id || permissionSets[0]?.id || '';
      showCreate = false;
      fetchUsers();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create user';
    } finally {
      submitting = false;
    }
  }

  async function handleToggleActive(userId: string, currentActive: boolean): Promise<void> {
    try {
      await api.put(`/v2/users/${userId}`, { active: !currentActive });
      fetchUsers();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update user';
    }
  }

  async function handlePermissionSetChange(userId: string): Promise<void> {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    try {
      await api.put(`/v2/users/${userId}`, { permissionSetId: user.permissionSetId || null });
      fetchUsers();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update permission set';
    }
  }
</script>

<svelte:head>
  <title>Users — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Users"
      description="Manage users and permission sets."
    >
      {#snippet actions()}
        {#if activeTab === 'users' && canManage}
          <button
            onclick={() => (showCreate = !showCreate)}
            class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover"
          >
            {#if showCreate}
              <X size={16} />
              Cancel
            {:else}
              <UserPlus size={16} />
              Add user
            {/if}
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  <!-- Tabs -->
  <div class="mb-6 flex gap-1 border-b border-border">
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

  {#if activeTab === 'users'}
    <ErrorAlert message={error} />

    <!-- Create form -->
    {#if showCreate && canManage}
      <form
        onsubmit={handleCreate}
        class="mb-6 card card-sm"
      >
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">
              Email
            </span>
            <input
              type="email"
              required
              bind:value={formEmail}
              placeholder="user@company.com"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>
          <label>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">
              Name
            </span>
            <input
              type="text"
              required
              bind:value={formName}
              placeholder="Full name"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>
          <div>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">
              Permission Set
            </span>
            <div class="flex gap-2">
              <Select
                bind:value={formPermissionSetId}
                class="flex-1"
                placeholder="None"
                options={permissionSets.map(ps => ({ value: ps.id, label: ps.name }))}
              />
              <button
                type="submit"
                disabled={submitting}
                class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover disabled:opacity-50"
              >
                {#if submitting}
                  ...
                {:else}
                  <Check size={16} />
                {/if}
              </button>
            </div>
          </div>
        </div>
      </form>
    {/if}

    <!-- Users table -->
    {#if loading}
      <LoadingState message="Loading users..." />
    {:else}
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">User</th>
              <th class="table-header">Permission Set</th>
              <th class="table-header">Status</th>
              <th class="table-header">Last seen</th>
              <th class="table-header text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each users as u (u.id)}
              {@const isSelf = u.id === auth.user?.id}
              <tr class="table-row table-row-interactive">
                <td class="table-cell">
                  <div class="font-medium text-text-primary">
                    {u.name}
                    {#if isSelf}
                      <span class="ml-2 text-2xs text-text-tertiary">(you)</span>
                    {/if}
                  </div>
                  <div class="text-2xs text-text-tertiary">{u.email}</div>
                </td>
                <td class="table-cell">
                  {#if isSelf || !canManage}
                    <span class="text-text-secondary">{u.permissionSetName || 'None'}</span>
                  {:else}
                    <Select
                      compact
                      bind:value={u.permissionSetId}
                      placeholder="None"
                      options={permissionSets.map(ps => ({ value: ps.id, label: ps.name }))}
                      onchange={() => handlePermissionSetChange(u.id)}
                    />
                  {/if}
                </td>
                <td class="table-cell">
                  <span class="badge {u.active ? 'badge-success' : 'badge-error'}">
                    {u.active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td class="table-cell text-text-secondary">
                  {formatDate(u.lastSeenAt)}
                </td>
                <td class="table-cell text-right">
                  {#if !isSelf && canManage}
                    <button
                      onclick={() => handleToggleActive(u.id, u.active)}
                      class="btn btn-sm btn-ghost {u.active ? 'text-error' : 'text-success'}"
                    >
                      {u.active ? 'Deactivate' : 'Activate'}
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}

  {#if activeTab === 'permission-sets'}
    <PermissionSetsTab />
  {/if}
</div>
