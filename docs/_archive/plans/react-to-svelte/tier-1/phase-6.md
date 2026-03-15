# Phase 6 — UI Components

## Objective

Port all reusable UI components from the React app. These components are used across multiple pages and must maintain visual parity.

---

## 1. Create `src/lib/components/ui/status-badge.svelte`

```svelte
<script lang="ts">
  const COLORS: Record<string, string> = {
    ACTIVE: 'bg-success-muted text-success',
    DEPRECATED: 'bg-warning-muted text-warning',
    EOL: 'bg-error-muted text-error',
    DRAFT: 'bg-accent-muted text-accent',
    RELEASED: 'bg-success-muted text-success',
    UPLOAD: 'bg-accent-muted text-accent',
    EXTERNAL: 'bg-surface-2 text-text-secondary'
  };

  let { status }: { status: string } = $props();

  const colorClass = $derived(COLORS[status] || 'bg-surface-2 text-text-secondary');
</script>

<span class="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium {colorClass}">
  {status}
</span>
```

---

## 2. Create `src/lib/components/ui/error-alert.svelte`

```svelte
<script lang="ts">
  import { AlertCircle } from 'lucide-svelte';

  let { message }: { message: string | null } = $props();
</script>

{#if message}
  <div class="mb-4 flex items-start gap-3 rounded-lg bg-error-muted px-4 py-3">
    <AlertCircle size={18} class="mt-0.5 shrink-0 text-error" strokeWidth={1.75} />
    <p class="text-sm text-error">{message}</p>
  </div>
{/if}
```

---

## 3. Create `src/lib/components/ui/loading-state.svelte`

```svelte
<script lang="ts">
  let { message = 'Loading...' }: { message?: string } = $props();
</script>

<div class="flex flex-col items-center justify-center py-12">
  <div class="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
  <p class="mt-3 text-sm text-text-tertiary">{message}</p>
</div>
```

---

## 4. Create `src/lib/components/ui/empty-state.svelte`

```svelte
<script lang="ts">
  import { Inbox } from 'lucide-svelte';

  let { message = 'No items found' }: { message?: string } = $props();
</script>

<div class="flex flex-col items-center justify-center rounded-xl border border-border bg-surface-1 py-12">
  <Inbox size={32} class="text-text-tertiary" strokeWidth={1.5} />
  <p class="mt-3 text-sm text-text-tertiary">{message}</p>
</div>
```

---

## 5. Create `src/lib/components/ui/back-button.svelte`

```svelte
<script lang="ts">
  import { ArrowLeft } from 'lucide-svelte';

  let {
    label = 'Back',
    onclick
  }: {
    label?: string;
    onclick: () => void;
  } = $props();
</script>

<button
  {onclick}
  class="mb-4 flex items-center gap-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
>
  <ArrowLeft size={16} strokeWidth={1.75} />
  {label}
</button>
```

---

## 6. Create `src/lib/components/ui/select.svelte`

```svelte
<script lang="ts">
  import { ChevronDown } from 'lucide-svelte';

  interface Option {
    value: string;
    label: string;
  }

  let {
    value = $bindable(''),
    options,
    placeholder = 'Select...',
    compact = false,
    disabled = false
  }: {
    value?: string;
    options: Option[];
    placeholder?: string;
    compact?: boolean;
    disabled?: boolean;
  } = $props();
</script>

<div class="relative">
  <select
    bind:value
    {disabled}
    class="w-full appearance-none rounded-lg border border-border bg-surface-0 pr-8 text-sm text-text-primary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
    class:px-3={!compact}
    class:py-2={!compact}
    class:px-2={compact}
    class:py-1={compact}
  >
    {#if placeholder}
      <option value="" disabled>{placeholder}</option>
    {/if}
    {#each options as option}
      <option value={option.value}>{option.label}</option>
    {/each}
  </select>
  <ChevronDown
    size={16}
    class="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-tertiary"
    strokeWidth={1.75}
  />
</div>
```

---

## 7. Create `src/lib/components/ui/confirm-delete-dialog.svelte`

