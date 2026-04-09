import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { ProductStageConfig } from '$lib/types/stages';

export async function listStageConfigs(productId: string, type?: string): Promise<ProductStageConfig[]> {
  const query = type ? `?type=${type}` : '';
  const res = await apiFetch<ApiResponse<ProductStageConfig[]>>(`/v2/products/${productId}/stages${query}`);
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

export async function initializeStages(productId: string): Promise<ProductStageConfig[]> {
  const res = await apiFetch<ApiResponse<ProductStageConfig[]>>(`/v2/products/${productId}/stages/initialize`, {
    method: 'POST',
  });
  return res.data;
}
