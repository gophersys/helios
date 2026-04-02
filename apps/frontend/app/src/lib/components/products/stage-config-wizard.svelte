<script lang="ts">
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import CodeEditor from '$lib/components/ui/code-editor.svelte';
  import {
    ChevronRight, ChevronLeft, Check, CircuitBoard, GitBranch, Key,
    Zap, Clock, Hand, GitPullRequest, GitMerge, Loader2, FlaskConical,
    FileCode, ShieldAlert, ChevronDown, RefreshCw, Power, AlertTriangle, X,
    Play, Square, Terminal, Download, ChevronUp,
  } from 'lucide-svelte';
  import { subscribeCiBuild, type CiBuildLogEvent } from '$lib/services/websocket';
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
  let recipeDirty = $state(false);        // editor content differs from last save
  let recipeSaving = $state(false);
  let recipeSavedVersion = $state<number | null>(null);  // last published version number
  let recipeLastSaved = $state<string | null>(null);
  let recipeMatchesPublished = $state(true);  // true when content === last published
  let recipeValidating = $state(false);
  let recipeValidation = $state<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null);
  let cursorLine = $state(1);
  let cursorCol = $state(1);

  // Test build state
  let testBuildId = $state<string | null>(null);
  let testBuildRunning = $state(false);
  let testBuildStarting = $state(false);
  let testBuildStatus = $state<'idle' | 'running' | 'success' | 'failed'>('idle');
  let testBuildLogs = $state<string[]>([]);
  let testBuildArtifacts = $state<any[]>([]);
  let terminalOpen = $state(false);
  let terminalHeight = $state(192);
  let dragging = $state(false);
  let testBuildContainerImage = $state<string | null>(null);
  let unsubscribeBuild: (() => void) | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let terminalEl: HTMLDivElement | null = $state(null);

  /** Clean up all test build subscriptions and timers */
  function cleanupTestBuild() {
    unsubscribeBuild?.();
    unsubscribeBuild = null;
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
  }

  function startDrag(e: MouseEvent) {
    e.preventDefault();
    dragging = true;
    const startY = e.clientY;
    const startHeight = terminalHeight;
    function onMove(ev: MouseEvent) {
      terminalHeight = Math.max(80, Math.min(600, startHeight + (startY - ev.clientY)));
    }
    function onUp() {
      dragging = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // Dynamic recipe analysis — only matches actual calls, not comments
  function hasCall(script: string, fn: string): boolean {
    // Match function call at start of line (ignoring whitespace), not in comments
    for (const line of script.split('\n')) {
      const trimmed = line.trim();
      if (trimmed.startsWith('#')) continue; // skip comments
      if (trimmed.includes(fn) && !trimmed.startsWith('#')) return true;
    }
    return false;
  }

  const recipeChecks = $derived.by(() => {
    const r = recipe || '';
    return [
      { label: 'Shebang (#!/bin/bash)', ok: r.startsWith('#!/bin/bash') || r.startsWith('#!/usr/bin/env bash'), required: true },
      { label: 'Error handling (set -eo pipefail)', ok: hasCall(r, 'set -eo pipefail'), required: false },
      { label: 'Source Concord SDK', ok: hasCall(r, 'source') && hasCall(r, 'concord-build.sh'), required: true },
      { label: 'Initialize (concord_init)', ok: hasCall(r, 'concord_init'), required: true },
      { label: 'Collect HEX artifacts', ok: hasCall(r, 'concord_collect_hex'), required: false },
      { label: 'Collect CFW artifacts', ok: hasCall(r, 'concord_collect_cfw'), required: false },
      { label: 'Finalize (concord_finalize)', ok: hasCall(r, 'concord_finalize'), required: true },
    ];
  });
  const requiredChecksPassing = $derived(recipeChecks.filter((c) => c.required).every((c) => c.ok));
  const allChecksPassing = $derived(recipeChecks.every((c) => c.ok));

  // Expected outputs based on selected revision's targets
  const expectedOutputs = $derived.by(() => {
    if (!selectedRevision?.targets?.length) return [];
    return selectedRevision.targets.map((t) => ({
      role: t.role,
      soc: t.soc,
      appId: t.appId,
      hasHex: hasCall(recipe, `concord_collect_hex`) && hasCall(recipe, `${t.appId}`),
      hasCfw: hasCall(recipe, `concord_collect_cfw`) && hasCall(recipe, `${t.appId}`),
    }));
  });

  // Known Concord env var values for hover tooltips
  const envVarValues: Record<string, string> = $derived.by(() => {
    const rev = selectedRevision;
    return {
      CONCORD_FW_TYPE: 'app or mfg (set by build system)',
      CONCORD_BOARD: rev?.ckBoardsName || '(selected revision)',
      CONCORD_VARIANT: 'debug / release',
      CONCORD_BRANCH: formBranch || 'main',
      CONCORD_TARGETS: rev?.targets ? JSON.stringify(rev.targets.map((t) => ({ role: t.role, appId: t.appId, soc: t.soc }))) : '[]',
      CONCORD_REPO_DIR: '/workspace/{jobId}/{repo}',
      CONCORD_BUILD_DIR: '/workspace/{jobId}/{repo}/build',
      CONCORD_OUTPUT_DIR: '/workspace/{jobId}/artifacts',
      CONCORD_CONFIG_LOG: 'y or n',
      CONCORD_PRODUCES_HEX: 'true',
      CONCORD_PRODUCES_CFW: 'true',
      CONCORD_COMMIT_SHA: '(commit hash)',
      CONCORD_MATRIX_LABEL: '(e.g., MFG_BASE, FUT_VERBOSE_A)',
      CONCORD_PRODUCT: selectedRevision ? 'alpha' : '(product name)',
    };
  });

  // Branch loading
  let branches = $state<string[]>([]);
  let branchesLoading = $state(false);

  // Fresh secrets (re-fetched when wizard opens, not stale from parent)
  let liveSecrets = $state<Secret[]>([]);
  let secretsLoading = $state(false);

  const stageName = $derived(STAGE_NAMES[stage] || `Stage ${stage}`);
  const stageDesc = $derived(STAGE_DESCRIPTIONS[stage] || '');
  const signingKeys = $derived(liveSecrets.filter((s) => s.type === 'signing_key'));
  const selectedRevision = $derived(revisions.find((r) => r.id === formRevisionId));
  const selectedKey = $derived(liveSecrets.find((s) => s.id === formSigningKeyId));
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
      loadSecrets();
      loadLastTestBuild();
    }
  });

  async function loadLastTestBuild() {
    // Check if there's a recent test build for this product
    try {
      const res = await apiFetch<ApiResponse<any>>(`/v2/builds?limit=10&productId=${productId}`);
      const data = res.data;
      const builds = Array.isArray(data) ? data : data?.data ?? [];
      const testBuild = builds.find((b: any) => b.matrixLabel === 'TEST_BUILD');
      if (!testBuild) return;

      testBuildId = testBuild.id;
      const isActive = testBuild.status === 'BUILDING' || testBuild.status === 'QUEUED' || testBuild.status === 'CLONING';

      // Parse config flags for builder image
      const flags = typeof testBuild.configFlags === 'string' ? JSON.parse(testBuild.configFlags) : testBuild.configFlags;
      const builderImage = flags?._builder_image || null;
      testBuildContainerImage = builderImage;

      testBuildStatus = isActive ? 'running' : testBuild.status === 'SUCCESS' ? 'success' : 'failed';
      testBuildRunning = isActive;
      terminalOpen = true;

      // Build header from job data
      const rev = selectedRevision;
      testBuildLogs = [
        `\x1b[36m▸ Test build ${isActive ? '(in progress)' : testBuild.status}\x1b[0m`,
        `\x1b[36m  Board:      \x1b[0m${testBuild.board}`,
        `\x1b[36m  Revision:   \x1b[0m${rev?.version ?? '?'} (${rev?.ckBoardsName ?? '?'})`,
        `\x1b[36m  Container:  \x1b[0m${builderImage}`,
        `\x1b[36m  Job:        \x1b[0m${testBuild.id}`,
        '',
      ];

      // Load existing build log
      if (testBuild.buildLog) {
        const lines = testBuild.buildLog.split('\n').filter((l: string) => l.length > 0);
        testBuildLogs = [...testBuildLogs, ...lines];
      }

      // Add completion status if finished
      if (!isActive) {
        testBuildLogs = [...testBuildLogs, '',
          `\x1b[${testBuild.status === 'SUCCESS' ? '32' : '31'}m▸ Build ${testBuild.status}${testBuild.durationSeconds ? ` (${testBuild.durationSeconds}s)` : ''}\x1b[0m`
        ];
        loadTestArtifacts();
      } else {
        // Resume polling for active builds
        unsubscribeBuild = subscribeCiBuild(testBuild.id, {
          onLog: (evt: CiBuildLogEvent) => {
            if (testBuildId !== testBuild.id) return;
            const chunk = evt.chunk || '';
            const lines = chunk.split('\n').filter((l) => l.length > 0);
            if (lines.length > 0) {
              testBuildLogs = [...testBuildLogs, ...lines];
              requestAnimationFrame(() => { if (terminalEl) terminalEl.scrollTop = terminalEl.scrollHeight; });
            }
          },
          onComplete: (evt: any) => {
            if (testBuildId !== testBuild.id) return;
            testBuildRunning = false;
            testBuildStatus = evt.status === 'SUCCESS' ? 'success' : 'failed';
            testBuildLogs = [...testBuildLogs, '', `\x1b[${evt.status === 'SUCCESS' ? '32' : '31'}m▸ Build ${evt.status} (${evt.durationSeconds ?? '?'}s)\x1b[0m`];
            if (terminalEl) terminalEl.scrollTop = terminalEl.scrollHeight;
            loadTestArtifacts();
          },
        });
        pollTestBuild(testBuild.id);
      }
    } catch {
      // No previous test build — that's fine
    }
  }

  async function loadSecrets() {
    secretsLoading = true;
    try {
      const res = await apiFetch<ApiResponse<Secret[]>>('/v2/system/secrets');
      liveSecrets = Array.isArray(res.data) ? res.data : (res.data as any)?.data ?? [];
    } catch {
      liveSecrets = [];
    } finally {
      secretsLoading = false;
    }
  }

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
    recipeSavedVersion = null;
    recipeLastSaved = null;
    try {
      // Load published recipe from MinIO (source of truth for builds)
      const res = await apiFetch<ApiResponse<{ content: string }>>(`/v2/products/${productId}/recipe?stage=${stage}`);
      const data = res.data as any;
      recipe = data?.content ?? '';
      if (typeof recipe !== 'string') recipe = '';

      // Get latest version number for display
      const versionsRes = await apiFetch<ApiResponse<any[]>>(`/v2/products/${productId}/recipe/versions?limit=1`);
      const versions = Array.isArray(versionsRes.data) ? versionsRes.data : (versionsRes.data as any)?.data ?? [];
      if (versions.length > 0) {
        recipeSavedVersion = versions[0].version;
      }
    } catch {
      recipe = '';
    } finally {
      recipeLoading = false;
    }
  }

  function toggleTrigger(value: string) {
    if (formTriggerTypes.includes(value)) {
      // Don't allow deselecting the last trigger
      if (formTriggerTypes.length <= 1) return;
      formTriggerTypes = formTriggerTypes.filter((t) => t !== value);
    } else {
      formTriggerTypes = [...formTriggerTypes, value];
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

  // Concord Build SDK autocomplete
  function concordCompletions(context: any) {
    const word = context.matchBefore(/\w*/);
    if (!word || (word.from === word.to && !context.explicit)) return null;
    return {
      from: word.from,
      options: [
        { label: 'concord_init', type: 'function', detail: 'Initialize build environment', info: 'Parse env vars, extract version, fix sysbuild paths, deploy signing keys' },
        { label: 'concord_collect_hex', type: 'function', detail: 'Register .hex artifact', info: 'concord_collect_hex <appId> <file.hex> <role> <processor>' },
        { label: 'concord_collect_cfw', type: 'function', detail: 'Register .cfw artifact', info: 'concord_collect_cfw <appId> <file.cfw> <role> <processor>' },
        { label: 'concord_finalize', type: 'function', detail: 'Generate build manifest', info: 'Creates build.json with all collected artifacts' },
        { label: 'CONCORD_FW_TYPE', type: 'variable', detail: 'app or mfg' },
        { label: 'CONCORD_BOARD', type: 'variable', detail: 'Board name (e.g. alpha_b0)' },
        { label: 'CONCORD_VARIANT', type: 'variable', detail: 'Build variant' },
        { label: 'CONCORD_BRANCH', type: 'variable', detail: 'Git branch' },
        { label: 'CONCORD_TARGETS', type: 'variable', detail: 'JSON array of targets' },
        { label: 'CONCORD_REPO_DIR', type: 'variable', detail: 'Cloned repo path' },
        { label: 'CONCORD_BUILD_DIR', type: 'variable', detail: 'Build output path' },
        { label: 'CONCORD_OUTPUT_DIR', type: 'variable', detail: 'Artifact output path' },
        { label: 'CONCORD_CONFIG_LOG', type: 'variable', detail: 'y/n — enable logging' },
        { label: 'CONCORD_PRODUCES_HEX', type: 'variable', detail: 'true/false' },
        { label: 'CONCORD_PRODUCES_CFW', type: 'variable', detail: 'true/false' },
      ],
    };
  }

  async function startTestBuild(): Promise<void> {
    if (!recipe.trim() || !formRevisionId) return;

    // Full reset — kill old subscriptions, clear state
    cleanupTestBuild();
    testBuildId = null;
    testBuildStarting = true;
    testBuildRunning = false;
    testBuildStatus = 'running';
    testBuildLogs = [];
    testBuildArtifacts = [];
    terminalOpen = true;
    error = null;

    try {
      if (recipeDirty) await saveRecipe();

      const recipeUrl = '/v2/products/' + productId + '/recipe/test-build';
      const res = await api.post(recipeUrl, {
        content: recipe,
        stage,
        boardRevisionId: formRevisionId,
      });
      const data = (res as any).data ?? res;
      const newBuildId = data.buildJobId;
      testBuildId = newBuildId;
      testBuildRunning = true;
      testBuildStarting = false;

      const rev = selectedRevision;
      testBuildLogs = [
        `\x1b[36m▸ Test build started\x1b[0m`,
        `\x1b[36m  Board:      \x1b[0m${data.board}`,
        `\x1b[36m  Revision:   \x1b[0m${rev?.version ?? '?'} (${rev?.ckBoardsName ?? '?'})`,
        `\x1b[36m  Targets:    \x1b[0m${rev?.targets?.map((t: any) => `${t.role}:${t.soc} (AppID ${t.appId})`).join(', ') ?? 'none'}`,
        `\x1b[36m  Container:  \x1b[0mResolving...`,
        `\x1b[36m  Source:     \x1b[0mDraft (editor content)`,
        `\x1b[36m  Job:        \x1b[0m${newBuildId}`,
        '',
      ];

      // Subscribe to WebSocket log stream
      unsubscribeBuild = subscribeCiBuild(newBuildId, {
        onLog: (evt: CiBuildLogEvent) => {
          if (testBuildId !== newBuildId) return; // stale subscription
          const chunk = evt.chunk || '';
          const lines = chunk.split('\n').filter((l) => l.length > 0);
          if (lines.length > 0) {
            testBuildLogs = [...testBuildLogs, ...lines];
            requestAnimationFrame(() => {
              if (terminalEl) terminalEl.scrollTop = terminalEl.scrollHeight;
            });
          }
        },
        onComplete: (evt: any) => {
          if (testBuildId !== newBuildId) return; // stale
          testBuildRunning = false;
          testBuildStatus = evt.status === 'SUCCESS' ? 'success' : 'failed';
          testBuildLogs = [...testBuildLogs, '', `\x1b[${evt.status === 'SUCCESS' ? '32' : '31'}m▸ Build ${evt.status} (${evt.durationSeconds ?? '?'}s)\x1b[0m`];
          if (terminalEl) terminalEl.scrollTop = terminalEl.scrollHeight;
          loadTestArtifacts();
        },
      });

      // Fallback poll — scoped to this specific build ID
      pollTestBuild(newBuildId);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to start test build';
      testBuildStatus = 'failed';
      testBuildStarting = false;
      testBuildRunning = false;
      testBuildLogs = [...testBuildLogs, `\x1b[31m▸ Error: ${error}\x1b[0m`];
    }
  }

  function pollTestBuild(buildId: string) {
    let lastLogLength = 0;

    const poll = async () => {
      // Stop if this build is no longer the active one
      if (testBuildId !== buildId || !testBuildRunning) return;
      try {
        const res = await apiFetch<ApiResponse<any>>(`/v2/builds/${buildId}`);
        const job = res.data;

        // Guard again after async
        if (testBuildId !== buildId) return;

        // Update container image when resolved by build service
        const configFlags = typeof job?.configFlags === 'string' ? JSON.parse(job.configFlags) : job?.configFlags;
        const builderImage = configFlags?._builder_image;
        if (builderImage) {
          testBuildContainerImage = builderImage;
          // Update terminal header line
          if (testBuildLogs[4]?.includes('Resolving...')) {
            testBuildLogs[4] = `\x1b[36m  Container:  \x1b[0m${builderImage}`;
            testBuildLogs = [...testBuildLogs];
          }
        }

        // Show error message if build failed
        if (job?.errorMessage && (job.status === 'FAILED')) {
          const hasError = testBuildLogs.some(l => l.includes(job.errorMessage));
          if (!hasError) {
            testBuildLogs = [...testBuildLogs, `\x1b[31m▸ Error: ${job.errorMessage}\x1b[0m`];
          }
        }

        // Pull logs if WebSocket isn't delivering them
        if (job?.buildLog && job.buildLog.length > lastLogLength) {
          const newChunk = job.buildLog.substring(lastLogLength);
          lastLogLength = job.buildLog.length;
          const lines = newChunk.split('\n').filter((l: string) => l.length > 0);
          if (lines.length > 0) {
            testBuildLogs = [...testBuildLogs, ...lines];
            requestAnimationFrame(() => {
              if (terminalEl) terminalEl.scrollTop = terminalEl.scrollHeight;
            });
          }
        }

        if (job && (job.status === 'SUCCESS' || job.status === 'FAILED' || job.status === 'CANCELLED')) {
          testBuildRunning = false;
          testBuildStatus = job.status === 'SUCCESS' ? 'success' : 'failed';
          testBuildLogs = [...testBuildLogs, '', `\x1b[${job.status === 'SUCCESS' ? '32' : '31'}m▸ Build ${job.status}${job.durationSeconds ? ` (${job.durationSeconds}s)` : ''}\x1b[0m`];
          requestAnimationFrame(() => {
            if (terminalEl) terminalEl.scrollTop = terminalEl.scrollHeight;
          });
          loadTestArtifacts();
          return;
        }
      } catch { /* ignore */ }
      pollTimer = setTimeout(poll, 2000);
    };
    pollTimer = setTimeout(poll, 3000);
  }

  async function loadTestArtifacts() {
    if (!testBuildId) return;
    try {
      const res = await apiFetch<ApiResponse<any[]>>(`/v2/builds/${testBuildId}/artifacts`);
      testBuildArtifacts = Array.isArray(res.data) ? res.data : [];
    } catch {
      testBuildArtifacts = [];
    }
  }

  function stopTestBuild() {
    cleanupTestBuild();
    testBuildRunning = false;
    testBuildStarting = false;
    testBuildStatus = 'failed';
    testBuildLogs = [...testBuildLogs, '\x1b[33m▸ Build stopped by user\x1b[0m'];
    // Clear the build ID so the next run starts fresh
    testBuildId = null;
  }

  /** Classify a log line for visual treatment */
  function classifyLogLine(line: string): 'header' | 'clone' | 'build' | 'sdk' | 'error' | 'normal' {
    const l = line.trim();
    if (l.startsWith('▸') || l.startsWith('\x1b[36m▸')) return 'header';
    if (l.includes('[clone]') || l.startsWith('Cloning into') || l.startsWith('Receiving objects') || l.startsWith('Resolving deltas') || l.includes('Initializing submodules') || l.includes('ready')) return 'clone';
    if (l.includes('concord_init') || l.includes('concord_finalize') || l.includes('Resolved version') || l.includes('Generated build.json') || l.includes('concord_collect')) return 'sdk';
    if (l.toLowerCase().includes('error') || l.toLowerCase().includes('fatal') || l.includes('FAILED')) return 'error';
    return l.includes('west build') || l.includes('ninja') || l.includes('Compiling') || l.includes('Linking') || l.includes('Memory region') ? 'build' : 'normal';
  }

  /** Format ANSI escape codes to HTML spans */
  function ansiToHtml(line: string): string {
    return line
      .replace(/\x1b\[36m/g, '<span style="color:#89dceb">')
      .replace(/\x1b\[32m/g, '<span style="color:#a6e3a1">')
      .replace(/\x1b\[31m/g, '<span style="color:#f38ba8">')
      .replace(/\x1b\[33m/g, '<span style="color:#f9e2af">')
      .replace(/\x1b\[0m/g, '</span>');
  }

  // Processed log lines — filters git noise, adds section headers
  const processedLogs = $derived.by(() => {
    const out: { html: string; type: string }[] = [];
    let inCloneSection = false;
    let cloneLineCount = 0;

    for (const line of testBuildLogs) {
      const cls = classifyLogLine(line);

      if (cls === 'clone') {
        if (!inCloneSection) {
          inCloneSection = true;
          cloneLineCount = 0;
          out.push({ html: '<span style="color:#585b70">── Cloning repositories ──</span>', type: 'section' });
        }
        cloneLineCount++;
        // Only show key clone lines, skip progress (Receiving/Resolving)
        if (line.includes('[clone]') || line.includes('Cloning into') || line.includes('ready')) {
          out.push({ html: '<span style="color:#585b70">' + line.replace(/</g, '&lt;') + '</span>', type: 'clone' });
        }
        continue;
      }

      if (inCloneSection && cls !== 'clone') {
        if (cloneLineCount > 3) {
          out.push({ html: `<span style="color:#585b70">  (${cloneLineCount} lines)</span>`, type: 'clone' });
        }
        inCloneSection = false;
        out.push({ html: '<span style="color:#585b70">── Build output ──</span>', type: 'section' });
      }

      if (cls === 'sdk') {
        out.push({ html: '<span style="color:#89dceb">' + ansiToHtml(line) + '</span>', type: 'sdk' });
      } else if (cls === 'error') {
        out.push({ html: '<span style="color:#f38ba8">' + line.replace(/</g, '&lt;') + '</span>', type: 'error' });
      } else if (cls === 'header') {
        out.push({ html: ansiToHtml(line), type: 'header' });
      } else {
        out.push({ html: ansiToHtml(line), type: 'normal' });
      }
    }
    return out;
  });

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  async function saveRecipe(): Promise<void> {
    // Save = overwrite the working draft in MinIO (no new version)
    if (!recipe.trim() || recipeSaving) return;
    recipeSaving = true;
    error = null;
    try {
      await api.put(`/v2/products/${productId}/recipe?stage=${stage}`, { content: recipe });
      recipeLastSaved = new Date().toLocaleTimeString();
      recipeDirty = false;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to save recipe';
    } finally {
      recipeSaving = false;
    }
  }

  let publishing = $state(false);

  async function publishRecipe(): Promise<void> {
    // Publish = save as a new numbered version (permanent snapshot)
    if (!recipe.trim() || publishing) return;
    publishing = true;
    error = null;
    try {
      // Save draft first
      if (recipeDirty) await saveRecipe();
      // Then create a versioned snapshot
      const res = await api.post(`/v2/products/${productId}/recipe/save`, {
        content: recipe,
        stage,
        changeNote: `Published for Stage ${stage} ${stageName}`,
      });
      const data = (res as any).data ?? res;
      recipeSavedVersion = data?.version ?? null;
      recipeMatchesPublished = true;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to publish recipe';
    } finally {
      publishing = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      if (currentStep === 3 && recipeDirty) saveRecipe();
    }
  }

  async function validateRecipe(): Promise<void> {
    recipeValidating = true;
    recipeValidation = null;
    try {
      const res = await api.post(`/v2/products/${productId}/recipe/validate`, { content: recipe, stage });
      recipeValidation = (res as any).data ?? res;
    } catch {
      // Client-side fallback validation
      const errors: string[] = [];
      const warnings: string[] = [];
      const lines = recipe.trim();
      if (!lines) {
        errors.push('Recipe is empty');
      } else {
        if (!lines.includes('concord_init')) errors.push('Missing concord_init — must be called to initialize the build environment');
        if (!lines.includes('concord_finalize')) errors.push('Missing concord_finalize — must be called to generate the build manifest');
        if (!lines.includes('concord_collect_hex') && !lines.includes('concord_collect_cfw')) {
          warnings.push('No artifact collection — call concord_collect_hex or concord_collect_cfw to register build outputs');
        }
        if (!lines.includes('#!/bin/bash') && !lines.includes('#!/usr/bin/env bash')) {
          warnings.push('Missing shebang (#!/bin/bash) — recommended for portability');
        }
        if (lines.includes('set -e') && !lines.includes('set -eo pipefail')) {
          warnings.push('Consider using set -eo pipefail instead of set -e for better error handling in pipes');
        }
      }
      recipeValidation = { valid: errors.length === 0, errors, warnings };
    } finally {
      recipeValidating = false;
    }
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

      // Save recipe draft if modified (does NOT create a new version)
      if (recipeDirty && recipe.trim()) {
        const recipeUrl = '/v2/products/' + productId + '/recipe?stage=' + stage;
        await api.put(recipeUrl, { content: recipe });
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

<svelte:window onkeydown={handleKeydown} />

<Modal {open} onclose={onClose} size="full" title="" noPadding showCloseButton={false}>
  <div class="flex flex-col h-[90vh]">
    <!-- Header (compact) -->
    <div class="flex items-center gap-3 px-6 py-3 border-b border-border shrink-0">
      <div class="flex items-center justify-center w-9 h-9 rounded-lg bg-accent/10">
        <FlaskConical size={18} class="text-accent" />
      </div>
      <div class="flex-1 min-w-0">
        <h2 class="text-sm font-semibold text-text-primary">
          {config ? 'Edit' : 'Configure'} Stage {stage}: {stageName}
        </h2>
        <p class="text-2xs text-text-tertiary truncate">{stageDesc}</p>
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

    <!-- Step indicator (compact) -->
    <div class="flex items-center gap-2 px-6 py-2.5 border-b border-border-subtle bg-surface-0/50 shrink-0">
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
    <div class="flex-1 overflow-y-auto px-6 py-4">
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

          {#if secretsLoading}
            <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary justify-center">
              <Loader2 size={16} class="animate-spin" /> Loading signing keys...
            </div>
          {:else if signingKeys.length === 0}
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
        <!-- Step 3: Build Recipe — IDE layout: editor + sidebar + terminal -->
        <div class="flex flex-col h-full -my-4 -mx-6">
          <div class="flex flex-1 min-h-0">
            <!-- Left: Editor -->
            <div class="flex-1 flex flex-col min-w-0 border-r border-[#313244]">
              <!-- Status bar -->
              <div class="flex items-center justify-between px-3 py-1 bg-[#181825] border-b border-[#313244] shrink-0">
                <!-- Left: file + version status -->
                <div class="flex items-center gap-2">
                  <FileCode size={12} class="text-[#89b4fa]" />
                  <span class="text-[11px] font-medium text-[#cdd6f4]">build.sh</span>
                  {#if recipeDirty}
                    <span class="text-[9px] px-1.5 py-0.5 rounded bg-[#f9e2af]/15 text-[#f9e2af] font-medium">
                      Unsaved changes
                    </span>
                  {:else if recipeMatchesPublished && recipeSavedVersion}
                    <span class="text-[9px] px-1.5 py-0.5 rounded bg-[#a6e3a1]/10 text-[#a6e3a1] font-medium">
                      Published v{recipeSavedVersion}
                    </span>
                  {:else if recipeLastSaved}
                    <span class="text-[9px] px-1.5 py-0.5 rounded bg-[#89b4fa]/10 text-[#89b4fa] font-medium">
                      Draft{recipeSavedVersion ? ` (v${recipeSavedVersion} + changes)` : ''}
                    </span>
                  {:else if recipe.trim()}
                    <span class="text-[9px] px-1.5 py-0.5 rounded bg-[#313244] text-[#585b70] font-medium">
                      Unpublished
                    </span>
                  {:else}
                    <span class="text-[9px] px-1.5 py-0.5 rounded bg-[#313244] text-[#585b70] font-medium">
                      Empty
                    </span>
                  {/if}
                </div>
                <!-- Right: actions + cursor -->
                <div class="flex items-center gap-1">
                  <button onclick={validateRecipe} disabled={recipeValidating || !recipe.trim()}
                    class="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium text-[#a6adc8] hover:bg-[#313244] disabled:opacity-40" title="Validate SDK usage">
                    {#if recipeValidating}<Loader2 size={10} class="animate-spin" />{:else}<Check size={10} />{/if} Check
                  </button>
                  <button onclick={saveRecipe} disabled={recipeSaving || !recipeDirty || !recipe.trim()}
                    class="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors disabled:opacity-25
                      {recipeDirty ? 'text-[#89b4fa] hover:bg-[#89b4fa]/15' : 'text-[#585b70]'}" title="Save draft (Ctrl+S)">
                    {#if recipeSaving}<Loader2 size={10} class="animate-spin" />{:else}<FileCode size={10} />{/if} Save
                  </button>
                  <button onclick={publishRecipe} disabled={publishing || !recipe.trim() || recipeDirty}
                    class="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium text-[#a6e3a1] hover:bg-[#a6e3a1]/15 transition-colors disabled:opacity-25"
                    title={recipeDirty ? 'Save first, then publish' : `Publish as v${(recipeSavedVersion ?? 0) + 1}`}>
                    {#if publishing}<Loader2 size={10} class="animate-spin" />{:else}<Check size={10} />{/if} Publish
                  </button>
                  <div class="w-px h-3 bg-[#313244] mx-0.5"></div>
                  <button
                    onclick={testBuildRunning ? stopTestBuild : startTestBuild}
                    disabled={testBuildStarting || (!testBuildRunning && !recipe.trim())}
                    class="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-colors disabled:opacity-25
                      {testBuildRunning ? 'text-[#f38ba8] hover:bg-[#f38ba8]/15' : 'text-[#a6e3a1] hover:bg-[#a6e3a1]/15'}"
                    title={testBuildRunning ? 'Stop build' : 'Test build with current editor content (draft)'}
                  >
                    {#if testBuildStarting}
                      <Loader2 size={10} class="animate-spin" />
                    {:else if testBuildRunning}
                      <Square size={10} />
                    {:else}
                      <Play size={10} />
                    {/if}
                    {testBuildRunning ? 'Stop' : 'Run'}
                  </button>
                  <div class="w-px h-3 bg-[#313244] mx-0.5"></div>
                  <span class="text-[9px] text-[#585b70] font-mono">{cursorLine}:{cursorCol}</span>
                </div>
              </div>

              <!-- Editor body -->
              {#if recipeLoading}
                <div class="flex-1 flex items-center justify-center bg-[#1e1e2e]">
                  <Loader2 size={20} class="animate-spin text-[#585b70]" />
                </div>
              {:else if !recipe.trim()}
                <div class="flex-1 flex flex-col items-center justify-center bg-[#1e1e2e] text-center px-6">
                  <FileCode size={28} class="mb-2 text-[#585b70]" />
                  <p class="text-xs text-[#a6adc8]">No build recipe configured</p>
                  <p class="text-[10px] text-[#585b70] mt-1 mb-3">Write a bash script or start from a template.</p>
                  <button
                    onclick={() => {
                      recipe = '#!/bin/bash\nset -eo pipefail\n\n# Source the Concord Build SDK\nsource concord-build.sh\nconcord_init\n\n# Build firmware\n# west build -b $CONCORD_BOARD ...\n\n# Collect artifacts\n# concord_collect_hex <appId> <file.hex> <role> <processor>\n# concord_collect_cfw <appId> <file.cfw> <role> <processor>\n\nconcord_finalize\n';
                      recipeDirty = true;
                      recipeMatchesPublished = false;
                    }}
                    class="flex items-center gap-1.5 rounded bg-[#313244] px-3 py-1.5 text-[11px] font-medium text-[#cdd6f4] hover:bg-[#45475a]"
                  >
                    <FileCode size={12} /> Start with template
                  </button>
                </div>
              {:else}
                <div class="flex-1 min-h-0">
                  <CodeEditor
                    value={recipe}
                    height="100%"
                    completions={concordCompletions}
                    onchange={(v) => { recipe = v; recipeDirty = true; recipeMatchesPublished = false; recipeValidation = null; }}
                    oncursorchange={(l, c) => { cursorLine = l; cursorCol = c; }}
                    class="h-full"
                  />
                </div>
              {/if}
            </div>

            <!-- Right: Sidebar -->
            <div class="w-64 shrink-0 flex flex-col bg-[#181825] text-[#cdd6f4] overflow-y-auto">
              <!-- SDK Requirements -->
              <div class="px-3 py-2.5 border-b border-[#313244]">
                <h4 class="text-[10px] font-semibold uppercase tracking-wider text-[#a6adc8] mb-1.5">SDK Checks</h4>
                <div class="space-y-1">
                  {#each recipeChecks as check}
                    <div class="flex items-center gap-1.5">
                      {#if check.ok}
                        <Check size={10} class="text-[#a6e3a1] shrink-0" />
                      {:else if check.required}
                        <X size={10} class="text-[#f38ba8] shrink-0" />
                      {:else}
                        <div class="w-2.5 h-2.5 rounded-full bg-[#313244] shrink-0"></div>
                      {/if}
                      <span class="text-[10px] {check.ok ? 'text-[#a6adc8]' : check.required ? 'text-[#f38ba8]' : 'text-[#585b70]'} truncate">{check.label}</span>
                    </div>
                  {/each}
                </div>
              </div>

              <!-- Build results OR targets (mutually exclusive) -->
              {#if testBuildStatus === 'success' && testBuildArtifacts.length > 0}
                <!-- Build verified — show artifacts -->
                {@const hexArts = testBuildArtifacts.filter(a => a.artifactType === 'plaintextHex')}
                {@const cfwArts = testBuildArtifacts.filter(a => a.artifactType === 'encryptedCfw')}
                {@const hasManifest = testBuildArtifacts.some(a => a.artifactType === 'manifest')}
                {@const targetCount = selectedRevision?.targets?.length ?? 0}
                <div class="px-3 py-2.5 border-b border-[#313244]">
                  <h4 class="text-[10px] font-semibold uppercase tracking-wider text-[#a6e3a1] mb-2">✓ Build Output</h4>
                  <div class="space-y-1">
                    {#each testBuildArtifacts.filter(a => a.artifactType !== 'log') as art}
                      {@const size = Number(art.sizeBytes || 0)}
                      <div class="flex items-center gap-1.5 text-[10px]">
                        <Check size={9} class="text-[#a6e3a1] shrink-0" />
                        <span class="font-mono text-[#cdd6f4] truncate flex-1">{art.name}</span>
                        <span class="text-[#585b70] shrink-0">{formatBytes(size)}</span>
                      </div>
                    {/each}
                  </div>
                  <div class="mt-2 pt-2 border-t border-[#313244] text-[9px] space-y-0.5">
                    <div class="{hexArts.length >= targetCount ? 'text-[#a6e3a1]' : 'text-[#f9e2af]'}">
                      {hexArts.length >= targetCount ? '✓' : '⚠'} {hexArts.length}/{targetCount} hex · {cfwArts.length}/{targetCount} cfw · {hasManifest ? '✓' : '✗'} manifest
                    </div>
                  </div>
                </div>

                <!-- Next steps -->
                <div class="px-3 py-2.5 border-b border-[#313244]">
                  <h4 class="text-[10px] font-semibold uppercase tracking-wider text-[#89b4fa] mb-1.5">Ready</h4>
                  <div class="space-y-1 text-[9px] text-[#a6adc8]">
                    <div>{recipeMatchesPublished ? '✓ Recipe published' : '→ Publish recipe'}</div>
                    <div>→ Step 4: Save & Enable</div>
                    <div>→ PRs to <span class="font-mono text-[#89b4fa]">{formBranch}</span> trigger builds</div>
                  </div>
                </div>

              {:else if testBuildStatus === 'failed'}
                <div class="px-3 py-2.5 border-b border-[#313244]">
                  <h4 class="text-[10px] font-semibold uppercase tracking-wider text-[#f38ba8] mb-1">✗ Build Failed</h4>
                  <p class="text-[9px] text-[#a6adc8]">Check terminal for errors.</p>
                </div>

              {:else if expectedOutputs.length > 0}
                <!-- Pre-build: show target info -->
                <div class="px-3 py-2.5 border-b border-[#313244]">
                  <h4 class="text-[10px] font-semibold uppercase tracking-wider text-[#a6adc8] mb-1.5">Targets</h4>
                  {#each expectedOutputs as out}
                    <div class="flex items-center gap-2 mb-1 text-[10px]">
                      <span class="text-[#cdd6f4] font-medium capitalize w-12">{out.role}</span>
                      <span class="text-[#585b70] font-mono flex-1">{out.soc}</span>
                      <span class="text-[#585b70] font-mono">{out.appId}</span>
                    </div>
                  {/each}
                </div>
              {/if}

              <!-- Key variables (always visible, compact) -->
              <div class="px-3 py-2.5 flex-1">
                <h4 class="text-[10px] font-semibold uppercase tracking-wider text-[#a6adc8] mb-1.5">Build Context</h4>
                <div class="space-y-0.5 text-[9px]">
                  <div><span class="text-[#585b70]">board</span> <span class="font-mono text-[#89b4fa] ml-1">{selectedRevision?.ckBoardsName ?? '—'}</span></div>
                  <div><span class="text-[#585b70]">branch</span> <span class="font-mono text-[#89b4fa] ml-1">{formBranch}</span></div>
                  <div><span class="text-[#585b70]">type</span> <span class="font-mono text-[#cdd6f4] ml-1">app</span></div>
                  <div><span class="text-[#585b70]">variant</span> <span class="font-mono text-[#cdd6f4] ml-1">debug</span></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Bottom: Terminal Panel (resizable) -->
          <div class="shrink-0 bg-[#11111b]">
            <!-- Drag handle -->
            {#if terminalOpen}
              <div
                onmousedown={startDrag}
                class="h-1 cursor-row-resize border-t border-[#313244] hover:bg-[#89b4fa]/30 transition-colors {dragging ? 'bg-[#89b4fa]/30' : ''}"
                role="separator"
                aria-orientation="horizontal"
              ></div>
            {:else}
              <div class="border-t border-[#313244]"></div>
            {/if}

            <!-- Terminal header -->
            <button
              onclick={() => { terminalOpen = !terminalOpen; if (!terminalOpen) terminalHeight = 192; }}
              class="flex items-center justify-between w-full px-3 py-1 text-[10px] font-medium text-[#a6adc8] hover:bg-[#181825]"
            >
              <div class="flex items-center gap-2">
                <Terminal size={11} />
                <span>Terminal</span>
                {#if testBuildRunning}
                  <span class="flex items-center gap-1 text-[#a6e3a1]"><Loader2 size={9} class="animate-spin" /> Building...</span>
                {:else if testBuildStatus === 'success'}
                  <span class="text-[#a6e3a1]">✓ Build succeeded</span>
                {:else if testBuildStatus === 'failed'}
                  <span class="text-[#f38ba8]">✗ Build failed</span>
                {/if}
                {#if testBuildContainerImage}
                  <span class="text-[#585b70]">·</span>
                  <span class="text-[#585b70] font-mono truncate max-w-[300px]">{testBuildContainerImage}</span>
                {/if}
                {#if testBuildLogs.length > 0}
                  <span class="text-[#585b70]">({testBuildLogs.length} lines)</span>
                {/if}
              </div>
              <ChevronUp size={12} class="transition-transform {terminalOpen ? '' : 'rotate-180'}" />
            </button>

            <!-- Terminal content -->
            {#if terminalOpen}
              <div
                bind:this={terminalEl}
                style="height: {terminalHeight}px"
                class="overflow-y-auto px-3 py-2 font-mono text-[11px] leading-relaxed text-[#cdd6f4]"
              >
                {#if testBuildLogs.length === 0}
                  <div class="text-[#585b70] py-4 text-center">
                    Click <span class="text-[#a6e3a1]">▸ Run</span> in the toolbar to start a test build
                  </div>
                {:else}
                  {#each processedLogs as entry}
                    {#if entry.type === 'section'}
                      <div class="my-1 text-[10px]">{@html entry.html}</div>
                    {:else}
                      <div class="whitespace-pre-wrap break-all {entry.type === 'clone' ? 'text-[10px] opacity-60' : ''}">{@html entry.html}</div>
                    {/if}
                  {/each}
                {/if}
              </div>
            {/if}
          </div>
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

    <!-- Footer (compact) -->
    <div class="flex items-center justify-between px-6 py-3 border-t border-border bg-surface-0/50 shrink-0">
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
