<script lang="ts">
  import { X, Clock, GitBranch, FileText, Download, ExternalLink, ChevronDown, ChevronRight, Hammer, AlertTriangle, XCircle } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import BuildLogViewer from '$lib/components/ci/build-log.svelte';
  import { formatDuration, formatSize } from '$lib/utils/formatting';
  import type { BuildJob, BuildJobArtifact } from '$lib/types/ci';

  // Stage 4 build step groups
  const BUILD_STEPS = [
    { id: 1, title: 'Step 1: Factory Flash', labels: ['MFG_BASE', 'MFG_BUMP'] },
    { id: 2, title: 'Step 2: Debug FUOTA', labels: ['FUT_DEBUG_A', 'FUT_DEBUG_B'] },
    { id: 3, title: 'Step 3: Release FUOTA', labels: ['FUT_RELEASE_A', 'FUT_RELEASE_B'] },
    { id: 4, title: 'Step 4: Field Upgrade', labels: ['MAIN_BASELINE', 'MAIN_MERGED'] },
  ];

  let {
    builds = [],
    artifacts = {},
    logs = {},
    pipelineId = '',
    onclose = () => {},
  }: {
    builds: BuildJob[];
    artifacts?: Record<string, BuildJobArtifact[]>;
    logs?: Record<string, string[]>;
    pipelineId?: string;
    onclose?: () => void;
  } = $props();

  let expandedBuildId = $state<string | null>(null);
  let activeTab = $state<'log' | 'artifacts'>('log');

  // Group builds by step
  const groupedBuilds = $derived.by(() => {
    return BUILD_STEPS.map(step => ({
      ...step,
      builds: builds.filter(b => step.labels.includes(b.matrixLabel ?? '')),
    })).filter(g => g.builds.length > 0);
  });

  // Summary stats
  const passedCount = $derived(builds.filter((b) => b.status === 'SUCCESS').length);
  const totalDuration = $derived(builds.reduce((sum, b) => sum + (b.durationSeconds ?? 0), 0));
  const totalArtifacts = $derived(
    builds.reduce((sum, b) => sum + (artifacts[b.id]?.length ?? 0), 0)
  );

  const expandedBuild = $derived(expandedBuildId ? builds.find(b => b.id === expandedBuildId) : null);
  const expandedArtifacts = $derived(expandedBuildId ? artifacts[expandedBuildId] ?? [] : []);
  const expandedLogLines = $derived(expandedBuildId ? logs[expandedBuildId] ?? [] : []);

  function toggleBuild(id: string) {
    expandedBuildId = expandedBuildId === id ? null : id;
    activeTab = 'log';
  }

  function getStepStatus(builds: BuildJob[]) {
    if (builds.every(b => b.status === 'SUCCESS')) return 'complete';
    if (builds.some(b => b.status === 'FAILED')) return 'failed';
    if (builds.some(b => b.status === 'BUILDING')) return 'building';
    return 'pending';
  }

  function getVersionBumpLabel(build: BuildJob): boolean {
    return build.matrixLabel?.includes('BUMP') ||
           build.matrixLabel?.includes('_B') ||
           build.matrixLabel === 'MAIN_MERGED' ||
           build.matrixLabel === 'FUT_DEBUG_B' ||
           build.matrixLabel === 'FUT_RELEASE_B';
  }
</script>

