<script lang="ts">
  import { Copy, Check, XCircle, AlertTriangle } from 'lucide-svelte';
  import { analyzeBuildLog, type LogAnalysis } from '$lib/utils/formatting';

  let {
    lines,
    streaming = false,
  }: {
    lines: string[];
    streaming?: boolean;
  } = $props();

  let containerEl: HTMLPreElement | undefined = $state(undefined);
  let copied = $state(false);
  let autoScroll = $state(true);

  // Analyze log for errors/warnings
  const analysis = $derived.by((): LogAnalysis => {
    if (lines.length === 0) return { errors: [], warnings: [], errorCount: 0, warningCount: 0 };
    return analyzeBuildLog(lines.join('\n'));
  });

  // ANSI color mapping - maps to design token classes
  function ansiToClass(code: string): string {
    switch (code) {
      // Standard foreground colors
      case '30': return 'ansi-black';
      case '31': return 'text-error';
      case '32': return 'text-success';
      case '33': return 'text-warning';
      case '34': return 'text-accent';
      case '35': return 'ansi-magenta';
      case '36': return 'text-info';
      case '37': return 'text-text-secondary';
      // Bright foreground colors
      case '90': return 'text-text-tertiary';
      case '91': return 'ansi-bright-red';
      case '92': return 'ansi-bright-green';
      case '93': return 'ansi-bright-yellow';
      case '94': return 'ansi-bright-blue';
      case '95': return 'ansi-bright-magenta';
      case '96': return 'ansi-bright-cyan';
      case '97': return 'text-text-primary';
      // Styles
      case '1': return 'font-bold';
      case '2': return 'opacity-60';
      case '3': return 'italic';
      case '4': return 'underline';
      default: return '';
    }
  }

  interface Segment {
    text: string;
    classes: string;
  }

  function parseAnsi(line: string): Segment[] {
    const segments: Segment[] = [];
    const regex = /\x1b\[([0-9;]*)m/g;
    let lastIndex = 0;
    let currentClasses = '';
    let match: RegExpExecArray | null;

    while ((match = regex.exec(line)) !== null) {
      // Text before this escape
      if (match.index > lastIndex) {
        segments.push({ text: line.slice(lastIndex, match.index), classes: currentClasses });
      }
      const codes = match[1].split(';');
      for (const code of codes) {
        if (code === '0' || code === '') {
          currentClasses = '';
        } else {
          const cls = ansiToClass(code);
          if (cls) currentClasses = currentClasses ? `${currentClasses} ${cls}` : cls;
        }
      }
      lastIndex = regex.lastIndex;
    }

    // Remaining text
    if (lastIndex < line.length) {
      segments.push({ text: line.slice(lastIndex), classes: currentClasses });
    }

    if (segments.length === 0) {
      segments.push({ text: line, classes: '' });
    }

    return segments;
  }

  $effect(() => {
    // Auto-scroll when new lines arrive
    if (autoScroll && containerEl && lines.length > 0) {
      containerEl.scrollTop = containerEl.scrollHeight;
    }
  });

  function handleScroll(): void {
    if (!containerEl) return;
    const atBottom = containerEl.scrollTop + containerEl.clientHeight >= containerEl.scrollHeight - 40;
    autoScroll = atBottom;
  }

  async function copyLog(): Promise<void> {
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      copied = true;
      setTimeout(() => { copied = false; }, 2000);
    } catch {
      // Clipboard not available
    }
  }
</script>

<div class="relative rounded-lg border border-border overflow-hidden">
  <!-- Toolbar -->
  <div class="flex items-center justify-between border-b border-border bg-surface-2 px-3 py-1.5">
    <div class="flex items-center gap-3">
      <span class="text-2xs font-medium text-text-tertiary">
        {lines.length} lines
        {#if streaming}
          <span class="ml-1.5 inline-flex items-center gap-1 text-accent">
            <span class="relative flex h-1.5 w-1.5">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
              <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent"></span>
            </span>
            streaming
          </span>
        {/if}
      </span>
      {#if analysis.errorCount > 0}
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-error-muted text-error text-2xs font-medium">
          <XCircle size={10} />
          {analysis.errorCount} error{analysis.errorCount > 1 ? 's' : ''}
        </span>
      {/if}
      {#if analysis.warningCount > 0}
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium">
          <AlertTriangle size={10} />
          {analysis.warningCount} warning{analysis.warningCount > 1 ? 's' : ''}
        </span>
      {/if}
    </div>
    <button
      onclick={copyLog}
      class="flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs text-text-tertiary transition-colors hover:bg-surface-1 hover:text-text-primary"
      title="Copy log"
    >
      {#if copied}
        <Check size={12} class="text-success" />
        Copied
      {:else}
        <Copy size={12} />
        Copy
      {/if}
    </button>
  </div>

  <!-- Log content -->
  <pre
    bind:this={containerEl}
    onscroll={handleScroll}
    class="max-h-[600px] overflow-auto bg-surface-2 px-3 py-2 font-mono text-xs leading-relaxed text-text-secondary"
  >{#each lines as line, i}<span class="mr-3 inline-block w-10 select-none text-right text-text-tertiary opacity-50">{i + 1}</span>{#each parseAnsi(line) as seg}<span class={seg.classes}>{seg.text}</span>{/each}
{/each}</pre>
</div>
