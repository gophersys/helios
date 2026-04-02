<script lang="ts">
  let {
    label,
    value,
    options,
    onchange,
    allLabel = 'All',
  }: {
    label: string;
    value: string;
    options: { value: string; label: string }[];
    onchange: (value: string) => void;
    allLabel?: string;
  } = $props();

  function handleChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    onchange(target.value);
  }
</script>

<label class="inline-flex items-center gap-1.5 text-xs text-text-secondary">
  <span class="font-medium whitespace-nowrap">{label}:</span>
  <select
    {value}
    onchange={handleChange}
    class="rounded-md border border-border bg-surface-0 px-2.5 py-1.5 text-xs text-text-primary transition-colors hover:border-text-tertiary focus:border-accent focus:outline-none"
  >
    <option value="">{allLabel}</option>
    {#each options as opt}
      <option value={opt.value}>{opt.label}</option>
    {/each}
  </select>
</label>