```svelte
<script lang="ts">
  import { AlertTriangle, X } from 'lucide-svelte';

  let {
    open,
    entityType,
    entityName,
    onConfirm,
    onCancel
  }: {
    open: boolean;
    entityType: string;
    entityName: string;
    onConfirm: () => void;
    onCancel: () => void;
  } = $props();

  let confirmText = $state('');

  const canConfirm = $derived(confirmText === entityName);

  function handleConfirm(): void {
    if (canConfirm) {
      onConfirm();
      confirmText = '';
    }
  }

  function handleCancel(): void {
    confirmText = '';
    onCancel();
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter' && canConfirm) {
      handleConfirm();
    }
  }
</script>

{#if open}
  <!-- Overlay -->
  <div
    class="fixed inset-0 z-50 bg-overlay animate-overlay-in"
    onclick={handleCancel}
    onkeydown={handleKeydown}
    role="button"
    tabindex="-1"
  ></div>

  <!-- Dialog -->
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div
      class="w-full max-w-md animate-modal-in rounded-xl border border-border bg-surface-1 shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <div class="flex items-center justify-between border-b border-border px-5 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error-muted">
            <AlertTriangle size={18} class="text-error" strokeWidth={1.75} />
          </div>
          <h2 id="delete-dialog-title" class="text-sm font-semibold text-text-primary">
            Delete {entityType}
          </h2>
        </div>
        <button
          onclick={handleCancel}
          class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
          title="Cancel"
          aria-label="Cancel deletion"
        >
          <X size={18} strokeWidth={1.75} />
        </button>
      </div>

      <div class="p-5">
        <p class="mb-4 text-sm text-text-secondary">
          This action cannot be undone. This will permanently delete the {entityType}
          <strong class="text-text-primary">{entityName}</strong> and all associated data.
        </p>

        <label class="mb-1 block text-2xs font-medium text-text-tertiary">
          Type <span class="font-mono text-text-primary">{entityName}</span> to confirm
        </label>
        <input
          type="text"
          bind:value={confirmText}
          onkeydown={handleKeydown}
          placeholder={entityName}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          autofocus
        />
      </div>

      <div class="flex justify-end gap-2 border-t border-border px-5 py-4">
        <button
          onclick={handleCancel}
          class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
        <button
          onclick={handleConfirm}
          disabled={!canConfirm}
          class="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
{/if}
```

---

## 8. Create `src/lib/components/ui/error-boundary.svelte`

In Svelte, error boundaries are handled at the route level with `+error.svelte`.

**`src/routes/+error.svelte`:**

```svelte
<script lang="ts">
  import { page } from '$app/stores';
  import { AlertTriangle, RefreshCw } from 'lucide-svelte';

  function handleRetry(): void {
    window.location.reload();
  }
</script>

<div class="flex min-h-screen items-center justify-center bg-surface-0 px-4">
  <div class="w-full max-w-md text-center">
    <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-error-muted">
      <AlertTriangle size={32} class="text-error" strokeWidth={1.5} />
    </div>

    <h1 class="mb-2 text-xl font-semibold text-text-primary">Something went wrong</h1>

    <p class="mb-6 text-sm text-text-secondary">
      {$page.error?.message || 'An unexpected error occurred.'}
    </p>

    <button
      onclick={handleRetry}
      class="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
    >
      <RefreshCw size={16} strokeWidth={1.75} />
      Try again
    </button>
  </div>
</div>
```

---

## 9. Create Index File for Components

**`src/lib/components/ui/index.ts`:**

```typescript
export { default as StatusBadge } from './status-badge.svelte';
export { default as ErrorAlert } from './error-alert.svelte';
export { default as LoadingState } from './loading-state.svelte';
export { default as EmptyState } from './empty-state.svelte';
export { default as BackButton } from './back-button.svelte';
export { default as Select } from './select.svelte';
export { default as ConfirmDeleteDialog } from './confirm-delete-dialog.svelte';
export { default as PageHeader } from './page-header.svelte';
export { default as ThemeToggle } from './theme-toggle.svelte';
```

---

## 10. Update Page Header (if not done in Phase 4)

Ensure `src/lib/components/ui/page-header.svelte` exists with proper implementation:

```svelte
<script lang="ts">
  let {
    title,
    description
  }: {
    title: string;
    description?: string;
  } = $props();
</script>

<div>
  <h1 class="text-xl font-semibold text-text-primary">{title}</h1>
  {#if description}
    <p class="mt-1 text-sm text-text-secondary">{description}</p>
  {/if}
</div>
```

