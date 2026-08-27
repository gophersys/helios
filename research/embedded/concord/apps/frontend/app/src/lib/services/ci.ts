import { apiFetch, api, apiDownload, apiUpload } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type {
  BuildJob,
  BuildArtifact,
  BuildRunDetail,
  BuildRunStageInfo,
  BuildRunStageStatus,
  BuildSummary,
  PrBuildSummary,
  TriggerBuildConfig,
  TriggerBuildRunConfig,
} from '$lib/types/ci';
import type { Pagination } from '$lib/types/models';

// ── Build Runs ──────────────────────────────────────────────────

export interface FetchBuildRunsParams {
  page?: number;
  limit?: number;
  status?: string;
  branch?: string;
  product?: string;
  productId?: string;
  stage?: number;
  prNumber?: number;
  triggerType?: string;
  createdAfter?: string;
  createdBefore?: string;
  matrixMode?: string;
}

export async function fetchBuildRuns(
  params?: FetchBuildRunsParams
): Promise<{ data: BuildRunDetail[]; pagination: Pagination }> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set('page', String(params.page));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.status) qs.set('status', params.status);
  if (params?.branch) qs.set('branch', params.branch);
  if (params?.product) qs.set('product', params.product);
  if (params?.productId) qs.set('productId', params.productId);
  if (params?.stage) qs.set('stage', String(params.stage));
  if (params?.prNumber) qs.set('prNumber', String(params.prNumber));
  if (params?.triggerType) qs.set('triggerType', params.triggerType);
  if (params?.createdAfter) qs.set('createdAfter', params.createdAfter);
  if (params?.createdBefore) qs.set('createdBefore', params.createdBefore);
  if (params?.matrixMode) qs.set('matrixMode', params.matrixMode);

  // API returns { data: { data: [...], pagination: {...} }, errors: [] }
  const res = await apiFetch<ApiResponse<{ data: BuildRunDetail[]; pagination: Pagination }>>(
    `/v2/builds/runs?${qs.toString()}`
  );
  const inner = res.data as { data: BuildRunDetail[]; pagination: Pagination };
  return {
    data: inner?.data ?? [],
    pagination: inner?.pagination ?? { page: 1, limit: 25, total: 0, pages: 0 },
  };
}

export async function fetchBuildRun(id: string): Promise<BuildRunDetail> {
  const res = await apiFetch<ApiResponse<BuildRunDetail>>(`/v2/builds/runs/${id}`);
  const buildRun = res.data;

  // Compute stages from build run status and builds
  const stages: BuildRunStageInfo[] = [];

  // BUILD stage
  const builds = buildRun.builds ?? [];
  const allBuildsComplete = builds.length > 0 && builds.every(b => b.status === 'SUCCESS' || b.status === 'FAILED' || b.status === 'CANCELLED');
  const anyBuildFailed = builds.some(b => b.status === 'FAILED');
  const anyBuildRunning = builds.some(b => b.status === 'BUILDING');

  let buildStatus: BuildRunStageStatus = 'PENDING';
  if (anyBuildRunning) buildStatus = 'RUNNING';
  else if (anyBuildFailed) buildStatus = 'FAILED';
  else if (allBuildsComplete && builds.length > 0) buildStatus = 'SUCCESS';
  else if (builds.length > 0) buildStatus = 'RUNNING';

  stages.push({
    stage: 'BUILD',
    status: buildStatus,
    startedAt: buildRun.startedAt,
    finishedAt: allBuildsComplete ? buildRun.finishedAt : null,
    detail: builds.length > 0 ? `${builds.filter(b => b.status === 'SUCCESS').length}/${builds.length} builds passed` : null,
  });

  // FLASH stage (only if validation is configured)
  if (buildRun.validationRunId || buildRun.status === 'VALIDATING') {
    stages.push({
      stage: 'FLASH',
      status: buildStatus === 'SUCCESS' ? 'SUCCESS' : buildStatus === 'FAILED' ? 'SKIPPED' : 'PENDING',
      startedAt: null,
      finishedAt: null,
      detail: null,
    });
  }

  // VALIDATE stage
  if (buildRun.validationRunId) {
    stages.push({
      stage: 'VALIDATE',
      status: buildRun.status === 'COMPLETED' ? 'SUCCESS' : buildRun.status === 'FAILED' ? 'FAILED' : 'PENDING',
      startedAt: null,
      finishedAt: null,
      detail: null,
    });
  }

  // Set computed fields for UI compatibility
  buildRun.stages = stages;
  buildRun.buildJob = builds.length > 0 ? {
    id: builds[0].id,
    product: builds[0].product,
    board: buildRun.board,
    target: '',
    variant: builds[0].variant,
    branch: buildRun.branch,
    commitSha: buildRun.commitSha ?? '',
    status: builds[0].status,
    versionString: builds[0].versionString,
    buildLog: null,
    startedAt: buildRun.startedAt,
    finishedAt: buildRun.finishedAt,
    durationSeconds: builds[0].durationSeconds,
    triggerTypes: buildRun.triggerType ?? 'worker',
    createdAt: buildRun.createdAt,
    artifacts: [],
  } : null;

  return buildRun;
}

