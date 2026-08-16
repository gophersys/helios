import { apiFetch, api } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type {
  TestBedDesign,
  TestBedDesignSummary,
  TestBench,
  UnregisteredMtib,
  Pagination,
} from '$lib/types/models';

// ── TestBed Designs ────────────────────────────────────────────

export interface FetchDesignsParams {
  page?: number;
  limit?: number;
  product?: string;
}

export async function fetchDesigns(
  params?: FetchDesignsParams
): Promise<{ data: TestBedDesignSummary[]; pagination: Pagination }> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set('page', String(params.page));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.product) qs.set('product', params.product);

  const res = await apiFetch<ApiResponse<{ data: TestBedDesignSummary[]; pagination: Pagination }>>(
    `/v2/test-bed-designs?${qs.toString()}`
  );
  return res.data;
}

export async function fetchDesign(id: string): Promise<TestBedDesign> {
  const res = await apiFetch<ApiResponse<TestBedDesign>>(`/v2/test-bed-designs/${id}`);
  return res.data;
}

export interface CreateDesignRequest {
  name: string;
  boardRevisionId: string;
  revision: string;
  profileTemplate: Record<string, unknown>;
  schematicUrl?: string;
  bomUrl?: string;
  assemblyGuide?: string;
  notes?: string;
}

export async function createDesign(data: CreateDesignRequest): Promise<TestBedDesign> {
  const res = await api.post<ApiResponse<TestBedDesign>>('/v2/test-bed-designs', data);
  return res.data;
}

export async function updateDesign(
  id: string,
  data: Partial<CreateDesignRequest>
): Promise<TestBedDesign> {
  const res = await apiFetch<ApiResponse<TestBedDesign>>(`/v2/test-bed-designs/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteDesign(id: string): Promise<void> {
  await api.delete(`/v2/test-bed-designs/${id}`);
}

// ── Test Benches ───────────────────────────────────────────────

export interface FetchBenchesParams {
  page?: number;
  limit?: number;
  product?: string;
  status?: string;
}

export async function fetchBenches(
  params?: FetchBenchesParams
): Promise<{ data: TestBench[]; pagination: Pagination }> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set('page', String(params.page));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.product) qs.set('product', params.product);
  if (params?.status) qs.set('status', params.status);

  const res = await apiFetch<ApiResponse<{ data: TestBench[]; pagination: Pagination }>>(
    `/v2/fixtures/benches?${qs.toString()}`
  );
  return res.data;
}

export async function fetchBench(id: string): Promise<TestBench> {
  const res = await apiFetch<ApiResponse<TestBench>>(`/v2/fixtures/benches/${id}`);
  return res.data;
}

export async function discoverMtibs(): Promise<UnregisteredMtib[]> {
  const res = await apiFetch<ApiResponse<UnregisteredMtib[]>>('/v2/fixtures/benches/discover');
  return res.data;
}

export interface CreateBenchRequest {
  stationId: string;
  name: string;
  mtibAddress: string;
  mtibRevision?: string;
  testBedDesignId?: string;
  profileOverrides?: Record<string, unknown>;
  dutProduct: string;
  dutRevision: string;
  dutDeviceId?: string;
  dutSnr?: string;
  dutImei?: string;
  dutIccids?: string[];
  jlinkAppSerial?: string;
  jlinkCommsSerial?: string;
  uartAppPath?: string;
  uartCommsPath?: string;
  status?: string;
  metadata?: Record<string, unknown>;
}

export async function createBench(data: CreateBenchRequest): Promise<TestBench> {
  const res = await api.post<ApiResponse<TestBench>>('/v2/fixtures/benches', data);
  return res.data;
}

export async function updateBench(
  id: string,
  data: Partial<CreateBenchRequest>
): Promise<TestBench> {
  const res = await apiFetch<ApiResponse<TestBench>>(`/v2/fixtures/benches/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteBench(id: string): Promise<void> {
  await api.delete(`/v2/fixtures/benches/${id}`);
}

export async function fetchBenchProfile(id: string): Promise<Record<string, unknown>> {
  const res = await apiFetch<ApiResponse<Record<string, unknown>>>(
    `/v2/fixtures/benches/${id}/profile`
  );
  return res.data;
}
