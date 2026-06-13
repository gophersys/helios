<script lang="ts">
  // The document-workspace home (the A0 project grid, doc 12 §2/§4). Each
  // registered project renders as a card: title, document count, a status
  // breakdown (the founder's status-first dots, doc 12 §5), and its validation
  // state — linking into /p/[slug], the workspace. A project whose corpus could
  // not be read renders an instructive error in place of stats (validator missing
  // → the build command to run).
  import StatusChip from '$lib/components/StatusChip.svelte';
  import { STATUS_ORDER, statusTone } from '$lib/documentModel';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
</script>

<svelte:head>
  <title>Eden — document workspace</title>
</svelte:head>

<main>
  <header class="masthead">
    <p class="eyebrow">Eden · document workspace</p>
    <h1>Projects</h1>
    <p class="lede">
      The product-design process as a working surface (ADR-0015). Each project's document set is
      projected from the <code>documentvalidator</code> — its tiers, statuses, link graph, and validation
      reported live. Open a project to read its documents and trace its coverage.
    </p>
  </header>

  <section class="grid">
    {#each data.cards as card (card.slug)}
      {#if card.errorMessage}
        <article class="panel card card--error">
          <header class="card__head">
            <h2 class="card__title">{card.title}</h2>
            <span class="chip chip--warn">unavailable</span>
          </header>
          <p class="card__error">{card.errorMessage}</p>
        </article>
      {:else}
        <a class="panel card card--link" href="/p/{card.slug}">
          <header class="card__head">
            <h2 class="card__title">{card.title}</h2>
            {#if card.ok}
              <span class="chip chip--ok">validates</span>
            {:else}
              <span class="chip chip--warn"
                >{card.violations} violation{card.violations === 1 ? '' : 's'}</span
              >
            {/if}
          </header>

          <p class="card__count">
            <strong>{card.documentCount}</strong>
            document{card.documentCount === 1 ? '' : 's'}
          </p>

          <div class="card__statuses">
            {#each STATUS_ORDER as status (status)}
              {#if card.statusCounts[status] > 0}
                <span
                  class="status-dot status-dot--{statusTone(status)}"
                  title="{card.statusCounts[status]} {status}"
                >
                  <span class="status-dot__mark"></span>
                  <span class="status-dot__count">{card.statusCounts[status]}</span>
                  <span class="status-dot__label">{status}</span>
                </span>
              {/if}
            {/each}
          </div>

          <footer class="card__foot">
            {#if card.coverageGaps > 0}
              <span class="chip chip--muted"
                >{card.coverageGaps} coverage gap{card.coverageGaps === 1 ? '' : 's'}</span
              >
            {:else}
              <span class="chip chip--ok">full P1 coverage</span>
            {/if}
            <span class="card__open">Open workspace →</span>
          </footer>
        </a>
      {/if}
    {/each}
  </section>

  <!-- A legend tying the dots to the status vocabulary; keeps the founder's
       status-first view legible without a manual (doc 12 §6 learnability). -->
  <p class="legend">
    Status:
    {#each STATUS_ORDER as status, index (status)}
      <span class="legend__item">
        <span class="status-dot__mark status-dot--{statusTone(status)}"></span>{status}</span
      >{#if index < STATUS_ORDER.length - 1}<span class="legend__sep">·</span>{/if}
    {/each}
  </p>
</main>

<style>
  main {
    max-width: 1080px;
    margin: 0 auto;
    padding: 3.2rem 1.6rem 6rem;
  }

  .masthead {
    margin-bottom: 2.4rem;
  }

  /* Micro-label (tokens.json typography.micro): JetBrains Mono, 12px, letterspaced, uppercase. */
  .eyebrow {
    font-family: var(--font-code);
    font-size: var(--type-micro);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.6rem;
  }

  /* Display heading — Fraunces via the global h1 rule; this sets the page-level scale. */
  h1 {
    font-size: var(--type-heading-1);
    line-height: 1.15;
    letter-spacing: -0.015em;
    margin: 0 0 0.9rem;
  }

  .lede {
    font-size: var(--type-lead);
    color: var(--muted);
    max-width: 70ch;
    margin: 0;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
    gap: 1.2rem;
    margin-bottom: 2rem;
  }

  .card {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    text-decoration: none;
    color: inherit;
  }

  .card--link {
    transition:
      border-color 0.12s ease,
      box-shadow 0.12s ease,
      transform 0.12s ease;
  }
  .card--link:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--color-ink) 12%, transparent);
    transform: translateY(-1px);
  }

  .card__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .card__title {
    font-size: 1.18rem;
    letter-spacing: -0.01em;
    margin: 0;
  }

  .card__count {
    margin: 0;
    color: var(--muted);
    font-size: 0.96rem;
  }
  .card__count strong {
    color: var(--fg);
    font-size: 1.4rem;
    font-variant-numeric: tabular-nums;
  }

  .card__statuses {
    display: flex;
    flex-wrap: wrap;
    gap: 0.7rem;
  }

  .status-dot {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.82rem;
    color: var(--muted);
  }
  .status-dot__mark {
    display: inline-block;
    width: 0.62rem;
    height: 0.62rem;
    border-radius: 50%;
    flex: none;
  }
  .status-dot__count {
    font-weight: 650;
    color: var(--fg);
    font-variant-numeric: tabular-nums;
  }
  .status-dot--ok .status-dot__mark,
  .status-dot--ok.status-dot__mark {
    background: var(--chip-ok-fg);
  }
  .status-dot--info .status-dot__mark,
  .status-dot--info.status-dot__mark {
    background: var(--chip-info-fg);
  }
  .status-dot--warn .status-dot__mark,
  .status-dot--warn.status-dot__mark {
    background: var(--chip-warn-fg);
  }
  .status-dot--muted .status-dot__mark,
  .status-dot--muted.status-dot__mark {
    background: var(--chip-muted-fg);
  }
  .status-dot--neutral .status-dot__mark,
  .status-dot--neutral.status-dot__mark {
    background: var(--chip-neutral-fg);
  }

  .card__foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    margin-top: auto;
    padding-top: 0.3rem;
  }
  .card__open {
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--accent);
  }

  .card--error .card__error {
    margin: 0;
    color: var(--chip-warn-fg);
    font-size: 0.9rem;
    line-height: 1.55;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.82rem;
    color: var(--muted);
    margin: 0;
  }
  .legend__item {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .legend__sep {
    opacity: 0.5;
  }
</style>
