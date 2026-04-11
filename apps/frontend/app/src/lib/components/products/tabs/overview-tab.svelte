<script lang="ts">
  import {
    CircuitBoard, FlaskConical, Factory, Hammer,
    GitBranch, ExternalLink, Lock,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import type { Product } from '$lib/types/models';
  import type { ProductStageConfig } from '$lib/types/stages';
  import { STAGE_NAMES } from '$lib/types/stages';
  import { formatTimeAgo } from '$lib/utils/formatting';
  import { api } from '$lib/api';

  interface Props {
    product: Product;
    canManage: boolean;
    onSwitchTab?: (tab: string) => void;
  }

  let { product, onSwitchTab }: Props = $props();

  // ── Revisions ────────────────────────────────────────────
  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );
  const activeRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE'));
  const deprecatedRevisions = $derived(revisions.filter((r) => r.status === 'DEPRECATED' || r.status === 'EOL'));
  const latestRevision = $derived(
    activeRevisions.length > 0
      ? activeRevisions.reduce((latest, r) =>
          new Date(r.createdAt) > new Date(latest.createdAt) ? r : latest
        )
      : null
  );

  // ── Stage configs ────────────────────────────────────────
  const stageConfigs = $derived((product as Product & { stageConfigs?: ProductStageConfig[] }).stageConfigs || []);
  const valStages = $derived(stageConfigs.filter((s) => !s.type || s.type === 'VALIDATION'));
  const mfgStages = $derived(stageConfigs.filter((s) => s.type === 'MANUFACTURING'));

  // Validation stage numbers (rows) — always show all 5 standard stages
  const stageNumbers = [1, 2, 3, 4, 5];

  // Manufacturing stage numbers (rows)
  const mfgStageNumbers = $derived(
    ([...new Set(mfgStages.map((s) => s.stage))] as number[]).sort((a, b) => a - b)
  );

  // All revisions are columns — active revisions without stages show dashes
  const matrixRevisions = $derived(revisions);

  // Lookup: (stageNumber, revisionId) → config
  const stageMatrix = $derived(() => {
    const map = new Map<string, ProductStageConfig>();
    for (const cfg of valStages) {
      if (cfg.boardRevisionId) {
        map.set(`${cfg.stage}:${cfg.boardRevisionId}`, cfg);
      }
    }
    return map;
  });

  function getStageCell(stage: number, revId: string): ProductStageConfig | null {
    return stageMatrix().get(`${stage}:${revId}`) ?? null;
  }

  // Check if any revision has a config for a given validation stage
  function hasAnyConfig(stage: number): boolean {
    return valStages.some((s) => s.stage === stage);
  }

  // Manufacturing stage lookup
  const mfgStageMatrix = $derived(() => {
    const map = new Map<string, ProductStageConfig>();
    for (const cfg of mfgStages) {
      if (cfg.boardRevisionId) {
        map.set(`${cfg.stage}:${cfg.boardRevisionId}`, cfg);
      }
    }
    return map;
  });

  function getMfgStageCell(stage: number, revId: string): ProductStageConfig | null {
    return mfgStageMatrix().get(`${stage}:${revId}`) ?? null;
  }

  // ── Activity data ────────────────────────────────────────

  interface BuildRecord {
    id: string;
    status: string;
    matrixLabel?: string;
    variant?: string;
    versionString?: string;
    branch?: string;
    commitSha?: string;
    createdAt?: string;
  }

  interface RunRecord {
    id: string;
    status: string;
    name?: string;
    stage?: number;
    targetCount?: number;
    duration?: number;
    createdAt?: string;
    completedAt?: string;
  }

  interface PaginatedResponse<T> {
    data?: { data?: T[]; pagination?: { total?: number } };
  }

  let recentBuilds = $state<BuildRecord[]>([]);
  let recentRuns = $state<RunRecord[]>([]);
  let totalBuilds = $state(0);
  let totalRuns = $state(0);
  let totalMfgSessions = $state(0);
  let loading = $state(true);

  // ── Derived stats ────────────────────────────────────────
  const lastBuild = $derived(recentBuilds.length > 0 ? recentBuilds[0] : null);
  const activeRuns = $derived(recentRuns.filter((r) => r.status === 'RUNNING' || r.status === 'QUEUED'));
  const completedRuns = $derived(recentRuns.filter((r) => r.status === 'PASSED' || r.status === 'FAILED'));
  const passRate = $derived(() => {
    if (completedRuns.length === 0) return null;
    const passed = completedRuns.filter((r) => r.status === 'PASSED').length;
    return Math.round((passed / completedRuns.length) * 100);
  });

  async function fetchActivity() {
    loading = true;
    try {
      const [buildsRes, runsRes, mfgRes] = await Promise.allSettled([
        api.get(`/v2/builds?productId=${product.id}&limit=5`),
        api.get(`/v2/runs?productId=${product.id}&limit=5&type=VALIDATION`),
        api.get(`/v2/runs?productId=${product.id}&limit=1&type=MANUFACTURING`),
      ]);
      if (buildsRes.status === 'fulfilled') {
        const d = buildsRes.value as PaginatedResponse<BuildRecord>;
        recentBuilds = d.data?.data || [];
        totalBuilds = d.data?.pagination?.total ?? 0;
      }
      if (runsRes.status === 'fulfilled') {
        const d = runsRes.value as PaginatedResponse<RunRecord>;
        recentRuns = d.data?.data || [];
        totalRuns = d.data?.pagination?.total ?? 0;
      }
      if (mfgRes.status === 'fulfilled') {
        const d = mfgRes.value as PaginatedResponse<RunRecord>;
        totalMfgSessions = d.data?.pagination?.total ?? 0;
      }
    } catch {
      // Non-critical
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (product?.id) fetchActivity();
  });

  // Repo URLs from product metadata
  const fwRepoUrl = $derived(product.fwRepoSlug ? `https://bitbucket.org/corekinect/${product.fwRepoSlug}` : null);
  const mfgRepoUrl = $derived(product.mfgFwRepoSlug ? `https://bitbucket.org/corekinect/${product.mfgFwRepoSlug}` : null);

  // ── Helpers ──────────────────────────────────────────────

  function truncateBranch(branch: string, max = 16): string {
    return branch.length > max ? branch.slice(0, max - 1) + '\u2026' : branch;
  }

  function truncateSha(sha: string): string {
    return sha.slice(0, 7);
  }

  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
  }

  function switchTab(tab: string): void {
    if (onSwitchTab) onSwitchTab(tab);
  }
