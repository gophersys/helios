import { Calendar, GitCommit, User } from 'lucide-svelte';

export interface TriggerConfigEntry {
  icon: typeof GitCommit;
  label: string;
  color: string;
}

export const TRIGGER_CONFIG: Record<string, TriggerConfigEntry> = {
  webhook: { icon: GitCommit, label: 'Bitbucket', color: 'text-info bg-info-muted' },
  manual: { icon: User, label: 'Manual', color: 'text-accent bg-accent-muted' },
  scheduled: { icon: Calendar, label: 'Scheduled', color: 'text-warning bg-warning-muted' },
};

export function getTriggerConfig(type: string): TriggerConfigEntry {
  return TRIGGER_CONFIG[type] || TRIGGER_CONFIG.manual;
}

export interface ProductInfoEntry {
  name: string;
  repo: string;
  rev: string;
}

export const PRODUCT_INFO: Record<string, ProductInfoEntry> = {
  alpha_b0: { name: 'Alpha', repo: 'alpha_fw', rev: 'B0' },
  sigma5_b0: { name: 'Sigma5', repo: 'sigma5_fw', rev: 'B0' },
  sigma5_c0: { name: 'Sigma5', repo: 'sigma5_fw', rev: 'C0' },
  theta_c0: { name: 'Theta', repo: 'theta_fw', rev: 'C0' },
};

export function getProductInfo(product: string): ProductInfoEntry {
  const key = product.toLowerCase().replace(/\s+/g, '_');
  return PRODUCT_INFO[key] ?? { name: product, repo: `${key}_fw`, rev: '' };
}
