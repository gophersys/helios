<script lang="ts">
  import { ExternalLink, type Icon } from 'lucide-svelte';
  import type { Snippet, ComponentType } from 'svelte';

  interface Props {
    icon: ComponentType<Icon>;
    href?: string;
    external?: boolean;
    variant?: 'default' | 'accent' | 'success' | 'warning' | 'error';
    children: Snippet;
  }

  let { icon: IconComponent, href, external = false, variant = 'default', children }: Props = $props();

  const variantClasses: Record<string, string> = {
    default: 'bg-surface-2 text-text-secondary hover:bg-surface-3',
    accent: 'bg-accent-muted text-accent hover:bg-accent/15',
    success: 'bg-success-muted text-success hover:bg-success/15',
    warning: 'bg-warning-muted text-warning hover:bg-warning/15',
    error: 'bg-error-muted text-error hover:bg-error/15',
  };

  const base = 'inline-flex items-center gap-1 rounded-md px-2 py-1 text-2xs font-medium transition-colors';
</script>

{#if href}
  <a
    {href}
    target={external ? '_blank' : undefined}
    rel={external ? 'noopener noreferrer' : undefined}
    class="{base} {variantClasses[variant]} cursor-pointer"
    onclick={(e) => e.stopPropagation()}
  >
    <IconComponent size={10} />
    {@render children()}
    {#if external}<ExternalLink size={8} class="opacity-50" />{/if}
  </a>
{:else}
  <span class="{base} {variantClasses[variant]}">
    <IconComponent size={10} />
    {@render children()}
  </span>
{/if}
