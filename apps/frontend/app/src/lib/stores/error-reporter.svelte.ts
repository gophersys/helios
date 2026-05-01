/**
 * Global error reporter — captures JS errors, API errors, WebSocket errors,
 * and user-reported issues with full context for debugging.
 *
 * Every report includes: who, where, when, what, and how to reproduce.
 * Reports are stored locally and can be sent to the backend ticketing system.
 */

import { browser } from '$app/environment';
import { PUBLIC_APP_ENVIRONMENT, PUBLIC_APP_VERSION } from '$env/static/public';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ErrorType = 'js' | 'api' | 'websocket' | 'validation' | 'unhandled' | 'user_report';
export type ErrorSeverity = 'critical' | 'error' | 'warning' | 'info';

export interface ErrorReport {
  // Identity
  id: string;
  timestamp: string;
  severity: ErrorSeverity;
  type: ErrorType;

  // What happened
  message: string;
  details?: string;
  stack?: string;
  componentStack?: string;

  // API context (for type=api)
  status?: number;
  url?: string;
  method?: string;
  requestBody?: string;
  responseBody?: string;
  requestDurationMs?: number;

  // WebSocket context (for type=websocket)
  wsNamespace?: string;
  wsEvent?: string;

  // User context
  userId?: string;
  userEmail?: string;
  userRole?: string;
  userPermissions?: string[];

  // Environment context
  currentPath: string;
  previousPath?: string;
  userAgent: string;
  appVersion: string;
  environment: string;
  screenSize?: string;

  // Action context — what was the user doing
  action?: string;           // e.g., "creating manufacturing session"
  entityType?: string;       // e.g., "ManufacturingSession"
  entityId?: string;         // e.g., "cmnx..."
  relatedEntities?: Record<string, string>; // e.g., { fixtureId: "...", productId: "..." }

  // Browser state
  networkOnline?: boolean;
  memoryUsage?: number;

  // User notes (for user_report type)
  userNotes?: string;

  // History — recent actions before the error
  recentActions?: string[];
}

// ---------------------------------------------------------------------------
// Action tracking — breadcrumbs of what the user did before the error
// ---------------------------------------------------------------------------

const MAX_ACTIONS = 20;
let _recentActions: string[] = [];

/** Track a user action for error context breadcrumbs. */
export function trackAction(action: string): void {
  _recentActions.push(`${new Date().toISOString().slice(11, 23)} ${action}`);
  if (_recentActions.length > MAX_ACTIONS) {
    _recentActions = _recentActions.slice(-MAX_ACTIONS);
  }
}

// ---------------------------------------------------------------------------
// Environment + user context resolution
// ---------------------------------------------------------------------------

function getAppVersion(): string {
  return PUBLIC_APP_VERSION || 'unknown';
}

function getEnvironment(): string {
  return PUBLIC_APP_ENVIRONMENT || 'unknown';
}

function getScreenSize(): string {
  if (!browser) return '';
  return `${window.innerWidth}x${window.innerHeight}`;
}

function getNetworkOnline(): boolean {
  if (!browser) return true;
  return navigator.onLine;
}

function getUserContext(): { userId?: string; userEmail?: string; userRole?: string } {
  if (!browser) return {};
  try {
    const raw = localStorage.getItem('concord-user');
    if (raw) {
      const user = JSON.parse(raw);
      return {
        userId: user.id,
        userEmail: user.email,
        userRole: user.role,
      };
    }
  } catch { /* ignore */ }
  return {};
}

function getPreviousPath(): string {
  if (!browser) return '';
  return (globalThis as any).__CONCORD_PREV_PATH__ ?? '';
}

/** Call from router to track page navigation. */
export function trackNavigation(path: string): void {
  if (browser) {
    (globalThis as any).__CONCORD_PREV_PATH__ = (globalThis as any).__CONCORD_CURRENT_PATH__ ?? '';
    (globalThis as any).__CONCORD_CURRENT_PATH__ = path;
    trackAction(`navigate → ${path}`);
  }
}

// ---------------------------------------------------------------------------
// Report builder — enriches raw error info with full context
// ---------------------------------------------------------------------------

