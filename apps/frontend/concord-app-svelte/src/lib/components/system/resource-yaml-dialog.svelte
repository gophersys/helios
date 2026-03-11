<script lang="ts">
  import { X, Pencil, Eye } from 'lucide-svelte';
  import { api } from '$lib/api';
  import YamlViewer from './yaml-viewer.svelte';
  import { getAuth } from '$lib/stores/auth.svelte';

  interface Props {
    kind: string;
    namespace?: string;
    name?: string;
    open: boolean;
    onclose: () => void;
  }

  let { kind, namespace = '', name = '', open, onclose }: Props = $props();

  let yaml = $state('');
  let loading = $state(true);
  let error = $state<string | null>(null);
  let editMode = $state(false);
  let editValue = $state('');
  let saving = $state(false);

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('Concord.Admin.System.Manage'));

  async function fetchYaml() {
    loading = true;
    error = null;
    try {
      const res = await api.get<{ data: { yaml: string } }>(`/v2/cluster/resources/${kind}/${namespace}/${name}`);
      if (res?.data) {
        yaml = res.data.yaml;
        editValue = res.data.yaml;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load YAML';
    } finally {
      loading = false;
    }
  }

  async function handleApply() {
    saving = true;
    error = null;
    try {
      await api.put(`/v2/cluster/resources/${kind}/${namespace}/${name}`, { yaml: editValue });
      yaml = editValue;
      editMode = false;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to update resource';
    } finally {
      saving = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onclose();
    }
  }

  function handleTabKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      (e.target as HTMLTextAreaElement).blur();
      return;
    }
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault();
      const target = e.target as HTMLTextAreaElement;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      editValue = editValue.slice(0, start) + '  ' + editValue.slice(end);
      // Set cursor position after the inserted spaces
      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      });
    }
  }

  $effect(() => {
    if (open) {
      fetchYaml();
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
      editMode = false;
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- Backdrop -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="fixed inset-0 bg-overlay z-modal-backdrop flex items-center justify-center p-4"
    onclick={onclose}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="bg-surface-1 rounded-lg border border-border shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 class="text-lg font-semibold text-text-primary">{kind}: {name}</h2>
        <div class="flex items-center gap-2">
          {#if canManage}
            <button
              onclick={() => { editMode = !editMode; editValue = yaml; }}
              class="p-1.5 rounded hover:bg-surface-2 text-text-secondary"
              aria-label={editMode ? 'View' : 'Edit'}
            >
              {#if editMode}
                <Eye class="w-4 h-4" />
              {:else}
                <Pencil class="w-4 h-4" />
              {/if}
            </button>
          {/if}
          <button
            onclick={onclose}
            class="p-1.5 rounded hover:bg-surface-2 text-text-secondary"
            aria-label="Close"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-auto p-4">
        {#if loading}
          <div class="flex items-center justify-center py-8">
            <span class="text-text-secondary">Loading...</span>
          </div>
        {:else if error}
          <div class="p-3 rounded bg-error-muted text-error text-sm">{error}</div>
        {:else if editMode}
          <div class="space-y-3">
            <textarea
              bind:value={editValue}
              onkeydown={handleTabKey}
              class="w-full h-96 p-3 rounded bg-surface-0 border border-border font-mono text-xs text-text-primary focus:outline-none focus:ring-1 focus:ring-accent resize-none"
              spellcheck="false"
            ></textarea>
            <div class="flex items-center justify-between">
              <span class="text-xs text-text-secondary">
                {editValue !== yaml ? 'Unsaved changes' : ''}
              </span>
              <div class="flex gap-2">
                <button
                  onclick={() => { editMode = false; editValue = yaml; }}
                  class="px-3 py-1.5 text-xs font-medium rounded bg-surface-2 text-text-secondary hover:bg-surface-2/80"
                >
                  Cancel
                </button>
                <button
                  onclick={handleApply}
                  disabled={saving || editValue === yaml}
                  class="px-3 py-1.5 text-xs font-medium rounded bg-accent text-white hover:bg-accent/90 disabled:opacity-50"
                >
                  {saving ? 'Applying...' : 'Apply'}
                </button>
              </div>
            </div>
          </div>
        {:else}
          <YamlViewer {yaml} />
        {/if}
      </div>
    </div>
  </div>
{/if}
