<script lang="ts">
  // WorktreeTree — the file TREE of the workspace center pane: the committed worktree assets
  // (init/product/* and the rest) rendered as a nested, file-browser-style tree. A click on a file
  // selects it (the host loads its content into the viewer); directories expand/collapse. Directories
  // default OPEN so the freshly generated product assets are visible without a click.
  //
  // REUSABLE + promotion-ready (agent-UI lib principle): pure presentation over the TreeNode model
  // (built once by worktreeTree.buildTree) — clean props in, one callback out (onSelect), no network.
  // Recurses on itself for nested directories (Svelte 5 self-import). Token-driven from @eden/theme.
  //
  // PROMOTION NOTE: staged in apps/frontend/src/lib/workspace pending the lib pipeline (ADR-0020);
  // it depends only on the local TreeNode model, so it promotes alongside worktreeTree.ts unchanged.
  import type { Theme } from '@eden/theme';
  import type { TreeNode } from './worktreeTree';
  import Self from './WorktreeTree.svelte';

  let {
    nodes,
    selectedPath = null,
    onSelect,
    depth = 0,
    theme: _theme,
  }: {
    /** The tree level to render (buildTree's output at the root; a directory's children when nested). */
    nodes: TreeNode[];
    /** The path of the currently-selected file, so the matching leaf reads as active. */
    selectedPath?: string | null;
    /** Invoked with a file's full relative path when the user selects it. */
    onSelect: (path: string) => void;
    /** The nesting depth (drives indentation). The host renders at depth 0. */
    depth?: number;
    theme?: Theme;
  } = $props();

  // Per-directory open state, keyed by directory path. Default open (true) so the generated assets
  // are visible immediately; a click toggles. $state so the toggle re-renders.
  let collapsed = $state<Record<string, boolean>>({});

  function toggle(path: string): void {
    collapsed = { ...collapsed, [path]: !collapsed[path] };
  }
</script>

<ul class="tree" role="tree" data-depth={depth}>
  {#each nodes as node (node.path)}
    {#if node.kind === 'directory'}
      <li
        class="tree__item"
        role="treeitem"
        aria-expanded={!collapsed[node.path]}
        aria-selected="false"
      >
        <button
          class="tree__row tree__row--dir"
          data-testid="worktree-dir"
          data-path={node.path}
          style="padding-inline-start: calc(var(--space-3, 12px) + {depth} * var(--space-4, 16px));"
          onclick={() => toggle(node.path)}
        >
          <span class="tree__twisty" data-open={!collapsed[node.path]} aria-hidden="true">▸</span>
          <span class="tree__glyph tree__glyph--dir" aria-hidden="true">▸</span>
          <span class="tree__name">{node.name}</span>
        </button>
        {#if !collapsed[node.path]}
          <Self
            nodes={node.children}
            {selectedPath}
            {onSelect}
            depth={depth + 1}
          />
        {/if}
      </li>
    {:else}
      <li class="tree__item" role="treeitem" aria-selected={selectedPath === node.path}>
        <button
          class="tree__row tree__row--file"
          class:tree__row--active={selectedPath === node.path}
          data-testid="worktree-file"
          data-path={node.path}
          style="padding-inline-start: calc(var(--space-3, 12px) + {depth} * var(--space-4, 16px));"
          onclick={() => onSelect(node.path)}
        >
          <span class="tree__twisty tree__twisty--spacer" aria-hidden="true"></span>
          <span class="tree__glyph tree__glyph--file" aria-hidden="true">▪</span>
          <span class="tree__name">{node.name}</span>
        </button>
      </li>
    {/if}
  {/each}
</ul>

<style>
  .tree {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .tree__item {
    margin: 0;
  }
  .tree__row {
    inline-size: 100%;
    display: flex;
    align-items: center;
    gap: var(--space-1, 4px);
    padding-block: var(--space-1, 4px);
    padding-inline-end: var(--space-2, 8px);
    background: none;
    border: none;
    border-radius: var(--eden-app-radius, 4px);
    color: var(--eden-app-fg);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    text-align: start;
    cursor: pointer;
  }
  .tree__row:hover {
    background: var(--eden-app-rail-bg);
  }
  .tree__row:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: -2px;
  }
  .tree__row--active {
    background: color-mix(in oklab, var(--eden-app-accent) 14%, var(--eden-app-bg));
    color: var(--eden-app-fg);
    font-weight: 650;
  }
  .tree__twisty {
    inline-size: 0.9em;
    flex: none;
    color: var(--eden-app-muted);
    transition: transform var(--duration-short-3, 150ms) var(--ease-standard, ease);
  }
  .tree__twisty[data-open='true'] {
    transform: rotate(90deg);
  }
  .tree__twisty--spacer {
    visibility: hidden;
  }
  .tree__glyph--dir {
    color: var(--eden-app-muted);
  }
  .tree__glyph--file {
    color: var(--eden-app-accent);
    flex: none;
  }
  .tree__name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  @media (prefers-reduced-motion: reduce) {
    .tree__twisty {
      transition: none;
    }
  }
</style>
