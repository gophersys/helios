<script lang="ts">
  import { FilePlus, ArrowRight } from 'lucide-svelte';
  import Card from '$lib/components/ui/card.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { RecipeTemplate } from '$lib/types/models';

  interface Props {
    templates: RecipeTemplate[];
    loading: boolean;
    onUseTemplate: (content: string) => void;
  }

  let { templates, loading, onUseTemplate }: Props = $props();

  let previewTemplate = $state<RecipeTemplate | null>(null);

  // Map template categories to StatusBadge-compatible status strings
  const categoryToStatus: Record<string, string> = {
    starter: 'ACTIVE',
    advanced: 'PENDING',
    manufacturing: 'MANUFACTURING',
  };
</script>

<div class="p-5 space-y-6">
  <div>
    <h3 class="text-sm font-semibold text-text-primary">Recipe Templates</h3>
    <p class="mt-1 text-2xs text-text-tertiary">
      Start from a template to quickly set up a build recipe. Templates include the SDK calls and build structure for common scenarios.
    </p>
  </div>

  {#if loading}
    <div class="py-8 text-center text-sm text-text-tertiary">Loading templates...</div>
  {:else if templates.length === 0}
    <div class="py-8 text-center">
      <FilePlus size={32} class="mx-auto mb-3 text-text-tertiary opacity-40" />
      <p class="text-sm text-text-tertiary">No templates available.</p>
    </div>
  {:else}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each templates as template}
        <Card size="sm">
          <div class="flex items-center gap-2 mb-1.5">
            <h4 class="text-sm font-semibold text-text-primary">{template.name}</h4>
            <StatusBadge status={categoryToStatus[template.category] ?? template.category.toUpperCase()} />
          </div>
          <p class="text-2xs text-text-secondary leading-relaxed">{template.description}</p>

          <!-- Preview snippet -->
          <div class="mt-3 rounded-md border border-border-subtle bg-surface-0 overflow-hidden">
            <pre class="p-2 text-[10px] font-mono text-text-tertiary leading-relaxed overflow-hidden max-h-[80px]">{template.content.split('\n').slice(0, 6).join('\n')}{template.content.split('\n').length > 6 ? '\n...' : ''}</pre>
          </div>

          <div class="mt-3 flex items-center gap-2">
            <button
              onclick={() => (previewTemplate = previewTemplate?.id === template.id ? null : template)}
              class="btn btn-sm btn-ghost text-2xs"
            >
              {previewTemplate?.id === template.id ? 'Hide preview' : 'Preview'}
            </button>
            <button
              onclick={() => onUseTemplate(template.content)}
              class="btn btn-sm btn-primary ml-auto"
            >
              Use template
              <ArrowRight size={12} />
            </button>
          </div>

          <!-- Full preview -->
          {#if previewTemplate?.id === template.id}
            <div class="mt-3 rounded-md border border-border bg-surface-0 overflow-hidden">
              <pre class="p-3 text-[11px] font-mono text-text-primary leading-relaxed overflow-x-auto max-h-[300px] overflow-y-auto">{template.content}</pre>
            </div>
          {/if}
        </Card>
      {/each}
    </div>
  {/if}
</div>
