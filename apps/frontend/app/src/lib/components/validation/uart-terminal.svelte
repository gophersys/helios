<script lang="ts">
  import { onMount } from 'svelte';
  import { Terminal, Search } from 'lucide-svelte';
  import { parseAnsi, stripAnsi } from '$lib/utils/ansi';

  interface Props {
    lines: string[];
    label: string;
    iconColor: string;
  }

  let { lines, label, iconColor }: Props = $props();

  let search = $state('');
  let searchIndex = $state(0);
  let scrollEl: HTMLElement;

  // Track rendered line count to detect new data without deep diffing
  let renderedCount = $state(0);
  let displayLines = $state<string[]>([]);

  // Use RAF to batch-check for new lines instead of reacting on every prop change
  let rafId: number | null = null;
  let mounted = false;

  onMount(() => {
    mounted = true;
    function tick() {
      if (lines.length !== renderedCount || lines !== displayLines) {
        // Only update if lines actually changed (new data appended or replaced)
        if (lines.length !== displayLines.length || lines !== displayLines) {
          displayLines = lines;
          renderedCount = lines.length;
        }
      }
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
    return () => {
      mounted = false;
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  });

  const matches = $derived.by(() => {
    if (!search.trim()) return [];
    const q = search.toLowerCase();
    return displayLines.reduce((acc: number[], line, i) => {
      if (stripAnsi(line).toLowerCase().includes(q)) acc.push(i);
      return acc;
    }, []);
  });

  function scrollToMatch(idx: number) {
    if (!scrollEl || matches.length === 0) return;
    const target = scrollEl.querySelectorAll('[data-line-index]')[matches[idx % matches.length]] as HTMLElement;
    target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  // Auto-scroll to bottom when new lines arrive (only if not searching)
  $effect(() => {
    if (displayLines.length > 0 && scrollEl && !search) {
      requestAnimationFrame(() => { scrollEl.scrollTop = scrollEl.scrollHeight; });
    }
  });
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col h-full">
  <div class="flex items-center gap-2 px-3 py-1 border-b border-border bg-surface-1 flex-shrink-0">
    <Terminal size={12} class={iconColor} />
    <span class="text-xs font-medium text-text-primary">{label}</span>
    {#if displayLines.length > 0}
      <span class="text-2xs text-text-tertiary ml-auto">{displayLines.length} lines</span>
    {/if}
  </div>
  <div class="flex items-center gap-1 px-2 py-0.5 border-b border-border bg-[#161b22]">
    <Search size={10} class="text-text-tertiary" />
    <input type="text" bind:value={search} placeholder="Search..." class="flex-1 bg-transparent text-xs text-[#c9d1d9] placeholder:text-text-tertiary outline-none font-mono" />
    {#if search && matches.length > 0}
      <span class="text-2xs text-text-tertiary">{(searchIndex % matches.length) + 1}/{matches.length}</span>
      <button onclick={() => { searchIndex = Math.max(0, searchIndex - 1); scrollToMatch(searchIndex); }} class="text-text-tertiary hover:text-text-primary p-0.5 text-xs">&#x25B2;</button>
      <button onclick={() => { searchIndex = searchIndex + 1; scrollToMatch(searchIndex); }} class="text-text-tertiary hover:text-text-primary p-0.5 text-xs">&#x25BC;</button>
    {:else if search}
      <span class="text-2xs text-text-tertiary">0 results</span>
    {/if}
  </div>
  <div bind:this={scrollEl} class="flex-1 overflow-y-auto overflow-x-auto bg-[#0d1117] px-2 py-1 font-mono text-xs leading-snug">
    {#if displayLines.length > 0}
      {#each displayLines as line, i (line)}
        <div data-line-index={i} class="whitespace-pre {matches.includes(i) ? 'bg-yellow-500/20' : ''}">{#each parseAnsi(line) as seg}<span class="{seg.classes || 'text-[#c9d1d9]'}">{seg.text}</span>{/each}</div>
      {/each}
    {:else}
      <div class="text-text-tertiary italic py-2">Waiting for {label} data...</div>
    {/if}
  </div>
</div>
