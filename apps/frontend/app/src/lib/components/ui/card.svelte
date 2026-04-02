<script lang="ts">
  import { X } from 'lucide-svelte';
  import type { Snippet } from 'svelte';

  interface Props {
    title?: string;
    subtitle?: string;
    size?: 'sm' | 'md' | 'lg';
    interactive?: boolean;
    closable?: boolean;
    onclose?: () => void;
    onclick?: () => void;
    header?: Snippet;
    footer?: Snippet;
    children: Snippet;
    class?: string;
  }

  let {
    title,
    subtitle,
    size = 'md',
    interactive = false,
    closable = false,
    onclose,
    onclick,
    header,
    footer,
    children,
    class: className = ''
  }: Props = $props();

  const sizeClasses = {
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6'
  };

  const baseClasses = 'rounded-xl border border-border bg-surface-1';
  const interactiveClasses = $derived(
    interactive
      ? 'cursor-pointer transition-all hover:border-accent/50 hover:shadow-md active:scale-[0.99]'
      : ''
  );
</script>

{#if interactive}
  <button
    type="button"
    class="{baseClasses} {interactiveClasses} {sizeClasses[size]} {className} text-left w-full"
    onclick={onclick}
  >
    {#if header || title}
      <div class="mb-3 flex items-start justify-between gap-3">
        {#if header}
          {@render header()}
        {:else}
          <div>
            {#if title}
              <h3 class="text-sm font-semibold text-text-primary">{title}</h3>
            {/if}
            {#if subtitle}
              <p class="mt-0.5 text-xs text-text-tertiary">{subtitle}</p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    {@render children()}

    {#if footer}
      <div class="mt-4 border-t border-border pt-3">
        {@render footer()}
      </div>
    {/if}
  </button>
{:else}
  <div class="{baseClasses} {sizeClasses[size]} {className}">
    {#if header || title || closable}
      <div class="mb-3 flex items-start justify-between gap-3">
        {#if header}
          {@render header()}
        {:else}
          <div>
            {#if title}
              <h3 class="text-sm font-semibold text-text-primary">{title}</h3>
            {/if}
            {#if subtitle}
              <p class="mt-0.5 text-xs text-text-tertiary">{subtitle}</p>
            {/if}
          </div>
        {/if}
        {#if closable && onclose}
          <button
            type="button"
            onclick={onclose}
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        {/if}
      </div>
    {/if}

    {@render children()}

    {#if footer}
      <div class="mt-4 border-t border-border pt-3">
        {@render footer()}
      </div>
    {/if}
  </div>
{/if}
