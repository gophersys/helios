<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ArrowLeft,
    CheckCircle2,
    Eye,
    EyeOff,
    GitBranch,
    Link,
    XCircle,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  const auth = getAuth();

  interface RepoConfig {
    id: string;
    name: string;
    webhookUrl: string;
    webhookSecret: string;
    connected: boolean;
    branches: string[];
    variants: string[];
    mtibRev: string;
    lastEventAt: string | null;
  }

  let repos = $state<RepoConfig[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let revealedSecrets = $state<Set<string>>(new Set());

  function toggleSecret(repoId: string): void {
    const next = new Set(revealedSecrets);
    if (next.has(repoId)) {
      next.delete(repoId);
    } else {
      next.add(repoId);
    }
    revealedSecrets = next;
  }

  function maskSecret(secret: string): string {
    if (secret.length <= 8) return '****';
    return secret.slice(0, 4) + '****' + secret.slice(-4);
  }

  async function loadSettings(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<RepoConfig[]>>('/v2/builds/settings/repos');
      repos = res.data;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load CI settings';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadSettings();
  });
</script>

<svelte:head>
  <title>CI Settings - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <button
    onclick={() => goto('/builds')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    CI / Builds
  </button>

  <div class="mb-6">
    <PageHeader
      title="CI Settings"
      description="Repository connections, webhook configuration, and build defaults."
    />
  </div>

  <ErrorAlert message={error} />

  {#if loading}
    <LoadingState message="Loading settings..." />
  {:else if repos.length === 0}
    <div class="card text-center text-sm text-text-tertiary py-8">
      No repositories configured. CI settings will appear here once the backend is set up.
    </div>
  {:else}
    <div class="space-y-4">
      {#each repos as repo (repo.id)}
        <div class="card">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <GitBranch size={16} class="text-text-tertiary" />
              <h3 class="text-sm font-medium text-text-primary">{repo.name}</h3>
              {#if repo.connected}
                <span class="inline-flex items-center gap-1 text-2xs text-success">
                  <CheckCircle2 size={12} />
                  Connected
                </span>
              {:else}
                <span class="inline-flex items-center gap-1 text-2xs text-error">
                  <XCircle size={12} />
                  Disconnected
                </span>
              {/if}
            </div>
          </div>

          <div class="space-y-3">
            <!-- Webhook URL -->
            <div>
              <span class="text-2xs font-medium text-text-tertiary">Webhook URL</span>
              <div class="mt-1 flex items-center gap-2 rounded bg-surface-1 px-3 py-2">
                <Link size={12} class="shrink-0 text-text-tertiary" />
                <code class="flex-1 text-xs font-mono text-text-primary break-all">{repo.webhookUrl}</code>
              </div>
            </div>

            <!-- Webhook Secret -->
            <div>
              <span class="text-2xs font-medium text-text-tertiary">Webhook Secret</span>
              <div class="mt-1 flex items-center gap-2 rounded bg-surface-1 px-3 py-2">
                <code class="flex-1 text-xs font-mono text-text-secondary">
                  {revealedSecrets.has(repo.id) ? repo.webhookSecret : maskSecret(repo.webhookSecret)}
                </code>
                <button
                  onclick={() => toggleSecret(repo.id)}
                  class="shrink-0 rounded p-1 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
                  title={revealedSecrets.has(repo.id) ? 'Hide secret' : 'Show secret'}
                >
                  {#if revealedSecrets.has(repo.id)}
                    <EyeOff size={14} />
                  {:else}
                    <Eye size={14} />
                  {/if}
                </button>
              </div>
            </div>

            <!-- Build config -->
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <span class="text-2xs font-medium text-text-tertiary">Trigger Branches</span>
                <div class="mt-1 flex flex-wrap gap-1">
                  {#each repo.branches as branch}
                    <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-secondary">
                      {branch}
                    </span>
                  {/each}
                  {#if repo.branches.length === 0}
                    <span class="text-2xs text-text-tertiary">All branches</span>
                  {/if}
                </div>
              </div>
              <div>
                <span class="text-2xs font-medium text-text-tertiary">Variants</span>
                <div class="mt-1 flex flex-wrap gap-1">
                  {#each repo.variants as variant}
                    <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-secondary capitalize">
                      {variant}
                    </span>
                  {/each}
                  {#if repo.variants.length === 0}
                    <span class="text-2xs text-text-tertiary">None configured</span>
                  {/if}
                </div>
              </div>
              <div>
                <span class="text-2xs font-medium text-text-tertiary">MTIB Rev</span>
                <p class="mt-1 text-sm text-text-primary">{repo.mtibRev || '--'}</p>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
