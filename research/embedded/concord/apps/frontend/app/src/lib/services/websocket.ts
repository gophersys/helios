import { browser } from '$app/environment';
import { io, Socket } from 'socket.io-client';
import { getToken } from '$lib/api';
import { reportWsError, trackAction } from '$lib/stores/error-reporter.svelte';

let systemSocket: Socket | null = null;
let runSocket: Socket | null = null;
let notificationSocket: Socket | null = null;

export interface LogSubscription {
  namespace: string;
  pod: string;
  container: string;
  tailLines?: number;
}

export interface ExecSession {
  namespace: string;
  pod: string;
  container: string;
  command?: string[];
}

export interface UartSubscription {
  nodeId: string;
  portName: string;
  baud?: number;
}

/**
 * Get or create the Socket.IO connection to /system namespace.
 * Authenticates with JWT token.
 */
export function getSystemSocket(): Socket | null {
  if (!browser) return null;

  if (systemSocket?.connected) {
    return systemSocket;
  }

  const token = getToken();
  if (!token) {
    console.warn('No auth token available for WebSocket connection');
    return null;
  }

  // Close existing socket if any
  if (systemSocket) {
    systemSocket.disconnect();
  }

  // Create new socket connection
  systemSocket = io('/kubernetes', {
    auth: { token },
    transports: ['polling', 'websocket'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000,
  });

  systemSocket.on('connect', () => {
    console.log('System WebSocket connected');
    trackAction('ws /kubernetes connected');
  });

  systemSocket.on('connect_error', (err) => {
    console.error('System WebSocket connection error:', err.message);
    reportWsError({ message: `System WS connect error: ${err.message}`, namespace: '/kubernetes' });
  });

  systemSocket.on('disconnect', (reason) => {
    console.log('System WebSocket disconnected:', reason);
    trackAction(`ws /kubernetes disconnected: ${reason}`);
  });

  return systemSocket;
}

/**
 * Disconnect the system socket.
 */
export function disconnectSystemSocket(): void {
  if (systemSocket) {
    systemSocket.disconnect();
    systemSocket = null;
  }
}

// ── Notification Namespace ───────────────────────────────────────────────────

/**
 * Get or create the Socket.IO connection to /notifications namespace.
 * Used for real-time notification delivery to the authenticated user.
 */
export function getNotificationSocket(): Socket | null {
  if (!browser) return null;

  if (notificationSocket?.connected) {
    return notificationSocket;
  }

  const token = getToken();
  if (!token) return null;

  if (notificationSocket) {
    notificationSocket.disconnect();
  }

  notificationSocket = io('/notifications', {
    auth: { token },
    transports: ['polling', 'websocket'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 2000,
    reconnectionDelayMax: 15000,
  });

  notificationSocket.on('connect', () => {
    trackAction('ws /notifications connected');
  });

  notificationSocket.on('connect_error', (err) => {
    reportWsError({ message: `Notification WS error: ${err.message}`, namespace: '/notifications' });
  });

  return notificationSocket;
}

export function disconnectNotificationSocket(): void {
  if (notificationSocket) {
    notificationSocket.disconnect();
    notificationSocket = null;
  }
}

// ── Runs Namespace (validation + manufacturing) ─────────────────────────────

/**
 * Get or create the Socket.IO connection to /runs namespace.
 * Used for both validation and manufacturing run events.
 */
export function getRunSocket(): Socket | null {
  if (!browser) return null;

  if (runSocket?.connected) {
    return runSocket;
  }

  const token = getToken();
  if (!token) {
    console.warn('No auth token available for run WebSocket connection');
    return null;
  }

  // Close existing socket if any
  if (runSocket) {
    runSocket.disconnect();
  }

  // Create new socket connection
  runSocket = io('/runs', {
    auth: { token },
    transports: ['polling', 'websocket'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000,
  });

  runSocket.on('connect', () => {
    console.log('Run WebSocket connected');
    trackAction('ws /runs connected');
  });

  runSocket.on('connect_error', (err) => {
    console.error('Run WebSocket connection error:', err.message);
    reportWsError({ message: `Run WS connect error: ${err.message}`, namespace: '/runs' });
  });

  runSocket.on('disconnect', (reason) => {
    console.log('Run WebSocket disconnected:', reason);
    trackAction(`ws /runs disconnected: ${reason}`);
  });

  return runSocket;
}

/**
 * Disconnect the run socket.
 */
export function disconnectRunSocket(): void {
  if (runSocket) {
    runSocket.disconnect();
    runSocket = null;
  }
}

/** @deprecated Use getRunSocket */
export const getValidationSocket = getRunSocket;
/** @deprecated Use disconnectRunSocket */
export const disconnectValidationSocket = disconnectRunSocket;

/**
 * Subscribe to pod logs.
 */
export function subscribeLogs(
  subscription: LogSubscription,
  onLine: (line: string) => void,
  onError: (message: string) => void,
  onConnected?: () => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError('WebSocket not available');
    return () => {};
  }

  const lineHandler = (data: { line: string }) => {
    onLine(data.line);
  };

  const errorHandler = (data: { message: string }) => {
    onError(data.message);
  };

  const connectErrorHandler = (err: Error) => {
    onError(`Connection failed: ${err.message}`);
  };

  const disconnectHandler = (reason: string) => {
    if (reason !== 'io client disconnect') {
      onError(`Disconnected: ${reason}`);
    }
  };

  const connectHandler = () => {
    onConnected?.();
    // Emit subscribe after connection is established
    socket.emit('subscribe_logs', {
      namespace: subscription.namespace,
      pod: subscription.pod,
      container: subscription.container,
      tailLines: subscription.tailLines ?? 100,
    });
  };

  socket.on('log_line', lineHandler);
  socket.on('log_error', errorHandler);
  socket.on('connect_error', connectErrorHandler);
  socket.on('disconnect', disconnectHandler);

  // If already connected, subscribe immediately
  if (socket.connected) {
    onConnected?.();
    socket.emit('subscribe_logs', {
      namespace: subscription.namespace,
      pod: subscription.pod,
      container: subscription.container,
      tailLines: subscription.tailLines ?? 100,
    });
  } else {
    socket.on('connect', connectHandler);
  }

  // Return unsubscribe function
  return () => {
    socket.off('log_line', lineHandler);
    socket.off('log_error', errorHandler);
    socket.off('connect_error', connectErrorHandler);
    socket.off('disconnect', disconnectHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_logs', {
        namespace: subscription.namespace,
        pod: subscription.pod,
        container: subscription.container,
      });
    }
  };
}