function generateId(): string {
  return `err_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function buildReport(partial: Partial<ErrorReport> & { type: ErrorType; message: string }): ErrorReport {
  const user = getUserContext();
  return {
    id: generateId(),
    timestamp: new Date().toISOString(),
    severity: partial.severity ?? (partial.type === 'api' && (partial.status ?? 0) >= 500 ? 'critical' : 'error'),
    currentPath: browser ? window.location.pathname : '',
    previousPath: getPreviousPath(),
    userAgent: browser ? navigator.userAgent : '',
    appVersion: getAppVersion(),
    environment: getEnvironment(),
    screenSize: getScreenSize(),
    networkOnline: getNetworkOnline(),
    recentActions: [..._recentActions],
    ...user,
    ...partial,
  };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

class ErrorReporterState {
  current = $state<ErrorReport | null>(null);
  history = $state<ErrorReport[]>([]);
  reportSent = $state(false);

  reportError(report: ErrorReport): void {
    this.current = report;
    this.reportSent = false;
    this.history = [...this.history.slice(-49), report]; // Keep last 50
  }

  dismiss(): void {
    this.current = null;
    this.reportSent = false;
  }

  private _sending = false;

  /**
   * POST the current report to the backend ticketing endpoint.
   * Returns true if the server accepted it, false on transport or
   * non-2xx response. Always sets `reportSent = true` so the UI moves
   * past the Send button regardless — caller can decide whether to
   * surface a success or failure toast based on the return value.
   */
  async sendReport(): Promise<boolean> {
    if (!this.current || this._sending) return false;
    this._sending = true;
    let ok = false;
    try {
      const token = localStorage.getItem('concord-token');
      const res = await fetch('/v2/system/error-reports', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(this.current),
      });
      if (!res.ok) {
        console.error('[error-reporter] Server returned', res.status);
      } else {
        ok = true;
      }
    } catch (err) {
      console.error('[error-reporter] Failed to send report:', err);
    } finally {
      this._sending = false;
      this.reportSent = true;
    }
    return ok;
  }

  getReportJson(): string {
    if (!this.current) return '{}';
    return JSON.stringify(this.current, null, 2);
  }
}

let instance: ErrorReporterState | null = null;

export function getErrorReporter(): ErrorReporterState {
  if (!instance) {
    instance = new ErrorReporterState();
  }
  return instance;
}

// ---------------------------------------------------------------------------
// Convenience reporters — call these from anywhere
// ---------------------------------------------------------------------------

/** JS runtime error or unhandled promise rejection. */
export function reportJsError(opts: {
  message: string;
  stack?: string;
  url?: string;
  componentStack?: string;
}): void {
  getErrorReporter().reportError(buildReport({
    type: 'js',
    severity: 'critical',
    message: opts.message,
    stack: opts.stack,
    url: opts.url,
    componentStack: opts.componentStack,
  }));
}

/** API error (typically 4xx/5xx responses). */
export function reportApiError(opts: {
  status: number;
  url: string;
  method: string;
  message: string;
  requestBody?: string;
  responseBody?: string;
  requestDurationMs?: number;
  action?: string;
  entityType?: string;
  entityId?: string;
}): void {
  getErrorReporter().reportError(buildReport({
    type: 'api',
    severity: opts.status >= 500 ? 'critical' : 'error',
    message: `${opts.method} ${opts.url} → ${opts.status}: ${opts.message}`,
    details: opts.message,
    status: opts.status,
    url: opts.url,
    method: opts.method,
    requestBody: opts.requestBody,
    responseBody: opts.responseBody,
    requestDurationMs: opts.requestDurationMs,
    action: opts.action,
    entityType: opts.entityType,
    entityId: opts.entityId,
  }));
}

/**
 * Patterns we treat as benign socket.io reconnect noise — not real backend
 * failures. socket.io's xhr-polling fallback emits "xhr post error" and a
 * few sibling messages every time the long-poll request is interrupted
 * (page unload, brief WS gateway restart, NAT idle drop). The library
 * already retries automatically, so logging a user-visible error report
 * for each one only pollutes /v2/system/error-reports without surfacing
 * any actionable signal.
 *
 * Anything outside this list is treated as a real WS error and reported
 * normally — auth failures, namespace not found, server-emitted errors,
 * etc. all stay visible.
 */
const TRANSIENT_WS_PATTERNS = [
  /xhr post error/i,
  /xhr poll error/i,
  /websocket error\b/i,
  /transport close/i,
  /transport error/i,
];

export function isTransientWsError(message: string): boolean {
  if (!message) return false;
  return TRANSIENT_WS_PATTERNS.some((re) => re.test(message));
}

/** WebSocket error. */
export function reportWsError(opts: {
  message: string;
  namespace?: string;
  event?: string;
}): void {
  // Suppress the noisy reconnect-cycle errors socket.io emits while the
  // backend WS endpoint is briefly unreachable. We still want them visible
  // in the browser console (the websocket.ts call site logs them), but
  // we don't want them creating new error-reports rows. Real WS errors
  // (auth failure, server-emitted error events, anything not matching the
  // transient patterns above) still flow through.
  if (isTransientWsError(opts.message)) {
    trackAction(`ws ${opts.namespace ?? ''} transient: ${opts.message}`);
    return;
  }
  getErrorReporter().reportError(buildReport({
    type: 'websocket',
    severity: 'error',
    message: opts.message,
    wsNamespace: opts.namespace,
    wsEvent: opts.event,
  }));
}

/** Validation/business logic error worth reporting. */
export function reportValidationError(opts: {
  message: string;
  details?: string;
  entityType?: string;
  entityId?: string;
  relatedEntities?: Record<string, string>;
}): void {
  getErrorReporter().reportError(buildReport({
    type: 'validation',
    severity: 'warning',
    message: opts.message,
    details: opts.details,
    entityType: opts.entityType,
    entityId: opts.entityId,
    relatedEntities: opts.relatedEntities,
  }));
}

/** User-initiated bug report. */
export function reportUserIssue(opts: {
  message: string;
  userNotes: string;
  entityType?: string;
  entityId?: string;
}): void {
  getErrorReporter().reportError(buildReport({
    type: 'user_report',
    severity: 'info',
    message: opts.message,
    userNotes: opts.userNotes,
    entityType: opts.entityType,
    entityId: opts.entityId,
  }));
}
