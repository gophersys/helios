/** UI component type definitions */

export interface SelectOption {
  value: string;
  label: string;
}

export interface Tab {
  id: string;
  label: string;
  icon?: any;
  badge?: string | number;
  disabled?: boolean;
}
