import { apiFetch } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { Product } from '$lib/types/models';

export async function fetchProducts(): Promise<Product[]> {
  const res = await apiFetch<ApiResponse<Product[] | { data: Product[] }>>('/v2/products');
  const payload = res.data;
  return Array.isArray(payload) ? payload : (payload as { data: Product[] }).data || [];
}
