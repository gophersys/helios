# Tier 3 — Domain Features

## Goal

Port the domain-specific feature pages: Products (with sub-entities), Codebases (with releases and artifacts), and Inventory (components, assemblies, BOM editor). These are the most complex pages with nested CRUD operations.

---

## Architecture

### New Routes

```
src/routes/
├── products/
│   └── +page.svelte               # Products list with inline detail
├── codebases/
│   └── +page.svelte               # Codebases list with inline detail
└── inventory/
    └── +page.svelte               # Inventory catalog (tabs: Components, Assemblies)
```

### New Components

```
src/lib/components/
├── products/
│   ├── product-card.svelte
│   ├── product-detail.svelte
│   ├── board-revision-list.svelte
│   ├── firmware-app-list.svelte
│   ├── firmware-build-list.svelte
│   └── firmware-build-upload.svelte
├── codebases/
│   ├── codebase-card.svelte
│   ├── codebase-detail.svelte
│   ├── release-form.svelte
│   ├── artifact-list.svelte
│   └── artifact-upload.svelte
└── inventory/
    ├── components-tab.svelte
    ├── component-card.svelte
    ├── assemblies-tab.svelte
    ├── assembly-card.svelte
    ├── bom-editor.svelte
    └── image-upload.svelte
```

### Utilities

```
src/lib/utils/
├── fetch-data.svelte.ts           # Reactive data fetching hook
└── chipset-config.svelte.ts       # Chipset configuration hook
```

---

## Components

| React Component | Svelte Target | Notes |
|-----------------|---------------|-------|
| **Products** |||
| `products-page.tsx` | `routes/products/+page.svelte` | List + detail |
| `product-card.tsx` | `lib/components/products/product-card.svelte` | Card component |
| `product-detail.tsx` | `lib/components/products/product-detail.svelte` | Tab-based detail |
| `board-revision-list.tsx` | `lib/components/products/board-revision-list.svelte` | Sub-entity list |
| `firmware-app-list.tsx` | `lib/components/products/firmware-app-list.svelte` | Sub-entity list |
| `firmware-build-list.tsx` | `lib/components/products/firmware-build-list.svelte` | Sub-entity list |
| `firmware-build-upload.tsx` | `lib/components/products/firmware-build-upload.svelte` | File upload |
| **Codebases** |||
| `codebases-page.tsx` | `routes/codebases/+page.svelte` | List + detail |
| `codebase-card.tsx` | `lib/components/codebases/codebase-card.svelte` | Card component |
| `codebase-detail.tsx` | `lib/components/codebases/codebase-detail.svelte` | Tab-based detail |
| `release-form.tsx` | `lib/components/codebases/release-form.svelte` | Release CRUD |
| `artifact-list.tsx` | `lib/components/codebases/artifact-list.svelte` | Artifact list |
| `artifact-upload.tsx` | `lib/components/codebases/artifact-upload.svelte` | File upload |
| **Inventory** |||
| `inventory-catalog.tsx` | `routes/inventory/+page.svelte` | Tabbed catalog |
| `components-tab.tsx` | `lib/components/inventory/components-tab.svelte` | Component list |
| `component-card.tsx` | `lib/components/inventory/component-card.svelte` | Card component |
| `assemblies-tab.tsx` | `lib/components/inventory/assemblies-tab.svelte` | Assembly list |
| `assembly-card.tsx` | `lib/components/inventory/assembly-card.svelte` | Card component |
| `bom-editor.tsx` | `lib/components/inventory/bom-editor.svelte` | BOM editing |
| `image-upload.tsx` | `lib/components/inventory/image-upload.svelte` | Image upload |
| **Hooks** |||
| `use-fetch-data.ts` | `lib/utils/fetch-data.svelte.ts` | Reactive fetcher |
| `use-chipset-config.ts` | `lib/utils/chipset-config.svelte.ts` | Chipset config |

---

## Phase Checklist

- [ ] Phase 1 — Products list page and card
- [ ] Phase 2 — Product detail and sub-entities
- [ ] Phase 3 — Codebases list and card
- [ ] Phase 4 — Codebase detail, releases, artifacts
- [ ] Phase 5 — Inventory catalog and tabs
- [ ] Phase 6 — Inventory cards, BOM editor, image upload

---

## Key Patterns

### Reactive Data Fetcher

Replace `useFetchData` hook with a Svelte 5 runes-based utility:

```typescript
// lib/utils/fetch-data.svelte.ts
import { api } from '$lib/api';
import type { ApiResponse } from '$lib/types';

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function createFetchData<T>(url: string | null, pollInterval?: number) {
  let state = $state<FetchState<T>>({
    data: null,
    loading: true,
    error: null
  });

  async function fetchData(): Promise<void> {
    if (!url) return;
    try {
      const res = await api<ApiResponse<T>>(url);
      state.data = res.data;
      state.error = null;
    } catch (err) {
      state.error = err instanceof Error ? err.message : 'Request failed';
    } finally {
      state.loading = false;
    }
  }

  $effect(() => {
    fetchData();

    if (pollInterval && pollInterval > 0) {
      const interval = setInterval(fetchData, pollInterval);
      return () => clearInterval(interval);
    }
  });

  return {
    get data() { return state.data; },
    get loading() { return state.loading; },
    get error() { return state.error; },
    refetch: fetchData
  };
}
```

### Tab-Based Detail View

```svelte
<script lang="ts">
  let activeTab = $state<'overview' | 'revisions' | 'firmware'>('overview');
</script>

<div class="border-b border-border">
  <nav class="-mb-px flex gap-6">
    <button
      onclick={() => (activeTab = 'overview')}
      class="border-b-2 px-1 py-3 text-sm font-medium transition-colors"
      class:border-accent={activeTab === 'overview'}
      class:text-accent={activeTab === 'overview'}
      class:border-transparent={activeTab !== 'overview'}
      class:text-text-secondary={activeTab !== 'overview'}
      class:hover:text-text-primary={activeTab !== 'overview'}
    >
      Overview
    </button>
    <!-- More tabs -->
  </nav>
</div>

{#if activeTab === 'overview'}
  <div>Overview content</div>
{:else if activeTab === 'revisions'}
  <div>Revisions content</div>
{:else if activeTab === 'firmware'}
  <div>Firmware content</div>
{/if}
```

### File Upload Pattern

```svelte
<script lang="ts">
  import { apiUpload } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  let { onUploadComplete }: { onUploadComplete: () => void } = $props();

  let uploading = $state(false);
  let error = $state<string | null>(null);

  async function handleFileChange(e: Event): Promise<void> {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    uploading = true;
    error = null;

    const formData = new FormData();
    formData.append('file', file);

    try {
      await apiUpload<ApiResponse<unknown>>('/v2/upload', formData);
      onUploadComplete();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Upload failed';
    } finally {
      uploading = false;
      input.value = '';
    }
  }
</script>

<input
  type="file"
  onchange={handleFileChange}
  disabled={uploading}
  class="..."
/>
```

---

## Verification

After Tier 3:
1. Products page shows product cards
2. Product detail shows tabs (Overview, Board Revisions, Firmware Apps, Builds)
3. Board revisions CRUD works
4. Firmware apps CRUD works
5. Firmware builds list and upload work
6. Codebases page shows codebase cards
7. Codebase detail shows releases and artifacts
8. Release and artifact CRUD works
9. Inventory catalog has Components and Assemblies tabs
10. Component and assembly CRUD works
11. BOM editor functions correctly
12. Image upload works for all entities
13. Visual parity with React app verified