---

## Verification

Test each component in isolation:

1. **StatusBadge**: Create a test page with all status types
2. **ErrorAlert**: Verify it renders when message is set, hidden when null
3. **LoadingState**: Check spinner animation and message
4. **EmptyState**: Verify icon and message render
5. **BackButton**: Click triggers onclick callback
6. **Select**: Options render, value binding works, compact mode works
7. **ConfirmDeleteDialog**: Type-to-confirm works, keyboard shortcuts work
8. **Error Page**: Navigate to invalid route, verify error page renders

Create a test page at `/test-components`:

**`src/routes/test-components/+page.svelte`:**

```svelte
<script lang="ts">
  import {
    StatusBadge,
    ErrorAlert,
    LoadingState,
    EmptyState,
    BackButton,
    Select,
    ConfirmDeleteDialog,
    PageHeader
  } from '$lib/components/ui';

  let selectValue = $state('');
  let deleteOpen = $state(false);

  const selectOptions = [
    { value: 'a', label: 'Option A' },
    { value: 'b', label: 'Option B' },
    { value: 'c', label: 'Option C' }
  ];
</script>

<div class="animate-fade-in space-y-8">
  <PageHeader title="Component Test" description="Testing all UI components." />

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Status Badges</h2>
    <div class="flex flex-wrap gap-2">
      <StatusBadge status="ACTIVE" />
      <StatusBadge status="DEPRECATED" />
      <StatusBadge status="EOL" />
      <StatusBadge status="DRAFT" />
      <StatusBadge status="RELEASED" />
      <StatusBadge status="UPLOAD" />
      <StatusBadge status="EXTERNAL" />
      <StatusBadge status="UNKNOWN" />
    </div>
  </section>

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Error Alert</h2>
    <ErrorAlert message="This is an error message." />
    <ErrorAlert message={null} />
  </section>

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Loading State</h2>
    <LoadingState message="Loading data..." />
  </section>

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Empty State</h2>
    <EmptyState message="No items found" />
  </section>

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Back Button</h2>
    <BackButton label="Go back" onclick={() => alert('Back clicked!')} />
  </section>

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Select</h2>
    <div class="max-w-xs space-y-2">
      <Select bind:value={selectValue} options={selectOptions} placeholder="Choose one..." />
      <Select bind:value={selectValue} options={selectOptions} compact />
    </div>
    <p class="mt-2 text-2xs text-text-tertiary">Selected: {selectValue || 'none'}</p>
  </section>

  <section>
    <h2 class="mb-4 text-sm font-semibold text-text-primary">Confirm Delete Dialog</h2>
    <button
      onclick={() => (deleteOpen = true)}
      class="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error-hover"
    >
      Open Delete Dialog
    </button>
    <ConfirmDeleteDialog
      open={deleteOpen}
      entityType="item"
      entityName="test-item"
      onConfirm={() => {
        alert('Deleted!');
        deleteOpen = false;
      }}
      onCancel={() => (deleteOpen = false)}
    />
  </section>
</div>
```

---

## Files Created

| File | Description |
|------|-------------|
| `src/lib/components/ui/status-badge.svelte` | Colored status pill |
| `src/lib/components/ui/error-alert.svelte` | Error message display |
| `src/lib/components/ui/loading-state.svelte` | Loading spinner with message |
| `src/lib/components/ui/empty-state.svelte` | Empty list placeholder |
| `src/lib/components/ui/back-button.svelte` | Back navigation button |
| `src/lib/components/ui/select.svelte` | Styled select input |
| `src/lib/components/ui/confirm-delete-dialog.svelte` | Type-to-confirm deletion |
| `src/lib/components/ui/index.ts` | Component exports |
| `src/routes/+error.svelte` | Error boundary page |
| `src/routes/test-components/+page.svelte` | Component test page |

---

## Tier 1 Complete

After Phase 6, Tier 1 is complete. The foundation is in place:

- ✅ SvelteKit project with Tailwind and design tokens
- ✅ API client and TypeScript types
- ✅ Auth store and login page
- ✅ Theme store and layout
- ✅ Sidebar with navigation
- ✅ All core UI components

**Next:** Proceed to Tier 2 to implement the core pages (Dashboard, Users, Permission Sets, History, Guides).
