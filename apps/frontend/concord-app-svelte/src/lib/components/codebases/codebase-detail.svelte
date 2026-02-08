<script lang="ts">
  import { Plus, ExternalLink, ChevronDown, ChevronRight, Pencil, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api';
  import BackButton from '$lib/components/ui/back-button.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ImageUpload from '$lib/components/ui/image-upload.svelte';
  import ReleaseForm from './release-form.svelte';
  import ArtifactList from './artifact-list.svelte';
  import { isSafeUrl } from '$lib/utils/url';
  import type { Codebase, Release } from '$lib/types/models';

  interface Props {
    codebase: Codebase;
    canManage: boolean;
    onBack: () => void;
    onRefresh: () => void;
    onImageUpload: (file: File) => Promise<void>;
  }

  let { codebase, canManage, onBack, onRefresh, onImageUpload }: Props = $props();

  let error = $state<string | null>(null);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);
  let showReleaseForm = $state(false);
  let editingRelease = $state<Release | null>(null);
  let expandedReleases = $state(new Set<string>());

  const releases = $derived(codebase.releases || []);

  function toggleExpanded(id: string) {
    const next = new Set(expandedReleases);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    expandedReleases = next;
  }

  async function handleCreateRelease(data: {
    version: string;
    status: string;
    releaseNotes: string | null;
    tagName: string | null;
  }) {
    error = null;
    try {
      await api.post(`/v2/codebases/${codebase.id}/releases`, data);
      showReleaseForm = false;
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create release';
    }
  }

  async function handleUpdateRelease(
    releaseId: string,
    data: {
      version: string;
      status: string;
      releaseNotes: string | null;
      tagName: string | null;
    }
  ) {
    error = null;
    try {
      await api.put(`/v2/codebases/${codebase.id}/releases/${releaseId}`, data);
      editingRelease = null;
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to update release';
    }
  }

  function promptDeleteRelease(releaseId: string) {
    const rel = releases.find((r) => r.id === releaseId);
    deleteTarget = { id: releaseId, name: rel?.version || '' };
  }

  async function handleDeleteRelease(releaseId: string) {
    error = null;
    try {
      await api.delete(`/v2/codebases/${codebase.id}/releases/${releaseId}`);
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete release';
    }
  }
</script>

<div class="animate-fade-in">
  <BackButton label="Back to codebases" onclick={onBack} />

  <ErrorAlert message={error} />

  <div class="card card-md">
    <div class="flex gap-6">
      <!-- Image -->
      <div class="w-48 shrink-0">
        <ImageUpload
          currentUrl={codebase.imageUrl}
          onUpload={onImageUpload}
          disabled={!canManage}
        />
      </div>

      <!-- Info -->
      <div class="flex-1">
        <h2 class="text-lg font-semibold text-text-primary">
          {codebase.name}
        </h2>
        {#if codebase.description}
          <p class="mt-1 text-sm text-text-secondary">
            {codebase.description}
          </p>
        {/if}
        <div class="mt-3 flex gap-4 text-2xs text-text-tertiary">
          <span>
            <strong class="text-text-secondary">Branch:</strong>
            {codebase.defaultBranch}
          </span>
          {#if codebase.repoUrl && isSafeUrl(codebase.repoUrl)}
            <a
              href={codebase.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 text-accent hover:underline"
            >
              <ExternalLink size={12} />
              Repository
            </a>
          {/if}
        </div>
      </div>
    </div>

    <!-- Releases -->
    <div class="mt-6">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-text-primary">Releases</h3>
        {#if canManage && !showReleaseForm}
          <button
            onclick={() => (showReleaseForm = true)}
            class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            Add release
          </button>
        {/if}
      </div>

      {#if showReleaseForm}
        <div class="mb-4">
          <ReleaseForm
            onSubmit={handleCreateRelease}
            onCancel={() => (showReleaseForm = false)}
          />
        </div>
      {/if}

      {#if releases.length > 0}
        <div class="space-y-2">
          {#each releases as release (release.id)}
            {@const isExpanded = expandedReleases.has(release.id)}
            {@const isEditing = editingRelease?.id === release.id}

            <div class="rounded-lg border border-border bg-surface-0">
              <!-- Release header -->
              <div
                role="button"
                tabindex="0"
                onclick={() => toggleExpanded(release.id)}
                onkeydown={(e) => e.key === 'Enter' && toggleExpanded(release.id)}
                class="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-surface-1"
              >
                {#if isExpanded}
                  <ChevronDown size={16} class="shrink-0 text-text-tertiary" />
                {:else}
                  <ChevronRight size={16} class="shrink-0 text-text-tertiary" />
                {/if}
                <span class="font-medium text-text-primary text-sm">
                  {release.version}
                </span>
                <StatusBadge status={release.status} />
                {#if release.tagName}
                  <span class="text-2xs text-text-tertiary">
                    tag: {release.tagName}
                  </span>
                {/if}
                {#if release.releasedAt}
                  <span class="text-2xs text-text-tertiary">
                    {new Date(release.releasedAt).toLocaleDateString()}
                  </span>
                {/if}
                <span class="ml-auto text-2xs text-text-tertiary">
                  {release.artifactCount || 0} artifact{(release.artifactCount || 0) !== 1 ? 's' : ''}
                </span>

                {#if canManage}
                  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                  <div
                    role="group"
                    class="flex gap-1"
                    onclick={(e) => e.stopPropagation()}
                    onkeydown={(e) => e.stopPropagation()}
                  >
                    <button
                      onclick={() => (editingRelease = release)}
                      class="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                      title="Edit release"
                      aria-label="Edit release"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onclick={() => promptDeleteRelease(release.id)}
                      class="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                      title="Delete release"
                      aria-label="Delete release"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                {/if}
              </div>

              <!-- Release notes -->
              {#if isExpanded && release.releaseNotes}
                <div class="border-t border-border-subtle px-4 py-2 text-sm text-text-secondary">
                  {release.releaseNotes}
                </div>
              {/if}

              <!-- Editing form -->
              {#if isEditing}
                <div class="border-t border-border px-4 py-3">
                  <ReleaseForm
                    initial={{
                      version: release.version,
                      status: release.status,
                      releaseNotes: release.releaseNotes,
                      tagName: release.tagName,
                    }}
                    onSubmit={(data) => handleUpdateRelease(release.id, data)}
                    onCancel={() => (editingRelease = null)}
                  />
                </div>
              {/if}

              <!-- Artifacts -->
              {#if isExpanded}
                <div class="border-t border-border-subtle px-4 py-3">
                  <ArtifactList
                    codebaseId={codebase.id}
                    releaseId={release.id}
                    artifacts={release.artifacts || []}
                    {canManage}
                    {onRefresh}
                  />
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div class="py-6 text-center text-sm text-text-tertiary">
          No releases yet
        </div>
      {/if}
    </div>
  </div>

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="release"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDeleteRelease(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