/**
 * Start an exec session.
 */
export function startExec(
  session: ExecSession,
  onOutput: (data: string) => void,
  onExit: (code: number) => void,
  onError: (message: string) => void
): {
  sendInput: (data: string) => void;
  resize: (cols: number, rows: number) => void;
  stop: () => void;
} {
  const socket = getSystemSocket();
  if (!socket) {
    onError('WebSocket not available');
    return {
      sendInput: () => {},
      resize: () => {},
      stop: () => {},
    };
  }

  const outputHandler = (data: { data: string }) => {
    onOutput(data.data);
  };

  const exitHandler = (data: { code: number }) => {
    onExit(data.code);
  };

  const errorHandler = (data: { message: string }) => {
    onError(data.message);
  };

  socket.on('exec_output', outputHandler);
  socket.on('exec_exit', exitHandler);
  socket.on('exec_error', errorHandler);

  socket.emit('exec_start', {
    namespace: session.namespace,
    pod: session.pod,
    container: session.container,
    command: session.command ?? ['/bin/sh'],
  });

  return {
    sendInput: (data: string) => {
      socket.emit('exec_input', { data });
    },
    resize: (cols: number, rows: number) => {
      socket.emit('exec_resize', { cols, rows });
    },
    stop: () => {
      socket.off('exec_output', outputHandler);
      socket.off('exec_exit', exitHandler);
      socket.off('exec_error', errorHandler);
      socket.emit('exec_stop');
    },
  };
}

