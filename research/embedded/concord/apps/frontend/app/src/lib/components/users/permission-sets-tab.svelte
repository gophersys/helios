<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Plus,
    X,
    Pencil,
    Trash2,
    Check,
    ChevronRight,
    ChevronDown,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { AvailablePermission, PermissionSet, TreeNode } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import { actionable } from '$lib/actions/actionable';

  const auth = getAuth();

  // ── Action color mapping ──────────────────────────────────────

  const ACTION_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
    Create: { bg: 'bg-success-muted', text: 'text-success', dot: 'bg-success' },
    View: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
    Read: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
    Update: { bg: 'bg-warning-muted', text: 'text-warning', dot: 'bg-warning' },
    Delete: { bg: 'bg-error-muted', text: 'text-error', dot: 'bg-error' },
    Manage: { bg: 'bg-accent-muted', text: 'text-accent', dot: 'bg-accent' },
    Run: { bg: 'bg-accent-muted', text: 'text-accent', dot: 'bg-accent' },
  };

  const DEFAULT_COLOR = { bg: 'bg-surface-2', text: 'text-text-secondary', dot: 'bg-text-tertiary' };

  function getActionColor(action: string) {
    return ACTION_COLORS[action] || DEFAULT_COLOR;
  }

  // ── Tree data structure ───────────────────────────────────────

  function buildTree(permissions: AvailablePermission[]): TreeNode[] {
    const root: TreeNode = { label: 'root', children: [] };

    for (const p of permissions) {
      const parts = p.key.split('.');
      const segments = parts.slice(1); // Skip "Concord" prefix

      let current = root;
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        const isLeaf = i === segments.length - 1;

        let child = current.children.find((c) => c.label === seg);
        if (!child) {
          child = {
            label: seg,
            children: [],
            // For leaves, permKey is the original "module:action" string (stored in p.name)
            // so it matches the format used in PermissionSet.permissions
            ...(isLeaf ? { permKey: p.name } : {}),
          };
          current.children.push(child);
        }
        if (isLeaf) {
          child.permKey = p.name;
        }
        current = child;
      }
    }

    return root.children;
  }

  function collectKeys(node: TreeNode): string[] {
    if (node.permKey) return [node.permKey];
    return node.children.flatMap(collectKeys);
  }

  // ── State ─────────────────────────────────────────────────────

  let sets = $state<PermissionSet[]>([]);
  let availablePerms = $state<AvailablePermission[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formName = $state('');
  let formDescription = $state('');
  let formPermissions = $state<Set<string>>(new Set());
  let submitting = $state(false);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  const canManage = $derived(auth.hasPermission('permissions:manage'));
  const tree = $derived(buildTree(availablePerms));

  async function fetchSets(): Promise<void> {
    try {
      const data = await apiFetch<ApiResponse<{ data: PermissionSet[]; pagination: unknown }>>('/v2/permissions');
      // Permissions endpoint returns paginated response: { data: [...], pagination: {...} }
      const payload = data.data;
      sets = Array.isArray(payload) ? payload : (payload as any).data ?? [];
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load permission sets';
    } finally {
      loading = false;
    }
  }

  async function fetchPermissions(): Promise<void> {
    try {
      const data = await apiFetch<ApiResponse<unknown>>('/v2/permissions/available');
      // The API returns { permissions: string[], registry: { group: entries[] } }.
      // Transform registry entries into AvailablePermission[] for the tree builder.
      // The tree builder splits key on '.' and skips the first segment ("Concord").
      // Permission sets store permissions as "module:action" strings, so the leaf
      // permKey (set to p.key by buildTree) must use the same format.
      const payload = data.data as Record<string, unknown>;
      const registry = (payload?.registry ?? {}) as Record<string, Array<{ permission: string; label: string }>>;
      const mapped: AvailablePermission[] = [];
      for (const [group, entries] of Object.entries(registry)) {
        if (!Array.isArray(entries)) continue;
        for (const entry of entries) {
          if (!entry?.permission) continue;
          // key: dotted path for buildTree to create the tree structure
          //   "Concord.<Group>.<ActionLabel>" — buildTree skips "Concord"
          // name: the original "module:action" string — used as permKey in leaf nodes
          //   so it matches the format stored in PermissionSet.permissions
          mapped.push({
            key: `Concord.${group}.${entry.label}`,
            name: entry.permission,
          });
        }
      }
      availablePerms = mapped;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load permissions';
    }
  }

  onMount(() => {
    fetchSets();
    fetchPermissions();
  });

  function resetForm(): void {
    formName = '';
    formDescription = '';
    formPermissions = new Set();
    editingId = null;
    showForm = false;
  }

  function startEdit(ps: PermissionSet): void {
    formName = ps.name;
    formDescription = ps.description || '';
    formPermissions = new Set(ps.permissions);
    editingId = ps.id;
    showForm = true;
  }

  function togglePermission(key: string): void {
    const next = new Set(formPermissions);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    formPermissions = next;
  }

  function toggleAll(keys: string[], selected: boolean): void {
    const next = new Set(formPermissions);
    for (const k of keys) {
      if (selected) next.add(k);
      else next.delete(k);
    }
    formPermissions = next;
  }

  async function handleSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      name: formName,
      description: formDescription || null,
      permissions: Array.from(formPermissions),
    };

    try {
      if (editingId) {
        await api.put(`/v2/permissions/${editingId}`, body);
      } else {
        await api.post('/v2/permissions', body);
      }
      resetForm();
      fetchSets();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save permission set';
    } finally {
      submitting = false;
    }
  }

  async function handleDelete(id: string): Promise<void> {
    error = null;
    try {
      await api.delete(`/v2/permissions/${id}`);
      fetchSets();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to delete permission set';
    }
  }

  function promptDelete(id: string): void {
    const target = sets.find((s) => s.id === id);
    deleteTarget = { id, name: target?.name || '' };
  }
