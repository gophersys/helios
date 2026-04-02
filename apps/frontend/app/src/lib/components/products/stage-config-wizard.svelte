<script lang="ts">
  import { onMount } from 'svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import {
    ChevronRight, ChevronLeft, Check, CircuitBoard, GitBranch, Key,
    Zap, Clock, Hand, GitPullRequest, GitMerge, Loader2, FlaskConical,
    FileCode, AlertTriangle,
  } from 'lucide-svelte';
  import type { ProductStageConfig, Secret } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS } from '$lib/types/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { updateStageConfig } from '$lib/services/stages';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    open: boolean;
    stage: number;
    config: ProductStageConfig | undefined;
    productId: string;
    revisions: BoardRevision[];
    secrets: Secret[];
    onClose: () => void;
    onSaved: () => void;
  }

  let { open, stage, config, productId, revisions, secrets, onClose, onSaved }: Props = $props();

  // Wizard state
  let currentStep = $state(1);
  let saving = $state(false);
  let error = $state<string | null>(null);

  // Step 1: Basic config
  let formEnabled = $state(false);
  let formRevisionId = $state('');
  let formBranch = $state('main');
  let formTriggerTypes = $state<string[]>(['manual']);

  // Step 2: Signing key
  let formSigningKeyId = $state('');

  // Step 3: Build recipe
  let recipe = $state('');
  let recipeLoading = $state(false);
  let recipeDirty = $state(false);

  const stageName = $derived(STAGE_NAMES[stage] || `Stage ${stage}`);
  const stageDesc = $derived(STAGE_DESCRIPTIONS[stage] || '');
  const activeRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE'));

  const triggerOptions = [
    { value: 'pr_push', label: 'Pull Request', icon: GitPullRequest, desc: 'Run when a PR targeting the branch is opened or updated' },
    { value: 'pr_merge', label: 'Merge', icon: GitMerge, desc: 'Run when code is merged into the branch' },
    { value: 'auto', label: 'Auto (after previous)', icon: Zap, desc: 'Automatically run when the previous stage passes' },
    { value: 'schedule', label: 'Schedule', icon: Clock, desc: 'Run on a cron schedule' },
    { value: 'manual', label: 'Manual', icon: Hand, desc: 'Only run when manually triggered' },
  ];

  const defaultTriggers: Record<number, string[]> = {
    1: ['pr_push'],
    2: ['auto'],
    3: ['auto'],
    4: ['schedule'],
    5: ['pr_merge', 'manual'],
  };

  // Initialize form from config when wizard opens
  $effect(() => {
    if (open) {
      currentStep = 1;
      error = null;
      recipeDirty = false;
      if (config) {
        formEnabled = config.enabled;
        formRevisionId = config.boardRevisionId || '';
        formBranch = config.watchBranch || 'main';
        formTriggerTypes = config.triggerTypes?.length ? [...config.triggerTypes] : defaultTriggers[stage] || ['manual'];
        formSigningKeyId = config.signingKeyId || '';
      } else {
        formEnabled = true;
        formRevisionId = activeRevisions[0]?.id || '';
        formBranch = 'main';
        formTriggerTypes = defaultTriggers[stage] || ['manual'];
        formSigningKeyId = '';
      }
      loadRecipe();
    }
  });

  async function loadRecipe() {
    recipeLoading = true;
    try {
      const res = await apiFetch<ApiResponse<{ content: string }>>(`/v2/products/${productId}/recipe`);
      recipe = (res.data as any)?.content ?? res.data ?? '';
      if (typeof recipe !== 'string') recipe = '';
    } catch {
      recipe = '';
    } finally {
      recipeLoading = false;
    }
  }

  function toggleTrigger(value: string) {
    if (formTriggerTypes.includes(value)) {
      formTriggerTypes = formTriggerTypes.filter((t) => t !== value);
      if (formTriggerTypes.length === 0) formTriggerTypes = ['manual'];
    } else {
      formTriggerTypes = [...formTriggerTypes.filter((t) => t !== 'manual'), value];
    }
  }

  function nextStep() {
    if (currentStep < 4) currentStep++;
  }

  function prevStep() {
    if (currentStep > 1) currentStep--;
  }

  async function handleSave(): Promise<void> {
    saving = true;
    error = null;
    try {
      // Save stage config
      await updateStageConfig(productId, stage, {
        enabled: formEnabled,
        boardRevisionId: formRevisionId || null,
        watchBranch: formBranch.trim() || null,
        triggerTypes: formTriggerTypes,
        signingKeyId: formSigningKeyId || null,
      });

      // Save recipe if changed
      if (recipeDirty && recipe.trim()) {
        await api.put(`/v2/products/${productId}/recipe`, {
          content: recipe,
        });
      }

      onSaved();
      onClose();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save stage configuration';
    } finally {
      saving = false;
    }
  }

  const selectedRevision = $derived(revisions.find((r) => r.id === formRevisionId));
  const selectedKey = $derived(secrets.find((s) => s.id === formSigningKeyId));

  const steps = [
    { num: 1, label: 'Configuration' },
    { num: 2, label: 'Signing' },
    { num: 3, label: 'Build Recipe' },
    { num: 4, label: 'Review' },
  ];
