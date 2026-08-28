<script lang="ts">
  import { Clock, ArrowLeftRight, User } from 'lucide-svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { api } from '$lib/api';
  import { formatDate, formatTimeAgo } from '$lib/utils/formatting';
  import type { ApiResponse } from '$lib/types';
  import type { RecipeVersion } from '$lib/types/models';

  interface Props {
    productId: string;
    versions: RecipeVersion[];
    loading: boolean;
    currentContent: string;
    onLoadVersion: (content: string) => void;
  }

  let { productId, versions, loading, currentContent, onLoadVersion }: Props = $props();

  let selectedVersion = $state<RecipeVersion | null>(null);
  let selectedContent = $state<string | null>(null);
  let loadingContent = $state(false);
  let showDiff = $state(false);

  async function handleViewVersion(version: RecipeVersion): Promise<void> {
    selectedVersion = version;
    showDiff = false;

    if (version.content) {
      selectedContent = version.content;
      return;
    }

    loadingContent = true;
    try {
      const res = await api.get<ApiResponse<RecipeVersion>>(
        `/v2/products/${productId}/recipe/versions/${version.id}`
      );
      selectedContent = res.data?.content ?? '';
    } catch {
      selectedContent = '# Failed to load version content';
    } finally {
      loadingContent = false;
    }
  }

  function handleCompare(): void {
    showDiff = !showDiff;
  }

  function handleRestore(): void {
    if (selectedContent !== null) {
      if (confirm('Load this version into the editor? Your current changes will be replaced.')) {
        onLoadVersion(selectedContent);
      }
    }
  }

  // Simple line-by-line diff for display
  function computeDiff(oldText: string, newText: string): { type: 'same' | 'add' | 'remove'; text: string }[] {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    const result: { type: 'same' | 'add' | 'remove'; text: string }[] = [];

    let oi = 0;
    let ni = 0;

    while (oi < oldLines.length || ni < newLines.length) {
      if (oi >= oldLines.length) {
        result.push({ type: 'add', text: newLines[ni] });
        ni++;
      } else if (ni >= newLines.length) {
        result.push({ type: 'remove', text: oldLines[oi] });
        oi++;
      } else if (oldLines[oi] === newLines[ni]) {
        result.push({ type: 'same', text: oldLines[oi] });
        oi++;
        ni++;
      } else {
        // Simple heuristic: check if the old line appears further in new
        const newIdx = newLines.indexOf(oldLines[oi], ni + 1);
        const oldIdx = oldLines.indexOf(newLines[ni], oi + 1);

        if (newIdx !== -1 && (oldIdx === -1 || newIdx - ni < oldIdx - oi)) {
          while (ni < newIdx) {
            result.push({ type: 'add', text: newLines[ni] });
            ni++;
          }
        } else if (oldIdx !== -1) {
          while (oi < oldIdx) {
            result.push({ type: 'remove', text: oldLines[oi] });
            oi++;
          }
        } else {
          result.push({ type: 'remove', text: oldLines[oi] });
          result.push({ type: 'add', text: newLines[ni] });
          oi++;
          ni++;
        }
      }
    }

    return result;
  }
</script>

