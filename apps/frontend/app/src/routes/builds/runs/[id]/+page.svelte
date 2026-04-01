<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    AlertTriangle,
    ArrowLeft,
    Check,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Clock,
    Cpu,
    Download,
    ExternalLink,
    FileText,
    FlaskConical,
    GitBranch,
    GitCommit,
    Hammer,
    Loader2,
    Package,
    RefreshCw,
    ShieldCheck,
    X,
    XCircle,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildRunDetail, PipelineBuildSummary, MatrixLabel, ValidationStage } from '$lib/types/ci';
  import { MATRIX_LABEL_DISPLAY, STAGE_DISPLAY } from '$lib/types/ci';
  import { fetchBuildRun, fetchBuildLog, fetchBuildArtifacts, resetBuild, downloadBuildArtifacts, downloadBuildRunArtifacts, downloadSingleArtifact, triggerBuildRunValidation, validateBuildRunArtifacts, fetchBuildRunSessions } from '$lib/services/ci';
  import type { BuildRunSessionSummary, ArtifactValidationReport } from '$lib/services/ci';
  import { getTriggerConfig, getProductInfo } from '$lib/constants/builds';
  import type { BuildArtifact } from '$lib/types/ci';
  import {
    subscribeCiPipeline,
    type CiPipelineCompleteEvent,
  } from '$lib/services/websocket';
  import { formatTimeAgo, formatDateTime, formatDuration, formatSize, ansiToHtml, analyzeBuildLog, type LogAnalysis } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import Skeleton from '$lib/components/ui/skeleton.svelte';

  const auth = getAuth();
  const runId = $derived($page.params.id);

  let buildRun = $state<Pipeline | null>(null);
  let loading = $state(true);
  let initialLoadComplete = $state(false);
  let error = $state<string | null>(null);
  let unsubscribeWs: (() => void) | null = null;
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  // Expandable build logs & artifacts
  let expandedBuilds = $state<Set<string>>(new Set());
  let buildLogs = $state<Record<string, string>>({});
  let buildArtifacts = $state<Record<string, BuildArtifact[]>>({});
  let loadingLogs = $state<Set<string>>(new Set());
  let logContainers = $state<Record<string, HTMLDivElement | null>>({});
  let logPollIntervals = $state<Record<string, ReturnType<typeof setInterval>>>({});
  let logAnalysis = $state<Record<string, LogAnalysis>>({});
  let resettingBuilds = $state<Set<string>>(new Set());
  let downloadingBuilds = $state<Set<string>>(new Set());
  let downloadingArtifacts = $state<Set<string>>(new Set());
  let downloadingAll = $state(false);
  let expandedIssues = $state<Set<string>>(new Set());
  let triggeringValidation = $state(false);
  let validatingArtifacts = $state(false);
  let artifactReport = $state<ArtifactValidationReport | null>(null);
  let showArtifactReport = $state(false);

  // Validation runs triggered from this build run
  let validationRuns = $state<BuildRunSessionSummary[]>([]);

  async function fetchValidationRuns() {
    try {
      validationRuns = await fetchBuildRunSessions(runId);
    } catch {
      // Pipeline may not have sessions yet
    }
  }

  // Can trigger validation: builds have at least some successes and pipeline isn't actively building
  const canTriggerValidation = $derived(
    buildRun &&
    ['SUCCESS', 'FAILED', 'BUILD_FAILED', 'VALIDATING'].includes(buildRun.status ?? '') &&
    buildRun.builds && buildRun.builds.length > 0 &&
    buildRun.builds.some(b => b.status === 'SUCCESS' || b.status === 'CACHED')
  );

  // Check if all builds are complete (success or failed)
  const allBuildsComplete = $derived(
    buildRun?.builds && buildRun.builds.length > 0 &&
    buildRun.builds.every(b => b.status === 'SUCCESS' || b.status === 'FAILED' || b.status === 'CANCELLED')
  );

  // Check if any builds have artifacts
  const hasAnyArtifacts = $derived(
    buildRun?.builds?.some(b => (b.artifactCount ?? 0) > 0) ?? false
  );

  async function handleDownloadBuild(build: PipelineBuildSummary, e: Event): Promise<void> {
    e.stopPropagation();
    if (downloadingBuilds.has(build.id)) return;

    downloadingBuilds.add(build.id);
    downloadingBuilds = new Set(downloadingBuilds);

    try {
      await downloadBuildArtifacts(
        build.id,
        build.product,
        build.variant ?? 'release',
        build.versionString ?? 'build'
      );
    } catch (err) {
      console.error('Failed to download build:', err);
      error = err instanceof Error ? err.message : 'Download failed';
    } finally {
      downloadingBuilds.delete(build.id);
      downloadingBuilds = new Set(downloadingBuilds);
    }
  }

  async function handleDownloadAll(): Promise<void> {
    if (!buildRun || downloadingAll) return;

    downloadingAll = true;

    try {
      await downloadBuildRunArtifacts(
        buildRun.id,
        buildRun.product,
        buildRun.branch
      );
    } catch (err) {
      console.error('Failed to download build run artifacts:', err);
      error = err instanceof Error ? err.message : 'Download failed';
    } finally {
      downloadingAll = false;
    }
  }

  async function handleTriggerValidation(): Promise<void> {
    if (!buildRun || triggeringValidation || !runId) return;
    triggeringValidation = true;
    try {
      await triggerBuildRunValidation(buildRun.id);
      // Refresh pipeline and validation runs list
      buildRun = await fetchBuildRun(runId);
      await fetchValidationRuns();
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to trigger validation';
    } finally {
      triggeringValidation = false;
    }
  }

  async function handleValidateArtifacts(): Promise<void> {
    if (!runId || validatingArtifacts) return;
    validatingArtifacts = true;
    try {
      artifactReport = await validateBuildRunArtifacts(runId);
      showArtifactReport = true;
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to validate artifacts';
    } finally {
      validatingArtifacts = false;
    }
  }

  async function handleDownloadArtifact(buildId: string, artifactName: string, e: Event): Promise<void> {
    e.preventDefault();
    e.stopPropagation();
    const key = `${buildId}:${artifactName}`;
    if (downloadingArtifacts.has(key)) return;

    downloadingArtifacts.add(key);
    downloadingArtifacts = new Set(downloadingArtifacts);

    try {
      await downloadSingleArtifact(buildId, artifactName);
    } catch (err) {
      console.error('Failed to download artifact:', err);
      error = err instanceof Error ? err.message : 'Download failed';
    } finally {
      downloadingArtifacts.delete(key);
      downloadingArtifacts = new Set(downloadingArtifacts);
    }
  }

  async function handleResetBuild(buildId: string, e: Event): Promise<void> {
    e.stopPropagation();
    if (resettingBuilds.has(buildId)) return;

    resettingBuilds.add(buildId);
    resettingBuilds = new Set(resettingBuilds);

    try {
      await resetBuild(buildId);
      // Reload the pipeline to get fresh status
      await loadBuildRun();
    } catch (err) {
      console.error('Failed to reset build:', err);
      error = err instanceof Error ? err.message : 'Failed to reset build';
    } finally {
      resettingBuilds.delete(buildId);
      resettingBuilds = new Set(resettingBuilds);
    }
  }

  const isRunning = $derived(
    buildRun?.status === 'BUILDING' || buildRun?.status === 'PENDING'
  );

  const triggerDisplay = $derived(getTriggerConfig(buildRun?.triggerTypes ?? 'manual'));

  const totalDuration = $derived.by(() => {
    if (!buildRun?.builds) return null;
    const totalSeconds = buildRun.builds.reduce((sum, b) => sum + (b.durationSeconds ?? 0), 0);
    return totalSeconds > 0 ? totalSeconds : null;
  });

  const totalArtifacts = $derived.by(() => {
    if (!buildRun?.builds) return 0;
    return buildRun.builds.reduce((sum, b) => sum + (b.artifactCount ?? 0), 0);
  });

  // Check if this is a stage pipeline with matrix labels (FUOTA has grouped view)
  const isFuota = $derived(buildRun?.matrixMode === 'fuota');
  const stageInfo = $derived(buildRun?.matrixMode ? STAGE_DISPLAY[buildRun.matrixMode as ValidationStage] : null);

  // Group builds by FUOTA step for display (ordered by flow)
  const groupedBuilds = $derived.by(() => {
    if (!buildRun?.builds || !isFuota) return null;

    // Group by fuotaStep, preserving FUOTA flow order
    const stepGroups: Map<number, { title: string; builds: PipelineBuildSummary[] }> = new Map();

    for (const build of buildRun.builds) {
      const label = build.matrixLabel as MatrixLabel;
      const info = label ? MATRIX_LABEL_DISPLAY[label] : null;

      if (info) {
        const step = info.fuotaStep;
        if (!stepGroups.has(step)) {
          stepGroups.set(step, { title: info.groupTitle, builds: [] });
        }
        stepGroups.get(step)!.builds.push(build);
      } else {
        // Other builds without matrix labels
        if (!stepGroups.has(99)) {
          stepGroups.set(99, { title: 'Other Builds', builds: [] });
        }
        stepGroups.get(99)!.builds.push(build);
      }
    }

    // Sort each group by priority (matrixIndex)
    for (const group of stepGroups.values()) {
      group.builds.sort((a, b) => (a.matrixIndex ?? 0) - (b.matrixIndex ?? 0));
    }

    // Return sorted by FUOTA step order
    return Array.from(stepGroups.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([_, group]) => group);
  });

  function getMatrixDisplay(label: string | null | undefined) {
    if (!label) return null;
    return MATRIX_LABEL_DISPLAY[label as MatrixLabel] ?? null;
  }

  // Bitbucket URL construction
  const BITBUCKET_WORKSPACE = 'corekinect';

  function getFwRepo(): string {
    // Use buildMatrix.mainFw when available (most accurate), fall back to product info
    if (pipeline?.buildMatrix?.mainFw) return buildRun?.buildMatrix.mainFw as string;
    const info = getProductInfo(buildRun?.product ?? '');
    return info.repo;
  }

  function getBitbucketCommitUrl(commitSha: string | null): string | null {
    if (!commitSha) return null;
    return `https://bitbucket.org/${BITBUCKET_WORKSPACE}/${getFwRepo()}/commits/${commitSha}`;
  }

  function getBitbucketBranchUrl(branch: string): string | null {
    if (!branch) return null;
    return `https://bitbucket.org/${BITBUCKET_WORKSPACE}/${getFwRepo()}/branch/${encodeURIComponent(branch)}`;
  }

  function scrollLogToBottom(buildId: string): void {
    const container = logContainers[buildId];
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  async function fetchAndUpdateLog(buildId: string, isInitial: boolean = false): Promise<void> {
    if (isInitial) {
      loadingLogs.add(buildId);
      loadingLogs = new Set(loadingLogs);
    }
    try {
      const [log, artifacts] = await Promise.all([
        fetchBuildLog(buildId),
        fetchBuildArtifacts(buildId),
      ]);
      const prevLog = buildLogs[buildId];
      buildLogs[buildId] = log;
      buildLogs = { ...buildLogs };
      buildArtifacts[buildId] = artifacts;
      buildArtifacts = { ...buildArtifacts };

      const analysis = analyzeBuildLog(log);
      logAnalysis[buildId] = analysis;
      logAnalysis = { ...logAnalysis };

      if (isInitial || log !== prevLog) {
        setTimeout(() => scrollLogToBottom(buildId), 50);
      }
    } catch {
      if (isInitial) {
        buildLogs[buildId] = 'Failed to load build log.';
        buildLogs = { ...buildLogs };
      }
    } finally {
      if (isInitial) {
        loadingLogs.delete(buildId);
        loadingLogs = new Set(loadingLogs);
      }
    }
  }

  function startLogPolling(buildId: string, build: { status: string }): void {
    if (build.status === 'BUILDING' || build.status === 'QUEUED') {
      if (!logPollIntervals[buildId]) {
        logPollIntervals[buildId] = setInterval(() => {
          fetchAndUpdateLog(buildId, false);
        }, 1000);
      }
    }
  }

  function stopLogPolling(buildId: string): void {
    if (logPollIntervals[buildId]) {
      clearInterval(logPollIntervals[buildId]);
      delete logPollIntervals[buildId];
    }
  }

  function stopAllLogPolling(): void {
    for (const buildId of Object.keys(logPollIntervals)) {
      stopLogPolling(buildId);
    }
  }

  async function toggleBuildLog(buildId: string, build?: { status: string }): Promise<void> {
    if (expandedBuilds.has(buildId)) {
      expandedBuilds.delete(buildId);
      expandedBuilds = new Set(expandedBuilds);
      stopLogPolling(buildId);
    } else {
      expandedBuilds.add(buildId);
      expandedBuilds = new Set(expandedBuilds);
      await fetchAndUpdateLog(buildId, true);
      if (build) {
        startLogPolling(buildId, build);
      }
    }
  }

  function isFirmwareArtifact(name: string): boolean {
    return name.endsWith('.hex') || name.endsWith('.cfw') || name.endsWith('.bin');
  }

  async function loadBuildRun(isInitial: boolean = false): Promise<void> {
    if (!runId) return;
    try {
      buildRun = await fetchBuildRun(runId);
      error = null;

      // On initial load, pre-fetch log analysis for all completed builds before showing content
      if (isInitial && buildRun?.builds) {
        const completedBuilds = buildRun.builds.filter(
          (b) => b.status === 'SUCCESS' || b.status === 'FAILED'
        );
        if (completedBuilds.length > 0) {
          await Promise.all(
            completedBuilds.map((b) => fetchAndUpdateLog(b.id, false))
          );
        }
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build';
    } finally {
      loading = false;
      if (isInitial) {
        initialLoadComplete = true;
      }
    }
  }

  function setupWebSocket(): void {
    if (!runId) return;
    unsubscribeWs = subscribeCiPipeline(
      runId,
      {
        onStageUpdate: () => { loadBuildRun(); },
        onComplete: (_data: CiPipelineCompleteEvent) => { loadBuildRun(); },
      },
      (msg) => console.warn('Build WS error:', msg)
    );
  }

  function cleanup(): void {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    if (unsubscribeWs) { unsubscribeWs(); unsubscribeWs = null; }
    stopAllLogPolling();
  }

  $effect(() => {
    if (!buildRun?.builds) return;
    for (const build of buildRun.builds) {
      if (expandedBuilds.has(build.id)) {
        if (build.status === 'BUILDING' || build.status === 'QUEUED') {
          startLogPolling(build.id, build);
        } else {
          stopLogPolling(build.id);
          fetchAndUpdateLog(build.id, false);
        }
      }
    }
  });

  // Pre-fetch artifacts for completed builds
  $effect(() => {
    if (!buildRun?.builds) return;
    for (const build of buildRun.builds) {
      if ((build.status === 'SUCCESS' || build.status === 'FAILED') && !logAnalysis[build.id]) {
        fetchAndUpdateLog(build.id, false);
      }
    }
  });

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadBuildRun(true); // Initial load - wait for all data
    fetchValidationRuns();
    setupWebSocket();
    pollInterval = setInterval(() => {
      if (isRunning) loadBuildRun(false); // Refresh - don't block
    }, 5000);
  });

  onDestroy(cleanup);
  beforeNavigate(cleanup);
