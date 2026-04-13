import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { ProductStageConfig } from '$lib/types/stages';

/** Build query string for stage config disambiguation. */
function _stageQuery(opts?: { configId?: string; type?: string; boardRevisionId?: string }): string {
  if (!opts) return '';
  const params = new URLSearchParams();
  if (opts.configId) params.set('configId', opts.configId);
  if (opts.type) params.set('type', opts.type);
  if (opts.boardRevisionId) params.set('boardRevisionId', opts.boardRevisionId);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function listStageConfigs(productId: string, type?: string, boardRevisionId?: string): Promise<ProductStageConfig[]> {
  const qs = _stageQuery({ type, boardRevisionId });
  const res = await apiFetch<ApiResponse<ProductStageConfig[]>>(`/v2/products/${productId}/stages${qs}`);
  return res.data;
}

export async function getStageConfig(productId: string, stage: number, configId?: string): Promise<ProductStageConfig> {
  const qs = _stageQuery({ configId });
  const res = await apiFetch<ApiResponse<ProductStageConfig>>(`/v2/products/${productId}/stages/${stage}${qs}`);
  return res.data;
}

export async function createStageConfig(productId: string, data: Partial<ProductStageConfig>): Promise<ProductStageConfig> {
  const res = await apiFetch<ApiResponse<ProductStageConfig>>(`/v2/products/${productId}/stages`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateStageConfig(
  productId: string,
  stage: number,
  data: Partial<ProductStageConfig>,
  configId?: string,
): Promise<ProductStageConfig> {
  const qs = _stageQuery({ configId });
  const res = await apiFetch<ApiResponse<ProductStageConfig>>(`/v2/products/${productId}/stages/${stage}${qs}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteStageConfig(productId: string, stage: number, configId?: string): Promise<void> {
  const qs = _stageQuery({ configId });
  await apiFetch(`/v2/products/${productId}/stages/${stage}${qs}`, { method: 'DELETE' });
}

export async function triggerStageRun(
  productId: string,
  stage: number,
  assetSetId: string,
  configId?: string,
): Promise<any> {
  const qs = _stageQuery({ configId });
  const res = await apiFetch<ApiResponse<any>>(`/v2/products/${productId}/stages/${stage}/trigger-run${qs}`, {
    method: 'POST',
    body: JSON.stringify({ assetSetId }),
  });
  return res.data;
}

export async function initializeStages(productId: string, boardRevisionId?: string): Promise<ProductStageConfig[]> {
  const body: Record<string, string> = {};
  if (boardRevisionId) body.boardRevisionId = boardRevisionId;

  const res = await apiFetch<ApiResponse<ProductStageConfig[]>>(`/v2/products/${productId}/stages/initialize`, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  });
  return res.data;
}
