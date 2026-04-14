import { browser } from '$app/environment';

export interface ErrorReport {
  id: string;
  timestamp: string;
  type: 'js' | 'api' | 'unhandled';
  message: string;
  status?: number;
  url?: string;
  method?: string;
  stack?: string;
  componentStack?: string;
  userAgent: string;
  currentPath: string;
  requestBody?: string;
  responseBody?: string;
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

class ErrorReporterState {
  current = $state<ErrorReport | null>(null);
  reportSent = $state(false);

  reportError(report: ErrorReport): void {
    this.current = report;
    this.reportSent = false;
  }

  dismiss(): void {
    this.current = null;
    this.reportSent = false;
  }

  async sendReport(): Promise<void> {
    if (!this.current) return;
    // Stub: log to console for now, will POST to backend later
    console.info('[error-reporter] Sending error report:', this.current);
    this.reportSent = true;
  }
}

let instance: ErrorReporterState | null = null;

export function getErrorReporter(): ErrorReporterState {
  if (!instance) {
    instance = new ErrorReporterState();
  }
  return instance;
}

/** Report a JS runtime or unhandled promise rejection error. */
export function reportJsError(opts: {
  message: string;
  stack?: string;
  url?: string;
  componentStack?: string;
}): void {
  const reporter = getErrorReporter();
  reporter.reportError({
    id: generateId(),
    timestamp: new Date().toISOString(),
    type: 'js',
    message: opts.message,
    stack: opts.stack,
    url: opts.url,
    componentStack: opts.componentStack,
    userAgent: browser ? navigator.userAgent : '',
    currentPath: browser ? window.location.pathname : '',
  });
}

/** Report an API error (typically 500+ status codes). */
export function reportApiError(opts: {
  status: number;
  url: string;
  method: string;
  message: string;
  requestBody?: string;
  responseBody?: string;
}): void {
  const reporter = getErrorReporter();
  reporter.reportError({
    id: generateId(),
    timestamp: new Date().toISOString(),
    type: 'api',
    message: opts.message,
    status: opts.status,
    url: opts.url,
    method: opts.method,
    requestBody: opts.requestBody,
    responseBody: opts.responseBody,
    userAgent: browser ? navigator.userAgent : '',
    currentPath: browser ? window.location.pathname : '',
  });
}
