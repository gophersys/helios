<script lang="ts">
  import { Copy, Check } from 'lucide-svelte';

  interface Props {
    yaml: string;
  }

  let { yaml }: Props = $props();

  let copied = $state(false);

  async function copyToClipboard() {
    await navigator.clipboard.writeText(yaml);
    copied = true;
    setTimeout(() => copied = false, 2000);
  }

  function highlightLine(line: string): { text: string; class: string }[] {
    const parts: { text: string; class: string }[] = [];

    // Comment
    if (line.trim().startsWith('#')) {
      return [{ text: line, class: 'text-text-tertiary' }];
    }

    // Key: value
    const keyMatch = line.match(/^(\s*)([^:\s][^:]*):(.*)$/);
    if (keyMatch) {
      const [, indent, key, value] = keyMatch;
      parts.push({ text: indent, class: '' });
      parts.push({ text: key, class: 'text-accent' });
      parts.push({ text: ':', class: 'text-text-tertiary' });

      const trimmedValue = value.trim();
      if (trimmedValue) {
        parts.push({ text: ' ', class: '' });
        // Determine value type color
        if (trimmedValue === 'true' || trimmedValue === 'false') {
          parts.push({ text: trimmedValue, class: 'text-warning' });
        } else if (trimmedValue === 'null' || trimmedValue === '~') {
          parts.push({ text: trimmedValue, class: 'text-text-tertiary' });
        } else if (/^-?\d+(\.\d+)?$/.test(trimmedValue)) {
          parts.push({ text: trimmedValue, class: 'text-info' });
        } else if (trimmedValue.startsWith('"') || trimmedValue.startsWith("'")) {
          parts.push({ text: trimmedValue, class: 'text-success' });
        } else {
          parts.push({ text: trimmedValue, class: 'text-success' });
        }
      }
      return parts;
    }

    // List item
    if (line.trim().startsWith('-')) {
      const dashMatch = line.match(/^(\s*)(-)(.*)$/);
      if (dashMatch) {
        const [, indent, dash, rest] = dashMatch;
        parts.push({ text: indent, class: '' });
        parts.push({ text: dash, class: 'text-warning' });
        parts.push({ text: rest, class: 'text-text-primary' });
        return parts;
      }
    }

    return [{ text: line, class: 'text-text-primary' }];
  }

  const lines = $derived(yaml.split('\n'));
</script>

<div class="relative rounded-lg bg-surface-0 border border-border overflow-hidden">
  <button
    onclick={copyToClipboard}
    class="absolute top-2 right-2 p-1.5 rounded bg-surface-2 hover:bg-surface-2/80 text-text-secondary"
    aria-label="Copy YAML"
  >
    {#if copied}
      <Check class="w-4 h-4 text-success" />
    {:else}
      <Copy class="w-4 h-4" />
    {/if}
  </button>

  <pre class="p-3 overflow-x-auto text-xs font-mono leading-relaxed max-h-96 overflow-y-auto">{#each lines as line, i}<span class="inline-block w-full hover:bg-surface-2/50">{#each highlightLine(line) as part}<span class={part.class}>{part.text}</span>{/each}</span>
{/each}</pre>
</div>
