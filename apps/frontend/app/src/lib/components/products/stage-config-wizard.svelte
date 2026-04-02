<script lang="ts">
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import {
    ChevronRight, ChevronLeft, Check, CircuitBoard, GitBranch, Key,
    Zap, Clock, Hand, GitPullRequest, GitMerge, Loader2, FlaskConical,
    FileCode, ShieldAlert, ChevronDown, RefreshCw, Power, AlertTriangle, X,
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
    config: ProductStageConfig | undefined;
    targetRevision: BoardRevision | null;
    productId: string;
    fwRepoSlug: string;
    revisions: BoardRevision[];
    secrets: Secret[];
    onClose: () => void;
    onSaved: () => void;
  }

  let {
    open, stage, config, targetRevision,
    productId, fwRepoSlug, revisions, secrets, onClose, onSaved,
  }: Props = $props();

  // ── Wizard state ───────────────────────────────────────
  let currentStep = $state(1);
  let saving = $state(false);
  let error = $state<string | null>(null);

  // Disable confirmation
  let showDisableConfirm = $state(false);
  let disableConfirmText = $state('');
  let disabling = $state(false);
  const disablePhrase = $derived(`disable ${stageName.toLowerCase()}`);
  const canDisable = $derived(disableConfirmText.toLowerCase() === disablePhrase);

  // Step 1
  let formRevisionId = $state('');
  let formBranch = $state('main');
  let formTriggerTypes = $state<string[]>(['manual']);
  let formCronExpression = $state('0 2 * * *');

  // Step 2
  let formSigningKeyId = $state('');

  // Step 3
  let recipe = $state('');
  let recipeLoading = $state(false);
  let recipeDirty = $state(false);

  // Branch loading
  let branches = $state<string[]>([]);
  let branchesLoading = $state(false);

  const stageName = $derived(STAGE_NAMES[stage] || `Stage ${stage}`);
  const stageDesc = $derived(STAGE_DESCRIPTIONS[stage] || '');
  const signingKeys = $derived(secrets.filter((s) => s.type === 'signing_key'));
  const selectedRevision = $derived(revisions.find((r) => r.id === formRevisionId));
  const selectedKey = $derived(secrets.find((s) => s.id === formSigningKeyId));
  const hasSchedule = $derived(formTriggerTypes.includes('schedule'));

  // Revision is locked when the wizard was opened from a specific revision row
  const revisionLocked = $derived(!!targetRevision);

  // Step gating
  const step1Valid = $derived(!!formRevisionId && formBranch.trim().length > 0);
  const step2Valid = $derived(signingKeys.length === 0 || !!formSigningKeyId);

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

      // Lock to target revision if provided
      formRevisionId = targetRevision?.id || config?.boardRevisionId || revisions.find((r) => r.status === 'ACTIVE')?.id || '';

      if (config) {
        formBranch = config.watchBranch || 'main';
        formTriggerTypes = config.triggerTypes?.length ? [...config.triggerTypes] : defaultTriggers[stage] || ['manual'];
        formSigningKeyId = config.signingKeyId || '';
      } else {
        formBranch = 'main';
        formTriggerTypes = defaultTriggers[stage] || ['manual'];
        formSigningKeyId = '';
      }

      loadBranches();
      loadRecipe();
    }
  });

  async function loadBranches() {
    if (!fwRepoSlug) return;
    branchesLoading = true;
    try {
      const res = await apiFetch<ApiResponse<{ branches: string[] }>>(`/v2/products/repos/branches?slug=${fwRepoSlug}`);
      const data = res.data as any;
      branches = data?.branches ?? [];
    } catch {
      branches = [];
    } finally {
      branchesLoading = false;
    }
  }

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

  async function handleDisable(): Promise<void> {
    if (!canDisable || !config) return;
    disabling = true;
    error = null;
    try {
      await updateStageConfig(productId, stage, { enabled: false });
      showDisableConfirm = false;
      disableConfirmText = '';
      onSaved();
      onClose();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to disable stage';
    } finally {
      disabling = false;
    }
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
        await createStageConfig(productId, { stage, name: stageName, ...data });
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
      <div class="flex items-center gap-3">
        {#if selectedRevision}
          <div class="flex items-center gap-2 rounded-lg border border-accent/30 bg-accent-muted px-3 py-2">
            <CircuitBoard size={14} class="text-accent" />
            <span class="text-sm font-semibold text-text-primary">{selectedRevision.version}</span>
            <span class="font-mono text-2xs text-text-tertiary">{selectedRevision.ckBoardsName}</span>
          </div>
        {/if}
        {#if config?.enabled}
          <button
            onclick={() => { showDisableConfirm = true; disableConfirmText = ''; }}
            class="flex items-center gap-2 rounded-lg border-2 border-error/30 bg-error-muted px-4 py-2 text-sm font-medium text-error hover:bg-error/15 transition-colors"
          >
            <Power size={16} />
            Disable Stage
          </button>
        {/if}
      </div>
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

    <!-- Content area -->
    <div class="flex-1 overflow-y-auto px-8 py-6">
      <ErrorAlert message={error} />

      {#if currentStep === 1}
        <div class="max-w-3xl space-y-6">
          <!-- Target revision (locked or selectable) -->
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Target Hardware Revision</h3>
            {#if revisionLocked && selectedRevision}
              <!-- Locked — show confirmed revision -->
              <div class="flex items-center gap-3 rounded-lg border-2 border-accent bg-accent-muted p-4">
                <CircuitBoard size={20} class="text-accent" />
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-bold text-text-primary">{selectedRevision.version}</span>
                    <StatusBadge status={selectedRevision.status} />
                    <span class="font-mono text-2xs text-text-tertiary">{selectedRevision.ckBoardsName}</span>
                  </div>
                  {#if selectedRevision.targets?.length}
                    <div class="mt-1 flex gap-2">
                      {#each selectedRevision.targets as t}
                        <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">{t.role}: {t.soc}</span>
                      {/each}
                    </div>
                  {/if}
                </div>
                <Check size={18} class="text-accent" />
              </div>
            {:else}
              <!-- Selectable -->
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
                    </div>
                    {#if formRevisionId === rev.id}
                      <Check size={18} class="text-accent shrink-0" />
                    {/if}
                  </button>
                {/each}
              </div>
            {/if}
          </div>

          <!-- Watch branch — dropdown from repo -->
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Watch Branch</h3>
            <p class="text-2xs text-text-tertiary mb-3">Git branch to monitor. PRs targeting this branch will trigger builds.</p>
            <div class="flex items-center gap-3 max-w-md">
              <GitBranch size={18} class="text-text-tertiary shrink-0" />
              {#if branchesLoading}
                <div class="flex items-center gap-2 text-sm text-text-tertiary">
                  <Loader2 size={14} class="animate-spin" /> Loading branches...
                </div>
              {:else if branches.length > 0}
                <select
                  bind:value={formBranch}
                  class="w-full rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm font-mono text-text-primary focus:border-accent focus:outline-none appearance-none"
                >
                  {#each branches as branch}
                    <option value={branch}>{branch}</option>
                  {/each}
                </select>
              {:else}
                <!-- Fallback to text input if repo not configured or no branches -->
                <input
                  type="text"
                  bind:value={formBranch}
                  placeholder="e.g. main, master, concord-main"
                  class="w-full rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              {/if}
            </div>
            {#if !fwRepoSlug}
              <p class="mt-1.5 text-2xs text-warning">No firmware repo configured — set it in the product settings to see available branches.</p>
            {/if}
          </div>

          <!-- Triggers -->
          <div>
            <h3 class="text-sm font-semibold text-text-primary mb-1">Triggers</h3>
            <p class="text-2xs text-text-tertiary mb-3">What events start this stage. Select all that apply.</p>
            <div class="space-y-2 max-w-2xl">
              {#each triggerOptions as opt}
                {@const TIcon = opt.icon}
                {@const active = formTriggerTypes.includes(opt.value)}
                <div>
                  <button
                    onclick={() => toggleTrigger(opt.value)}
                    class="flex w-full items-center gap-4 rounded-lg border-2 px-4 py-3 text-left transition-all
                      {active ? 'border-accent bg-accent-muted rounded-b-none' : 'border-border bg-surface-0 hover:border-text-tertiary'}
                      {active && opt.value === 'schedule' ? 'border-b-0' : ''}
                      {active && opt.value === 'pr_push' ? 'border-b-0' : ''}"
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

                  <!-- Inline settings per trigger -->
                  {#if active && opt.value === 'schedule'}
                    <div class="border-2 border-t-0 border-accent bg-accent-muted rounded-b-lg px-4 py-3 ml-0">
                      <label class="block">
                        <span class="mb-1 block text-2xs font-medium text-text-primary">Cron Expression</span>
                        <input
                          type="text"
                          bind:value={formCronExpression}
                          placeholder="0 2 * * *"
                          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                        />
                        <span class="mt-1 block text-2xs text-text-tertiary">
                          Examples: <code class="bg-surface-2 px-1 rounded">0 2 * * *</code> daily 2am ·
                          <code class="bg-surface-2 px-1 rounded">0 */6 * * *</code> every 6h ·
                          <code class="bg-surface-2 px-1 rounded">0 0 * * 1</code> weekly Monday
                        </span>
                      </label>
                    </div>
                  {/if}

                  {#if active && opt.value === 'pr_push'}
                    <div class="border-2 border-t-0 border-accent bg-accent-muted rounded-b-lg px-4 py-3">
                      <span class="text-2xs text-text-secondary">
                        Builds will trigger when PRs target the <strong class="font-mono text-text-primary">{formBranch || 'selected'}</strong> branch above.
                      </span>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        </div>

      {:else if currentStep === 2}
        <!-- Step 2: Signing Key (unchanged) -->
        <div class="max-w-3xl space-y-4">
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
        <!-- Step 3: Build Recipe -->
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-text-primary">Build Recipe</h3>
              <p class="text-2xs text-text-tertiary mt-0.5">
                Bash script using the Concord Build SDK (<code class="font-mono bg-surface-2 px-1 rounded text-accent">concord_init</code>,
                <code class="font-mono bg-surface-2 px-1 rounded text-accent">concord_collect_hex</code>,
                <code class="font-mono bg-surface-2 px-1 rounded text-accent">concord_finalize</code>).
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
        <!-- Step 4: Review -->
        <div class="max-w-3xl space-y-6">
          <h3 class="text-sm font-semibold text-text-primary">Review Configuration</h3>

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
            {#if hasSchedule}
              <div class="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle">
                <span class="text-sm text-text-secondary">Cron Schedule</span>
                <span class="font-mono text-sm text-text-primary">{formCronExpression}</span>
              </div>
            {/if}
            <div class="flex items-center justify-between px-5 py-3.5 border-b border-border-subtle {hasSchedule ? 'bg-surface-0/50' : ''}">
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
          <span class="text-2xs text-text-tertiary">Select a branch to continue</span>
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

<!-- Disable confirmation dialog (AWS-style) -->
{#if showDisableConfirm}
  <div class="fixed inset-0 z-[500] flex items-center justify-center p-4">
    <div class="fixed inset-0 bg-overlay" onclick={() => { showDisableConfirm = false; }} role="presentation" tabindex="-1"></div>
    <div class="relative w-full max-w-md rounded-xl border border-border bg-surface-1 shadow-2xl" role="dialog" aria-modal="true">
      <div class="flex items-center justify-between border-b border-border px-5 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error-muted">
            <AlertTriangle size={20} class="text-error" />
          </div>
          <h2 class="text-sm font-semibold text-text-primary">Disable Stage {stage}: {stageName}</h2>
        </div>
        <button onclick={() => { showDisableConfirm = false; }} class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary">
          <X size={20} />
        </button>
      </div>
      <div class="p-5">
        <p class="mb-4 text-sm text-text-secondary">
          This will disable all builds and validation runs for <strong class="text-text-primary">{stageName}</strong>
          {#if selectedRevision}
            on <strong class="text-text-primary">{selectedRevision.version}</strong>
          {/if}.
          Existing data will be preserved but no new runs will be triggered.
        </p>
        <label for="disable-confirm-input" class="mb-1 block text-2xs font-medium text-text-tertiary">
          Type <span class="font-mono text-error">{disablePhrase}</span> to confirm
        </label>
        <input
          id="disable-confirm-input"
          type="text"
          bind:value={disableConfirmText}
          onkeydown={(e) => { if (e.key === 'Enter' && canDisable) handleDisable(); }}
          placeholder={disablePhrase}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          autofocus
        />
      </div>
      <div class="flex justify-end gap-2 border-t border-border px-5 py-4">
        <button onclick={() => { showDisableConfirm = false; }} class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2">
          Cancel
        </button>
        <button
          onclick={handleDisable}
          disabled={!canDisable || disabling}
          class="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {disabling ? 'Disabling...' : 'Disable Stage'}
        </button>
      </div>
    </div>
  </div>
{/if}