/**
 * Subscribe to live UART data from an MTIB node.
 * Filters events by portName so multiple ports can share one socket.
 */
export function subscribeUart(
  subscription: UartSubscription,
  onData: (data: string) => void,
  onError: (message: string) => void,
  onOpened?: () => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError('WebSocket not available');
    return () => {};
  }

  const { nodeId, portName } = subscription;

  const dataHandler = (event: { portName: string; data: string }) => {
    if (event.portName === portName) onData(event.data);
  };

  const errorHandler = (event: { portName: string; message: string }) => {
    if (event.portName === portName) onError(event.message);
  };

  const openedHandler = (event: { portName: string; streamId: string }) => {
    if (event.portName === portName) onOpened?.();
  };

  socket.on('uart_data', dataHandler);
  socket.on('uart_error', errorHandler);
  socket.on('uart_opened', openedHandler);

  const emitSubscribe = () => {
    socket.emit('subscribe_uart', {
      nodeId,
      portName,
      baud: subscription.baud ?? 115200,
    });
  };

  const connectHandler = () => {
    emitSubscribe();
  };

  if (socket.connected) {
    emitSubscribe();
  } else {
    socket.on('connect', connectHandler);
  }

  return () => {
    socket.off('uart_data', dataHandler);
    socket.off('uart_error', errorHandler);
    socket.off('uart_opened', openedHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_uart', { nodeId, portName });
    }
  };
}

// ── Run Subscriptions (validation + manufacturing) ──────────────────────────

export interface RunExecutionStartEvent {
  runId: string;
  name: string;
  testName?: string; // alias — backend emits "name"
  module: string | null;
  executionId: string;
  targetId?: string;
  testIndex?: number;
  totalTests?: number;
}

export interface RunExecutionResultEvent {
  runId: string;
  name: string;
  testName?: string; // alias — backend emits "name"
  module: string | null;
  passed: boolean;
  skipped?: boolean;
  durationMs: number | null;
  durationS?: number | null; // legacy alias
  errorMessage: string | null;
  measurements: Record<string, unknown> | null;
  logOutput: string | null;
  targetId?: string;
}

export interface RunFinishEvent {
  runId: string;
  status: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
  durationMs: number | null;
  durationS?: number | null; // legacy alias
}

export interface RunLogChunkEvent {
  runId: string;
  testName?: string;
  file: string;
  offset: number;
  data: string;  // base64 encoded
  chunk?: string; // raw text (alternative to base64)
  timestamp: number;
  targetId?: string;
  slotIndex?: number;
}

export interface TelemetrySample {
  t: number;       // POSIX timestamp (seconds, microsecond precision)
  type: string;    // "uart" | "power" | "accel" | ...
  target?: string; // "app" | "comms" (for UART)
  test?: string;   // test step name
  line?: string;   // UART line content
  mA?: number;     // power: current in milliamps
  mV?: number;     // power: voltage in millivolts
  [key: string]: unknown; // extensible for future sensor types
}

export interface RunTelemetryEvent {
  runId: string;
  samples: TelemetrySample[];
}

/** Backward-compat aliases */
export type ValidationTestStartEvent = RunExecutionStartEvent;
export type ValidationTestResultEvent = RunExecutionResultEvent;
export type ValidationRunFinishEvent = RunFinishEvent;
export type ValidationLogChunkEvent = RunLogChunkEvent;
export type TelemetryEvent = RunTelemetryEvent;

