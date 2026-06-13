<script lang="ts">
  // The document workspace for one project (doc 12 §5): a left sidebar grouping
  // documents by tier with status chips, and a main panel rendering the selected
  // document (?doc= param, or the first document). A breadcrumb (doc 12 §2 "where
  // am I") spans Projects → this project → the active document. When the validator
  // could not run, an instructive setup banner stands in for the workspace.
  import { page } from '$app/state';
  import WorkspaceSidebar from '$lib/components/WorkspaceSidebar.svelte';
  import DocumentPanel from '$lib/components/DocumentPanel.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const workspace = $derived(data.workspace);

  // The selected document id from the URL, falling back to the first document in
  // the corpus (sidebar order). Reading from page.url keeps the panel in sync with
  // back/forward navigation without extra state.
  const requestedId = $derived(page.url.searchParams.get('doc'));
  const activeDocument = $derived(
    workspace.documents.find((document) => document.meta.id === requestedId) ??
      workspace.documents[0] ??
      null,
  );
  const activeId = $derived(activeDocument?.meta.id ?? '');
</script>

<svelte:head>
  <title>{workspace.title} — document workspace</title>
</svelte:head>

{#if workspace.validatorError}
  <main class="setup">
    <nav class="breadcrumb">
      <a href="/">Projects</a>
      <span class="breadcrumb__sep">/</span>
      <span>{workspace.title}</span>
    </nav>
    <div class="panel setup__card">
      <h1>The projection source of truth is unavailable</h1>
      <p>
        This workspace renders the document corpus through the <code>documentvalidator</code>, and
        it could not be invoked:
      </p>
      <pre class="setup__message">{workspace.validatorError}</pre>
    </div>
  </main>
{:else if workspace.documents.length === 0}
  <main class="setup">
    <nav class="breadcrumb">
      <a href="/">Projects</a>
      <span class="breadcrumb__sep">/</span>
      <span>{workspace.title}</span>
    </nav>
    <div class="panel setup__card">
      <h1>No documents</h1>
      <p>This project's corpus is empty — there are no documents to render yet.</p>
    </div>
  </main>
{:else}
  <div class="workspace">
    <aside class="workspace__sidebar">
      <WorkspaceSidebar tiers={data.tiers} slug={workspace.slug} {activeId} />
    </aside>

    <main class="workspace__main">
      <nav class="breadcrumb">
        <a href="/">Projects</a>
        <span class="breadcrumb__sep">/</span>
        <a href={`/p/${workspace.slug}`}>{workspace.title}</a>
        {#if activeDocument}
          <span class="breadcrumb__sep">/</span>
          <span class="breadcrumb__current">{activeDocument.meta.id}</span>
        {/if}
      </nav>

      {#if activeDocument}
        {#key activeDocument.meta.id}
          <DocumentPanel
            document={activeDocument}
            backlinks={workspace.backlinks}
            validation={workspace.validation}
          />
        {/key}
      {/if}
    </main>
  </div>
{/if}

<style>
  .workspace {
    display: grid;
    grid-template-columns: minmax(15rem, 18rem) 1fr;
    min-height: 100vh;
    align-items: start;
  }
  .workspace__sidebar {
    position: sticky;
    top: 0;
    align-self: start;
    height: 100vh;
    overflow-y: auto;
    background: var(--navbg);
    border-right: 1px solid var(--line);
  }
  .workspace__main {
    padding: 1.4rem 2rem 5rem;
    min-width: 0;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.84rem;
    color: var(--muted);
    margin-bottom: 1.2rem;
  }
  .breadcrumb a {
    color: var(--muted);
    text-decoration: none;
  }
  .breadcrumb a:hover {
    color: var(--accent);
  }
  .breadcrumb__sep {
    opacity: 0.5;
  }
  .breadcrumb__current {
    color: var(--fg);
    font-weight: 600;
    font-family: var(--font-mono);
    font-size: 0.92em;
  }

  .setup {
    max-width: 720px;
    margin: 0 auto;
    padding: 3rem 1.6rem;
  }
  .setup__card h1 {
    font-size: 1.3rem;
    margin: 0 0 0.8rem;
  }
  .setup__message {
    background: var(--codebg);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 0.8rem 1rem;
    white-space: pre-wrap;
    font-size: 0.82rem;
    color: var(--chip-warn-fg);
    margin: 0.8rem 0 0;
  }

  @media (max-width: 760px) {
    .workspace {
      grid-template-columns: 1fr;
    }
    .workspace__sidebar {
      position: static;
      height: auto;
      border-right: none;
      border-bottom: 1px solid var(--line);
    }
    .workspace__main {
      padding: 1.4rem 1.2rem 4rem;
    }
  }
</style>
