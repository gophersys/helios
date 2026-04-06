/** UI component type definitions */

export interface SelectOption {
  value: string;
  label: string;
}

export interface Tab {
  id: string;
  label: string;
  // Lucide icons use legacy Svelte component types, so we use a permissive type here
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  icon?: any;
  badge?: string | number;
  disabled?: boolean;
}
