import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { ValidationQueueEntry, QueueStats } from '$lib/types/queue';
import type { Pagination } from '$lib/types/models';

interface PaginatedApiResponse<T> {
  data: T;
  errors?: { message: string }[];
  page?: number;
  totalPages?: number;
  totalResults?: number;
  resultsPerPage?: number;
}

export async function listQueue(params?: {
  status?: string;
  stage?: number;
  page?: number;
  limit?: number;
}): Promise<{ data: ValidationQueueEntry[]; pagination: Pagination }> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.stage) searchParams.set('stage', String(params.stage));
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  const qs = searchParams.toString();

  const res = await apiFetch<PaginatedApiResponse<ValidationQueueEntry[]>>(
    `/v2/sessions/queue${qs ? `?${qs}` : ''}`
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

export async function getQueueEntry(entryId: string): Promise<ValidationQueueEntry> {
  const res = await apiFetch<ApiResponse<ValidationQueueEntry>>(`/v2/sessions/queue/${entryId}`);
  return res.data;
}

export async function createQueueEntry(data: {
  pipelineRunId: string;
  stage: number;
  priority?: number;
  reason?: string;
}): Promise<ValidationQueueEntry> {
  const res = await apiFetch<ApiResponse<ValidationQueueEntry>>('/v2/sessions/queue', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function cancelQueueEntry(entryId: string): Promise<ValidationQueueEntry> {
  const res = await apiFetch<ApiResponse<ValidationQueueEntry>>(`/v2/sessions/queue/${entryId}/cancel`, {
    method: 'POST',
  });
  return res.data;
}

export async function promoteQueueEntry(entryId: string): Promise<ValidationQueueEntry> {
  const res = await apiFetch<ApiResponse<ValidationQueueEntry>>(`/v2/sessions/queue/${entryId}/promote`, {
    method: 'POST',
  });
  return res.data;
}

export async function getQueueStats(): Promise<QueueStats> {
  const res = await apiFetch<ApiResponse<QueueStats>>('/v2/sessions/queue/stats');
  return res.data;
}