export async function triggerBuildRun(config: TriggerBuildRunConfig): Promise<BuildRunDetail> {
  const res = await api.post<ApiResponse<BuildRunDetail>>('/v2/builds/trigger', config);
  return res.data;
}

// ── Builds ─────────────────────────────────────────────────────

export interface FetchBuildsParams {
  page?: number;
  limit?: number;
  status?: string;
  branch?: string;
  product?: string;
  triggerTypes?: string;
}

export async function fetchBuilds(
  params?: FetchBuildsParams
): Promise<{ data: BuildJob[]; pagination: Pagination }> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set('page', String(params.page));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.status) qs.set('status', params.status);
  if (params?.branch) qs.set('branch', params.branch);
  if (params?.product) qs.set('product', params.product);
  if (params?.triggerTypes) qs.set('triggerTypes', params.triggerTypes);

  // API returns { data: { data: [...], pagination: {...} }, errors: [] }
  const res = await apiFetch<ApiResponse<{ data: BuildJob[]; pagination: Pagination }>>(
    `/v2/builds?${qs.toString()}`
  );
  const inner = res.data as { data: BuildJob[]; pagination: Pagination };
  return {
    data: inner?.data ?? [],
    pagination: inner?.pagination ?? { page: 1, limit: 25, total: 0, pages: 0 },
  };
}

export async function fetchBuild(id: string): Promise<BuildJob> {
  const res = await apiFetch<ApiResponse<BuildJob>>(`/v2/builds/${id}`);
  return res.data;
}

export async function fetchBuildLog(id: string): Promise<string> {
  const res = await apiFetch<ApiResponse<{ log: string }>>(`/v2/builds/${id}/log`);
  return res.data.log;
}

export async function fetchBuildArtifacts(id: string): Promise<BuildArtifact[]> {
  const res = await apiFetch<ApiResponse<BuildArtifact[]>>(`/v2/builds/${id}/artifacts`);
  return res.data;
}

export async function triggerBuild(config: TriggerBuildConfig): Promise<BuildJob> {
  const res = await api.post<ApiResponse<BuildJob>>('/v2/builds', config);
  return res.data;
}

export interface ManualBuildConfig {
  product: string;
  board: string;
  target: string;
  variant: string;
  branch: string;
  versionString?: string;
  notes?: string;
  productId?: string;
}

export async function createManualBuild(config: ManualBuildConfig): Promise<BuildJob> {
  const res = await api.post<ApiResponse<BuildJob>>('/v2/builds', {
    product: config.product,
    board: config.board,
    target: config.target,
    variant: config.variant,
    branch: config.branch,
    versionString: config.versionString || undefined,
    notes: config.notes || undefined,
    productId: config.productId || undefined,
    triggerTypes: 'manual',
    initialStatus: 'SUCCESS',
  });
  return res.data;
}

export async function uploadBuildArtifact(
  buildId: string,
  file: File,
  metadata: { role?: string; processor?: string; artifactType?: string; contentType?: string }
): Promise<BuildArtifact> {
  const formData = new FormData();
  formData.append('file', file);
  if (metadata.role) formData.append('role', metadata.role);
  if (metadata.processor) formData.append('processor', metadata.processor);
  if (metadata.artifactType) formData.append('artifactType', metadata.artifactType);
  if (metadata.contentType) formData.append('contentType', metadata.contentType);

  const res = await apiUpload<ApiResponse<BuildArtifact>>(`/v2/builds/${buildId}/artifacts`, formData);
  return res.data;
}

export interface ArtifactValidationReport {
  valid: boolean;
  builds: Array<{
    label: string;
    buildId: string | null;
    status: string | null;
    artifacts: {
      plaintextHex: Record<string, boolean>;
      encryptedCfw: Record<string, boolean>;
      manifest: boolean;
    };
    complete: boolean;
  }>;
  missing: Array<{
    label: string;
    role: string;
    artifactType: string;
  }>;
}

