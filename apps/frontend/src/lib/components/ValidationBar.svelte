<script lang="ts">
  // The validation bar at the top of the document panel (doc 12 §5: a validation
  // bar — violations count + T6 coverage gaps, expandable). It shows the corpus
  // totals (the gate-relevant numbers) and, expanded, lists every diagnostic;
  // entries touching the active document are marked so the reader sees what
  // pertains to what they are looking at. A non-zero validator exit is flagged
  // explicitly (the validate verb exits 1 on violations but still returns JSON).
  import type { Diagnostic } from '$lib/server/validatorClient';

  let {
    violations,
    coverage,
    ok,
    violationsExit,
    activeIds = [],
  }: {
    violations: Diagnostic[];
    coverage: Diagnostic[];
    ok: boolean;
    violationsExit: boolean;
    // The ids that belong to the active document (its document id + every item id
    // in its data); a diagnostic whose documentId is one of these pertains to it.
    activeIds?: string[];
  } = $props();

  let expanded = $state(false);
  const activeIdSet = $derived(new Set(activeIds));

  function pertains(diagnostic: Diagnostic): boolean {
    return diagnostic.documentId !== undefined && activeIdSet.has(diagnostic.documentId);
  }

  const tone = $derived(violations.length > 0 ? 'warn' : coverage.length > 0 ? 'info' : 'ok');
</script>

<div class="validation-bar validation-bar--{tone}">
  <button
    class="validation-bar__summary"
    type="button"
    aria-expanded={expanded}
    onclick={() => (expanded = !expanded)}
  >
    <span class="validation-bar__caret" class:open={expanded}>▸</span>
    {#if ok}
      <span class="chip chip--ok">validates</span>
    {:else}
      <span class="chip chip--warn"
        >{violations.length} violation{violations.length === 1 ? '' : 's'}</span
      >
    {/if}
    {#if coverage.length > 0}
      <span class="chip chip--info"
        >{coverage.length} T6 coverage gap{coverage.length === 1 ? '' : 's'}</span
      >
    {:else}
      <span class="chip chip--muted">no coverage gaps</span>
    {/if}
    {#if violationsExit}
      <span class="validation-bar__note">validator exited non-zero (report retained)</span>
    {/if}
  </button>

  {#if expanded}
    <div class="validation-bar__detail">
      {#if violations.length > 0}
        <h4>Violations</h4>
        <ul class="diagnostic-list">
          {#each violations as diagnostic, index (index)}
            <li class:pertinent={pertains(diagnostic)}>
              <code class="diagnostic-rule">{diagnostic.rule ?? '—'}</code>
              {#if diagnostic.documentId}<code class="diagnostic-id">{diagnostic.documentId}</code
                >{/if}
              <span class="diagnostic-message">{diagnostic.message}</span>
              <span class="diagnostic-file">{diagnostic.file}</span>
            </li>
          {/each}
        </ul>
      {/if}

      {#if coverage.length > 0}
        <h4>T6 coverage gaps (reported, not blocking here)</h4>
        <ul class="diagnostic-list">
          {#each coverage as diagnostic, index (index)}
            <li class:pertinent={pertains(diagnostic)}>
              <code class="diagnostic-rule">{diagnostic.rule ?? 'T6'}</code>
              {#if diagnostic.documentId}<code class="diagnostic-id">{diagnostic.documentId}</code
                >{/if}
              <span class="diagnostic-message">{diagnostic.message}</span>
            </li>
          {/each}
        </ul>
      {/if}

      {#if violations.length === 0 && coverage.length === 0}
        <p class="validation-bar__clean">
          The corpus validates with no shape, traceability, or coverage findings.
        </p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .validation-bar {
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--panel-bg);
    margin-bottom: 1.2rem;
  }
  .validation-bar--warn {
    border-color: var(--chip-warn-fg);
  }

  .validation-bar__summary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    background: none;
    border: none;
    padding: 0.7rem 0.9rem;
    cursor: pointer;
    font: inherit;
    color: inherit;
    text-align: left;
  }
  .validation-bar__caret {
    color: var(--muted);
    transition: transform 0.12s ease;
    display: inline-block;
  }
  .validation-bar__caret.open {
    transform: rotate(90deg);
  }
  .validation-bar__note {
    font-size: 0.78rem;
    color: var(--chip-warn-fg);
  }

  .validation-bar__detail {
    padding: 0 0.9rem 0.9rem;
    border-top: 1px solid var(--line);
  }
  .validation-bar__detail h4 {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
    margin: 0.9rem 0 0.4rem;
  }
  .diagnostic-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .diagnostic-list li {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.4rem;
    font-size: 0.84rem;
    padding: 0.25rem 0.4rem;
    border-radius: 6px;
  }
  .diagnostic-list li.pertinent {
    background: var(--chip-info-bg);
  }
  .diagnostic-rule {
    background: var(--chipbg);
    color: var(--accent);
    font-size: 0.76em;
    padding: 0.05em 0.35em;
    border-radius: 5px;
  }
  .diagnostic-id {
    background: var(--codebg);
    color: var(--muted);
    font-size: 0.76em;
    padding: 0.05em 0.35em;
    border-radius: 5px;
  }
  .diagnostic-message {
    flex: 1 1 16rem;
  }
  .diagnostic-file {
    color: var(--muted);
    font-size: 0.78em;
  }
  .validation-bar__clean {
    margin: 0.6rem 0 0;
    color: var(--muted);
    font-size: 0.88rem;
  }
</style>