/**
 * Subscribe to real-time run events using the /runs namespace.
 * Works for both validation and manufacturing runs.
 * Uses room-based subscription for efficient event delivery.
 *
 * @param runId - The run ID to subscribe to
 * @param callbacks - Event handlers for execution and log events
 * @param onError - Optional error handler
 * @returns Cleanup function to unsubscribe
 */
export function subscribeRunWithLogs(
  runId: string,
  callbacks: {
    onTestStart?: (data: RunExecutionStartEvent) => void;
    onTestResult?: (data: RunExecutionResultEvent) => void;
    onRunFinish?: (data: RunFinishEvent) => void;
    onRunStart?: (data: { runId: string; status: string }) => void;
    onLogChunk?: (data: RunLogChunkEvent) => void;
    onTelemetry?: (data: RunTelemetryEvent) => void;
    onTestList?: (data: { runId: string; targetId?: string; tests: { name: string; module: string | null }[] }) => void;
  },
  onError?: (message: string) => void
): () => void {
  const socket = getRunSocket();
  if (!socket) {
    onError?.('Run WebSocket not available');
    return () => {};
  }

  // Event handlers - no need to filter by runId since we're in a room
  const runStartHandler = (data: { runId: string; status: string }) => {
    callbacks.onRunStart?.(data);
  };

  const testStartHandler = (data: RunExecutionStartEvent) => {
    callbacks.onTestStart?.(data);
  };

  const testResultHandler = (data: RunExecutionResultEvent) => {
    callbacks.onTestResult?.(data);
  };

  const runFinishHandler = (data: RunFinishEvent) => {
    callbacks.onRunFinish?.(data);
  };

  const logChunkHandler = (data: RunLogChunkEvent) => {
    callbacks.onLogChunk?.(data);
  };

  const telemetryHandler = (data: RunTelemetryEvent) => {
    callbacks.onTelemetry?.(data);
  };

  const testListHandler = (data: { runId: string; targetId?: string; tests: { name: string; module: string | null }[] }) => {
    callbacks.onTestList?.(data);
  };

  const errorHandler = (data: { message: string }) => {
    onError?.(data.message);
  };

  const subscribedHandler = (data: { runId: string }) => {
    console.log('Subscribed to run:', data.runId);
  };

  // Register handlers with new event names
  socket.on('run_start', runStartHandler);
  socket.on('run_execution_start', testStartHandler);
  socket.on('run_execution_result', testResultHandler);
  socket.on('run_finish', runFinishHandler);
  socket.on('run_log_chunk', logChunkHandler);
  socket.on('run_telemetry', telemetryHandler);
  socket.on('run_test_list', testListHandler);
  socket.on('error', errorHandler);
  socket.on('subscribed', subscribedHandler);

  // Subscribe to the run room
  const emitSubscribe = () => {
    socket.emit('subscribe_run', { runId });
  };

  const connectHandler = () => {
    emitSubscribe();
  };

  if (socket.connected) {
    emitSubscribe();
  } else {
    socket.on('connect', connectHandler);
  }

  // Return cleanup function
  return () => {
    socket.off('run_start', runStartHandler);
    socket.off('run_execution_start', testStartHandler);
    socket.off('run_execution_result', testResultHandler);
    socket.off('run_finish', runFinishHandler);
    socket.off('run_log_chunk', logChunkHandler);
    socket.off('run_telemetry', telemetryHandler);
    socket.off('run_test_list', testListHandler);
    socket.off('error', errorHandler);
    socket.off('subscribed', subscribedHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_run', { runId });
    }
  };
}

/** @deprecated Use subscribeRunWithLogs */
export const subscribeValidationRunWithLogs = subscribeRunWithLogs;

// ── CI Build Subscriptions ────────────────────────────────────

export interface CiBuildStartEvent {
  buildId: string;
  product: string;
  branch: string;
  status: string;
}

export interface CiBuildLogEvent {
  buildId: string;
  chunk: string;
}

