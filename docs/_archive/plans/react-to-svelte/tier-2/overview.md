# Tier 2 — Core Pages

## Goal

Port the core admin pages: Dashboard, Users, Permission Sets, History, Guides, and the full Settings modal. By the end of Tier 2, all basic admin functionality is operational.

---

## Architecture

### New Routes

```
src/routes/
├── +page.svelte                    # Dashboard (already exists)
├── users/+page.svelte              # Users management
├── permission-sets/+page.svelte    # Permission sets management
├── history/+page.svelte            # Audit log viewer
├── guides/+page.svelte             # Documentation guides
```

### New Components

```
src/lib/components/
└── settings/
    ├── settings-modal.svelte       # Full settings modal
    └── sections/
        ├── api-keys-section.svelte
        ├── permissions-section.svelte
        └── system-section.svelte
```

---

## Components

| React Component | Svelte Target | Notes |
|-----------------|---------------|-------|
| `pages/dashboard.tsx` | `routes/+page.svelte` | Basic dashboard |
| `pages/users.tsx` | `routes/users/+page.svelte` | User CRUD |
| `pages/permission-sets.tsx` | `routes/permission-sets/+page.svelte` | Permission set CRUD |
| `pages/history/history-page.tsx` | `routes/history/+page.svelte` | Audit log viewer |
| `pages/guides/guides-page.tsx` | `routes/guides/+page.svelte` | Guides placeholder |
| `settings/settings-modal.tsx` | `lib/components/settings/settings-modal.svelte` | Full settings |
| `settings/sections/api-keys-section.tsx` | `lib/components/settings/sections/api-keys-section.svelte` | API key management |
| `settings/sections/permissions-section.tsx` | `lib/components/settings/sections/permissions-section.svelte` | My permissions |
| `settings/sections/system-section.tsx` | `lib/components/settings/sections/system-section.svelte` | System info |

---

## Phase Checklist

- [ ] Phase 1 — Dashboard page
- [ ] Phase 2 — Users and Permission Sets pages
- [ ] Phase 3 — History page
- [ ] Phase 4 — Settings modal (full) and Guides page

---

## Key Patterns

### CRUD Page Pattern

Each CRUD page follows the same pattern:

```svelte
<script lang="ts">
  import { goto } from '$app/navigation';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Entity } from '$lib/types/models';
  import { PageHeader, ErrorAlert, LoadingState, EmptyState, ConfirmDeleteDialog } from '$lib/components/ui';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.Module.Manage'));

  // Check permission
  if (!auth.hasPermission('Concord.Admin.Module.View')) {
    goto('/');
  }

  // Data state
  let items = $state<Entity[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Form state
  let showForm = $state(false);
  let editingId = $state<string | null>(null);
  let formField = $state('');
  let submitting = $state(false);

  // Delete state
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  // Fetch
  async function fetchItems(): Promise<void> {
    try {
      const res = await api<ApiResponse<Entity[]>>('/v2/module');
      items = res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load';
    } finally {
      loading = false;
    }
  }

  // Init
  $effect(() => {
    fetchItems();
  });

  // Reset form
  function resetForm(): void {
    formField = '';
    editingId = null;
    showForm = false;
  }

  // Submit
  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    submitting = true;
    error = null;

    try {
      if (editingId) {
        await api(`/v2/module/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify({ field: formField })
        });
      } else {
        await api('/v2/module', {
          method: 'POST',
          body: JSON.stringify({ field: formField })
        });
      }
      resetForm();
      await fetchItems();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      submitting = false;
    }
  }

  // Delete
  async function handleDelete(id: string): Promise<void> {
    try {
      await api(`/v2/module/${id}`, { method: 'DELETE' });
      await fetchItems();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete';
    }
  }
</script>

{#if loading}
  <LoadingState message="Loading..." />
{:else}
  <div class="animate-fade-in">
    <PageHeader title="Module" description="Manage module." />
    <ErrorAlert message={error} />
    <!-- Form, list, etc. -->
  </div>
{/if}

<ConfirmDeleteDialog
  open={!!deleteTarget}
  entityType="item"
  entityName={deleteTarget?.name ?? ''}
  onConfirm={() => {
    if (deleteTarget) handleDelete(deleteTarget.id);
    deleteTarget = null;
  }}
  onCancel={() => (deleteTarget = null)}
/>
```

---

## Verification

After Tier 2:
1. Dashboard shows user info
2. Users page shows user list with CRUD operations
3. Permission Sets page shows permission set list with CRUD
4. History page shows audit log entries with search
5. Guides page renders placeholder content
6. Settings modal has all sections (Theme, API Keys, Permissions)
7. Visual parity with React app verified
