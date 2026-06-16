<script lang="ts">
  // The DOCUMENTS widget — the documents the ARCHITECT agent produced (specs, ADRs, notes, READMEs),
  // derived LIVE from the session's tool-call stream so the panel fills in the instant the architect
  // writes a doc. We reuse deriveArtifacts/extractPath (one home for path parsing) and keep only the
  // artifacts that look like DOCUMENTS — markdown/text family, or anything under a docs/ tree or an
  // adr path. Each row shows the file name + its directory + the operations applied. Token-driven
  // from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import { deriveArtifacts, type Artifact } from '$lib/workspace/agentWorkspace';
  import PanelWidget from './PanelWidget.svelte';

  let { session, theme }: { session: ChatSession; theme?: Theme } = $props();

  const DOC_EXT = /\.(md|mdx|adr|rst|txt)$/i;

  function isDoc(path: string): boolean {
    const p = path.toLowerCase();
    return DOC_EXT.test(p) || p.includes('/docs/') || p.includes('adr');
  }

  const docs = $derived(deriveArtifacts(session.entries).filter((a) => isDoc(a.path)));

  function fileName(path: string): string {
    const parts = path.split('/');
    return parts[parts.length - 1] || path;
  }
  function dirName(path: string): string {
    const i = path.lastIndexOf('/');
    return i > 0 ? path.slice(0, i) : '';
  }
</script>

<div
  class="documents"
  data-testid="documents-widget"
  data-count={docs.length}
  aria-label="architect documents"
>
  <PanelWidget title="Documents" count={docs.length} {theme}>
    {#snippet children()}
      {#if docs.length === 0}
        <p class="documents__empty" data-testid="documents-empty">
          No documents yet — they appear as the architect writes specs and notes.
        </p>
      {:else}
        <ul class="documents__list" role="list">
          {#each docs as doc (doc.path)}
            {@const dir = dirName(doc.path)}
            <li
              class="doc"
              data-testid="document-row"
              data-status={doc.status}
              data-path={doc.path}
            >
              <span class="doc__dot" data-status={doc.status} aria-hidden="true"></span>
              <span class="doc__name">
                {fileName(doc.path)}
                {#if dir}<span class="doc__dir">{dir}</span>{/if}
              </span>
              <span class="doc__ops">
                {#each doc.operations as op (op)}<span class="doc__op">{op}</span>{/each}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    {/snippet}
  </PanelWidget>
</div>

<style>
  .documents {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .documents__empty {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    margin: 0;
  }
  .documents__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .doc {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    animation: doc-in 240ms ease-out;
  }
  .doc:hover {
    background: var(--eden-app-panel-bg);
  }
  .doc__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .doc__dot[data-status='running'] {
    background: var(--eden-app-accent);
    animation: doc-pulse 1.2s ease-in-out infinite;
  }
  .doc__dot[data-status='ok'] {
    background: var(--color-info);
  }
  .doc__dot[data-status='error'],
  .doc__dot[data-status='denied'] {
    background: var(--color-error);
  }
  .doc__name {
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-inline-size: 0;
  }
  .doc__dir {
    color: var(--eden-app-muted);
    margin-inline-start: var(--space-2, 8px);
    opacity: 0.7;
  }
  .doc__ops {
    display: inline-flex;
    gap: 3px;
    flex: none;
  }
  .doc__op {
    font-size: 10px;
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 3px;
    padding: 0 4px;
  }
  @keyframes doc-in {
    from {
      opacity: 0;
      transform: translateY(-3px);
    }
  }
  @keyframes doc-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .doc {
      animation: none;
    }
    .doc__dot[data-status='running'] {
      animation: none;
    }
  }
</style>
