<script lang="ts">
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import {
    ChevronRight, ChevronLeft, Check, CircuitBoard, GitBranch, Key,
    Zap, Clock, Hand, GitPullRequest, GitMerge, Loader2, FlaskConical,
    FileCode, AlertTriangle, ShieldAlert,
  } from 'lucide-svelte';
  import type { ProductStageConfig, Secret } from '$lib/types/stages';
  import { STAGE_NAMES, STAGE_DESCRIPTIONS } from '$lib/types/stages';
  import type { BoardRevision } from '$lib/types/models';
  import { updateStageConfig, createStageConfig } from '$lib/services/stages';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';

  interface Props {
    open: boolean;
    stage: number;
    /** Existing config for this stage+revision combo, or undefined for new */
    config: ProductStageConfig | undefined;
    /** Pre-selected revision (from the stages tab grouping) */
    targetRevision: BoardRevision | null;
    productId: string;
    revisions: BoardRevision[];
    secrets: Secret[];
    onClose: () => void;
    onSaved: () => void;
  }

  let {
    open, stage, config, targetRevision,
    productId, revisions, secrets, onClose, onSaved,
  }: Props = $props();

  // ── Wizard state ───────────────────────────────────────
  let currentStep = $state(1);
  let saving = $state(false);
  let error = $state<string | null>(null);

  // Step 1: Target & Config
  let formRevisionId = $state('');
  let formBranch = $state('main');
  let formTriggerTypes = $state<string[]>(['manual']);

  // Step 2: Signing
  let formSigningKeyId = $state('');

  // Step 3: Build recipe
  let recipe = $state('');
  let recipeLoading = $state(false);
  let recipeDirty = $state(false);

  const stageName = $derived(STAGE_NAMES[stage] || `Stage ${stage}`);
  const stageDesc = $derived(STAGE_DESCRIPTIONS[stage] || '');
  const signingKeys = $derived(secrets.filter((s) => s.type === 'signing_key'));
  const selectedRevision = $derived(revisions.find((r) => r.id === formRevisionId));
  const selectedKey = $derived(secrets.find((s) => s.id === formSigningKeyId));

  // Step gating
  const step1Valid = $derived(!!formRevisionId && formBranch.trim().length > 0);
  const step2Valid = $derived(signingKeys.length === 0 || !!formSigningKeyId);
  const step2Required = $derived(signingKeys.length > 0);

  const triggerOptions = [
    { value: 'pr_push', label: 'Pull Request', icon: GitPullRequest, desc: 'Run when a PR targeting the branch is opened or updated' },
    { value: 'pr_merge', label: 'Merge', icon: GitMerge, desc: 'Run when code is merged into the branch' },
    { value: 'auto', label: 'Auto (after previous)', icon: Zap, desc: 'Automatically run when the previous stage passes' },
    { value: 'schedule', label: 'Schedule', icon: Clock, desc: 'Run on a cron schedule' },
    { value: 'manual', label: 'Manual', icon: Hand, desc: 'Only run when manually triggered' },
  ];

  const defaultTriggers: Record<number, string[]> = {
    1: ['pr_push'], 2: ['auto'], 3: ['auto'], 4: ['schedule'], 5: ['pr_merge', 'manual'],
  };

  // Initialize when wizard opens
  $effect(() => {
    if (open) {
      currentStep = 1;
      error = null;
      recipeDirty = false;
      if (config) {
        formRevisionId = config.boardRevisionId || targetRevision?.id || '';
        formBranch = config.watchBranch || 'main';
        formTriggerTypes = config.triggerTypes?.length ? [...config.triggerTypes] : defaultTriggers[stage] || ['manual'];
        formSigningKeyId = config.signingKeyId || '';
      } else {
        formRevisionId = targetRevision?.id || revisions.find((r) => r.status === 'ACTIVE')?.id || '';
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
    if (currentStep === 1 && !step1Valid) return;
    if (currentStep === 2 && !step2Valid) return;
    if (currentStep < 4) currentStep++;
  }

  function prevStep() {
    if (currentStep > 1) currentStep--;
  }

  async function handleSave(): Promise<void> {
    saving = true;
    error = null;
    try {
      const data = {
        enabled: true,
        boardRevisionId: formRevisionId || null,
        watchBranch: formBranch.trim() || null,
        triggerTypes: formTriggerTypes,
        signingKeyId: formSigningKeyId || null,
      };

      if (config) {
        await updateStageConfig(productId, stage, data);
      } else {
        await createStageConfig(productId, {
          stage,
          name: stageName,
          ...data,
        });
      }

      if (recipeDirty && recipe.trim()) {
        await api.put(`/v2/products/${productId}/recipe`, { content: recipe });
      }

      onSaved();
      onClose();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save stage configuration';
    } finally {
      saving = false;
    }
  }

  const steps = [
    { num: 1, label: 'Target & Triggers' },
    { num: 2, label: 'Signing Key' },
    { num: 3, label: 'Build Recipe' },
    { num: 4, label: 'Review & Save' },
  ];
</script>

<Modal {open} onclose={onClose} size="full" title="" noPadding>
  <div class="flex flex-col h-[85vh]">
    <!-- Header -->
    <div class="flex items-center gap-4 px-8 py-5 border-b border-border shrink-0">
      <div class="flex items-center justify-center w-11 h-11 rounded-xl bg-accent/10">
        <FlaskConical size={22} class="text-accent" />
      </div>
      <div class="flex-1">
        <h2 class="text-lg font-semibold text-text-primary">
          {config ? 'Edit' : 'Configure'} Stage {stage}: {stageName}
        </h2>
        <p class="text-sm text-text-tertiary">{stageDesc}</p>
      </div>
      {#if selectedRevision}
        <div class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-3 py-2">
          <CircuitBoard size={14} class="text-accent" />
          <span class="text-sm font-semibold text-text-primary">{selectedRevision.version}</span>
          <span class="font-mono text-2xs text-text-tertiary">{selectedRevision.ckBoardsName}</span>
        </div>
      {/if}
    </div>

    <!-- Step indicator -->
    <div class="flex items-center gap-3 px-8 py-4 border-b border-border-subtle bg-surface-0/50 shrink-0">
      {#each steps as s}
        {@const isComplete = currentStep > s.num}
        {@const isCurrent = currentStep === s.num}
        {@const isDisabled = (s.num === 2 && !step1Valid) || (s.num === 3 && !step2Valid) || (s.num === 4 && !step2Valid)}
        <button
          onclick={() => { if (!isDisabled && (isComplete || isCurrent)) currentStep = s.num; }}
          disabled={isDisabled && !isComplete}
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
            {isCurrent ? 'bg-accent text-white shadow-sm' :
             isComplete ? 'bg-success-muted text-success' :
             isDisabled ? 'bg-surface-2 text-text-tertiary cursor-not-allowed opacity-50' :
             'bg-surface-2 text-text-tertiary hover:text-text-secondary'}"
        >
          {#if isComplete}
            <Check size={14} />
          {:else}
            <span class="w-5 h-5 flex items-center justify-center rounded-full text-xs border
              {isCurrent ? 'border-white/50' : 'border-text-tertiary/30'}">{s.num}</span>
          {/if}
          {s.label}
        </button>
        {#if s.num < steps.length}
          <div class="h-px flex-1 bg-border-subtle max-w-8" />
        {/if}
      {/each}
    </div>

    <!-- Content area (scrollable) -->
    <div class="flex-1 overflow-y-auto px-8 py-6">
      <ErrorAlert message={error} />

      {#if currentStep === 1}
        <!-- ═══ STEP 1: Target & Triggers ═══ -->
        <div class="max-w-3xl space-y-6">
          <!-- Target revision -->
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Target Hardware Revision</h3>
            <p class="text-2xs text-text-tertiary mb-3">Which board revision to build firmware for and test against.</p>
            <div class="grid gap-2 sm:grid-cols-2">
              {#each revisions.filter(r => r.status === 'ACTIVE' || r.status === 'DRAFT') as rev}
                <button
                  onclick={() => (formRevisionId = rev.id)}
                  class="flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all
                    {formRevisionId === rev.id ? 'border-accent bg-accent-muted shadow-sm' : 'border-border bg-surface-0 hover:border-text-tertiary'}"
                >
                  <CircuitBoard size={20} class={formRevisionId === rev.id ? 'text-accent' : 'text-text-tertiary'} />
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-bold text-text-primary">{rev.version}</span>
                      <StatusBadge status={rev.status} />
                    </div>
                    <div class="font-mono text-2xs text-text-tertiary">{rev.ckBoardsName}</div>
                    {#if rev.targets?.length}
                      <div class="mt-1.5 flex flex-wrap gap-1.5">
                        {#each rev.targets as t}
                          <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">{t.role}: {t.soc}</span>
                        {/each}
                      </div>
                    {/if}
                  </div>
                  {#if formRevisionId === rev.id}
                    <Check size={18} class="text-accent shrink-0" />
                  {/if}
                </button>
              {/each}
            </div>
          </div>

          <!-- Watch branch -->
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Watch Branch</h3>
            <p class="text-2xs text-text-tertiary mb-3">Git branch to monitor for changes. PRs targeting this branch will trigger builds.</p>
            <div class="flex items-center gap-3 max-w-md">
              <GitBranch size={18} class="text-text-tertiary shrink-0" />
              <input
                type="text"
                bind:value={formBranch}
                placeholder="e.g. main, develop, concord-main"
                class="w-full rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
          </div>

          <!-- Triggers -->
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Triggers</h3>
            <p class="text-2xs text-text-tertiary mb-3">What events start this stage. Select all that apply.</p>
            <div class="space-y-2 max-w-2xl">
              {#each triggerOptions as opt}
                {@const TIcon = opt.icon}
                {@const active = formTriggerTypes.includes(opt.value)}
                <button
                  onclick={() => toggleTrigger(opt.value)}
                  class="flex w-full items-center gap-4 rounded-lg border-2 px-4 py-3 text-left transition-all
                    {active ? 'border-accent bg-accent-muted' : 'border-border bg-surface-0 hover:border-text-tertiary'}"
                >
                  <div class="flex items-center justify-center w-9 h-9 rounded-lg {active ? 'bg-accent/15' : 'bg-surface-2'}">
                    <TIcon size={18} class={active ? 'text-accent' : 'text-text-tertiary'} />
                  </div>
                  <div class="flex-1">
                    <div class="text-sm font-medium text-text-primary">{opt.label}</div>
                    <div class="text-2xs text-text-tertiary">{opt.desc}</div>
                  </div>
                  {#if active}
                    <Check size={16} class="text-accent shrink-0" />
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        </div>

      {:else if currentStep === 2}
        <!-- ═══ STEP 2: Signing Key ═══ -->
        <div class="max-w-3xl space-y-6">
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Signing Key</h3>
            <p class="text-2xs text-text-tertiary mb-3">
              The bootloader signing key used to sign firmware artifacts. Required for real hardware builds.
            </p>
          </div>

          {#if signingKeys.length === 0}
            <div class="rounded-xl border-2 border-warning/40 bg-warning-muted px-6 py-5">
              <div class="flex items-center gap-3 mb-2">
                <ShieldAlert size={22} class="text-warning" />
                <span class="text-base font-semibold text-warning">No signing keys configured</span>
              </div>
              <p class="text-sm text-text-secondary">
                Go to <strong>Settings → Secrets</strong> to add a signing key before you can enable builds for this stage.
                Without a signing key, firmware cannot be signed and devices will reject it.
              </p>
            </div>
          {:else}
            <div class="space-y-2">
              {#each signingKeys as secret}
                <button
                  onclick={() => (formSigningKeyId = secret.id)}
                  class="flex w-full items-center gap-4 rounded-lg border-2 px-4 py-4 text-left transition-all
                    {formSigningKeyId === secret.id ? 'border-accent bg-accent-muted shadow-sm' : 'border-border bg-surface-0 hover:border-text-tertiary'}"
                >
                  <div class="flex items-center justify-center w-10 h-10 rounded-lg {formSigningKeyId === secret.id ? 'bg-accent/15' : 'bg-surface-2'}">
                    <Key size={20} class={formSigningKeyId === secret.id ? 'text-accent' : 'text-text-tertiary'} />
                  </div>
                  <div class="flex-1">
                    <div class="text-sm font-semibold text-text-primary">{secret.name}</div>
                    {#if secret.description}
                      <div class="text-2xs text-text-tertiary">{secret.description}</div>
                    {/if}
                  </div>
                  {#if formSigningKeyId === secret.id}
                    <Check size={18} class="text-accent shrink-0" />
                  {/if}
                </button>
              {/each}
            </div>
          {/if}
        </div>

      {:else if currentStep === 3}
        <!-- ═══ STEP 3: Build Recipe ═══ -->
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-text-primary">Build Recipe</h3>
              <p class="text-2xs text-text-tertiary mt-0.5">
                Bash script using the Concord Build SDK. Uses
                <code class="font-mono bg-surface-2 px-1 rounded text-accent">concord_init</code>,
                <code class="font-mono bg-surface-2 px-1 rounded text-accent">concord_collect_hex</code>,
                <code class="font-mono bg-surface-2 px-1 rounded text-accent">concord_finalize</code>.
              </p>
            </div>
            {#if recipeDirty}
              <span class="rounded-full bg-warning-muted px-2.5 py-1 text-2xs font-medium text-warning">Unsaved changes</span>
            {/if}
          </div>

          {#if recipeLoading}
            <div class="flex items-center justify-center py-16">
              <Loader2 size={24} class="animate-spin text-text-tertiary" />
            </div>
          {:else}
            <div class="rounded-lg border border-border overflow-hidden">
              <CodeEditor
                value={recipe}
                height="calc(85vh - 340px)"
                onchange={(v) => { recipe = v; recipeDirty = true; }}
              />
            </div>
          {/if}

          {#if !recipe.trim() && !recipeLoading}
            <div class="rounded-lg border border-border-subtle bg-surface-0 p-6 text-center">
              <FileCode size={28} class="mx-auto mb-2 text-text-tertiary" />
              <p class="text-sm text-text-secondary">No build recipe configured.</p>
              <p class="text-2xs text-text-tertiary mt-1">Skip this step if using TeamCity or an external CI system to upload builds.</p>
            </div>
          {/if}
        </div>

      {:else if currentStep === 4}
        <!-- ═══ STEP 4: Review ═══ -->
        <div class="max-w-3xl space-y-6">
          <h3 class="text-sm font-semibold text-text-primary">Review Configuration</h3>
          <p class="text-2xs text-text-tertiary">Verify your stage settings before saving.</p>

          <div class="rounded-xl border border-border overflow-hidden">
            <div class="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle bg-surface-0/50">
              <span class="text-sm text-text-secondary">Target Revision</span>
              <div class="flex items-center gap-2">
                <CircuitBoard size={14} class="text-accent" />
                <span class="text-sm font-semibold text-text-primary">
                  {selectedRevision ? `${selectedRevision.version} (${selectedRevision.ckBoardsName})` : '—'}
                </span>
              </div>
            </div>
            <div class="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle">
              <span class="text-sm text-text-secondary">Watch Branch</span>
              <span class="font-mono text-sm text-text-primary">{formBranch || '—'}</span>
            </div>
            <div class="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle bg-surface-0/50">
              <span class="text-sm text-text-secondary">Triggers</span>
              <div class="flex gap-1.5">
                {#each formTriggerTypes as t}
                  <span class="rounded-full bg-accent-muted px-2.5 py-0.5 text-2xs font-medium text-accent">{t}</span>
                {/each}
              </div>
            </div>
            <div class="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle">
              <span class="text-sm text-text-secondary">Signing Key</span>
              <span class="text-sm font-medium text-text-primary">{selectedKey?.name || 'None'}</span>
            </div>
            <div class="flex items-center justify-between px-5 py-3.5">
              <span class="text-sm text-text-secondary">Build Recipe</span>
              <span class="text-sm text-text-primary">
                {recipe.trim() ? `${recipe.split('\n').length} lines` : 'Not configured (external CI)'}
                {#if recipeDirty}
                  <span class="text-warning ml-1">(modified)</span>
                {/if}
              </span>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between px-8 py-4 border-t border-border bg-surface-0/50 shrink-0">
      <button
        onclick={currentStep === 1 ? onClose : prevStep}
        class="flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-2 transition-colors"
      >
        <ChevronLeft size={16} />
        {currentStep === 1 ? 'Cancel' : 'Back'}
      </button>

      <div class="flex items-center gap-3">
        {#if currentStep === 1 && !step1Valid}
          <span class="text-2xs text-text-tertiary">Select a revision and branch to continue</span>
        {/if}
        {#if currentStep === 2 && !step2Valid}
          <span class="text-2xs text-warning">A signing key is required</span>
        {/if}

        {#if currentStep < 4}
          <button
            onclick={nextStep}
            disabled={(currentStep === 1 && !step1Valid) || (currentStep === 2 && !step2Valid)}
            class="flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next <ChevronRight size={16} />
          </button>
        {:else}
          <button
            onclick={handleSave}
            disabled={saving}
            class="flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
          >
            {#if saving}
              <Loader2 size={16} class="animate-spin" /> Saving...
            {:else}
              <Check size={16} /> Save & Enable Stage
            {/if}
          </button>
        {/if}
      </div>
    </div>
  </div>
</Modal>
