import { type ComponentType } from 'react';
import { type LucideIcon, Monitor, KeyRound } from 'lucide-react';
import { SystemSection } from './sections/system-section';
import { ApiKeysSection } from './sections/api-keys-section';

export interface SettingsSection {
  id: string;
  label: string;
  icon: LucideIcon;
  component: ComponentType;
  requiredPermission?: string;
}

export const settingsSections: SettingsSection[] = [
  { id: 'system', label: 'System', icon: Monitor, component: SystemSection },
  { id: 'api-keys', label: 'API Keys', icon: KeyRound, component: ApiKeysSection },
];
