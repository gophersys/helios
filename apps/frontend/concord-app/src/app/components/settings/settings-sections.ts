import { type ComponentType } from 'react';
import { type LucideIcon, Monitor } from 'lucide-react';
import { SystemSection } from './sections/system-section';

export interface SettingsSection {
  id: string;
  label: string;
  icon: LucideIcon;
  component: ComponentType;
  requiredRole?: 'ADMIN' | 'OPERATOR';
}

export const settingsSections: SettingsSection[] = [
  { id: 'system', label: 'System', icon: Monitor, component: SystemSection },
];