</script>

<svelte:head>
  <title>Build {runId?.slice(0, 8) ?? ''} - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <button
    onclick={() => goto('/builds')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    All Builds
  </button>

  {#if loading || !initialLoadComplete}
    <!-- Skeleton loading state -->
    <div class="animate-fade-in space-y-6">
      <!-- Header skeleton -->
      <div class="flex items-start justify-between gap-4">
        <div class="space-y-2">
          <div class="flex items-center gap-3">
            <Skeleton width="180px" height="1.5rem" />
            <Skeleton width="80px" height="1.25rem" class="rounded-full" />
          </div>
          <div class="flex items-center gap-4">
            <Skeleton width="120px" height="0.875rem" />
            <Skeleton width="80px" height="0.875rem" />
            <Skeleton width="60px" height="0.875rem" />
          </div>
        </div>
        <Skeleton width="100px" height="2rem" class="rounded" />
      </div>
      <!-- Stats cards skeleton -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {#each [1, 2, 3, 4] as _}
          <div class="card card-sm">
            <Skeleton width="60px" height="0.625rem" class="mb-2" />
            <Skeleton width="80px" height="1.25rem" />
          </div>
        {/each}
      </div>
      <!-- Builds skeleton -->
      <div class="space-y-3">
        <Skeleton width="120px" height="1rem" />
        {#each [1, 2, 3] as _}
          <div class="card p-4 space-y-2">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <Skeleton width="14px" height="14px" />
                <Skeleton width="150px" height="1rem" />
                <Skeleton width="60px" height="1rem" class="rounded-full" />
              </div>
              <Skeleton width="80px" height="0.875rem" />
            </div>
          </div>
        {/each}
      </div>
    </div>
  {:else if error && !buildRun}
    <ErrorAlert message={error} />
  {:else if buildRun}
    <ErrorAlert message={error} />

    <!-- Header -->
    {@const productInfo = getProductInfo(buildRun.product)}
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-lg font-semibold text-text-primary">
            {productInfo.name}
          </h1>
          {#if isRunning}
            <span class="inline-flex items-center gap-1.5 rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
              </span>
              {buildRun.status}
            </span>
          {:else}
            <StatusBadge status={buildRun.status} />
          {/if}
        </div>
        <div class="mt-2 flex items-center gap-2 flex-wrap">
          <!-- Branch card -->
          {#if buildRun.branch}
            {@const branchUrl = getBitbucketBranchUrl(buildRun.branch)}
            <a
              href={branchUrl ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-surface-1 text-xs font-medium text-text-primary hover:bg-surface-2 hover:border-accent transition-colors"
              title="View branch on Bitbucket"
            >
              <GitBranch size={14} class="text-accent" />
              {buildRun.branch}
              {#if branchUrl}
                <ExternalLink size={10} class="text-text-tertiary" />
              {/if}
            </a>
          {/if}
          <!-- Hardware Rev card -->
          {#if productInfo.rev}
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-surface-1 text-xs font-medium text-text-primary">
              <Package size={14} class="text-info" />
              {productInfo.rev}
            </span>
          {/if}
          <!-- Commit badge -->
          {#if buildRun.commitSha}
            {@const commitUrl = getBitbucketCommitUrl(buildRun.commitSha)}
            <a
              href={commitUrl ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-surface-1 text-xs font-mono text-text-primary hover:bg-surface-2 hover:border-accent transition-colors"
              title="View commit on Bitbucket"
            >
              <GitCommit size={14} class="text-warning" />
              {buildRun.commitSha.slice(0, 7)}
              {#if commitUrl}
                <ExternalLink size={10} class="text-text-tertiary" />
              {/if}
            </a>
          {/if}
          <!-- Trigger badge -->
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg {triggerDisplay.color} text-xs font-medium">
            {#if triggerDisplay.icon}{@const TriggerIcon = triggerDisplay.icon}<TriggerIcon size={14} />{/if}
            {triggerDisplay.label}
          </span>
        </div>
      </div>
      <div class="flex items-center gap-3 text-xs text-text-tertiary">
        {#if totalDuration}
          <span class="flex items-center gap-1">
            <Clock size={14} />
            {formatDuration(totalDuration * 1000)}
          </span>
        {/if}
        <span title={formatDateTime(buildRun.createdAt)}>
          {formatTimeAgo(buildRun.createdAt)}
        </span>
        <!-- Validate Artifacts button -->
        {#if hasAnyArtifacts}
          <button
            onclick={handleValidateArtifacts}
            disabled={validatingArtifacts}
            class="btn btn-sm flex items-center gap-1.5"
            title="Validate that all required artifacts are present"
          >
            {#if validatingArtifacts}
              <Loader2 size={14} class="animate-spin" />
            {:else}
              <ShieldCheck size={14} />
            {/if}
            Validate
          </button>
        {/if}
        <!-- Download All button -->
        {#if hasAnyArtifacts}
          <button
            onclick={handleDownloadAll}
            disabled={!allBuildsComplete || downloadingAll}
            class="btn btn-sm btn-accent flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            title={allBuildsComplete ? 'Download all artifacts as ZIP' : 'Waiting for builds to complete'}
          >
            {#if downloadingAll}
              <Loader2 size={14} class="animate-spin" />
            {:else}
              <Download size={14} />
            {/if}
            Download All
          </button>
        {/if}
      </div>
    </div>

    <!-- Metadata cards -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Builds</div>
        <div class="mt-1 flex items-center gap-1.5">
          <Hammer size={16} class="text-text-tertiary" />
          <span class="text-sm font-semibold text-text-primary">
            {buildRun.completedBuilds}/{buildRun.expectedBuilds}
          </span>
        </div>
      </div>
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Duration</div>
        <div class="mt-1 flex items-center gap-1.5">
          <Clock size={16} class="text-text-tertiary" />
          <span class="text-sm font-semibold tabular-nums text-text-primary">
            {totalDuration ? formatDuration(totalDuration * 1000) : '--'}
          </span>
        </div>
      </div>
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Artifacts</div>
        <div class="mt-1 flex items-center gap-1.5">
          <FileText size={16} class="text-text-tertiary" />
          <span class="text-sm font-semibold tabular-nums text-text-primary">{totalArtifacts}</span>
        </div>
      </div>
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Commit</div>
        <div class="mt-1 flex items-center gap-1.5">
          <GitCommit size={16} class="text-text-tertiary" />
          {#if buildRun.commitSha}
            {@const commitUrl = getBitbucketCommitUrl(buildRun.commitSha)}
            {#if commitUrl}
              <a
                href={commitUrl}
                target="_blank"
                rel="noopener noreferrer"
                class="text-sm font-mono text-text-primary hover:text-accent transition-colors inline-flex items-center gap-1"
                title="View commit on Bitbucket"
              >
                {buildRun.commitSha.slice(0, 12)}
                <ExternalLink size={12} />
              </a>
            {:else}
              <span class="text-sm font-mono text-text-primary">{buildRun.commitSha.slice(0, 12)}</span>
            {/if}
          {:else}
            <span class="text-sm text-text-tertiary italic">Manual trigger</span>
          {/if}
        </div>
      </div>
    </div>

    <!-- Validation section -->
    <div class="mb-6 rounded-lg border border-border bg-surface-0 overflow-hidden">
      <div class="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-1">
        <div class="flex items-center gap-3">
          <FlaskConical size={16} class="text-accent" />
          <span class="text-sm font-medium text-text-primary">Validation</span>
          {#if buildRun.autoValidate}
            <span class="inline-flex items-center rounded bg-accent-muted px-1.5 py-0.5 text-2xs font-medium text-accent">
              Auto
            </span>
          {/if}
          {#if buildRun.matrixMode}
            {@const stageInfo = STAGE_DISPLAY[buildRun.matrixMode as ValidationStage]}
            {#if stageInfo}
              <span class="inline-flex items-center rounded {stageInfo.color} px-1.5 py-0.5 text-2xs font-medium">
                {stageInfo.name}
              </span>
            {/if}
          {/if}
        </div>
        <div class="flex items-center gap-2">
          {#if canTriggerValidation}
            <button
              onclick={handleTriggerValidation}
              disabled={triggeringValidation}
              class="btn btn-sm btn-primary flex items-center gap-1.5 text-2xs"
            >
              {#if triggeringValidation}
                <Loader2 size={12} class="animate-spin" />
                Triggering...
              {:else}
                <FlaskConical size={12} />
                {validationRuns.length > 0 ? 'Re-run' : 'Run Validation'}
              {/if}
            </button>
          {:else if buildRun.status === 'BUILDING' || buildRun.status === 'PENDING'}
            <span class="text-2xs text-text-tertiary">Waiting for builds...</span>
          {/if}
        </div>
      </div>
      <!-- Validation runs list -->
      {#if validationRuns.length > 0}
        <div class="divide-y divide-border">
          {#each validationRuns as vr (vr.id)}
            <a href="/validation/runs/{vr.id}" class="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-1 transition-colors">
              <StatusBadge status={vr.status} />
              <span class="text-xs font-medium text-text-primary truncate flex-1 min-w-0">{vr.name}</span>
              <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary flex-shrink-0">
                {buildRun.autoValidate ? 'Auto' : 'Manual'}
              </span>
              {#if vr.passedCount > 0}
                <span class="flex items-center gap-1 text-2xs text-success flex-shrink-0">
                  <CheckCircle2 size={10} />
                  {vr.passedCount}
                </span>
              {/if}
              {#if vr.failedCount > 0}
                <span class="flex items-center gap-1 text-2xs text-error flex-shrink-0">
                  <XCircle size={10} />
                  {vr.failedCount}
                </span>
              {/if}
              {#if vr.startedAt}
                <span class="text-2xs text-text-tertiary flex-shrink-0">{formatTimeAgo(vr.startedAt)}</span>
              {/if}
              <ExternalLink size={10} class="text-text-tertiary flex-shrink-0" />
            </a>
          {/each}
        </div>
      {:else}
        <div class="px-4 py-3 text-xs text-text-tertiary">No validation runs yet</div>
      {/if}
    </div>

    <!-- Builds section -->
    {#if buildRun.builds && buildRun.builds.length > 0}
      <div class="mb-6 min-w-0 overflow-hidden">
        <h2 class="mb-3 text-sm font-medium text-text-primary flex items-center gap-2">
          <Hammer size={16} class="text-text-tertiary" />
          Build Jobs
          {#if stageInfo}
            <span class="text-2xs px-1.5 py-0.5 rounded {stageInfo.color} font-medium" title={stageInfo.description}>{stageInfo.name}</span>
          {/if}
        </h2>

        {#if isFuota && groupedBuilds}
          <!-- FUOTA grouped view (FUOTA flow order) -->
          <div class="space-y-4 min-w-0">
            {#each groupedBuilds as group, groupIdx (group.title)}
              <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
                <div class="px-4 py-2 bg-surface-2 border-b border-border flex items-center gap-2">
                  <span class="text-xs font-medium text-text-primary">{group.title}</span>
                  <span class="text-2xs text-text-tertiary">({group.builds.length} builds)</span>
                  <!-- Show group status summary -->
                  {#if group.builds.every(b => b.status === 'SUCCESS')}
                    <span class="ml-auto text-2xs text-success">All complete</span>
                  {:else if group.builds.some(b => b.status === 'FAILED')}
                    <span class="ml-auto text-2xs text-error">{group.builds.filter(b => b.status === 'FAILED').length} failed</span>
                  {:else if group.builds.some(b => b.status === 'BUILDING')}
                    <span class="ml-auto text-2xs text-warning">{group.builds.filter(b => b.status === 'BUILDING').length} building</span>
                  {/if}
                </div>
                <div class="divide-y divide-border">
                  {#each group.builds as build (build.id)}
                    {@const isExpanded = expandedBuilds.has(build.id)}
                    {@const isLoadingLog = loadingLogs.has(build.id)}
                    {@const analysis = logAnalysis[build.id]}
                    {@const artifacts = buildArtifacts[build.id] ?? []}
                    {@const matrixInfo = getMatrixDisplay(build.matrixLabel)}
                    <div class="overflow-hidden max-w-full">
                      <button
                        onclick={() => toggleBuildLog(build.id, build)}
                        class="w-full p-3 text-left hover:bg-surface-1 transition-colors overflow-x-hidden"
                      >
                        <div class="flex items-center justify-between gap-4">
                          <div class="flex items-center gap-2 min-w-0 flex-1">
                            {#if isExpanded}
                              <ChevronDown size={14} class="text-text-tertiary flex-shrink-0" />
                            {:else}
                              <ChevronRight size={14} class="text-text-tertiary flex-shrink-0" />
                            {/if}
                            <!-- Build info -->
                            <span class="text-xs font-medium text-text-primary flex-shrink-0">
                              {build.product || 'Unknown'}
                            </span>
                            <span class="inline-flex items-center rounded bg-surface-2 px-1 py-0.5 text-2xs text-text-secondary font-mono flex-shrink-0">
                              {build.variant}
                            </span>
                            {#if build.commitSha}
                              <span class="inline-flex items-center rounded bg-info-muted px-1 py-0.5 text-2xs text-info font-mono font-medium flex-shrink-0">
                                {build.commitSha.slice(0, 7)}
                              </span>
                            {/if}
                            {#if build.versionString}
                              <span class="inline-flex items-center rounded bg-accent-muted px-1 py-0.5 text-2xs text-accent font-mono font-medium flex-shrink-0">
                                v{build.versionString}
                              </span>
                            {/if}
                            <StatusBadge status={build.status} />
                            {#if build.status === 'CACHED' && build.reusedFromId}
                              <a
                                href="/builds/{build.reusedFromId}"
                                onclick={(e) => e.stopPropagation()}
                                class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 text-text-tertiary text-2xs hover:text-accent transition-colors flex-shrink-0"
                                title="View original build"
                              >
                                View Original
                              </a>
                            {/if}
                            {#if build.versionBump}
                              <span class="text-2xs text-info px-1 py-0.5 rounded bg-info-muted flex-shrink-0" title="Version bump (+1 from base)">+1</span>
                            {/if}
                            {#if build.status === 'BUILDING' || build.status === 'FAILED'}
                              <button
                                onclick={(e) => handleResetBuild(build.id, e)}
                                disabled={resettingBuilds.has(build.id)}
                                class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium hover:bg-warning/20 transition-colors disabled:opacity-50"
                                title="Reset build to QUEUED (re-run)"
                              >
                                <RefreshCw size={10} class={resettingBuilds.has(build.id) ? 'animate-spin' : ''} />
                                Reset
                              </button>
                            {/if}
                            {#if build.status === 'SUCCESS' && (build.artifactCount ?? 0) > 0}
                              <button
                                onclick={(e) => handleDownloadBuild(build, e)}
                                disabled={downloadingBuilds.has(build.id)}
                                class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent text-surface-0 text-2xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
                                title="Download build artifacts"
                              >
                                {#if downloadingBuilds.has(build.id)}
                                  <Loader2 size={10} class="animate-spin" />
                                {:else}
                                  <Download size={10} />
                                {/if}
                                Download
                              </button>
                            {/if}
                          </div>
                          <div class="flex items-center gap-2 text-2xs text-text-tertiary flex-shrink-0">
                            {#if analysis?.errorCount}
                              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-error-muted text-error font-medium">
                                <XCircle size={10} />
                                {analysis.errorCount}
                              </span>
                            {/if}
                            {#if analysis?.warningCount}
                              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning font-medium">
                                <AlertTriangle size={10} />
                                {analysis.warningCount}
                              </span>
                            {/if}
                            {#if build.durationSeconds}
                              <span class="flex items-center gap-1">
                                <Clock size={12} />
                                {formatDuration(build.durationSeconds * 1000)}
                              </span>
                            {/if}
                            <span class="tabular-nums">#{build.buildNum}</span>
                          </div>
                        </div>
                      </button>
                      {#if isExpanded}
                        <div class="border-t border-border bg-surface-1 p-4 overflow-x-hidden max-w-full">
                          {#if isLoadingLog}
                            <div class="flex items-center justify-center py-8 text-text-tertiary">
                              <Loader2 size={20} class="animate-spin mr-2" />
                              Loading...
                            </div>
                          {:else}
                            <!-- Artifacts section -->
                            {#if artifacts.length > 0}
                              <div class="mb-4">
                                <h4 class="text-xs font-medium text-text-primary mb-2 flex items-center gap-1.5">
                                  <FileText size={14} />
                                  Artifacts ({artifacts.length})
                                </h4>
                                <div class="grid gap-2 sm:grid-cols-2">
                                  {#each artifacts as artifact (artifact.id)}
                                    {@const isDownloading = downloadingArtifacts.has(`${build.id}:${artifact.name}`)}
                                    <button
                                      onclick={(e) => handleDownloadArtifact(build.id, artifact.name, e)}
                                      disabled={isDownloading}
                                      class="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-border bg-surface-0 hover:bg-surface-2 transition-colors text-left disabled:opacity-50"
                                    >
                                      <div class="flex items-center gap-2 min-w-0">
                                        <FileText size={14} class="flex-shrink-0 text-text-tertiary" />
                                        <span class="text-xs font-mono text-text-primary truncate">{artifact.name}</span>
                                      </div>
                                      <div class="flex items-center gap-2 flex-shrink-0">
                                        <span class="text-2xs text-text-tertiary">{formatSize(String(artifact.sizeBytes))}</span>
                                        {#if isDownloading}
                                          <Loader2 size={14} class="text-accent animate-spin" />
                                        {:else}
                                          <Download size={14} class="text-accent" />
                                        {/if}
                                      </div>
                                    </button>
                                  {/each}
                                </div>
                              </div>
                            {/if}

                            <!-- Error/Warning Summary Panel -->
                            {#if analysis && (analysis.errorCount > 0 || analysis.warningCount > 0)}
                              {@const issuesOpen = expandedIssues.has(build.id)}
                              <div class="mb-4 rounded-lg border border-border bg-surface-0 overflow-hidden">
                                <button
                                  class="w-full px-3 py-2 bg-surface-2 flex items-center gap-3 hover:bg-surface-1 transition-colors"
                                  onclick={(e) => { e.stopPropagation(); if (expandedIssues.has(build.id)) { expandedIssues.delete(build.id); } else { expandedIssues.add(build.id); } expandedIssues = new Set(expandedIssues); }}
                                >
                                  {#if issuesOpen}
                                    <ChevronDown size={12} class="text-text-tertiary transition-transform" />
                                  {:else}
                                    <ChevronRight size={12} class="text-text-tertiary transition-transform" />
                                  {/if}
                                  <span class="text-xs font-medium text-text-primary">Build Issues</span>
                                  {#if analysis.errorCount > 0}
                                    <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-error-muted text-error text-2xs font-medium">
                                      <XCircle size={10} />
                                      {analysis.errorCount} error{analysis.errorCount > 1 ? 's' : ''}
                                    </span>
                                  {/if}
                                  {#if analysis.warningCount > 0}
                                    <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium">
                                      <AlertTriangle size={10} />
                                      {analysis.warningCount} warning{analysis.warningCount > 1 ? 's' : ''}
                                    </span>
                                  {/if}
                                </button>
                                {#if issuesOpen}
                                <div class="p-3 max-h-48 overflow-y-auto">
                                  {#if analysis.errors.length > 0}
                                    <div class="mb-3">
                                      <h5 class="text-2xs font-medium text-error mb-1.5 flex items-center gap-1">
                                        <XCircle size={12} />
                                        Errors
                                      </h5>
                                      <div class="space-y-1">
                                        {#each analysis.errors.slice(0, 10) as error}
                                          <div class="text-2xs font-mono text-text-secondary bg-error-muted/50 rounded px-2 py-1 break-all">
                                            {error}
                                          </div>
                                        {/each}
                                        {#if analysis.errors.length > 10}
                                          <div class="text-2xs text-text-tertiary">...and {analysis.errors.length - 10} more</div>
                                        {/if}
                                      </div>
                                    </div>
                                  {/if}
                                  {#if analysis.warnings.length > 0}
                                    <div>
                                      <h5 class="text-2xs font-medium text-warning mb-1.5 flex items-center gap-1">
                                        <AlertTriangle size={12} />
                                        Warnings
                                      </h5>
                                      <div class="space-y-1">
                                        {#each analysis.warnings.slice(0, 10) as warning}
                                          <div class="text-2xs font-mono text-text-secondary bg-warning-muted/50 rounded px-2 py-1 break-all">
                                            {warning}
                                          </div>
                                        {/each}
                                        {#if analysis.warnings.length > 10}
                                          <div class="text-2xs text-text-tertiary">...and {analysis.warnings.length - 10} more</div>
                                        {/if}
                                      </div>
                                    </div>
                                  {/if}
                                </div>
                                {/if}
                              </div>
                            {/if}

                            <!-- Log section -->
                            {#if buildLogs[build.id]}
                              <div>
                                <div class="flex items-center justify-between mb-2">
                                  <h4 class="text-xs font-medium text-text-primary">Build Log</h4>
                                </div>
                                <div
                                  bind:this={logContainers[build.id]}
                                  class="text-xs font-mono text-text-secondary whitespace-pre-wrap max-h-60 overflow-y-auto bg-surface-0 rounded-lg border border-border p-3 leading-relaxed break-all"
                                >{@html ansiToHtml(buildLogs[build.id])}</div>
                              </div>
                            {:else}
                              <p class="text-xs text-text-tertiary text-center py-4">No log available.</p>
                            {/if}
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <!-- Legacy flat view -->
          <div class="space-y-3 min-w-0">
            {#each buildRun.builds as build (build.id)}
            {@const isExpanded = expandedBuilds.has(build.id)}
            {@const isLoadingLog = loadingLogs.has(build.id)}
            {@const analysis = logAnalysis[build.id]}
            {@const artifacts = buildArtifacts[build.id] ?? []}
            {@const firmwareArtifacts = artifacts.filter(a => isFirmwareArtifact(a.name))}
            <div class="rounded-lg border border-border bg-surface-0 overflow-hidden max-w-full">
              <!-- Build header -->
              <button
                onclick={() => toggleBuildLog(build.id, build)}
                class="w-full p-4 text-left hover:bg-surface-1 transition-colors overflow-x-hidden"
              >
                <div class="flex items-center justify-between gap-4 mb-2">
                  <div class="flex items-center gap-2 min-w-0 flex-1">
                    {#if isExpanded}
                      <ChevronDown size={14} class="text-text-tertiary flex-shrink-0" />
                    {:else}
                      <ChevronRight size={14} class="text-text-tertiary flex-shrink-0" />
                    {/if}
                    <Package size={16} class="text-text-tertiary flex-shrink-0" />
                    <span class="text-sm font-medium text-text-primary truncate">{build.product}</span>
                    <StatusBadge status={build.status} />
                    {#if build.variant}
                      <span class="text-2xs text-text-tertiary px-1.5 py-0.5 rounded bg-surface-2 flex-shrink-0">
                        {build.variant}
                      </span>
                    {/if}
                    {#if build.versionString}
                      <span class="text-2xs font-mono text-text-secondary flex-shrink-0">v{build.versionString}</span>
                    {/if}
                    {#if build.status === 'BUILDING' || build.status === 'FAILED'}
                      <button
                        onclick={(e) => handleResetBuild(build.id, e)}
                        disabled={resettingBuilds.has(build.id)}
                        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium hover:bg-warning/20 transition-colors disabled:opacity-50"
                        title="Reset build to QUEUED (re-run)"
                      >
                        <RefreshCw size={10} class={resettingBuilds.has(build.id) ? 'animate-spin' : ''} />
                        Reset
                      </button>
                    {/if}
                    {#if build.status === 'SUCCESS' && (build.artifactCount ?? 0) > 0}
                      <button
                        onclick={(e) => handleDownloadBuild(build, e)}
                        disabled={downloadingBuilds.has(build.id)}
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent text-surface-0 text-2xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
                        title="Download build artifacts"
                      >
                        {#if downloadingBuilds.has(build.id)}
                          <Loader2 size={10} class="animate-spin" />
                        {:else}
                          <Download size={10} />
                        {/if}
                        Download
                      </button>
                    {/if}
                  </div>
                  <div class="flex items-center gap-2 text-2xs text-text-tertiary flex-shrink-0">
                    {#if analysis?.errorCount}
                      <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-error-muted text-error font-medium">
                        <XCircle size={10} />
                        {analysis.errorCount}
                      </span>
                    {/if}
                    {#if analysis?.warningCount}
                      <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning font-medium">
                        <AlertTriangle size={10} />
                        {analysis.warningCount}
                      </span>
                    {/if}
                    {#if build.durationSeconds}
                      <span class="flex items-center gap-1">
                        <Clock size={12} />
                        {formatDuration(build.durationSeconds * 1000)}
                      </span>
                    {/if}
                    <span class="tabular-nums">#{build.buildNum}</span>
                  </div>
                </div>
              </button>

              {#if isExpanded}
                <div class="border-t border-border bg-surface-1 p-4 overflow-x-hidden max-w-full">
                  {#if isLoadingLog}
                    <div class="flex items-center justify-center py-8 text-text-tertiary">
                      <Loader2 size={20} class="animate-spin mr-2" />
                      Loading...
                    </div>
                  {:else}
                    <!-- Artifacts section -->
                    {#if artifacts.length > 0}
                      <div class="mb-4">
                        <h4 class="text-xs font-medium text-text-primary mb-2 flex items-center gap-1.5">
                          <FileText size={14} />
                          Artifacts ({artifacts.length})
                        </h4>
                        <div class="grid gap-2 sm:grid-cols-2">
                          {#each artifacts as artifact (artifact.id)}
                            {@const isDownloading = downloadingArtifacts.has(`${build.id}:${artifact.name}`)}
                            <button
                              onclick={(e) => handleDownloadArtifact(build.id, artifact.name, e)}
                              disabled={isDownloading}
                              class="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-border bg-surface-0 hover:bg-surface-2 transition-colors text-left disabled:opacity-50"
                            >
                              <div class="flex items-center gap-2 min-w-0">
                                <FileText size={14} class="flex-shrink-0 text-text-tertiary" />
                                <span class="text-xs font-mono text-text-primary truncate">{artifact.name}</span>
                              </div>
                              <div class="flex items-center gap-2 flex-shrink-0">
                                <span class="text-2xs text-text-tertiary">{formatSize(String(artifact.sizeBytes))}</span>
                                {#if isDownloading}
                                  <Loader2 size={14} class="text-accent animate-spin" />
                                {:else}
                                  <Download size={14} class="text-accent" />
                                {/if}
                              </div>
                            </button>
                          {/each}
                        </div>
                      </div>
                    {/if}

                    <!-- Error/Warning Summary Panel -->
                    {#if analysis && (analysis.errorCount > 0 || analysis.warningCount > 0)}
                      <div class="mb-4 rounded-lg border border-border bg-surface-0 overflow-hidden">
                        <div class="px-3 py-2 bg-surface-2 flex items-center gap-3">
                          <span class="text-xs font-medium text-text-primary">Build Issues</span>
                          {#if analysis.errorCount > 0}
                            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-error-muted text-error text-2xs font-medium">
                              <XCircle size={10} />
                              {analysis.errorCount} error{analysis.errorCount > 1 ? 's' : ''}
                            </span>
                          {/if}
                          {#if analysis.warningCount > 0}
                            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium">
                              <AlertTriangle size={10} />
                              {analysis.warningCount} warning{analysis.warningCount > 1 ? 's' : ''}
                            </span>
                          {/if}
                        </div>
                        <div class="p-3 max-h-48 overflow-y-auto">
                          {#if analysis.errors.length > 0}
                            <div class="mb-3">
                              <h5 class="text-2xs font-medium text-error mb-1.5 flex items-center gap-1">
                                <XCircle size={12} />
                                Errors
                              </h5>
                              <div class="space-y-1">
                                {#each analysis.errors.slice(0, 10) as error}
                                  <div class="text-2xs font-mono text-text-secondary bg-error-muted/50 rounded px-2 py-1 break-all">
                                    {error}
                                  </div>
                                {/each}
                                {#if analysis.errors.length > 10}
                                  <div class="text-2xs text-text-tertiary">...and {analysis.errors.length - 10} more</div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                          {#if analysis.warnings.length > 0}
                            <div>
                              <h5 class="text-2xs font-medium text-warning mb-1.5 flex items-center gap-1">
                                <AlertTriangle size={12} />
                                Warnings
                              </h5>
                              <div class="space-y-1">
                                {#each analysis.warnings.slice(0, 10) as warning}
                                  <div class="text-2xs font-mono text-text-secondary bg-warning-muted/50 rounded px-2 py-1 break-all">
                                    {warning}
                                  </div>
                                {/each}
                                {#if analysis.warnings.length > 10}
                                  <div class="text-2xs text-text-tertiary">...and {analysis.warnings.length - 10} more</div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </div>
                      </div>
                    {/if}

                    <!-- Log section -->
                    {#if buildLogs[build.id]}
                      <div>
                        <div class="flex items-center justify-between mb-2">
                          <h4 class="text-xs font-medium text-text-primary">Build Log</h4>
                        </div>
                        <div
                          bind:this={logContainers[build.id]}
                          class="text-xs font-mono text-text-secondary whitespace-pre-wrap max-h-80 overflow-y-auto overflow-x-auto bg-surface-0 rounded-lg border border-border p-3 leading-relaxed break-all"
                        >{@html ansiToHtml(buildLogs[build.id])}</div>
                      </div>
                    {:else}
                      <p class="text-xs text-text-tertiary text-center py-4">No log available.</p>
                    {/if}
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
        {/if}
      </div>
    {/if}

    <!-- Modem Firmware -->
    {#if buildRun.triggerData?.modemFirmware}
      {@const modem = buildRun.triggerData.modemFirmware}
      <div class="mb-6 rounded-lg border border-border bg-surface-0 px-4 py-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <Cpu size={16} class="text-text-tertiary" />
            <span class="text-sm font-medium text-text-primary">Modem Firmware</span>
            <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary font-mono">
              nRF91x1
            </span>
            <span class="inline-flex items-center rounded bg-accent-muted px-1.5 py-0.5 text-2xs text-accent font-mono font-medium">
              v{modem.version}
            </span>
            <span class="text-2xs font-mono text-text-tertiary">{modem.name}</span>
          </div>
          <a
            href="/v2/storage/download?key={encodeURIComponent(modem.storageKey)}"
            class="btn btn-sm text-2xs flex items-center gap-1"
            target="_blank"
          >
            <Download size={12} />
            Download
          </a>
        </div>
      </div>
    {/if}

    <!-- Metadata footer -->
    <div class="mt-6 flex items-center gap-4 text-2xs text-text-tertiary">
      <span>Created {formatDateTime(buildRun.createdAt)}</span>
      <span class="font-mono">{buildRun.id}</span>
    </div>
  {/if}
</div>

<!-- Artifact Validation Report Modal -->
<Modal open={showArtifactReport} title="Artifact Validation" onclose={() => { showArtifactReport = false; }} size="lg">
  {#if artifactReport}
    <div class="space-y-4">
      <!-- Overall status -->
      <div class="flex items-center gap-3 rounded-lg p-3 {artifactReport.valid ? 'bg-success-muted' : 'bg-error-muted'}">
        {#if artifactReport.valid}
          <CheckCircle2 size={20} class="text-success" />
          <span class="text-sm font-medium text-success">All artifacts present</span>
        {:else}
          <XCircle size={20} class="text-error" />
          <span class="text-sm font-medium text-error">
            Missing {artifactReport.missing.length} artifact{artifactReport.missing.length !== 1 ? 's' : ''}
          </span>
        {/if}
      </div>

      <!-- Per-build report -->
      {#if artifactReport.builds.length > 0}
        <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
          <div class="px-4 py-2 bg-surface-2 text-2xs font-medium text-text-tertiary uppercase tracking-wider">
            Build Artifacts
          </div>
          <div class="divide-y divide-border">
            {#each artifactReport.builds as build}
              <div class="px-4 py-3">
                <div class="flex items-center gap-3 mb-2">
                  <span class="text-sm font-medium text-text-primary">{build.label}</span>
                  {#if build.status}
                    <StatusBadge status={build.status} />
                  {:else}
                    <span class="inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium bg-error-muted text-error">MISSING</span>
                  {/if}
                  {#if build.complete}
                    <Check size={14} class="text-success" />
                  {:else}
                    <X size={14} class="text-error" />
                  {/if}
                </div>
                <div class="flex flex-wrap gap-3 text-2xs">
                  <!-- Plaintext HEX -->
                  {#each Object.entries(build.artifacts.plaintextHex) as [role, present]}
                    <span class="inline-flex items-center gap-1 rounded px-2 py-1 {present ? 'bg-success-muted text-success' : 'bg-error-muted text-error'}">
                      {#if present}
                        <Check size={10} />
                      {:else}
                        <X size={10} />
                      {/if}
                      HEX ({role})
                    </span>
                  {/each}
                  <!-- Encrypted CFW -->
                  {#each Object.entries(build.artifacts.encryptedCfw) as [role, present]}
                    <span class="inline-flex items-center gap-1 rounded px-2 py-1 {present ? 'bg-success-muted text-success' : 'bg-error-muted text-error'}">
                      {#if present}
                        <Check size={10} />
                      {:else}
                        <X size={10} />
                      {/if}
                      CFW ({role})
                    </span>
                  {/each}
                  <!-- Manifest -->
                  <span class="inline-flex items-center gap-1 rounded px-2 py-1 {build.artifacts.manifest ? 'bg-success-muted text-success' : 'bg-error-muted text-error'}">
                    {#if build.artifacts.manifest}
                      <Check size={10} />
                    {:else}
                      <X size={10} />
                    {/if}
                    Manifest
                  </span>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center text-sm text-text-tertiary">
          No build matrix configured for this build run. Artifact validation skipped.
        </div>
      {/if}

      <!-- Missing artifacts detail -->
      {#if artifactReport.missing.length > 0}
        <div class="rounded-lg border border-error/30 bg-error/5 p-4">
          <div class="text-sm font-medium text-error mb-2">Missing Artifacts</div>
          <div class="space-y-1">
            {#each artifactReport.missing as item}
              <div class="flex items-center gap-2 text-xs text-error/80">
                <X size={12} />
                <span class="font-medium">{item.label}</span>
                <span class="text-text-tertiary">-</span>
                <span>{item.artifactType}</span>
                <span class="text-text-tertiary">(role: {item.role})</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</Modal>