export interface CiBuildCompleteEvent {
  buildId: string;
  status: string;
  durationSeconds: number | null;
  artifactCount: number;
}

export interface CiBuildRunStartEvent {
  runId: string;
  status: string;
}

export interface CiBuildRunStageUpdateEvent {
  runId: string;
  stage: string;
  status: string;
  detail: string | null;
}

export interface CiBuildRunCompleteEvent {
  runId: string;
  status: string;
  durationSeconds: number | null;
}

/**
 * Subscribe to real-time CI build events (log streaming, status changes).
 */
export function subscribeCiBuild(
  buildId: string,
  callbacks: {
    onStart?: (data: CiBuildStartEvent) => void;
    onLog?: (data: CiBuildLogEvent) => void;
    onComplete?: (data: CiBuildCompleteEvent) => void;
  },
  onError?: (message: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError?.('WebSocket not available');
    return () => {};
  }

  const startHandler = (data: CiBuildStartEvent) => {
    if (data.buildId === buildId) callbacks.onStart?.(data);
  };

  const logHandler = (data: CiBuildLogEvent) => {
    if (data.buildId === buildId) callbacks.onLog?.(data);
  };

  const completeHandler = (data: CiBuildCompleteEvent) => {
    if (data.buildId === buildId) callbacks.onComplete?.(data);
  };

  socket.on('ci_build_start', startHandler);
  socket.on('ci_build_log', logHandler);
  socket.on('ci_build_complete', completeHandler);

  return () => {
    socket.off('ci_build_start', startHandler);
    socket.off('ci_build_log', logHandler);
    socket.off('ci_build_complete', completeHandler);
  };
}

/**
 * Subscribe to real-time CI build run events (stage transitions, completion).
 */
export function subscribeCiBuildRun(
  runId: string,
  callbacks: {
    onStart?: (data: CiBuildRunStartEvent) => void;
    onStageUpdate?: (data: CiBuildRunStageUpdateEvent) => void;
    onComplete?: (data: CiBuildRunCompleteEvent) => void;
  },
  onError?: (message: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError?.('WebSocket not available');
    return () => {};
  }

  const startHandler = (data: CiBuildRunStartEvent) => {
    if (data.runId === runId) callbacks.onStart?.(data);
  };

  const stageHandler = (data: CiBuildRunStageUpdateEvent) => {
    if (data.runId === runId) callbacks.onStageUpdate?.(data);
  };

  const completeHandler = (data: CiBuildRunCompleteEvent) => {
    if (data.runId === runId) callbacks.onComplete?.(data);
  };

  socket.on('ci_build_run_start', startHandler);
  socket.on('ci_build_run_stage_update', stageHandler);
  socket.on('ci_build_run_complete', completeHandler);

  return () => {
    socket.off('ci_build_run_start', startHandler);
    socket.off('ci_build_run_stage_update', stageHandler);
    socket.off('ci_build_run_complete', completeHandler);
  };
}

// ── Run Log Streaming ───────────────────────────────────────────

export interface RunLogSubscription {
  runId: string;
  testName: string;
  file: string;
}

/** @deprecated Use RunLogSubscription */
export type ValidationLogSubscription = RunLogSubscription;

/**
 * Subscribe to real-time run log streaming for a specific test file.
 * Supports gap detection and recovery via offset tracking.
 *
 * @param subscription - Log file subscription details
 * @param onChunk - Callback for log chunks with offset info
 * @param onError - Optional error handler
 * @returns Cleanup function to unsubscribe
 */
