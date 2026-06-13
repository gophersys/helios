<script lang="ts">
  // A ```mermaid fence rendered as a diagram (doc 12 §5, REQ-0028: "```mermaid
  // fences render as diagrams … lazy-load mermaid so it does not bloat first
  // paint"). mermaid is a ~multi-MB browser library that needs the DOM, so it is
  // dynamically imported only on mount and only when a mermaid block is actually
  // present — first paint and the SSR pass never touch it. The diagram theme is
  // driven by the document's resolved tokens (Deep-Forest/Moss/Sage/Bone) read off
  // the live CSS custom properties, so diagrams match the surface in light and
  // dark. While loading, the diagram source shows as a labeled code block so the
  // content is never blank or lost.
  import { onMount } from 'svelte';

  let { code }: { code: string } = $props();

  let container = $state<HTMLDivElement | undefined>();
  let status = $state<'loading' | 'ready' | 'error'>('loading');
  let errorMessage = $state('');

  // A stable-enough unique id per diagram instance for mermaid's render target.
  const diagramId = `mermaid-${Math.random().toString(36).slice(2, 10)}`;

  // Read a resolved CSS custom property off :root so the diagram theme tracks the
  // active light/dark token values rather than hard-coding hexes.
  function token(name: string, fallback: string): string {
    if (typeof window === 'undefined') return fallback;
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  onMount(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        const surface = token('--color-deep-forest', '#243d2c');
        const moss = token('--color-moss', '#5c7f5c');
        const sage = token('--color-sage', '#a8b89c');
        const bone = token('--color-bone', '#f4f1e8');
        const line = token('--line', '#c9c6bd');

        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          fontFamily: token('--font-text', 'Inter, sans-serif'),
          themeVariables: {
            // Map mermaid's theme slots onto the Eden palette so nodes read as
            // Deep-Forest surfaces with Moss/Sage accents and Bone text.
            primaryColor: surface,
            primaryTextColor: bone,
            primaryBorderColor: moss,
            lineColor: moss,
            secondaryColor: sage,
            tertiaryColor: bone,
            background: 'transparent',
            mainBkg: surface,
            nodeBorder: moss,
            clusterBkg: 'transparent',
            clusterBorder: line,
            edgeLabelBackground: bone,
            fontSize: '15px',
          },
        });

        const { svg } = await mermaid.render(diagramId, code);
        if (cancelled) return;
        if (container) container.innerHTML = svg;
        status = 'ready';
      } catch (caught) {
        if (cancelled) return;
        errorMessage = caught instanceof Error ? caught.message : 'failed to render diagram';
        status = 'error';
      }
    })();
    return () => {
      cancelled = true;
    };
  });
</script>

<figure class="mermaid-figure" data-status={status}>
  {#if status === 'error'}
    <figcaption class="mermaid-figure__error">
      Diagram could not be rendered: {errorMessage}
    </figcaption>
    <pre class="mermaid-figure__source"><code>{code}</code></pre>
  {:else}
    <div
      bind:this={container}
      class="mermaid-figure__canvas"
      class:is-loading={status === 'loading'}
      role="img"
      aria-label="Diagram"
    >
      {#if status === 'loading'}
        <pre class="mermaid-figure__source"><code>{code}</code></pre>
      {/if}
    </div>
  {/if}
</figure>

<style>
  .mermaid-figure {
    margin: 1.6rem 0;
    padding: 1rem;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--color-sage) 8%, var(--bg));
    overflow-x: auto;
    text-align: center;
  }
  .mermaid-figure__canvas :global(svg) {
    max-width: 100%;
    height: auto;
  }
  .mermaid-figure__canvas.is-loading {
    opacity: 0.55;
  }
  .mermaid-figure__source {
    margin: 0;
    text-align: left;
    font-family: var(--font-code);
    font-size: 0.82rem;
    color: var(--muted);
    white-space: pre;
    overflow-x: auto;
  }
  .mermaid-figure__error {
    font-size: 0.82rem;
    color: var(--chip-warn-fg);
    margin-bottom: 0.6rem;
    text-align: left;
  }
</style>
