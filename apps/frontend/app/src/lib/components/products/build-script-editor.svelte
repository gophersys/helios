<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Code2, Layers, Braces, Clock, FilePlus, Save, Upload,
    RefreshCw,
  } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import Tabs from '$lib/components/ui/tabs.svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { RecipeVersion, RecipeTemplate } from '$lib/types/models';
  import type { Tab } from '$lib/components/ui/types';

  import EditorSection from './build-script-editor/editor-section.svelte';
  import VariablesSection from './build-script-editor/variables-section.svelte';
  import StageBuildsSection from './build-script-editor/stage-builds-section.svelte';
  import HistorySection from './build-script-editor/history-section.svelte';
  import TemplatesSection from './build-script-editor/templates-section.svelte';

  interface Props {
    open: boolean;
    productId: string;
    productName: string;
    initialContent: string;
    onClose: () => void;
    onSave: (content: string) => void;
  }

  let { open, productId, productName, initialContent, onClose, onSave }: Props = $props();

  // ── Navigation state ────────────────────────────────────────
  const sectionTabs: Tab[] = [
    { id: 'editor', label: 'Editor', icon: Code2 },
    { id: 'stages', label: 'Stage Builds', icon: Layers },
    { id: 'variables', label: 'Variables', icon: Braces },
    { id: 'history', label: 'History', icon: Clock },
    { id: 'templates', label: 'Templates', icon: FilePlus },
  ];

  let activeSection = $state('editor');

  // ── Editor state ────────────────────────────────────────────
  // svelte-ignore state_referenced_locally
  let content = $state(initialContent);
  let saving = $state(false);
  let publishing = $state(false);
  let error = $state<string | null>(null);
  let currentVersion = $state<number | null>(null);

  let isDirty = $derived(content !== initialContent);

  // ── History state ───────────────────────────────────────────
  let versions = $state<RecipeVersion[]>([]);
  let versionsLoading = $state(false);

  // ── Templates state ─────────────────────────────────────────
  let templates = $state<RecipeTemplate[]>([]);
  let templatesLoading = $state(false);

  // Lock body scroll while open
  onMount(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  });

  // ── API methods ─────────────────────────────────────────────
  async function handleSave(): Promise<void> {
    saving = true;
    error = null;
    try {
      await api.put(`/v2/products/${productId}/recipe`, { content });
      onSave(content);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save recipe';
    } finally {
      saving = false;
    }
  }

  async function handlePublish(): Promise<void> {
    publishing = true;
    error = null;
    try {
      await api.post(`/v2/products/${productId}/recipe/publish`, { content });
      onSave(content);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to publish recipe';
    } finally {
      publishing = false;
    }
  }

  async function loadVersions(): Promise<void> {
    if (versions.length > 0) return;
    versionsLoading = true;
    try {
      const res = await api.get<ApiResponse<RecipeVersion[]>>(`/v2/products/${productId}/recipe/versions`);
      versions = res.data ?? [];
      if (versions.length > 0) {
        currentVersion = versions[0].version;
      }
    } catch {
      versions = [];
    } finally {
      versionsLoading = false;
    }
  }

  async function loadTemplates(): Promise<void> {
    if (templates.length > 0) return;
    templatesLoading = true;
    try {
      const res = await api.get<ApiResponse<RecipeTemplate[]>>('/v2/builds/recipe-templates');
      templates = res.data ?? [];
    } catch {
      // Fallback to hardcoded templates
      templates = getDefaultTemplates();
    } finally {
      templatesLoading = false;
    }
  }

  function getDefaultTemplates(): RecipeTemplate[] {
    return [
      {
        id: 'basic',
        name: 'Basic Build',
        description: 'Simple single-processor build with hex collection.',
        category: 'starter',
        content: `#!/bin/bash
set -euo pipefail
source /app/sdk/concord-build.sh
concord_init

# ── Build ──────────────────────────────────────
west build -b $CONCORD_BOARD app/ -- \\
  -DCONFIG_BUILD_VERSION="$CONCORD_VERSION"

# ── Collect artifacts ──────────────────────────
concord_collect_hex app build/zephyr/zephyr.hex

concord_finalize`,
      },
      {
        id: 'dual-processor',
        name: 'Dual Processor',
        description: 'Multi-processor build for app + comms SoCs with CFW generation.',
        category: 'advanced',
        content: `#!/bin/bash
set -euo pipefail
source /app/sdk/concord-build.sh
concord_init

# ── Build app processor ────────────────────────
west build -b $CONCORD_BOARD app/ -d build/app -- \\
  -DCONFIG_BUILD_VERSION="$CONCORD_VERSION"

# ── Build comms processor ──────────────────────
west build -b $CONCORD_BOARD comms/ -d build/comms -- \\
  -DCONFIG_BUILD_VERSION="$CONCORD_VERSION"

# ── Collect hex artifacts ──────────────────────
concord_collect_hex app build/app/zephyr/merged.hex
concord_collect_hex comms build/comms/zephyr/merged.hex

# ── Generate encrypted firmware (CFW) ──────────
concord_collect_cfw app build/app/zephyr/app_update.bin
concord_collect_cfw comms build/comms/zephyr/app_update.bin

concord_finalize`,
      },
      {
        id: 'manufacturing',
        name: 'Manufacturing Build',
        description: 'Manufacturing firmware with shell and test harness enabled.',
        category: 'manufacturing',
        content: `#!/bin/bash
set -euo pipefail
source /app/sdk/concord-build.sh
concord_init

# ── Build with manufacturing overlays ──────────
west build -b $CONCORD_BOARD app/ -- \\
  -DCONFIG_BUILD_VERSION="$CONCORD_VERSION" \\
  -DOVERLAY_CONFIG="overlay-mfg.conf" \\
  -DCONFIG_SHELL=y \\
  -DCONFIG_MANUFACTURING_MODE=y

# ── Collect artifacts ──────────────────────────
concord_collect_hex app build/zephyr/merged.hex

concord_finalize`,
      },
    ];
  }

  // Load data when switching to sections that need it
  $effect(() => {
    if (activeSection === 'history') {
      loadVersions();
    }
    if (activeSection === 'templates') {
      loadTemplates();
    }
  });

  function handleUseTemplate(templateContent: string): void {
    if (isDirty) {
      if (!confirm('You have unsaved changes. Loading a template will overwrite your current content. Continue?')) {
        return;
      }
    }
    content = templateContent;
    activeSection = 'editor';
  }

  function handleLoadVersion(versionContent: string): void {
    content = versionContent;
    activeSection = 'editor';
  }

  function handleClose(): void {
    if (isDirty) {
      if (!confirm('You have unsaved changes. Close anyway?')) return;
    }
    onClose();
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (!open) return;
    // Ctrl/Cmd + S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      if (isDirty && !saving) {
        handleSave();
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<Modal
  {open}
  size="editor"
  noPadding
  onclose={handleClose}
  showCloseButton={false}
  closeOnEscape={!isDirty}
>
  {#snippet header()}
    <div class="flex flex-1 items-center justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <Code2 size={18} class="text-accent shrink-0" />
        <div class="min-w-0">
          <h2 id="modal-title" class="text-sm font-semibold text-text-primary truncate">{productName}</h2>
          <div class="flex items-center gap-2 text-2xs text-text-tertiary">
            <span>Build Recipe Editor</span>
            {#if currentVersion}
              <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono">v{currentVersion}</span>
            {/if}
          </div>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        {#if isDirty}
          <span class="text-2xs text-warning font-medium">Unsaved changes</span>
        {/if}
        {#if error}
          <span class="text-2xs text-error font-medium truncate max-w-[200px]" title={error}>{error}</span>
        {/if}
        <button
          onclick={handleSave}
          disabled={saving || !isDirty}
          class="btn btn-sm btn-secondary"
        >
          {#if saving}
            <RefreshCw size={14} class="animate-spin" />
          {:else}
            <Save size={14} />
          {/if}
          Save
        </button>
        <button
          onclick={handlePublish}
          disabled={publishing || !content}
          class="btn btn-sm btn-primary"
        >
          {#if publishing}
            <RefreshCw size={14} class="animate-spin" />
          {:else}
            <Upload size={14} />
          {/if}
          Publish
        </button>
      </div>
    </div>
  {/snippet}

  <!-- Body: sidebar + content -->
  <div class="flex flex-1 min-h-0 overflow-hidden">
    <!-- Left sidebar (desktop) -->
    <div class="hidden sm:flex w-48 shrink-0 flex-col border-r border-border bg-surface-0">
      <nav class="flex-1 px-2 py-3">
        <Tabs tabs={sectionTabs} bind:activeTab={activeSection} variant="pills" size="sm" />
      </nav>
      <div class="border-t border-border px-3 py-3">
        <div class="text-2xs text-text-tertiary space-y-1">
          <div><kbd class="rounded bg-surface-2 px-1 py-0.5 text-[10px] font-mono">Ctrl+S</kbd> Save</div>
          <div><kbd class="rounded bg-surface-2 px-1 py-0.5 text-[10px] font-mono">Ctrl+F</kbd> Search</div>
          <div><kbd class="rounded bg-surface-2 px-1 py-0.5 text-[10px] font-mono">Esc</kbd> Close</div>
        </div>
      </div>
    </div>

    <!-- Mobile tabs (visible below sm) -->
    <div class="flex sm:hidden border-b border-border bg-surface-0 overflow-x-auto shrink-0 w-full">
      <Tabs tabs={sectionTabs} bind:activeTab={activeSection} variant="underline" size="sm" />
    </div>

    <!-- Content panel -->
    <div class="flex-1 min-w-0 overflow-y-auto">
      {#if activeSection === 'editor'}
        <EditorSection
          bind:content
          {productId}
          readonly={false}
        />
      {:else if activeSection === 'stages'}
        <StageBuildsSection />
      {:else if activeSection === 'variables'}
        <VariablesSection />
      {:else if activeSection === 'history'}
        <HistorySection
          {productId}
          {versions}
          loading={versionsLoading}
          currentContent={content}
          onLoadVersion={handleLoadVersion}
        />
      {:else if activeSection === 'templates'}
        <TemplatesSection
          {templates}
          loading={templatesLoading}
          onUseTemplate={handleUseTemplate}
        />
      {/if}
    </div>
  </div>
</Modal>
