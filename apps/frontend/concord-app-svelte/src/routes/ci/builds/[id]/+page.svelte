<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    ArrowLeft,
    Clock,
    Download,
    FileText,
    GitBranch,
    RefreshCw,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildJob, BuildJobArtifact } from '$lib/types/ci';
  import { fetchBuild, fetchBuildLog, fetchBuildArtifacts, triggerBuild } from '$lib/services/ci';
  import {
    subscribeCiBuild,
    type CiBuildLogEvent,
    type CiBuildCompleteEvent,
  } from '$lib/services/websocket';
  import { formatTimeAgo, formatDateTime, formatDuration, formatSize } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import BuildLogViewer from '$lib/components/ci/build-log.svelte';

  const auth = getAuth();
  const buildId = $derived($page.params.id);

  let build = $state<BuildJob | null>(null);
  let artifacts = $state<BuildJobArtifact[]>([]);
  let logLines = $state<string[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let retriggering = $state(false);
  let unsubscribeWs: (() => void) | null = null;

  const isBuilding = $derived(build?.status === 'BUILDING' || build?.status === 'QUEUED');

  async function loadBuild(): Promise<void> {
    try {
      build = await fetchBuild(buildId);
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build';
    } finally {
      loading = false;
    }
  }

  async function loadLog(): Promise<void> {
    try {
      const log = await fetchBuildLog(buildId);
      logLines = log.split('\n');
    } catch {
      // Log may not be available yet
    }
  }

  async function loadArtifacts(): Promise<void> {
    try {
      artifacts = await fetchBuildArtifacts(buildId);
    } catch {
      artifacts = [];
    }
  }

  async function retrigger(): Promise<void> {
    if (!build) return;
    if (!confirm('Re-trigger this build with the same configuration?')) return;