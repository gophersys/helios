import { type ComponentType } from 'react';
import { type LucideIcon, Monitor, KeyRound, Shield } from 'lucide-react';
import { SystemSection } from './sections/system-section';
import { ApiKeysSection } from './sections/api-keys-section';
import { PermissionsSection } from './sections/permissions-section';

export interface SettingsSection {
  id: string;
  label: string;
  icon: LucideIcon;
  component: ComponentType;
  requiredPermission?: string;
}

export const settingsSections: SettingsSection[] = [
  { id: 'permissions', label: 'My Permissions', icon: Shield, component: PermissionsSection },
  { id: 'api-keys', label: 'API Keys', icon: KeyRound, component: ApiKeysSection },
  { id: 'system', label: 'System', icon: Monitor, component: SystemSection },
];
