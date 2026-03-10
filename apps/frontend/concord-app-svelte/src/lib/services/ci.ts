import { apiFetch, api } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type {
  BuildJob,
  BuildJobArtifact,
  Pipeline,
  PipelineStageInfo,
  PipelineStageStatus,
  TriggerBuildConfig,
  TriggerPipelineConfig,
} from '$lib/types/ci';
import type { Pagination } from '$lib/types/models';

// ── Pipelines ──────────────────────────────────────────────────

export interface FetchPipelinesParams {
  page?: number;
  limit?: number;
  status?: string;
  branch?: string;
  product?: string;
}

interface PaginatedApiResponse<T> {
  data: T;
  errors: { message: string }[];
  page?: number;
  totalPages?: number;
  totalResults?: number;
  resultsPerPage?: number;
}

export async function fetchPipelines(
  params?: FetchPipelinesParams
): Promise<{ data: Pipeline[]; pagination: Pagination }> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set('page', String(params.page));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.status) qs.set('status', params.status);
  if (params?.branch) qs.set('branch', params.branch);
  if (params?.product) qs.set('product', params.product);

  const res = await apiFetch<PaginatedApiResponse<Pipeline[]>>(
    `/v2/ci/pipelines?${qs.toString()}`
  );
  return {
    data: res.data,
    pagination: {
      page: res.page ?? 1,
      limit: res.resultsPerPage ?? 25,
      total: res.totalResults ?? 0,
      pages: res.totalPages ?? 0,
    },
  };
}

export async function fetchPipeline(id: string): Promise<Pipeline> {
  const res = await apiFetch<ApiResponse<Pipeline>>(`/v2/ci/pipelines/${id}`);
  const pipeline = res.data;

  // Compute stages from pipeline status and builds
  const stages: PipelineStageInfo[] = [];

  // BUILD stage
  const builds = pipeline.builds ?? [];
  const allBuildsComplete = builds.length > 0 && builds.every(b => b.status === 'SUCCESS' || b.status === 'FAILED' || b.status === 'CANCELLED');
  const anyBuildFailed = builds.some(b => b.status === 'FAILED');
  const anyBuildRunning = builds.some(b => b.status === 'BUILDING');

  let buildStatus: PipelineStageStatus = 'PENDING';
  if (anyBuildRunning) buildStatus = 'RUNNING';
  else if (anyBuildFailed) buildStatus = 'FAILED';
  else if (allBuildsComplete && builds.length > 0) buildStatus = 'SUCCESS';
  else if (builds.length > 0) buildStatus = 'RUNNING';

  stages.push({
    stage: 'BUILD',
    status: buildStatus,
    startedAt: pipeline.startedAt,
    finishedAt: allBuildsComplete ? pipeline.finishedAt : null,
    detail: builds.length > 0 ? `${builds.filter(b => b.status === 'SUCCESS').length}/${builds.length} builds passed` : null,
  });

  // FLASH stage (only if validation is configured)
  if (pipeline.validationRunId || pipeline.status === 'VALIDATING') {
    stages.push({
      stage: 'FLASH',
      status: buildStatus === 'SUCCESS' ? 'SUCCESS' : buildStatus === 'FAILED' ? 'SKIPPED' : 'PENDING',
      startedAt: null,
      finishedAt: null,
      detail: null,
    });
  }

  // VALIDATE stage
  if (pipeline.validationRunId) {
    stages.push({
      stage: 'VALIDATE',
      status: pipeline.status === 'COMPLETED' ? 'SUCCESS' : pipeline.status === 'FAILED' ? 'FAILED' : 'PENDING',
      startedAt: null,
      finishedAt: null,
      detail: null,
    });
  }

  // Set computed fields for UI compatibility
  pipeline.stages = stages;
  pipeline.buildJob = builds.length > 0 ? {
    id: builds[0].id,
    product: builds[0].product,
    board: pipeline.board,
    target: '',
    variant: builds[0].variant,
    branch: pipeline.branch,
    commitSha: pipeline.commitSha ?? '',
    status: builds[0].status,
    versionString: builds[0].versionString,
    buildLog: null,
    startedAt: pipeline.startedAt,
    finishedAt: pipeline.finishedAt,
    durationSeconds: builds[0].durationSeconds,
    createdAt: pipeline.createdAt,
    artifacts: [],
  } : null;

  return pipeline;
}

export async function triggerPipeline(config: TriggerPipelineConfig): Promise<Pipeline> {
  const res = await api.post<ApiResponse<Pipeline>>('/v2/ci/trigger', config);
  return res.data;
}

// ── Builds ─────────────────────────────────────────────────────

export interface FetchBuildsParams {
  page?: number;
  limit?: number;
  status?: string;
  branch?: string;
  product?: string;
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

  const res = await apiFetch<PaginatedApiResponse<BuildJob[]>>(
    `/v2/ci/builds?${qs.toString()}`
  );
  return {
    data: res.data,
    pagination: {
      page: res.page ?? 1,
      limit: res.resultsPerPage ?? 25,
      total: res.totalResults ?? 0,
      pages: res.totalPages ?? 0,
    },
  };
}

export async function fetchBuild(id: string): Promise<BuildJob> {
  const res = await apiFetch<ApiResponse<BuildJob>>(`/v2/ci/builds/${id}`);
  return res.data;
}

export async function fetchBuildLog(id: string): Promise<string> {
  const res = await apiFetch<ApiResponse<{ log: string }>>(`/v2/ci/builds/${id}/log`);
  return res.data.log;
}

export async function fetchBuildArtifacts(id: string): Promise<BuildJobArtifact[]> {
  const res = await apiFetch<ApiResponse<BuildJobArtifact[]>>(`/v2/ci/builds/${id}/artifacts`);
  return res.data;
}

export async function triggerBuild(config: TriggerBuildConfig): Promise<BuildJob> {
  const res = await api.post<ApiResponse<BuildJob>>('/v2/ci/builds', config);
  return res.data;
}
