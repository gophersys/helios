import { browser } from '$app/environment';
import { io, Socket } from 'socket.io-client';
import { getToken } from '$lib/api';
import type { ObservabilitySnapshot, AnalyzerSample } from '$lib/types/mtib';
import type { IcleUpdateEvent } from '$lib/types/icle';

let systemSocket: Socket | null = null;

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
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
  });

  systemSocket.on('connect', () => {
    console.log('System WebSocket connected');
  });

  systemSocket.on('connect_error', (err) => {
    console.error('System WebSocket connection error:', err.message);
  });

  systemSocket.on('disconnect', (reason) => {
    console.log('System WebSocket disconnected:', reason);
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

/**
 * Subscribe to MTIB observability updates (power, GPIO, ADC, system metrics).
 *
 * @param nodeId - MTIB node identifier
 * @param features - Array of features to observe: 'power', 'gpio', 'adc', 'system'
 * @param onUpdate - Callback for observability updates
 * @param onError - Optional error callback
 * @returns Cleanup function to unsubscribe
 */
export function subscribeMtibObservability(
  nodeId: string,
  features: string[],
  onUpdate: (data: ObservabilitySnapshot) => void,
  onError?: (error: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError?.('WebSocket not available');
    return () => {};
  }

  const updateHandler = (data: ObservabilitySnapshot) => {
    onUpdate(data);
  };

  const errorHandler = (event: { message: string }) => {
    onError?.(event.message);
  };

  socket.on('observability_update', updateHandler);
  socket.on('observability_error', errorHandler);

  const emitSubscribe = () => {
    socket.emit('subscribe_observability', {
      nodeId,
      features,
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
    socket.off('observability_update', updateHandler);
    socket.off('observability_error', errorHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_observability', { nodeId });
    }
  };
}

/**
 * Subscribe to logic analyzer capture streaming.
 * Receives sample chunks as they're captured.
 *
 * @param nodeId - MTIB node identifier
 * @param captureId - Unique capture session identifier
 * @param onSample - Callback for sample chunks
 * @param onComplete - Callback when capture completes
 * @param onError - Optional error callback
 * @returns Cleanup function to unsubscribe
 */
export function subscribeAnalyzer(
  nodeId: string,
  captureId: string,
  onSample: (data: { samples: AnalyzerSample[] }) => void,
  onComplete: (data: { status: string; totalSamples: number }) => void,
  onError?: (error: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError?.('WebSocket not available');
    return () => {};
  }

  const sampleHandler = (data: { samples: AnalyzerSample[] }) => {
    onSample(data);
  };

  const completeHandler = (data: { status: string; totalSamples: number }) => {
    onComplete(data);
  };

  const errorHandler = (event: { message: string }) => {
    onError?.(event.message);
  };

  socket.on('analyzer_sample_chunk', sampleHandler);
  socket.on('analyzer_complete', completeHandler);
  socket.on('analyzer_error', errorHandler);

  const emitSubscribe = () => {
    socket.emit('subscribe_analyzer', {
      nodeId,
      captureId,
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
    socket.off('analyzer_sample_chunk', sampleHandler);
    socket.off('analyzer_complete', completeHandler);
    socket.off('analyzer_error', errorHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_analyzer', { nodeId, captureId });
    }
  };
}

/**
 * Subscribe to ICLE device updates (status, power readings).
 *
 * @param deviceId - ICLE device identifier
 * @param onUpdate - Callback for device updates
 * @param onError - Optional error callback
 * @returns Cleanup function to unsubscribe
 */
export function subscribeIcle(
  deviceId: string,
  onUpdate: (data: IcleUpdateEvent) => void,
  onError?: (error: string) => void
): () => void {
  const socket = getSystemSocket();
  if (!socket) {
    onError?.('WebSocket not available');
    return () => {};
  }

  const updateHandler = (data: IcleUpdateEvent) => {
    if (data.deviceId === deviceId) {
      onUpdate(data);
    }
  };

  const errorHandler = (event: { deviceId: string; message: string }) => {
    if (event.deviceId === deviceId) {
      onError?.(event.message);
    }
  };

  socket.on('icle_update', updateHandler);
  socket.on('icle_error', errorHandler);

  const emitSubscribe = () => {
    socket.emit('subscribe_icle', { deviceId });
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
    socket.off('icle_update', updateHandler);
    socket.off('icle_error', errorHandler);
    socket.off('connect', connectHandler);
    if (socket.connected) {
      socket.emit('unsubscribe_icle', { deviceId });
    }
  };
}