<div class="flex h-full flex-col bg-surface-0 overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between border-b border-surface-2 px-4 py-3 flex-shrink-0">
    <div class="flex items-center gap-3">
      <Hammer class="h-5 w-5 text-text-tertiary" />
      <span class="font-medium">Build Details</span>
      <span class="text-xs rounded-full bg-accent-muted text-accent px-2 py-0.5 font-medium">
        Stage 4
      </span>
    </div>
    <button
      type="button"
      class="rounded p-1 hover:bg-surface-1"
      onclick={onclose}
    >
      <X class="h-4 w-4" />
    </button>
  </div>

  <!-- Summary stats -->
  <div class="grid grid-cols-4 gap-3 border-b border-surface-2 px-4 py-3 flex-shrink-0">
    <div>
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Builds</div>
      <div class="mt-0.5 flex items-center gap-1 text-sm font-semibold">
        <Hammer class="h-3.5 w-3.5 text-text-tertiary" />
        {passedCount}/{builds.length}
      </div>
    </div>
    <div>
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Duration</div>
      <div class="mt-0.5 flex items-center gap-1 text-sm font-semibold tabular-nums">
        <Clock class="h-3.5 w-3.5 text-text-tertiary" />
        {formatDuration(totalDuration * 1000)}
      </div>
    </div>
    <div>
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Artifacts</div>
      <div class="mt-0.5 flex items-center gap-1 text-sm font-semibold tabular-nums">
        <FileText class="h-3.5 w-3.5 text-text-tertiary" />
        {totalArtifacts}
      </div>
    </div>
    <div>
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Pipeline</div>
      <div class="mt-0.5">
        {#if pipelineId}
          <a href="/ci/pipelines/{pipelineId}" class="text-xs text-accent hover:underline flex items-center gap-1">
            View <ExternalLink class="h-3 w-3" />
          </a>
        {:else}
          <span class="text-sm text-text-tertiary">--</span>
        {/if}
      </div>
    </div>
  </div>

  <!-- Grouped builds -->
  <div class="flex-1 overflow-auto">
    <div class="p-3 space-y-3">
      {#each groupedBuilds as group (group.id)}
        {@const status = getStepStatus(group.builds)}
        <div class="rounded-lg border border-surface-2 bg-surface-1 overflow-hidden">
          <!-- Group header -->
          <div class="px-3 py-2 bg-surface-2 flex items-center gap-2">
            <span class="text-xs font-medium text-text-primary">{group.title}</span>
            <span class="text-2xs text-text-tertiary">({group.builds.length} builds)</span>
            {#if status === 'complete'}
              <span class="ml-auto text-2xs text-success">All complete</span>
            {:else if status === 'failed'}
              <span class="ml-auto text-2xs text-error">{group.builds.filter(b => b.status === 'FAILED').length} failed</span>
            {:else if status === 'building'}
              <span class="ml-auto text-2xs text-warning">{group.builds.filter(b => b.status === 'BUILDING').length} building</span>
            {/if}
          </div>

          <!-- Builds in group -->
          <div class="divide-y divide-surface-2">
            {#each group.builds as build (build.id)}
              {@const isExpanded = expandedBuildId === build.id}
              {@const buildArtifacts = artifacts[build.id] ?? []}
              <div class="bg-surface-0">
                <button
                  type="button"
                  onclick={() => toggleBuild(build.id)}
                  class="w-full p-3 text-left hover:bg-surface-1 transition-colors"
                >
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex items-center gap-2 min-w-0 flex-1">
                      {#if isExpanded}
                        <ChevronDown class="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
                      {:else}
                        <ChevronRight class="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
                      {/if}

                      <!-- Build name with friendly label -->
                      <span class="text-xs font-medium text-text-primary">
                        {#if build.matrixLabel === 'MFG_BASE'}Mfg v1
                        {:else if build.matrixLabel === 'MFG_BUMP'}Mfg v2
                        {:else if build.matrixLabel === 'FUT_DEBUG_A'}Debug v1
                        {:else if build.matrixLabel === 'FUT_DEBUG_B'}Debug v2
                        {:else if build.matrixLabel === 'FUT_RELEASE_A'}Release v1
                        {:else if build.matrixLabel === 'FUT_RELEASE_B'}Release v2
                        {:else if build.matrixLabel === 'MAIN_BASELINE'}Baseline
                        {:else if build.matrixLabel === 'MAIN_MERGED'}Merged
                        {:else}{build.matrixLabel ?? build.variant}
                        {/if}

                        {#if build.versionString}
                          <span class="font-mono text-accent ml-1">v{build.versionString}</span>
                        {/if}
                      </span>

                      <StatusBadge status={build.status} />

                      {#if getVersionBumpLabel(build)}
                        <span class="text-2xs text-info px-1 py-0.5 rounded bg-info-muted" title="Version bump">+1</span>
                      {/if}
                    </div>

                    <div class="flex items-center gap-2 text-2xs text-text-tertiary flex-shrink-0">
                      {#if buildArtifacts.length > 0}
                        <span class="flex items-center gap-1">
                          <FileText class="h-3 w-3" />
                          {buildArtifacts.length}
                        </span>
                      {/if}
                      {#if build.durationSeconds}
                        <span class="flex items-center gap-1">
                          <Clock class="h-3 w-3" />
                          {formatDuration(build.durationSeconds * 1000)}
                        </span>
                      {/if}
                      {#if build.buildNum}
                        <span class="tabular-nums">#{build.buildNum}</span>
                      {/if}
                    </div>
                  </div>
                </button>

                <!-- Expanded build details -->
                {#if isExpanded && expandedBuild}
                  <div class="border-t border-surface-2 bg-surface-1">
                    <!-- Build metadata -->
                    <div class="px-4 py-3 border-b border-surface-2 grid grid-cols-3 gap-3 text-xs">
                      <div>
                        <span class="text-text-tertiary">Branch:</span>
                        <span class="ml-1 flex items-center gap-1">
                          <GitBranch class="h-3 w-3" />
                          {expandedBuild.branch}
                        </span>
                      </div>
                      <div>
                        <span class="text-text-tertiary">Product:</span>
                        <span class="ml-1">{expandedBuild.product}</span>
                      </div>
                      <div>
                        <a href="/ci/builds/{expandedBuild.id}" class="text-accent hover:underline flex items-center gap-1">
                          Full build page <ExternalLink class="h-3 w-3" />
                        </a>
                      </div>
                    </div>

                    <!-- Tabs -->
                    <div class="flex border-b border-surface-2 px-2">
                      <button
                        type="button"
                        class="px-3 py-2 text-xs {activeTab === 'log'
                          ? 'border-b-2 border-accent text-accent -mb-[1px]'
                          : 'text-text-secondary hover:text-text-primary'}"
                        onclick={() => (activeTab = 'log')}
                      >
                        Build Log
                      </button>
                      <button
                        type="button"
                        class="px-3 py-2 text-xs {activeTab === 'artifacts'
                          ? 'border-b-2 border-accent text-accent -mb-[1px]'
                          : 'text-text-secondary hover:text-text-primary'}"
                        onclick={() => (activeTab = 'artifacts')}
                      >
                        Artifacts ({expandedArtifacts.length})
                      </button>
                    </div>

                    <!-- Tab content -->
                    <div class="max-h-64 overflow-auto">
                      {#if activeTab === 'log'}
                        {#if expandedLogLines.length > 0}
                          <BuildLogViewer
                            lines={expandedLogLines}
                            streaming={expandedBuild.status === 'BUILDING'}
                          />
                        {:else if expandedBuild.status === 'BUILDING'}
                          <div class="flex h-24 items-center justify-center text-xs text-text-tertiary">
                            Waiting for build output...
                          </div>
                        {:else}
                          <div class="flex h-24 items-center justify-center text-xs text-text-tertiary">
                            No build log available
                          </div>
                        {/if}
                      {:else if activeTab === 'artifacts'}
                        {#if expandedArtifacts.length > 0}
                          <div class="p-2 space-y-1">
                            {#each expandedArtifacts as artifact}
                              <a
                                href={artifact.downloadUrl}
                                class="flex items-center justify-between rounded bg-surface-0 px-3 py-2 hover:bg-surface-2 transition-colors"
                                download
                              >
                                <div class="flex items-center gap-2 min-w-0">
                                  <FileText class="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
                                  <span class="font-mono text-xs truncate">{artifact.name}</span>
                                </div>
                                <div class="flex items-center gap-2 flex-shrink-0">
                                  <span class="text-2xs text-text-tertiary">{formatSize(artifact.sizeBytes ?? 0)}</span>
                                  <Download class="h-3.5 w-3.5 text-accent" />
                                </div>
                              </a>
                            {/each}
                          </div>
                        {:else}
                          <div class="flex h-24 items-center justify-center text-xs text-text-tertiary">
                            No artifacts available
                          </div>
                        {/if}
                      {/if}
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>
