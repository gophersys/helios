<script lang="ts">
  // Svelte imports
  import { onMount } from 'svelte';

  // External libraries
  import { X, Monitor, Shield, KeyRound, Lock, Sun, Moon, Plus, Trash2, Copy, Check, GitBranch, Server, Globe, Clock } from 'lucide-svelte';

  // Internal imports
  import { getAuth } from '$lib/stores/auth.svelte';
  import { getTheme } from '$lib/stores/theme.svelte';
  import { apiFetch } from '$lib/api';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import { formatDate } from '$lib/utils/formatting';

  // Type imports
  import type { ApiResponse } from '$lib/types';
  import type { TreeNode } from '$lib/types/models';

  let { onClose }: { onClose: () => void } = $props();

  const auth = getAuth();
  const theme = getTheme();

  // ── Build info state ─────────────────────────────────────────────
  interface BuildInfo {
    service: string;
    version: string;
    environment: string;
    gitCommit: string;
    gitBranch: string;
    gitDirty: string | boolean;
    buildTime: string;
    buildHost: string;
    pythonVersion?: string;
    arch?: string;
    os?: string;
  }

  let backendInfo = $state<BuildInfo | null>(null);
  let frontendInfo = $state<BuildInfo | null>(null);
  let buildInfoLoaded = $state(false);

  async function loadBuildInfo() {
    if (buildInfoLoaded) return;
    buildInfoLoaded = true;
    try {
      const [beRes, feRes] = await Promise.allSettled([
        apiFetch<ApiResponse<BuildInfo>>('/v2/system/info'),
        fetch('/build-info.json').then(r => r.json()),
      ]);
      if (beRes.status === 'fulfilled') backendInfo = beRes.value.data;
      if (feRes.status === 'fulfilled') {
        const fe = feRes.value;
        frontendInfo = {
          service: fe.service || 'concord-frontend',
          version: fe.version || 'unknown',
          environment: fe.environment || 'unknown',
          gitCommit: fe.git_commit || fe.gitCommit || 'unknown',
          gitBranch: fe.git_branch || fe.gitBranch || 'unknown',
          gitDirty: fe.git_dirty || fe.gitDirty || 'false',
          buildTime: fe.build_time || fe.buildTime || 'unknown',
          buildHost: fe.build_host || fe.buildHost || 'unknown',
        };
      }
    } catch { /* silently fail — info section just stays empty */ }
  }

  function isDirty(val: string | boolean): boolean {
    return val === true || val === 'true' || val === '1';
  }

  function formatBuildTime(iso: string): string {
    if (!iso || iso === 'unknown') return 'unknown';
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    } catch { return iso; }
  }

  interface SettingsSection {
    id: string;
    label: string;
    icon: typeof Monitor;
  }

  const sections: SettingsSection[] = [
    { id: 'system', label: 'System', icon: Monitor },
    { id: 'permissions', label: 'My Permissions', icon: Shield },
    { id: 'api-keys', label: 'API Keys', icon: KeyRound },
    { id: 'secrets', label: 'Secrets', icon: Lock },
  ];

  let activeId = $state('system');

  // Lock body scroll while open
  onMount(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  });

  // ── Permission tree helpers ────────────────────────────────────

  const ACTION_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
    Create: { bg: 'bg-success-muted', text: 'text-success', dot: 'bg-success' },
    View: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
    Read: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
    Update: { bg: 'bg-warning-muted', text: 'text-warning', dot: 'bg-warning' },
    Delete: { bg: 'bg-error-muted', text: 'text-error', dot: 'bg-error' },
    Manage: { bg: 'bg-accent-muted', text: 'text-accent', dot: 'bg-accent' },
    Run: { bg: 'bg-accent-muted', text: 'text-accent', dot: 'bg-accent' },
  };

  const DEFAULT_COLOR = { bg: 'bg-surface-2', text: 'text-text-secondary', dot: 'bg-text-tertiary' };

  function getActionColor(action: string) {
    return ACTION_COLORS[action] || DEFAULT_COLOR;
  }

  function buildTree(permissions: string[]): TreeNode[] {
    const root: TreeNode = { label: 'root', children: [] };

    for (const perm of permissions) {
      const parts = perm.split('.');
      const segments = parts.slice(1); // skip "Concord"

      let current = root;
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        const isLeaf = i === segments.length - 1;

        let child = current.children.find((c) => c.label === seg);
        if (!child) {
          child = {
            label: seg,
            children: [],
            ...(isLeaf ? { permKey: perm } : {}),
          };
          current.children.push(child);
        }
        if (isLeaf) child.permKey = perm;
        current = child;
      }
    }

    return root.children;
  }

  const permTree = $derived(buildTree(auth.user?.permissions ?? []));

  // ── API Keys state ─────────────────────────────────────────────

  interface ApiKey {
    id: string;
    name: string;
    keyPrefix: string;
    expiresAt: string | null;
    lastUsedAt: string | null;
    createdAt: string;
  }

  // Secrets state
  interface SecretEntry { id: string; name: string; type: string; description: string | null; }
  let secrets = $state<SecretEntry[]>([]);
  let secretsLoading = $state(true);
  let showSecretForm = $state(false);
  let secretName = $state('');
  let secretType = $state('signing_key');
  let secretValue = $state('');
  let secretDescription = $state('');
  let secretSaving = $state(false);

  async function fetchSecrets(): Promise<void> {
    try {
      const data = await apiFetch<ApiResponse<SecretEntry[]>>('/v2/system/secrets');
      secrets = data.data ?? [];
    } catch { secrets = []; }
    finally { secretsLoading = false; }
  }

  async function handleCreateSecret(): Promise<void> {
    secretSaving = true;
    try {
      await apiFetch('/v2/system/secrets', {
        method: 'POST',
        body: JSON.stringify({
          name: secretName.trim(),
          type: secretType,
          value: secretValue.trim(),
          description: secretDescription.trim() || null,
        }),
      });
      secretName = ''; secretType = 'signing_key'; secretValue = ''; secretDescription = '';
      showSecretForm = false;
      await fetchSecrets();
    } catch (err: unknown) {
      console.error('Failed to create secret:', err);
    } finally { secretSaving = false; }
  }

  async function handleDeleteSecret(id: string, name: string): Promise<void> {
    if (!confirm(`Delete secret "${name}"? This cannot be undone.`)) return;
    try {
      await apiFetch(`/v2/system/secrets/${id}`, { method: 'DELETE' });
      await fetchSecrets();
    } catch (err: unknown) {
      console.error('Failed to delete secret:', err);
    }
  }

  // API Keys state
  let apiKeys = $state<ApiKey[]>([]);
  let apiKeysLoading = $state(true);
  let showCreateKey = $state(false);
  let apiKeyError = $state<string | null>(null);
  let newKey = $state<string | null>(null);
  let copied = $state(false);
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  let formKeyName = $state('');
  let formExpiresAt = $state('');
  let submitting = $state(false);

  async function fetchApiKeys(): Promise<void> {
    try {
      const data = await apiFetch<ApiResponse<ApiKey[]>>('/v2/api-keys');
      apiKeys = data.data;
    } catch (err: unknown) {
      apiKeyError = err instanceof Error ? err.message : 'Failed to load API keys';
    } finally {
      apiKeysLoading = false;
    }
  }

  async function handleCreateKey(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    apiKeyError = null;
    submitting = true;
    try {
      const body: Record<string, string> = { name: formKeyName };
      if (formExpiresAt) {
        body.expiresAt = new Date(formExpiresAt).toISOString();
      }
      const data = await apiFetch<ApiResponse<{ key: string } & ApiKey>>('/v2/api-keys', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      newKey = data.data.key;
      formKeyName = '';
      formExpiresAt = '';
      showCreateKey = false;
      fetchApiKeys();
    } catch (err: unknown) {
      apiKeyError = err instanceof Error ? err.message : 'Failed to create API key';
    } finally {
      submitting = false;
    }
  }

  async function handleDeleteKey(keyId: string): Promise<void> {
    try {
      await apiFetch(`/v2/api-keys/${keyId}`, { method: 'DELETE' });
      fetchApiKeys();
    } catch (err: unknown) {
      apiKeyError = err instanceof Error ? err.message : 'Failed to delete API key';
    }
  }

  async function handleCopy(key: string): Promise<void> {
    await navigator.clipboard.writeText(key);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }

  // Load data when switching to sections
  $effect(() => {
    if (activeId === 'api-keys' && apiKeysLoading) {
      fetchApiKeys();
    }
    if (activeId === 'secrets' && secretsLoading) {
      fetchSecrets();
    }
    if (activeId === 'system' && !buildInfoLoaded) {
      loadBuildInfo();
    }
  });

  // Kick off build info load immediately since system is the default tab
  onMount(() => { loadBuildInfo(); });
</script>

{#snippet TreeDisplayNode(node: TreeNode, depth: number)}
  {@const isLeaf = !!node.permKey}

  {#if isLeaf}
    {@const color = getActionColor(node.label)}
    <span class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-medium {color.bg} {color.text}">
      <span class="h-1.5 w-1.5 rounded-full {color.dot}"></span>
      {node.label}
    </span>
  {:else}
    {@const leafChildren = node.children.filter((c) => c.permKey)}
    {@const branchChildren = node.children.filter((c) => !c.permKey)}

    <div style:padding-left={depth > 0 ? '16px' : '0'}>
      <div class="flex items-center gap-2 py-1">
        <span class="text-2xs font-semibold text-text-primary">
          {node.label}
        </span>
        {#if leafChildren.length > 0}
          <div class="flex flex-wrap gap-1">
            {#each leafChildren as child}
              {@render TreeDisplayNode(child, 0)}
            {/each}
          </div>
        {/if}
      </div>
      {#each branchChildren as child}
        {@render TreeDisplayNode(child, depth + 1)}
      {/each}
    </div>
  {/if}
{/snippet}

<!-- Overlay -->
<div
  class="fixed inset-0 z-modal-backdrop bg-overlay animate-overlay-in"
  onclick={onClose}
  onkeydown={(e) => e.key === 'Escape' && onClose()}
  role="presentation"
  tabindex="-1"
></div>

<!-- Centered container -->
<div class="fixed inset-0 z-modal flex items-center justify-center p-4 pointer-events-none">
  <div
    class="pointer-events-auto flex w-full max-w-[900px] sm:h-full max-h-[90vh] sm:max-h-[680px] flex-col sm:flex-row rounded-lg border border-border bg-surface-0 shadow-modal animate-modal-in"
    onclick={(e) => e.stopPropagation()}
    onkeydown={() => {}}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Left nav (side on sm+, top tabs on mobile) -->
    <div class="hidden sm:flex w-56 shrink-0 flex-col rounded-l-lg border-r border-border bg-surface-1">
      <div class="px-4 pt-4 pb-4">
        <h2 class="text-sm font-semibold text-text-primary">Settings</h2>
      </div>
      <nav class="flex-1 space-y-0.5 px-3 pb-3">
        {#each sections as section}
          {@const Icon = section.icon}
          {@const isActive = section.id === activeId}
          <button
            onclick={() => (activeId = section.id)}
            class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors {isActive
              ? 'bg-accent-muted text-accent'
              : 'text-text-secondary hover:bg-sidebar-hover hover:text-text-primary'}"
          >
            <Icon size={16} strokeWidth={1.75} class="shrink-0" />
            <span class="truncate">{section.label}</span>
          </button>
        {/each}
      </nav>
    </div>

    <!-- Mobile top tabs (visible below sm) -->
    <div class="flex sm:hidden border-b border-border bg-surface-1 rounded-t-lg overflow-x-auto shrink-0">
      {#each sections as section}
        {@const Icon = section.icon}
        {@const isActive = section.id === activeId}
        <button
          onclick={() => (activeId = section.id)}
          class="flex items-center gap-1.5 whitespace-nowrap px-4 py-3 text-xs font-medium transition-colors border-b-2 {isActive
            ? 'border-accent text-accent'
            : 'border-transparent text-text-secondary hover:text-text-primary'}"
        >
          <Icon size={14} strokeWidth={1.75} class="shrink-0" />
          {section.label}
        </button>
      {/each}
    </div>

    <!-- Right panel -->
    <div class="flex flex-1 flex-col min-w-0">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border px-4 sm:px-6 py-4">
        <h3 class="text-sm font-semibold text-text-primary">
          <span class="sm:hidden">Settings — </span>{sections.find((s) => s.id === activeId)?.label}
        </h3>
        <button
          onclick={onClose}
          aria-label="Close settings"
          class="flex h-7 w-7 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
        >
          <X size={16} strokeWidth={1.75} />
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto px-4 sm:px-6 py-4">
        {#if activeId === 'system'}
          <!-- System Section -->

          <!-- Version header -->
          {#if backendInfo || frontendInfo}
            {@const info = backendInfo || frontendInfo}
            <div class="mb-4 rounded-lg border border-border-subtle bg-surface-1 px-4 py-4">
              <div class="flex items-center justify-between">
                <div>
                  <div class="text-lg font-semibold text-text-primary tracking-tight">
                    Concord
                    <span class="text-accent">v{info?.version || 'dev'}</span>
                  </div>
                  <div class="mt-0.5 text-2xs text-text-tertiary">
                    {info?.environment || 'unknown'} environment
                  </div>
                </div>
                {#if info}
                  <div class="flex items-center gap-1.5">
                    <GitBranch size={14} strokeWidth={1.75} class="text-text-tertiary" />
                    <code class="text-2xs font-mono text-text-secondary">
                      {info.gitCommit?.slice(0, 7) || '?'}
                    </code>
                    {#if info.gitBranch && info.gitBranch !== 'unknown'}
                      <span class="text-2xs text-text-tertiary">({info.gitBranch})</span>
                    {/if}
                    {#if isDirty(info.gitDirty)}
                      <span class="badge badge-warning">dirty</span>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <!-- Build details grid -->
          {#if backendInfo || frontendInfo}
            <div class="mb-4 space-y-3">
              {#each [{ label: 'API Server', info: backendInfo, icon: Server }, { label: 'Frontend', info: frontendInfo, icon: Globe }] as svc}
                {#if svc.info}
                  {@const SvcIcon = svc.icon}
                  <div class="rounded-lg border border-border-subtle px-4 py-3">
                    <div class="mb-2 flex items-center gap-2">
                      <SvcIcon size={14} strokeWidth={1.75} class="text-accent" />
                      <span class="text-xs font-semibold text-text-primary">{svc.label}</span>
                      <span class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-secondary">
                        v{svc.info.version}
                      </span>
                    </div>
                    <div class="grid grid-cols-2 gap-x-6 gap-y-1.5 text-2xs">
                      <div class="flex items-center gap-1.5 text-text-tertiary">
                        <span>Commit</span>
                      </div>
                      <code class="font-mono text-text-secondary">{svc.info.gitCommit?.slice(0, 7) || 'unknown'}</code>

                      <div class="text-text-tertiary">Branch</div>
                      <span class="text-text-secondary">{svc.info.gitBranch || 'unknown'}</span>

                      <div class="text-text-tertiary">Built</div>
                      <span class="text-text-secondary">{formatBuildTime(svc.info.buildTime)}</span>

                      <div class="text-text-tertiary">Build host</div>
                      <span class="text-text-secondary">{svc.info.buildHost || 'unknown'}</span>

                      {#if svc.info.pythonVersion}
                        <div class="text-text-tertiary">Runtime</div>
                        <span class="text-text-secondary">Python {svc.info.pythonVersion} · {svc.info.arch || ''}</span>
                      {/if}

                      {#if svc.info.os}
                        <div class="text-text-tertiary">OS</div>
                        <span class="text-text-secondary">{svc.info.os}</span>
                      {/if}
                    </div>
                  </div>
                {/if}
              {/each}
            </div>
          {:else if buildInfoLoaded}
            <div class="mb-4 rounded-lg border border-border-subtle px-4 py-6 text-center text-sm text-text-tertiary">
              Build information not available.
            </div>
          {/if}

          <!-- Theme preference -->
          <div class="flex items-center justify-between border-t border-border-subtle py-4">
            <div>
              <div class="text-sm font-medium text-text-primary">Theme</div>
              <div class="mt-0.5 text-2xs text-text-tertiary">
                Switch between light and dark mode
              </div>
            </div>
            <button
              onclick={() => theme.toggle()}
              class="btn btn-sm {theme.theme === 'dark'
                ? 'bg-warning-muted text-warning hover:bg-warning-muted border border-border'
                : 'bg-accent-muted text-accent hover:bg-accent-muted border border-border'}"
            >
              {#if theme.theme === 'dark'}
                <Sun size={16} strokeWidth={1.75} />
                <span>Light</span>
              {:else}
                <Moon size={16} strokeWidth={1.75} />
                <span>Dark</span>
              {/if}
            </button>
          </div>
        {:else if activeId === 'permissions'}
          <!-- Permissions Section -->
          <p class="mb-4 text-sm text-text-secondary">
            Your current access level in Concord.
          </p>

          <!-- Permission set badge -->
          <div class="mb-4 flex items-center justify-between rounded-lg border border-border-subtle px-4 py-3">
            <div>
              <div class="text-2xs text-text-tertiary">Permission set</div>
              <div class="mt-0.5 text-sm font-semibold text-text-primary">
                {auth.user?.permissionSetName || 'None assigned'}
              </div>
            </div>
            <span class="rounded-full bg-accent-muted px-2.5 py-0.5 text-2xs font-medium text-accent">
              {auth.user?.permissions?.length ?? 0} permission{(auth.user?.permissions?.length ?? 0) !== 1 ? 's' : ''}
            </span>
          </div>

          <!-- Tree display -->
          {#if auth.user?.permissions && auth.user.permissions.length > 0}
            <div class="rounded-lg border border-border-subtle p-3">
              {#each permTree as node}
                {@render TreeDisplayNode(node, 0)}
              {/each}
            </div>
          {:else}
            <div class="rounded-lg border border-border-subtle px-4 py-6 text-center text-sm text-text-tertiary">
              No permissions assigned. Contact an administrator.
            </div>
          {/if}
        {:else if activeId === 'api-keys'}
          <!-- API Keys Section -->
          <p class="mb-4 text-sm text-text-secondary">
            Create API keys to authenticate programmatic access to Concord. Keys inherit your permissions.
          </p>

          <ErrorAlert message={apiKeyError} />

          <!-- New key display -->
          {#if newKey}
            <div class="mb-4 rounded-lg border border-success bg-success-muted p-4">
              <p class="mb-2 text-sm font-medium text-success">
                API key created. Copy it now — you won't see it again.
              </p>
              <div class="flex items-center gap-2">
                <code class="flex-1 rounded bg-surface-0 px-3 py-2 text-xs font-mono text-text-primary break-all">
                  {newKey}
                </code>
                <button
                  onclick={() => handleCopy(newKey!)}
                  class="shrink-0 rounded-lg border border-border bg-surface-0 p-2 text-text-secondary transition-colors hover:bg-surface-1"
                >
                  {#if copied}
                    <Check size={16} />
                  {:else}
                    <Copy size={16} />
                  {/if}
                </button>
              </div>
              <button
                onclick={() => (newKey = null)}
                class="mt-2 text-2xs text-text-tertiary hover:text-text-secondary"
              >
                Dismiss
              </button>
            </div>
          {/if}

          <!-- Create button / form -->
          <div class="mb-4">
            {#if showCreateKey}
              <form
                onsubmit={handleCreateKey}
                class="card card-sm"
              >
                <div class="grid grid-cols-2 gap-3">
                  <label>
                    <span class="mb-1 block text-2xs font-medium text-text-tertiary">
                      Key name
                    </span>
                    <input
                      type="text"
                      required
                      bind:value={formKeyName}
                      placeholder="e.g. CI Pipeline"
                      class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
                    />
                  </label>
                  <label>
                    <span class="mb-1 block text-2xs font-medium text-text-tertiary">
                      Expires (optional)
                    </span>
                    <input
                      type="date"
                      bind:value={formExpiresAt}
                      class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden"
                    />
                  </label>
                </div>
                <div class="mt-3 flex gap-2">
                  <button
                    type="submit"
                    disabled={submitting}
                    class="btn btn-sm btn-primary"
                  >
                    {submitting ? 'Creating...' : 'Create key'}
                  </button>
                  <button
                    type="button"
                    onclick={() => (showCreateKey = false)}
                    class="btn btn-sm btn-ghost"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            {:else}
              <button
                onclick={() => (showCreateKey = true)}
                class="btn btn-sm btn-secondary"
              >
                <Plus size={16} />
                Create API key
              </button>
            {/if}
          </div>

          <!-- Keys list -->
          {#if apiKeysLoading}
            <div class="py-8 text-center text-sm text-text-tertiary">
              Loading API keys...
            </div>
          {:else if apiKeys.length === 0}
            <div class="py-8 text-center text-sm text-text-tertiary">
              No API keys yet.
            </div>
          {:else}
            <div class="space-y-2">
              {#each apiKeys as k (k.id)}
                <div class="flex items-center justify-between rounded-lg border border-border-subtle px-4 py-3">
                  <div>
                    <div class="text-sm font-medium text-text-primary">{k.name}</div>
                    <div class="mt-0.5 flex items-center gap-3 text-2xs text-text-tertiary">
                      <code class="font-mono">{k.keyPrefix}...</code>
                      <span>Created {formatDate(k.createdAt)}</span>
                      {#if k.expiresAt}
                        <span>Expires {formatDate(k.expiresAt)}</span>
                      {/if}
                      {#if k.lastUsedAt}
                        <span>Last used {formatDate(k.lastUsedAt)}</span>
                      {/if}
                    </div>
                  </div>
                  <button
                    onclick={() => (deleteTarget = { id: k.id, name: k.name })}
                    class="shrink-0 rounded-lg p-2 text-text-tertiary transition-colors hover:bg-error-muted hover:text-error"
                    title="Delete key"
                    aria-label="Delete key"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              {/each}
            </div>
          {/if}

          <ConfirmDeleteDialog
            open={!!deleteTarget}
            entityType="API key"
            entityName={deleteTarget?.name || ''}
            onConfirm={() => {
              handleDeleteKey(deleteTarget!.id);
              deleteTarget = null;
            }}
            onCancel={() => (deleteTarget = null)}
          />

        {:else if activeId === 'secrets'}
          <!-- Secrets Section -->
          <p class="mb-4 text-sm text-text-secondary">
            Manage signing keys and credentials used by the build system and validation stages.
          </p>

          <!-- Add secret form -->
          {#if showSecretForm}
            <div class="mb-4 rounded-lg border border-border bg-surface-1 p-4 space-y-3">
              <div class="grid gap-3 sm:grid-cols-2">
                <div>
                  <label for="secret-name" class="mb-1 block text-2xs font-medium text-text-tertiary">Name</label>
                  <input id="secret-name" type="text" bind:value={secretName} placeholder="e.g. Bench Signing Key"
                    class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden" />
                </div>
                <div>
                  <label for="secret-type" class="mb-1 block text-2xs font-medium text-text-tertiary">Type</label>
                  <select id="secret-type" bind:value={secretType}
                    class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden">
                    <option value="signing_key">Signing Key</option>
                    <option value="ssh_key">SSH Key</option>
                    <option value="api_token">API Token</option>
                  </select>
                </div>
              </div>
              <div>
                <label for="secret-value" class="mb-1 block text-2xs font-medium text-text-tertiary">Value (base64-encoded)</label>
                <textarea id="secret-value" bind:value={secretValue} rows={3} placeholder="Paste base64-encoded key..."
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden resize-none"></textarea>
              </div>
              <div>
                <label for="secret-desc" class="mb-1 block text-2xs font-medium text-text-tertiary">Description (optional)</label>
                <input id="secret-desc" type="text" bind:value={secretDescription} placeholder="What this secret is for"
                  class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden" />
              </div>
              <div class="flex gap-2">
                <button onclick={handleCreateSecret} disabled={secretSaving || !secretName.trim() || !secretValue.trim()}
                  class="btn btn-sm btn-primary">
                  {secretSaving ? 'Saving...' : 'Add Secret'}
                </button>
                <button onclick={() => (showSecretForm = false)}
                  class="btn btn-sm btn-ghost">Cancel</button>
              </div>
            </div>
          {:else}
            <button onclick={() => (showSecretForm = true)}
              class="btn btn-sm btn-primary mb-4">
              <Plus size={14} /> Add Secret
            </button>
          {/if}

          <!-- Secrets list -->
          {#if secretsLoading}
            <p class="text-sm text-text-tertiary">Loading secrets...</p>
          {:else if secrets.length === 0}
            <p class="text-sm text-text-tertiary">No secrets configured. Add signing keys to use with validation stages.</p>
          {:else}
            <div class="space-y-2">
              {#each secrets as secret}
                <div class="flex items-center justify-between rounded-lg border border-border bg-surface-0 px-4 py-3">
                  <div>
                    <div class="flex items-center gap-2">
                      <Lock size={14} class="text-accent" />
                      <span class="text-sm font-medium text-text-primary">{secret.name}</span>
                      <span class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">{secret.type.replace('_', ' ')}</span>
                    </div>
                    {#if secret.description}
                      <p class="mt-1 text-2xs text-text-tertiary">{secret.description}</p>
                    {/if}
                  </div>
                  <button onclick={() => handleDeleteSecret(secret.id, secret.name)}
                    class="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error" title="Delete secret">
                    <Trash2 size={14} />
                  </button>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </div>
    </div>
  </div>
</div>
