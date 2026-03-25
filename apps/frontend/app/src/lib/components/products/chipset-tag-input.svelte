<script lang="ts">
  import { X, ChevronDown } from 'lucide-svelte';

  interface Props {
    selected: string[];
    options: { id: string; name: string }[];
    onchange: (values: string[]) => void;
    placeholder?: string;
  }

  let { selected, options, onchange, placeholder = 'Select chipsets...' }: Props = $props();

  let open = $state(false);
  let inputRef = $state<HTMLDivElement | null>(null);

  const available = $derived(options.filter((o) => !selected.includes(o.id)));

  /** Get the display name for a chipset ID */
  function getName(id: string): string {
    return options.find((o) => o.id === id)?.name || id;
  }

  function add(id: string) {
    if (!selected.includes(id)) {
      onchange([...selected, id]);
    }
    open = false;
  }

  function remove(id: string) {
    onchange(selected.filter((v) => v !== id));
  }
</script>

<svelte:window onclick={(e) => {
  if (inputRef && !inputRef.contains(e.target as Node)) {
    open = false;
  }
}} />

<div class="relative" bind:this={inputRef}>
  <div
    role="combobox"
    tabindex="0"
    aria-expanded={open}
    aria-haspopup="listbox"
    aria-controls="chipset-listbox"
    aria-label="Select chipsets"
    onclick={() => (open = !open)}
    onkeydown={(e) => e.key === 'Enter' && (open = !open)}
    class="flex min-h-[38px] flex-wrap items-center gap-1 rounded-lg border border-border bg-surface-1 px-2 py-1.5 text-sm"
  >
    {#each selected as id}
      <span class="inline-flex items-center gap-1 rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
        {getName(id)}
        <button
          type="button"
          onclick={(e) => { e.stopPropagation(); remove(id); }}
          class="hover:text-error"
          aria-label="Remove {getName(id)}"
        >
          <X size={12} />
        </button>
      </span>
    {/each}
    {#if selected.length === 0}
      <span class="text-text-tertiary">{placeholder}</span>
    {/if}
    <ChevronDown size={16} class="ml-auto text-text-tertiary" />
  </div>

  {#if open && available.length > 0}
    <div id="chipset-listbox" role="listbox" class="absolute left-0 right-0 top-full z-20 mt-1 max-h-48 overflow-y-auto rounded-lg border border-border bg-surface-1 py-1 shadow-card">
      {#each available as opt}
        <button
          type="button"
          role="option"
          aria-selected="false"
          onclick={() => add(opt.id)}
          class="w-full px-3 py-1.5 text-left text-sm text-text-primary hover:bg-surface-2"
        >
          {opt.name}
        </button>
      {/each}
    </div>
  {/if}
</div>