</script>

<!-- Stat cards -->
<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
  <!-- Hardware -->
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <CircuitBoard size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Hardware</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{activeRevisions.length}</div>
    <div class="text-2xs text-text-tertiary">
      {activeRevisions.length === 1 ? '1 active' : `${activeRevisions.length} active`}{#if deprecatedRevisions.length > 0}<span class="text-text-tertiary"> · {deprecatedRevisions.length} deprecated</span>{/if}
    </div>
    {#if latestRevision}
      <div class="text-2xs text-text-secondary mt-0.5">Latest: {latestRevision.version}</div>
    {/if}
  </div>

  <!-- Builds -->
  <a href="/builds?product={product.slug}" class="rounded-lg border border-border bg-surface-0 p-3 hover:border-accent hover:bg-surface-1 transition-colors cursor-pointer no-underline">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Hammer size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Builds</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{loading ? '\u2014' : totalBuilds}</div>
    {#if !loading && lastBuild}
      <div class="text-2xs text-text-tertiary flex items-center gap-1">
        Last:
        {#if lastBuild.createdAt}
          <span>{formatTimeAgo(lastBuild.createdAt)}</span>
        {/if}
        <span class="inline-block w-1.5 h-1.5 rounded-full shrink-0
          {lastBuild.status === 'SUCCESS' ? 'bg-success' :
           lastBuild.status === 'FAILED' || lastBuild.status === 'BUILD_FAILED' ? 'bg-error' :
           lastBuild.status === 'BUILDING' ? 'bg-accent' :
           'bg-text-tertiary'}"></span>
        <span class="uppercase">{lastBuild.status}</span>
      </div>
    {:else if !loading}
      <div class="text-2xs text-text-tertiary">no builds yet</div>
    {/if}
  </a>

  <!-- Validation -->
  <a href="/validation?product={product.slug}" class="rounded-lg border border-border bg-surface-0 p-3 hover:border-accent hover:bg-surface-1 transition-colors cursor-pointer no-underline">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <FlaskConical size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Validation</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{loading ? '\u2014' : totalRuns}</div>
    {#if !loading && activeRuns.length > 0}
      <div class="text-2xs text-accent">{activeRuns.length} active</div>
    {:else if !loading && passRate() !== null}
      <div class="text-2xs text-text-tertiary">{passRate()}% pass rate</div>
    {:else if !loading}
      <div class="text-2xs text-text-tertiary">{totalRuns === 0 ? 'no runs yet' : 'total runs'}</div>
    {/if}
  </a>

  <!-- Manufacturing -->
  <a href="/manufacturing?product={product.slug}" class="rounded-lg border border-border bg-surface-0 p-3 hover:border-accent hover:bg-surface-1 transition-colors cursor-pointer no-underline">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Factory size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Manufacturing</span>
    </div>
    {#if product.manufacturingStats}
      {#if product.manufacturingStats.totalDevices > 0}
        <div class="text-xl font-semibold text-text-primary">{product.manufacturingStats.totalDevices}</div>
        <div class="text-2xs text-text-tertiary">
          devices tested ·
          <span class="text-success">{product.manufacturingStats.passedDevices} passed</span> ·
          <span class="text-error">{product.manufacturingStats.failedDevices} failed</span>
        </div>
        {#if product.manufacturingStats.activeSessions > 0}
          <div class="text-2xs text-accent mt-0.5">{product.manufacturingStats.activeSessions} active session{product.manufacturingStats.activeSessions !== 1 ? 's' : ''}</div>
        {/if}
      {:else}
        <div class="text-xl font-semibold text-text-primary">0</div>
        <div class="text-2xs text-text-tertiary">no devices tested yet</div>
      {/if}
    {:else}
      <div class="text-xl font-semibold text-text-primary">{loading ? '\u2014' : totalMfgSessions}</div>
      <div class="text-2xs text-text-tertiary">{totalMfgSessions === 0 ? 'no sessions yet' : 'total sessions'}</div>
    {/if}
  </a>
</div>

<!-- Repos -->
{#if fwRepoUrl || mfgRepoUrl}
  <div class="mb-6">
    <h3 class="text-sm font-semibold text-text-primary mb-3">Repositories</h3>
    <div class="flex flex-wrap gap-3">
      {#if fwRepoUrl}
        <a href={fwRepoUrl} target="_blank" rel="noopener noreferrer"
          class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm text-text-primary hover:border-accent hover:bg-surface-2 transition-colors">
          <GitBranch size={14} class="text-accent" />
          <span class="font-medium">{product.fwRepoSlug}</span>
          <span class="text-2xs text-text-tertiary">firmware</span>
          <ExternalLink size={12} class="text-text-tertiary" />
        </a>
      {/if}
      {#if mfgRepoUrl}
        <a href={mfgRepoUrl} target="_blank" rel="noopener noreferrer"
          class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm text-text-primary hover:border-accent hover:bg-surface-2 transition-colors">
          <GitBranch size={14} class="text-warning" />
          <span class="font-medium">{product.mfgFwRepoSlug}</span>
          <span class="text-2xs text-text-tertiary">manufacturing</span>
          <ExternalLink size={12} class="text-text-tertiary" />
        </a>
      {/if}
    </div>
  </div>
{/if}

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
  <!-- Left: Validation stage matrix -->
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-text-primary">Validation Stages</h3>
      <span class="text-2xs text-text-tertiary">{valStages.filter((s) => s.enabled).length} of 5 configured</span>
    </div>
      <!-- Stage x revision matrix table with sticky stage column -->
      <div class="rounded-lg border border-border overflow-x-auto">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="bg-surface-2">
              <th class="sticky left-0 z-10 bg-surface-2 text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary border-r border-border-subtle min-w-[140px]">Stage</th>
              {#each matrixRevisions as rev}
                <th class="text-center px-4 py-2 min-w-[120px]">
                  <span class="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded {rev.status === 'ACTIVE' ? 'bg-accent-muted text-accent' : 'bg-surface-1 text-text-tertiary'}">{rev.version}</span>
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each stageNumbers as stageNum}
              {@const configured = hasAnyConfig(stageNum)}
              <tr class="border-t border-border-subtle">
                <td class="sticky left-0 z-10 bg-surface-0 px-4 py-2.5 border-r border-border-subtle">
                  <div class="flex items-center gap-2">
                    <div class="w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold shrink-0
                      {configured ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
                      {stageNum}
                    </div>
                    <span class="whitespace-nowrap {configured ? 'font-medium text-text-primary' : 'font-medium text-text-tertiary'}">{STAGE_NAMES['VALIDATION']?.[stageNum] || `Stage ${stageNum}`}</span>
                  </div>
                </td>
                {#each matrixRevisions as rev}
                  {@const cell = getStageCell(stageNum, rev.id)}
                  <td class="text-center px-4 py-2.5">
                    {#if cell?.enabled && cell.triggerTypes?.length > 0}
                      <div class="flex flex-col items-center gap-0.5">
                        <div class="flex flex-wrap justify-center gap-0.5">
                          {#each cell.triggerTypes as trigger}
                            <span class="text-[9px] font-mono px-1 py-0.5 rounded whitespace-nowrap
                              {trigger === 'AUTO' ? 'bg-success-muted text-success' : 'bg-accent-muted text-accent'}">{trigger}</span>
                          {/each}
                        </div>
                        <div class="flex items-center gap-0.5">
                          {#if cell.watchBranch}
                            <span class="flex items-center gap-0.5 text-[9px] text-text-tertiary" title="Watch branch: {cell.watchBranch}">
                              <GitBranch size={8} />
                              <span class="font-mono">{truncateBranch(cell.watchBranch, 12)}</span>
                            </span>
                          {/if}
                          {#if cell.signingKeyId}
                            <span class="text-text-tertiary" title="Signing key: {cell.signingKey?.name || 'configured'}">
                              <Lock size={8} />
                            </span>
                          {/if}
                        </div>
                      </div>
                    {:else if cell}
                      <span class="text-text-tertiary opacity-30">&mdash;</span>
                    {:else}
                      <span class="text-2xs text-text-tertiary opacity-50">Not configured</span>
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

    <!-- Manufacturing stage matrix -->
    <div class="mt-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-text-primary">Manufacturing Stages</h3>
        {#if mfgStages.length > 0}
          <span class="text-2xs text-text-tertiary">{mfgStages.filter((s) => s.enabled).length} of {mfgStages.length} enabled</span>
        {/if}
      </div>
      {#if mfgStages.length === 0}
        <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
          <Factory size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
          <p class="text-sm text-text-secondary">No manufacturing stages configured</p>
          {#if onSwitchTab}
            <button
              onclick={() => switchTab('manufacturing')}
              class="mt-2 text-2xs font-medium text-accent hover:text-accent-hover transition-colors"
            >
              Go to Manufacturing tab
            </button>
          {:else}
            <p class="text-2xs text-text-tertiary mt-1">Go to the Manufacturing tab to set up stages for this product.</p>
          {/if}
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-x-auto">
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="bg-surface-2">
                <th class="sticky left-0 z-10 bg-surface-2 text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary border-r border-border-subtle min-w-[140px]">Stage</th>
                {#each matrixRevisions as rev}
                  <th class="text-center px-4 py-2 min-w-[120px]">
                    <span class="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded {rev.status === 'ACTIVE' ? 'bg-accent-muted text-accent' : 'bg-surface-1 text-text-tertiary'}">{rev.version}</span>
                  </th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each mfgStageNumbers as stageNum}
                {@const stageName = mfgStages.find((s) => s.stage === stageNum)?.name}
                <tr class="border-t border-border-subtle">
                  <td class="sticky left-0 z-10 bg-surface-0 px-4 py-2.5 border-r border-border-subtle">
                    <div class="flex items-center gap-2">
                      <div class="w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold bg-warning text-white shrink-0">
                        {stageNum}
                      </div>
                      <span class="font-medium text-text-primary whitespace-nowrap">{stageName || `Stage ${stageNum}`}</span>
                    </div>
                  </td>
                  {#each matrixRevisions as rev}
                    {@const cell = getMfgStageCell(stageNum, rev.id)}
                    <td class="text-center px-4 py-2.5">
                      {#if cell?.enabled && cell.triggerTypes?.length > 0}
                        <div class="flex flex-col items-center gap-0.5">
                          <div class="flex flex-wrap justify-center gap-0.5">
                            {#each cell.triggerTypes as trigger}
                              <span class="text-[9px] font-mono px-1 py-0.5 rounded whitespace-nowrap
                                {trigger === 'AUTO' ? 'bg-success-muted text-success' : 'bg-warning-muted text-warning'}">{trigger}</span>
                            {/each}
                          </div>
                          <div class="flex items-center gap-0.5">
                            {#if cell.watchBranch}
                              <span class="flex items-center gap-0.5 text-[9px] text-text-tertiary" title="Watch branch: {cell.watchBranch}">
                                <GitBranch size={8} />
                                <span class="font-mono">{truncateBranch(cell.watchBranch, 12)}</span>
                              </span>
                            {/if}
                            {#if cell.signingKeyId}
                              <span class="text-text-tertiary" title="Signing key: {cell.signingKey?.name || 'configured'}">
                                <Lock size={8} />
                              </span>
                            {/if}
                          </div>
                        </div>
                      {:else}
                        <span class="text-text-tertiary opacity-30">&mdash;</span>
                      {/if}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  </div>

  <!-- Right: Recent activity -->
  <div class="space-y-6">
    <!-- Recent builds -->
    <div>
      <h3 class="text-sm font-semibold text-text-primary mb-3">Recent Builds</h3>
      {#if loading}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
        </div>
      {:else if recentBuilds.length === 0}
        <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
          <Hammer size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
          <p class="text-sm text-text-secondary">No builds yet</p>
          <p class="text-2xs text-text-tertiary mt-1">Builds appear here when triggered by the CI pipeline or manually.</p>
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-hidden">
          {#each recentBuilds as build}
            <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
              <StatusBadge status={build.status} />
              <div class="flex-1 min-w-0">
                <div class="text-sm text-text-primary truncate">{build.matrixLabel || build.variant}</div>
                <div class="flex items-center gap-1.5 text-2xs text-text-tertiary">
                  {#if build.branch}
                    <span class="flex items-center gap-0.5">
                      <GitBranch size={9} />
                      <span class="font-mono">{truncateBranch(build.branch)}</span>
                    </span>
                  {/if}
                  {#if build.commitSha}
                    <span class="font-mono">{truncateSha(build.commitSha)}</span>
                  {/if}
                  {#if build.versionString}
                    <span class="font-mono">v{build.versionString}</span>
                  {/if}
                </div>
              </div>
              {#if build.createdAt}
                <span class="text-2xs text-text-tertiary whitespace-nowrap">
                  <TimeDisplay datetime={build.createdAt} />
                </span>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Recent validation runs -->
    <div>
      <h3 class="text-sm font-semibold text-text-primary mb-3">Recent Validation Runs</h3>
      {#if loading}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
        </div>
      {:else if recentRuns.length === 0}
        <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
          <FlaskConical size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
          <p class="text-sm text-text-secondary">No validation runs yet</p>
          {#if onSwitchTab}
            <button
              onclick={() => switchTab('stages')}
              class="mt-2 text-2xs font-medium text-accent hover:text-accent-hover transition-colors"
            >
              Go to Validation tab
            </button>
          {:else}
            <p class="text-2xs text-text-tertiary mt-1">Runs appear here when validation is triggered from the pipeline or manually.</p>
          {/if}
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-hidden">
          {#each recentRuns as run}
            <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
              <StatusBadge status={run.status} />
              <div class="flex-1 min-w-0">
                <div class="text-sm text-text-primary truncate">{run.name}</div>
                <div class="flex items-center gap-1.5 text-2xs text-text-tertiary">
                  {#if run.stage}
                    <span>Stage {run.stage}</span>
                  {/if}
                  {#if run.targetCount}
                    <span>{run.targetCount} target{run.targetCount !== 1 ? 's' : ''}</span>
                  {/if}
                  {#if run.duration}
                    <span>{formatDuration(run.duration)}</span>
                  {/if}
                </div>
              </div>
              {#if run.createdAt}
                <span class="text-2xs text-text-tertiary whitespace-nowrap">
                  <TimeDisplay datetime={run.createdAt} />
                </span>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
