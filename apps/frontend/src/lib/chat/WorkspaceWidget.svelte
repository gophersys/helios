<script lang="ts">
  // The WORKSPACE widget — the files/folders/assets the agent has generated, derived LIVE from its
  // tool-call stream (Write/Edit/Read/… targets), so the panel fills in the instant the agent
  // touches a file. Each artifact shows its path, the operations applied, and a status dot. Fully
  // token-driven from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { Entry } from '$lib/gateway/session.svelte';
  import { deriveArtifacts } from '$lib/workspace/agentWorkspace';

  let { entries, theme: _theme }: { entries: Entry[]; theme?: Theme } = $props();

  const artifacts = $derived(deriveArtifacts(entries));

  function fileName(path: string): string {
    const parts = path.split('/');
    return parts[parts.length - 1] || path;
  }
  function dirName(path: string): string {
    const i = path.lastIndexOf('/');
    return i > 0 ? path.slice(0, i) : '';
  }
</script>

<section class="workspace" data-testid="workspace-widget" aria-label="agent workspace files">
  <header class="workspace__head">
    <span class="workspace__title">Workspace</span>
    <span class="workspace__count" data-testid="workspace-count">{artifacts.length}</span>
  </header>

  {#if artifacts.length === 0}
    <p class="workspace__empty" data-testid="workspace-empty">No files yet — they appear as the agent writes.</p>
  {:else}
    <ul class="workspace__list" role="list">
      {#each artifacts as artifact (artifact.path)}
        <li class="file" data-testid="workspace-file" data-status={artifact.status} data-path={artifact.path}>
          <span class="file__dot" data-status={artifact.status} aria-hidden="true"></span>
          <span class="file__name">
            {fileName(artifact.path)}
            {#if dirName(artifact.path)}<span class="file__dir">{dirName(artifact.path)}</span>{/if}
          </span>
          <span class="file__ops">
            {#each artifact.operations as op (op)}<span class="file__op">{op}</span>{/each}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .workspace {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .workspace__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2, 8px);
  }
  .workspace__title {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .workspace__count {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-accent);
    font-variant-numeric: tabular-nums;
  }
  .workspace__empty {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    margin: 0;
  }
  .workspace__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .file {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    animation: file-in 240ms ease-out;
  }
  .file:hover {
    background: var(--eden-app-panel-bg);
  }
  .file__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .file__dot[data-status='running'] {
    background: var(--eden-app-accent);
    animation: file-pulse 1.2s ease-in-out infinite;
  }
  .file__dot[data-status='ok'] {
    background: var(--color-info);
  }
  .file__dot[data-status='error'],
  .file__dot[data-status='denied'] {
    background: var(--color-error);
  }
  .file__name {
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-inline-size: 0;
  }
  .file__dir {
    color: var(--eden-app-muted);
    margin-inline-start: var(--space-2, 8px);
    opacity: 0.7;
  }
  .file__ops {
    display: inline-flex;
    gap: 3px;
    flex: none;
  }
  .file__op {
    font-size: 10px;
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 3px;
    padding: 0 4px;
  }
  @keyframes file-in {
    from {
      opacity: 0;
      transform: translateY(-3px);
    }
  }
  @keyframes file-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .file {
      animation: none;
    }
    .file__dot[data-status='running'] {
      animation: none;
    }
  }
</style>
