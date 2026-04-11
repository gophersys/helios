<script lang="ts">
  import { Wrench, Box, ExternalLink } from 'lucide-svelte';
  import { api } from '$lib/api';
  import type { FixtureDesign } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    type: 'MANUFACTURING' | 'VALIDATION';
    boardRevisionId?: string;
  }

  let { type, boardRevisionId }: Props = $props();

  let designs = $state<FixtureDesign[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  interface DesignGroup {
    name: string;
    revisions: FixtureDesign[];
  }

  const grouped = $derived.by<DesignGroup[]>(() => {
    const map = new Map<string, FixtureDesign[]>();
    for (const d of designs) {
      const list = map.get(d.name) || [];
      list.push(d);
      map.set(d.name, list);
    }
    return Array.from(map.entries()).map(([name, revisions]) => ({
      name,
      revisions: revisions.sort((a, b) => b.revision.localeCompare(a.revision)),
    }));
  });

  async function fetchDesigns(): Promise<void> {
    loading = true;
    error = null;
    try {
      let url = `/v2/fixtures/designs?type=${type}&limit=100`;
      if (boardRevisionId) {
        url += `&boardRevisionId=${boardRevisionId}`;
      }
      const res = await api.get<ApiResponse<{ data: FixtureDesign[]; pagination: unknown }>>(url);
      designs = (res.data as any).data ?? res.data;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load fixture designs';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    type;
    boardRevisionId;
    fetchDesigns();
  });
</script>

<div class="mt-4">
  <h4 class="text-xs font-semibold text-text-secondary mb-2 flex items-center gap-1.5">
    <Wrench size={13} class="text-text-tertiary" />
    Fixture Designs
  </h4>

  {#if loading}
    <p class="text-2xs text-text-tertiary py-3">Loading...</p>
  {:else if error}
    <p class="text-2xs text-error py-2">{error}</p>
  {:else if designs.length === 0}
    <div class="rounded-lg border border-dashed border-border bg-surface-0 px-4 py-5 text-center">
      <Wrench size={20} class="mx-auto text-text-tertiary mb-2 opacity-40" />
      <p class="text-xs text-text-secondary">No fixture designs yet.</p>
      <p class="text-2xs text-text-tertiary mt-1">
        Designs are auto-extracted when a test app is uploaded via <code class="font-mono">corectl test upload</code>.
      </p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each grouped as group}
        <div class="rounded-lg border border-border bg-surface-0 px-4 py-3">
          <h5 class="text-xs font-medium text-text-primary mb-2">{group.name}</h5>
          <div class="space-y-1.5">
            {#each group.revisions as design}
              <div class="flex items-center gap-3 text-2xs py-1 px-2 rounded hover:bg-surface-1 transition-colors">
                <code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-text-primary">v{design.revision}</code>

                <div class="flex items-center gap-1 flex-wrap">
                  {#each design.capabilities as cap}
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-text-secondary">{cap}</span>
                  {/each}
                </div>

                {#if design.boardRevision}
                  <span class="text-text-tertiary">
                    {design.boardRevision.version}
                  </span>
                {/if}

                <span class="text-text-tertiary ml-auto flex items-center gap-1">
                  <Box size={11} />
                  {design.benchCount ?? 0} {(design.benchCount ?? 0) === 1 ? 'instance' : 'instances'}
                </span>

                <a
                  href="/fixtures?designId={design.id}"
                  class="text-accent hover:text-accent-hover flex items-center gap-0.5"
                  title="Create or view instances"
                >
                  <ExternalLink size={11} />
                </a>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
