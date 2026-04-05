/** UI component type definitions */

import type { Component } from 'svelte';

export interface SelectOption {
  value: string;
  label: string;
}

export interface Tab {
  id: string;
  label: string;
  icon?: Component;
  badge?: string | number;
  disabled?: boolean;
}