export async function validateBuildRunArtifacts(runId: string): Promise<ArtifactValidationReport> {
  const res = await api.post<ApiResponse<ArtifactValidationReport>>(
    `/v2/builds/runs/${runId}/validate-artifacts`
  );
  return res.data;
}

export async function resetBuild(id: string): Promise<BuildJob> {
  const res = await api.post<ApiResponse<BuildJob>>(`/v2/builds/${id}/reset`, {});
  return res.data;
}

export async function cancelBuildRun(id: string): Promise<BuildRunDetail> {
  const res = await api.post<ApiResponse<BuildRunDetail>>(`/v2/builds/runs/${id}/cancel`, {});
  return res.data;
}

export async function retriggerBuildRun(id: string): Promise<{ buildRunId: string; jobCount: number }> {
  const res = await api.post<ApiResponse<{ buildRunId: string; jobCount: number }>>(`/v2/builds/runs/${id}/retrigger`, {});
  return res.data;
}

export async function triggerBuildRunValidation(
  runId: string
): Promise<{ runId: string; validationRunId: string; status: string }> {
  const res = await api.post<ApiResponse<{ runId: string; validationRunId: string; status: string }>>(
    `/v2/builds/runs/${runId}/validate`, {}
  );
  return res.data;
}

// ── Build Run Sessions ─────────────────────────────────────────

export interface BuildRunSessionSummary {
  id: string;
  name: string;
  status: string;
  startedAt: string | null;
  finishedAt: string | null;
  passedCount: number;
  failedCount: number;
  config: Record<string, unknown> | null;
}

export async function fetchBuildRunSessions(runId: string): Promise<BuildRunSessionSummary[]> {
  const res = await apiFetch<ApiResponse<BuildRunSessionSummary[]>>(
    `/v2/builds/runs/${runId}/sessions`
  );
  return Array.isArray(res.data) ? res.data : [];
}

// ── Downloads ───────────────────────────────────────────────────

/**
 * Download all artifacts for a single build as a ZIP.
 */
export async function downloadBuildArtifacts(
  buildId: string,
  product: string,
  variant: string,
  version: string
): Promise<void> {
  const filename = `${product}_${variant}_${version}.zip`;
  await apiDownload(`/v2/builds/${buildId}/artifacts/download`, filename);
}

/**
 * Download all artifacts for a build run (all builds) as a ZIP.
 */
export async function downloadBuildRunArtifacts(
  runId: string,
  product: string,
  branch: string
): Promise<void> {
  const safeBranch = branch.replace(/[^a-zA-Z0-9-_]/g, '_');
  const filename = `${product}_${safeBranch}_all.zip`;
  await apiDownload(`/v2/builds/runs/${runId}/artifacts/download`, filename);
}

/**
 * Download a single artifact by name.
 */
export async function downloadSingleArtifact(
  buildId: string,
  artifactName: string
): Promise<void> {
  await apiDownload(`/v2/builds/${buildId}/artifacts/${encodeURIComponent(artifactName)}`, artifactName);
}

// ── PR Build Runs ─────────────────────────────────────────────────

export interface FetchPrBuildRunsParams {
  page?: number;
  limit?: number;
  productId?: string;
  status?: string; // "active" | "completed" | "failed"
}

export async function fetchPrBuildRuns(
  params?: FetchPrBuildRunsParams
): Promise<{ data: PrBuildSummary[]; pagination: Pagination }> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set('page', String(params.page));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.productId) qs.set('productId', params.productId);
  if (params?.status) qs.set('status', params.status);

  // API returns { data: { data: [...], pagination: {...} }, errors: [] }
  const res = await apiFetch<ApiResponse<{ data: PrBuildSummary[]; pagination: Pagination }>>(
    `/v2/builds/prs?${qs.toString()}`
  );
  const inner = res.data as { data: PrBuildSummary[]; pagination: Pagination };
  return {
    data: inner?.data ?? [],
    pagination: inner?.pagination ?? { page: 1, limit: 20, total: 0, pages: 0 },
  };
}

// ── Build Summary ─────────────────────────────────────────────────

export async function fetchBuildSummary(): Promise<BuildSummary> {
  const res = await apiFetch<ApiResponse<BuildSummary>>('/v2/builds/summary');
  return res.data;
}
