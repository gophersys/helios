import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { ProductStageConfig } from '$lib/types/stages';

export async function listStageConfigs(productId: string, type?: string, boardRevisionId?: string): Promise<ProductStageConfig[]> {
  const params = new URLSearchParams();
  if (type) params.set('type', type);
  if (boardRevisionId) params.set('boardRevisionId', boardRevisionId);
  const qs = params.toString();
  const res = await apiFetch<ApiResponse<ProductStageConfig[]>>(`/v2/products/${productId}/stages${qs ? `?${qs}` : ''}`);
  return res.data;
}

export async function getStageConfig(productId: string, stage: number): Promise<ProductStageConfig> {
  const res = await apiFetch<ApiResponse<ProductStageConfig>>(`/v2/products/${productId}/stages/${stage}`);
  return res.data;
}

export async function createStageConfig(productId: string, data: Partial<ProductStageConfig>): Promise<ProductStageConfig> {
  const res = await apiFetch<ApiResponse<ProductStageConfig>>(`/v2/products/${productId}/stages`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function updateStageConfig(productId: string, stage: number, data: Partial<ProductStageConfig>): Promise<ProductStageConfig> {
  const res = await apiFetch<ApiResponse<ProductStageConfig>>(`/v2/products/${productId}/stages/${stage}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  return res.data;
}

export async function deleteStageConfig(productId: string, stage: number): Promise<void> {
  await apiFetch(`/v2/products/${productId}/stages/${stage}`, { method: 'DELETE' });
}

export async function triggerStageRun(
  productId: string,
  stage: number,
  assetSetId: string,
): Promise<any> {
  const res = await apiFetch<ApiResponse<any>>(`/v2/products/${productId}/stages/${stage}/trigger-run`, {
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