export function subscribeRunLogs(
  subscription: RunLogSubscription,
  onChunk: (data: { offset: number; chunk: string }) => void,
  onError?: (message: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError?.('WebSocket not available');
    return () => {};
  }

  const { runId, testName, file } = subscription;

  const chunkHandler = (data: RunLogChunkEvent) => {
    // Filter to this specific file
    if (data.runId !== runId || data.testName !== testName || data.file !== file) {
      return;
    }

    // Decode base64 if needed, otherwise use raw chunk
    let chunk = data.chunk || '';
    if (data.data && !chunk) {
      try {
        chunk = atob(data.data);
      } catch {
        chunk = data.data;
      }
    }

    onChunk({ offset: data.offset, chunk });
  };

  const errorHandler = (data: { message: string }) => {
    onError?.(data.message);
  };

  socket.on('run_log_chunk', chunkHandler);
  socket.on('run_log_error', errorHandler);

  // Subscribe to log stream
  const emitSubscribe = () => {
    socket.emit('subscribe_run_logs', { runId, testName, file });
  };

  const connectHandler = () => {
    emitSubscribe();
  };

  if (socket.connected) {
    emitSubscribe();
  } else {
    socket.on('connect', connectHandler);
  }

  return () => {
    socket.off('run_log_chunk', chunkHandler);
    socket.off('run_log_error', errorHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_run_logs', { runId, testName, file });
    }
  };
}

/** @deprecated Use subscribeRunLogs */
export const subscribeValidationLogs = subscribeRunLogs;

// ── Manufacturing Run Subscriptions ─────────────────────────────

/**
 * Subscribe to real-time manufacturing run events.
 * Delegates to subscribeRunWithLogs, mapping the shared run events
 * (run_target_start, run_execution_result, run_target_result, run_finish)
 * into manufacturing-oriented callbacks.
 *
 * Each manufacturing panel scan creates a TestRun. Subscribe to individual
 * runs — not the session — because the backend reporter emits events on
 * room `run:{runId}`.
 */
export function subscribeManufacturingRun(
  runId: string,
  callbacks: {
    onTargetStart?: (data: { runId: string; targetId: string; slotIndex: number; serialNumber?: string }) => void;
    onExecutionResult?: (data: { runId: string; targetId: string; name: string; passed: boolean; durationMs?: number; errorMessage?: string; measurements?: Record<string, unknown> | null }) => void;
    onTargetResult?: (data: { runId: string; targetId: string; slotIndex: number; status: string; durationMs?: number }) => void;
    onRunFinish?: (data: RunFinishEvent) => void;
    onRunStart?: (data: { runId: string; status: string }) => void;
  },
  onError?: (message: string) => void
): () => void {
  return subscribeRunWithLogs(runId, {
    onTestStart: (data) => callbacks.onTargetStart?.({
      runId: data.runId || runId,
      targetId: data.targetId || '',
      slotIndex: 0,
      serialNumber: undefined,
    }),
    onTestResult: (data) => callbacks.onExecutionResult?.({
      runId: data.runId || runId,
      targetId: '',
      name: data.name || data.testName || '',
      passed: data.passed,
      durationMs: data.durationMs ?? undefined,
      errorMessage: data.errorMessage ?? undefined,
      measurements: data.measurements ?? undefined,
    }),
    onRunFinish: (data) => callbacks.onRunFinish?.(data),
    onRunStart: (data) => callbacks.onRunStart?.(data),
  }, onError);
}

/**
 * @deprecated Use subscribeManufacturingRun with individual run IDs.
 * This wrapper exists for backward compatibility but cannot subscribe to
 * session-level events — the backend emits events per run, not per session.
 */
export function subscribeManufacturingSession(
  _sessionId: string,
  _callbacks: Record<string, unknown>,
  onError?: (message: string) => void
): () => void {
  console.warn(
    'subscribeManufacturingSession is deprecated. Use subscribeManufacturingRun with individual run IDs.'
  );
  onError?.('subscribeManufacturingSession is deprecated — use subscribeManufacturingRun');
  return () => {};
}

/**
 * Disconnect the manufacturing socket.
 * @deprecated Use disconnectRunSocket — manufacturing now uses the shared /runs namespace.
 */
export const disconnectManufacturingSocket = disconnectRunSocket;
