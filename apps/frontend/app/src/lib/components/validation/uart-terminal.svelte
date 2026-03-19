<script lang="ts">
  import { onMount } from 'svelte';
  import { Terminal, Search, ArrowDown } from 'lucide-svelte';
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

  const WINDOW = 200;
  let followTail = $state(true);
  let displayLines = $state<string[]>([]);
  let displayOffset = $state(0);
  let lastLinesRef: string[] = [];
  let scrollLock = false; // prevent scroll handler from firing during programmatic scrolls

  onMount(() => {
    if (lines.length > 0) {
      displayOffset = Math.max(0, lines.length - WINDOW);
      displayLines = lines.slice(displayOffset);
      lastLinesRef = lines;
      requestAnimationFrame(() => {
        if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
      });
    }

    let rafId = requestAnimationFrame(function loop() {
      if (lines !== lastLinesRef) {
        lastLinesRef = lines;
        if (followTail) {
          displayOffset = Math.max(0, lines.length - WINDOW);
          displayLines = lines.slice(displayOffset);
          scrollLock = true;
          requestAnimationFrame(() => {
            if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
            setTimeout(() => { scrollLock = false; }, 200);
          });
        }
      }
      rafId = requestAnimationFrame(loop);
    });

    return () => cancelAnimationFrame(rafId);
  });

  function onWheel(e: WheelEvent) {
    if (e.deltaY < 0) followTail = false;
  }

  function onScroll() {
    if (!scrollEl || scrollLock) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollEl;

    // Scrolled to top — load earlier lines
    if (scrollTop < 10 && displayOffset > 0) {
      const prevOffset = displayOffset;
      displayOffset = Math.max(0, displayOffset - 100);
      displayLines = lines.slice(displayOffset, displayOffset + WINDOW);
      scrollLock = true;
      requestAnimationFrame(() => {
        if (scrollEl) {
          const linesAdded = prevOffset - displayOffset;
          scrollEl.scrollTop = linesAdded * 16;
        }
        setTimeout(() => { scrollLock = false; }, 200);
      });
      return;
    }

    // Scrolled to bottom — load later lines or re-enable follow
    if (scrollHeight - scrollTop - clientHeight < 10) {
      const maxOffset = Math.max(0, lines.length - WINDOW);
      if (displayOffset < maxOffset) {
        displayOffset = Math.min(displayOffset + 100, maxOffset);
        displayLines = lines.slice(displayOffset, displayOffset + WINDOW);
        scrollLock = true;
        requestAnimationFrame(() => {
          if (scrollEl) scrollEl.scrollTop = 0;
          setTimeout(() => { scrollLock = false; }, 200);
        });
      }
      if (displayOffset >= maxOffset) {
        followTail = true;
      }
    }
  }

  function jumpToLatest() {
    followTail = true;
    displayOffset = Math.max(0, lines.length - WINDOW);
    displayLines = lines.slice(displayOffset);
    scrollLock = true;
    requestAnimationFrame(() => {
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
      setTimeout(() => { scrollLock = false; }, 200);
    });
  }

  const showJump = $derived(!followTail && lines.length > displayOffset + WINDOW);

  const matches = $derived.by(() => {
    if (!search.trim()) return [];
    const q = search.toLowerCase();
    return lines.reduce((acc: number[], line, i) => {
      if (stripAnsi(line).toLowerCase().includes(q)) acc.push(i);
      return acc;
    }, []);
  });

  function scrollToMatch(idx: number) {
    if (matches.length === 0) return;
    const globalIdx = matches[idx % matches.length];
    followTail = false;
    displayOffset = Math.max(0, globalIdx - Math.floor(WINDOW / 2));
    displayLines = lines.slice(displayOffset, displayOffset + WINDOW);
    requestAnimationFrame(() => {
      if (!scrollEl) return;
      const localIdx = globalIdx - displayOffset;
      const el = scrollEl.querySelectorAll('[data-line-index]')[localIdx] as HTMLElement;
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
  }
</script>

<div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col h-full">
  <div class="flex items-center gap-2 px-3 py-1 border-b border-border bg-surface-1 flex-shrink-0">
    <Terminal size={12} class={iconColor} />
    <span class="text-xs font-medium text-text-primary">{label}</span>
    {#if lines.length > 0}
      <span class="text-2xs text-text-tertiary ml-auto">{lines.length} lines</span>
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
  <div class="relative flex-1 min-h-0">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div bind:this={scrollEl} onwheel={onWheel} onscroll={onScroll} class="absolute inset-0 overflow-y-auto overflow-x-auto bg-[#0d1117] px-2 py-1 font-mono text-xs leading-snug">
      {#if displayLines.length > 0}
        {#each displayLines as line, i (displayOffset + i)}
          {@const globalIdx = displayOffset + i}
          <div data-line-index={i} class="whitespace-pre {matches.includes(globalIdx) ? 'bg-yellow-500/20' : ''}">{#each parseAnsi(line) as seg}<span class="{seg.classes || 'text-[#c9d1d9]'}">{seg.text}</span>{/each}</div>
        {/each}
      {:else}
        <div class="text-text-tertiary italic py-2">Waiting for {label} data...</div>
      {/if}
    </div>
    {#if showJump}
      <button
        onclick={jumpToLatest}
        class="absolute bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-accent/90 hover:bg-accent text-xs text-white font-medium shadow-lg backdrop-blur-sm transition-colors z-10 flex items-center gap-1"
      >
        <ArrowDown size={12} />
        Jump to latest
      </button>
    {/if}
  </div>
</div>