</script>

<Modal {open} onclose={onClose} size="xl" title="">
  <!-- Custom header with stage info -->
  <div class="flex items-center gap-3 mb-6">
    <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-accent/10">
      <FlaskConical size={20} class="text-accent" />
    </div>
    <div>
      <h2 class="text-base font-semibold text-text-primary">Configure Stage {stage}: {stageName}</h2>
      <p class="text-2xs text-text-tertiary">{stageDesc}</p>
    </div>
  </div>

  <!-- Step indicator -->
  <div class="flex items-center gap-2 mb-6">
    {#each steps as s}
      <button
        onclick={() => (currentStep = s.num)}
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
          {currentStep === s.num ? 'bg-accent text-white' : currentStep > s.num ? 'bg-success-muted text-success' : 'bg-surface-2 text-text-tertiary'}"
      >
        {#if currentStep > s.num}
          <Check size={12} />
        {:else}
          <span class="w-4 text-center">{s.num}</span>
        {/if}
        <span class="hidden sm:inline">{s.label}</span>
      </button>
      {#if s.num < steps.length}
        <div class="h-px flex-1 bg-border-subtle" />
      {/if}
    {/each}
  </div>

  <ErrorAlert message={error} />

  <!-- Step content -->
  <div class="min-h-[300px]">
    {#if currentStep === 1}
      <!-- Step 1: Configuration -->
      <div class="space-y-4">
        <!-- Enable toggle -->
        <div class="flex items-center justify-between rounded-lg border border-border bg-surface-0 px-4 py-3">
          <div>
            <div class="text-sm font-medium text-text-primary">Enable this stage</div>
            <div class="text-2xs text-text-tertiary">Builds and validation will run when triggered</div>
          </div>
          <button
            onclick={() => (formEnabled = !formEnabled)}
            class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors {formEnabled ? 'bg-accent' : 'bg-surface-3'}"
          >
            <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm {formEnabled ? 'translate-x-6' : 'translate-x-1'}" />
          </button>
        </div>

        <!-- Target revision -->
        <div>
          <label class="mb-1.5 block text-sm font-medium text-text-primary">Target Hardware Revision</label>
          <p class="mb-2 text-2xs text-text-tertiary">Which board revision to build and test against</p>
          <div class="space-y-1.5">
            {#each revisions.filter(r => r.status === 'ACTIVE' || r.status === 'DRAFT') as rev}
              <button
                onclick={() => (formRevisionId = rev.id)}
                class="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                  {formRevisionId === rev.id ? 'border-accent bg-accent-muted' : 'border-border bg-surface-0 hover:bg-surface-2/50'}"
              >
                <CircuitBoard size={16} class={formRevisionId === rev.id ? 'text-accent' : 'text-text-tertiary'} />
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
                    <StatusBadge status={rev.status} />
                    <span class="font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</span>
                  </div>
                  {#if rev.targets?.length}
                    <div class="mt-1 flex gap-2">
                      {#each rev.targets as t}
                        <span class="font-mono text-2xs text-text-secondary">{t.role}: {t.soc} (AppID {t.appId})</span>
                      {/each}
                    </div>
                  {/if}
                </div>
                {#if formRevisionId === rev.id}
                  <Check size={16} class="text-accent" />
                {/if}
              </button>
            {/each}
          </div>
        </div>

        <!-- Watch branch -->
        <div>
          <label for="stage-branch" class="mb-1.5 block text-sm font-medium text-text-primary">Watch Branch</label>
          <p class="mb-2 text-2xs text-text-tertiary">Git branch to monitor for changes</p>
          <div class="flex items-center gap-2">
            <GitBranch size={16} class="text-text-tertiary shrink-0" />
            <input
              id="stage-branch"
              type="text"
              bind:value={formBranch}
              placeholder="e.g. main, develop, concord-main"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        <!-- Trigger types -->
        <div>
          <label class="mb-1.5 block text-sm font-medium text-text-primary">Triggers</label>
          <p class="mb-2 text-2xs text-text-tertiary">What events start this stage</p>
          <div class="space-y-1.5">
            {#each triggerOptions as opt}
              {@const TriggerIcon = opt.icon}
              {@const active = formTriggerTypes.includes(opt.value)}
              <button
                onclick={() => toggleTrigger(opt.value)}
                class="flex w-full items-center gap-3 rounded-lg border px-4 py-2.5 text-left transition-colors
                  {active ? 'border-accent bg-accent-muted' : 'border-border bg-surface-0 hover:bg-surface-2/50'}"
              >
                <TriggerIcon size={16} class={active ? 'text-accent' : 'text-text-tertiary'} />
                <div class="flex-1">
                  <div class="text-sm font-medium text-text-primary">{opt.label}</div>
                  <div class="text-2xs text-text-tertiary">{opt.desc}</div>
                </div>
                {#if active}
                  <Check size={14} class="text-accent" />
                {/if}
              </button>
            {/each}
          </div>
        </div>
      </div>

    {:else if currentStep === 2}
      <!-- Step 2: Signing Key -->
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-text-primary">Signing Key</label>
          <p class="mb-3 text-2xs text-text-tertiary">The bootloader signing key used to sign firmware artifacts for this stage. Managed in Settings → Secrets.</p>

          {#if secrets.length === 0}
            <div class="rounded-lg border border-warning/30 bg-warning-muted px-4 py-3">
              <div class="flex items-center gap-2 text-sm font-medium text-warning">
                <AlertTriangle size={16} />
                No signing keys configured
              </div>
              <p class="mt-1 text-2xs text-text-secondary">Go to Settings → Secrets to add a signing key before enabling builds.</p>
            </div>
          {:else}
            <div class="space-y-1.5">
              <button
                onclick={() => (formSigningKeyId = '')}
                class="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                  {!formSigningKeyId ? 'border-accent bg-accent-muted' : 'border-border bg-surface-0 hover:bg-surface-2/50'}"
              >
                <Key size={16} class={!formSigningKeyId ? 'text-accent' : 'text-text-tertiary'} />
                <div class="flex-1">
                  <div class="text-sm font-medium text-text-primary">No signing key</div>
                  <div class="text-2xs text-text-tertiary">Builds will use development keys (not for production)</div>
                </div>
                {#if !formSigningKeyId}
                  <Check size={14} class="text-accent" />
                {/if}
              </button>
              {#each secrets.filter(s => s.type === 'signing_key') as secret}
                <button
                  onclick={() => (formSigningKeyId = secret.id)}
                  class="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                    {formSigningKeyId === secret.id ? 'border-accent bg-accent-muted' : 'border-border bg-surface-0 hover:bg-surface-2/50'}"
                >
                  <Key size={16} class={formSigningKeyId === secret.id ? 'text-accent' : 'text-text-tertiary'} />
                  <div class="flex-1">
                    <div class="text-sm font-medium text-text-primary">{secret.name}</div>
                    {#if secret.description}
                      <div class="text-2xs text-text-tertiary">{secret.description}</div>
                    {/if}
                  </div>
                  {#if formSigningKeyId === secret.id}
                    <Check size={14} class="text-accent" />
                  {/if}
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>

    {:else if currentStep === 3}
      <!-- Step 3: Build Recipe -->
      <div class="space-y-4">
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-sm font-medium text-text-primary">Build Recipe</label>
            {#if recipeDirty}
              <span class="text-2xs text-warning">Modified</span>
            {/if}
          </div>
          <p class="mb-3 text-2xs text-text-tertiary">
            Bash script using the Concord Build SDK. This recipe is shared across all stages for this product.
            Use <code class="font-mono bg-surface-2 px-1 rounded">concord_init</code>, <code class="font-mono bg-surface-2 px-1 rounded">concord_collect_hex</code>, <code class="font-mono bg-surface-2 px-1 rounded">concord_finalize</code>.
          </p>
        </div>

        {#if recipeLoading}
          <div class="flex items-center justify-center py-8">
            <Loader2 size={20} class="animate-spin text-text-tertiary" />
          </div>
        {:else}
          <div class="rounded-lg border border-border overflow-hidden">
            <CodeEditor
              value={recipe}
              height="350px"
              onchange={(v) => { recipe = v; recipeDirty = true; }}
            />
          </div>
        {/if}

        {#if !recipe.trim() && !recipeLoading}
          <div class="rounded-lg border border-border-subtle bg-surface-0 p-4 text-center">
            <FileCode size={24} class="mx-auto mb-2 text-text-tertiary" />
            <p class="text-sm text-text-secondary">No build recipe configured yet.</p>
            <p class="text-2xs text-text-tertiary mt-1">You can skip this step if using TeamCity or external CI.</p>
          </div>
        {/if}
      </div>

    {:else if currentStep === 4}
      <!-- Step 4: Review -->
      <div class="space-y-4">
        <h3 class="text-sm font-semibold text-text-primary">Review Configuration</h3>

        <div class="rounded-lg border border-border divide-y divide-border-subtle">
          <!-- Enabled -->
          <div class="flex items-center justify-between px-4 py-3">
            <span class="text-sm text-text-secondary">Status</span>
            <StatusBadge status={formEnabled ? 'ACTIVE' : 'DISABLED'} />
          </div>

          <!-- Revision -->
          <div class="flex items-center justify-between px-4 py-3">
            <span class="text-sm text-text-secondary">Target Revision</span>
            <span class="text-sm font-medium text-text-primary">
              {#if selectedRevision}
                {selectedRevision.version} ({selectedRevision.ckBoardsName})
              {:else}
                <span class="text-text-tertiary">None selected</span>
              {/if}
            </span>
          </div>

          <!-- Branch -->
          <div class="flex items-center justify-between px-4 py-3">
            <span class="text-sm text-text-secondary">Watch Branch</span>
            <span class="font-mono text-sm text-text-primary">{formBranch || '—'}</span>
          </div>

          <!-- Triggers -->
          <div class="flex items-center justify-between px-4 py-3">
            <span class="text-sm text-text-secondary">Triggers</span>
            <div class="flex gap-1.5">
              {#each formTriggerTypes as t}
                <span class="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{t}</span>
              {/each}
            </div>
          </div>

          <!-- Signing key -->
          <div class="flex items-center justify-between px-4 py-3">
            <span class="text-sm text-text-secondary">Signing Key</span>
            <span class="text-sm text-text-primary">
              {selectedKey?.name || 'None (dev keys)'}
            </span>
          </div>

          <!-- Recipe -->
          <div class="flex items-center justify-between px-4 py-3">
            <span class="text-sm text-text-secondary">Build Recipe</span>
            <span class="text-sm text-text-primary">
              {recipe.trim() ? `${recipe.split('\n').length} lines` : 'Not configured'}
              {#if recipeDirty}
                <span class="text-2xs text-warning ml-1">(modified)</span>
              {/if}
            </span>
          </div>
        </div>
      </div>
    {/if}
  </div>

  <!-- Footer navigation -->
  <div class="flex items-center justify-between mt-6 pt-4 border-t border-border">
    <button
      onclick={currentStep === 1 ? onClose : prevStep}
      class="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 transition-colors"
    >
      <ChevronLeft size={14} />
      {currentStep === 1 ? 'Cancel' : 'Back'}
    </button>

    {#if currentStep < 4}
      <button
        onclick={nextStep}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover transition-colors"
      >
        Next
        <ChevronRight size={14} />
      </button>
    {:else}
      <button
        onclick={handleSave}
        disabled={saving}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
      >
        {#if saving}
          <Loader2 size={14} class="animate-spin" />
          Saving...
        {:else}
          <Check size={14} />
          Save Configuration
        {/if}
      </button>
    {/if}
  </div>
</Modal>