<div class="flex h-full min-h-0">
  <!-- Version list -->
  <div class="w-72 shrink-0 border-r border-border overflow-y-auto">
    <div class="p-4 border-b border-border">
      <h3 class="text-sm font-semibold text-text-primary">Version History</h3>
      <p class="mt-1 text-2xs text-text-tertiary">
        Previous versions of the build recipe.
      </p>
    </div>

    {#if loading}
      <div class="p-4 text-center text-sm text-text-tertiary">Loading versions...</div>
    {:else if versions.length === 0}
      <div class="p-4 text-center">
        <Clock size={24} class="mx-auto mb-2 text-text-tertiary opacity-40" />
        <p class="text-sm text-text-tertiary">No versions yet.</p>
        <p class="mt-1 text-2xs text-text-tertiary">Save and publish your recipe to create the first version.</p>
      </div>
    {:else}
      <div class="divide-y divide-border-subtle">
        {#each versions as version}
          {@const isSelected = selectedVersion?.id === version.id}
          <button
            onclick={() => handleViewVersion(version)}
            class="w-full text-left px-4 py-3 transition-colors {isSelected
              ? 'bg-accent/5 border-l-2 border-l-accent'
              : 'hover:bg-surface-2 border-l-2 border-l-transparent'}"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-text-primary">v{version.version}</span>
              <StatusBadge status={version.status.toUpperCase()} />
            </div>
            {#if version.changeNote}
              <p class="mt-1 text-2xs text-text-secondary line-clamp-2">{version.changeNote}</p>
            {/if}
            <div class="mt-1.5 flex items-center gap-2 text-[10px] text-text-tertiary">
              {#if version.createdBy}
                <span class="flex items-center gap-1">
                  <User size={10} />
                  {version.createdBy.name}
                </span>
              {/if}
              <span>{formatTimeAgo(version.createdAt)}</span>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Version content / diff viewer -->
  <div class="flex-1 min-w-0 flex flex-col">
    {#if selectedVersion && selectedContent !== null}
      <div class="flex items-center justify-between border-b border-border px-4 py-2 bg-surface-0">
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold text-text-primary">v{selectedVersion.version}</span>
          <StatusBadge status={selectedVersion.status.toUpperCase()} />
          <span class="text-2xs text-text-tertiary">{formatDate(selectedVersion.createdAt)}</span>
        </div>
        <div class="flex items-center gap-2">
          <button
            onclick={handleCompare}
            class="btn btn-sm {showDiff ? 'btn-primary' : 'btn-ghost'}"
          >
            <ArrowLeftRight size={12} />
            {showDiff ? 'View source' : 'Compare'}
          </button>
          <button
            onclick={handleRestore}
            class="btn btn-sm btn-primary"
          >
            Load into editor
          </button>
        </div>
      </div>

      <div class="flex-1 min-h-0 overflow-auto">
        {#if loadingContent}
          <div class="p-8 text-center text-sm text-text-tertiary">Loading version content...</div>
        {:else if showDiff}
          <!-- Diff view -->
          {@const diffLines = computeDiff(selectedContent, currentContent)}
          <div class="font-mono text-xs">
            {#each diffLines as line, i}
              <div class="flex {line.type === 'add'
                  ? 'bg-success/10'
                  : line.type === 'remove'
                    ? 'bg-error/10'
                    : ''}">
                <span class="w-10 shrink-0 px-2 py-0.5 text-right text-text-tertiary select-none border-r border-border-subtle">
                  {i + 1}
                </span>
                <span class="w-6 shrink-0 text-center py-0.5 select-none
                  {line.type === 'add' ? 'text-success' : line.type === 'remove' ? 'text-error' : 'text-text-tertiary'}">
                  {line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '}
                </span>
                <pre class="flex-1 py-0.5 px-2 whitespace-pre-wrap break-all
                  {line.type === 'add'
                    ? 'text-success'
                    : line.type === 'remove'
                      ? 'text-error'
                      : 'text-text-primary'}">{line.text}</pre>
              </div>
            {/each}
          </div>
        {:else}
          <!-- Read-only source view -->
          <CodeEditor value={selectedContent} readonly maxHeight="" height="100%" />
        {/if}
      </div>
    {:else if selectedVersion && loadingContent}
      <div class="flex-1 flex items-center justify-center">
        <p class="text-sm text-text-tertiary">Loading...</p>
      </div>
    {:else}
      <div class="flex-1 flex flex-col items-center justify-center text-center p-8">
        <Clock size={32} class="mb-3 text-text-tertiary opacity-40" />
        <p class="text-sm text-text-secondary">Select a version to view its content</p>
        <p class="mt-1 text-2xs text-text-tertiary">
          You can compare versions or load previous content into the editor.
        </p>
      </div>
    {/if}
  </div>
</div>
