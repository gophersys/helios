/**
 * Centralized color mappings for consistent UI styling.
 * Update these to change colors globally across the app.
 */

/** Color configuration for action types (CRUD operations, permissions) */
export interface ActionColor {
  bg: string;
  text: string;
  dot: string;
  border?: string;
}

/** Colors for RBAC/CRUD actions */
export const ACTION_COLORS: Record<string, ActionColor> = {
  Create: {
    bg: 'bg-success/10',
    text: 'text-success',
    dot: 'bg-success',
    border: 'border-success/20'
  },
  View: {
    bg: 'bg-info/10',
    text: 'text-info',
    dot: 'bg-info',
    border: 'border-info/20'
  },
  Read: {
    bg: 'bg-info/10',
    text: 'text-info',
    dot: 'bg-info',
    border: 'border-info/20'
  },
  Update: {
    bg: 'bg-warning/10',
    text: 'text-warning',
    dot: 'bg-warning',
    border: 'border-warning/20'
  },
  Edit: {
    bg: 'bg-warning/10',
    text: 'text-warning',
    dot: 'bg-warning',
    border: 'border-warning/20'
  },
  Delete: {
    bg: 'bg-error/10',
    text: 'text-error',
    dot: 'bg-error',
    border: 'border-error/20'
  },
  Manage: {
    bg: 'bg-accent/10',
    text: 'text-accent',
    dot: 'bg-accent',
    border: 'border-accent/20'
  },
  Admin: {
    bg: 'bg-violet-500/10',
    text: 'text-violet-500',
    dot: 'bg-violet-500',
    border: 'border-violet-500/20'
  },
};

/** Default color when action type is not found */
export const DEFAULT_ACTION_COLOR: ActionColor = {
  bg: 'bg-surface-2',
  text: 'text-text-secondary',
  dot: 'bg-text-tertiary',
  border: 'border-border'
};

/** Get color configuration for an action type */
export function getActionColor(action: string): ActionColor {
  return ACTION_COLORS[action] || DEFAULT_ACTION_COLOR;
}

// ============================================================================
// STATUS COLORS
// ============================================================================

export interface StatusColor {
  bg: string;
  text: string;
  dot: string;
  border?: string;
}

/** Colors for status indicators (pods, deployments, etc.) */
export const STATUS_COLORS: Record<string, StatusColor> = {
  // Success states
  Running: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },
  Ready: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },
  Active: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },
  Completed: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },
  Healthy: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },
  Normal: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },
  Succeeded: { bg: 'bg-success/10', text: 'text-success', dot: 'bg-success' },

  // Warning states
  Pending: { bg: 'bg-warning/10', text: 'text-warning', dot: 'bg-warning' },
  Starting: { bg: 'bg-warning/10', text: 'text-warning', dot: 'bg-warning' },
  Terminating: { bg: 'bg-warning/10', text: 'text-warning', dot: 'bg-warning' },
  ContainerCreating: { bg: 'bg-warning/10', text: 'text-warning', dot: 'bg-warning' },
  Warning: { bg: 'bg-warning/10', text: 'text-warning', dot: 'bg-warning' },

  // Error states
  Failed: { bg: 'bg-error/10', text: 'text-error', dot: 'bg-error' },
  Error: { bg: 'bg-error/10', text: 'text-error', dot: 'bg-error' },
  CrashLoopBackOff: { bg: 'bg-error/10', text: 'text-error', dot: 'bg-error' },
  NotReady: { bg: 'bg-error/10', text: 'text-error', dot: 'bg-error' },
  Unknown: { bg: 'bg-error/10', text: 'text-error', dot: 'bg-error' },
  ImagePullBackOff: { bg: 'bg-error/10', text: 'text-error', dot: 'bg-error' },

  // Info states
  Info: { bg: 'bg-info/10', text: 'text-info', dot: 'bg-info' },
};

/** Default status color */
export const DEFAULT_STATUS_COLOR: StatusColor = {
  bg: 'bg-surface-2',
  text: 'text-text-secondary',
  dot: 'bg-text-tertiary'
};

/** Get color configuration for a status */
export function getStatusColor(status: string): StatusColor {
  return STATUS_COLORS[status] || DEFAULT_STATUS_COLOR;
}

// ============================================================================
// SEVERITY COLORS
// ============================================================================

export interface SeverityColor {
  bg: string;
  text: string;
  border: string;
}

/** Colors for severity levels (logs, alerts) */
export const SEVERITY_COLORS: Record<string, SeverityColor> = {
  critical: { bg: 'bg-error/10', text: 'text-error', border: 'border-error/20' },
  error: { bg: 'bg-error/10', text: 'text-error', border: 'border-error/20' },
  warning: { bg: 'bg-warning/10', text: 'text-warning', border: 'border-warning/20' },
  info: { bg: 'bg-info/10', text: 'text-info', border: 'border-info/20' },
  debug: { bg: 'bg-surface-2', text: 'text-text-secondary', border: 'border-border' },
  success: { bg: 'bg-success/10', text: 'text-success', border: 'border-success/20' },
};

/** Get color for a severity level */
export function getSeverityColor(severity: string): SeverityColor {
  return SEVERITY_COLORS[severity.toLowerCase()] || SEVERITY_COLORS.info;
}