</script>

<!-- Tree Checkbox Node (for form) -->
{#snippet TreeCheckboxNode(node: TreeNode, selectedPerms: Set<string>, depth: number)}
  {@const isLeaf = !!node.permKey}
  {@const allKeys = collectKeys(node)}
  {@const checkedCount = allKeys.filter((k) => selectedPerms.has(k)).length}
  {@const allChecked = checkedCount === allKeys.length}
  {@const someChecked = checkedCount > 0 && !allChecked}

  {#if isLeaf}
    {@const color = getActionColor(node.label)}
    <label
      class="flex items-center gap-2.5 py-0.5 cursor-pointer group"
      style:padding-left="{depth * 20}px"
    >
      <input
        type="checkbox"
        checked={selectedPerms.has(node.permKey!)}
        onchange={() => togglePermission(node.permKey!)}
        class="rounded border-border text-accent focus:ring-accent"
      />
      <span
        class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-medium transition-opacity {color.bg} {color.text}"
        class:opacity-100={selectedPerms.has(node.permKey!)}
        class:opacity-50={!selectedPerms.has(node.permKey!)}
      >
        <span class="h-1.5 w-1.5 rounded-full {color.dot}"></span>
        {node.label}
      </span>
    </label>
  {:else}
    {@const expanded = true}
    <div>
      <div
        class="flex items-center gap-1 py-1 cursor-pointer select-none"
        style:padding-left="{depth * 20}px"
      >
        <div class="flex h-5 w-5 items-center justify-center rounded text-text-tertiary">
          <ChevronDown size={16} strokeWidth={2} />
        </div>
        <input
          type="checkbox"
          checked={allChecked}
          indeterminate={someChecked}
          onchange={() => toggleAll(allKeys, !allChecked)}
          class="rounded border-border text-accent focus:ring-accent"
        />
        <span class="text-xs font-semibold text-text-primary">
          {node.label}
        </span>
        <span class="text-2xs text-text-tertiary ml-1">
          {checkedCount}/{allKeys.length}
        </span>
      </div>
      {#if expanded}
        <div>
          {#each node.children as child}
            {@render TreeCheckboxNode(child, selectedPerms, depth + 1)}
          {/each}
        </div>
      {/if}
    </div>
  {/if}
{/snippet}

<!-- Tree Display Node (read-only) -->
{#snippet TreeDisplayNode(node: TreeNode, enabledPerms: Set<string>, depth: number)}
  {@const isLeaf = !!node.permKey}

  {#if isLeaf}
    {@const enabled = enabledPerms.has(node.permKey!)}
    {@const color = getActionColor(node.label)}
    <span
      class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-medium"
      class:text-text-tertiary={!enabled}
      class:line-through={!enabled}
      class:opacity-40={!enabled}
      class:bg-transparent={!enabled}
      class:bg-success-muted={enabled && color.bg === 'bg-success-muted'}
      class:bg-info-muted={enabled && color.bg === 'bg-info-muted'}
      class:bg-warning-muted={enabled && color.bg === 'bg-warning-muted'}
      class:bg-error-muted={enabled && color.bg === 'bg-error-muted'}
      class:bg-accent-muted={enabled && color.bg === 'bg-accent-muted'}
      class:bg-surface-2={enabled && color.bg === 'bg-surface-2'}
      class:text-success={enabled && color.text === 'text-success'}
      class:text-info={enabled && color.text === 'text-info'}
      class:text-warning={enabled && color.text === 'text-warning'}
      class:text-error={enabled && color.text === 'text-error'}
      class:text-accent={enabled && color.text === 'text-accent'}
      class:text-text-secondary={enabled && color.text === 'text-text-secondary'}
    >
      <span
        class="h-1.5 w-1.5 rounded-full"
        class:bg-text-tertiary={!enabled || color.dot === 'bg-text-tertiary'}
        class:bg-success={enabled && color.dot === 'bg-success'}
        class:bg-info={enabled && color.dot === 'bg-info'}
        class:bg-warning={enabled && color.dot === 'bg-warning'}
        class:bg-error={enabled && color.dot === 'bg-error'}
        class:bg-accent={enabled && color.dot === 'bg-accent'}
      ></span>
      {node.label}
    </span>
  {:else}
    {@const childKeys = collectKeys(node)}
    {@const enabledCount = childKeys.filter((k) => enabledPerms.has(k)).length}
    {@const leafChildren = node.children.filter((c) => c.permKey)}
    {@const branchChildren = node.children.filter((c) => !c.permKey)}

    <div style:padding-left={depth > 0 ? '16px' : '0'}>
      <div class="flex items-center gap-2 py-1">
        <span
          class="text-2xs font-semibold"
          class:text-text-primary={enabledCount > 0}
          class:text-text-tertiary={enabledCount === 0}
          class:opacity-60={enabledCount === 0}
        >
          {node.label}
        </span>
        {#if leafChildren.length > 0}
          <div class="flex flex-wrap gap-1">
            {#each leafChildren as child}
              {@render TreeDisplayNode(child, enabledPerms, 0)}
            {/each}
          </div>
        {/if}
      </div>
      {#each branchChildren as child}
        {@render TreeDisplayNode(child, enabledPerms, depth + 1)}
      {/each}
    </div>
  {/if}
{/snippet}

<!-- Permission Set Card -->
{#snippet PermissionSetCard(ps: PermissionSet)}
  {@const enabledPerms = new Set(ps.permissions)}
  {@const allKeys = tree.flatMap(collectKeys)}
  {@const totalCount = allKeys.length}
  {@const users = ps.users ?? []}

  <div class="card">
    <!-- Header row -->
    <div class="flex w-full items-center gap-3 px-4 py-3.5">
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="flex flex-1 items-center gap-3 cursor-pointer"
        onclick={() => {
          const el = document.getElementById(`ps-${ps.id}`);
          if (el) el.classList.toggle('hidden');
        }}
      >
        <div class="flex h-5 w-5 shrink-0 items-center justify-center text-text-tertiary">
          <ChevronRight size={16} strokeWidth={2} class="transition-transform" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-semibold text-text-primary">{ps.name}</h4>
            <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
              {ps.permissions.length}/{totalCount}
            </span>
          </div>
          {#if ps.description}
            <p class="mt-0.5 text-2xs text-text-tertiary">{ps.description}</p>
          {/if}
        </div>
        <div class="flex shrink-0 items-center gap-3">
          {#if users.length > 0}
            <div class="flex items-center gap-1.5">
              <div class="flex -space-x-1.5">
                {#each users.slice(0, 5) as u}
                  <div
                    title="{u.name} ({u.email})"
                    class="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface-1 bg-accent-muted text-2xs font-semibold text-accent"
                  >
                    {u.name.charAt(0).toUpperCase()}
                  </div>
                {/each}
                {#if users.length > 5}
                  <div class="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface-1 bg-surface-2 text-2xs font-medium text-text-tertiary">
                    +{users.length - 5}
                  </div>
                {/if}
              </div>
              <span class="text-2xs text-text-tertiary">
                {ps.userCount ?? 0} user{(ps.userCount ?? 0) !== 1 ? 's' : ''}
              </span>
            </div>
          {:else}
            <span class="text-2xs text-text-tertiary">No users</span>
          {/if}
        </div>
      </div>
      {#if canManage}
        <div class="flex items-center gap-1">
          <button
            onclick={() => startEdit(ps)}
            class="rounded-lg p-2 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
            title="Edit"
            aria-label="Edit"
          >
            <Pencil size={16} />
          </button>
          <button
            onclick={() => promptDelete(ps.id)}
            class="rounded-lg p-2 text-text-tertiary transition-colors hover:bg-error-muted hover:text-error"
            title="Delete"
            aria-label="Delete"
          >
            <Trash2 size={16} />
          </button>
        </div>
      {/if}
    </div>

    <!-- Collapsible body -->
    <div id="ps-{ps.id}" class="hidden border-t border-border-subtle">
      {#if users.length > 0}
        <div class="border-b border-border-subtle px-4 py-3">
          <div class="mb-2 text-2xs font-medium text-text-tertiary">Assigned users</div>
          <div class="flex flex-wrap gap-2">
            {#each users as u}
              <div class="flex items-center gap-2 rounded-lg bg-surface-2 px-2.5 py-1.5">
                <div class="flex h-5 w-5 items-center justify-center rounded-full bg-accent-muted text-2xs font-semibold text-accent">
                  {u.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div class="text-2xs font-medium text-text-primary">{u.name}</div>
                  <div class="text-2xs text-text-tertiary">{u.email}</div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="px-4 py-3">
        {#each tree as node}
          {@render TreeDisplayNode(node, enabledPerms, 0)}
        {/each}
      </div>
    </div>
  </div>
{/snippet}

<div>
  <!-- Action bar -->
  {#if canManage && !showForm}
    <div class="mb-4 flex justify-end">
      <button
        use:actionable={{ id: 'create-permission-set', label: 'Create permission set' }}
        onclick={() => {
          resetForm();
          showForm = true;
        }}
        class="btn btn-sm btn-primary"
      >
        <Plus size={16} />
        New set
      </button>
    </div>
  {/if}

  <ErrorAlert message={error} />

  <!-- Create/Edit form -->
  {#if showForm && canManage}
    <div class="mb-6 card card-md">
      <div class="mb-4 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-text-primary">
          {editingId ? 'Edit permission set' : 'New permission set'}
        </h3>
        <button
          onclick={resetForm}
          class="rounded-lg p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
        >
          <X size={16} />
        </button>
      </div>

      <form onsubmit={handleSubmit}>
        <div class="mb-4 grid grid-cols-2 gap-3">
          <label>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
            <input
              type="text"
              required
              bind:value={formName}
              placeholder="e.g. Technician"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
            />
          </label>
          <label>
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
            <input
              type="text"
              bind:value={formDescription}
              placeholder="Optional description"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
            />
          </label>
        </div>

        <div class="mb-4">
          <span class="mb-2 block text-2xs font-medium text-text-tertiary">Permissions</span>
          <div class="rounded-lg border border-border bg-surface-0 p-3 max-h-96 overflow-y-auto">
            {#each tree as node}
              {@render TreeCheckboxNode(node, formPermissions, 0)}
            {/each}
          </div>
        </div>

        <div class="flex gap-2">
          <button
            type="submit"
            disabled={formPermissions.size === 0 || submitting}
            class="btn btn-sm btn-primary"
          >
            <Check size={16} />
            {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
          </button>
          <button
            type="button"
            onclick={resetForm}
            class="btn btn-sm btn-ghost"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  {/if}

  <!-- Permission sets list -->
  {#if loading}
    <LoadingState message="Loading permission sets..." />
  {:else}
    <div class="space-y-3">
      {#each sets as ps (ps.id)}
        {@render PermissionSetCard(ps)}
      {/each}
    </div>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="permission set"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => {
      handleDelete(deleteTarget!.id);
      deleteTarget = null;
    }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
