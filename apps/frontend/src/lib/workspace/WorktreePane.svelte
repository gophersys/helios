<script lang="ts">
  // WorktreePane — the workspace CENTER pane: the generated-assets file tree beside the file viewer,
  // both driven by one WorktreeStore. The tree lists the committed worktree (init/product/* + the
  // rest), refreshing LIVE as commits land; selecting a file loads it into the viewer (markdown/JSON
  // pretty-rendered). A small header names the asset count + offers a manual refresh.
  //
  // REUSABLE + promotion-ready (agent-UI lib principle): it owns the tree↔viewer split and binds the
  // store's reactive surface to the two child widgets — no network of its own (the store holds the
  // WorktreeFileSource). Token-driven from @eden/theme.
  //
  // PROMOTION NOTE: staged in apps/frontend/src/lib/workspace pending the lib pipeline (ADR-0020).
  import type { Theme } from '@eden/theme';
  import { buildTree } from './worktreeTree';
  import type { WorktreeStore } from './worktreeFiles.svelte';
  import WorktreeTree from './WorktreeTree.svelte';
  import FileViewer from './FileViewer.svelte';

  let {
    store,
    onRefresh,
    theme,
  }: {
    /** The reactive worktree store (the file list + selection + loaded content). */
    store: WorktreeStore;
    /** Invoked when the user clicks the manual refresh affordance (the host re-lists the worktree). */
    onRefresh?: () => void;
    theme?: Theme;
  } = $props();

  // The nested tree, rebuilt from the flat list on every refresh (pure + cheap).
  const tree = $derived(buildTree(store.files));
</script>

<div class="worktree" data-testid="worktree-pane">
  <aside class="worktree__tree" aria-label="generated files">
    <header class="worktree__tree-head">
      <span class="worktree__title">Generated assets</span>
      <span class="worktree__count" data-testid="worktree-count">{store.files.length}</span>
      {#if onRefresh}
        <button
          class="worktree__refresh"
          data-testid="worktree-refresh"
          title="Refresh files"
          aria-label="Refresh files"
          onclick={onRefresh}
        >
          <span aria-hidden="true">↻</span>
        </button>
      {/if}
    </header>
    <div class="worktree__tree-body">
      {#if store.listError}
        <p class="worktree__note worktree__note--error" data-testid="worktree-error">
          {store.listError}
        </p>
      {:else if !store.loadedList}
        <p class="worktree__note" data-testid="worktree-loading">Loading the worktree…</p>
      {:else if store.files.length === 0}
        <p class="worktree__note" data-testid="worktree-empty">
          No committed files yet — Eden's generated assets appear here as the build commits them.
        </p>
      {:else}
        <WorktreeTree
          nodes={tree}
          selectedPath={store.selectedPath}
          onSelect={(path) => store.select(path)}
          {theme}
        />
      {/if}
    </div>
  </aside>

  <div class="worktree__viewer">
    <FileViewer
      content={store.content}
      selectedPath={store.selectedPath}
      loading={store.loadingContent}
      error={store.contentError}
      {theme}
    />
  </div>
</div>

<style>
  .worktree {
    display: grid;
    grid-template-columns: clamp(220px, 24vw, 320px) minmax(0, 1fr);
    flex: 1;
    min-block-size: 0;
    overflow: hidden;
  }
  .worktree__tree {
    display: flex;
    flex-direction: column;
    min-block-size: 0;
    overflow: hidden;
    border-inline-end: 1px solid var(--eden-app-line);
    background: var(--eden-app-rail-bg);
  }
  .worktree__tree-head {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border-block-end: 1px solid var(--eden-app-line);
    flex: none;
  }
  .worktree__title {
    font-size: var(--font-size-caption, 12px);
    font-weight: 650;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .worktree__count {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    background: color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface));
    border-radius: 999px;
    padding: 0 0.5rem;
    font-variant-numeric: tabular-nums;
  }
  .worktree__refresh {
    margin-inline-start: auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: calc(var(--space-5, 20px) + var(--space-1, 4px));
    block-size: calc(var(--space-5, 20px) + var(--space-1, 4px));
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    color: var(--eden-app-muted);
    cursor: pointer;
  }
  .worktree__refresh:hover {
    color: var(--eden-app-fg);
    border-color: var(--eden-app-accent);
  }
  .worktree__refresh:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
  .worktree__tree-body {
    flex: 1;
    min-block-size: 0;
    overflow: auto;
    padding: var(--space-2, 8px) var(--space-1, 4px);
  }
  .worktree__note {
    color: var(--eden-app-muted);
    font-size: var(--font-size-caption, 12px);
    margin: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
  }
  .worktree__note--error {
    color: var(--color-error);
    font-family: var(--font-code);
    overflow-wrap: anywhere;
  }
  .worktree__viewer {
    min-inline-size: 0;
    min-block-size: 0;
    overflow: hidden;
    background: var(--eden-app-bg);
  }
  @media (max-width: 760px) {
    .worktree {
      grid-template-columns: 1fr;
    }
    .worktree__tree {
      display: none;
    }
  }
</style>
