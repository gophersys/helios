<script lang="ts">
  interface Props {
    value: string;
    id?: string;
    label?: string;
    placeholder?: string;
    required?: boolean;
    type?: 'text' | 'email' | 'password' | 'number' | 'url';
    disabled?: boolean;
    class?: string;
    onchange?: (value: string) => void;
  }

  let {
    value = $bindable(),
    id,
    label,
    placeholder,
    required = false,
    type = 'text',
    disabled = false,
    class: className = '',
    onchange
  }: Props = $props();

  const fallbackId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);
  const inputId = $derived(id ?? fallbackId);

  function handleInput(e: Event): void {
    value = (e.target as HTMLInputElement).value;
    onchange?.(value);
  }
</script>

<div class={className}>
  {#if label}
    <label for={inputId} class="mb-1 block text-2xs font-medium text-text-tertiary">{label}</label>
  {/if}
  <input
    id={inputId}
    {type}
    {required}
    {disabled}
    {placeholder}
    value={value}
    oninput={handleInput}
    class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
  />
</div>
